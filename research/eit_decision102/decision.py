"""KTC2023 physical-data proxy: material-by-quadrant decisions at 40/76 patterns.

Only the source owner's already-exposed physical data and inverse are used.
This adds no sensing, funding, compliance or commercial implementation.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import numpy as np
from scipy import linalg, sparse

from research.measurement_compiler.run import archive, payload, reference, signal, EXPECTED
from research.measurement_compiler.core import signature
from research.measurement_compiler.calibrated import compile_calibrated

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_name("PROTOCOL.md")
OWNER_INVERSE = ROOT / "campaign/measurement-compiler-001/reconstruct.py"
OWNER_COMMIT = "a5859d378ca6298d1ae22e45dc6c083b060103ff"
LABELS = (1, 2)
QUADRANTS = ((0, 128, 0, 128), (0, 128, 128, 256),
             (128, 256, 0, 128), (128, 256, 128, 256))
ROI_FRACTION = 0.05
PATTERNS = 40
N_TARGETS = 21


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decisions(mask):
    """Eight frozen binary decisions; reject changed target/label denominator."""
    a = np.asarray(mask)
    if a.shape != (256, 256) or a.dtype.kind not in "iuf" or not np.isfinite(a).all():
        raise ValueError("FROZEN_256X256_FINITE_IMAGE_REQUIRED")
    if not np.isin(a, (0, 1, 2)).all():
        raise ValueError("EXACT_THREE_MATERIAL_LABELS_REQUIRED")
    return tuple(
        int(np.count_nonzero(a[lo:hi, left:right] == label)
            >= ROI_FRACTION * (hi - lo) * (right - left))
        for label in LABELS
        for lo, hi, left, right in QUADRANTS
    )


def confusion(truth_rows, predicted_rows):
    if (len(truth_rows) != N_TARGETS or len(predicted_rows) != N_TARGETS
            or any(len(v) != 8 or any(type(x) is not int or x not in (0, 1) for x in v)
                   for v in [*truth_rows, *predicted_rows])):
        raise ValueError("FROZEN_21X8_BINARY_DENOMINATOR_REQUIRED")
    by_label = []
    for label_i in range(2):
        truth = [v[label_i * 4 + k] for v in truth_rows for k in range(4)]
        predicted = [v[label_i * 4 + k] for v in predicted_rows for k in range(4)]
        tp = sum(t == p == 1 for t, p in zip(truth, predicted))
        tn = sum(t == p == 0 for t, p in zip(truth, predicted))
        fp = sum(t == 0 and p == 1 for t, p in zip(truth, predicted))
        fn = sum(t == 1 and p == 0 for t, p in zip(truth, predicted))
        positive, negative = tp + fn, tn + fp
        by_label.append({
            "material": LABELS[label_i], "positive": positive, "negative": negative,
            "TP": tp, "TN": tn, "FP": fp, "FN": fn,
            "balanced_accuracy": (tp / positive + tn / negative) / 2
                if positive and negative else None,
        })
    informative = all(x["positive"] >= 8 and x["negative"] >= 8 for x in by_label)
    return {
        "correct": sum(x["TP"] + x["TN"] for x in by_label),
        "denominator": N_TARGETS * 8,
        "accuracy": sum(x["TP"] + x["TN"] for x in by_label) / (N_TARGETS * 8),
        "by_label": by_label, "informative_frozen_task": informative,
        "macro_balanced_accuracy": sum(x["balanced_accuracy"] for x in by_label) / 2
            if informative else None,
    }


def proxy_verdict(stats):
    if any(not v["informative_frozen_task"] for v in stats.values()):
        return "UNINFORMATIVE_FROZEN_TASK_NO_DEPLOY", []
    full = stats["full76"]["macro_balanced_accuracy"]
    zero = max(stats["no_measure_absent"]["macro_balanced_accuracy"],
               stats["no_measure_present"]["macro_balanced_accuracy"])
    eligible = []
    for arm in ("direct40", "impute40"):
        value = stats[arm]["macro_balanced_accuracy"]
        if value >= 0.75 and full - value <= 0.05 and value - zero >= 0.05:
            eligible.append(arm)
    return ("CONDITIONAL_EXPOSED_PROXY_SCREEN_PASS_NO_DEPLOY" if eligible
            else "REJECT_PROXY_SCREEN_NO_DEPLOY"), eligible


def _source_inverse():
    spec = importlib.util.spec_from_file_location("owner_ktc_reconstruct", OWNER_INVERSE)
    if spec is None or spec.loader is None:
        raise ValueError("PINNED_OWNER_RECONSTRUCT_REQUIRED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _reference_setup(code, folder, output):
    """Execute unedited original KTC setup only, before target-result loop."""
    for name in code.namelist():
        relative = Path(name)
        if not relative.parts or relative.parts[0] != "Codes_Python":
            raise ValueError("UNEXPECTED_KTC_CODE_ARCHIVE_PATH")
        rel = relative.relative_to("Codes_Python")
        if ".." in rel.parts:
            raise ValueError("UNSAFE_KTC_ARCHIVE_MEMBER")
        if name.endswith(".py") or rel.as_posix() in ("Mesh_sparse.mat", "TrainingData/ref.mat"):
            target = folder / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(code.read(name))
    sys.path.insert(0, str(folder))
    os.chdir(folder)
    import KTCScoring  # loaded only from pinned public KTC source archive
    tree = ast.parse((folder / "main.py").read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    prefix = []
    for node in fn.body:
        if isinstance(node, ast.For) and isinstance(node.target, ast.Name) and node.target.id == "objectno":
            break
        prefix.append(node)
    else:
        raise ValueError("PINNED_KTC_SETUP_BOUNDARY_MISSING")
    prefix.append(ast.Return(ast.Tuple(
        [ast.Name(v, ast.Load()) for v in ("Mesh", "solver", "sigma0", "z", "smprior", "vincl")],
        ast.Load())))
    fn.body = prefix
    ast.fix_missing_locations(tree)
    ns = {}
    exec(compile(tree, "pinned_ktc_setup", "exec"), ns)
    mesh, solver, sigma0, contact, prior, vincl = ns["main"](str(folder / "TrainingData"), str(output), 1)
    return mesh, solver, sigma0, contact, prior, KTCScoring


def _diagnostic_counts(rows):
    truth = [r["truth"] for r in rows]
    labels = ["full76", "direct40", "impute40"]
    result = {}
    for name in labels:
        result[name] = confusion(truth, [r[name] for r in rows])
    for name, value in (("no_measure_absent", 0), ("no_measure_present", 1)):
        result[name] = confusion(truth, [tuple([value] * 8) for _ in rows])
    for name in labels[1:]:
        result[name]["disagreements_with_full76"] = sum(
            sum(a != b for a, b in zip(r[name], r["full76"])) for r in rows
        )
    return result


def evaluate(data, output):
    if not output.is_absolute() or output.exists() or output.is_symlink():
        raise ValueError("FRESH_ABSOLUTE_OUTPUT_REQUIRED")
    for name, expected in EXPECTED.items():
        path = data / name
        if path.is_symlink() or not path.is_file() or digest(path) != expected:
            raise ValueError("ORIGINAL_PUBLIC_KTC_ARCHIVE_SHA_MISMATCH")
    begin_wall, begin_cpu = time.perf_counter(), time.process_time()
    original_cwd = Path.cwd()
    owner = _source_inverse()
    code = archive(data / "Codes_Python.zip")
    test = archive(data / "EvaluationData_full.zip")
    names = sorted(test.namelist())
    refs = [n for n in names if Path(n).name.lower() == "ref.mat"]
    targets = [n for n in names if Path(n).name.startswith("data") and n.endswith(".mat")]
    if len(targets) != N_TARGETS:
        raise ValueError("ORIGINAL_21_TARGETS_REQUIRED")
    I, M, U0 = reference(payload(code, "Codes_Python/TrainingData/ref.mat"))
    plan = compile_calibrated(I, M, U0, PATTERNS)
    if len(plan.selected) != PATTERNS or len(set(plan.selected)) != PATTERNS:
        raise ValueError("EXACT_40_DISTINCT_PATTERNS_REQUIRED")
    images = []
    setup_wall_start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="eit102-source-") as temporary:
        folder = Path(temporary)
        try:
            mesh, solver, sigma0, contact, prior, scoring = _reference_setup(
                code, folder, output.parent)
            solver.SolveForward(sigma0, contact)
            J = solver.Jacobian(sigma0, contact)
            G = solver.InvGamma_n
            precision = np.asarray(G.diagonal() if sparse.issparse(G) else np.diag(G)).ravel()
            if not np.isfinite(precision).all() or np.any(precision <= 0):
                raise ValueError("INVALID_PINNED_INVERSE_PRECISION")
            if J.shape[0] != M.shape[1] * I.shape[1] or len(precision) != J.shape[0]:
                raise ValueError("INVERSE_GEOMETRY_DIMENSIONS_CHANGED")
            lhs = J.T @ (precision[:, None] * J) + prior.L.T @ prior.L
            full_factor = linalg.cho_factor(lhs, check_finite=True)
            rows_selected = np.concatenate([
                np.arange(k * M.shape[1], (k + 1) * M.shape[1])
                for k in plan.selected
            ])
            selected_J = J[rows_selected, :]
            selected_precision = precision[rows_selected]
            small_lhs = (selected_J.T @ (selected_precision[:, None] * selected_J)
                         + prior.L.T @ prior.L)
            selected_factor = linalg.cho_factor(small_lhs, check_finite=True)
            interpolation, _ = owner.interpolate(mesh)
            setup_wall = time.perf_counter() - setup_wall_start
            for idx, name in enumerate(targets):
                ref = owner.Path(name)  # same pathlib semantics as owner code
                matching = owner.nearest_reference(name, refs) if hasattr(owner, "nearest_reference") else None
                if matching is None:
                    from research.measurement_compiler.calibrated_run import nearest_reference
                    matching = nearest_reference(name, refs)
                target_I, target_M, target_U0 = reference(payload(test, matching))
                if signature(target_I, target_M) != signature(I, M) or not np.array_equal(target_U0, U0):
                    raise ValueError("TARGET_SOURCE_GEOMETRY_OR_REFERENCE_CHANGED")
                actual = signal(payload(test, name), I, M, U0)
                acquired = np.array(actual[:, plan.selected], copy=True)
                imputed = plan.predict(I, M, U0, acquired)
                if not np.array_equal(imputed[:, plan.selected], acquired):
                    raise ValueError("ACQUIRED_PHYSICAL_VALUES_OVERWRITTEN")
                pair = np.column_stack((actual.T.ravel(), imputed.T.ravel()))
                full_coeffs = linalg.cho_solve(
                    full_factor, J.T @ (precision[:, None] * pair))
                direct_coeff = linalg.cho_solve(
                    selected_factor,
                    selected_J.T @ (selected_precision * acquired.T.ravel()))
                coefficients = np.column_stack((full_coeffs, direct_coeff))
                pixels = interpolation @ coefficients
                fields = [np.flipud(pixels[:, k].reshape(256, 256)) for k in range(3)]
                masks = [owner.segment(field, scoring) for field in fields]
                level = Path(name).parent.name.replace("level", "")
                number = Path(name).stem.replace("data", "")
                truth_name = f"EvaluationData_full/GroundTruths/level_{level}/{number}_true.mat"
                ground = payload(test, truth_name)
                truth = next((v for k, v in ground.items()
                              if not k.startswith("_") and getattr(v, "shape", None) == (256, 256)), None)
                if truth is None:
                    raise ValueError("ORIGINAL_PHYSICAL_GROUND_TRUTH_REQUIRED")
                images.append({
                    "target": name, "truth": decisions(truth),
                    "full76": decisions(masks[0]),
                    "impute40": decisions(masks[1]),
                    "direct40": decisions(masks[2]),
                })
                if (idx + 1) % 3 == 0:
                    print(json.dumps({"targets_processed": idx + 1}), flush=True)
        finally:
            os.chdir(original_cwd)
            if str(folder) in sys.path:
                sys.path.remove(str(folder))
    statistics = _diagnostic_counts(images)
    verdict, eligible = proxy_verdict(statistics)
    response = {
        "schema": "agi-alpha/eit-decision102/v1",
        "decision": verdict,
        "proxy_screen_eligible_arms": eligible,
        "source_owner_commit": OWNER_COMMIT,
        "source_sha256": {
            "protocol": digest(PROTOCOL),
            "implementation": digest(__file__),
            "owner_reconstructor": digest(OWNER_INVERSE),
            "physical_archives": EXPECTED,
        },
        "source_commit_executing": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "data_exposure": "PREVIOUSLY_EXPOSED_ORIGINAL_21_PHYSICAL_TARGETS",
        "scope": "RETROSPECTIVE_AUTHORED_PROPERTY_PROXY_NOT_VALIDATED_BENEFICIARY_MEASUREMENT",
        "registered_tasks": "2 materials x 4 fixed quadrants x 21 targets",
        "original_targets": N_TARGETS,
        "decisions_total": N_TARGETS * 8,
        "patterns_per_target": {"direct40": PATTERNS, "impute40": PATTERNS, "full76": 76},
        "homogeneous_setup_pattern_equivalents": 76,
        "recorded_physical_target_acquisitions_performed_here": 0,
        "statistics": statistics,
        "original_owner_48_pattern_reject_preserved": True,
        "other_owner_40_pattern_experiment_unchanged": True,
        "end_user_acceptance": "UNKNOWN",
        "scientific_novelty": "NOT_ESTABLISHED",
        "strongest_production_comparators_covered": False,
        "actual_paid_customers": 0,
        "actual_collected_revenue_usd": 0,
        "native_account_actions": 0,
        "complete_cost_usd": None,
        "trailing_365_complete_cost_profit_usd": None,
        "target_3b_qualified": False,
        "no_bid_no_deploy": True,
        "host_model_bill_usd": "UNKNOWN",
        "inverse_setup_wall_seconds": setup_wall,
        "process_cpu_seconds": time.process_time() - begin_cpu,
        "wall_seconds": time.perf_counter() - begin_wall,
        "per_target_proxy": images,
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / "RESULT.json").write_text(json.dumps(response, sort_keys=True, indent=2) + "\n")
    print(json.dumps({
        "decision": verdict, "eligible": eligible,
        "arms": {k: v["macro_balanced_accuracy"] for k, v in statistics.items()},
        "source_commit": response["source_commit_executing"],
    }, sort_keys=True))
    return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evaluate(args.data, args.output)


if __name__ == "__main__":
    main()
