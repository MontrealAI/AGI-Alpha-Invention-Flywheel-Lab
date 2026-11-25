"""Fit public TOI-216 c ground photometry without any TESS data or event times."""

import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares


RADIUS_RATIO = 0.123
SECONDS_PER_DAY = 86_400
SOURCE_IDS = (5821, 10172)
COLUMNS = ("BJD_TDB", "JD_UTC", "rel_flux_T1", "rel_flux_err_T1", "AIRMASS", "EXPTIME")
# Label, nuisance baseline, impact parameter and quadratic limb coefficients.
VARIANTS = (
    ("primary", "airmass", 0.14, 0.50, 0.20),
    ("linear-time", "time", 0.14, 0.50, 0.20),
    ("weak-limb-darkening", "airmass", 0.24, 0.35, 0.20),
    ("strong-limb-darkening", "airmass", 0.24, 0.65, 0.16),
)


def sha(raw):
    return sha256(raw).hexdigest()


def utc_date(julian):
    return datetime.fromtimestamp((julian - 2440587.5) * SECONDS_PER_DAY, timezone.utc).isoformat()


def read_columns(raw):
    values = []
    for record in csv.DictReader(io.StringIO(raw.decode("utf-8-sig")), delimiter="\t"):
        try:
            values.append([float(record[name]) for name in COLUMNS])
        except (TypeError, ValueError):
            values.append([float("nan")] * len(COLUMNS))
    matrix = np.array(values, dtype=float)
    finite = np.isfinite(matrix).all(axis=1)
    usable = finite & (matrix[:, :2] > 2_400_000).all(axis=1) & (matrix[:, 2:] > 0).all(axis=1)
    used = matrix[usable]
    used = used[np.argsort(used[:, 0])]
    if len(used) < 30 or np.any(np.diff(used[:, 0]) <= 0):
        raise ValueError("Too few independent ground samples or duplicate BJD_TDB")
    return used.T, len(matrix) - len(used)


def occultation_profile(impact, limb1, limb2):
    """Integrate the masked fraction of the stellar disk in radial annuli."""
    radius = (np.arange(1200) + 0.5) / 1200
    mu = np.sqrt(1.0 - radius * radius)
    intensity = (1 - limb1 * (1 - mu) - limb2 * (1 - mu) ** 2) * radius
    separation = np.linspace(impact, 1.0 + RADIUS_RATIO, 3000)
    distance = separation[:, None]
    argument = (radius * radius + distance * distance - RADIUS_RATIO ** 2) / (2 * radius * distance)
    arc_fraction = np.arccos(np.clip(argument, -1.0, 1.0)) / np.pi
    missing = (arc_fraction @ intensity) / intensity.sum()
    return separation, missing / missing[0]


def red_noise_factor(time, residual):
    bin_ids = np.floor((time - time.min()) / (10.0 / 60.0)).astype(int)
    samples = np.bincount(bin_ids)
    residual_sum = np.bincount(bin_ids, weights=residual)
    valid = samples >= 3
    unbinned = np.std(residual, ddof=1)
    if valid.sum() < 5 or unbinned == 0:
        return 1.0
    whitened = residual_sum[valid] / np.sqrt(samples[valid])
    return max(1.0, float(np.std(whitened, ddof=1) / unbinned))


