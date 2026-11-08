#!/usr/bin/env python3
"""Frozen mechanism diagnostics on retained, already exposed calibration data.

The order experiment replays cached scores through builder.construct. It does
not rerun image inference or measure the original search cost. The factorial
experiment executes r12 on exactly four exposed BBBC007 calibration fields.
Every invocation writes a new output directory; --verify compares scientific
endpoints with the retained RESULTS.json while allowing new runtime telemetry.
"""
from __future__ import annotations

import time

WALL_START = time.perf_counter()
CPU_START = time.process_time()

import argparse
import copy
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import sys
import traceback

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
CONSTRUCTION = HERE.parent

INTEGER_METRICS = (
    "predicted_count", "reference_count", "tp", "fp", "fn",
    "reference_internal_boundary_pixels", "predicted_internal_boundary_pixels",
    "reference_foreground_pixels", "predicted_foreground_pixels", "matched_pair_count",
)
FLOAT_METRICS = (
    "instance_f1", "relative_count_error", "foreground_dice", "boundary_precision",
    "boundary_recall", "internal_boundary_f1", "matched_area_error_sum",
    "matched_area_relative_error", "matched_reference_fraction", "matched_predicted_fraction",
)
METRICS = INTEGER_METRICS + FLOAT_METRICS
REL_TOL = 1e-10
ABS_TOL = 1e-12


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def same(actual, expected, label):
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        require(type(actual) is type(expected) and actual == expected, f"Mismatch: {label}")
    elif isinstance(expected, int):
        require(type(actual) is int and actual == expected, f"Integer mismatch: {label}")
    elif isinstance(expected, float):
        require(type(actual) in (int, float) and math.isfinite(actual)
                and math.isclose(actual, expected, rel_tol=REL_TOL, abs_tol=ABS_TOL),
                f"Number mismatch: {label}: {actual!r} != {expected!r}")
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), f"List mismatch: {label}")
        for i, (a, e) in enumerate(zip(actual, expected)):
            same(a, e, f"{label}[{i}]")
    elif isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), f"Keys mismatch: {label}")
        for key in expected:
            same(actual[key], expected[key], f"{label}.{key}")
    else:
        raise ValueError(f"Unsupported comparison at {label}: {type(expected).__name__}")


def elapsed(cpu, wall):
    return {"cpu_seconds": time.process_time() - cpu,
            "wall_seconds": time.perf_counter() - wall}


def scientific_row(row):
    result = {key: row[key] for key in ("field", "recipe_id", "task", "label_array_sha256")}
    require(re.fullmatch(r"[0-9a-f]{64}", result["label_array_sha256"]) is not None,
            "Malformed prediction hash")
    for key in ("height", "width") + INTEGER_METRICS:
        result[key] = int(row[key])
    for key in FLOAT_METRICS:
        value = row[key]
        result[key] = None if value is None or value == "" else float(value)
        require(result[key] is None or math.isfinite(result[key]), f"Nonfinite metric: {key}")
    return result


def load_calibration(path, fields, recipe_ids):
    with Path(path).open(newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames is not None and len(reader.fieldnames) == len(set(reader.fieldnames)),
                "Missing or duplicate CSV header")
        rows = list(reader)
    indexed = {}
    for row in rows:
        require(None not in row and all(value is not None for value in row.values()), "Malformed CSV")
        require(row["task"] == "cells" and row["reference_inputs_used"] == "False",
                "Primary cached scores must be raw-input cell scores")
        parsed = scientific_row(row)
        key = (parsed["recipe_id"], parsed["field"])
        require(key not in indexed, "Duplicate recipe/field")
        indexed[key] = parsed
    require(set(indexed) == {(rid, field) for rid in recipe_ids for field in fields},
            "Calibration recipe/field coverage differs from registration")
    return indexed


def bind_inputs(registration, classical, cache):
    bindings = {}
    for name, expected in registration["source_files"].items():
        path = CONSTRUCTION / name
        same(sha256(path), expected["sha256"], "source/" + name)
        same(path.stat().st_size, expected["bytes"], "source-bytes/" + name)
        bindings["source/" + name] = expected
    for name, expected in registration["retained_files"].items():
        path = classical / name
        same(sha256(path), expected["sha256"], "retained/" + name)
        same(path.stat().st_size, expected["bytes"], "retained-bytes/" + name)
        bindings["retained/" + name] = expected
    for name, expected in registration["archive_files"].items():
        path = cache / name
        same(sha256(path), expected["sha256"], "archive/" + name)
        same(path.stat().st_size, expected["bytes"], "archive-bytes/" + name)
        bindings["archive/" + name] = expected
    return bindings


