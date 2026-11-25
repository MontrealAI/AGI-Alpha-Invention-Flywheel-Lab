"""Reconstruct a diagnostic BJD_TDB clock and compare two independent ephemerides."""

import argparse
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import time

from astropy import __version__ as astropy_version, units as u
from astropy.coordinates import EarthLocation, SkyCoord
from astropy.time import Time
from astropy.utils import iers
import numpy as np


HERE = Path(__file__).resolve().parent
REGISTRATION = HERE / "CLOCK-REGISTRATION.json"
ROOT = HERE.parents[2]
C_KM_S = 299792.458
SECONDS_PER_DAY = 86400


def bound_bytes(source, expected):
    observed = source.read_bytes()
    if sha256(observed).hexdigest() != expected:
        raise ValueError("source bytes differ from the registered public evidence")
    return observed


def photometry(raw, station):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")), delimiter="\t")
    columns = np.array([[float(row["JD_UTC"]), float(row["BJD_TDB"])] for row in reader])
    if (
        len(columns) < 2 or not np.isfinite(columns).all() or not np.all(np.diff(columns[:, 0]) > 0)
        or np.min(columns[:, 0]) <= 2_400_000
    ):
        raise ValueError("UTC sample clock is not admissible")
    utc = Time(columns[:, 0], format="jd", scale="utc", location=station)
    return columns, utc


def horizon_geocenter(raw, tdb, direction):
    result = json.loads(raw)["result"]
    if any(label not in result for label in (
        "Target body name: Earth (399)", "Center body name: Solar System Barycenter (0)",
        "Reference frame : ICRF",
    )):
        raise ValueError("unregistered external ephemeris coordinate frame")
    start = result.index("$$SOE") + len("$$SOE")
    stop = result.index("$$EOE", start)
    ephemeris = np.array([[float(row[i]) for i in (0, 2, 3, 4)]
                          for row in csv.reader(result[start:stop].strip().splitlines())])
    if tdb.jd.min() < ephemeris[0, 0] or tdb.jd.max() > ephemeris[-1, 0]:
        raise ValueError("external ephemeris does not bracket the ground sample")
    projection = ephemeris[:, 1:] @ direction / C_KM_S
    return np.interp(tdb.jd, ephemeris[:, 0], projection)


def clocks(raw, raw_horizons, station, pointing):
    original, utc = photometry(raw, station)
    path = utc.light_travel_time(pointing, kind="barycentric", ephemeris="builtin")
    tdb = utc.tdb
    bjd = tdb + path
    external = horizon_geocenter(raw_horizons, tdb, pointing.cartesian.xyz.value)
    converted = bjd.jd
    discrepancy = abs(path.to_value(u.s) - external)
    return original, converted, {
        "rows": len(original), "zero_published_bjd": int(np.count_nonzero(original[:, 1] == 0)),
        "published_jd_utc_bounds": [float(original[0, 0]), float(original[-1, 0])],
        "reconstructed_bjd_tdb_bounds": [float(converted[0]), float(converted[-1])],
        "reconstructed_total_correction_seconds": [float(x) for x in
            ((converted - original[:, 0]).min() * SECONDS_PER_DAY,
             (converted - original[:, 0]).max() * SECONDS_PER_DAY)],
        "maximum_site_to_JPL_geocenter_difference_s": float(discrepancy.max()),
    }


def calculate(folder):
    start = time.perf_counter()
    raw_registration = REGISTRATION.read_bytes()
    config = json.loads(raw_registration)
    witness = json.loads((folder / "horizons-request.json").read_bytes())
    tess = config["tess_reference"]
    bound_bytes(ROOT / "publication/opportunity/science/RESULT.json", tess["source_sha256"])
    if astropy_version != config["astropy_version"]:
        raise ValueError("reproduce the pinned reference Astropy implementation")
    lon, lat, height = config["approximated_saao_geodetic"]
    ra, dec = config["target_icrs_degrees"]
    site = EarthLocation.from_geodetic(lon * u.deg, lat * u.deg, height * u.m)
    sky = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs")
    iers.conf.auto_download = False
    controls = {}
    for name, filename in (("missing", "2020.tbl"), ("control", "2023.tbl")):
        raw = bound_bytes(folder / filename, config["photometry"][name]["sha256"])
        secondary = bound_bytes(folder / (name + "-horizons.json"), witness[name]["sha256"])
        original, bjd, observed = clocks(raw, secondary, site, sky)
        if name == "control":
            if not np.all(original[:, 1] > 2_400_000):
                raise ValueError("positive comparator BJD_TDB values required")
            errors = abs(bjd - original[:, 1]) * SECONDS_PER_DAY
            observed["maximum_discrepancy_to_original_s"] = float(errors.max())
            observed["median_discrepancy_to_original_s"] = float(np.median(errors))
            observed["clock_control_qualified"] = bool(errors.max() <= 0.5)
        else:
            contact = tess["mid_bjd_tdb"] + tess["duration_hour"] / 48
            gap_hours = (bjd[0] - contact) * 24
            observed["tess_sector_27_nominal_last_contact_bjd_tdb"] = contact
            observed["first_sample_after_contact_hours"] = float(gap_hours)
            observed["minimum_gap_with_1000_s_margin_hours"] = float(gap_hours - 1000 / 3600)
        controls[name] = observed
    control_pass = controls["control"]["clock_control_qualified"] and all(
        value["maximum_site_to_JPL_geocenter_difference_s"] <= 0.05 for value in controls.values()
    )
    return {
        "schema": "frontier/toi216-barycentric-clock-reconciliation-v1",
        "registration_sha256": sha256(raw_registration).hexdigest(), "jpl_source_receipts": witness,
        "control_passed": control_pass, "visits": controls, "attribution": "ABSTAIN",
        "forecast": "ABSTAIN", "completion_scope": "Reproducible chronology. No new flux fit or physically independent confirmation.",
        "elapsed_seconds": round(time.perf_counter() - start, 6),
        "software": {"Astropy": astropy_version, "NumPy": np.__version__, "Horizons_ephemeris": "DE441"},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("captures", type=Path)
    args = parser.parse_args()
    print(json.dumps(calculate(args.captures), indent=2))
