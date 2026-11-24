#!/usr/bin/env python3
"""Conventional single-transit timing with CFITSIO, NumPy and SciPy."""

import argparse
import ctypes as c
from ctypes.util import find_library
import hashlib
import json
import math
from pathlib import Path
import platform
import time

import numpy as np
from scipy import __version__ as scipy_version
from scipy.linalg import qr
from scipy.optimize import brentq, minimize
from scipy.signal import find_peaks

SECONDS_PER_DAY = 86400.0
SIGNAL_TO_NOISE_MINIMUM = 7.0
ALIAS_MINIMUM_SEPARATION = 0.55
ALIAS_DELTA_CHI_SQUARED = 12.0
DURATION_BOUNDS = (0.65, 1.45)
INGRESS_FRACTION_BOUNDS = (0.035, 0.47)
METHOD = "Weighted single-event Box Least Squares and an exposure-integrated trapezoid profile"


class FitsTable:
    def __init__(self, path):
        library_name = find_library("cfitsio")
        if not library_name:
            raise RuntimeError("CFITSIO is unavailable")
        self.library = c.CDLL(library_name)
        self.handle = c.c_void_p()
        self.status = c.c_int()
        self.library.ffopen(c.byref(self.handle), str(path).encode(), 0, c.byref(self.status))
        self.check()
        try:
            self.library.ffmnhd(self.handle, 2, c.c_char_p(b"LIGHTCURVE"), 0, c.byref(self.status))
            self.check()
            count = c.c_longlong()
            self.library.ffgnrwll(self.handle, c.byref(count), c.byref(self.status))
            self.check()
            self.count = count.value
        except Exception:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        if self.handle.value:
            close_status = c.c_int()
            self.library.ffclos(self.handle, c.byref(close_status))
            self.handle = c.c_void_p()

    def check(self):
        if self.status.value:
            message = c.create_string_buffer(81)
            self.library.ffgerr(self.status, message)
            raise ValueError(f"CFITSIO {self.status.value}: {message.value.decode()}")

    def keyword(self, name, text=False):
        status = c.c_int()
        comment = c.create_string_buffer(81)
        if text:
            value = c.create_string_buffer(81)
            self.library.ffgkys(self.handle, name.encode(), value, comment, c.byref(status))
            return value.value.decode().strip() if status.value == 0 else None
        value = c.c_double()
        self.library.ffgkyd(self.handle, name.encode(), c.byref(value), comment, c.byref(status))
        return value.value if status.value == 0 else None

    def column(self, name):
        status = c.c_int()
        number = c.c_int()
        self.library.ffgcno(self.handle, 0, name.encode(), c.byref(number), c.byref(status))
        if status.value:
            return None
        values = np.empty(self.count, dtype=np.float64)
        any_null = c.c_int()
        self.library.ffgcvd(
            self.handle,
            number,
            c.c_longlong(1),
            c.c_longlong(1),
            c.c_longlong(self.count),
            c.c_double(math.nan),
            values.ctypes.data_as(c.POINTER(c.c_double)),
            c.byref(any_null),
            c.byref(self.status),
        )
        self.check()
        return values


def software_versions():
    library = c.CDLL(find_library("cfitsio"))
    library.ffvers.restype = c.c_float
    version = c.c_float()
    library.ffvers(c.byref(version))
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy_version,
        "cfitsio": f"{version.value:.3f}".rstrip("0").rstrip("."),
    }


def mad(values):
    return 1.482602218505602 * np.median(np.abs(values - np.median(values)))


def exclusions_for(event):
    for interval in event.get("exclusions", []):
        if isinstance(interval, dict):
            start = interval.get("start_bjd_tdb", interval.get("search_start_bjd_tdb"))
            stop = interval.get("stop_bjd_tdb", interval.get("search_stop_bjd_tdb"))
        else:
            start, stop = interval
        if start is None or stop is None or not float(start) < float(stop):
            raise ValueError("Invalid excluded BJD interval")
        yield float(start), float(stop)


