"""Optional reconstruction of the registered astronomy result, without importing the product.

From the product directory:
  python -m pip install numpy==2.2.6 scipy==1.17.0 astropy==7.2.0 \
      pyerfa==2.0.1.5 astropy-iers-data==0.2026.11.16.0.37.44
  python -B field_trials/independent_sky.py --check field_trials/independent_sky_receipt.json
The reference uses packaged IERS data, builtin ephemerides and no network access.
"""
import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
from importlib.metadata import version
import itertools
import json
from pathlib import Path
import sys
import time

import astropy.units as u
from astropy.coordinates import AltAz, EarthLocation, SkyCoord, get_body, solar_system_ephemeris
from astropy.time import Time
from astropy.utils import iers
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp


HERE = Path(__file__).resolve().parent
INPUTS = ("mission.json", "catalog.json", "public.json", "sources/fink-alerts.json",
          "sources/fink-holdout.json", "sources/holdout-source.json")
PACKAGES = ("numpy", "scipy", "astropy", "pyerfa", "astropy-iers-data")


def check(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def archive(holdout, interval, targets, expected):
    observations = {name: [] for name in targets}
    seen = set()
    for row in holdout:
        key, name = row["i:candid"], row["i:objectId"]
        check(type(key) is int and key not in seen and name in targets
              and interval[0] <= row["i:jd"] < interval[1], "unexpected, duplicate or out-of-window observation")
        seen.add(key)
        if (row["i:isdiffpos"] in {"t","1"} and row["i:fid"] in {1,2,3}
                and row["i:magpsf"].is_finite() and row["i:sigmapsf"].is_finite() and row["i:sigmapsf"] > 0):
            observations[name].append(row)
    check(expected["max_gap_minutes"] == 120 and expected["targets"] == len(targets)
          and expected["public_rows"] == len(holdout), "archive scope mismatch")
    pairs = {}
    for name, records in observations.items():
        greens = [r for r in records if r["i:fid"] == 1]
        reds = [r for r in records if r["i:fid"] == 2]
        eligible = []
        for g,r in itertools.product(greens,reds):
            gap = abs(g["i:jd"] - r["i:jd"]) * 1440
            if gap <= 120:
                order = (gap,g["i:jd"],r["i:jd"],g["i:candid"],r["i:candid"])
                eligible.append((order,g,r))
        if eligible:
            order,g,r = min(eligible,key=lambda option: option[0])
            color = g["i:magpsf"] - r["i:magpsf"]
            sigma = (g["i:sigmapsf"]**2 + r["i:sigmapsf"]**2).sqrt()
            pairs[name] = (g,r,order[0],color,sigma)
    published = {row["target_id"]:row for row in expected["pairs"]}
    check(pairs.keys() == published.keys() and len(published) == len(expected["pairs"])
          and sorted(targets.keys() - pairs.keys()) == expected["missing_pair"], "two-band cohort mismatch")
    results = {}
    for name,(g,r,gap,color,sigma) in sorted(pairs.items()):
        out = published[name]
        for band,row in (("g",g),("r",r)):
            check(out[f"{band}_candid"] == str(row["i:candid"]), "detection identifier mismatch")
            for field,source in (("jd","i:jd"),("error_mag","i:sigmapsf"),("diff_mag","i:magpsf")):
                check(Decimal(str(out[f"{band}_{field}"])) == row[source], "photometric source value mismatch")
            unix_seconds = (row["i:jd"] - Decimal("2440587.5")) * 86400
            published_utc = datetime.fromisoformat(out[f"{band}_utc"].replace("Z","+00:00"))
            actual_utc = datetime(1970,1,1,tzinfo=timezone.utc) + timedelta(microseconds=int(unix_seconds*1_000_000))
            check(abs((published_utc - actual_utc).total_seconds()) <= .001, "photometric UTC mismatch")
        for key,value,digits in (("separation_minutes",gap,5),("g_minus_r_diff_mag",color,6),("formal_error_mag",sigma,6)):
            check(abs(Decimal(str(out[key])) - value) <= Decimal(5).scaleb(-digits-1), "photometry mismatch: "+key)
        results[name] = {"g_candid":str(g["i:candid"]), "r_candid":str(r["i:candid"]),
                         "separation_minutes":str(round(gap,7)), "g_minus_r_mag":str(round(color,6)),
                         "sigma_mag":str(round(sigma,6))}
    return {"retained_rows":len(holdout), "targets_with_detections":sum(bool(rs) for rs in observations.values()),
            "accepted_pairs":results, "missing_pair":sorted(targets.keys() - pairs.keys())}


def sky(mission, targets):
    starts = [datetime.fromisoformat(t.replace("Z","+00:00")) for t in mission["slots_utc"]]
    points = 60 * mission["duration_minutes"] + 1
    sampling = Time([start + timedelta(seconds=s) for start in starts for s in range(points)])
    site = mission["site"]
    observer = EarthLocation.from_geodetic(site["longitude_deg"]*u.deg,site["latitude_deg"]*u.deg,0*u.m)
    iers.conf.auto_download = False
    frame = AltAz(location=observer,obstime=sampling,pressure=0*u.hPa)
    with solar_system_ephemeris.set("builtin"):
        sun = get_body("sun",sampling,location=observer).transform_to(frame).alt.deg
    sun = sun.reshape(len(starts),points).max(axis=1)
    targets_min = {}
    for name,(ra,dec) in targets.items():
        target = SkyCoord(ra* u.deg, dec* u.deg, frame="icrs")
        target_angles = target.transform_to(frame).alt.deg.reshape(len(starts),points)
        targets_min[name] = target_angles.min(axis=1)
    eligible = {name:set(np.flatnonzero((sun <= mission["max_sun_alt_deg"] - mission["guard_deg"])
                                        & (alt >= mission["min_target_alt_deg"] + mission["guard_deg"])))
                for name,alt in targets_min.items()}
    return starts,sun,targets_min,eligible


def scheduling(mission,targets,starts,sun,alt,eligible,cases):
    by_case = {(c["visits"],c["budget"]): c for c in cases}
    nslots = len(starts)
    check(len(cases) == len(by_case) == 2*(nslots+1), "registered case denominator")
    outcomes = {}
    for visits in (1,2):
        bundles = []
        for name,available in eligible.items():
            for group in itertools.combinations(sorted(available),visits):
                if visits == 2:
                    a,b = (starts[i] for i in group)
                    if a.date()==b.date() or (b-a).total_seconds()<3600*mission["min_revisit_hours"]:
                        continue
                bundles.append((name,group))
        # One binary variable per possible target/cadence. Each target and each time has capacity 1.
        constraints = [[int(name==target) for name,_ in bundles] for target in targets]
        constraints += [[int(slot in group) for _,group in bundles] for slot in range(nslots)]
        constraints.append([visits]*len(bundles))
        outcomes[str(visits)] = []
        for budget in range(nslots+1):
            bounds = LinearConstraint(constraints,0,([1]*(len(targets)+nslots))+[budget])
            solution = milp(-np.ones(len(bundles)),integrality=np.ones(len(bundles)),
                            bounds=Bounds(0,1),constraints=bounds)
            check(solution.success and solution.mip_gap <= 1e-9, "MILP did not prove the finite optimum")
            optimum = round(-solution.fun)
            case = by_case[(visits,budget)]
            rows = case["slots"]
            check(optimum == case["objective"] == case["direct_objective"] and case["accepted"] is True
                  and len(rows) == visits*optimum and len(rows) <= budget, "registered objective differs")
            used,assigned = set(),{}
            for row in rows:
                name = row["target_id"]
                slot = mission["slots_utc"].index(row["utc"])
                check(slot not in used and slot in eligible[name] and targets[name] == (row["ra_deg"],row["dec_deg"])
                      and abs(row["max_sun_alt_deg"]-sun[slot])<=.1 and abs(row["min_alt_deg"]-alt[name][slot])<=.1,
                      "published pointing, angle or visibility mismatch")
                used.add(slot)
                assigned.setdefault(name,[]).append(slot)
            check(all((name,tuple(sorted(group))) in bundles for name,group in assigned.items()),"invalid visit cadence")
            outcomes[str(visits)].append(optimum)
    return outcomes


def observe(directory):
    contents = {name:(directory/name).read_bytes() for name in INPUTS}
    mission,catalog,public = [json.loads(contents[k]) for k in INPUTS[:3]]
    alerts = json.loads(contents["sources/fink-alerts.json"])
    targets = {a["i:objectId"]:(a["i:ra"],a["i:dec"]) for a in alerts}
    require_targets = {t["id"]:(t["ra_deg"],t["dec_deg"]) for t in catalog["targets"]}
    check(public["mission"] == mission and targets == require_targets and len(targets)==len(alerts),
          "frozen mission or target coordinates differ")
    check(sha(contents["sources/fink-alerts.json"]) == public["alerts_sha256"] == catalog["alerts_sha256"],
          "claimed alert source differs")
    desc = json.loads(contents["sources/holdout-source.json"],parse_float=Decimal)
    rows = json.loads(contents["sources/fink-holdout.json"],parse_float=Decimal)
    check(len(rows) == desc["retained_rows"],"held-out source denominator")
    if "projection_sha256" in desc:
        check(sha(contents["sources/fink-holdout.json"]) == desc["projection_sha256"],"held-out source identity")
    photo = archive(rows,desc["interval_jd"],targets,public["photometry"])
    starts,sun,alt,eligible = sky(mission,targets)
    result = scheduling(mission,targets,starts,sun,alt,eligible,public["cases"])
    ref = catalog["reference"]
    sun_delta = float(np.max(np.abs(sun - ref["max_sun_alt_deg"])))
    target_delta = max(float(np.max(np.abs(alt[n]-ref["min_alt_deg"][n]))) for n in targets)
    check(max(sun_delta,target_delta) < .1,"one-second ephemeris disagrees with reference grid")
    return {"schema":1,"method":"source decimals; topocentric get_body Sun; one-second AltAz; binary HiGHS MILP",
            "script_sha256":sha(Path(__file__).read_bytes()), "packages":{p:version(p) for p in PACKAGES},
            "input_sha256":{k:sha(v) for k,v in contents.items()}, "archival_photometry":photo,
            "geometry":{"offered_windows":len(starts),"sample_period_s":1,"fully_modeled":True,
                        "max_dense_vs_reference_sun_deg":round(sun_delta,7),
                        "max_dense_vs_reference_target_deg":round(target_delta,7)},
            "maximum_targets_by_visits_and_budget":result}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs",type=Path,default=HERE.parent/"invention")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check",type=Path,help="recalculate and compare the complete receipt")
    mode.add_argument("--out",type=Path,help="write a receipt at a new path")
    args = parser.parse_args()
    started = time.monotonic()
    receipt = observe(args.inputs)
    if args.check:
        check(receipt == json.loads(args.check.read_bytes()),"independent receipt or exact dependencies differ")
        print("Four archival products and fourteen observing decisions reproduced.")
    else:
        rendered = json.dumps(receipt,indent=2,ensure_ascii=False)+"\n"
        if args.out:
            with args.out.open("x") as dest:
                dest.write(rendered)
        else:
            print(rendered,end="")
    print(f"Reconstruction wall time {time.monotonic()-started:.3f} s",file=sys.stderr)