def fit_variant(time, flux, errors, airmass, exposure, variant):
    name, baseline_kind, impact, limb1, limb2 = variant
    baseline = airmass if baseline_kind == "airmass" else time
    baseline = baseline - np.median(baseline)
    nodes, weights = np.polynomial.legendre.leggauss(5)
    mid_exposure = time[:, None] + (exposure[:, None] / 7200.0) * nodes
    separations, losses = occultation_profile(impact, limb1, limb2)
    half_chord = np.sqrt((1.0 + RADIUS_RATIO) ** 2 - impact ** 2)

    def model(parameters):
        center, duration, depth, intercept, slope = parameters
        advance = (mid_exposure - center) * (2.0 * half_chord / duration)
        distance = np.sqrt(impact ** 2 + advance ** 2)
        attenuation = np.interp(distance, separations, losses, right=0.0) @ (weights / 2.0)
        return (1 + intercept + slope * baseline) * (1 - depth * attenuation)

    def residual(parameters):
        return (model(parameters) - flux) / errors

    lower = (time[0], 4.3, 0.005, -0.20, -0.09)
    upper = (time[-1], 6.8, 0.035, 0.20, 0.09)
    start_centers = np.linspace(time[0], time[-1], max(13, int(np.ptp(time) / 0.4) + 1))
    fits = [
        least_squares(
            residual, (center, 5.47, 0.018, 0.0, 0.0),
            bounds=(lower, upper), loss="soft_l1", f_scale=2.0,
            x_scale=(2.0, 2.0, 0.02, 0.02, 0.01), max_nfev=250,
        )
        for center in start_centers
    ]
    successful = [r for r in fits if r.success]
    if not successful:
        raise ArithmeticError(f"No successful bounded fit for {name}")
    fit = min(successful, key=lambda r: r.cost)
    center, duration, depth, _, _ = fit.x
    residuals = residual(fit.x)
    covariance = np.linalg.pinv(fit.jac.T @ fit.jac, hermitian=True)
    noise_scale = max(1.0, float(1.4826 * np.median(np.abs(residuals - np.median(residuals)))))
    sigma_white_s = float(np.sqrt(covariance[0, 0]) * noise_scale * 3600)
    half_full = duration / (2.0 * half_chord) * np.sqrt((1.0 - RADIUS_RATIO) ** 2 - impact ** 2)
    contacts = np.array([-duration / 2.0, -half_full, half_full, duration / 2.0])
    counts = np.bincount(np.searchsorted(contacts, time - center), minlength=5)
    return {
        "variant": name,
        "baseline": baseline_kind,
        "impact_parameter": impact,
        "quadratic_limb_coefficients": [limb1, limb2],
        "relative_midpoint_hours": float(center),
        "duration_hours": float(duration),
        "fractional_depth": float(depth),
        "contact_offsets_hours": contacts.tolist(),
        "cadence_counts": dict(zip(("before", "ingress", "interior", "egress", "after"), counts.tolist())),
        "parameter_at_bound": [name for name, active in zip(("center", "duration", "depth", "intercept", "slope"), fit.active_mask) if active],
        "successful_start_count": len(successful),
        "attempted_start_count": len(fits),
        "normalized_flux_residual_rms_ppt": float(np.std(model(fit.x) - flux, ddof=1) * 1000),
        "white_sigma_s": sigma_white_s,
        "ten_minute_binning_factor": red_noise_factor(time, residuals),
        "cost": float(fit.cost),
    }


def fit_file(source, directory):
    path = directory / source["file_name"]
    raw = path.read_bytes()
    if sha(raw) != source["sha256"] or len(raw) != source["bytes"]:
        raise ValueError(f"Ground photometry digest mismatch in {path.name}")
    (bjd, utc, flux, error, airmass, exposure), excluded = read_columns(raw)
    reference = float(np.floor(np.median(bjd)))
    time = (bjd - reference) * 24.0
    clock_correction = (bjd - utc) * SECONDS_PER_DAY
    norm = float(np.median(flux))
    scaled_errors = error / norm
    errors = np.maximum(scaled_errors, np.median(scaled_errors) * 0.4)
    variants = [fit_variant(time, flux / norm, errors, airmass, exposure, v) for v in VARIANTS]
    primary = variants[0]
    midpoint_hour = primary["relative_midpoint_hours"]
    shape_change_s = 3600 * max(abs(v["relative_midpoint_hours"] - midpoint_hour) for v in variants)
    for v in variants:
        v["mid_bjd_tdb"] = reference + v["relative_midpoint_hours"] / 24.0
    return {
        "source": {key: source[key] for key in ("file_id", "file_name", "url", "sha256", "bytes")},
        "basis": "BJD_TDB",
        "visit_jd_utc_endpoints": [float(utc[0]), float(utc[-1])],
        "visit_utc_endpoints": [utc_date(utc[0]), utc_date(utc[-1])],
        "visit_bjd_tdb_endpoints": [float(bjd[0]), float(bjd[-1])],
        "bjd_tdb_minus_jd_utc_s_range": [float(clock_correction.min()), float(clock_correction.max())],
        "row_count": len(bjd),
        "excluded_row_count": excluded,
        "median_exposure_s": float(np.median(exposure)),
        "median_relative_flux_error_ppt": float(np.median(scaled_errors) * 1000),
        "error_floor_applied_row_count": int(np.sum(errors > scaled_errors)),
        "primary_mid_bjd_tdb": primary["mid_bjd_tdb"],
        "maximum_alternate_midpoint_change_s": shape_change_s,
        "conditional_timing_uncertainty_s": max(
            primary["white_sigma_s"] * primary["ten_minute_binning_factor"], shape_change_s
        ),
        "variants": variants,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent
    source_manifest = directory / "EXOFOP-FILES.json"
    records = {
        r["file_id"]: r for r in json.loads(source_manifest.read_bytes()) if r["status"] == "downloaded"
    }
    output = {
        "schema": "toi216-ground-only-v1",
        "registration_sha256": sha((directory / "GROUND-ONLY-REGISTRATION.json").read_bytes()),
        "script_sha256": sha(Path(__file__).read_bytes()),
        "ground_source_manifest_sha256": sha(source_manifest.read_bytes()),
        "results": [fit_file(records[i], directory / "exofop") for i in SOURCE_IDS],
    }
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")
    print("Completed independent ground-only reduction of", len(output["results"]), "curves.")


if __name__ == "__main__":
    main()
