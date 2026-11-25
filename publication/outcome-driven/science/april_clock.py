#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Replay the registered TOI-216 timing-convention controls on pinned public data."""

import argparse
import csv
from decimal import Decimal
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import re
import time

from astropy import __version__ as astropy_version, units as u
from astropy.coordinates import EarthLocation, SkyCoord
from astropy.time import Time, TimeDelta
from astropy.utils import iers
import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
C_KM_PER_S = 299792.458
SECS_DAY = 86400
MODES = (("JD", "utc"), ("JD", "tdb"), ("BJD", "utc"), ("BJD", "tdb"), ("HJD", "utc"), ("HJD", "tdb"))
DAYS_SHIFT = (Decimal(0), Decimal("-0.5"), Decimal("0.5"))


def checked_bytes(path, expected):
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError(f"Source hash did not match {path.name}")
    return raw


def vectors(raw, target):
    source = json.loads(raw)["result"]
    header, data = source.split("$$SOE", 1)
    required = (f"Target body name: {target}", "Center body name: Solar System Barycenter (0)",
                "Center-site name: BODY CENTER", "{source: DE441}", "Calendar Date (TDB)",
                "GEOMETRIC cartesian states")
    if not all(label in header for label in required) or not re.search(r"Output units\s*:\s*KM-S\b", header) \
            or not re.search(r"Reference frame\s*:\s*ICRF\b", header):
        raise ValueError("Horizons source frame, center, time system, units or body differs from registration")
    rows = csv.reader(StringIO(data.split("$$EOE", 1)[0].strip()))
    points = np.array([[float(row[i]) for i in (0, 2, 3, 4)] for row in rows])
    if len(points) < 2 or not np.isfinite(points).all() or not np.allclose(np.diff(points[:, 0]), 1 / 96, atol=2e-9, rtol=0):
        raise ValueError("Horizons vectors must be finite and have a strict registered 15-minute grid")
    return points


def vector_delay(earth, sun, direction, when, origin):
    if not earth[0, 0] <= when.tdb.jd <= earth[-1, 0]:
        raise ValueError("Horizons source does not bracket the evaluated event")
    points = earth[:, 1:] if origin == "BJD" else earth[:, 1:] - sun[:, 1:]
    return np.interp(when.tdb.jd, earth[:, 0], points @ direction) / C_KM_PER_S


def jd_time(value, scale):
    whole = int(value)
    return Time(whole, float(value - whole), scale=scale, format="jd")


def undo_origin(tag, origin, delay):
    """Recover the observation epoch from a geometrically corrected time."""
    geometric = tag
    for _ in range(6):
        corrected = tag - TimeDelta(delay(geometric, origin), format="sec")
        if abs((corrected - geometric).sec) < 0.001:
            return corrected
        geometric = corrected
    raise ValueError("Clock inversion did not converge within the registered bound")


def normalize(tag, origin, delay):
    geometric = tag.tdb if origin == "JD" else undo_origin(tag.tdb, origin, delay)
    return geometric + TimeDelta(delay(geometric, "BJD"), format="sec")


