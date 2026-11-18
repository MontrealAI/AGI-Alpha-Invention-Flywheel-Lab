"""Direct complete slot assignment and independent acceptance using Astropy ephemerides."""
import argparse
import itertools
import json
import math
from collections import defaultdict
from pathlib import Path

from geometry import digest, geometry_scope, validate


def exact_direct(mission, catalog):
    starts = validate(mission, catalog)
    ref = catalog.get("reference", {})
    if ref.get("scope_sha256") != geometry_scope(mission, catalog):
        raise ValueError("changed observer, target coordinates or windows require fresh reference")
    try:
        solar = ref["max_sun_alt_deg"]
        stars = ref["min_alt_deg"]
        names = sorted(t["id"] for t in catalog["targets"])
        vectors = [solar] + [stars[name] for name in names]
        if any(len(row) != len(starts) or any(type(x) not in (int, float) or not math.isfinite(x)
                                               or abs(x) > 90 for x in row) for row in vectors):
            raise ValueError("invalid reference angles")
    except (KeyError, TypeError) as exc:
        raise ValueError("incomplete reference angles") from exc
    feasible = []
    for i, sun in enumerate(solar):
        allowed = []
        for name in names:
            if (stars[name][i] >= mission["min_target_alt_deg"] + mission["guard_deg"]
                    and sun <= mission["max_sun_alt_deg"] - mission["guard_deg"]):
                allowed.append(name)
        feasible.append(allowed)

    # Enumerate the small offered calendar directly. The producer instead packs target bundles.
    best = []
    visits = mission["visits_per_target"]
    for assigned in itertools.product(*[[None] + ids for ids in feasible]):
        occupied = [(i, name) for i, name in enumerate(assigned) if name is not None]
        if len(occupied) > mission["max_slots"] or len(occupied) <= len(best):
            continue
        groups = defaultdict(list)
        for i, name in occupied:
            groups[name].append(starts[i])
        if any(len(times) != visits for times in groups.values()):
            continue
        if visits == 2 and any(times[0].date() == times[1].date() or
                               (times[1] - times[0]).total_seconds() < mission["min_revisit_hours"]*3600
                               for times in groups.values()):
            continue
        best = occupied
    return {"direct_objective": len(best) // visits,
            "assignments": [[mission["slots_utc"][i], n] for i, n in best]}, feasible


def verify(mission, catalog, plan):
    baseline, feasible = exact_direct(mission, catalog)
    if (plan.get("mission_sha256") != digest(mission) or plan.get("catalog_sha256") != digest(catalog)
            or plan.get("scope") != mission["scope"] or plan.get("dispatch_authorized") is not False):
        raise ValueError("worklist identity or authority differs")
    rows = plan.get("slots")
    if not isinstance(rows, list) or len(rows) > mission["max_slots"]:
        raise ValueError("invalid slot count")
    starts = validate(mission, catalog)
    by_time = {value: i for i, value in enumerate(mission["slots_utc"])}
    targets = {o["id"]: o for o in catalog["targets"]}
    seen = set()
    by_target = defaultdict(list)
    ref = catalog["reference"]
    try:
        for row in rows:
            t, name = row["utc"], row["target_id"]
            i = by_time[t]
            obj = targets[name]
            if name not in feasible[i] or i in seen:
                raise ValueError("infeasible or repeated observing slot")
            if (row["ra_deg"], row["dec_deg"]) != (obj["ra_deg"], obj["dec_deg"]):
                raise ValueError("pointing differs from public source")
            for key, expected in [("min_alt_deg", ref["min_alt_deg"][name][i]),
                                  ("max_sun_alt_deg", ref["max_sun_alt_deg"][i])]:
                reported = row[key]
                if type(reported) not in (float, int) or not math.isfinite(reported) or abs(reported-expected) > 0.1:
                    raise ValueError("reported geometry differs from independent reference")
            if (row["min_alt_deg"] < mission["min_target_alt_deg"] + mission["guard_deg"] or
                    row["max_sun_alt_deg"] > mission["max_sun_alt_deg"] - mission["guard_deg"]):
                raise ValueError("reported angles violate margin")
            seen.add(i)
            by_target[name].append(starts[i])
    except (KeyError, TypeError) as exc:
        raise ValueError("unknown target, slot or missing measurement") from exc
    for times in by_target.values():
        times.sort()
        if len(times) != mission["visits_per_target"]:
            raise ValueError("incomplete observing cadence")
        if len(times) == 2 and (times[0].date() == times[1].date() or
                               (times[1]-times[0]).total_seconds() < mission["min_revisit_hours"]*3600):
            raise ValueError("revisit does not meet mission")
    if (type(plan.get("objective")) is not int or plan["objective"] != len(by_target)
            or plan["objective"] != baseline["direct_objective"]):
        raise ValueError("claimed coverage differs from observed assignments or exact optimum")
    return {"accepted": True, "direct_objective": baseline["direct_objective"],
            "direct_assignments": baseline["assignments"], "scope": mission["scope"],
            "dispatch_authorized": False}


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("worklist", type=Path)
    p.add_argument("--mission", type=Path, default=here/"mission.json")
    p.add_argument("--catalog", type=Path, default=here/"catalog.json")
    args = p.parse_args()
    print(json.dumps(verify(*[json.loads(f.read_text()) for f in (args.mission, args.catalog, args.worklist)]),
                     indent=2))