def read_event(path, event):
    start = float(event["search_start_bjd_tdb"])
    stop = float(event["search_stop_bjd_tdb"])
    duration = float(event["nominal_duration_hour"]) / 24.0
    if not (2.0e6 < start < stop < 3.0e6 and 0 < duration < stop):
        raise ValueError("Invalid BJD search interval or duration")
    origin = (start + stop) / 2.0
    with FitsTable(path) as table:
        times = table.column("TIME")
        if times is None or not np.any(np.isfinite(times)):
            raise ValueError("No finite FITS TIME values")
        system = table.keyword("TIMESYS", text=True)
        unit = table.keyword("TIMEUNIT", text=True)
        if system and system.upper() != "TDB":
            raise ValueError(f"Unsupported FITS time scale {system}")
        if unit and unit.lower() not in {"d", "day", "days"}:
            raise ValueError(f"Unsupported FITS TIMEUNIT {unit}")
        reference = table.keyword("BJDREFI")
        if 2.0e6 < np.nanmedian(times) < 3.0e6:
            reference = 0.0
        elif reference is None:
            raise ValueError("Missing FITS BJDREFI for relative times")
        else:
            reference += table.keyword("BJDREFF") or 0.0
        timezero = table.keyword("TIMEZERO") or 0.0
        time_del = table.keyword("TIMEDEL")
        flux_column = "PDCSAP_FLUX"
        flux = table.column(flux_column)
        if flux is None or not np.any(np.isfinite(flux)):
            flux_column = "SAP_FLUX"
            flux = table.column(flux_column)
        if flux is None or not np.any(np.isfinite(flux)):
            raise ValueError("No finite FITS PDCSAP_FLUX or SAP_FLUX values")
        error = table.column(flux_column + "_ERR")
        quality = table.column("QUALITY")
        if quality is None:
            quality = table.column("SAP_QUALITY")

    times += reference - origin + timezero
    padding = max(2.25 * duration, 0.08)
    valid = (
        np.isfinite(times) & np.isfinite(flux) & (times >= start - origin - padding)
        & (times <= stop - origin + padding)
    )
    if quality is not None:
        valid &= quality == 0
    for left, right in exclusions_for(event):
        valid &= (times < left - origin) | (times > right - origin)

    selected = np.flatnonzero(valid)
    selected = selected[np.argsort(times[selected], kind="stable")]
    if selected.size < 12:
        return None
    times = times[selected] / duration
    flux = flux[selected]
    unique = np.r_[True, np.diff(times) > 0]
    times, flux = times[unique], flux[unique]
    if times.size < 12:
        return None
    cadence = float(np.median(np.diff(times)))
    if cadence <= 0 or not math.isfinite(cadence):
        raise ValueError("Unable to infer cadence")
    exposure = float(time_del / duration) if time_del and time_del > 0 else cadence
    if not 0 < exposure <= 1.2 * cadence:
        exposure = cadence
    normalization = float(np.median(flux))
    if normalization <= 0:
        raise ValueError("Median calibrated flux is nonpositive")
    flux = flux / normalization - 1.0
    local_pairs = np.diff(times) <= 1.5 * cadence
    differences = np.diff(flux)[local_pairs]
    scatter = mad(differences) / math.sqrt(2.0) if differences.size >= 8 else mad(flux)
    scatter = max(scatter, 1e-9)
    if error is None:
        uncertainty = np.full(times.size, scatter)
    else:
        uncertainty = error[selected][unique] / normalization
        good_error = np.isfinite(uncertainty) & (uncertainty > 0)
        fallback = float(np.median(uncertainty[good_error])) if np.any(good_error) else scatter
        uncertainty[~good_error] = fallback
        uncertainty = np.maximum(uncertainty, 0.3 * fallback)
    center_bounds = np.array([start - origin, stop - origin]) / duration
    return times, flux, uncertainty, cadence, exposure, center_bounds, origin, duration, flux_column


def coverage(times, center, width, cadence):
    left = center - width / 2.0
    right = center + width / 2.0
    cuts = np.searchsorted(times, [left - 0.95, left, center, right, right + 0.95])
    before, first_half, second_half, after = np.diff(cuts)
    transit_minimum = max(2, math.ceil(0.20 * width / cadence))
    baseline_minimum = max(2, math.ceil(0.30 / cadence))
    return min(first_half, second_half) >= transit_minimum and min(before, after) >= baseline_minimum


