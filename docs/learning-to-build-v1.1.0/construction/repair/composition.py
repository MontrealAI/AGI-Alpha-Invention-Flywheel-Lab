#!/usr/bin/env python3
"""One supplied composition: specialist foreground and classical r12 watershed.

The prediction function receives raw channels and a raw-input specialist mask,
never manual references. The operation CLI executes the pinned incumbent first.
"""
from __future__ import annotations

import time

WALL_START, CPU_START = time.perf_counter(), time.process_time()

import argparse
import importlib.util
import json
from pathlib import Path
import resource
import subprocess
import sys
import traceback

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE))
spec = importlib.util.spec_from_file_location("ltb_diagnostic_support", BASE / "diagnostics/run.py")
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)


def bind_source(registration):
    for name, expected in registration["source_files"].items():
        support.same(support.sha256(BASE / name), expected["sha256"], "source/" + name)
        support.same((BASE / name).stat().st_size, expected["bytes"], "source-bytes/" + name)


def compose(dna, actin, specialist_labels):
    """Execute the single fixed candidate without reference data or selection."""
    import numpy as np
    import instrument
    labels = np.asarray(specialist_labels)
    support.require(labels.ndim == 2 and labels.shape == dna.shape == actin.shape
                    and labels.dtype.kind in "iu" and bool(np.all(labels >= 0)),
                    "Specialist labels must be a nonnegative integer image aligned with raw channels")
    return instrument.segment_cells(dna, actin, instrument.RECIPE_MAP["r12"],
                                    nucleus_labels=None, foreground_override=labels > 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dna", required=True, type=Path)
    parser.add_argument("--actin", required=True, type=Path)
    parser.add_argument("--weights", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--registration", type=Path, default=HERE / "PREREGISTRATION.json")
    parser.add_argument("--expected-specialist-mask", type=Path)
    parser.add_argument("--expected-composite-mask", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    child_start = resource.getrusage(resource.RUSAGE_CHILDREN)
    status = "FAILED"
    try:
        registration = support.read_json(args.registration)
        bind_source(registration)
        command = [sys.executable, "-B", str(BASE / "incumbent.py"), "operate", "--task", "cells",
                   "--weights", str(args.weights.resolve()), "--dna", str(args.dna.resolve()),
                   "--actin", str(args.actin.resolve()), "--output", str(output / "specialist")]
        with (output / "specialist.log").open("w") as log:
            process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        support.require(process.returncode == 0, "Pinned specialist operation failed; inspect specialist.log")
        import numpy as np
        from PIL import Image
        import builder
        import data
        import instrument
        inputs, arrays = {}, {}
        for name, path in (("dna", args.dna), ("actin", args.actin)):
            with Image.open(path) as image:
                raw = np.asarray(image).copy()
                mode = image.mode
            arrays[name], adapter = data.canonicalize_raw_pixels(raw, mode=mode)
            inputs[name] = {"sha256": support.sha256(path), "bytes": path.stat().st_size, "adapter": adapter}
        with Image.open(output / "specialist/labels.png") as image:
            labels = np.asarray(image).copy()
        prediction = compose(arrays["dna"], arrays["actin"], labels)
        mask_sha = instrument.save_labels(output / "labels.png", prediction)
        instrument.write_measurements(output / "measurements.csv", instrument.measurements(prediction))
        comparisons = {}
        for name, actual, expected in (("specialist", output / "specialist/labels.png", args.expected_specialist_mask),
                                       ("composite", output / "labels.png", args.expected_composite_mask)):
            if expected is not None:
                support.same(support.sha256(actual), support.sha256(expected), "expected raw-operation mask/" + name)
                comparisons[name] = True
        result = {"schema": "learning-to-build/specialist-foreground-composition-operation/v1",
                  "status": "OPERATED", "registration_sha256": support.sha256(args.registration),
                  "inputs": inputs, "child_command": command,
                  "specialist_operation_receipt_sha256": support.sha256(output / "specialist/OPERATION.json"),
                  "specialist_labels_sha256": support.sha256(output / "specialist/labels.png"),
                  "composition_labels_sha256": mask_sha,
                  "composition_label_array_sha256": builder.label_array_hash(prediction),
                  "measurements_sha256": support.sha256(output / "measurements.csv"),
                  "expected_mask_comparisons": comparisons, "reference_inputs_to_predictor": False,
                  "accuracy_on_supplied_images_established": False, "fresh_confirmation": False,
                  "authorship": "Assistant-authored ordinary composition of supplied operators and existing pretrained weights."}
        support.write_json(output / "OPERATION.json", result)
        status = "OPERATED"
        print(json.dumps({"status": status, "output": str(output), "expected_mask_comparisons": comparisons}, sort_keys=True))
    except Exception as exc:
        support.write_json(output / "FAILURE.json", {"error": f"{type(exc).__name__}: {exc}",
                                                     "traceback": traceback.format_exc()})
        raise
    finally:
        children = resource.getrusage(resource.RUSAGE_CHILDREN)
        child_cpu = children.ru_utime + children.ru_stime - child_start.ru_utime - child_start.ru_stime
        support.write_json(output / "PROCESS_COST.json", {
            "status": status, "parent_cpu_seconds": time.process_time() - CPU_START,
            "waited_child_cpu_seconds": child_cpu, "wall_seconds": time.perf_counter() - WALL_START,
            "billing_usd": None, "human_seconds": None,
            "scope": "Current parent and waited specialist process. Child OPERATION timings are components, not additional charges."})


if __name__ == "__main__":
    main()
