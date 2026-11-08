#!/usr/bin/env python3
"""Evaluate one frozen ordinary composition; stop if exposed calibration fails.

Uses the already executed specialist masks as an explicitly cached constituent.
Original constituent inference is attributed separately, never priced at zero.
An accepted candidate additionally requires a new real raw-input operation.
"""
from __future__ import annotations

import time

WALL_START, CPU_START = time.perf_counter(), time.process_time()

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
import traceback

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE))
import composition

support = composition.support


def evaluate_cohort(name, fields, registration, incumbent_root, cache, output):
    import numpy as np
    from PIL import Image
    import builder
    import check as checker
    import data
    import instrument
    cpu, wall = time.process_time(), time.perf_counter()
    relative = "successor/" + name
    for filename, expected in registration["retained_files_by_cohort"][name].items():
        path = incumbent_root / filename
        support.same(support.sha256(path), expected["sha256"], "cached constituent/" + filename)
        support.same(path.stat().st_size, expected["bytes"], "cached bytes/" + filename)
    masks = support.read_json(incumbent_root / relative / "MASKS.json")
    support.same(sorted(masks), sorted(fields), "cached field coverage/" + name)
    cases = data.load007(cache, fields)
    support.same([case.name for case in cases], fields, "exact cohort/" + name)
    rows, incumbent_rows, field_costs, historical_costs = [], [], [], []
    for case in cases:
        field_cpu, field_wall = time.process_time(), time.perf_counter()
        mask_record = masks[case.name]
        support.same(case.sources, mask_record["sources"], "constituent raw/reference source binding/" + case.name)
        support.same(builder.label_array_hash(case.truth), mask_record["reference_label_array_sha256"],
                     "reference identity/" + case.name)
        mask_path = incumbent_root / relative / mask_record["path"]
        support.same(support.sha256(mask_path), mask_record["sha256"], "constituent mask bytes/" + case.name)
        with Image.open(mask_path) as image:
            labels = np.asarray(image).copy()
        support.same(builder.label_array_hash(labels), mask_record["label_array_sha256"],
                     "constituent mask array/" + case.name)
        field_receipt = support.read_json(incumbent_root / relative / "fields" / (builder.field_slug(case.name) + ".json"))
        support.same(field_receipt["field"], case.name, "constituent field receipt")
        constituent_scores = checker.score(labels, case.truth)
        for key, value in constituent_scores.items():
            support.same(value, field_receipt["metrics"][key], "constituent score/" + case.name + "/" + key)
        incumbent_rows.append({"field": case.name, **constituent_scores})
        # Only measured raw-channel arrays and a verified raw-input prediction
        # enter compose; manual references are used solely below for scoring.
        predict_cpu, predict_wall = time.process_time(), time.perf_counter()
        prediction = composition.compose(case.dna, case.actin, labels)
        prediction_cost = support.elapsed(predict_cpu, predict_wall)
        score_cpu, score_wall = time.process_time(), time.perf_counter()
        metrics = builder.score_masks(prediction, case.truth)
        support.same(metrics, checker.score(prediction, case.truth), "separate repair score/" + case.name)
        scoring_cost = support.elapsed(score_cpu, score_wall)
        destination = Path(name) / "masks" / (builder.field_slug(case.name) + ".png")
        mask_sha = instrument.save_labels(output / destination, prediction)
        rows.append({"field": case.name, "candidate": registration["candidate_id"],
                     "height": int(prediction.shape[0]), "width": int(prediction.shape[1]), **metrics,
                     "label_array_sha256": builder.label_array_hash(prediction),
                     "mask_path": destination.as_posix(), "mask_sha256": mask_sha,
                     "cached_constituent_mask_sha256": mask_record["sha256"],
                     "reference_label_array_sha256": mask_record["reference_label_array_sha256"],
                     "reference_inputs_to_composition": False, "neural_inference_executed_in_this_call": False})
        field_costs.append({"field": case.name, "composition_segmentation": prediction_cost,
                           "producer_and_separate_scoring": scoring_cost,
                           "total_including_constituent_rescore": support.elapsed(field_cpu, field_wall)})
        historical_costs.append({"field": case.name,
            "segmentation_cpu_seconds": field_receipt["metrics"]["segmentation_cpu_seconds"],
            "scoring_cpu_seconds": field_receipt["metrics"]["scoring_cpu_seconds"],
            "actual_field_cpu_seconds": field_receipt["metrics"]["actual_cpu_seconds"],
            "actual_field_wall_seconds": field_receipt["metrics"]["actual_wall_seconds"],
            "source_receipt_sha256": support.sha256(incumbent_root / relative / "fields" / (builder.field_slug(case.name) + ".json"))})
    summary = builder.aggregate(rows)
    support.same(summary, checker.aggregate(rows), "separate repair aggregate/" + name)
    criteria = support.read_json(BASE / "PROTOCOL-amendment-2.json")["criteria"]
    gate = builder.qualifies(summary, "cells", criteria, heldout=name == "test")
    support.same(gate, checker.qualified(summary, "cells", criteria, heldout=name == "test"), "repair gate/" + name)
    incumbent_summary = builder.aggregate(incumbent_rows)
    builder.write_csv(output / name / "metrics.csv", rows)
    return {"cohort": name, "fields": fields, "rows": rows, "summary": summary,
            "numerical_cohort_gate_met": gate, "fixed_specialist_summary": incumbent_summary,
            "cached_constituent_source": "Registered executed incumbent final post-border cell masks; foreground is labels > 0.",
            "neural_inference_calls_in_this_evaluation": 0, "composition_segmentation_calls": len(cases),
            "independent_metric_implementation_matches": True,
            "historical_constituent_cost_attribution": historical_costs,
            "historical_cost_scope": "Already charged in original incumbent run. Attribute for lineage/full-route comparison; do not add to incremental execution or double-count in an edition total. Acquisition, model loading, training and human/billing costs are not fully allocated by these field times."}, {
                "total": support.elapsed(cpu, wall), "fields": field_costs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--incumbent", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--registration", type=Path, default=HERE / "PREREGISTRATION.json")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--expected", type=Path, default=HERE / "RESULTS.json")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    status = "FAILED"
    telemetry = {}
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        registration = support.read_json(args.registration)
        support.require(registration["status"] == "FROZEN_BEFORE_CANDIDATE_SCORING", "Candidate not frozen")
        composition.bind_source(registration)
        import numpy as np
        import scipy
        import skimage
        import PIL
        runtime = {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                   "scikit-image": skimage.__version__, "Pillow": PIL.__version__}
        support.same(runtime, registration["cached_evaluation_runtime"], "cached numeric runtime")
        for filename, expected in registration["archive_files"].items():
            support.same(support.sha256(args.cache / filename), expected["sha256"], "archive/" + filename)
        support.write_json(output / "INVOCATION.json", {"started_at_utc": started, "argv": sys.argv,
                           "registration_sha256": support.sha256(args.registration), "runtime_versions": runtime})
        calibration, telemetry["calibration"] = evaluate_cohort(
            "calibration", registration["calibration_fields"], registration, args.incumbent, args.cache, output)
        cohorts = {"calibration": calibration}
        if calibration["numerical_cohort_gate_met"]:
            test, telemetry["test"] = evaluate_cohort(
                "test", registration["conditionally_eligible_exposed_test_fields"], registration,
                args.incumbent, args.cache, output)
            cohorts["test"] = test
            status = "COMPLETED_NUMERICALLY_QUALIFIED" if test["numerical_cohort_gate_met"] else "COMPLETED_NEGATIVE_TEST"
        else:
            status = "COMPLETED_NEGATIVE_CALIBRATION_STOP"
        endpoints = {"status": status, "candidate_id": registration["candidate_id"], "cohorts": cohorts,
                     "candidate_completely_qualifies_on_exposed_cohorts": status == "COMPLETED_NUMERICALLY_QUALIFIED",
                     "test_fields_scored": len(cohorts["test"]["fields"]) if "test" in cohorts else 0,
                     "test_not_scored_reason": None if "test" in cohorts else "Frozen calibration gate failed; stop rule enforced.",
                     "new_raw_field_neural_operation_performed": False,
                     "candidate_provenance": "Assistant-authored ordinary composition, not learned by the registered six policies.",
                     "fresh_confirmation": False, "retained_learning_advantage": False}
        expected_match = None
        if args.verify:
            expected = support.read_json(args.expected)
            support.same(support.sha256(args.registration), expected["registration_sha256"], "expected candidate registration")
            support.same(endpoints, expected["numerical_endpoints"], "retained candidate endpoints")
            expected_match = True
        support.write_json(output / "RESULTS.json", {
            "schema": "learning-to-build/specialist-foreground-repair-results/v1",
            "registration_sha256": support.sha256(args.registration), "started_at_utc": started,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "numerical_endpoints": endpoints, "telemetry": telemetry,
            "expected_numerical_endpoints_verified": expected_match,
            "cost_scope": registration["cost_scope"]})
        print(json.dumps({"status": status, "output": str(output), "calibration_qualified": calibration["numerical_cohort_gate_met"],
                          "test_fields_scored": endpoints["test_fields_scored"],
                          "expected_numerical_endpoints_verified": expected_match}, sort_keys=True))
    except Exception as exc:
        status = "FAILED"
        support.write_json(output / "FAILURE.json", {"error": f"{type(exc).__name__}: {exc}",
                           "traceback": traceback.format_exc(), "telemetry_so_far": telemetry})
        raise
    finally:
        support.write_json(output / "PROCESS_COST.json", {
            "status": status, "started_at_utc": started,
            "ended_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "instrumented_process": support.elapsed(CPU_START, WALL_START),
            "process_cpu_seconds_including_startup": time.process_time(),
            "billing_usd": None, "human_seconds": None,
            "scope": "Current cached-constituent candidate evaluation, including source/input hashing, imports, decoding, constituent rescore, actual classical composition and separate score implementation. Historical neural inference is attributed separately, not rerun or double-counted."})


if __name__ == "__main__":
    main()