def trapezoid_shape(times, center, width, ingress_fraction, exposure):
    ingress = width * ingress_fraction

    def integral(position):
        rise = np.clip(position, 0.0, ingress)
        middle = np.clip(position - ingress, 0.0, width - 2.0 * ingress)
        fall = np.clip(position - (width - ingress), 0.0, ingress)
        return rise**2 / (2.0 * ingress) + middle + fall - fall**2 / (2.0 * ingress)

    position = times - center + width / 2.0
    return (integral(position + exposure / 2.0) - integral(position - exposure / 2.0)) / exposure


class TrendProfile:
    def __init__(self, times, flux, error, exposure, degree=2):
        self.times = times
        self.flux = flux
        self.error = error
        self.exposure = exposure
        self.degree = degree
        self.design = np.polynomial.legendre.legvander(2.0 * (times - times[0]) / np.ptp(times) - 1.0, degree)
        self.sqrt_weight = 1.0 / error
        self.q, _ = qr(self.design * self.sqrt_weight[:, None], mode="economic", check_finite=False)
        whitened = flux * self.sqrt_weight
        self.residual = whitened - self.q @ (self.q.T @ whitened)

    def box_scores(self, centers, widths, cadence):
        times = self.times
        prefix_norm = np.r_[0.0, np.cumsum(self.sqrt_weight**2)]
        prefix_dot = np.r_[0.0, np.cumsum(self.residual * self.sqrt_weight)]
        prefix_nuisance = np.vstack([
            np.zeros((1, self.degree + 1)),
            np.cumsum(self.q * self.sqrt_weight[:, None], axis=0),
        ])
        scores = np.full((widths.size, centers.size), -np.inf)
        baseline_minimum = max(2, math.ceil(0.30 / cadence))
        middle = np.searchsorted(times, centers)
        for index, width in enumerate(widths):
            left = np.searchsorted(times, centers - width / 2.0)
            right = np.searchsorted(times, centers + width / 2.0)
            outer_left = np.searchsorted(times, centers - width / 2.0 - 0.95)
            outer_right = np.searchsorted(times, centers + width / 2.0 + 0.95)
            transit_minimum = max(2, math.ceil(0.20 * width / cadence))
            sufficient = (
                (middle - left >= transit_minimum) & (right - middle >= transit_minimum)
                & (left - outer_left >= baseline_minimum) & (outer_right - right >= baseline_minimum)
            )
            numerator = np.maximum(prefix_dot[left] - prefix_dot[right], 0.0)
            nuisance = prefix_nuisance[right] - prefix_nuisance[left]
            denominator = prefix_norm[right] - prefix_norm[left] - np.sum(nuisance**2, axis=1)
            valid = sufficient & (denominator > 0.0)
            scores[index, valid] = numerator[valid] ** 2 / denominator[valid]
        return scores

    def fit_shape(self, center, width, ingress_fraction):
        half_support = (width + self.exposure) / 2.0
        left, right = np.searchsorted(self.times, [center - half_support, center + half_support])
        if right - left < 2:
            return 0.0, 0.0
        location = slice(left, right)
        shape = trapezoid_shape(self.times[location], center, width, ingress_fraction, self.exposure)
        whitened_shape = self.sqrt_weight[location] * shape
        nuisance = self.q[location].T @ whitened_shape
        numerator = max(0.0, -float(self.residual[location] @ whitened_shape))
        denominator = whitened_shape @ whitened_shape - nuisance @ nuisance
        if denominator <= 0:
            return 0.0, 0.0
        return float(numerator**2 / denominator), float(numerator / denominator)

    def residual_diagnostics(self, center, width, ingress_fraction, depth, cadence):
        shape = trapezoid_shape(self.times, center, width, ingress_fraction, self.exposure)
        adjusted = (self.flux + depth * shape) * self.sqrt_weight
        detrended = adjusted - self.q @ (self.q.T @ adjusted)
        out = np.abs(self.times - center) >= (width + self.exposure) / 2.0
        scale = max(1.0, mad(detrended[out]))
        bin_width = min(0.35, max(0.12, width * ingress_fraction, 4.0 * cadence))
        if np.count_nonzero(out) >= 24:
            for offset in (0.0, 0.5):
                bins = np.floor((self.times[out] - self.times[0]) / bin_width + offset).astype(int)
                _, inverse = np.unique(bins, return_inverse=True)
                errors = self.sqrt_weight[out]
                sums = np.bincount(inverse, weights=detrended[out] * errors)
                weights = np.bincount(inverse, weights=errors**2)
                count = np.bincount(inverse)
                enough = count >= 3
                if np.count_nonzero(enough) >= 7:
                    scale = max(scale, mad(sums[enough] / np.sqrt(weights[enough])))
        transit_residual = detrended - depth * shape * self.sqrt_weight
        evidence = []
        for side in (self.times < center, self.times >= center):
            template = (shape * self.sqrt_weight)[side]
            norm = float(np.linalg.norm(template))
            evidence.append(-float(transit_residual[side] @ template) / (scale * norm) if norm else 0.0)
        return float(scale), evidence


