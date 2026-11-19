"""EIT189 fixed authors' full covariance inverse and 16-fold predictive diagnostic.

Original MATLAB equations (sample SHA registered in EIT186/EIT189):
  iGe = (1 / 0.001)^2 I
  Gamma_ij = 2.5^2 exp(-||mesh.nodes_i-mesh.nodes_j||^2 / (2 a^2))
  a^2 = -24.5^2 / (2 log(0.01));  Gamma += 0.01 Gamma[0,0] I
  ds = (J.T iGe J + inv(Gamma))^-1 J.T iGe dV

An exactly equivalent dual-space formula is used numerically:
  H=J Gamma J.T + 0.001^2 I, ds=Gamma J.T solve(H,dV).
Posterior predictive whole-column scores are separate from full-data ds.
No MATLAB execution, no inferred row-order truth or physical-property claim.
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
from scipy.linalg import cho_factor, cho_solve
from scipy.spatial.distance import cdist

from research.eit_physical_control183.control import (
    EXPECTED_SHA256, MEMBERS, SHAPE, Refusal, download_exact,
    parse_member, validate_zip,
)
from research.eit_ordinary_inverse187.compare import (
    EXPECTED_J_SHAPE, JACOBIAN_BASENAME, load_original_J,
)
from research.eit_matlab_source186.review import JACOBIAN_SHA
from research.eit_author_inverse189.inspect import inspect_original, write_fresh

MESH_NAME = "AgarCylinderPhantom/Data/mesh_AgarCylinderPhantom_2D_inverse_1197.mat"
MESH_SHA256 = "13a82df71bd70641c73115f6d37643fe0a4ea4a73c83be36e07281e56723ad4c"
NOISE_STD = 0.001
DISTANCE_AT_CC = 24.5
CORRELATION_AT_DISTANCE = 0.01
CONDUCTIVITY_STD = 2.5
STABILIZATION = 0.01
EXPECTED_NODES = 1197


def original_inverse_nodes(raw: bytes):
    """Read the exact 2-D inverse mesh nodes; no guessed/alternative geometry."""
    if len(raw) > 250_000_000:
        raise Refusal("EIT189_MESH_TOO_LARGE")
    if raw.startswith(b"MATLAB 5.0 MAT-file"):
        try:
            mat = loadmat(io.BytesIO(raw), struct_as_record=False, squeeze_me=True,
                          variable_names=["mesh"], verify_compressed_data_integrity=True)
            if "mesh" not in mat:
                raise Refusal("EIT189_ORIGINAL_MESH_VARIABLE_MISSING")
            mesh = mat["mesh"]
            if not hasattr(mesh, "nodes"):
                raise Refusal("EIT189_MATLAB_MESH_NODES_MISSING")
            points = np.asarray(mesh.nodes)
        except Refusal:
            raise
        except (ValueError, OSError, TypeError, IndexError) as exc:
            raise Refusal("EIT189_MAT5_MESH_INVALID") from exc
    else:
        import h5py
        try:
            with h5py.File(io.BytesIO(raw), "r") as h:
                if "mesh" not in h or not isinstance(h.get("mesh", getlink=True), h5py.HardLink):
                    raise Refusal("EIT189_ORIGINAL_MESH_VARIABLE_MISSING")
                group = h["mesh"]
                if not isinstance(group, h5py.Group):
                    raise Refusal("EIT189_MESH_NOT_A_STRUCT_GROUP")
                if "nodes" not in group or not isinstance(group.get("nodes", getlink=True), h5py.HardLink):
                    raise Refusal("EIT189_MESH_NODES_MISSING")
                dataset = group["nodes"]
                if not isinstance(dataset, h5py.Dataset):
                    raise Refusal("EIT189_NODES_NOT_A_DATASET")
                obj = dataset[()]
                if obj.dtype.kind == "O":
                    # MATLAB v7.3 structs may use a one-element object reference.
                    refs = obj.ravel()
                    if len(refs) != 1 or not isinstance(refs[0], h5py.Reference) or not refs[0]:
                        raise Refusal("EIT189_NODES_REFERENCE_AMBIGUOUS")
                    actual = h[refs[0]]
                    if not isinstance(actual, h5py.Dataset):
                        raise Refusal("EIT189_NODES_REF_NOT_DATASET")
                    obj = actual[()]
                points = np.asarray(obj)
        except Refusal:
            raise
        except (OSError, ValueError, TypeError, IndexError) as exc:
            raise Refusal("EIT189_HDF5_MESH_INVALID") from exc

    if points.dtype.kind != "f" or points.ndim != 2:
        raise Refusal("EIT189_MESH_NUMERIC_DIMENSION_INVALID")
    # v7.3 h5py surfaces MATLAB's 2xN array in reverse-axis storage;
    # reject any other orientation rather than fitting the data to choose.
    if points.shape == (2, EXPECTED_NODES):
        points = points.T
    elif points.shape != (EXPECTED_NODES, 2):
        raise Refusal("EIT189_MESH_NODE_COUNT_OR_DIMENSION_CHANGED")
    points = np.asarray(points, dtype=np.float64, order="C")
    if not np.isfinite(points).all():
        raise Refusal("EIT189_NONFINITE_MESH_NODES")
    if np.unique(points, axis=0).shape[0] != EXPECTED_NODES:
        raise Refusal("EIT189_DUPLICATE_MESH_NODES")
    return points


def fixed_original_prior(nodes: np.ndarray):
    """Literal original mesh correlation prior, not L2-ridge substitution."""
    a = np.asarray(nodes, dtype=np.float64)
    if a.ndim != 2 or a.shape[1] != 2 or not np.isfinite(a).all():
        raise Refusal("EIT189_MESH_NODES_INCOMPATIBLE")
    corr_sq = -(DISTANCE_AT_CC ** 2) / (2 * math.log(CORRELATION_AT_DISTANCE))
    if not (math.isfinite(corr_sq) and corr_sq > 0):
        raise Refusal("EIT189_BAD_ORIGINAL_PRIOR_PARAMETER")
    sqdist = cdist(a, a, "sqeuclidean")
    prior = (CONDUCTIVITY_STD ** 2) * np.exp(-sqdist / (2 * corr_sq))
    prior.flat[::a.shape[0] + 1] += STABILIZATION * prior[0, 0]
    if not np.isfinite(prior).all():
        raise Refusal("EIT189_NONFINITE_PRIOR")
    if not np.allclose(prior, prior.T, atol=1e-12, rtol=1e-13):
        raise Refusal("EIT189_ASYMMETRIC_PRIOR")
    try:
        cho_factor(prior, lower=True, check_finite=True)
    except np.linalg.LinAlgError as exc:
        raise Refusal("EIT189_ORIGINAL_PRIOR_NOT_SPD") from exc
    return prior


def author_posterior(J, prior):
    j, g = np.asarray(J), np.asarray(prior)
    if (j.ndim != 2 or g.shape != (j.shape[1], j.shape[1]) or
            j.dtype.kind != "f" or g.dtype.kind != "f" or
            not np.isfinite(j).all() or not np.isfinite(g).all()):
        raise Refusal("EIT189_J_OR_PRIOR_INVALID")
    H = (j @ g) @ j.T
    H.flat[::j.shape[0] + 1] += NOISE_STD ** 2
    if not np.isfinite(H).all():
        raise Refusal("EIT189_NONFINITE_MEASUREMENT_COVARIANCE")
    H = (H + H.T) * 0.5
    try:
        fac = cho_factor(H, lower=True, check_finite=True)
        precision = cho_solve(fac, np.eye(j.shape[0]))
    except np.linalg.LinAlgError as exc:
        raise Refusal("EIT189_AUTHOR_POSTERIOR_NOT_SPD") from exc
    if not np.isfinite(precision).all() or not np.allclose(
            precision, precision.T, rtol=1e-7, atol=1e-7):
        raise Refusal("EIT189_UNSTABLE_AUTHOR_PRECISION")
    return H, fac, precision


def conditional_prediction_from_precision(precision, observed, heldout_indices):
    """Exact Gaussian block conditional; must match direct training-only solve.

    Although the algebra computes P*y, the heldout contribution cancels
    identically in y_h - (P_hh)^-1 (P*y)_h. Offline mutation/direct tests
    verify there is no access to target y in the returned prediction.
    """
    p, y = np.asarray(precision), np.asarray(observed)
    idx = np.asarray(heldout_indices, dtype=np.intp)
    if (p.ndim != 2 or p.shape != (y.size, y.size) or
            idx.ndim != 1 or len(np.unique(idx)) != idx.size or
            idx.size == 0 or idx.size >= y.size or np.any(idx < 0) or
            np.any(idx >= y.size) or not np.isfinite(p).all() or
            not np.isfinite(y).all()):
        raise Refusal("EIT189_INVALID_HELDOUT_PREDICTION_INPUT")
    sub = p[np.ix_(idx, idx)]
    try:
        residual = np.linalg.solve(sub, (p @ y)[idx])
    except np.linalg.LinAlgError as exc:
        raise Refusal("EIT189_HELDOUT_PRECISION_SINGULAR") from exc
    estimate = y[idx] - residual
    if not np.isfinite(estimate).all():
        raise Refusal("EIT189_NONFINITE_HELDOUT_ESTIMATE")
    return estimate


def conditional_prediction_direct(H, observed, heldout_indices):
    """Independent strong direct train-only construction (offline control)."""
    h, y = np.asarray(H), np.asarray(observed)
    idx = np.asarray(heldout_indices, dtype=np.intp)
    train = np.ones(y.size, dtype=bool)
    train[idx] = False
    block = h[np.ix_(train, train)]
    return h[np.ix_(idx, train)] @ np.linalg.solve(block, y[train])


def all_folds(j, nodes, baseline, changed):
    a, b = np.asarray(baseline), np.asarray(changed)
    if (a.shape != b.shape or a.ndim != 2 or a.shape[1] < 2 or
            a.shape[0] < 2 or j.shape[0] != a.size or
            j.shape[1] != nodes.shape[0] or
            a.dtype.kind != "f" or b.dtype.kind != "f" or
            not np.isfinite(a).all() or not np.isfinite(b).all()):
        raise Refusal("EIT189_ARRAY_SHAPE_OR_FINITE_INVALID")

    prior = fixed_original_prior(nodes)
    H, factor, P = author_posterior(j, prior)
    n, cols = a.shape
    count = a.size
    grid_all = np.arange(count)
    arms = []
    for order in ("C", "F"):
        grid = grid_all.reshape(a.shape, order=order)
        dV = (b-a).reshape(-1, order=order)
        # Faithful all-observation normal-equation posterior using the
        # authors' full fixed prior; no externally verified conductivity.
        ds = prior @ j.T @ cho_solve(factor, dV)
        if not np.isfinite(ds).all():
            raise Refusal("EIT189_NONFINITE_AUTHOR_DS")
        alpha = P @ dV
        folds = []
        for col in range(cols):
            idx = grid[:, col]
            psub = P[np.ix_(idx, idx)]
            try:
                # Reuse alpha instead of recomputing a full matrix product.
                pred = dV[idx] - np.linalg.solve(psub, alpha[idx])
            except np.linalg.LinAlgError as exc:
                raise Refusal("EIT189_CONDITIONAL_PRECISION_SINGULAR") from exc
            if not np.isfinite(pred).all():
                raise Refusal("EIT189_NONFINITE_AUTHOR_FOLD")
            err = pred-dV[idx]
            folds.append({
                "heldout_column": col,
                "heldout_count": n,
                "heldout_sse": float(err @ err),
                "heldout_rms": float(np.linalg.norm(err)/math.sqrt(n)),
            })
            # Direct train-only physical-row algebra checks the first fold;
            # this is never a choice of method or selection of heldout data.
            if col == 0:
                direct = conditional_prediction_direct(H, dV, idx)
                if not np.allclose(pred, direct, rtol=1e-5, atol=1e-7):
                    raise Refusal("EIT189_AUTHOR_FOLD_DISAGREES_WITH_DIRECT_TRAIN_ONLY")
        if len(folds) != cols:
            raise Refusal("EIT189_MISSING_FROZEN_FOLD")
        sse = sum(f["heldout_sse"] for f in folds)
        arms.append({
            "raw_hdf5_vector_order_hypothesis": order,
            "all_column_folds": folds,
            "distinct_heldout_count": count,
            "pooled_heldout_l2": math.sqrt(sse),
            "pooled_heldout_rms": math.sqrt(sse/count),
            "full_data_author_ds_l2": float(np.linalg.norm(ds)),
            "full_data_author_ds_sha256": hashlib.sha256(
                np.asarray(ds, dtype="<f8", order="C").tobytes()
            ).hexdigest(),
            "fully_source_bound_prior": True,
        })
    # Ordinary strongest competent nuisance benchmark from EIT188 is
    # recomputed on identical heldout columns, without altering its terms.
    gain_sse, offset_sse, zero_sse = 0.0, 0.0, 0.0
    for col in range(cols):
        train = np.ones(a.shape, dtype=bool)
        train[:, col] = False
        xa, yb = a[train], b[train]
        xt, yt = a[:, col], b[:, col]
        denominator = float(xa @ xa)
        if denominator <= 0:
            raise Refusal("EIT189_NUISANCE_GAIN_UNDEFINED")
        gain = float(xa @ yb / denominator)
        design = np.column_stack((xa, np.ones_like(xa)))
        if np.linalg.matrix_rank(design) != 2:
            raise Refusal("EIT189_NUISANCE_OFFSET_UNIDENTIFIABLE")
        coefficients, *_ = np.linalg.lstsq(design, yb, rcond=None)
        gain_sse += float(np.sum((gain*xt-yt)**2))
        offset_sse += float(np.sum((coefficients[0]*xt+coefficients[1]-yt)**2))
        zero_sse += float(np.sum((xt-yt)**2))
    return {
        "schema": "agi-alpha/eit189-authors-covariance-frozen-heldout-v1",
        "fixed_original_author_parameters": {
            "eStd": NOISE_STD, "dsCL": DISTANCE_AT_CC,
            "cc": CORRELATION_AT_DISTANCE, "dsStd": CONDUCTIVITY_STD,
            "diagonal_stabilization_fraction": STABILIZATION,
        },
        "original_mesh_node_shape": list(nodes.shape),
        "J_shape": list(j.shape),
        "heldout_column_count": cols,
        "all_methods": arms,
        "ordinary_gain_only_rms": math.sqrt(gain_sse/count),
        "ordinary_gain_and_offset_rms": math.sqrt(offset_sse/count),
        "ordinary_zero_change_rms": math.sqrt(zero_sse/count),
        "complete_original_prior_reproduced_numerically": True,
        "source_order_independently_authenticated": False,
        "authors_original_matlab_run_executed": False,
        "physical_property_truth_verified": False,
        "sensor_noise_independently_measured": False,
        "native_account_accessed": False,
        "revenue_collected_usd": None,
        "whole_campaign_host_model_billing_usd": None,
        "decision": "HOLD_NO_DEPLOY_NO_BID",
    }


def inspect_pinned_physical_archive(path: Path):
    # Guard every source, original author expression, J candidate, and mesh.
    semantics = inspect_original(path)
    with ZipFile(path) as z:
        validate_zip(z)
        mesh_raw = z.read(MESH_NAME)
        if hashlib.sha256(mesh_raw).hexdigest() != MESH_SHA256:
            raise Refusal("EIT189_INVERSE_MESH_SOURCE_CHANGED")
        js = [x for x in z.infolist()
              if not x.is_dir() and x.filename.rsplit("/", 1)[-1] == JACOBIAN_BASENAME]
        if len(js) != 1:
            raise Refusal("EIT189_ORIGINAL_J_AMBIGUOUS")
        rawJ = z.read(js[0])
        if hashlib.sha256(rawJ).hexdigest() != JACOBIAN_SHA:
            raise Refusal("EIT189_ORIGINAL_J_CHANGED")
        observations = []
        for name, digest in MEMBERS.items():
            raw = z.read(name)
            if hashlib.sha256(raw).hexdigest() != digest:
                raise Refusal("EIT189_MEASUREMENTS_CHANGED")
            observations.append(parse_member(raw))
    if not np.array_equal(observations[0][0], observations[1][0]):
        raise Refusal("EIT189_CURRENTS_NOT_MATCHED")
    nodes = original_inverse_nodes(mesh_raw)
    J = load_original_J(rawJ)
    if J.shape != EXPECTED_J_SHAPE or nodes.shape != (EXPECTED_NODES, 2):
        raise Refusal("EIT189_ORIGINAL_MESH_J_DIMENSIONS_CHANGED")
    result = all_folds(J, nodes, observations[0][1], observations[1][1])
    result.update({
        "protocol_freeze": "campaign/eit-original-authors189/STAGE2_FREEZE.md",
        "original_archive_sha256": EXPECTED_SHA256,
        "original_J_sha256": JACOBIAN_SHA,
        "original_mesh_sha256": MESH_SHA256,
        "original_author_script_sha256": semantics["original_matlab_sha256"],
        "original_measurements_sha256": dict(MEMBERS),
    })
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    dest = Path(parser.parse_args(argv).out)
    if dest.exists() or dest.is_symlink():
        raise Refusal("EIT189_OUTPUT_MUST_BE_FRESH")
    with tempfile.TemporaryDirectory(prefix="eit189-full-author-inverse-") as d:
        source = Path(d) / "source.zip"
        if download_exact(source) != EXPECTED_SHA256:
            raise Refusal("EIT189_SOURCE_SHA_CHANGED")
        result = inspect_pinned_physical_archive(source)
    write_fresh(dest, result)
    print(json.dumps({
        "decision": result["decision"],
        "all_author_hypotheses": len(result["all_methods"]),
        "all_folds": result["heldout_column_count"],
        "source_verified": True, "original_prior_reproduced": True,
        "independent_property_acceptance": False,
    }, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (Refusal, OSError, ValueError, TypeError) as error:
        print(json.dumps({"decision": "FAILED_HOLD_NO_DEPLOY",
                          "reason": str(error)}, sort_keys=True))
        raise SystemExit(2)
