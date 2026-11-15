"""EIT181: prospective archive-internal cross-stem calibration-transfer falsifier.

This is neither physical-property reconstruction nor an independently validated
instrument; no second target stem is used for fitting transferred coefficients.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import sys
import time
from urllib.error import HTTPError, URLError
from zipfile import ZipFile, BadZipFile

import numpy as np
from research import eit_chest177 as source
from research import eit_real179 as original_pair
from research import eit_repeat180 as baseline

SCHEMA = "agi-alpha/eit181-first-two-stem-transfer/v1"
FROZEN_PROTOCOL = "01f244524c68e3a1333669be9e667340c744aed6"


def first_two_data_pairs(entries):
    """Deterministic pair selection; no skipping bad/stale first or second pair."""
    groups = {}
    for info in entries:
        if info.is_dir():
            continue
        path = PurePosixPath(info.filename)
        parts = path.parts
        if (len(parts) != 3 or parts[0].casefold() != "agarchestphantom"
                or parts[1].casefold() != "data" or path.name.startswith(".")
                or path.suffix.casefold() != ".mat"):
            continue
        stem = path.stem
        if len(stem) < 3 or stem[-2:].casefold() not in ("_1", "_2"):
            continue
        key = stem[:-2].casefold()
        digit = stem[-1]
        group = groups.setdefault(key, {})
        if digit in group:
            raise source.Refused("DUPLICATE_DATA_REPEAT_SLOT")
        group[digit] = info
    choices = sorted(k for k, d in groups.items() if set(d) == {"1", "2"})
    if len(choices) < 2:
        raise source.Refused("INSUFFICIENT_DISTINCT_COMPLETE_DATA_STEMS")
    return len(choices), tuple(
        (key, groups[key]["1"], groups[key]["2"]) for key in choices[:2]
    )


def _checked_pair(c1, c2, x, y):
    arrays = tuple(np.asarray(v, dtype=np.float64) for v in (c1, c2, x, y))
    a, b, x, y = arrays
    if any(z.ndim != 2 for z in arrays) or a.shape != b.shape or x.shape != y.shape:
        raise source.Refused("REPEAT_DIMENSIONS_CHANGED")
    if a.shape != x.shape or x.shape[0] < 6 or x.shape[1] < 1:
        raise source.Refused("UNSUPPORTED_MEASUREMENT_GEOMETRY")
    if not all(np.isfinite(z).all() for z in arrays):
        raise source.Refused("NONFINITE_MEASUREMENT")
    if not np.array_equal(a, b):
        raise source.Refused("CURRENT_PATTERNS_DIFFER_WITHIN_STEM")
    return a, x, y


def compare_stems(ac1, ac2, ax, ay, bc1, bc2, bx, by):
    """All of A trains; all of B is untouched by transferred fitting."""
    ac, ax, ay = _checked_pair(ac1, ac2, ax, ay)
    bc, bx, by = _checked_pair(bc1, bc2, bx, by)
    if ax.shape != bx.shape:
        raise source.Refused("CROSS_STEM_MEASUREMENT_SHAPE_CHANGED")
    # EIT180's unmodified ordinary double-precision fitting kernels.
    g1, _ = baseline._fit(ax, ay, intercept=False)
    g2, b2 = baseline._fit(ax, ay, intercept=True)
    gains, offsets = [], []
    for j in range(ax.shape[1]):
        gain, offset = baseline._fit(ax[:, j], ay[:, j], intercept=True)
        gains.append(gain)
        offsets.append(offset)
    gains = np.asarray(gains, dtype=np.float64)
    offsets = np.asarray(offsets, dtype=np.float64)

    predictions = {
        "R0_identity": bx,
        "R1_transferred_global_gain": g1 * bx,
        "R2_transferred_global_affine": g2 * bx + b2,
        "R3_transferred_per_column_affine": bx * gains[None, :] + offsets[None, :],
    }
    report = {
        key: baseline._stats(by, pred) for key, pred in predictions.items()
    }
    # Label this within-B fitted comparison accurately: it has target-stem
    # information, so it cannot substantiate a zero-shot transfer claim.
    b_even, b_odd = bx[::2], bx[1::2]
    y_even, y_odd = by[::2], by[1::2]
    b_gain, _ = baseline._fit(b_even, y_even, intercept=False)
    oracle = baseline._stats(y_odd, b_gain * b_odd)
    raw = report["R0_identity"]["rms"]
    transferred = report["R1_transferred_global_gain"]["rms"]
    ordinary = min(
        ("R0_identity", "R1_transferred_global_gain",
         "R2_transferred_global_affine"),
        key=lambda name: (report[name]["rms"], name)
    )
    best_rms = report[ordinary]["rms"]
    special = report["R3_transferred_per_column_affine"]["rms"]
    gain_reduction = ((raw - transferred) / raw) if raw > 0 else None
    special_reduction = ((best_rms - special) / best_rms) if best_rms > 0 else None
    oracle_rms = oracle["rms"]
    optimistic_ratio = transferred / oracle_rms if oracle_rms > 0 else None
    accepts = (gain_reduction is not None and gain_reduction >= 0.50
               and optimistic_ratio is not None and optimistic_ratio <= 1.25)
    return {
        "matrix_shape": list(bx.shape),
        "first_stem_train_rows": ax.shape[0],
        "second_stem_full_evaluation_rows": bx.shape[0],
        "cross_stem_current_pattern_equal": bool(np.array_equal(ac, bc)),
        "within_each_stem_current_patterns_equal": True,
        "model_heldout_second_stem": report,
        "within_second_stem_gain_oracle_even_train_odd_eval": {
            "trained_parameters": 1,
            "second_stem_train_rows": list(range(0, bx.shape[0], 2)),
            "second_stem_odd_rows": list(range(1, bx.shape[0], 2)),
            "fitted_gain": b_gain,
            "odd_row_report": oracle,
            "has_target_stem_training_information": True,
        },
        "source_stem_a_fitted_parameters": {
            "global_gain": g1,
            "global_affine": {"gain": g2, "offset": b2},
            "per_channel_affine": [
                {"gain": float(g), "offset": float(b)}
                for g, b in zip(gains, offsets)
            ],
        },
        "ordinary_best_transferred_or_identity": ordinary,
        "gain_relative_rms_reduction_vs_identity": gain_reduction,
        "transferred_gain_to_optimistic_odd_row_rms_ratio": optimistic_ratio,
        "per_channel_relative_rms_reduction_vs_best_simple": special_reduction,
        "per_channel_improves_at_least_ten_percent": (
            special_reduction is not None and special_reduction >= 0.10
        ),
        "decision": ("TRANSFERRED_ORDINARY_GAIN_PLAUSIBLE_WITHIN_ARCHIVE"
                     if accepts else "TRANSFER_NOT_ESTABLISHED"),
        "no_physical_property_ground_truth": True,
        "no_independent_session_claim": True,
        "no_commercial_or_financial_result": True,
    }


def analyze_source(raw: bytes):
    proof = source.verify_source(raw)
    if proof["archive_sha256"] != original_pair.PINNED_SHA256:
        raise source.Refused("FROZEN_OBSERVED_SOURCE_SHA256_CHANGED")
    try:
        with ZipFile(BytesIO(raw)) as archive:
            entries, total = source._members(archive)
            count, selected = first_two_data_pairs(entries)
            records = []
            for stem, i, j in selected:
                x = source._mat(archive, i)
                y = source._mat(archive, j)
                records.append((stem, x, y))
    except BadZipFile as e:
        raise source.Refused("INVALID_SOURCE_ZIP") from e
    (_, a, a2), (_, b, b2) = records
    get = lambda item, name: item["arrays"][name]
    return {
        **proof,
        "status": "ANALYZED_ARCHIVE_INTERNAL_TRANSFER_ONLY",
        "archive_member_count": len(entries),
        "declared_uncompressed_bytes": total,
        "distinct_complete_data_stem_count": count,
        "selected_stem_names": [record[0] for record in records],
        "selected_stem_member_proofs": [
            {
                "stem": stem,
                "members": [
                    {"path": obj["path"], "sha256": obj["sha256"]}
                    for obj in (first, second)
                ],
            }
            for stem, first, second in records
        ],
        **compare_stems(
            get(a, "currents_matrix"), get(a2, "currents_matrix"),
            get(a, "voltages_matrix"), get(a2, "voltages_matrix"),
            get(b, "currents_matrix"), get(b2, "currents_matrix"),
            get(b, "voltages_matrix"), get(b2, "voltages_matrix")
        ),
        "original_eit177_result": "FAILED",
        "original_eit180_repeat_result": "DIAGNOSTIC_ONLY",
    }


def run(path):
    destination = Path(path).absolute()
    if destination.exists() or destination.is_symlink():
        raise source.Refused("CREATE_ONLY_RECEIPT_REQUIRED")
    started = time.perf_counter()
    cpu_started = time.process_time()
    receipt = {
        "schema": SCHEMA,
        "protocol_commit": FROZEN_PROTOCOL,
        "status": "FAILED",
        "failure_code": None,
        "source": source.SOURCE,
        "publisher_bytes": source.SIZE,
        "publisher_md5": source.MD5,
        "expected_observed_sha256": original_pair.PINNED_SHA256,
        "original_eit177_result": "FAILED",
        "new_instrument_qualified": False,
        "actual_paid_commerce": False,
        "trailing_365_profit_usd": None,
        "whole_host_model_billing_usd": None,
    }
    exit_code = 1
    try:
        raw = source.download_once()
        receipt.update(analyze_source(raw))
        exit_code = 0
    except HTTPError as e:
        receipt["failure_code"] = "HTTP_" + str(e.code)
    except (source.Refused, URLError, OSError, TimeoutError, ValueError) as e:
        receipt["failure_code"] = str(e) if isinstance(e, source.Refused) else type(e).__name__
    receipt["self_cpu_seconds"] = round(time.process_time() - cpu_started, 6)
    receipt["wall_seconds"] = round(time.perf_counter() - started, 6)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644), "w") as f:
        json.dump(receipt, f, indent=2, sort_keys=True, allow_nan=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps({
        key: receipt.get(key) for key in
        ("status", "decision", "failure_code", "selected_stem_names")
    }, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    sys.exit(run(parser.parse_args().output))
