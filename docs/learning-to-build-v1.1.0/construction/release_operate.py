#!/usr/bin/env python3
"""Operate one registered raw test field from an identified research package.

The field is the first official test entry, fixed by the published metadata.
Only the raw DNA image is passed to the instrument. Agreement with its retained
prediction checks release operation, not a new scientific confirmation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

import data

ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--weights", required=True, type=Path)
    parser.add_argument("--incumbent-evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--origin", required=True, choices=("candidate", "downloaded-release"),
                        help="Identify whether this is a candidate-package gate or an actual downloaded release")
    args = parser.parse_args()
    require(args.output.is_absolute() and not args.output.exists(), "Choose a new absolute operation directory")
    protocol = json.loads((ROOT / "PROTOCOL-amendment-2.json").read_text())
    data.verify_archives(args.cache, protocol["data"]["archives"])
    name = data.metadata039(args.cache)["test"][0]
    field = Path(name).stem
    output = args.output.resolve()
    require(not output.is_relative_to(ROOT.parent), "Operate outside the canonical release source")
    output.mkdir(parents=True)
    started = time.perf_counter()
    with zipfile.ZipFile(data.archive_path(args.cache, "bbbc039_images")) as archive:
        member = data.by_stem(archive, (".tif", ".tiff", ".png"))[field]
        dna = output / ("dna" + Path(member).suffix)
        dna.write_bytes(archive.read(member))
    command = [sys.executable, "-B", str(ROOT / "incumbent.py"), "operate",
               "--task", "nuclei", "--weights", str(args.weights.resolve()),
               "--dna", str(dna), "--output", str(output / "operation")]
    with (output / "operation.log").open("w") as log:
        process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    require(process.returncode == 0, "Packaged instrument operation failed; inspect operation.log")
    masks = json.loads((args.incumbent_evidence / "source/test/MASKS.json").read_text())
    require(field in masks, "Registered release-operation field is missing from retained evidence")
    recorded = masks[field]
    expected = args.incumbent_evidence / "source/test" / recorded["path"]
    actual = output / "operation/labels.png"
    require(digest(expected) == recorded["sha256"], "Retained prediction identity differs")
    require(digest(actual) == recorded["sha256"], "Packaged operation differs from the retained prediction")
    receipt = {
        "schema": "learning-to-build/packaged-instrument-operation/v1", "status": "PASS",
        "source_origin": args.origin,
        "field": field, "selection": "First official BBBC039 test metadata entry, without score selection",
        "raw_input_sha256": digest(dna), "prediction_sha256": digest(actual),
        "operation_receipt_sha256": digest(output / "operation/OPERATION.json"),
        "actual_wall_seconds": time.perf_counter() - started,
        "reference_inputs_to_instrument": False, "prediction_matches_retained_bytes": True,
        "fields_operated": 1, "fresh_scientific_confirmation": False,
        "scope": "Actual fixed research-instrument operation from " + args.origin + " source; existing exposed field, not a new assay, customer acceptance or commercial qualification.",
    }
    (output / "RELEASE_OPERATION.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