def calculate(directory):
    start = time.perf_counter()
    raw_reg = (HERE / "APRIL-REGISTRATION.json").read_bytes()
    reg = json.loads(raw_reg)
    frozen = {name: json.loads(checked_bytes(ROOT / name, digest)) for name, digest in reg["source_binding"].items()}
    source_record = frozen["publication/cascade/POST-REVEAL-INPUT.json"]["inner"]
    focal = Decimal(reg["focal_bjd_tdb"])
    if Decimal(str(source_record["catalogue_mid_bjd_tdb"])) != focal:
        raise ValueError("Disputed timing does not match the source ledger")
    events = frozen["publication/factory/TRANSIT.json"]["development"]["s64_measured"]
    data, receipts = {}, {}
    for body, name in (("earth", "Earth (399)"), ("sun", "Sun (10)")):
        receipt = json.loads((directory / f"{body}-receipt.json").read_bytes())
        raw = checked_bytes(directory / f"{body}.raw", receipt["sha256"])
        if receipt["status"] != 200 or receipt["bytes"] != len(raw):
            raise ValueError("Horizons receipt is inconsistent with capture")
        data[body], receipts[body] = vectors(raw, name), receipt
    earth, sun = data["earth"], data["sun"]
    if not np.array_equal(earth[:, 0], sun[:, 0]):
        raise ValueError("Earth and Sun vectors use different grids")
    sky = SkyCoord(ra=reg["object"]["icrs_ra_deg"] * u.deg, dec=reg["object"]["icrs_dec_deg"] * u.deg, frame="icrs")
    heading = sky.cartesian.xyz.value
    site = EarthLocation.from_geocentric(0, 0, 0, unit=u.m)
    iers.conf.auto_download = False

    def jpl(when, origin):
        return vector_delay(earth, sun, heading, when, origin)

    def conventional(when, origin):
        kind = "barycentric" if origin == "BJD" else "heliocentric"
        return when.light_travel_time(sky, kind=kind, location=site, ephemeris="builtin").to_value(u.s)

    gold = {f"{row['planet']}-{i}": (jd_time(Decimal(str(row["mid_bjd_tdb"])), "tdb"),
                                     max(row["timing_error_min"]) * 60) for i, row in enumerate(events)}
    tolerances = {name: max(120, 3 * ((source_record["catalogue_uncertainty_days"] * SECS_DAY) ** 2
                                      + error ** 2) ** 0.5) + 2 for name, (_, error) in gold.items()}
    rows = []
    for shift in DAYS_SHIFT:
        for origin, scale in MODES:
            time_tag = jd_time(focal + shift, scale)
            projected, comparison = normalize(time_tag, origin, jpl), normalize(time_tag, origin, conventional)
            rows.append({"clock": f"{origin}_{scale.upper()}", "noon_shift_days": float(shift),
                         "bjd_tdb": projected.jd, "geocentric_observation_utc": undo_origin(projected, "BJD", jpl).utc.isot,
                         "conventional_disagreement_s": abs((projected - comparison).sec),
                         "distance_to_frozen_centres_s": {name: abs((projected - centre).sec) for name, (centre, _) in gold.items()}})

    class_quality = max(row["conventional_disagreement_s"] for row in rows)
    geometry = jd_time(focal, "utc").tdb
    expected = normalize(geometry, "JD", jpl)
    checks = {}
    for origin, scale in MODES:
        tag = geometry if origin == "JD" else geometry + TimeDelta(jpl(geometry, origin), format="sec")
        forwarded = getattr(tag, scale)
        recovered = normalize(forwarded, origin, conventional)
        checks[f"{origin}_{scale.upper()}"] = abs((recovered - expected).sec)
    raw_earth = (directory / "earth.raw").read_bytes()
    corruptions = (
        lambda: vectors(raw_earth.replace(b"ICRF", b"ECLIPJ2000"), "Earth (399)"),
        lambda: vectors(raw_earth.replace(b"KM-S", b"AU-D"), "Earth (399)"),
        lambda: vectors(raw_earth, "Sun (10)"),
        lambda: jpl(jd_time(Decimal("2460050"), "tdb"), "BJD"),
    )
    rejected = 0
    for bad in corruptions:
        try:
            bad()
        except ValueError:
            rejected += 1
    passed = class_quality <= 0.1 and max(checks.values()) <= 0.1 and rejected == len(corruptions)
    minimum = {name: min(row["distance_to_frozen_centres_s"][name] for row in rows) for name in gold}
    canonical = {name: min(row["distance_to_frozen_centres_s"][name] for row in rows if row["noon_shift_days"] == 0) for name in gold}
    return {
        "schema": "frontier/toi216-april-clock-admission-v1", "registration_sha256": sha256(raw_reg).hexdigest(),
        "jpl_receipts": receipts,
        "vector_payload_sha256": {name: sha256(values.astype("<f8").tobytes()).hexdigest() for name, values in data.items()},
        "conventional": {"astropy": astropy_version, "numpy": np.__version__, "ephemeris": "builtin"},
        "geometric_delay_at_focal_if_jd_utc_s": {origin: jpl(geometry, origin) for origin in ("BJD", "HJD")},
        "normalizations": rows, "match_tolerance_s": tolerances, "minimum_without_noon_shift_s": canonical,
        "minimum_including_noon_shift_s": minimum, "maximum_independent_disagreement_s": class_quality,
        "synthetic_clock_roundtrip_errors_s": checks, "invalid_vector_controls_rejected": [rejected, len(corruptions)],
        "registered_common_clocks_explain_any_frozen_center": (any(minimum[name] <= tolerances[name] for name in gold) if passed else None),
        "attribution": "ABSTAIN", "forecast_adoption": "ABSTAIN", "physically_independent_confirmation": False,
        "elapsed_seconds": time.perf_counter() - start,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Directory containing earth.raw, sun.raw, and their source receipts")
    args = parser.parse_args()
    print(json.dumps(calculate(args.directory), indent=2, sort_keys=True))
