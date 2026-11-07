"""One frozen KTC2023 research cycle: train-only LOO, then exposed targets if eligible."""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
import time
from pathlib import Path
import numpy as np

from research.measurement_compiler import calibrated
from research.measurement_compiler.calibrated_run import nearest_reference
from research.measurement_compiler.run import (
    archive, payload, reference, signal, source_hashes, EXPECTED,
)
from research.measurement_compiler.core import signature
from research.eit40.model import COUNT, compile_plan, error, development_gate, matrix_hash

BASE = "a5859d378ca6298d1ae22e45dc6c083b060103ff"
ROOT = Path(__file__).parent
PREREG = ROOT / "PREREGISTRATION.md"
MODEL = ROOT / "model.py"


def digest_file(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def immutable_inputs():
    return {
        "owner_head": BASE,
        "owner_source_hashes": source_hashes(),
        "experiment_model_sha256": digest_file(MODEL),
        "experiment_runner_sha256": digest_file(__file__),
        "preregistration_sha256": digest_file(PREREG),
        "public_archive_sha256": EXPECTED,
    }


def read_training(directory):
    z = archive(directory / "Codes_Python.zip")
    I, M, U0 = reference(payload(z, "Codes_Python/TrainingData/ref.mat"))
    training = [
        signal(payload(z, f"Codes_Python/TrainingData/data{j}.mat"), I, M, U0)
        for j in range(1, 5)
    ]
    if any(x.shape != U0.shape for x in training):
        raise ValueError("TRAINING_SCHEMA_CHANGED")
    return I, M, U0, training


def plan_receipt(plan):
    return {
        "mode": plan.mode, "pattern_count": len(plan.selected),
        "selected": list(plan.selected), "basis_rank": plan.basis.shape[0],
        "basis_sha256": plan.basis_sha256,
        "geometry_sha256": plan.geometry_sha256,
        "calibration_sha256": plan.calibration_sha256,
        "operator_sha256": matrix_hash(plan.operator),
        "operator_bytes": int(plan.operator.nbytes),
        "number_of_full_calibration_specimens": plan.calibration_specimens,
    }


def run_develop(data, output):
    started, cpu = time.perf_counter(), time.process_time()
    I, M, U0, training = read_training(data)
    folds = []
    for left_out in range(4):
        train = [v for j, v in enumerate(training) if j != left_out]
        plan = compile_plan(I, M, U0, train)
        predicted = plan.predict(I, M, U0, train, training[left_out][:, plan.selected])
        folds.append({
            "left_out_specimen": left_out + 1,
            "relative_rms": error(predicted, training[left_out]),
            "plan": plan_receipt(plan),
        })
    eligible = development_gate([f["relative_rms"] for f in folds])
    result = {
        "schema": "agi-alpha/eit40/v1",
        "stage": "DEVELOPMENT",
        "source": immutable_inputs(),
        "calibration_data_sha256": matrix_hash(U0, *training),
        "fixed_acquisitions": COUNT,
        "development_folds": folds,
        "all_four_within_five_percent": eligible,
        "decision": "ELIGIBLE_FOR_EXPOSED_RETROSPECTIVE" if eligible else "STOP_DEVELOPMENT_FAILED",
        "explicit_exposed_holdout": True,
        "historical_48_pattern_failure_preserved": True,
        "physical_measurements_acquired_here": 0,
        "actual_customers": 0,
        "actual_revenue_usd": 0,
        "host_model_billing_usd": None,
        "wall_seconds": time.perf_counter() - started,
        "process_cpu_seconds": time.process_time() - cpu,
    }
    if eligible:
        full_plan = compile_plan(I, M, U0, training)
        result["frozen_all_four_plan"] = plan_receipt(full_plan)
    output.mkdir(parents=True, exist_ok=False)
    (output / "DEVELOPMENT.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({
        "development_gate": eligible,
        "fold_errors": [f["relative_rms"] for f in folds],
        "next_decision": result["decision"],
    }, sort_keys=True))
    return result