def optimize_candidate(profile, seed, bounds):
    def objective(values):
        return -profile.fit_shape(*values)[0]

    result = minimize(
        objective,
        seed,
        method="Powell",
        bounds=bounds,
        options={"xtol": 2e-5, "ftol": 1e-6, "maxiter": 40},
    )
    return result.x if result.fun <= objective(seed) else np.asarray(seed)


def best_candidates(profile, centers, score_table, durations, search_bounds, cadence):
    scores = np.max(score_table, axis=0)
    step = (centers[-1] - centers[0]) / (centers.size - 1)
    peaks = find_peaks(scores, distance=max(1, int(0.15 / step)))[0]
    endpoint_peaks = []
    if scores[0] >= scores[1]:
        endpoint_peaks.append(0)
    if scores[-1] >= scores[-2]:
        endpoint_peaks.append(centers.size - 1)
    strongest = np.unique(np.r_[peaks, endpoint_peaks, np.argmax(scores)].astype(int))
    strongest = strongest[np.argsort(scores[strongest])[::-1]]
    candidates = []
    for index in strongest[:20]:
        if not np.isfinite(scores[index]) or scores[index] <= 0:
            continue
        center = centers[index]
        fit_bounds = [
            (max(search_bounds[0], center - 0.28), min(search_bounds[1], center + 0.28)),
            DURATION_BOUNDS,
            INGRESS_FRACTION_BOUNDS,
        ]
        duration = durations[np.argmax(score_table[:, index])]
        for ingress in (0.12, 0.28):
            seed = (center, duration, ingress)
            optimum = optimize_candidate(profile, seed, fit_bounds)
            if coverage(profile.times, optimum[0], optimum[1], cadence):
                score, depth = profile.fit_shape(*optimum)
                candidates.append((score, depth, optimum))
    return sorted(candidates, key=lambda candidate: candidate[0], reverse=True), float(np.max(scores))


def timing_errors(profile, optimum, score, scale, cadence, search_bounds):
    center, duration, ingress = optimum
    threshold = score - scale**2

    def profile_difference(trial_center):
        def objective(shape):
            return -profile.fit_shape(trial_center, *shape)[0]

        seed = np.array([duration, ingress])
        result = minimize(
            objective,
            seed,
            method="Powell",
            bounds=[DURATION_BOUNDS, INGRESS_FRACTION_BOUNDS],
            options={"xtol": 4e-5, "ftol": 1e-6, "maxiter": 25},
        )
        return max(-result.fun, -objective(seed)) - threshold

    errors = []
    for direction, bound in zip((-1.0, 1.0), search_bounds):
        previous = center
        step = min(0.01, max(0.001, cadence / 4.0))
        for _ in range(90):
            trial = float(np.clip(center + direction * step, *search_bounds))
            if trial == previous:
                return None
            if profile_difference(trial) <= 0:
                root = brentq(profile_difference, min(previous, trial), max(previous, trial), xtol=1e-7)
                errors.append(abs(float(root) - center))
                break
            if trial == bound or abs(trial - center) > 0.55:
                return None
            previous = trial
            step += min(step * 0.25, 0.01)
        else:
            return None
    return errors