def order_diagnostic(registration, classical, output, builder, checker, instrument, criteria):
    cpu, wall = time.process_time(), time.perf_counter()
    fields, recipe_ids = registration["calibration_fields"], registration["recipe_ids"]
    orders = read_json(classical / "donor/orders.json")
    arms = registration["observed_arms"]
    require(set(orders) == set(arms), "Unexpected observed arm set")
    cached = {}
    for arm in arms:
        cached[arm] = load_calibration(classical / "successor" / arm / "calibration.csv", fields, recipe_ids)
    reference = cached["full_enumeration"]
    identity = {}
    for arm in arms:
        for key, row in reference.items():
            same(cached[arm][key], row, f"cached scientific identity/{arm}/{key}")
        identity[arm] = {"recipe_field_rows_matched": len(reference),
                         "prediction_hashes_exact": True, "scientific_metrics_match": True}
    candidates = {}
    for rid in recipe_ids:
        rows = [reference[(rid, field)] for field in fields]
        summary = builder.aggregate(rows)
        same(summary, checker.aggregate(rows), "independent cached aggregate/" + rid)
        accepted = builder.qualifies(summary, "cells", criteria)
        same(accepted, checker.qualified(summary, "cells", criteria), "cached gate/" + rid)
        candidates[rid] = {"summary": summary, "calibration_qualified": accepted}

    expert = orders["fixed_no_history"]
    interventions = [("observed__" + arm, orders[arm], arm == "full_enumeration") for arm in arms]
    interventions += [("reverse_expert", list(reversed(expert)), False),
                      ("lexical", sorted(recipe_ids), False),
                      ("reverse_lexical", sorted(recipe_ids, reverse=True), False)]
    interventions += [(f"cyclic_expert_{offset:02d}", expert[offset:] + expert[:offset], False)
                      for offset in range(len(recipe_ids))]
    same(len(interventions), registration["order_intervention_count"], "order intervention count")
    endpoints, timings = [], []
    original_evaluate = builder.evaluate
    calls = []

    def replay_evaluate(recipe, task, cases, retain=None, artifact=None, direct_artifact=False, oracle=False):
        require(task == "cells" and list(cases) == fields and retain is None and artifact is None
                and not direct_artifact and not oracle, "Unexpected cached replay evaluator call")
        calls.append(recipe.id)
        rows = [copy.deepcopy(reference[(recipe.id, field)]) for field in fields]
        # Original inference/scoring times are deliberately not copied into these
        # replay rows. Their sunk cost remains in the original evidence ledger.
        for row in rows:
            row["evaluation_origin"] = "cached-score-order-replay-no-image-inference"
        return rows, copy.deepcopy(candidates[recipe.id]["summary"])

    try:
        builder.evaluate = replay_evaluate
        for name, order, exhaustive in interventions:
            calls.clear()
            result = builder.construct(order, fields, criteria, output / "order_raw" / name,
                                       exhaustive=exhaustive, artifact_path=None)
            same(calls, result["executed_order"], "actual adapter calls/" + name)
            if name.startswith("observed__"):
                arm = name.removeprefix("observed__")
                old = read_json(classical / "successor" / arm / "construction.json")
                for key in ("selected_recipe_id", "calibration_candidates_executed", "calibration_qualified",
                            "calibration_field_evaluations", "executed_order", "calibration"):
                    same(result[key], old[key], f"retained construction endpoint/{arm}/{key}")
            endpoints.append({"intervention": name, "proposed_order": list(order), "exhaustive": exhaustive,
                              "executed_order": list(calls), "selected_recipe_id": result["selected_recipe_id"],
                              "candidate_evaluations": result["calibration_candidates_executed"],
                              "calibration_field_evaluations": result["calibration_field_evaluations"],
                              "calibration_qualified": result["calibration_qualified"],
                              "selected_calibration": result["calibration"], "image_inference_calls": 0})
            timings.append({"intervention": name, "cpu_seconds": result["actual_construction_cpu_seconds"],
                            "wall_seconds": result["actual_construction_wall_seconds"]})
    finally:
        builder.evaluate = original_evaluate
    result = {"kind": "cached-score-control-flow-replay", "original_arm_scientific_identity": identity,
              "observed_distinct_orders": len({tuple(order) for order in orders.values()}),
              "intervention_distinct_orders": len({tuple(order) for _, order, _ in interventions}),
              "candidate_summaries": candidates, "runs": endpoints,
              "accepted_candidates_in_shared_bank": sum(row["calibration_qualified"] for row in candidates.values()),
              "selected_recipe_ids": sorted({row["selected_recipe_id"] for row in endpoints}),
              "all_interventions_exhaust_bank": all(row["candidate_evaluations"] == len(recipe_ids) for row in endpoints),
              "actual_builder_construct_calls": len(endpoints),
              "actual_cached_evaluator_calls": sum(row["candidate_evaluations"] for row in endpoints),
              "artifact_execution_replayed": False, "fresh_confirmation": False}
    return result, {"total": elapsed(cpu, wall), "construction_calls": timings}, reference


