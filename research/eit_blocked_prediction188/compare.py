"""Frozen EIT188 blocked-column *predictive* control, not physical identification.

All 16 folds, the zero/change nuisance alternatives, both unverified raw HDF5
flattening hypotheses and all three fixed ridge penalties must be reported.
No source/parameter selection, original MATLAB execution or native account use.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from zipfile import ZipFile

import numpy as np
from scipy.sparse.linalg import lsmr

from research.eit_physical_control183.control import (
    EXPECTED_SHA256, MEMBERS, SHAPE, Refusal, download_exact,
    parse_member, validate_zip,
)
from research.eit_jacobian185.original_source import run_archive
from research.eit_matlab_source186.review import (
    SAMPLE_BASENAME, SAMPLE_SHA, SAMPLE_BYTES, JACOBIAN_SHA,
    source_line_index,
)
from research.eit_ordinary_inverse187.compare import (
    DIFFERENCE_LINE_SHA256, EXPECTED_SCRIPT_DIFFERENCE_LINE,
    EXPECTED_J_SHAPE, GAMMAS, MAXITER, JACOBIAN_BASENAME,
    difference_source_gate, load_original_J,
)


def _input_arrays(J, v0, v1):
    j = np.asarray(J)
    a, b = np.asarray(v0), np.asarray(v1)
    if (j.ndim != 2 or j.shape[0] != a.size or j.shape[1] < 1 or
            a.ndim != 2 or b.shape != a.shape or a.shape[1] < 2 or
            a.shape[0] < 2 or any(x.dtype.kind != "f" for x in (j, a, b)) or
            any(not np.isfinite(x).all() for x in (j, a, b))):
        raise Refusal("EIT188_INPUT_SHAPE_OR_FINITE_TYPE_INVALID")
    return (np.asarray(j, dtype=np.float64), np.asarray(a, dtype=np.float64),
            np.asarray(b, dtype=np.float64))


def fixed_blocked_predictions(J, v0, v1, *, gammas=GAMMAS, maxiter=MAXITER):
    """Fit each method ONLY on fifteen columns, predict the untouched column.

    Optional synthetic sizes are for offline analytic tests; the physical
    source gate separately enforces 79 x 16 and 1264 x 1197.
    """
    j, a, b = _input_arrays(J, v0, v1)
    nrows, ncols = a.shape
    count = a.size
    frozen_scale = float(np.sum(j * j, dtype=np.float64) / j.shape[1])
    if not (math.isfinite(frozen_scale) and frozen_scale > 0):
        raise Refusal("EIT188_DEGENERATE_J")
    if not math.isfinite(float(np.linalg.norm(b - a))) or np.array_equal(a, b):
        raise Refusal("EIT188_DEGENERATE_CONTRAST")
    if not isinstance(maxiter, int) or maxiter < 1 or any(
            not math.isfinite(float(g)) or float(g) <= 0 for g in gammas):
        raise Refusal("EIT188_INVALID_FIXED_SOLVER_PARAMETERS")

    names = ["zero", "gain_only", "gain_and_offset"]
    names.extend(f"ridge_{order}_gamma_{g:g}"
                 for order in ("C", "F") for g in gammas)
    record = {name: {"fold_sse": [], "fold_rms": [], "fit_details": []}
              for name in names}
    flat_delta = {order: (b-a).reshape(-1, order=order) for order in ("C", "F")}
    flat_grids = {order: np.arange(count).reshape(a.shape, order=order)
                  for order in ("C", "F")}

    def store(name, error, detail):
        if not np.isfinite(error).all():
            raise Refusal("EIT188_NONFINITE_PREDICTION")
        sse = float(np.dot(error, error))
        if not math.isfinite(sse):
            raise Refusal("EIT188_NONFINITE_SQUARED_ERROR")
        record[name]["fold_sse"].append(sse)
        record[name]["fold_rms"].append(math.sqrt(sse / nrows))
        record[name]["fit_details"].append(detail)

    for heldout_col in range(ncols):
        train = np.ones(a.shape, dtype=bool)
        train[:, heldout_col] = False
        xtrain, ytrain = a[train], b[train]
        xtest, ytest = a[:, heldout_col], b[:, heldout_col]
        store("zero", xtest-ytest, {"heldout_column": heldout_col})
        norm2 = float(np.dot(xtrain, xtrain))
        if not math.isfinite(norm2) or norm2 <= 0:
            raise Refusal("EIT188_ZERO_GAIN_TRAINING_DENOMINATOR")
        gain = float(np.dot(xtrain, ytrain) / norm2)
        if not math.isfinite(gain):
            raise Refusal("EIT188_NONFINITE_GAIN")
        store("gain_only", gain*xtest-ytest,
              {"heldout_column": heldout_col, "training_gain": gain})
        design = np.column_stack((xtrain, np.ones_like(xtrain)))
        if np.linalg.matrix_rank(design) != 2:
            raise Refusal("EIT188_RANK_DEFICIENT_NUISANCE")
        coeff, *_ = np.linalg.lstsq(design, ytrain, rcond=None)
        if not np.isfinite(coeff).all():
            raise Refusal("EIT188_NONFINITE_NUISANCE_COEFFICIENTS")
        store("gain_and_offset", coeff[0]*xtest+coeff[1]-ytest, {
            "heldout_column": heldout_col, "training_gain": float(coeff[0]),
            "training_offset": float(coeff[1]),
        })

        for order in ("C", "F"):
            test_indices = flat_grids[order][:, heldout_col]
            is_train = np.ones(count, dtype=bool)
            is_train[test_indices] = False
            train_indices = np.nonzero(is_train)[0]
            train_J = j[train_indices, :]
            source_delta = flat_delta[order]
            for gamma in gammas:
                penalty = float(gamma * frozen_scale)
                solution = lsmr(train_J, source_delta[train_indices],
                                damp=math.sqrt(penalty), atol=1e-8,
                                btol=1e-8, maxiter=maxiter)
                x, code, iterations = solution[0], int(solution[1]), int(solution[2])
                if not np.isfinite(x).all():
                    raise Refusal("EIT188_NONFINITE_RIDGE_SOLUTION")
                prediction = j[test_indices, :] @ x
                err = prediction - source_delta[test_indices]
                name = f"ridge_{order}_gamma_{gamma:g}"
                store(name, err, {
                    "heldout_column": heldout_col,
                    "training_readings": int(train_indices.size),
                    "heldout_readings": int(test_indices.size),
                    "gamma": float(gamma), "lambda": penalty,
                    "solver_stop_code": code, "solver_iterations": iterations,
                    "solver_iteration_limit_reached": code == 7,
                    "solver_convergence_not_proven": code not in (1, 2),
                    "fitted_delta_coefficient_l2": float(np.linalg.norm(x)),
                    "fitted_coefficient_sha256": hashlib.sha256(
                        np.ascontiguousarray(x, dtype="<f8").tobytes()).hexdigest(),
                })

    arm_rows = []
    for name in names:
        arm = record[name]
        if (len(arm["fold_sse"]) != ncols or
                len(arm["fit_details"]) != ncols):
            raise Refusal("EIT188_INCOMPLETE_FROZEN_FOLDS")
        sse = float(sum(arm["fold_sse"]))
        arm_rows.append({
            "method": name,
            "heldout_column_count": ncols,
            "heldout_readings": count,
            "heldout_l2": math.sqrt(sse),
            "heldout_rms": math.sqrt(sse/count),
            "max_fold_rms": max(arm["fold_rms"]),
            "all_fold_rms": arm["fold_rms"],
            "all_fold_fit_details": arm["fit_details"],
        })
    lookups = {r["method"]: r["heldout_rms"] for r in arm_rows}
    if lookups["zero"] <= 0 or min(lookups["gain_only"],
                                 lookups["gain_and_offset"]) <= 0:
        # A perfect nuisance model is legitimate; retain exact zero while
        # avoiding an undefined comparative ratio.
        best_nuisance = min(lookups["gain_only"], lookups["gain_and_offset"])
    else:
        best_nuisance = min(lookups["gain_only"], lookups["gain_and_offset"])
    for r in arm_rows:
        r["rms_ratio_to_zero"] = r["heldout_rms"] / lookups["zero"]
        r["rms_ratio_to_best_nuisance"] = (
            r["heldout_rms"]/best_nuisance if best_nuisance > 0 else None)
    return {
        "schema": "agi-alpha/eit188-fixed-blocked-predictive-v1",
        "protocol": "campaign/eit-blocked-prediction188/PREREGISTRATION.md",
        "source_is_original_physical_pair": False,
        "all_fixed_columns": list(range(ncols)),
        "readings_per_heldout_column": nrows,
        "total_distinct_heldout_readings": count,
        "candidate_methods_in_fixed_order": names,
        "fixed_solver_gammas": list(gammas),
        "solver_max_iterations": maxiter,
        "full_J_frobenius_scale_per_column": frozen_scale,
        "arms": arm_rows,
        "best_nuisance_heldout_rms": best_nuisance,
        "original_full_spatial_prior_reconstructed": False,
        "original_J_row_order_independently_authenticated": False,
        "within_same_acquisition_not_independent_property_truth": True,
        "physical_uncertainty_calibrated": False,
        "complete_commercial_costs_measured": False,
        "native_financial_account_accessed": False,
        "actual_buyer_payments_usd": None,
        "decision": "HOLD_NO_DEPLOY_NO_BID",
    }


def inspect_original_archive(path: Path):
    archived = run_archive(path)
    if not archived["matched_original_currents"]:
        raise Refusal("EIT188_SOURCE_CURRENTS_NOT_MATCHED")
    with ZipFile(path) as z:
        validate_zip(z)
        js = [i for i in z.infolist()
              if not i.is_dir() and i.filename.rsplit("/", 1)[-1] == JACOBIAN_BASENAME]
        scripts = [i for i in z.infolist()
                   if not i.is_dir() and i.filename.rsplit("/", 1)[-1] == SAMPLE_BASENAME]
        if len(js) != 1 or len(scripts) != 1:
            raise Refusal("EIT188_SOURCE_OR_SCRIPT_AMBIGUOUS")
        jraw = z.read(js[0])
        if hashlib.sha256(jraw).hexdigest() != JACOBIAN_SHA:
            raise Refusal("EIT188_CHANGED_ORIGINAL_J")
        script = z.read(scripts[0])
        index = source_line_index(script, SAMPLE_SHA, SAMPLE_BYTES)
        lines = script.decode("ascii").splitlines()
        if len(lines) != 65 or index["code_bearing_line_count"] != 29:
            raise Refusal("EIT188_CHANGED_ORIGINAL_SCRIPT")
        difference_source_gate(lines[14])
        if hashlib.sha256(lines[14].encode("ascii")).hexdigest() != DIFFERENCE_LINE_SHA256:
            raise Refusal("EIT188_CHANGED_SCRIPT_DIFFERENCE")
        data = []
        for path_name, digest in MEMBERS.items():
            raw = z.read(path_name)
            if hashlib.sha256(raw).hexdigest() != digest:
                raise Refusal("EIT188_CHANGED_MEASURED_MEMBER")
            data.append(parse_member(raw))
    if not np.array_equal(data[0][0], data[1][0]):
        raise Refusal("EIT188_CHANGED_CURRENTS")
    J = load_original_J(jraw)
    if J.shape != EXPECTED_J_SHAPE or np.iscomplexobj(J):
        raise Refusal("EIT188_INVALID_ORIGINAL_J")
    if data[0][1].shape != SHAPE or data[1][1].shape != SHAPE:
        raise Refusal("EIT188_INVALID_ORIGINAL_VOLTAGES")
    receipt = fixed_blocked_predictions(J, data[0][1], data[1][1])
    receipt.update({
        "source_is_original_physical_pair": True,
        "pinned_zip_sha256": EXPECTED_SHA256,
        "jacobian_member_sha256": JACOBIAN_SHA,
        "original_matlab_example_sha256": SAMPLE_SHA,
        "measured_member_sha256": dict(MEMBERS),
        "original_currents_identical": True,
        "measured_voltage_shape": list(SHAPE),
        "original_J_shape": list(J.shape),
        "measured_source_run_manifest": archived.get("schema"),
    })
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    destination = Path(args.out)
    if destination.exists() or destination.is_symlink():
        raise Refusal("EIT188_OUTPUT_EXISTS_OR_SYMLINK")
    with tempfile.TemporaryDirectory(prefix="eit188-pinned-") as tmp:
        source = Path(tmp) / "source.zip"
        if download_exact(source) != EXPECTED_SHA256:
            raise Refusal("EIT188_SOURCE_CHANGED")
        result = inspect_original_archive(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    with os.fdopen(os.open(destination, flags, 0o600), "w", encoding="utf8") as output:
        json.dump(result, output, indent=2, sort_keys=True, allow_nan=False)
        output.write("\n")
    print(json.dumps({
        "decision": result["decision"],
        "all_fixed_arms": len(result["arms"]),
        "all_folds_per_arm": result["all_fixed_columns"],
        "source_sha256": result["pinned_zip_sha256"],
        "claims_physical_property": False,
    }, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (Refusal, OSError, ValueError, TypeError) as exc:
        print(json.dumps({"decision": "FAILED_HOLD_NO_DEPLOY", "reason": str(exc)},
                         sort_keys=True))
        raise SystemExit(2)
