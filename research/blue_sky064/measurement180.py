"""Unverified external four-force intake for the frozen Blue Sky 178 contract.

This module NEVER authenticates a measurement, sensor, laboratory, physical effect,
buyer, compliance status, financial action or deployment. Synthetic tests only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import stat

from research.blue_sky064.observation178 import assess

INPUT_SCHEMA = "agi-alpha/blue-sky180-unverified-force-input/v1"
OUTPUT_SCHEMA = "agi-alpha/blue-sky180-conditional-measurement-report/v1"
REGISTRATION_SHA256 = "6eece869fb53ed7d6977a88b01ce0ba78af6a5d6931aea9df99c51b4c6f348fa"
ROOT = Path(__file__).resolve().parents[2]
REGISTRATION_PATH = ROOT / "campaign/blue-sky-064/friction-probe/MIXED_REGISTRATION.json"


def _regular_bytes(path: Path, maximum: int) -> bytes:
    """Read bounded source/input bytes; reject symlinks and nonregular entries."""
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("ABSOLUTE_NON_SYMLINK_REGULAR_INPUT_REQUIRED")
    if not path.is_file():
        raise ValueError("REGULAR_INPUT_REQUIRED")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= maximum:
        raise ValueError("BOUNDED_REGULAR_INPUT_REQUIRED")
    contents = path.read_bytes()
    if not 0 < len(contents) <= maximum or len(contents) != info.st_size:
        raise ValueError("INPUT_CHANGED_OR_OVERSIZED")
    return contents


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY_FORBIDDEN")
        result[key] = value
    return result


def _load_json(raw: bytes):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("STRICT_UTF8_JSON_REQUIRED") from exc


def _load_registration():
    raw = _regular_bytes(REGISTRATION_PATH, 100_000)
    if hashlib.sha256(raw).hexdigest() != REGISTRATION_SHA256:
        raise ValueError("REGISTERED_SOURCE_HASH_MISMATCH")
    registration = _load_json(raw)
    loads = registration["test_indentation_mm"]
    threshold = registration["necessary_construction_target"]["increase_in_static_dynamic_ratio_at_least"]
    if (registration["schema"] != "friction064/mixed-hold-slide-probe/v1"
            or loads != [0.01, 0.10] or threshold != 0.05):
        raise ValueError("REGISTERED_LOADS_OR_TARGET_CHANGED")
    return loads, threshold


def _parse_payload(payload, frozen_loads):
    if not isinstance(payload, dict) or set(payload) != {
            "schema", "indentation_mm", "force_readings_N",
            "absolute_force_error_bound_N", "measurement_authority"}:
        raise ValueError("EXACT_UNVERIFIED_FORCE_INPUT_SCHEMA_REQUIRED")
    if payload["schema"] != INPUT_SCHEMA or payload["measurement_authority"] != "UNVERIFIED_EXTERNAL_INPUT":
        raise ValueError("UNVERIFIED_INPUT_STATUS_REQUIRED")
    loads = payload["indentation_mm"]
    if (not isinstance(loads, dict) or set(loads) != {"low", "high"}
            or any(type(loads[k]) not in (int, float) or not math.isfinite(loads[k])
                   for k in ("low", "high"))
            or loads["low"] != frozen_loads[0] or loads["high"] != frozen_loads[1]):
        raise ValueError("EXACT_FROZEN_INDENTATIONS_REQUIRED")
    return payload["force_readings_N"], payload["absolute_force_error_bound_N"]


def interpret_unverified(path: Path) -> dict:
    """Return conditional mathematics, never acceptance of source observations."""
    frozen_loads, threshold = _load_registration()
    raw = _regular_bytes(path, 16_384)
    readings, epsilon = _parse_payload(_load_json(raw), frozen_loads)
    interval = assess(readings, epsilon, threshold)
    return {
        "schema": OUTPUT_SCHEMA,
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "source_registration_sha256": REGISTRATION_SHA256,
        "frozen_indentation_mm": {"low": frozen_loads[0], "high": frozen_loads[1]},
        "source_registered_threshold": threshold,
        "conditional_mathematical_assessment": interval,
        "source_type": "EXTERNAL_SUBMISSION_NOT_AUTHENTICATED",
        "physical_measurement_verified": False,
        "independent_force_error_calibration_verified": False,
        "beneficiary_acceptance_verified": False,
        "commercial_payment_verified": False,
        "financial_authority_or_account_action": False,
        "decision": "HOLD_NO_DEPLOY_UNVERIFIED_INPUT",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if (not args.output.is_absolute() or args.output.exists()
            or any(p.is_symlink() for p in (args.output, *args.output.parents))
            or not args.output.parent.is_dir()):
        raise SystemExit("NEW_ABSOLUTE_NON_SYMLINK_REPORT_REQUIRED")
    result = interpret_unverified(args.input)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, sort_keys=True, allow_nan=False)
        output.write("\n")
    print(json.dumps({"decision": result["decision"],
                      "conditional_math_verdict": result["conditional_mathematical_assessment"]["conditional_math_verdict"],
                      "physical_measurement_verified": False}, sort_keys=True))


if __name__ == "__main__":
    main()
