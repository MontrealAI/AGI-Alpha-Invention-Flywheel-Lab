#!/usr/bin/env python3
"""Run the registered microscopy construction, with three resumable stages.

The offline fixture is a packaging demonstration, never scientific evidence.
Full runs require the independently created registration receipt, exact core
implementation and public archive identities.  No downloaded images are
decoded during preflight.  Completed-stage files are hashed on every resume.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
import traceback

PROCESS_WALL_START, PROCESS_CPU_START = time.perf_counter(), time.process_time()
sys.dont_write_bytecode = True

import numpy as np
import PIL
from PIL import Image
import scipy
import skimage

import builder
import data
import instrument


BASE = Path(__file__).resolve().parent
EXPECTED_PROTOCOL_SHA256 = "76b37f0c1a2c951ed42e53d383063ce5b30c4dda5500665f63d3fa6831adb7ce"
EXPECTED_REGISTRATION_SHA256 = "69985fb0cee36f85bc2595147d34450c1683eeb9bceb99fb155acc040b0e65f4"
IMPLEMENTATION_FILES = ("instrument.py", "builder.py", "data.py", "run.py", "requirements.txt")
STAGES = ("donor", "source", "successor")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def runtime_versions() -> dict:
    return {"python": platform.python_version(), "numpy": np.__version__,
            "scipy": scipy.__version__, "scikit-image": skimage.__version__, "Pillow": PIL.__version__}


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def read_json(path: Path) -> dict:
    value = instrument.strict_json(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def preflight(protocol_path: Path, registration_path: Path, supplied_hash: str | None,
              cache: Path) -> tuple[dict, dict]:
    if instrument.file_hash(protocol_path) != EXPECTED_PROTOCOL_SHA256:
        raise ValueError("This registered edition requires its exact frozen protocol bytes")
    if instrument.file_hash(registration_path) != EXPECTED_REGISTRATION_SHA256:
        raise ValueError("This registered edition requires its exact frozen registration receipt")
    registration = read_json(registration_path)
    if registration.get("schema") != "learning-to-build/microscopy-registration/v1":
        raise ValueError("Unsupported registration receipt")
    protocol_hash = instrument.file_hash(protocol_path)
    if protocol_hash != registration.get("protocol_sha256"):
        raise ValueError("Protocol does not match the independently frozen registration")
    if supplied_hash is not None and protocol_hash != supplied_hash:
        raise ValueError("Protocol does not match --protocol-sha256")
    protocol = read_json(protocol_path)
    if protocol.get("status") != "REGISTERED_BEFORE_SCORING" or not protocol.get("registered_at_utc"):
        raise ValueError("The protocol is not registered; no public pixels may be decoded")
    core = registration.get("implementation_files", {})
    if set(core) != {"instrument.py", "builder.py", "data.py"}:
        raise ValueError("Registration must pin exactly the three core implementation files")
    for name, expected in core.items():
        if instrument.file_hash(BASE / name) != expected:
            raise ValueError(f"Registered implementation mismatch: {name}")
    if registration.get("recipe_bank_sha256") != instrument.bank_hash():
        raise ValueError("Registered recipe bank does not match the implementation")
    grammar = protocol["recipe_grammar"]
    if (grammar["candidate_count"] != 24 or grammar["background"] != ["none", "opening"]
            or grammar["threshold"] != ["li", "otsu"] or grammar["seed_distance"] != [4, 7, 10]
            or grammar["watershed_surface"] != ["distance", "intensity"]
            or grammar["gaussian_sigma"] != 1.0 or grammar["minimum_object_area_pixels"] != 20
            or grammar["fill_holes"] is not True):
        raise ValueError("The registered finite grammar is not a configurable simulator")
    archives = data.verify_archives(cache, protocol["data"]["archives"])
    split = data.metadata039(cache)
    if [len(split[k]) for k in ("training", "validation", "test")] != [100, 50, 50]:
        raise ValueError("Unexpected official BBBC039 split sizes")
    paired = list(data.pairs007(cache))
    target = protocol["data"]["bbbc007"]
    if target["calibration_ids"] != paired[:4] or target["test_ids"] != paired[4:] or len(paired[4:]) < 4:
        raise ValueError("Registered successor cohort differs from the source-order split")
    runtime = runtime_versions()
    registered_runtime = registration.get("runtime_versions", {})
    # Python patch versions are recorded, while numeric-library versions bind
    # reproducibility. A supported Python minor is not a new scientific arm.
    for key, value in registered_runtime.items():
        actual_key = {"skimage": "scikit-image", "scikit_image": "scikit-image",
                      "pillow": "Pillow"}.get(key, key)
        if actual_key == "python":
            if str(value).split(".")[:2] != runtime["python"].split(".")[:2]:
                raise ValueError("Python minor version differs from registration")
        elif actual_key not in runtime or runtime[actual_key] != value:
            raise ValueError(f"Numeric runtime differs from registration: {key}")
    binding = {"protocol_sha256": protocol_hash,
               "registration_sha256": instrument.file_hash(registration_path),
               "implementation_files": {name: instrument.file_hash(BASE / name) for name in IMPLEMENTATION_FILES},
               "archives": archives, "recipe_bank_sha256": instrument.bank_hash(),
               "runtime_versions": runtime}
    return protocol, binding


def tree_hashes(path: Path) -> dict:
    result = {}
    for member in sorted(path.rglob("*")):
        if member.is_symlink():
            raise ValueError(f"Evidence cannot contain symlinks: {member}")
        if member.is_file():
            result[member.relative_to(path).as_posix()] = instrument.file_hash(member)
    return result


def verify_completed_stages(output: Path, state: dict) -> None:
    for stage, receipt in state["stages"].items():
        if stage not in STAGES or tree_hashes(output / stage) != receipt["files"]:
            raise ValueError(f"Completed checkpoint changed: {stage}")


def donor_stage(destination: Path, cache: Path, protocol: dict, bindings: dict, output: Path) -> dict:
    cases = data.load039(cache, "training")
    rows = []
    for recipe in instrument.recipes():
        candidate_rows, _ = builder.evaluate(recipe, "nuclei", cases)
        rows.extend(candidate_rows)
        builder.write_csv(destination / "history.csv", rows)
        print(f"donor {recipe.id}: {len(candidate_rows)} training fields completed", flush=True)
    selected, summaries = builder.select_donor(rows)
    orders, learned = builder.arm_orders(rows, selected, protocol["criteria"])
    builder.write_json(destination / "learned_order.json", learned)
    builder.write_json(destination / "orders.json", orders)
    result = {"task": "nuclei", "training_fields": len(cases), "recipes_evaluated": 24,
              "field_evaluations": len(rows), "selected_recipe_id": selected,
              "selected_training": summaries[selected], "all_recipe_training_summaries": summaries,
              "selected_training_qualified": builder.qualifies(summaries[selected], "nuclei", protocol["criteria"]),
              "history_sha256": instrument.file_hash(destination / "history.csv"),
              "learning_scope": "Greedy coverage updates an ordering parameter of a supplied finite policy.",
              "program_or_operator_discovery": False}
    builder.write_json(destination / "summary.json", result)
    return result


def source_stage(destination: Path, cache: Path, protocol: dict, bindings: dict, output: Path) -> dict:
    donor = read_json(output / "donor" / "summary.json")
    recipe = instrument.RECIPE_MAP[donor["selected_recipe_id"]]
    provenance = {"protocol_sha256": bindings["protocol_sha256"],
                  "registration_sha256": bindings["registration_sha256"],
                  "construction_history_sha256": donor["history_sha256"],
                  "selection_cohort": "BBBC039 official training only"}
    instrument.emit(destination / "instrument", recipe, "nuclei", provenance)
    result = {"selected_recipe_id": recipe.id, "cohorts": {}}
    for split in ("validation", "test"):
        cases = data.load039(cache, split)
        rows, summary = builder.evaluate(recipe, "nuclei", cases, retain=destination / split)
        builder.write_csv(destination / split / "metrics.csv", rows)
        result["cohorts"][split] = summary
        result[split + "_qualified"] = builder.qualifies(summary, "nuclei", protocol["criteria"])
        print(f"source {split}: {len(cases)} fields completed", flush=True)
    result["complete_qualification"] = result["validation_qualified"] and result["test_qualified"]
    result["independent_laboratory_acceptance"] = False
    result["instrument_sha256"] = instrument.file_hash(destination / "instrument" / "instrument.json")
    builder.write_json(destination / "summary.json", result)
    return result


def successor_stage(destination: Path, cache: Path, protocol: dict, bindings: dict, output: Path) -> dict:
    target = protocol["data"]["bbbc007"]
    calibration_cases = data.load007(cache, target["calibration_ids"])
    orders = read_json(output / "donor" / "orders.json")
    donor = read_json(output / "donor" / "summary.json")
    artifact_path = output / "source" / "instrument" / "instrument.json"
    constructions, selections = {}, {}
    for arm in protocol["arms"]:
        name = arm["id"]
        use_artifact = name in ("ordinary_reuse", "updated_with_artifact")
        result = builder.construct(orders[name], calibration_cases, protocol["criteria"], destination / name,
                                   exhaustive=name == "full_enumeration",
                                   artifact_path=artifact_path if use_artifact else None)
        constructions[name] = result
        recipe = instrument.RECIPE_MAP[result["selected_recipe_id"]]
        provenance = {"protocol_sha256": bindings["protocol_sha256"], "construction_arm": name,
                      "source_history_sha256": donor["history_sha256"],
                      "calibration_fields": target["calibration_ids"],
                      "calibration_qualified": result["calibration_qualified"],
                      "source_artifact_sha256": instrument.file_hash(artifact_path) if use_artifact else None}
        instrument.emit(destination / name / "instrument", recipe, "cells", provenance)
        selections[name] = {"recipe_id": recipe.id,
                            "instrument_sha256": instrument.file_hash(destination / name / "instrument" / "instrument.json"),
                            "calibration_candidates_executed": result["calibration_candidates_executed"]}
        print(f"successor {name}: construction completed after {result['calibration_candidates_executed']} candidates", flush=True)
    # All six choices and executable instruments exist before any target test
    # image or reference is decoded. No selection function receives test data.
    builder.write_json(destination / "SELECTIONS_BEFORE_TEST.json", selections)
    heldout_cases = data.load007(cache, target["test_ids"])
    arms = {}
    for arm in protocol["arms"]:
        name = arm["id"]
        result = constructions[name]
        recipe = instrument.RECIPE_MAP[result["selected_recipe_id"]]
        started_wall, started_cpu = time.perf_counter(), time.process_time()
        artifact = builder.RetainedNucleusArtifact(artifact_path) if result["artifact_access"] else None
        rows, summary = builder.evaluate(recipe, "cells", heldout_cases, retain=destination / name / "holdout",
                                          artifact=artifact)
        builder.write_csv(destination / name / "holdout" / "metrics.csv", rows)
        heldout_qualified = builder.qualifies(summary, "cells", protocol["criteria"], heldout=True)
        result = {**result, "holdout": summary, "heldout_qualified": heldout_qualified,
                  "complete_qualification": bool(result["calibration_qualified"] and heldout_qualified),
                  "actual_holdout_cpu_seconds": time.process_time() - started_cpu,
                  "actual_holdout_wall_seconds": time.perf_counter() - started_wall,
                  "heldout_artifact_invocations": artifact.invocations if artifact is not None else 0,
                  "instrument_sha256": selections[name]["instrument_sha256"],
                  "reference_inputs_in_primary_prediction": False}
        arms[name] = result
        builder.write_json(destination / name / "summary.json", result)
        print(f"successor {name}: {len(rows)} heldout fields completed", flush=True)
    diagnostic_results = {}
    for diagnostic in ("old_artifact", "oracle_input"):
        started_wall, started_cpu = time.perf_counter(), time.process_time()
        if diagnostic == "old_artifact":
            recipe = instrument.RECIPE_MAP[donor["selected_recipe_id"]]
            artifact = builder.RetainedNucleusArtifact(artifact_path)
            rows, summary = builder.evaluate(recipe, "cells", heldout_cases,
                                              retain=destination / "diagnostics" / diagnostic,
                                              artifact=artifact, direct_artifact=True)
        else:
            recipe = instrument.RECIPE_MAP[arms["full_enumeration"]["selected_recipe_id"]]
            rows, summary = builder.evaluate(recipe, "cells", heldout_cases,
                                              retain=destination / "diagnostics" / diagnostic, oracle=True)
        folder = destination / "diagnostics" / diagnostic
        builder.write_csv(folder / "metrics.csv", rows)
        diagnostic_results[diagnostic] = {
            "recipe_id": recipe.id, "holdout": summary,
            "heldout_criteria_met": builder.qualifies(summary, "cells", protocol["criteria"], heldout=True),
            "primary_arm": False, "complete_raw_channel_qualification": False,
            "manual_reference_inputs_used": diagnostic == "oracle_input",
            "actual_cpu_seconds": time.process_time() - started_cpu,
            "actual_wall_seconds": time.perf_counter() - started_wall,
        }
        builder.write_json(folder / "summary.json", diagnostic_results[diagnostic])
    updated, conventional = arms["updated_no_artifact"], arms["same_content_empirical"]
    local_advantage = bool(updated["complete_qualification"] and
                           updated["calibration_candidates_executed"] < conventional["calibration_candidates_executed"])
    result = {"task": "whole-cell instances from measured DNA plus actin",
              "calibration_fields": len(calibration_cases), "heldout_fields": len(heldout_cases),
              "arms": arms, "diagnostics": diagnostic_results,
              "primary_comparison": {
                  "updated_arm": "updated_no_artifact", "conventional_arm": "same_content_empirical",
                  "candidate_evaluations_saved": conventional["calibration_candidates_executed"] - updated["calibration_candidates_executed"],
                  "updated_qualified": updated["complete_qualification"],
                  "conventional_qualified": conventional["complete_qualification"],
                  "local_accepted_prefix_advantage": local_advantage,
                  "general_constructor_improvement_established": False,
                  "total_lifecycle_advantage_established": False},
              "any_primary_arm_qualified": any(arm["complete_qualification"] for arm in arms.values()),
              "direct_full_enumeration_qualified": arms["full_enumeration"]["complete_qualification"],
              "exclusive_artifact_enabling_established": False,
              "cohort_scope": "One source-ordered calibration/test split of a publicly known assay."}
    builder.write_json(destination / "summary.json", result)
    return result


PHASE_FUNCTIONS = {"donor": donor_stage, "source": source_stage, "successor": successor_stage}


def fixture(output: Path) -> None:
    if output.exists():
        raise ValueError("Fixture output already exists; use a fresh directory")
    output.mkdir(parents=True)
    yy, xx = np.mgrid[:96, :96]
    dna = np.zeros((96, 96), dtype=float)
    actin = np.zeros_like(dna)
    for row, column in ((28, 30), (30, 64), (66, 48)):
        distance = (yy - row) ** 2 + (xx - column) ** 2
        dna += np.exp(-distance / 40.0)
        actin += np.exp(-distance / 180.0)
    dna = np.clip(dna * 230, 0, 255).astype(np.uint8)
    actin = np.clip(actin * 230, 0, 255).astype(np.uint8)
    Image.fromarray(dna).save(output / "dna.tif")
    Image.fromarray(actin).save(output / "actin.tif")
    recipe = instrument.RECIPE_MAP[builder.fixed_order()[0]]
    instrument.emit(output / "instrument", recipe, "cells", {"scope": "OFFLINE_FIXTURE_ONLY"})
    labels = instrument.apply(dna, recipe, "cells", actin)
    label_hash = instrument.save_labels(output / "labels.png", labels)
    rows = instrument.measurements(labels)
    instrument.write_measurements(output / "measurements.csv", rows)
    result = {"schema": "learning-to-build/offline-fixture/v1", "status": "OFFLINE_FIXTURE_ONLY",
              "scientific_evidence": False, "public_data_used": False, "recipe_id": recipe.id,
              "instances": len(rows), "labels_sha256": label_hash,
              "instrument_sha256": instrument.file_hash(output / "instrument" / "instrument.json"),
              "inputs": {"dna.tif": instrument.file_hash(output / "dna.tif"),
                         "actin.tif": instrument.file_hash(output / "actin.tif")},
              "purpose": "Check installation, emitted program, file outputs and byte bindings only."}
    builder.write_json(output / "FIXTURE.json", result)
    print(json.dumps(result, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--protocol", type=Path, default=BASE / "PROTOCOL.json")
    parser.add_argument("--registration", type=Path, default=BASE / "REGISTRATION-amendment-1.json")
    parser.add_argument("--protocol-sha256")
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stop-after", choices=STAGES)
    args = parser.parse_args()
    output = args.output.resolve()
    if output == BASE or output in BASE.parents:
        raise ValueError("Evidence destination must not contain the implementation source")
    if args.fixture:
        if args.resume or args.stop_after:
            raise ValueError("The small fixture has no resumable scientific stages")
        fixture(output)
        return
    if args.cache is None:
        parser.error("--cache is required for the registered public-data run")
    protocol, bindings = preflight(args.protocol, args.registration, args.protocol_sha256, args.cache)
    if args.resume:
        state = read_json(output / "RUN_STATE.json")
        if state["bindings"] != bindings:
            raise ValueError("Resume source, runtime, archive or protocol identity changed")
        for name, binding_name in (("PROTOCOL.json", "protocol_sha256"),
                                   ("REGISTRATION.json", "registration_sha256")):
            if instrument.file_hash(output / name) != bindings[binding_name]:
                raise ValueError(f"Retained registration/protocol copy changed: {name}")
        verify_completed_stages(output, state)
        if state["status"] == "COMPLETE":
            if set(state["stages"]) != set(STAGES):
                raise ValueError("A complete run must contain all three completed checkpoints")
            if instrument.file_hash(output / "RESULTS.json") != state["results_sha256"]:
                raise ValueError("Completed result changed")
            result = read_json(output / "RESULTS.json")
            expected_status = {"status": "COMPLETE", "scientific_run_completed": True,
                               "source_qualified": result["source_qualified"],
                               "successor_any_primary_qualified": result["successor_any_primary_qualified"]}
            if instrument.canonical_hash(read_json(output / "STATUS.json")) != instrument.canonical_hash(expected_status):
                raise ValueError("Completed status receipt changed")
            print(json.dumps({"status": "COMPLETE", "idempotent_resume": True,
                              "results_sha256": state["results_sha256"]}, sort_keys=True))
            return
        for attempt in state["attempts"]:
            if attempt["status"] == "RUNNING":
                attempt["status"] = "INTERRUPTED_WITH_UNMEASURED_REMAINDER"
                attempt["interruption_observed_at_utc"] = utc_now()
                attempt["unmeasured_work_is_not_zero"] = True
        # A hard termination can fall between directory rename and checkpoint
        # persistence. Preserve that uncommitted product; never silently erase
        # its work or let a nonempty directory block a faithful rerun.
        for stage in STAGES:
            orphan = output / stage
            if stage not in state["stages"] and orphan.exists():
                number = 1
                while (output / "attempts" / f"{stage}-uncommitted-{number:03d}").exists():
                    number += 1
                preserved = output / "attempts" / f"{stage}-uncommitted-{number:03d}"
                preserved.parent.mkdir(parents=True, exist_ok=True)
                orphan.replace(preserved)
                state.setdefault("uncommitted_stage_directories", []).append({
                    "stage": stage, "path": preserved.relative_to(output).as_posix(),
                    "detected_at_utc": utc_now(), "files": tree_hashes(preserved),
                    "disposition": "preserved_and_recomputed", "unmeasured_work_is_not_zero": True})
    else:
        if output.exists():
            raise ValueError("Output already exists; choose a fresh directory or use --resume")
        output.mkdir(parents=True)
        state = {"schema": "learning-to-build/microscopy-run-state/v1", "status": "PARTIAL",
                 "bindings": bindings, "stages": {}, "attempts": [], "invocations": [],
                 "created_at_utc": utc_now()}
        (output / "PROTOCOL.json").write_bytes(args.protocol.read_bytes())
        (output / "REGISTRATION.json").write_bytes(args.registration.read_bytes())
    atomic_json(output / "RUN_STATE.json", state)
    invocation = {"started_at_utc": utc_now(), "resumed": args.resume, "completed_stages": []}
    try:
        for stage in STAGES:
            if stage in state["stages"]:
                continue
            number = 1 + sum(attempt["stage"] == stage for attempt in state["attempts"])
            temporary = output / "attempts" / f"{stage}-{number:03d}"
            temporary.mkdir(parents=True, exist_ok=False)
            attempt = {"stage": stage, "attempt": number, "status": "RUNNING",
                       "path": temporary.relative_to(output).as_posix(), "started_at_utc": utc_now()}
            state["attempts"].append(attempt)
            atomic_json(output / "RUN_STATE.json", state)
            started_wall, started_cpu = time.perf_counter(), time.process_time()
            try:
                PHASE_FUNCTIONS[stage](temporary, args.cache, protocol, bindings, output)
            except BaseException as exc:
                attempt.update(status="FAILED", error=f"{type(exc).__name__}: {exc}",
                               ended_at_utc=utc_now(), actual_cpu_seconds=time.process_time() - started_cpu,
                               actual_wall_seconds=time.perf_counter() - started_wall)
                builder.write_json(temporary / "FAILURE.json", {**attempt, "traceback": traceback.format_exc()})
                raise
            attempt.update(status="COMPLETE", ended_at_utc=utc_now(),
                           actual_cpu_seconds=time.process_time() - started_cpu,
                           actual_wall_seconds=time.perf_counter() - started_wall)
            temporary.replace(output / stage)
            attempt["path"] = stage
            state["stages"][stage] = {"files": tree_hashes(output / stage),
                                      "actual_cpu_seconds": attempt["actual_cpu_seconds"],
                                      "actual_wall_seconds": attempt["actual_wall_seconds"]}
            invocation["completed_stages"].append(stage)
            atomic_json(output / "RUN_STATE.json", state)
            if args.stop_after == stage and stage != "successor":
                state["status"] = "PARTIAL"
                atomic_json(output / "STATUS.json", {"status": "PARTIAL", "completed_stages": list(state["stages"]),
                                                     "requested_stop_after": stage, "accepted_run": False})
                print(f"PARTIAL: stopped after {stage}; resume with the identical registered inputs", flush=True)
                return
        source = read_json(output / "source" / "summary.json")
        successor = read_json(output / "successor" / "summary.json")
        result = {"schema": "learning-to-build/microscopy-results/v1", "status": "COMPLETE",
                  "bindings": bindings, "source": source, "successor": successor,
                  "donor": read_json(output / "donor" / "summary.json"),
                  "source_qualified": source["complete_qualification"],
                  "successor_any_primary_qualified": successor["any_primary_arm_qualified"],
                  "continuation_after_unqualified_donor": not source["complete_qualification"],
                  "completed_stage_cpu_seconds": sum(row["actual_cpu_seconds"] for row in state["stages"].values()),
                  "completed_stage_wall_seconds": sum(row["actual_wall_seconds"] for row in state["stages"].values()),
                  "all_measured_attempt_cpu_seconds": sum(row.get("actual_cpu_seconds", 0.0) for row in state["attempts"]),
                  "all_measured_attempt_wall_seconds": sum(row.get("actual_wall_seconds", 0.0) for row in state["attempts"]),
                  "has_unmeasured_interrupted_work": bool(state.get("uncommitted_stage_directories")) or any(row["status"] == "INTERRUPTED_WITH_UNMEASURED_REMAINDER" for row in state["attempts"]),
                  "cost_scope": "Measured local run work; authoring, included-model billing, external acceptance and economic costs remain unmeasured.",
                  "economics": protocol["economics"], "claims_not_tested": protocol["claims_not_tested"]}
        builder.write_json(output / "RESULTS.json", result)
        state["status"] = "COMPLETE"
        state["results_sha256"] = instrument.file_hash(output / "RESULTS.json")
        atomic_json(output / "STATUS.json", {"status": "COMPLETE", "scientific_run_completed": True,
                                             "source_qualified": result["source_qualified"],
                                             "successor_any_primary_qualified": result["successor_any_primary_qualified"]})
        print(json.dumps({"status": "COMPLETE", "source_qualified": result["source_qualified"],
                          "successor_any_primary_qualified": result["successor_any_primary_qualified"],
                          "primary_comparison": successor["primary_comparison"]}, sort_keys=True))
    except BaseException as exc:
        state["status"] = "FAILED"
        atomic_json(output / "STATUS.json", {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}",
                                             "completed_stages": list(state["stages"]), "accepted_run": False})
        raise
    finally:
        invocation.update(ended_at_utc=utc_now(), actual_cpu_seconds=time.process_time() - PROCESS_CPU_START,
                          actual_wall_seconds=time.perf_counter() - PROCESS_WALL_START, status=state["status"])
        state["invocations"].append(invocation)
        atomic_json(output / "RUN_STATE.json", state)


if __name__ == "__main__":
    main()
