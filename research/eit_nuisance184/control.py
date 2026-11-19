"""EIT184: pre-registered conventional global gain/offset nuisance comparison.

Research-only. Reuses verified EIT183 source bytes and exact parent member hashes.
No uncertainty calibration, property inverse solution, buyer or account authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import tempfile
from zipfile import ZipFile

import numpy as np
from research.eit_physical_control183.control import (
    MEMBERS, SHAPE, Refusal, download_exact, parse_member, validate_zip,
)


def _model_fit(x: np.ndarray, y: np.ndarray, *, affine: bool):
    """Ordinary unregularized least squares; refuse degenerate fits."""
    x, y = x.reshape(-1), y.reshape(-1)
    a = np.column_stack((x, np.ones(x.size))) if affine else x.reshape(-1, 1)
    if np.linalg.matrix_rank(a) != a.shape[1]:
        raise Refusal("DEGENERATE_NUISANCE_DESIGN")
    coef, *_ = np.linalg.lstsq(a, y, rcond=None)
    if not np.isfinite(coef).all():
        raise Refusal("NONFINITE_NUISANCE_COEFFICIENT")
    return coef


def _predict(x: np.ndarray, coef: np.ndarray):
    if coef.size == 2:
        return coef[0] * x + coef[1]
    return coef[0] * x


def nuisance_control(currents0, voltages0, currents1, voltages1):
    """Fit global conventional drift models, holding out each column in turn."""
    for v in (currents0, voltages0, currents1, voltages1):
        if (not isinstance(v, np.ndarray) or v.shape != SHAPE or
                v.dtype.kind not in "fi" or not np.isfinite(v).all()):
            raise Refusal("INCOMPATIBLE_PAIR_ARRAY")
    if not np.array_equal(currents0, currents1):
        raise Refusal("EXCITATIONS_NOT_IDENTICAL")
    x, y = np.asarray(voltages0, dtype=float), np.asarray(voltages1, dtype=float)
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise Refusal("NONFINITE_CAST")
    d = y - x
    if not np.isfinite(d).all() or not np.isfinite(np.square(d)).all():
        raise Refusal("NONFINITE_CONTRAST")
    raw = float(np.sqrt(np.mean(np.square(d))))
    if not math.isfinite(raw) or raw == 0:
        raise Refusal("NO_FINITE_NONZERO_CONTRAST")
    # Model coefficients trained on all 1264 exposed readings are descriptive only.
    gain = _model_fit(x, y, affine=False)
    affine = _model_fit(x, y, affine=True)
    gain_rms = float(np.sqrt(np.mean(np.square(y - _predict(x, gain)))))
    affine_rms = float(np.sqrt(np.mean(np.square(y - _predict(x, affine)))))
    # All 16 columns form exactly one out-of-column prediction each.
    heldout_gain = np.zeros_like(x)
    heldout_affine = np.zeros_like(x)
    for c in range(SHAPE[1]):
        included = [j for j in range(SHAPE[1]) if j != c]
        gx = _model_fit(x[:, included], y[:, included], affine=False)
        ax = _model_fit(x[:, included], y[:, included], affine=True)
        heldout_gain[:, c] = y[:, c] - _predict(x[:, c], gx)
        heldout_affine[:, c] = y[:, c] - _predict(x[:, c], ax)
    cv_gain_rms = float(np.sqrt(np.mean(np.square(heldout_gain))))
    cv_affine_rms = float(np.sqrt(np.mean(np.square(heldout_affine))))
    values = [raw, gain_rms, affine_rms, cv_gain_rms, cv_affine_rms,
              *gain.tolist(), *affine.tolist()]
    if not np.isfinite(values).all():
        raise Refusal("NONFINITE_RESULT")
    return {
        "data_shape": list(SHAPE),
        "readings_per_case": int(x.size),
        "training_and_holdout_columns": [15, 1],
        "held_out_columns_once_each": list(range(SHAPE[1])),
        "observed_raw_rms": raw,
        "all_data_gain_rms": gain_rms,
        "all_data_gain_offset_rms": affine_rms,
        "leave_column_out_gain_rms": cv_gain_rms,
        "leave_column_out_gain_offset_rms": cv_affine_rms,
        "all_data_gain_coefficient": float(gain[0]),
        "all_data_affine_gain": float(affine[0]),
        "all_data_affine_offset": float(affine[1]),
        "gain_rms_fraction_reduced_in_sample": float(1.0 - gain_rms / raw),
        "gain_offset_rms_fraction_reduced_in_sample": float(1.0 - affine_rms / raw),
        "gain_rms_fraction_reduced_heldout": float(1.0 - cv_gain_rms / raw),
        "gain_offset_rms_fraction_reduced_heldout": float(1.0 - cv_affine_rms / raw),
        "physical_error_calibration": None,
        "new_physical_information_channel": False,
        "interior_property_identified": False,
        "causal_out_of_acquisition_generalization_established": False,
    }


def run(archive_path: Path):
    with ZipFile(archive_path) as archive:
        validate_zip(archive)
        arrays = []
        for name, sha in MEMBERS.items():
            info = archive.getinfo(name)
            if info.file_size > 250_000_000:
                raise Refusal("FROZEN_MEMBER_TOO_LARGE")
            member = archive.read(info)
            if hashlib.sha256(member).hexdigest() != sha:
                raise Refusal("FROZEN_MEMBER_HASH_MISMATCH:" + name)
            arrays.append(parse_member(member))
    return nuisance_control(*arrays[0], *arrays[1])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    output = Path(args.out)
    if output.exists() or output.is_symlink():
        raise Refusal("OUTPUT_MUST_BE_NEW")
    with tempfile.TemporaryDirectory(prefix="eit184-") as tmp:
        source = Path(tmp) / "source.zip"
        sha = download_exact(source)
        measured = run(source)
    receipt = {
        "schema": "blue-sky-eit184-conventional-gain-offset-v1",
        "source_archive_sha256": sha,
        "frozen_physical_member_sha256": dict(MEMBERS),
        "ordinary_nuisance_control": measured,
        "source_reused_previously_exposed": True,
        "strong_jacobian_tikhonov_executed": False,
        "beneficiary_accepted": False,
        "actual_collected_revenue_usd": None,
        "actual_host_or_model_billing_usd": None,
        "decision": "HOLD_NO_DEPLOY_NO_BID",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "source_sha256": sha, "raw_rms": measured["observed_raw_rms"],
        "heldout_gain_offset_rms": measured["leave_column_out_gain_offset_rms"],
        "decision": receipt["decision"], "receipt": str(output)}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, Refusal) as exc:
        print(json.dumps({"decision": "FAILED_HOLD_NO_DEPLOY", "reason": str(exc)}))
        raise SystemExit(2)
