"""Time an isolated transit directly from a SHA-256-bound TESS SPOC light curve.

The input supplies time search bounds and an approximate first-to-fourth-contact
duration. The fitted times come from the PDCSAP flux and exposure timestamps.
TIME is the SPOC barycentric exposure midpoint. Kipping (2010, MNRAS 408:1758)
describes the effect of exposure integration on transit morphology. The timing
error combines a local profile estimate with checks for time-correlated baseline
noise and sensitivity to detrending and transit shape.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
import json
from math import ceil, isfinite, sqrt
from pathlib import Path
import re

import numpy as np
from scipy.optimize import brentq, least_squares
from scipy.signal import find_peaks


HOURS_PER_DAY = 24.0
SECONDS_PER_HOUR = 3600.0
METHOD = "tess-spoc-local-transit-profile-v1"
DETECTION_SNR = 7.0
DURATION_RANGE = (0.55, 1.65)
FITS_BLOCK = 2880
FITS_FIELD_BYTES = {"A": 1, "L": 1, "B": 1, "I": 2, "J": 4, "K": 8,
                    "E": 4, "D": 8, "C": 8, "M": 16, "P": 8, "Q": 16}
FLUX_FIELDS = {"TIME": ("D", ">f8"), "PDCSAP_FLUX": ("E", ">f4"),
               "PDCSAP_FLUX_ERR": ("E", ">f4"), "QUALITY": ("J", ">i4")}
QUAD_NODES, QUAD_WEIGHTS = np.polynomial.legendre.leggauss(7)


class Abstain(ValueError):
    def __init__(self, verdict: str, reason: str, **evidence):
        super().__init__(reason)
        self.verdict = f"ABSTAIN_{verdict}"
        self.evidence = evidence


@dataclass(frozen=True)
class Source:
    time: np.ndarray
    flux: np.ndarray
    error: np.ndarray
    reference: float
    cadence: float
    receipt: dict


@dataclass(frozen=True)
class Window:
    time: np.ndarray
    flux: np.ndarray
    error: np.ndarray
    cadence: float
    nominal: float
    search: tuple[float, float]

    def select(self, mask: np.ndarray) -> Window:
        return Window(self.time[mask], self.flux[mask], self.error[mask],
                      self.cadence, self.nominal, self.search)


@dataclass(frozen=True)
class Candidate:
    window: Window
    guess: float
    parameters: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    cost: float
    snr: float
    white_scale: float
    red_scale: float
    coverage: dict

    @property
    def center(self) -> float:
        return float(self.parameters[0])


def fits_header(data: bytes, start: int) -> tuple[dict[str, str], int]:
    cards = {}
    for position in range(start, len(data) - 79, 80):
        card = data[position:position + 80].decode("ascii")
        keyword = card[:8].strip()
        if keyword == "END":
            end = position + 80 - start
            return cards, start + ceil(end / FITS_BLOCK) * FITS_BLOCK
        if card[8:10] == "= ":
            value = card[10:].strip()
            cards[keyword] = value.split("'", 2)[1].strip() if value.startswith("'") else value.split("/", 1)[0].strip()
    raise ValueError("Missing FITS END card")


def number(value: str) -> float:
    result = float(value.replace("D", "E"))
    if not isfinite(result):
        raise ValueError("Non-finite FITS header value")
    return result


def fits_light_curve(raw: bytes, digest: str) -> Source:
    primary, table_start = fits_header(raw, 0)
    light, data_start = fits_header(raw, table_start)
    if primary.get("SIMPLE") != "T" or primary.get("NAXIS") != "0" or primary.get("TELESCOP") != "TESS":
        raise ValueError("Expected a TESS FITS file with an empty primary HDU")
    if light.get("XTENSION") != "BINTABLE" or light.get("EXTNAME") != "LIGHTCURVE":
        raise ValueError("Expected the SPOC LIGHTCURVE binary table")
    if (light.get("TIMESYS") != "TDB" or light.get("TIMEUNIT") != "d"
            or light.get("TIMEREF") != "SOLARSYSTEM" or number(light["TIMEPIXR"]) != 0.5
            or light.get("TREFPOS", "BARYCENTER") != "BARYCENTER"):
        raise ValueError("Expected barycentric TDB timestamps at exposure midpoints")
    if number(light.get("TIMEZERO", "0")) != 0 or number(light.get("TIMEOFFS", "0")) != 0:
        raise ValueError("Nonzero additional FITS time offset")
    reference = number(light["BJDREFI"]) + number(light["BJDREFF"])
    cadence = number(light["TIMEDEL"]) * HOURS_PER_DAY
    if not (2_400_000 < reference < 2_600_000 and 0 < cadence < 1):
        raise ValueError("Unexpected barycentric reference or TESS cadence")

    width, count = int(light["NAXIS1"]), int(light["NAXIS2"])
    fields = {}
    offset = 0
    for index in range(1, int(light["TFIELDS"]) + 1):
        name, form = light[f"TTYPE{index}"], light[f"TFORM{index}"]
        match = re.fullmatch(r"(\d*)([A-Z])", form)
        if match is None or name in fields:
            raise ValueError(f"Unsupported FITS column layout for {name}")
        repeats, code = match.groups()
        if name in FLUX_FIELDS:
            if (code != FLUX_FIELDS[name][0] or int(repeats or 1) != 1
                    or number(light.get(f"TSCAL{index}", "1")) != 1
                    or number(light.get(f"TZERO{index}", "0")) != 0
                    or f"TNULL{index}" in light):
                raise ValueError(f"Unexpected SPOC encoding for {name}")
        fields[name] = offset
        offset += int(repeats or 1) * FITS_FIELD_BYTES[code]
    if width != offset or count <= 0 or data_start + width * count > len(raw):
        raise ValueError("Invalid FITS binary table byte range")
    names = list(FLUX_FIELDS)
    dtype = np.dtype({"names": names, "formats": [FLUX_FIELDS[name][1] for name in names],
                      "offsets": [fields[name] for name in names], "itemsize": width})
    rows = np.frombuffer(raw, dtype, count=count, offset=data_start)
    valid = ((rows["QUALITY"] == 0) & np.isfinite(rows["TIME"])
             & np.isfinite(rows["PDCSAP_FLUX"]) & np.isfinite(rows["PDCSAP_FLUX_ERR"])
             & (rows["PDCSAP_FLUX_ERR"] > 0))
    time = rows["TIME"][valid].astype(float)
    order = np.argsort(time)
    time = time[order]
    if np.any(np.diff(time) <= 0):
        raise ValueError("Duplicate quality-accepted times in FITS light curve")
    flux = rows["PDCSAP_FLUX"][valid][order].astype(float)
    error = rows["PDCSAP_FLUX_ERR"][valid][order].astype(float)
    receipt = {"source_sha256": digest, "source_bytes": len(raw), "tic_id": int(primary["TICID"]),
               "sector": int(primary["SECTOR"]), "spoc_pipeline": primary.get("PROCVER"),
               "time_basis": "BJD_TDB", "bjd_reference": reference, "quality_rule": "QUALITY == 0",
               "cadence_s": cadence * SECONDS_PER_HOUR, "finite_quality_zero_cadences": int(valid.sum()),
               "original_cadences": count, "flux_column": "PDCSAP_FLUX"}
    return Source(time, flux, error, reference, cadence, receipt)


@lru_cache(maxsize=8)
def load_source(path: Path, expected: str) -> Source:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise Abstain("SOURCE_UNAVAILABLE", str(exc)) from exc
    digest = sha256(raw).hexdigest()
    if digest != expected:
        raise Abstain("SOURCE_SHA256", "The FITS source did not match the expected SHA-256.",
                      source_sha256=digest, expected_source_sha256=expected)
    try:
        return fits_light_curve(raw, digest)
    except (ValueError, KeyError, IndexError, OverflowError) as exc:
        raise Abstain("FITS_UNSUPPORTED", str(exc), source_sha256=digest) from exc


def event_interval(start, stop) -> tuple[float, float]:
    a, b = float(start), float(stop)
    if not (isfinite(a) and isfinite(b) and a < b):
        raise ValueError("Expected a finite ordered BJD_TDB interval")
    return a, b


def event_exclusions(value) -> list[tuple[float, float]]:
    if not isinstance(value, list):
        raise ValueError("Exclusions must be a list of BJD_TDB intervals")
    return [event_interval(item["start_bjd_tdb"], item["stop_bjd_tdb"]) if isinstance(item, dict)
            else event_interval(*item) for item in value]


def mad(x: np.ndarray) -> float:
    return float(1.4826022185 * np.median(np.abs(x - np.median(x))))


def candidate_seeds(window: Window) -> tuple[float, np.ndarray]:
    """Screen all allowed centers using an interpolated two-sided box statistic."""
    t, f, e = window.time, window.flux, window.error
    nominal = window.nominal
    start = max(window.search[0], float(t[0]))
    stop = min(window.search[1], float(t[-1]))
    step = min(window.cadence, nominal / 30)
    if stop <= start:
        return 0.0, np.array([])
    centers = np.linspace(start, stop, ceil((stop - start) / step) + 1)
    weight = 1 / np.square(e)
    cumul_w, cumul_f, cumul_t = [np.r_[0.0, np.cumsum(values)] for values in (weight, f * weight, t * weight)]

    def segment(left, right):
        a, b = np.searchsorted(t, left), np.searchsorted(t, right, side="right")
        w = cumul_w[b] - cumul_w[a]
        positive = w > 0
        scales = np.divide(1, w, out=np.full_like(w, np.inf), where=positive)
        flux = np.divide(cumul_f[b] - cumul_f[a], w, out=np.zeros_like(w), where=positive)
        times = np.divide(cumul_t[b] - cumul_t[a], w, out=np.zeros_like(w), where=positive)
        return b - a, scales, flux, times

    nl, vl, fl, tl = segment(centers - 1.35 * nominal, centers - 0.65 * nominal)
    nr, vr, fr, tr = segment(centers + 0.65 * nominal, centers + 1.35 * nominal)
    valid = (nl >= 3) & (nr >= 3) & (tr > tl)
    right = np.divide(centers - tl, tr - tl, out=np.full_like(tl, 0.5), where=valid)
    baseline = (1 - right) * fl + right * fr
    variance = np.square(1 - right) * vl + np.square(right) * vr
    score = np.zeros_like(centers)
    for fraction in (0.36, 0.54, 0.76, 1.00, 1.20):
        half = 0.5 * fraction * nominal
        n, v, depth_flux, _ = segment(centers - half, centers + half)
        significance = np.divide(baseline - depth_flux, np.sqrt(variance + v),
                                 out=np.zeros_like(centers), where=valid & (n >= 4))
        score = np.maximum(score, significance)
    padded = np.r_[0.0, score, 0.0]
    peaks, _ = find_peaks(padded, height=3.5, distance=max(1, ceil(0.23 * nominal / step)))
    peaks -= 1
    ranked = peaks[np.argsort(-score[peaks], kind="stable")]
    return float(score.max()), centers[ranked]


def integrated_dip(time: np.ndarray, duration: float, ingress: float, curvature: float,
                   cadence: float, rounded: bool) -> np.ndarray:
    half = duration / 2
    ramp = duration * ingress
    flat = half - ramp
    if rounded:
        distance = np.abs(time[:, None] + 0.5 * cadence * QUAD_NODES)
        fraction = np.clip((distance - flat) / ramp, 0, 1)
        taper = 1 - fraction ** 2 * (3 - 2 * fraction)
        brightness = 1 - curvature * np.square(np.minimum(distance / half, 1))
        return (taper * brightness) @ (QUAD_WEIGHTS / 2)

    def integral(x: np.ndarray) -> np.ndarray:
        distance = np.abs(x)
        plateau = np.minimum(distance, flat)
        q = np.clip(distance - flat, 0, ramp)
        area = plateau + q - q ** 2 / (2 * ramp)
        moment = plateau ** 3 / 3 + flat ** 2 * q + flat * q ** 2 + q ** 3 / 3
        moment -= (flat ** 2 * q ** 2 / 2 + 2 * flat * q ** 3 / 3 + q ** 4 / 4) / ramp
        return np.sign(x) * (area - curvature * moment / half ** 2)

    return (integral(time + 0.5 * cadence) - integral(time - 0.5 * cadence)) / cadence


def standardized_residuals(parameters: np.ndarray, window: Window, guess: float, rounded=False) -> np.ndarray:
    center, duration, ingress, curvature, depth, offset, slope, *quadratic = parameters
    t = (window.time - guess) / window.nominal
    trend = offset + slope * t
    if quadratic:
        trend += quadratic[0] * np.square(t)
    eclipse = integrated_dip(window.time - center, duration, ingress, curvature, window.cadence, rounded)
    return (window.flux - trend + depth * eclipse) / window.error


def fit_coverage(window: Window, center: float, duration: float, ingress: float) -> dict:
    t, cadence = window.time - center, window.cadence
    half, ramp = duration / 2, duration * ingress
    margin = max(0.35 * duration, 6 * cadence)
    ingress_mask = (t >= -half - 0.5 * cadence) & (t <= -half + ramp + 0.5 * cadence)
    egress_mask = (t >= half - ramp - 0.5 * cadence) & (t <= half + 0.5 * cadence)
    pre = (t < -half - cadence) & (t >= -half - margin)
    post = (t > half + cadence) & (t <= half + margin)
    pre_total = t < -half - cadence
    post_total = t > half + cadence
    transit = np.r_[-half, t[(t > -half) & (t < half)], half]
    break_size = float(np.diff(transit).max())
    counts = {"ingress": int(ingress_mask.sum()), "egress": int(egress_mask.sum()),
              "pre_baseline_near": int(pre.sum()), "post_baseline_near": int(post.sum()),
              "pre_baseline_total": int(pre_total.sum()), "post_baseline_total": int(post_total.sum()),
              "max_transit_gap_s": break_size * SECONDS_PER_HOUR}
    enough_baseline = (min(counts["pre_baseline_near"], counts["post_baseline_near"]) >= max(4, ceil(0.40 * margin / cadence))
                       and min(counts["pre_baseline_total"], counts["post_baseline_total"]) >= max(8, ceil(0.40 * duration / cadence)))
    sides = int(((t >= -half) & (t < 0)).sum()), int(((t <= half) & (t > 0)).sum())
    enough_transit = (min(counts["ingress"], counts["egress"]) >= max(2, ceil(0.45 * ramp / cadence))
                      and min(sides) >= max(4, ceil(0.30 * duration / cadence))
                      and break_size <= max(3.5 * cadence, 0.16 * duration))
    return {**counts, "sufficient_baseline": bool(enough_baseline), "sufficient_transit": bool(enough_transit)}


def noise_scales(window: Window, residual: np.ndarray, parameters: np.ndarray) -> tuple[float, float]:
    center, duration, ingress = parameters[:3]
    outside = np.abs(window.time - center) > duration / 2 + window.cadence
    values = residual[outside]
    white = max(1.0, mad(values)) if values.size >= 8 else 1.0
    t = window.time[outside]
    ingress_count = round(duration * ingress / window.cadence)
    beta = 1.0
    for length in {4, 8, min(30, max(4, ingress_count))}:
        phases = []
        for phase in (0.0, 0.5):
            bins = np.floor(t / (length * window.cadence) + phase).astype(int)
            _, idx = np.unique(bins, return_inverse=True)
            count = np.bincount(idx)
            full = count >= 0.75 * length
            if full.sum() >= 5:
                means = np.bincount(idx, weights=values)[full] / count[full]
                phases.append(float(np.std(means, ddof=1) * sqrt(float(np.median(count[full]))) / white))
        if phases:
            beta = max(beta, float(np.median(phases)))
    return white, beta


def solve_transit(window: Window, guess: float, start: np.ndarray, lower: np.ndarray,
                  upper: np.ndarray, rounded=False):
    return least_squares(standardized_residuals, np.clip(start, lower, upper), bounds=(lower, upper),
                         args=(window, guess, rounded), x_scale="jac", loss="soft_l1", f_scale=2.5,
                         max_nfev=180)


def fit_candidate(window: Window, guess: float) -> Candidate | None:
    nominal = window.nominal
    local = window.select(np.abs(window.time - guess) <= 2.0 * nominal)
    if local.time.size < 24:
        return None
    off = np.abs(local.time - guess) > 0.65 * nominal
    if off.sum() < 10:
        return None
    intercept, slope = np.polynomial.polynomial.polyfit(
        (local.time[off] - guess) / nominal, local.flux[off], 1, w=1 / local.error[off])
    center_mask = np.abs(local.time - guess) < 0.19 * nominal
    if not center_mask.any():
        return None
    depth = float(np.median(intercept - local.flux[center_mask]))
    lower = np.array([max(window.search[0], guess - 0.54 * nominal), DURATION_RANGE[0] * nominal,
                      0.035, 0.0, 0.0, -np.inf, -np.inf])
    upper = np.array([min(window.search[1], guess + 0.54 * nominal), DURATION_RANGE[1] * nominal,
                      0.50, 0.9, 1000.0, np.inf, np.inf])
    if lower[0] >= upper[0]:
        return None
    starts = ((1.0, 0.16), (0.82, 0.40))
    fits = [solve_transit(local, guess, np.array([guess, nominal * dur, ingress, 0.17, max(0.05, depth),
                                                  intercept, slope]), lower, upper) for dur, ingress in starts]
    stable = [fit for fit in fits if fit.success]
    if not stable:
        return None
    fit = min(stable, key=lambda x: x.cost)
    t = (local.time - guess) / nominal
    flat = least_squares(lambda x: (local.flux - x[0] - x[1] * t) / local.error,
                         [fit.x[5], fit.x[6]], loss="soft_l1", f_scale=2.5)
    white, beta = noise_scales(local, fit.fun, fit.x)
    snr = sqrt(max(0, 2 * (flat.cost - fit.cost))) / (white * beta)
    coverage = fit_coverage(local, *fit.x[:3])
    return Candidate(local, guess, fit.x, lower, upper, float(fit.cost), snr, white, beta, coverage)


def has_coverage(candidate: Candidate) -> bool:
    return candidate.coverage["sufficient_baseline"] and candidate.coverage["sufficient_transit"]


def candidate_evidence(candidate: Candidate) -> dict:
    _, duration, ingress, _, depth = candidate.parameters[:5]
    return {"duration_hour": float(duration), "ingress_hour": float(duration * ingress),
            "transit_depth_ppt": float(depth), "detection_snr": candidate.snr,
            "white_noise_scale": candidate.white_scale, "time_correlated_noise_scale": candidate.red_scale,
            "fit_cadences": candidate.window.time.size, **candidate.coverage}


def timing_profile(candidate: Candidate) -> tuple[float, float]:
    """Find both local one-sigma crossings after profiling transit and baseline."""
    win, best = candidate.window, candidate.parameters
    target = (candidate.white_scale * candidate.red_scale) ** 2

    def crossing(center: float) -> float:
        fit = least_squares(lambda p: standardized_residuals(np.r_[center, p], win, candidate.guess),
                            best[1:], bounds=(candidate.lower[1:], candidate.upper[1:]),
                            x_scale="jac", loss="soft_l1", f_scale=2.5, max_nfev=140)
        if not fit.success:
            raise Abstain("UNRESOLVED_UNCERTAINTY", "The timing profile fit did not converge.")
        return float(2 * (fit.cost - candidate.cost) - target)

    def endpoint(direction: int, boundary: float) -> float:
        available = abs(boundary - candidate.center)
        step = min(available, 0.20 * win.cadence)
        while step > 1e-9:
            other = candidate.center + direction * step
            if crossing(other) >= 0:
                left, right = sorted((candidate.center, other))
                return brentq(crossing, left, right, xtol=1e-7)
            if step >= available:
                break
            step = min(available, 2 * step)
        raise Abstain("UNRESOLVED_UNCERTAINTY", "The timing profile did not close inside the search region.")

    left = endpoint(-1, float(candidate.lower[0]))
    right = endpoint(1, float(candidate.upper[0]))
    return candidate.center - left, right - candidate.center


def alternate_fits(candidate: Candidate) -> tuple[float, np.ndarray]:
    win, best = candidate.window, candidate.parameters
    # Independently vary the local baseline degree and the transit contact shape.
    restricted = win.select(np.abs(win.time - candidate.center) <= 1.4 * win.nominal)
    alternatives = [
        solve_transit(win, candidate.guess, np.r_[best, 0.0], np.r_[candidate.lower, -np.inf],
                      np.r_[candidate.upper, np.inf]),
        solve_transit(win, candidate.guess, best, candidate.lower, candidate.upper, rounded=True),
        solve_transit(restricted, candidate.guess, best, candidate.lower, candidate.upper),
    ]
    if any(not fit.success for fit in alternatives):
        raise Abstain("UNSTABLE_TIMING", "An alternate shape or detrending fit did not converge.")
    changes = max(abs(float(fit.x[0]) - candidate.center) for fit in alternatives)
    best_alternative = min(alternatives[:2], key=lambda fit: fit.cost)
    return changes, best_alternative.fun


def coherent_negative_residual(candidate: Candidate, alternative_residual: np.ndarray) -> dict | None:
    """Look for a secondary excursion that both supported transit fits leave behind."""
    t = candidate.window.time
    cadence = candidate.window.cadence
    center, duration, _, _, depth = candidate.parameters[:5]
    main_residual = standardized_residuals(candidate.parameters, candidate.window, candidate.guess)
    strong = None
    for fraction in (0.12, 0.20, 0.33, 0.50, 0.72):
        width = max(4.0 * cadence, fraction * duration)
        left = np.searchsorted(t, t - width / 2)
        right = np.searchsorted(t, t + width / 2, side="right")
        count = right - left
        # Range is tied to fitted contacts and nearby continuum used for timing.
        valid = (np.abs(t - center) <= 1.25 * duration) & (count >= max(4, ceil(0.70 * width / cadence)))
        scales = candidate.white_scale * candidate.red_scale
        significances = []
        for residual in (main_residual, alternative_residual):
            cumulative = np.r_[0.0, np.cumsum(np.clip(residual, -8 * scales, 8 * scales))]
            significances.append(-(cumulative[right] - cumulative[left]) / (np.sqrt(count) * scales))
        significance = np.minimum(*significances)
        index = int(np.argmax(np.where(valid, significance, -np.inf)))
        if not valid[index] or significance[index] < 6:
            continue
        segment = slice(left[index], right[index])
        actual = main_residual[segment] * candidate.window.error[segment]
        if np.median(actual) > -0.10 * depth or np.mean(actual < 0) < 0.75:
            continue
        if strong is None or significance[index] > strong["unexplained_dip_snr"]:
            strong = {"unexplained_dip_snr": float(significance[index]), "unexplained_dip_duration_hour": float(width),
                      "unexplained_dip_offset_hour": float(t[index] - center)}
    return strong


def measure(source: Source, start: float, stop: float, nominal: float, exclusions: list,
            evidence: dict, competing: tuple = ()) -> tuple[float, float]:
    anchor = start + (stop - start) / 2
    relative = (source.time - (anchor - source.reference)) * HOURS_PER_DAY
    search = ((start - anchor) * HOURS_PER_DAY, (stop - anchor) * HOURS_PER_DAY)
    near = (relative >= search[0] - 2.55 * nominal) & (relative <= search[1] + 2.55 * nominal)
    excluded = np.zeros(near.size, dtype=bool)
    local_exclusions = []
    for first, last in exclusions:
        a, b = (first - anchor) * HOURS_PER_DAY, (last - anchor) * HOURS_PER_DAY
        local_exclusions.append((a, b))
        excluded |= (relative >= a - source.cadence / 2) & (relative <= b + source.cadence / 2)
    usable = near & ~excluded
    evidence.update({"window_cadences": int(usable.sum()), "excluded_cadences": int((near & excluded).sum())})
    if usable.sum() < 24 or nominal < 5 * source.cadence:
        raise Abstain("INSUFFICIENT_CADENCES", "Too few quality-accepted cadences for two transit contacts and baseline.")
    flux_scale = float(np.median(source.flux[usable]))
    if not isfinite(flux_scale) or flux_scale <= 0:
        raise Abstain("INVALID_PHOTOMETRY", "The local PDCSAP flux has no positive normalization.")
    time = relative[usable]
    flux = (source.flux[usable] / flux_scale - 1) * 1000
    reported = source.error[usable] / flux_scale * 1000
    consecutive = np.diff(time) <= 1.5 * source.cadence
    white = mad(np.diff(flux)[consecutive]) / sqrt(2) if consecutive.sum() >= 8 else 0.0
    extra = sqrt(max(0.0, white ** 2 - float(np.median(reported)) ** 2))
    window = Window(time, flux, np.hypot(reported, extra), source.cadence, nominal, search)
    best_seed, seeds = candidate_seeds(window)
    evidence.update({"box_search_max_snr": best_seed, "box_search_candidate_count": int(seeds.size)})
    if seeds.size > 32:
        raise Abstain("AMBIGUOUS_SEARCH", "The search interval contains too many distinct candidate dips to identify one transit.")
    candidates = [fit_candidate(window, float(seed)) for seed in seeds]
    fitted = sorted((candidate for candidate in candidates if candidate is not None), key=lambda c: -c.snr)
    evidence.update({"converged_candidates": len(fitted), "detection_snr_threshold": DETECTION_SNR,
                     "highest_trial_detection_snr": fitted[0].snr if fitted else None})
    significant = [candidate for candidate in fitted if candidate.snr >= DETECTION_SNR]
    complete = [c for c in significant if has_coverage(c)]
    if not complete:
        if significant:
            evidence.update(candidate_evidence(significant[0]))
            raise Abstain("INCOMPLETE_TRANSIT", "A candidate dip lacks covered ingress, egress, or nearby baselines.")
        raise Abstain("NO_IDENTIFIABLE_TRANSIT", "No supported transit cleared the robust detection threshold.")

    candidate = complete[0]
    evidence.update(candidate_evidence(candidate))
    provisional_center = anchor + candidate.center / HOURS_PER_DAY
    possible_identities = [r["id"] for r in competing if r["start"] <= provisional_center <= r["stop"]
                           and DURATION_RANGE[0] * r["duration"] <= candidate.parameters[1] <= DURATION_RANGE[1] * r["duration"]]
    if possible_identities:
        raise Abstain("AMBIGUOUS_TARGET", "The same light curve and search constraints admit another target for this dip.",
                      competing_event_ids=possible_identities)
    for other in significant:
        separation = abs(other.center - candidate.center)
        distinct = separation > max(3 * window.cadence, 0.30 * min(candidate.parameters[1], other.parameters[1]))
        if distinct and (has_coverage(other) or other.snr >= 0.70 * candidate.snr):
            raise Abstain("AMBIGUOUS_CENTER", "A distinct supported dip lies inside the center search interval.",
                          alternate_detection_snr=other.snr, alternate_separation_hour=separation)

    center, duration, ingress = candidate.parameters[:3]
    duration_range = candidate.upper[1] - candidate.lower[1]
    if min(duration - candidate.lower[1], candidate.upper[1] - duration) <= 0.005 * duration_range:
        raise Abstain("UNSTABLE_DURATION", "The data drive the transit duration to the edge of the supported shape range.")
    first, last = center - duration / 2, center + duration / 2
    if any(a <= last + window.cadence / 2 and b >= first - window.cadence / 2 for a, b in local_exclusions):
        raise Abstain("POSSIBLE_OVERLAP", "A declared exclusion intersects the fitted transit contacts.")
    profile_left, profile_right = timing_profile(candidate)
    formal = max(profile_left, profile_right)
    if min(center - search[0], search[1] - center) <= max(0.75 * window.cadence, 2 * formal):
        raise Abstain("SEARCH_EDGE", "The fitted center is insufficiently separated from a search boundary.")
    if any(abs(center - edge) <= 2 * formal for edge in (candidate.lower[0], candidate.upper[0])):
        raise Abstain("AMBIGUOUS_CENTER", "A search branch boundary limits the fitted timing profile.")
    sensitivity, alternate_residual = alternate_fits(candidate)
    overlap = coherent_negative_residual(candidate, alternate_residual)
    if overlap is not None:
        raise Abstain("POSSIBLE_OVERLAP", "Both fitted shapes leave a coherent nearby flux dip.", **overlap)
    evidence.update({"profile_left_s": profile_left * SECONDS_PER_HOUR, "profile_right_s": profile_right * SECONDS_PER_HOUR,
                     "detrending_and_shape_shift_s": sensitivity * SECONDS_PER_HOUR})
    if sensitivity > max(3 * formal, 0.30 * duration * ingress, 1.5 * window.cadence):
        raise Abstain("UNSTABLE_TIMING", "The fitted center changes substantially under plausible detrending or transit shapes.")
    uncertainty = np.hypot(formal, sensitivity)
    if not isfinite(uncertainty) or uncertainty <= 0 or uncertainty >= 0.20 * duration:
        raise Abstain("UNRESOLVED_UNCERTAINTY", "The timing uncertainty is too large relative to the fitted transit.")
    return float(anchor + center / HOURS_PER_DAY), float(uncertainty * SECONDS_PER_HOUR)


def run_event(event: dict, base: Path, competing: tuple = ()) -> dict:
    receipt = {"id": event.get("id"), "target": event.get("target"), "mid_bjd_tdb": None,
               "uncertainty_s": None, "source_sha256": None}
    try:
        expected = event["sha256"].lower()
        if re.fullmatch(r"[0-9a-f]{64}", expected) is None:
            raise ValueError("A hexadecimal SHA-256 is required")
        start, stop = event_interval(event["search_start_bjd_tdb"], event["search_stop_bjd_tdb"])
        nominal = float(event["nominal_duration_hour"])
        if not isfinite(nominal) or nominal <= 0:
            raise ValueError("A positive finite nominal duration is required")
        exclusions = event_exclusions(event.get("exclusions", []))
        path = (base / event["fits"]).resolve()
        source = load_source(path, expected)
        receipt.update(source.receipt)
        differences = {key: event[key] for key, actual in (("tic", "tic_id"), ("sector", "sector"), ("bytes", "source_bytes"))
                       if key in event and int(event[key]) != source.receipt[actual]}
        if differences:
            raise Abstain("SOURCE_METADATA", "The source FITS disagrees with the declared TIC, sector, or byte count.",
                          conflicting_source_metadata=differences)
        result, error = measure(source, start, stop, nominal, exclusions, receipt, competing)
        receipt.update(verdict="MEASURED", mid_bjd_tdb=result, uncertainty_s=error)
    except Abstain as exc:
        receipt.update(verdict=exc.verdict, reason=str(exc), **exc.evidence)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        receipt.update(verdict="ABSTAIN_INVALID_INPUT", reason=str(exc))
    return receipt


def run(manifest: Path) -> dict:
    payload = json.loads(manifest.read_bytes())
    if not isinstance(payload, dict):
        raise ValueError("The manifest must be a JSON object")
    events = payload.get("events", payload.get("cases"))
    if not isinstance(events, list) or any(not isinstance(event, dict) for event in events):
        raise ValueError("The manifest must contain an events list of objects")
    by_hash = {}
    for event in events:
        try:
            start, stop = event_interval(event["search_start_bjd_tdb"], event["search_stop_bjd_tdb"])
            duration = float(event["nominal_duration_hour"])
            group = by_hash.setdefault(event["sha256"].lower(), [])
            group.append({"id": event["id"], "target": event["target"], "start": start, "stop": stop,
                          "duration": duration})
        except (ValueError, TypeError, KeyError, AttributeError):
            continue  # run_event reports the malformed record in input order.
    results = []
    for event in events:
        digest = str(event.get("sha256", "")).lower()
        competing = tuple(r for r in by_hash.get(digest, ()) if r["target"] != event.get("target"))
        results.append(run_event(event, manifest.parent, competing))
    return {"method": METHOD, "time_basis": "BJD_TDB", "events": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.manifest), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