def factorial_diagnostic(registration, cache, output, builder, checker, instrument, data, criteria, cached):
    cpu, wall = time.process_time(), time.perf_counter()
    fields = registration["calibration_fields"]
    load_cpu, load_wall = time.process_time(), time.perf_counter()
    cases = data.load007(cache, fields)
    require([case.name for case in cases] == fields, "Loader did not preserve exact four-field cohort")
    loading = elapsed(load_cpu, load_wall)
    recipe = instrument.RECIPE_MAP[registration["fixed_recipe"]]
    sources = {case.name: {"sources": case.sources, "decoder_diagnostics": case.decoder_diagnostics,
                           "cell_reference_label_array_sha256": builder.label_array_hash(case.truth),
                           "nucleus_reference_label_array_sha256": builder.label_array_hash(case.nucleus_truth)}
               for case in cases}
    conditions = [("raw_raw", False, False), ("reference_seeds", True, False),
                  ("reference_foreground", False, True), ("reference_both", True, True)]
    endpoints, timings = {}, {}
    for name, reference_seeds, reference_foreground in conditions:
        condition_cpu, condition_wall = time.process_time(), time.perf_counter()
        rows, per_field = [], []
        for case in cases:
            field_cpu, field_wall = time.process_time(), time.perf_counter()
            prediction = instrument.segment_cells(
                case.dna, case.actin, recipe,
                nucleus_labels=case.nucleus_truth if reference_seeds else None,
                foreground_override=case.truth > 0 if reference_foreground else None,
            )
            prediction_cost = elapsed(field_cpu, field_wall)
            score_cpu, score_wall = time.process_time(), time.perf_counter()
            metrics = builder.score_masks(prediction, case.truth)
            same(metrics, checker.score(prediction, case.truth), f"separate scorer/{name}/{case.name}")
            scoring_cost = elapsed(score_cpu, score_wall)
            mask_path = Path("factorial") / name / "masks" / (builder.field_slug(case.name) + ".png")
            mask_sha = instrument.save_labels(output / mask_path, prediction)
            row = {"field": case.name, "recipe_id": recipe.id, "task": "cells",
                   "height": int(prediction.shape[0]), "width": int(prediction.shape[1]),
                   **metrics, "label_array_sha256": builder.label_array_hash(prediction),
                   "mask_path": mask_path.as_posix(), "mask_sha256": mask_sha,
                   "reference_seeds": reference_seeds, "reference_foreground": reference_foreground,
                   "independent_metric_implementation_matches": True}
            rows.append(row)
            per_field.append({"field": case.name, "segmentation": prediction_cost,
                              "producer_and_separate_scoring": scoring_cost, "total": elapsed(field_cpu, field_wall)})
        summary = builder.aggregate(rows)
        same(summary, checker.aggregate(rows), "separate aggregate/" + name)
        gate = builder.qualifies(summary, "cells", criteria)
        same(gate, checker.qualified(summary, "cells", criteria), "separate gate/" + name)
        endpoints[name] = {"reference_seeds": reference_seeds, "reference_foreground": reference_foreground,
                           "rows": rows, "summary": summary, "numerical_calibration_gate_met": gate,
                           "complete_raw_channel_qualification": False}
        builder.write_csv(output / "factorial" / name / "metrics.csv", rows)
        timings[name] = {"total": elapsed(condition_cpu, condition_wall), "fields": per_field}

    # Controls are evaluated before interpreting any component effects. The
    # retained baseline has four historical calibration rows. No historical
    # combined-reference calibration output exists, so that control executes
    # the unchanged producer now; it is not represented as archived evidence.
    for row in endpoints["raw_raw"]["rows"]:
        same(scientific_row(row), cached[(recipe.id, row["field"])], "retained baseline/" + row["field"])
    controls = {}
    for name, oracle in (("raw_raw", False), ("reference_both", True)):
        control_cpu, control_wall = time.process_time(), time.perf_counter()
        rows, summary = builder.evaluate(recipe, "cells", cases,
                                         retain=output / "producer_controls" / name, oracle=oracle)
        builder.write_csv(output / "producer_controls" / name / "metrics.csv", rows)
        require(len(rows) == len(fields), "Producer control returned wrong field count")
        for direct, old in zip(endpoints[name]["rows"], rows):
            same(scientific_row(direct), scientific_row(old), f"unchanged producer/{name}/{direct['field']}")
            same(direct["mask_sha256"], old["mask_sha256"], "producer-control encoded mask/" + direct["field"])
        same(endpoints[name]["summary"], summary, "unchanged producer aggregate/" + name)
        controls[name] = {"call": "builder.evaluate", "oracle_argument": oracle,
                          "fields": len(rows), "prediction_hashes_exact": True, "metrics_match": True,
                          "historically_retained_calibration_scores_available": name == "raw_raw"}
        timings["producer_control__" + name] = elapsed(control_cpu, control_wall)

    deltas = {}
    for metric in builder.MEAN_METRICS:
        key = "mean_" + metric
        base = endpoints["raw_raw"]["summary"][key]
        seeds = endpoints["reference_seeds"]["summary"][key]
        foreground = endpoints["reference_foreground"]["summary"][key]
        both = endpoints["reference_both"]["summary"][key]
        deltas[key] = {"reference_seeds_minus_baseline": seeds - base,
                       "reference_foreground_minus_baseline": foreground - base,
                       "reference_both_minus_baseline": both - base,
                       "interaction_both_minus_seeds_minus_foreground_plus_baseline": both - seeds - foreground + base}
    return {"kind": "exposed-calibration-reference-input-component-diagnostic", "fixed_recipe": recipe.id,
            "calibration_fields": fields, "field_count": len(cases), "source_receipts": sources,
            "conditions": endpoints, "unchanged_producer_controls": controls,
            "baseline_matches_retained_calibration": True, "mean_metric_differences": deltas,
            "actual_segmentation_calls": len(cases) * (len(conditions) + len(controls)),
            "separately_implemented_metric_scores": len(cases) * len(conditions),
            "target_test_fields_decoded": 0, "fresh_confirmation": False,
            "raw_input_successor_qualification_established": False,
            "scope": "Branch interventions: the raw-foreground branch unions its mask with supplied seeds, so replacing seeds can also change that foreground. This is not an isolated biological causal estimate."}, {
                "data_loading": loading, "conditions_and_controls": timings, "total": elapsed(cpu, wall)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--classical", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--registration", type=Path, default=HERE / "PREREGISTRATION.json")
    parser.add_argument("--verify", action="store_true", help="Compare all frozen scientific endpoints with --expected")
    parser.add_argument("--expected", type=Path, default=HERE / "RESULTS.json")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    status = "FAILED"
    start_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    telemetry = {}
    try:
        registration = read_json(args.registration)
        require(registration["schema"] == "learning-to-build/exposed-mechanism-diagnostic-registration/v1",
                "Unsupported diagnostic registration")
        require(registration["status"] == "FROZEN_BEFORE_DIAGNOSTIC_EXECUTION", "Registration is not frozen")
        same(registration["numerical_tolerance"], {"relative": REL_TOL, "absolute": ABS_TOL}, "tolerance")
        inputs = bind_inputs(registration, args.classical.resolve(), args.cache.resolve())
        sys.path.insert(0, str(CONSTRUCTION))
        import numpy as np
        import scipy
        import skimage
        import PIL
        import builder
        import check as checker
        import data
        import instrument
        runtime = {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                   "scikit-image": skimage.__version__, "Pillow": PIL.__version__}
        same(runtime, registration["runtime_versions"], "registered runtime")
        protocol = read_json(CONSTRUCTION / "PROTOCOL-amendment-2.json")
        same(protocol["data"]["bbbc007"]["calibration_ids"], registration["calibration_fields"], "frozen calibration")
        require(not set(registration["calibration_fields"]) & set(protocol["data"]["bbbc007"]["test_ids"]),
                "Diagnostic would touch the target test cohort")
        same(list(instrument.RECIPE_MAP), registration["recipe_ids"], "recipe bank")
        same(instrument.bank_hash(), registration["recipe_bank_sha256"], "recipe bank identity")
        write_json(output / "INVOCATION.json", {"started_at_utc": start_utc, "argv": sys.argv,
                    "registration_sha256": sha256(args.registration), "runtime_versions": runtime,
                    "input_hashes": inputs, "fresh_scientific_confirmation": False})
        order, telemetry["order_replay"], cached = order_diagnostic(
            registration, args.classical.resolve(), output, builder, checker, instrument, protocol["criteria"])
        factorial, telemetry["factorial"] = factorial_diagnostic(
            registration, args.cache.resolve(), output, builder, checker, instrument, data, protocol["criteria"], cached)
        endpoints = {"order_replay": order, "factorial": factorial}
        expected_match = None
        if args.verify:
            expected = read_json(args.expected)
            same(sha256(args.registration), expected["registration_sha256"], "expected registration identity")
            same(endpoints, expected["numerical_endpoints"], "retained numerical endpoints")
            expected_match = True
        scientific_files = {path.relative_to(output).as_posix(): {"sha256": sha256(path), "bytes": path.stat().st_size}
                            for path in sorted(output.rglob("*")) if path.is_file()}
        write_json(output / "OUTPUT_INVENTORY.json", scientific_files)
        telemetry["process_until_result"] = elapsed(CPU_START, WALL_START)
        result = {"schema": "learning-to-build/exposed-mechanism-diagnostic-results/v1", "status": "COMPLETE",
                  "registration_sha256": sha256(args.registration), "started_at_utc": start_utc,
                  "completed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "runtime_versions": runtime, "input_bindings": inputs, "numerical_endpoints": endpoints,
                  "telemetry": telemetry, "expected_numerical_endpoints_verified": expected_match,
                  "claims": {"fresh_scientific_confirmation": False, "new_raw_input_capability": False,
                             "retained_learning_advantage": False, "complete_cost_savings": False},
                  "cost_scope": registration["cost_scope"]}
        write_json(output / "RESULTS.json", result)
        status = "COMPLETE"
        print(json.dumps({"status": status, "output": str(output), "order_replays": len(order["runs"]),
                          "selected_recipes": order["selected_recipe_ids"], "segmentation_calls": factorial["actual_segmentation_calls"],
                          "expected_numerical_endpoints_verified": expected_match}, sort_keys=True))
    except Exception as exc:
        write_json(output / "FAILURE.json", {"schema": "learning-to-build/diagnostic-failure/v1",
                   "started_at_utc": start_utc, "error": f"{type(exc).__name__}: {exc}",
                   "traceback": traceback.format_exc(), "telemetry_so_far": telemetry,
                   "process_until_failure": elapsed(CPU_START, WALL_START)})
        raise
    finally:
        write_json(output / "PROCESS_COST.json", {"status": status, "started_at_utc": start_utc,
                   "ended_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "instrumented_process": elapsed(CPU_START, WALL_START),
                   "process_cpu_seconds_including_startup": time.process_time(),
                   "measurement_scope": "Current process including numerical imports, source/input hashing, cached replay, image decoding, all segmentation/control/scoring calls, and output preparation. Wall timing starts inside the script. Final receipt serialization is excluded.",
                   "billing_usd": None, "human_seconds": None,
                   "does_not_replace_original_experiment_costs": True})


if __name__ == "__main__":
    main()