def evaluate_event(event):
    started = time.perf_counter()
    result = {"id": event["id"], "mid_bjd_tdb": None, "uncertainty_s": None, "source_sha256": None}

    def finish(verdict, **details):
        return {**result, "verdict": verdict, **details, "wall_time_s": time.perf_counter() - started}

    path = Path(event["fits"])
    with path.open("rb") as stream:
        result["source_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    if result["source_sha256"] != event["sha256"].lower():
        return finish("ABSTAIN_HASH_MISMATCH")
    data = read_event(path, event)
    if data is None:
        return finish("ABSTAIN_COVERAGE")
    times, flux, error, cadence, exposure, search_bounds, origin, nominal_duration, flux_column = data
    result.update(flux_column=flux_column, usable_cadences=int(times.size), cadence_s=cadence * nominal_duration * SECONDS_PER_DAY)
    profile = TrendProfile(times, flux, error, exposure)
    # Clip large upward spikes only. A real transit is a downward feature.
    positive_clip = profile.residual > max(9.0 * mad(profile.residual), 10.0)
    if np.any(positive_clip):
        times, flux, error = times[~positive_clip], flux[~positive_clip], error[~positive_clip]
        if times.size < 12:
            return finish("ABSTAIN_COVERAGE")
        profile = TrendProfile(times, flux, error, exposure)
    grid_step = min(cadence / 4.0, 1.0 / 80.0)
    grid_count = min(30001, max(3, math.ceil(np.ptp(search_bounds) / grid_step) + 1))
    centers = np.linspace(*search_bounds, grid_count)
    durations = np.linspace(*DURATION_BOUNDS, 9)
    scores = profile.box_scores(centers, durations, cadence)
    candidates, box_score = best_candidates(profile, centers, scores, durations, search_bounds, cadence)
    if not np.any(np.isfinite(scores)):
        return finish("ABSTAIN_COVERAGE")
    if not candidates:
        return finish("ABSTAIN_WEAK_SIGNAL")

    score, depth, optimum = candidates[0]
    center, width, ingress = optimum
    noise_scale, half_evidence = profile.residual_diagnostics(center, width, ingress, depth, cadence)
    signal_to_noise = math.sqrt(score) / noise_scale
    result.update(
        signal_to_noise=signal_to_noise,
        box_delta_chi_squared=box_score / noise_scale**2,
        noise_scale=noise_scale,
        minimum_half_signal_to_noise=min(half_evidence),
    )
    if signal_to_noise < SIGNAL_TO_NOISE_MINIMUM or min(half_evidence) < 2.5:
        return finish("ABSTAIN_WEAK_SIGNAL")

    for alternate_score, _, alternate in candidates[1:]:
        separation = abs(alternate[0] - center)
        if separation >= ALIAS_MINIMUM_SEPARATION:
            alias_delta_chi_squared = (score - alternate_score) / noise_scale**2
            result["alias_delta_chi_squared"] = alias_delta_chi_squared
            if alias_delta_chi_squared <= ALIAS_DELTA_CHI_SQUARED:
                return finish("ABSTAIN_ALIAS")
            break

    errors = timing_errors(profile, optimum, score, noise_scale, cadence, search_bounds)
    if errors is None:
        return finish("ABSTAIN_TIMING_UNCONSTRAINED")
    lower, upper = np.array(errors) * nominal_duration * SECONDS_PER_DAY
    linear_profile = TrendProfile(times, flux, error, exposure, degree=1)
    trend_bounds = [(max(search_bounds[0], center - 0.25), min(search_bounds[1], center + 0.25)), DURATION_BOUNDS, INGRESS_FRACTION_BOUNDS]
    linear_fit = optimize_candidate(linear_profile, optimum, trend_bounds)
    trend_shift_s = abs(linear_fit[0] - center) * nominal_duration * SECONDS_PER_DAY
    uncertainty = math.hypot(max(lower, upper), trend_shift_s)
    return finish(
        "MEASURED",
        mid_bjd_tdb=float(origin + center * nominal_duration),
        uncertainty_s=uncertainty,
        statistical_lower_s=float(lower),
        statistical_upper_s=float(upper),
        linear_detrending_shift_s=float(trend_shift_s),
        duration_hour=float(width * nominal_duration * 24.0),
        ingress_fraction=float(ingress),
        depth_fraction=depth,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    began = time.perf_counter()
    payload = json.loads(args.inputs.read_text())
    results = []
    for event in payload["events"]:
        try:
            results.append(evaluate_event(event))
        except (OSError, ValueError, TypeError, KeyError, OverflowError) as error:
            results.append({"id": event.get("id"), "verdict": "ABSTAIN_INPUT_ERROR", "mid_bjd_tdb": None, "uncertainty_s": None, "source_sha256": None, "message": str(error)})
    result = {
        "method": METHOD,
        "versions": software_versions(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "wall_time_s": time.perf_counter() - began,
        "events": results,
    }
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    temporary.replace(args.output)


if __name__ == "__main__":
    main()
