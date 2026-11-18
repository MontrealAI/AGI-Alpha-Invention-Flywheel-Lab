"""Regenerate the independent observer's ephemeris from public alerts with Astropy."""
import argparse
import hashlib
import importlib.metadata
import json
from datetime import timedelta
from pathlib import Path

from geometry import geometry_scope, utc


def targets_from_alerts(source):
    seen = {}
    for row in sorted(source, key=lambda r: (-r["i:jd"], r["i:objectId"])):
        seen.setdefault(row["i:objectId"], row)
    targets = []
    for row in list(seen.values())[:6]:
        targets.append({"id": row["i:objectId"], "ra_deg": row["i:ra"], "dec_deg": row["i:dec"],
                        "alert_jd": row["i:jd"], "reported_band": {1: "g", 2: "r", 3: "i"}[row["i:fid"]],
                        "reported_diff_mag": row["i:magpsf"], "reported_error_mag": row["i:sigmapsf"]})
    return targets


def make_reference(mission, catalog):
    import astropy.units as u
    from astropy.coordinates import AltAz, EarthLocation, SkyCoord, get_sun
    from astropy.time import Time
    from astropy.utils import iers

    iers.conf.auto_download = False
    site = EarthLocation.from_geodetic(mission["site"]["longitude_deg"]*u.deg,
                                       mission["site"]["latitude_deg"]*u.deg, 0*u.m)
    times = [utc(s) + timedelta(minutes=j) for s in mission["slots_utc"]
             for j in range(mission["duration_minutes"] + 1)]
    frames = AltAz(obstime=Time(times), location=site, pressure=0*u.hPa)
    sun = get_sun(frames.obstime).transform_to(frames).alt.deg
    size = mission["duration_minutes"] + 1
    slots = len(mission["slots_utc"])
    result = {"scope_sha256": geometry_scope(mission, catalog),
              "packages": {p: importlib.metadata.version(p) for p in ("astropy", "pyerfa", "astropy-iers-data")},
              "max_sun_alt_deg": [round(float(max(sun[i*size:(i+1)*size])), 6) for i in range(slots)],
              "min_alt_deg": {}}
    for obj in catalog["targets"]:
        coord = SkyCoord(ra=obj["ra_deg"]*u.deg, dec=obj["dec_deg"]*u.deg, frame="icrs")
        angles = coord.transform_to(frames).alt.deg
        result["min_alt_deg"][obj["id"]] = [
            round(float(min(angles[i*size:(i+1)*size])), 6) for i in range(slots)]
    return result


def construct_catalog(mission, raw):
    catalog = {"issuer": "Fink / Zwicky Transient Facility", "classification": "SLSN candidate",
               "selection_start_utc": "2026-10-25T00:00:00Z", "cutoff_utc": "2026-11-01T00:00:00Z",
               "alerts_sha256": hashlib.sha256(raw).hexdigest(),
               "source_url": "https://api.ztf.fink-portal.org/api/v1/latests?class=SLSN+candidate&n=100&startdate=2026-10-25&stopdate=2026-11-01&columns=i%3AobjectId%2Ci%3Ajd%2Ci%3Ara%2Ci%3Adec%2Ci%3Afid%2Ci%3Amagpsf%2Ci%3Asigmapsf&output-format=json",
               "targets": targets_from_alerts(json.loads(raw))}
    catalog["reference"] = make_reference(mission, catalog)
    return catalog


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    here = Path(__file__).resolve().parent
    parser.add_argument("--mission", type=Path, default=here / "mission.json")
    parser.add_argument("--alerts", type=Path, default=here / "sources/fink-alerts.json")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    catalog = construct_catalog(json.loads(args.mission.read_text()), args.alerts.read_bytes())
    args.out.write_text(json.dumps(catalog, indent=2) + "\n")
