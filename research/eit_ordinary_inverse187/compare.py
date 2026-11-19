"""Pinned two-order ordinary EIT inverse diagnostic. No physical-property claim.

Does not execute the original MATLAB script or use native financial accounts.
All parameters and observed source choices were frozen in EIT187 preregistration.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import tempfile
from zipfile import ZipFile

import numpy as np
from scipy.io import loadmat
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

EXPECTED_SCRIPT_DIFFERENCE_LINE = "dV = m2.voltages_matrix(:) - m1.voltages_matrix(:);"
DIFFERENCE_LINE_SHA256 = "4cc267836d05ae695e23327f02de5ccd8499cd60bbf682fba0d6a34bc84cf7e4"
JACOBIAN_BASENAME = "J_AgarCylinderPhantom.mat"
EXPECTED_J_SHAPE = (1264, 1197)
GAMMAS = (0.01, 1.0, 100.0)
MAXITER = 100


def difference_source_gate(line: str) -> None:
    """Require an exact original MATLAB column-major vectorization expression."""
    if (line != EXPECTED_SCRIPT_DIFFERENCE_LINE or
            hashlib.sha256(line.encode("ascii")).hexdigest() != DIFFERENCE_LINE_SHA256):
        raise Refusal("MATLAB_DIFFERENCE_EXPRESSION_UNSUPPORTED")


def load_original_J(raw: bytes, shape=EXPECTED_J_SHAPE):
    """Load only the single original J variable, with no alternative selection."""
    if len(raw) > 250_000_000:
        raise Refusal("ORIGINAL_J_TOO_LARGE")
    if raw.startswith(b"MATLAB 5.0 MAT-file"):
        try:
            data = loadmat(io.BytesIO(raw), variable_names=["J"],
                           squeeze_me=False, verify_compressed_data_integrity=True)
            if "J" not in data:
                raise Refusal("ORIGINAL_J_VARIABLE_NOT_FOUND")
            matrix = data["J"]
        except Refusal:
            raise
        except (ValueError, OSError, TypeError, IndexError) as e:
            raise Refusal("ORIGINAL_MATLAB_J_INVALID") from e
    else:
        import h5py
        try:
            with h5py.File(io.BytesIO(raw), "r") as h:
                if "J" not in h or not isinstance(h.get("J", getlink=True), h5py.HardLink):
                    raise Refusal("ORIGINAL_J_VARIABLE_NOT_FOUND")
                dataset = h["J"]
                if not isinstance(dataset, h5py.Dataset) or dataset.shape != shape:
                    raise Refusal("ORIGINAL_J_SHAPE_CHANGED")
                matrix = dataset[()]
        except Refusal:
            raise
        except (ValueError, OSError, TypeError) as e:
            raise Refusal("ORIGINAL_HDF5_J_INVALID") from e
    from scipy.sparse import issparse
    if issparse(matrix):
        if matrix.shape != shape or not np.isfinite(matrix.data).all():
            raise Refusal("ORIGINAL_J_INVALID_SPARSE")
        matrix = matrix.toarray()
    result = np.asarray(matrix)
    if result.shape != shape or result.dtype.kind not in "fc" or not np.isfinite(result).all():
        raise Refusal("ORIGINAL_J_NONFINITE_SHAPE_OR_TYPE")
    return np.ascontiguousarray(result)


def fixed_ordinary_controls(J, raw_delta, *, gammas=GAMMAS, maxiter=MAXITER):
    """No parameter tuning. Preserve every preregistered order and gamma."""
    if (J.shape != EXPECTED_J_SHAPE or raw_delta.shape != SHAPE
            or not np.isfinite(J).all() or not np.isfinite(raw_delta).all()):
        raise Refusal("INCOMPATIBLE_J_OR_PHYSICAL_MATRIX")
    frob = float(np.sum(np.abs(J) ** 2, dtype=np.float64))
    if frob <= 0 or not math.isfinite(frob):
        raise Refusal("DEGENERATE_OR_UNBOUNDED_J")
    rows = []
    for order in ("C", "F"):
        # C is HDF5-storage row-major; F is raw-array MATLAB-style column major.
        # Actual original MATLAB matrix orientation is not independently witnessed.
        dV = raw_delta.reshape(-1, order=order)
        null_residual = float(np.linalg.norm(dV))
        if not math.isfinite(null_residual) or null_residual <= 0:
            raise Refusal("DEGENERATE_PHYSICAL_CONTRAST")
        samples = []
        for gamma in gammas:
            lam = float(gamma * frob / J.shape[1])
            if lam <= 0 or not math.isfinite(lam):
                raise Refusal("NONFINITE_REGULARIZATION")
            candidate = lsmr(J, dV, damp=math.sqrt(lam),
                             atol=1e-8, btol=1e-8, maxiter=maxiter)
            x, stop, iterations = candidate[0], int(candidate[1]), int(candidate[2])
            residual = float(np.linalg.norm(J @ x - dV))
            penalty = float(np.linalg.norm(x))
            if not (math.isfinite(residual) and math.isfinite(penalty)):
                raise Refusal("NONFINITE_INVERSE_OUTPUT")
            samples.append({
                "gamma": float(gamma),
                "lambda": lam,
                "residual_l2": residual,
                "residual_rms": residual / math.sqrt(dV.size),
                "ratio_to_zero_control": residual / null_residual,
                "candidate_l2": penalty,
                "objective": float(residual**2 + lam * penalty**2),
                "solver_stop_code": stop,
                "iterations": iterations,
                "solver_iteration_limit_reached": stop == 7,
                "solver_convergence_not_proven": stop not in (1, 2),
            })
        rows.append({
            "HDF5_raw_flatten_order_hypothesis": order,
            "zero_solution_residual_l2": null_residual,
            "zero_solution_residual_rms": null_residual / math.sqrt(dV.size),
            "all_fixed_regularizers": samples,
        })
    return {
        "schema": "agi-alpha/eit187-frozen-ordinary-inverse-v1",
        "source_protocol": "campaign/eit-ordinary-inverse187/PREREGISTRATION.md",
        "J_shape": list(J.shape),
        "reading_count": raw_delta.size,
        "source_script_difference_expression_verified": True,
        "original_matlab_evaluation_performed": False,
        "original_full_spatial_covariance_prior_reconstructed": False,
        "independent_original_J_row_correspondence_authenticated": False,
        "original_MATLAB_array_orientation_independently_verified": False,
        "method": "ordinary_l2_Tikhonov_diagnostic_only",
        "no_posthoc_selection_of_row_order_or_gamma": True,
        "both_predeclared_order_arms": rows,
        "property_truth_available": False,
        "sensor_repeatability_calibrated": False,
        "buyer_accepted": False,
        "commercial_collections_usd": None,
        "native_account_accessed": False,
        "actual_model_host_billing_usd": None,
        "decision": "HOLD_NO_DEPLOY_NO_BID",
    }


def inspect_frozen_archive(path: Path):
    checked = run_archive(path)
    if not checked["matched_original_currents"]:
        raise Refusal("SOURCE_CURRENT_MATCH_NOT_PROVEN")
    with ZipFile(path) as archive:
        validate_zip(archive)
        js = [i for i in archive.infolist()
              if i.filename.split("/")[-1] == JACOBIAN_BASENAME and not i.is_dir()]
        scripts = [i for i in archive.infolist()
                   if i.filename.split("/")[-1] == SAMPLE_BASENAME and not i.is_dir()]
        if len(js) != 1 or len(scripts) != 1:
            raise Refusal("ORIGINAL_SOURCE_J_OR_SCRIPT_AMBIGUOUS")
        J_raw, script = archive.read(js[0]), archive.read(scripts[0])
        if hashlib.sha256(J_raw).hexdigest() != JACOBIAN_SHA:
            raise Refusal("ORIGINAL_J_CHANGED")
        indexed = source_line_index(script, SAMPLE_SHA, SAMPLE_BYTES)
        lines = script.decode("ascii").splitlines()
        if (len(lines) != 65 or indexed["code_bearing_line_count"] != 29):
            raise Refusal("ORIGINAL_SCRIPT_CHANGED")
        difference_source_gate(lines[14])
        # Source line 58 is original authors' regularized estimator; this
        # diagnostic does NOT claim to implement its spatial covariance.
        if (hashlib.sha256(lines[57].encode("ascii")).hexdigest()
                != "f232324c3110215a0e27062c584088bcfb631cf8da802eef33945d58fff19a52"):
            raise Refusal("ORIGINAL_SCRIPT_ESTIMATOR_CHANGED")
        pairs = []
        for name, digest in MEMBERS.items():
            raw = archive.read(name)
            if hashlib.sha256(raw).hexdigest() != digest:
                raise Refusal("ORIGINAL_MEASUREMENT_CHANGED")
            pairs.append(parse_member(raw))
    if not np.array_equal(pairs[0][0], pairs[1][0]):
        raise Refusal("ORIGINAL_CURRENTS_DIFFER")
    J = load_original_J(J_raw)
    report = fixed_ordinary_controls(J, pairs[1][1] - pairs[0][1])
    report.update({
        "original_ZIP_sha256": EXPECTED_SHA256,
        "original_J_member_sha256": JACOBIAN_SHA,
        "original_script_sha256": SAMPLE_SHA,
        "original_script_difference_line_sha256": DIFFERENCE_LINE_SHA256,
        "original_measurement_member_sha256": dict(MEMBERS),
    })
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)
    destination = Path(args.out)
    if destination.exists() or destination.is_symlink():
        raise Refusal("OUTPUT_MUST_BE_FRESH")
    with tempfile.TemporaryDirectory(prefix="eit187-inverse-") as tmp:
        archive = Path(tmp) / "pinned-source.zip"
        if download_exact(archive) != EXPECTED_SHA256:
            raise Refusal("PINNED_SOURCE_CHANGED")
        receipt = inspect_frozen_archive(archive)
    destination.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_EXCL | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    with os.fdopen(os.open(destination, flags, 0o600), "w", encoding="utf8") as f:
        json.dump(receipt, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps({
        "decision": receipt["decision"],
        "order_hypotheses": [x["HDF5_raw_flatten_order_hypothesis"]
                             for x in receipt["both_predeclared_order_arms"]],
        "regularizers_per_order": len(receipt["both_predeclared_order_arms"][0]["all_fixed_regularizers"]),
        "reconstruction_of_original_full_prior": False,
        "source_sha256": receipt["original_ZIP_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (Refusal, OSError, ValueError, TypeError) as exc:
        print(json.dumps({"decision": "FAILED_HOLD_NO_DEPLOY", "reason": str(exc)}, sort_keys=True))
        raise SystemExit(2)