def run_confirm(data, output, frozen):
    # Fail closed BEFORE opening or parsing EvaluationData_full.zip.
    dev = json.loads(frozen.read_text())
    if dev.get("schema") != "agi-alpha/eit40/v1" or dev.get("stage") != "DEVELOPMENT":
        raise ValueError("UNRECOGNIZED_FROZEN_DEVELOPMENT")
    if not dev.get("all_four_within_five_percent") or dev.get("decision") != "ELIGIBLE_FOR_EXPOSED_RETROSPECTIVE":
        raise ValueError("DEVELOPMENT_FAILED_NO_EVALUATION_PERMITTED")
    if dev.get("source") != immutable_inputs() or dev.get("fixed_acquisitions") != COUNT:
        raise ValueError("SOURCE_OR_PROTOCOL_CHANGED")
    started, cpu = time.perf_counter(), time.process_time()
    I, M, U0, training = read_training(data)
    if dev["calibration_data_sha256"] != matrix_hash(U0, *training):
        raise ValueError("CALIBRATION_DATA_CHANGED")
    plan = compile_plan(I, M, U0, training)
    if dev.get("frozen_all_four_plan") != plan_receipt(plan):
        raise ValueError("FROZEN_ACQUISITION_PLAN_CHANGED")

    # Only now access the prior study's ALREADY EXPOSED 21 evaluation targets.
    z = archive(data / "EvaluationData_full.zip")
    names = sorted(z.namelist())
    refs = [n for n in names if Path(n).name.lower() == "ref.mat"]
    targets = [n for n in names if Path(n).name.startswith("data") and n.endswith(".mat")]
    if len(targets) != 21:
        raise ValueError("EVALUATION_DENOMINATOR_NOT_21")
    conventional = compile_plan(I, M, U0, training, mode="conventional_pca")
    owner_one = calibrated.compile_calibrated(I, M, U0, COUNT)
    owner_current = calibrated.compile_calibrated(
        I, M, U0, COUNT, mode="current_only", selected=plan.selected
    )
    rows = []
    for name in targets:
        ref = nearest_reference(name, refs)
        eI, eM, eU0 = reference(payload(z, ref))
        if signature(eI, eM) != signature(I, M) or not np.array_equal(eU0, U0):
            raise ValueError("EVALUATION_GEOMETRY_OR_CALIBRATION_CHANGED")
        actual = signal(payload(z, name), I, M, U0)
        pred = plan.predict(I, M, U0, training, actual[:, plan.selected])
        ordinary_lstsq = np.linalg.lstsq(plan.basis[:, plan.selected].T,
                                       actual[:, plan.selected].T, rcond=1e-11)[0].T @ plan.basis
        ordinary_lstsq[:, plan.selected] = actual[:, plan.selected]
        if not np.allclose(pred, ordinary_lstsq, atol=1e-10, rtol=1e-10):
            raise ValueError("STRONG_ORDINARY_ALGEBRA_DISAGREES")
        comparisons = {
            "physical_residual": error(pred, actual),
            "conventional_pca": error(
                conventional.predict(I, M, U0, training, actual[:, conventional.selected]), actual
            ),
            "original_one_extra_40": error(
                owner_one.predict(I, M, U0, actual[:, owner_one.selected]), actual
            ),
            "current_only_on_candidate_indices": error(
                owner_current.predict(I, M, U0, actual[:, owner_current.selected]), actual
            ),
            "full_76_direct": 0.0,
        }
        rows.append({"target": name, "relative_rms_by_arm": comparisons,
                     "ordinary_same_algebra_difference": float(np.max(np.abs(pred - ordinary_lstsq)))})
    errs = [r["relative_rms_by_arm"]["physical_residual"] for r in rows]
    verdict = len(rows) == 21 and sum(x <= 0.05 for x in errs) >= 20 and max(errs) <= 0.10
    result = {
        "schema": "agi-alpha/eit40/v1",
        "stage": "EXPOSED_RETROSPECTIVE_RESEARCH",
        "decision": "RETROSPECTIVE_NUMERIC_SCREEN_PASS_NO_DEPLOY" if verdict else "RETROSPECTIVE_SCREEN_REJECT_NO_DEPLOY",
        "source": immutable_inputs(),
        "frozen_development_sha256": digest_file(frozen),
        "plan": plan_receipt(plan),
        "strong_conventional": plan_receipt(conventional),
        "owner_40": {"count": COUNT, "selected": list(owner_one.selected)},
        "rows": rows,
        "targets": len(rows),
        "physical_residual_within_five_percent": sum(x <= .05 for x in errs),
        "worst_relative_rms": max(errs),
        "median_relative_rms": float(np.median(errs)),
        "calibration_pattern_equivalent_setup": 76 * 5,
        "patterns_per_new_specimen": COUNT,
        "retrospective_data_exposed_by_previous_study": True,
        "independent_new_physical_confirmation": False,
        "physical_measurements_acquired_here": 0,
        "actual_customers": 0, "actual_revenue_usd": 0,
        "host_model_billing_usd": None,
        "complete_cost_usd": None, "industrial_acceptance": False,
        "historical_pr262_reject_remains_reject": True,
        "wall_seconds": time.perf_counter() - started,
        "process_cpu_seconds": time.process_time() - cpu,
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / "RETROSPECTIVE.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in (
        "decision", "targets", "physical_residual_within_five_percent", "worst_relative_rms"
    )}, sort_keys=True))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("develop", "confirm"))
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--freeze", type=Path)
    args = parser.parse_args()
    if not args.output.is_absolute() or args.output.exists() or args.output.is_symlink():
        raise SystemExit("ABSOLUTE_FRESH_OUTPUT_REQUIRED")
    if args.stage == "develop":
        run_develop(args.data, args.output)
    else:
        if args.freeze is None:
            raise SystemExit("FROZEN_DEVELOPMENT_REQUIRED")
        run_confirm(args.data, args.output, args.freeze)


if __name__ == "__main__":
    main()
