"""EIT180: frozen even-row/odd-row repeat calibration against ordinary baselines.

This is a *diagnostic* of one pair of real phantom measurements, not an inverse
conductivity solution, device calibration, new observation, or commercial result.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from zipfile import BadZipFile, ZipFile

import numpy as np
from research import eit_chest177 as original
from research import eit_real179 as previous

FROZEN_PROTOCOL = "6cafa6ac49472393671e13230a3be5462cbff824"
SCHEMA = "agi-alpha/eit180-cross-replicate-structure/v1"


def _fit(x: np.ndarray, y: np.ndarray, *, intercept: bool) -> tuple[float, float]:
    """Explicit one-dimensional ordinary least squares; no hidden regularization."""
    a = np.asarray(x, dtype=np.float64).reshape(-1)
    b = np.asarray(y, dtype=np.float64).reshape(-1)
    if len(a) != len(b) or len(a) < 3 or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise original.Refused("INVALID_FINITE_TRAINING_PAIR")
    if intercept:
        am, bm = float(np.mean(a)), float(np.mean(b))
        ac, bc = a-am, b-bm
        denominator = float(np.dot(ac, ac))
        numerator = float(np.dot(ac, bc))
    else:
        am, bm = 0., 0.
        denominator = float(np.dot(a, a))
        numerator = float(np.dot(a, b))
    if not np.isfinite(denominator) or denominator <= 1.e-24:
        raise original.Refused("RANK_DEFICIENT_TRAINING")
    gain = numerator / denominator
    offset = bm - gain * am if intercept else 0.
    if not np.isfinite([gain, offset]).all():
        raise original.Refused("NONFINITE_FITTED_PARAMETERS")
    return float(gain), float(offset)


def _stats(actual: np.ndarray, predicted: np.ndarray) -> dict:
    residual = np.asarray(actual) - np.asarray(predicted)
    if residual.shape != actual.shape or not np.isfinite(residual).all():
        raise original.Refused("NONFINITE_OR_WRONG_SHAPE_PREDICTION")
    return {
        "rms": float(np.sqrt(np.mean(np.square(residual)))),
        "mean_absolute_error": float(np.mean(np.abs(residual))),
        "per_column_rms": [float(x) for x in np.sqrt(np.mean(residual*residual, axis=0))],
    }


def analyze_arrays(currents_first, currents_second, voltage_first, voltage_second) -> dict:
    ci, cj = map(lambda a: np.asarray(a, dtype=np.float64), (currents_first, currents_second))
    x, y = map(lambda a: np.asarray(a, dtype=np.float64), (voltage_first, voltage_second))
    if any(z.ndim != 2 for z in (ci, cj, x, y)) or ci.shape != cj.shape or x.shape != y.shape:
        raise original.Refused("REPEAT_DIMENSIONS_CHANGED")
    if ci.shape != x.shape or x.shape[0] < 6 or x.shape[1] < 1:
        raise original.Refused("UNSUPPORTED_MEASUREMENT_GEOMETRY")
    if not all(np.isfinite(z).all() for z in (ci, cj, x, y)):
        raise original.Refused("NONFINITE_MEASUREMENT")
    if not np.array_equal(ci, cj):
        raise original.Refused("CURRENT_PATTERNS_DIFFER")
    # Immutable parity split. No target holdout value enters parameter estimation.
    x_train, y_train = x[::2], y[::2]
    x_hold, y_hold = x[1::2], y[1::2]
    g1, b1 = _fit(x_train, y_train, intercept=False)
    g2, b2 = _fit(x_train, y_train, intercept=True)
    gains, offsets = [], []
    for col in range(x.shape[1]):
        g, b = _fit(x_train[:, col], y_train[:, col], intercept=True)
        gains.append(g)
        offsets.append(b)
    c3 = x_hold * np.asarray(gains)[None, :] + np.asarray(offsets)[None, :]
    c3_train = x_train * np.asarray(gains)[None, :] + np.asarray(offsets)[None, :]
    models = {
        "O0_identity": (x_train, x_hold, 0),
        "O1_global_gain": (g1*x_train, g1*x_hold, 1),
        "O2_global_affine": (g2*x_train+b2, g2*x_hold+b2, 2),
        "C3_per_column_affine": (c3_train, c3, 2*x.shape[1]),
    }
    out = {}
    for name, (train, held, nparams) in models.items():
        out[name] = {"trained_parameters": nparams,
                     "development": _stats(y_train, train),
                     "holdout": _stats(y_hold, held)}
    best_name = min(("O0_identity","O1_global_gain","O2_global_affine"),
                    key=lambda name: (out[name]["holdout"]["rms"], name))
    ordinary = out[best_name]["holdout"]["rms"]
    candidate = out["C3_per_column_affine"]["holdout"]["rms"]
    raw_cols = out["O0_identity"]["holdout"]["per_column_rms"]
    proposed_cols = out["C3_per_column_affine"]["holdout"]["per_column_rms"]
    no_large_regression = all((p <= 2.*v if v > 0. else p == 0.)
                              for p, v in zip(proposed_cols, raw_cols))
    improvement = (ordinary-candidate)/ordinary if ordinary > 0 else None
    # A ratio between two machine-roundoff residuals is not evidence of
    # incremental structure. Scale the IEEE-754 tolerance to the observed
    # heldout voltage amplitudes rather than imposing a voltage-unit floor.
    precision_floor = float(
        64. * np.finfo(np.float64).eps *
        max(float(np.max(np.abs(x_hold))), float(np.max(np.abs(y_hold))))
    )
    ordinary_at_machine_precision = ordinary <= precision_floor
    structured = (not ordinary_at_machine_precision
                  and improvement is not None and improvement >= 0.10
                  and no_large_regression)
    return {
        "matrix_shape": list(x.shape),
        "development_rows": list(range(0, x.shape[0], 2)),
        "holdout_rows": list(range(1, x.shape[0], 2)),
        "current_matrix_exact_match": True,
        "models": out,
        "ordinary_best_name": best_name,
        "incremental_heldout_rms_reduction_over_best_ordinary": improvement,
        "ordinary_precision_floor": precision_floor,
        "ordinary_at_machine_precision": ordinary_at_machine_precision,
        "per_channel_no_more_than_double_raw_rms": no_large_regression,
        "decision": "CONDITIONAL_REPEAT_STRUCTURE_ONLY" if structured
                    else "REJECT_INCREMENTAL_STRUCTURE",
        "global_gain": g1,
        "global_affine": {"gain": g2, "offset": b2},
        "per_column_affine_parameters": [
            {"gain": float(g), "offset": float(b)}
            for g, b in zip(gains, offsets)
        ],
        "not_a_new_measurement_or_inversion": True,
        "no_ground_truth_property_validation": True,
        "actual_commerce_proved": False,
    }


def analyze_source(raw: bytes) -> dict:
    proof = original.verify_source(raw)
    if proof["archive_sha256"] != previous.PINNED_SHA256:
        raise original.Refused("FROZEN_OBSERVED_SOURCE_SHA256_CHANGED")
    try:
        with ZipFile(BytesIO(raw)) as z:
            entries, declared = original._members(z)
            stem, member1, member2 = previous.true_data_first_pair(entries)
            first, second = original._mat(z, member1), original._mat(z, member2)
    except BadZipFile as e:
        raise original.Refused("INVALID_SOURCE_ZIP") from e
    return {
        **proof,
        "selected_true_data_stem": stem,
        "zip_member_count": len(entries),
        "declared_uncompressed_bytes": declared,
        "members": [{"path": m["path"], "sha256": m["sha256"]}
                    for m in (first, second)],
        **analyze_arrays(first["arrays"]["currents_matrix"],
                         second["arrays"]["currents_matrix"],
                         first["arrays"]["voltages_matrix"],
                         second["arrays"]["voltages_matrix"]),
        "original_eit177_source_run": "FAILED",
        "eit178_format_diagnosis": "SUCCESS",
        "eit179_real_pair": "SUCCESS",
    }


def run(output) -> int:
    path = Path(output).absolute()
    if path.exists() or path.is_symlink():
        raise original.Refused("CREATE_ONLY_RECEIPT")
    wall, cpu = time.perf_counter(), time.process_time()
    receipt = {
        "schema": SCHEMA, "protocol_commit": FROZEN_PROTOCOL,
        "status": "FAILED", "source": original.SOURCE,
        "publisher_bytes": original.SIZE, "publisher_md5": original.MD5,
        "expected_archive_sha256": previous.PINNED_SHA256,
        "original_eit177_source_run": "FAILED",
        "new_instrument_qualified": False,
        "conductivity_reconstruction_tested": False,
        "actual_commerce_proved": False,
        "whole_host_and_model_billing_usd": None,
    }
    code = 1
    try:
        raw = original.download_once()
        receipt.update(analyze_source(raw))
        receipt["failure_code"] = None
        receipt["status"] = "ANALYZED_DIAGNOSTIC_ONLY"
        code = 0
    except HTTPError as e:
        receipt["failure_code"] = "HTTP_" + str(e.code)
    except (original.Refused, URLError, OSError, TimeoutError, ValueError) as e:
        receipt["failure_code"] = str(e) if isinstance(e, original.Refused) else type(e).__name__
    receipt["self_cpu_seconds"] = round(time.process_time()-cpu, 6)
    receipt["wall_seconds"] = round(time.perf_counter()-wall, 6)
    path.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644),
                   "w") as fp:
        json.dump(receipt, fp, indent=2, sort_keys=True, allow_nan=False)
        fp.write("\n")
        fp.flush()
        os.fsync(fp.fileno())
    print(json.dumps({k: receipt.get(k) for k in
                      ("status", "decision", "selected_true_data_stem", "failure_code")},
                     sort_keys=True))
    return code


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True)
    return run(p.parse_args().output)


if __name__ == "__main__":
    sys.exit(main())
