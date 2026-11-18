"""Narrow, source-bound test of what the stock nucleuswatch 1.2.0 view can prove.

No broker requests, credentials, accounting, scientific source rewriting, or live work.
This tests the upstream *public adapter's representation*, not a complete
nucleuswatch-plus-competent-analyst workflow.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import nucleuswatch
import pandas as pd
from nucleuswatch.brokers.alerce import parse as parse_alerce
from nucleuswatch.brokers.base import BrokerResult, lightcurve_frame
from nucleuswatch.core import MergedObject

EXPECTED_VERSION = "1.2.0"
WHEEL_SHA256 = "7c578e37ec958008424d02cef843d856f773c87ce4158186e19c836900403ed0"
UPSTREAM_COMMIT = "fe3b81da66c3bd24fdd0dd4942bb01e4e0a45018"
OWNER_SOURCE = "ffd8a0ebf1000173ca2446b9475be128463d6c17"
TARGET = "ZTF26acbezdh"
REQUIRED_PROVENANCE = ("rfid", "field", "rcid", "programid", "pid")


def synthetic_raw_detection(*, rfid: int = 1001, field: int = 505,
                            rcid: int = 58) -> dict:
    """One deliberately synthetic input: NOT an observed sky detection."""
    return {
        "mjd": 61341.25, "fid": 1, "magpsf": 16.260494,
        "sigmapsf": 0.04, "candid": "SYNTHETIC-CANDID",
        "rfid": rfid, "field": field, "rcid": rcid,
        "programid": 1, "pid": 2001,
    }


def stock_view(row: dict) -> pd.DataFrame:
    """Use the unmodified, installed upstream ALeRCE adapter."""
    return parse_alerce(TARGET, {}, [], {"detections": [row]}).lightcurve


def cross_broker_coverage_positive_control() -> dict:
    """The real stock interface *does* show an ALeRCE-only candidate ID."""
    shared = {"mjd": 61341.25, "band": "g", "mag": 16.260494,
              "mag_err": 0.04, "candid": "SYNTHETIC-CANDID"}
    other = {**shared, "mjd": 61341.26, "candid": "OTHER-CANDID"}
    obj = MergedObject(
        TARGET,
        results={
            "alerce": BrokerResult("alerce", TARGET,
                                   lightcurve=lightcurve_frame([shared, other], "alerce")),
            "fink": BrokerResult("fink", TARGET,
                                lightcurve=lightcurve_frame([other], "fink")),
        },
    )
    rows = obj.coverage()
    sole = rows[rows["candid"] == "SYNTHETIC-CANDID"]
    if len(sole) != 1:
        raise AssertionError("STOCK_CANDID_COVERAGE_UNEXPECTED")
    row = sole.iloc[0]
    if not bool(row["alerce"]) or bool(row["fink"]):
        raise AssertionError("STOCK_BROKER_COVERAGE_UNEXPECTED")
    return {"alerce_present": True, "fink_present": False,
            "meaning": "positive synthetically induced alert-coverage distinction"}


def probe(*, wheel_path: Path | None = None) -> dict:
    if nucleuswatch.__version__ != EXPECTED_VERSION:
        raise ValueError("UPSTREAM_VERSION_NOT_PINNED")
    if wheel_path is not None:
        if not wheel_path.is_file():
            raise FileNotFoundError("PINNED_WHEEL_MISSING")
        if hashlib.sha256(wheel_path.read_bytes()).hexdigest() != WHEEL_SHA256:
            raise ValueError("PINNED_WHEEL_DIGEST_MISMATCH")
    base = stock_view(synthetic_raw_detection())
    different_reference = stock_view(synthetic_raw_detection(rfid=9999))
    different_geometry = stock_view(synthetic_raw_detection(field=506, rcid=59))
    pd.testing.assert_frame_equal(base, different_reference, check_exact=True)
    pd.testing.assert_frame_equal(base, different_geometry, check_exact=True)
    missing = sorted(set(REQUIRED_PROVENANCE) - set(base.columns))
    if missing != sorted(REQUIRED_PROVENANCE):
        raise AssertionError("UPSTREAM_STOCK_SCHEMA_DIFFERS_FROM_FROZEN_HYPOTHESIS")
    if list(base["candid"]) != ["SYNTHETIC-CANDID"] or list(base["band"]) != ["g"]:
        raise AssertionError("STOCK_PHOTOMETRY_PRESERVATION_CONTROL_FAILED")
    return {
        "schema": "agi-alpha/ignition-stock-incumbent-interface/v1",
        "source": {"owner_source_sha": OWNER_SOURCE,
                   "upstream_commit": UPSTREAM_COMMIT,
                   "installed_nucleuswatch_version": nucleuswatch.__version__,
                   "verified_pypi_wheel_sha256": WHEEL_SHA256 if wheel_path else None},
        "fixture": "SYNTHETIC_ONLY_NO_PUBLIC_BROKER_RETRIEVAL",
        "stock_only": {
            "required_provenance_missing": missing,
            "reference_perturbation_indistinguishable": True,
            "field_and_rcid_perturbation_indistinguishable": True,
            "verdict": "INSUFFICIENT_SOURCE_FIELDS_FOR_SPECIFIC_REFERENCE_STREAM",
            "coverage_positive_control": cross_broker_coverage_positive_control(),
        },
        "competent_augmented_route": "NOT_EXECUTED_OR_DISQUALIFIED",
        "known_direct_raw_packet_control": "HISTORICAL_ONLY_NOT_REEXECUTED",
        "new_buyers": 0,
        "new_collected_revenue_usd": 0,
        "commerce_verdict": "UNQUALIFIED_NO_DEPLOY",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verified-wheel", type=Path,
                        help="Exact downloaded wheel to verify against registered digest")
    parser.add_argument("--output", type=Path,
                        help="Create-only JSON receipt path, otherwise print")
    args = parser.parse_args()
    result = probe(wheel_path=args.verified_wheel)
    body = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output is None:
        print(body, end="")
    else:
        with args.output.open("x", encoding="utf-8") as out:
            out.write(body)
        print(json.dumps({"receipt": str(args.output),
                          "sha256": hashlib.sha256(body.encode()).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
