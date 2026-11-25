"""Identify and jointly profile TOI-216b/c transits from pinned TESS SPOC FITS.

The input manifest provides products and optional broad observing groups. No
per-event ephemeris, comparison timings, planet labels or event count are inputs.
Only the screening step uses a cadence grid. All reported parameters use the
original quality-zero barycentric exposure midpoints.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
import json
from math import ceil
from pathlib import Path
import platform

import numpy as np
from scipy import __version__ as scipy_version
from scipy.integrate import cumulative_trapezoid
from scipy.ndimage import median_filter
from scipy.optimize import brentq, least_squares
from scipy.signal import fftconvolve, find_peaks

import post_reveal_overlap as fits_columns
import transit_cascade as fits


BJD_ORIGIN = 2457000.0
TARGET_TIC = 55652896
PRIMARY, STRESS = "PDCSAP_FLUX", "SAP_FLUX"
MINIMUM_DEVIANCE = 36.0
STRESS_DEVIANCE = 16.0
ALIAS_MARGIN = 12.0
PATCH_HOURS = 9.0
PROFILE_RADIUS_HOUR = 1.2
CADENCE_FRACTION = 0.52
OVERLAP_STEP_HOUR = 0.25
MODEL_VARIANTS = ((PRIMARY, 0, 2), (STRESS, 1, 2), (PRIMARY, 1, 1))
# A wider envelope than the published c total duration of 5.514 h (+0.052/-0.047 h).
# Apply only when b and c compete to explain the same ingress or egress.
OUTER_OVERLAP_DURATION_HOUR = (5.20, 5.82)
MODE_SEPARATION_HOUR = 0.20
METHOD_SOURCE = "https://doi.org/10.3847/1538-3881/abd8d0"
PARAMETER_SOURCE = "https://exoplanetarchive.ipac.caltech.edu/overview/TOI-216"
LD_GEOMETRIES = ((0.38, 0.22), (0.49, 0.13))


@dataclass(frozen=True)
class Planet:
    period_days: float
    period_tolerance_days: float
    radius_ratio: float
    impact_parameters: tuple[float, float]
    durations: tuple[float, ...]
    duration_range: tuple[float, float]
    depth_range_ppt: tuple[float, float]


# Dawson et al. motivate the shape, order and period class. The screening and
# fit bounds are wider to accommodate changing impact parameter and TTVs.
PLANETS = {
    "b": Planet(17.16073, 1.80, 0.10, (0.98, 0.90), (1.4, 2.1, 2.8, 3.5),
                (1.00, 4.20), (1.8, 12.5)),
    "c": Planet(34.525528, 1.80, 0.123, (0.14, 0.24), (4.8, 5.5, 6.2),
                (4.15, 7.00), (10.0, 25.0)),
}


@dataclass(frozen=True)
class Curve:
    time: np.ndarray
    flux: np.ndarray
    error: np.ndarray
    cadence: float
    exposure: float

    def select(self, mask):
        return Curve(self.time[mask], self.flux[mask], self.error[mask], self.cadence, self.exposure)


@dataclass(frozen=True)
class Seed:
    planet: str
    center: float
    duration: float
    depth: float
    score: float


@dataclass(frozen=True)
class Fit:
    curve: Curve
    seeds: tuple[Seed, ...]
    geometry: int
    trend: np.ndarray
    parameters: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    residual: np.ndarray
    cost: float
    outer_duration_range: tuple[float, float] | None

    def event(self, index):
        return self.parameters[3 * index:3 * index + 3]


def hours(bjd):
    return (float(bjd) - BJD_ORIGIN) * 24.0


def bjd(hour):
    return BJD_ORIGIN + float(hour) / 24.0


def robust_scale(values):
    return fits.mad(values) if len(values) >= 4 else 0.0


def read_product(specification, base):
    path = base / specification["file"]
    raw = path.read_bytes()
    digest = sha256(raw).hexdigest()
    if digest != specification["sha256"]:
        raise ValueError(f"FITS SHA-256 mismatch in {path.name}")
    source = fits.fits_light_curve(raw, digest)
    sector = specification["sector"]
    if (int(specification.get("tic_id", TARGET_TIC)) != TARGET_TIC
            or source.receipt["tic_id"] != TARGET_TIC or source.receipt["sector"] != sector):
        raise ValueError(f"Unexpected TIC or sector in {path.name}")
    header, extension = fits.fits_header(raw, 0)
    light, _ = fits.fits_header(raw, extension)
    for name in ("SAP_FLUX", "SAP_FLUX_ERR"):
        index = next(i for i in range(1, int(light["TFIELDS"]) + 1) if light[f"TTYPE{i}"] == name)
        if (light[f"TFORM{index}"] not in ("E", "1E")
                or fits.number(light.get(f"TSCAL{index}", "1")) != 1
                or fits.number(light.get(f"TZERO{index}", "0")) != 0 or f"TNULL{index}" in light):
            raise ValueError(f"Unexpected {name} encoding in {path.name}")
    # The shutterless integrations span the cadence except for the frame readouts.
    exposure = source.cadence
    if "INT_TIME" in light and "FRAMETIM" in light:
        exposure *= fits.number(light["INT_TIME"]) / fits.number(light["FRAMETIM"])
    if not 0 < exposure <= source.cadence:
        raise ValueError(f"Invalid effective exposure in {path.name}")
    rows = fits_columns.quality_rows(raw, vars(fits))
    time = (rows["TIME"] + (source.reference - BJD_ORIGIN)) * 24.0
    curves = {}
    for column in (PRIMARY, STRESS):
        values = rows[column].astype(float)
        errors = rows[column + "_ERR"].astype(float)
        valid = np.isfinite(values) & np.isfinite(errors) & (errors > 0)
        norm = float(np.median(values[valid])) if np.count_nonzero(valid) >= 30 else 0.0
        if norm <= 0:
            raise ValueError(f"Insufficient valid {column} in {path.name}")
        flux, error = (values[valid] / norm - 1) * 1000, errors[valid] / norm * 1000
        selected = time[valid]
        if np.any(np.diff(selected) <= 0):
            raise ValueError(f"Nonunique exposure midpoints in {path.name}")
        adjacent = np.diff(selected) < 1.5 * source.cadence
        white = robust_scale(np.diff(flux)[adjacent]) / np.sqrt(2)
        extra = np.sqrt(max(0, white ** 2 - np.median(error) ** 2))
        curves[column] = Curve(selected, flux, np.hypot(error, extra), source.cadence, exposure)
    receipt = {**source.receipt, "source_uri": specification.get("uri"), "file_name": path.name,
               "effective_exposure_s": exposure * 3600, "sap_cadences": len(curves[STRESS].time),
               "camera": int(header["CAMERA"]), "ccd": int(header["CCD"])}
    return curves, receipt


@lru_cache(maxsize=4)
def shape_integral(planet, geometry):
    """Integrate a quadratic limb-darkened stellar disk over occulted rings."""
    p = PLANETS[planet]
    impact = p.impact_parameters[geometry]
    radius = p.radius_ratio
    u1, u2 = LD_GEOMETRIES[geometry]
    phase = np.linspace(-1, 1, 4001)
    separation = np.sqrt(impact ** 2 + phase ** 2 * ((1 + radius) ** 2 - impact ** 2))[:, None]
    roots, weights = np.polynomial.legendre.leggauss(64)

    def light(ring):
        mu = np.sqrt(np.maximum(0, 1 - ring ** 2))
        return 1 - u1 * (1 - mu) - u2 * (1 - mu) ** 2

    inner = np.abs(separation - radius)
    outer = np.minimum(separation + radius, 1.0)
    width = np.maximum(0, outer - inner)
    ring = inner + width * (roots + 1) / 2
    subtended = np.clip((ring ** 2 + separation ** 2 - radius ** 2) / (2 * ring * separation), -1, 1)
    partly_blocked = np.sum(width * weights * ring * light(ring) * np.arccos(subtended) / np.pi, axis=1)
    full_radius = np.maximum(0, radius - separation)
    inner_ring = full_radius * (roots + 1) / 2
    fully_blocked = np.sum(full_radius * weights * inner_ring * light(inner_ring), axis=1)
    loss = partly_blocked + fully_blocked
    return phase, cumulative_trapezoid(loss / loss.max(), phase, initial=0)


def shape(time, center, duration, exposure, planet, geometry=0):
    phase, integral = shape_integral(planet, geometry)
    half = duration / 2
    before = (time - center - exposure / 2) / half
    after = (time - center + exposure / 2) / half
    return half / exposure * (np.interp(after, phase, integral) - np.interp(before, phase, integral))


def screening_grid(curve, remove):
    t = curve.time
    y = curve.flux.copy()
    for event in remove:
        y += event.depth * shape(t, event.center, event.duration, curve.exposure, event.planet)
    index = np.rint((t - t[0]) / curve.cadence).astype(int)
    size = index[-1] + 1
    grid_flux = np.zeros(size)
    grid_weight = np.zeros(size)
    # Fit baselines on separated observed runs. Search only on this regular grid.
    for run in np.split(np.arange(len(t)), np.flatnonzero(np.diff(t) > 1) + 1):
        if len(run) < 30:
            continue
        span = min(2 * int(12 / curve.cadence) + 1, len(run) // 2 * 2 + 1)
        residual = y[run] - median_filter(y[run], size=span, mode="nearest")
        weight = np.ones(len(run)) / np.maximum(curve.error[run], 1e-6) ** 2
        np.add.at(grid_flux, index[run], -residual * weight)
        np.add.at(grid_weight, index[run], weight)
    return grid_flux, grid_weight


def discover(curve, planet, eligibility, remove=()):
    if len(curve.time) < 30:
        return []
    data, weight = screening_grid(curve, remove)
    if not np.any(weight > 0):
        return []
    grid_time = curve.time[0] + np.arange(len(data)) * curve.cadence
    allowed = (grid_time >= eligibility[0]) & (grid_time <= eligibility[1])
    minimum_depth, maximum_depth = PLANETS[planet].depth_range_ppt
    seeds = []
    for duration in PLANETS[planet].durations:
        width = ceil(duration / (2 * curve.cadence))
        relative = np.arange(-width, width + 1) * curve.cadence
        template = shape(relative, 0, duration, curve.exposure, planet)
        numerator = fftconvolve(data, template[::-1], mode="same")
        norm_sq = fftconvolve(weight, template[::-1] ** 2, mode="same")
        depth = numerator / np.maximum(norm_sq, 1e-8)
        score = numerator / np.sqrt(np.maximum(norm_sq, 1e-8))
        good = (allowed & (depth >= 0.66 * minimum_depth) & (depth <= 1.35 * maximum_depth)
                & (norm_sq > 0.45 * np.dot(template, template) * np.median(weight[weight > 0])))
        peaks, _ = find_peaks(np.where(good, score, 0), height=5.0, distance=ceil(0.6 / curve.cadence))
        seeds.extend(Seed(planet, float(grid_time[j]), duration, float(depth[j]), float(score[j])) for j in peaks)
    distinct = []
    for seed in sorted(seeds, key=lambda s: -s.score):
        if all(abs(seed.center - other.center) > 0.70 for other in distinct):
            distinct.append(seed)
    return distinct


def patch(curve, seeds):
    centers = [seed.center for seed in seeds]
    return curve.select((curve.time >= min(centers) - PATCH_HOURS) & (curve.time <= max(centers) + PATCH_HOURS))


def standardized(curve, seeds, geometry, trend, parameters):
    y = trend @ parameters[3 * len(seeds):]
    for i, seed in enumerate(seeds):
        center, duration, depth = parameters[3 * i:3 * i + 3]
        y -= depth * shape(curve.time, center, duration, curve.exposure, seed.planet, geometry)
    return (curve.flux - y) / curve.error


def fit_model(curve, seeds, geometry=0, degree=2, fixed=None, start=None, outer_duration_range=None):
    if len(curve.time) < 30:
        raise ValueError("Too few unflagged exposures for a local fit")
    seeds = tuple(seeds)
    base_time = (curve.time - np.mean(curve.time)) / PATCH_HOURS
    trend = np.vander(base_time, N=degree + 1, increasing=True)
    estimate, lower, upper = [], [], []
    for seed in seeds:
        p = PLANETS[seed.planet]
        duration_range = outer_duration_range if seed.planet == "c" and outer_duration_range else p.duration_range
        estimate.extend((seed.center, np.clip(seed.duration, *duration_range), seed.depth))
        lower.extend((seed.center - PROFILE_RADIUS_HOUR, duration_range[0], 0))
        upper.extend((seed.center + PROFILE_RADIUS_HOUR, duration_range[1], 60))
    estimate.extend([np.median(curve.flux)] + [0.0] * degree)
    lower = np.r_[lower, np.full(degree + 1, -np.inf)]
    upper = np.r_[upper, np.full(degree + 1, np.inf)]
    initial = np.clip(estimate if start is None else start, lower, upper)
    # Local offsets inside the optimizer avoid numerical steps based on absolute BJD.
    origin = np.zeros(len(initial))
    for i, seed in enumerate(seeds):
        origin[3 * i] = seed.center
    free = np.ones(len(initial), dtype=bool)
    for index, value in (fixed or {}).items():
        initial[index], free[index] = value, False

    def expand(offset):
        parameters = initial.copy()
        parameters[free] = origin[free] + offset
        return parameters

    def residual(offset):
        return standardized(curve, seeds, geometry, trend, expand(offset))

    fit = least_squares(residual, (initial - origin)[free], bounds=((lower - origin)[free], (upper - origin)[free]),
                        loss="soft_l1", f_scale=2.5, x_scale="jac", max_nfev=240)
    if not fit.success:
        raise ValueError("Local fit did not converge")
    return Fit(curve, seeds, geometry, trend, expand(fit.x), lower, upper, fit.fun, float(fit.cost), outer_duration_range)


def noise_scale(fit):
    outside = np.ones(len(fit.curve.time), dtype=bool)
    for index in range(len(fit.seeds)):
        center, duration, _ = fit.event(index)
        outside &= np.abs(fit.curve.time - center) > duration / 2 + 0.20
    t, y = fit.curve.time[outside], fit.residual[outside]
    white = max(1.0, robust_scale(y))
    beta = 1.0
    if len(t) >= 30:
        for span in (0.25, 0.5, 1.0):
            labels = np.floor((t - t[0]) / span).astype(int)
            counts = np.bincount(labels)
            enough = counts >= max(3, int(0.6 * span / fit.curve.cadence))
            if np.sum(enough) >= 6:
                means = np.bincount(labels, weights=y)[enough] / np.sqrt(counts[enough])
                beta = max(beta, robust_scale(means) / white)
    return white, beta


def coverage(curve, center, duration):
    t = curve.time - center

    def fraction(a, b):
        actual = np.count_nonzero((t >= a) & (t < b))
        return float(min(1, actual / max(1, (b - a) / curve.cadence)))

    half = duration / 2
    edge = max(0.15, 0.12 * duration)
    samples = np.r_[-half, t[np.abs(t) < half], half]
    parts = {"before": fraction(-half - 1.0, -half), "first_half": fraction(-half, 0),
             "second_half": fraction(0, half), "after": fraction(half, half + 1.0),
             "ingress": fraction(-half - edge, -half + edge),
             "egress": fraction(half - edge, half + edge),
             "largest_in_transit_gap_min": float(np.max(np.diff(samples)) * 60)}
    accepted = (min(parts["first_half"], parts["second_half"], parts["ingress"], parts["egress"]) >= CADENCE_FRACTION
                and min(parts["before"], parts["after"]) >= 0.45
                and parts["largest_in_transit_gap_min"] <= 60 * max(0.18, min(0.38, duration * 0.23)))
    return accepted, parts


def conditional(fit, fixed):
    return fit_model(fit.curve, fit.seeds, fit.geometry, fit.trend.shape[1] - 1,
                     fixed, fit.parameters, fit.outer_duration_range)


def component_deviance(fit, index, noise):
    # Give the single-component alternative the full duration bounds. The
    # overlap prior has to stabilize timing without inflating detection evidence.
    seeds = fit.seeds[:index] + fit.seeds[index + 1:]
    initial = np.delete(fit.parameters, np.s_[3 * index:3 * index + 3])
    null = fit_model(fit.curve, seeds, fit.geometry, fit.trend.shape[1] - 1, start=initial)
    return max(0.0, 2 * (null.cost - fit.cost) / (noise[0] * noise[1]) ** 2)


def profile_error(fit, index, noise, component, first_step):
    parameter = 3 * index + component
    best = fit.parameters[parameter]
    denom = (noise[0] * noise[1]) ** 2

    def difference(value):
        return 2 * (conditional(fit, {parameter: value}).cost - fit.cost) / denom - 1

    limits = []
    for bound in (fit.lower[parameter], fit.upper[parameter]):
        previous = best
        for offset in np.geomspace(first_step, max(first_step, abs(bound - best)), 15):
            candidate = float(np.clip(best + np.sign(bound - best) * offset,
                                      fit.lower[parameter], fit.upper[parameter]))
            if difference(candidate) >= 0:
                limits.append(abs(brentq(difference, *sorted((previous, candidate)), xtol=0.00005) - best))
                break
            previous = candidate
        else:
            limits.append(None)
    return limits


def consistent_spacing(left, right):
    if left.planet != right.planet:
        return True
    period = PLANETS[left.planet].period_days
    days = abs(right.center - left.center) / 24
    cycles = int(round(days / period))
    if cycles <= 0:
        return False
    tolerance = PLANETS[left.planet].period_tolerance_days + 0.36 * (cycles - 1)
    return abs(days - cycles * period) <= tolerance


def single_assessment(seed, curve):
    if not coverage(curve, seed.center, seed.duration)[0]:
        return None, "INSUFFICIENT_COVERAGE"
    try:
        fit = fit_model(patch(curve, (seed,)), (seed,))
        center, duration, depth = fit.event(0)
        strength = component_deviance(fit, 0, noise_scale(fit))
    except (ValueError, RuntimeError, np.linalg.LinAlgError):
        return None, "FIT_FAILED"
    if strength < MINIMUM_DEVIANCE or not coverage(curve, center, duration)[0]:
        return None, "INSUFFICIENT_SIGNAL_OR_COVERAGE"
    p = PLANETS[seed.planet]
    if not p.depth_range_ppt[0] <= depth <= p.depth_range_ppt[1]:
        return None, "INCONSISTENT_PHYSICAL_SHAPE"
    if (duration - p.duration_range[0]) <= 0.025 or (p.duration_range[1] - duration) <= 0.025:
        return None, "SHAPE_AT_DURATION_BOUND"
    return Seed(seed.planet, float(center), float(duration), float(depth), strength), None


def overlapping_components(seeds):
    if len(seeds) != 2 or seeds[0].planet == seeds[1].planet:
        return False
    return abs(seeds[0].center - seeds[1].center) <= (seeds[0].duration + seeds[1].duration) / 2 + 0.75


def fit_modes(curve, seeds, geometry=0, degree=2, outer_duration_range=None):
    fit = fit_model(curve, seeds, geometry, degree, outer_duration_range=outer_duration_range)
    if not overlapping_components(seeds):
        return [fit]
    b = next(i for i, seed in enumerate(seeds) if seed.planet == "b") * 3
    c = 3 - b
    modes = [fit]
    for length in (1.5, 2.35, 3.25):
        for shift in (-0.55, 0.0, 0.55):
            initial = fit.parameters.copy()
            initial[b] += shift
            initial[b + 1] = length
            initial[c + 1] = 5.51
            try:
                alternative = fit_model(curve, seeds, geometry, degree, start=initial,
                                        outer_duration_range=outer_duration_range)
            except (ValueError, RuntimeError, np.linalg.LinAlgError):
                continue
            modes.append(alternative)
    return sorted(modes, key=lambda item: item.cost)


def alternate_labels(fit, noise):
    """Swap assignments and reoptimize under the same data and nuisance trend."""
    seeds = []
    for seed in fit.seeds:
        label = "c" if seed.planet == "b" else "b"
        p = PLANETS[label]
        seeds.append(Seed(label, seed.center, p.durations[len(p.durations) // 2], seed.depth, seed.score))
    competing = fit_modes(fit.curve, seeds, outer_duration_range=fit.outer_duration_range)[0]
    for i, seed in enumerate(seeds):
        center, duration, depth = competing.event(i)
        low, high = PLANETS[seed.planet].depth_range_ppt
        if not low <= depth <= high or not coverage(fit.curve, center, duration)[0]:
            return None
    # When both transit centers have overlapping optimization ranges, the
    # swapped starts may converge again to the original physical solution.
    if len(seeds) == 2 and all(abs(competing.event(i)[0] - fit.event(1 - i)[0]) < MODE_SEPARATION_HOUR for i in range(2)):
        return None
    white, beta = noise
    return float(2 * (competing.cost - fit.cost) / (white * beta) ** 2)


def choose_sequence(seeds):
    if not seeds:
        return [], []
    # The duration of a TESS sector varies. Enumerate compatible hypotheses
    # without assuming a fixed number of possible epochs in a source product.
    hypotheses = [()]
    for seed in sorted(set(seeds), key=lambda row: (row.center, -row.score)):
        additions = [(*hypothesis, seed) for hypothesis in hypotheses
                     if all(consistent_spacing(seed, other) for other in hypothesis)]
        hypotheses.extend(additions)
    ranked = sorted(hypotheses, key=lambda h: -sum(seed.score for seed in h))
    best_score = sum(seed.score for seed in ranked[0])
    near_best = [hypothesis for hypothesis in ranked if best_score - sum(seed.score for seed in hypothesis) < ALIAS_MARGIN]
    certain = set.intersection(*(set(hypothesis) for hypothesis in near_best))
    possible = set.union(*(set(hypothesis) for hypothesis in near_best))
    abstained = [(seed, "AMBIGUOUS_ORBITAL_SEQUENCE" if seed in possible else "INCOMPATIBLE_ORBITAL_SEQUENCE")
                 for seed in dict.fromkeys(seeds) if seed not in certain]
    return sorted(certain, key=lambda e: e.center), abstained


def clusters(seeds):
    groups = []
    for seed in sorted(seeds, key=lambda s: s.center):
        if groups and seed.center - groups[-1][-1].center <= PATCH_HOURS + 4:
            groups[-1].append(seed)
        else:
            groups.append([seed])
    return groups


def assess_cluster(curves, seeds):
    outer_range = OUTER_OVERLAP_DURATION_HOUR if overlapping_components(seeds) else None
    modes = [fit_modes(patch(curves[column], seeds), seeds, geometry, degree, outer_range)
             for column, geometry, degree in MODEL_VARIANTS]
    fits_ = [variant[0] for variant in modes]
    noise = [noise_scale(fit) for fit in fits_]
    competing = alternate_labels(fits_[0], noise[0])
    outside_outer_range = False
    if outer_range:
        outer = next(i for i, seed in enumerate(seeds) if seed.planet == "c")
        duration = fits_[0].event(outer)[1]
        outside_outer_range = min(duration - outer_range[0], outer_range[1] - duration) <= 0.025
    outcomes = []
    for i, seed in enumerate(seeds):
        center, duration, depth = fits_[0].event(i)
        rows = []
        accepted_coverage = True
        for fit, scales, (column, geometry, degree) in zip(fits_, noise, MODEL_VARIANTS):
            time, length, amplitude = fit.event(i)
            valid, counts = coverage(fit.curve, time, length)
            accepted_coverage &= valid
            rows.append({"flux_column": column, "geometry": geometry, "trend_degree": degree,
                         "mid_bjd_tdb": bjd(time), "center_difference_min": float((time - center) * 60),
                         "duration_hour": float(length), "depth_ppt": float(amplitude),
                         "component_deviance": component_deviance(fit, i, scales), "coverage": counts,
                         "white_noise_scale": scales[0], "red_noise_scale": scales[1]})
        p = PLANETS[seed.planet]
        formal = profile_error(fits_[0], i, noise[0], 0, 0.004)
        profile_depth = profile_error(fits_[0], i, noise[0], 2, 0.025)
        model_motion = max(abs(row["center_difference_min"]) for row in rows)
        depth_motion = max(abs(row["depth_ppt"] - depth) for row in rows)
        alternative_mode = None
        for trial in modes[0][1:]:
            time, length, amplitude = trial.event(i)
            if abs(center - time) < MODE_SEPARATION_HOUR or not p.depth_range_ppt[0] <= amplitude <= p.depth_range_ppt[1]:
                continue
            if not coverage(trial.curve, time, length)[0]:
                continue
            scaled = float(2 * (trial.cost - fits_[0].cost) / (noise[0][0] * noise[0][1]) ** 2)
            alternative_mode = {"mid_bjd_tdb": bjd(time), "center_difference_min": float((time - center) * 60),
                                "deviance_penalty": scaled}
            break
        reasons = []
        if competing is not None and competing < ALIAS_MARGIN:
            reasons.append("AMBIGUOUS_PLANET_LABEL")
        if alternative_mode and alternative_mode["deviance_penalty"] < ALIAS_MARGIN:
            reasons.append("AMBIGUOUS_OVERLAP_TIMING_MODE")
        if outside_outer_range:
            reasons.append("OVERLAP_OUTER_SHAPE_AT_BOUND")
        if not accepted_coverage:
            reasons.append("INSUFFICIENT_INGRESS_EGRESS_OR_BASELINE")
        if rows[0]["component_deviance"] < MINIMUM_DEVIANCE or any(row["component_deviance"] < STRESS_DEVIANCE for row in rows[1:]):
            reasons.append("INSUFFICIENT_COMPONENT_EVIDENCE")
        if not p.depth_range_ppt[0] <= depth <= p.depth_range_ppt[1]:
            reasons.append("INCONSISTENT_PHYSICAL_SHAPE")
        if min(duration - p.duration_range[0], p.duration_range[1] - duration) <= 0.025:
            reasons.append("SHAPE_AT_DURATION_BOUND")
        if None in formal or max(value or 0 for value in formal) > 0.5:
            reasons.append("PROFILE_UNBOUNDED_OR_TOO_WIDE")
        if model_motion > max(12.0, 3.0 * 60 * max(value or 0 for value in formal)):
            reasons.append("UNSTABLE_ALTERNATIVE_MODEL")
        timing = None if None in formal else [float(max(60 * value, model_motion)) for value in formal]
        depth_errors = [None if value is None else float(max(value, depth_motion)) for value in profile_depth]
        outcomes.append({"verdict": "ABSTAIN" if reasons else "MEASURE", "planet": "TOI-216" + seed.planet,
                         "mid_bjd_tdb": bjd(center) if not reasons else None, "candidate_bjd_tdb": bjd(center),
                         "timing_error_min": timing, "profile_error_min": [None if x is None else x * 60 for x in formal],
                         "duration_hour": float(duration), "depth_ppt": float(depth), "depth_error_ppt": depth_errors,
                         "swapped_label_deviance_penalty": competing, "alternate_timing_mode": alternative_mode,
                         "overlap_outer_duration_range_hour": outer_range, "models": rows,
                         "reasons": reasons, "fitted_components": len(seeds)})
    return outcomes


def overlap_at(null_fits, outer, center, duration, alternate_duration):
    profiles, starts = [], []
    for null, (column, geometry, degree), length in zip(null_fits, MODEL_VARIANTS,
                                                       (duration, duration, alternate_duration)):
        inner = Seed("b", center, length, 1.0, 0.0)
        if not coverage(null.curve, center, length)[0]:
            return [], None
        fixed = {3: center, 4: length}
        initial = np.r_[null.parameters[:3], center, length, 1.0, null.parameters[3:]]
        both = fit_model(null.curve, (outer, inner), geometry, degree, fixed, initial)
        white, beta = noise_scale(both)
        variance = (white * beta) ** 2
        # Reoptimize the outer planet and the trend at every fixed inner depth.
        def difference(depth):
            cost = conditional(both, {**fixed, 5: depth}).cost
            return 2 * (cost - min(both.cost, null.cost)) / variance - 2.71

        best_depth = float(both.event(1)[2])
        upper_cap = max(22.0, best_depth + 8.0)
        upper = (brentq(difference, best_depth, upper_cap, xtol=0.005)
                 if difference(best_depth) < 0 < difference(upper_cap) else None)
        support = max(0.0, 2 * (null.cost - both.cost) / variance)
        profiles.append({"flux_column": column, "geometry": geometry, "trend_degree": degree,
                         "inner_template_duration_hour": length, "inner_depth_ppt": best_depth,
                         "upper_depth_ppt": upper, "component_deviance": support,
                         "outer_mid_bjd_tdb": bjd(both.event(0)[0]),
                         "white_noise_scale": white, "red_noise_scale": beta})
        starts.append(Seed("b", center, length, best_depth, support))
    minimum_depth, maximum_depth = PLANETS["b"].depth_range_ppt
    viable = (starts[0].score >= MINIMUM_DEVIANCE and all(seed.score >= STRESS_DEVIANCE for seed in starts[1:])
              and minimum_depth <= starts[0].depth <= maximum_depth)
    return profiles, starts[0] if viable else None


def overlap_scan(curves, outer, isolated, eligibility, specific_centers=None):
    duration = float(np.median([seed.duration for seed in isolated])) if isolated else 2.1
    alternate = float(np.clip(max(2.8, duration * 1.13), *PLANETS["b"].duration_range))
    half_width = (outer.duration + max(duration, alternate)) / 2
    half_steps = int(np.floor(half_width / OVERLAP_STEP_HOUR))
    offsets = OVERLAP_STEP_HOUR * np.arange(-half_steps, half_steps + 1)
    centers = (outer.center + offsets) if specific_centers is None else map(float, specific_centers)
    null = [fit_model(patch(curves[column], (outer,)), (outer,), geometry, degree)
            for column, geometry, degree in MODEL_VARIANTS]
    scan, viable = [], []
    for center in centers:
        if not eligibility[0] <= center <= eligibility[1]:
            continue
        try:
            profiles, additional = overlap_at(null, outer, center, duration, alternate)
        except (ValueError, RuntimeError, np.linalg.LinAlgError):
            scan.append({"tested_bjd_tdb": bjd(center), "offset_min": float((center - outer.center) * 60),
                         "verdict": "ABSTAIN_FIT", "models": []})
            continue
        scan.append({"tested_bjd_tdb": bjd(center), "offset_min": float((center - outer.center) * 60),
                     "verdict": "PROFILE" if profiles else "ABSTAIN_COVERAGE", "models": profiles})
        if additional is not None:
            viable.append(additional)
    distinct = []
    for seed in sorted(viable, key=lambda s: -s.score):
        if all(abs(seed.center - other.center) > 0.70 for other in distinct):
            distinct.append(seed)
    witness = {"outer_anchor_bjd_tdb": bjd(outer.center),
               "duration_source": "isolated b transits in the same sector" if isolated else "published b template family",
               "isolated_b_transits": len(isolated), "inner_duration_hour": duration,
               "alternate_inner_duration_hour": alternate, "pointwise_profiles": scan,
               "relative_center_grid_min": OVERLAP_STEP_HOUR * 60,
               "upper_depth_deviance_threshold": 2.71,
               "upper_depth_scope": "pointwise conditional profile under each fixed center, duration and geometry"}
    return witness, distinct


def seed_evidence(seed, reason):
    return {"verdict": "ABSTAIN", "planet": "TOI-216" + seed.planet, "mid_bjd_tdb": None,
            "candidate_bjd_tdb": bjd(seed.center), "duration_hour": seed.duration,
            "depth_ppt": seed.depth, "screening_score": seed.score, "reasons": [reason]}


def sector_results(curves, eligibility):
    primary = curves[PRIMARY]
    retained, rejected = [], []
    outer = []
    for seed in discover(primary, "c", eligibility):
        event, reason = single_assessment(seed, primary)
        if event is not None:
            outer.append(event)
        else:
            rejected.append(seed_evidence(seed, reason))
    outer, conflicts = choose_sequence(outer)
    rejected.extend(seed_evidence(*row) for row in conflicts)
    inner = []
    cleaned_flux = primary.flux.copy()
    for event in outer:
        cleaned_flux += event.depth * shape(primary.time, event.center, event.duration, primary.exposure, "c")
    cleaned = Curve(primary.time, cleaned_flux, primary.error, primary.cadence, primary.exposure)
    for seed in discover(primary, "b", eligibility, outer):
        event, reason = single_assessment(seed, cleaned)
        if event is not None:
            inner.append(event)
        else:
            rejected.append(seed_evidence(seed, reason))
    overlaps = []
    for peak in outer:
        isolated = [seed for seed in inner if abs(seed.center - peak.center) > PATCH_HOURS + 4]
        try:
            witness, simultaneous = overlap_scan(curves, peak, isolated, eligibility)
            overlaps.append(witness)
        except (ValueError, RuntimeError, np.linalg.LinAlgError):
            rejected.append(seed_evidence(peak, "OVERLAP_PROFILE_FAILED"))
            continue
        for seed in simultaneous:
            existing = [p for p in inner if abs(seed.center - p.center) <= 0.70]
            if not existing:
                inner.append(seed)
            elif max(p.score for p in existing) < seed.score:
                inner = [p for p in inner if p not in existing] + [seed]
    inner, conflicts = choose_sequence(inner)
    rejected.extend(seed_evidence(*row) for row in conflicts)
    for cluster in clusters((*outer, *inner)):
        try:
            retained.extend(assess_cluster(curves, cluster))
        except (ValueError, RuntimeError, np.linalg.LinAlgError):
            rejected.extend(seed_evidence(seed, "JOINT_FIT_FAILED") for seed in cluster)
    return retained, rejected, overlaps


def period_checks(events):
    rows = []
    for label, planet in PLANETS.items():
        ordered = [row for row in events if row["verdict"] == "MEASURE" and row["planet"] == "TOI-216" + label]
        for earlier, later in zip(ordered, ordered[1:]):
            start, stop = earlier["mid_bjd_tdb"], later["mid_bjd_tdb"]
            days = stop - start
            cycles = int(round(days / planet.period_days))
            expected = cycles * planet.period_days
            allowable = planet.period_tolerance_days + 0.36 * (cycles - 1)
            rows.append({"planet": "TOI-216" + label, "earlier_bjd_tdb": start, "later_bjd_tdb": stop,
                         "elapsed_days": days, "nearest_cycle_count": cycles,
                         "residual_days": days - expected,
                         "compatible_with_spacing_envelope": cycles >= 1 and abs(days - expected) <= allowable})
    return rows


def run(manifest):
    raw = manifest.read_bytes()
    inputs = json.loads(raw)
    data, receipts = {}, []
    for specification in inputs["products"]:
        curves, receipt = read_product(specification, manifest.parent)
        if receipt["sector"] in data:
            raise ValueError("Multiple products for the same sector")
        data[receipt["sector"]] = curves
        receipts.append(receipt)
    if not data:
        raise ValueError("The manifest must provide a TOI-216 source product")
    groups = inputs.get("groups", [{"id": f"sector-{sector}", "sectors": [sector]} for sector in data])
    outputs = []
    for group in groups:
        eligibility = (-np.inf, np.inf)
        if "start_bjd_tdb" in group or "stop_bjd_tdb" in group:
            eligibility = tuple(map(hours, fits.event_interval(group["start_bjd_tdb"], group["stop_bjd_tdb"])))
        events, abstentions, overlaps = [], [], []
        for sector in group["sectors"]:
            found, rejected, tested = sector_results(data[sector], eligibility)
            events.extend({**row, "sector": sector} for row in found)
            abstentions.extend({**row, "sector": sector} for row in rejected)
            overlaps.extend({**row, "sector": sector} for row in tested)
        events.sort(key=lambda row: row["candidate_bjd_tdb"])
        abstentions.sort(key=lambda row: row["candidate_bjd_tdb"])
        outputs.append({"id": group["id"], "events": events, "screened_abstentions": abstentions,
                        "overlap_models": overlaps,
                        "period_checks": period_checks(events),
                        "verdict": "MEASURE" if any(row["verdict"] == "MEASURE" for row in events) else "ABSTAIN"})
    dependencies = (Path(fits.__file__), Path(fits_columns.__file__))
    return {"format": "toi-216-joint-transit-v2", "purpose": inputs.get("purpose"),
            "manifest_sha256": sha256(raw).hexdigest(), "reducer_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "dependencies_sha256": {p.name: sha256(p.read_bytes()).hexdigest() for p in dependencies},
            "software": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy_version},
            "time_system": "BJD_TDB", "sources": receipts, "groups": outputs,
            "prior_sources": [METHOD_SOURCE, PARAMETER_SOURCE],
            "models": {"screening": "phase-blind cadence-grid physical matched filter",
                       "fit": "simultaneous finite-exposure limb-darkened chord losses with a shared local trend",
                       "noise": "empirical white floor and out-of-transit binned robust scale",
                       "errors": "conditional timing and amplitude profiles widened to model differences",
                       "assignment": "physical class with optimized label alternative and intra-sector recurrence",
                       "overlap_timing": "multistart fits with a broad published outer-duration envelope and an alternative-mode veto"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = json.dumps(run(arguments.inputs), indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output:
        arguments.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
