#!/usr/bin/env python3
"""Replay a preregistered ground-only TOI-216b visit on its explicit clocks."""

import argparse
import csv
from datetime import datetime, UTC
from hashlib import sha256
import io
import json
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from joint_transit import shape


FIELDS = ("BJD_TDB", "JD_UTC", "rel_flux_T1", "rel_flux_err_T1", "AIRMASS", "EXPTIME")
SEC_PER_DAY = 86_400
MIN_DEPTH = 0.0018
MAX_DEPTH = 0.0125


def source_columns(source):
    reader = csv.DictReader(io.StringIO(source.decode("utf-8-sig")), delimiter="\t")
    if not set(FIELDS).issubset(reader.fieldnames or ()):
        raise ValueError("incomplete explicit ground-photometry columns")
    rows = []
    for row in reader:
        try:
            rows.append([float(row[key]) for key in FIELDS])
        except (ValueError, TypeError):
            rows.append([np.nan] * len(FIELDS))
    all_rows = np.asarray(rows).reshape(-1, len(FIELDS))
    mask = np.isfinite(all_rows).all(axis=1) & (all_rows[:, 2:] > 0).all(axis=1)
    observed = all_rows[mask]
    observed = observed[np.argsort(observed[:, 1])]
    return observed.T, len(all_rows) - len(observed)


def trapezoid(time, center, duration, exposure, _):
    """Integrate a separate short-flat-bottom model over the actual exposures."""
    nodes = np.linspace(-0.5, 0.5, 9)
    sample = time[:, None] + exposure[:, None] * nodes
    phase = np.abs((sample - center) * 2 / duration)
    return np.clip((1 - phase) / 0.80, 0, 1).mean(axis=1)


def grazing(time, center, duration, exposure, geometry):
    return shape(time, center, duration, exposure, "b", geometry)


def fit_visit(time, flux, error, exposure, trend, geometry, model_template):
    design = np.column_stack((np.ones(len(time)), trend))
    null, *_ = np.linalg.lstsq(design / error[:, None], flux / error, rcond=None)
    null_residual = (design @ null - flux) / error
    null_difference = np.sum(null_residual ** 2)

    def model(params):
        center, duration, depth, offset, slope = params
        return offset + slope * trend - depth * model_template(time, center, duration, exposure, geometry)

    def residual(params):
        return (model(params) - flux) / error

    starts = []
    for center in np.arange(time[0], time[-1], 0.20):
        for duration in np.arange(1.10, 4.20, 0.20):
            candidate_profile = model_template(time, center, duration, exposure, geometry)
            columns = np.column_stack((design, -candidate_profile))
            (offset, slope, depth), *_ = np.linalg.lstsq(columns / error[:, None], flux / error, rcond=None)
            initial = (center, duration, np.clip(depth, MIN_DEPTH, MAX_DEPTH), offset, slope)
            values = residual(initial)
            starts.append((np.dot(values, values), initial))
    bounds = ((time[0], 1, MIN_DEPTH, -np.inf, -np.inf),
              (time[-1], 4.2, MAX_DEPTH, np.inf, np.inf))
    tests = [least_squares(residual, initial, bounds=bounds,
                          x_scale=(1, 1, 0.01, 0.01, 0.01), max_nfev=180)
             for _, initial in sorted(starts, key=lambda x: x[0])[:12]]
    fitted = min((row for row in tests if row.success), key=lambda row: row.cost)
    center, duration, depth, _, _ = fitted.x
    contacts = [center - duration / 2, center + duration / 2]
    shape_covariance = np.linalg.pinv(fitted.jac.T @ fitted.jac, hermitian=True)
    scale = max(1, np.sqrt(2 * fitted.cost / (time.size - len(fitted.x))))
    return {
        "relative_center_hours": float(center), "duration_hours": float(duration), "depth_fraction": float(depth),
        "delta_weighted_residual_sum_squares": float(null_difference - 2 * fitted.cost),
        "conditional_white_timing_seconds": float(3600 * scale * np.sqrt(shape_covariance[0, 0])),
        "cadences_before_and_after": [int((time < contacts[0]).sum()), int((time > contacts[1]).sum())],
        "active_center_duration_depth_bounds": fitted.active_mask[:3].tolist(),
    }


def run(source):
    (bjd, utc, flux, sigma, airmass, exposure), excluded = source_columns(source)
    offsets = (bjd - utc) * SEC_PER_DAY
    report = {"source_sha256": sha256(source).hexdigest(), "source_bytes": len(source),
              "samples": len(bjd), "excluded": excluded, "clock": "BJD_TDB"}
    if (
        len(bjd) < 30 or bjd.min() < 2_400_000 or utc.min() < 2_400_000
        or not (np.diff(bjd) > 0).all() or not (np.diff(utc) > 0).all()
        or np.max(np.abs(offsets)) > 1000 or np.ptp(offsets) > 5
    ):
        report["decision"] = "ABSTAIN_CLOCK_OR_CADENCE"
        return report
    utc_strings = [datetime.fromtimestamp((float(value) - 2440587.5) * SEC_PER_DAY, UTC).isoformat()
                   for value in (utc[0], utc[-1])]
    report.update({"visit_utc": utc_strings, "reported_bjd_minus_jd_utc_seconds": [float(offsets.min()), float(offsets.max())]})
    origin = float(bjd[0])
    time = (bjd - origin) * 24
    norm = np.median(flux)
    error = np.maximum(sigma / norm, 0.4 * np.median(sigma / norm))
    variants = {}
    for name, trend, geometry, template in [
        ("primary_airmass", airmass, 0, grazing),
        ("independent_baseline_geometry", time, 1, grazing),
        ("trapezoid_time_baseline", time, 0, trapezoid),
    ]:
        result = fit_visit(time, flux / norm, error, exposure / 3600, trend - np.median(trend), geometry, template)
        result["mid_bjd_tdb"] = origin + result["relative_center_hours"] / 24
        variants[name] = result
    centers = [row["mid_bjd_tdb"] for row in variants.values()]
    span = (max(centers) - min(centers)) * SEC_PER_DAY
    qualified = span <= 300 and all(
        row["delta_weighted_residual_sum_squares"] >= 36 and min(row["cadences_before_and_after"]) >= 8
        and not any(row["active_center_duration_depth_bounds"])
        for row in variants.values()
    )
    report.update({"decision": "GROUND_EPOCH_DIAGNOSTIC_ACCEPT" if qualified else "ABSTAIN_MODEL_OR_COVERAGE",
                   "model_midpoint_span_seconds": span, "models": variants,
                   "april_attribution": "ABSTAIN", "forecast_adoption": "ABSTAIN"})
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ground", type=Path)
    args = parser.parse_args()
    data = args.ground.read_bytes()
    print(json.dumps(run(data), ensure_ascii=False, indent=2, allow_nan=False))
