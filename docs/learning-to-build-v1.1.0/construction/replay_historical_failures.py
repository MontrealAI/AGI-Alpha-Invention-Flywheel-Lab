#!/usr/bin/env python3
"""Reproduce the two preserved input failures on their exact source snapshots.

These focused operations exercise the original failure boundaries. They do not
recreate historical full-run receipts or recover the earlier local bundle.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent


def load_snapshot(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Preserve the existing failure-reproduction receipt")
    protocol = json.loads((ROOT / "PROTOCOL-amendment-2.json").read_text())
    cases = [
        ("original", protocol["data"]["bbbc007"]["calibration_ids"][0],
         "Manual outlines must be two-dimensional monochrome rasters with <=2 values"),
        ("amendment-1", protocol["data"]["bbbc007"]["test_ids"][0],
         "BBBC007 channel/reference shape mismatch"),
    ]
    receipts = []
    for number, (snapshot, field, expected) in enumerate(cases):
        path = ROOT / "registrations" / snapshot / "data.py"
        module = load_snapshot("ltb_historical_failure_" + str(number), path)
        module.verify_archives(args.cache, protocol["data"]["archives"])
        started, cpu = time.perf_counter(), time.process_time()
        try:
            module.load007(args.cache, [field])
        except ValueError as error:
            if expected not in str(error):
                raise
            receipts.append({
                "snapshot": snapshot, "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "field": field, "observed_error_type": type(error).__name__, "observed_error": str(error),
                "expected_failure_reproduced": True, "prediction_performed": False,
                "cpu_seconds": time.process_time() - cpu, "wall_seconds": time.perf_counter() - started,
            })
        else:
            raise ValueError("Historical source no longer reproduces its registered failure: " + snapshot)
    record = {
        "schema": "learning-to-build/focused-historical-failure-reproduction/v1", "status": "PASS",
        "cases": receipts, "historical_full_runs_recovered": False,
        "scope": "New focused replay of two input failures from preserved source. Earlier full operations, their CPU costs and original run-state hashes have not been recreated or relabeled.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps(record, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
