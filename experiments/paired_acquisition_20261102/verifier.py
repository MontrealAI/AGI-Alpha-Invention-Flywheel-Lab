"""Independent prospective verifier for a synthetic paired-acquisition interface.

No constructor code is imported.  The supplied callbacks receive observations
and declared model inputs only.  Truth is used here for scoring, never to select
the candidate's decisions.  Shared source access means procedural separation,
not external blinding.  See VERIFIER_CONTRACT.md before interpreting results.

Importing this module does not generate or execute the registered challenge.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Callable

import numpy as np


SCHEMA = "paired-acquisition-independent-verification/v1"
SEED = 202611020153
MU = np.array([[0.3681, 2.613], [0.1704, 0.4584], [0.1378, 0.2217]])
ENERGIES_KEV = (50.0, 100.0, 150.0)
EPS = 1e-4
DRIFT_BOUND = 2e-4
THRESHOLD = 0.10
CELL_SIDE_CM = 0.25
NUMERIC_ATOL = 2e-9
NUMERIC_RTOL = 2e-9
ROUND_OFF = 1e-11
OBS_KEYS = ("a0", "b0", "a1", "b1")
CONTROL_IDS = tuple(f"nonpositive_{key}" for key in OBS_KEYS) + (
    "nonfinite_observation", "extra_unmodeled_spectral_component",
    "fixed_unequal_gain_scope_expansion", "rank_deficient_geometry")
LIMITATION_IDS = ("coherent_out_of_bound_relative_gain_change",
                  "coherent_coefficient_mismatch", "nonblank_reference_in_material_span",
                  "spatial_decision_alias_outside_drift_contract")


def _parameter_bounds(eps: float, drift_bound: float) -> tuple[float, float]:
    eps, drift_bound = float(eps), float(drift_bound)
    if not math.isfinite(eps) or not 0 <= eps < 1:
        raise ValueError("corrected-read relative bound must be finite in [0,1)")
    if not math.isfinite(drift_bound) or drift_bound < 0:
        raise ValueError("log path-ratio change bound must be finite and nonnegative")
    return math.log1p(eps) - math.log1p(-eps), drift_bound


def _readings(*values) -> tuple[np.ndarray, ...]:
    arrays = tuple(np.asarray(value, dtype=float) for value in values)
    if len(arrays) != 4 or any(a.shape != arrays[0].shape for a in arrays):
        raise ValueError("four matching corrected observations required")
    if arrays[0].ndim < 1 or arrays[0].shape[-1] != 3:
        raise ValueError("observations must end in three energy channels")
    if any(not np.isfinite(a).all() for a in arrays):
        raise ValueError("nonfinite corrected observation")
    if any((a <= 0).any() for a in arrays):
        raise ValueError("strictly positive corrected observations required")
    return arrays


def _basis(mu=MU) -> tuple[np.ndarray, np.ndarray]:
    matrix = np.asarray(mu, dtype=float)
    if matrix.shape != (3, 2) or not np.isfinite(matrix).all():
        raise ValueError("finite three-channel, two-material basis required")
    if np.linalg.matrix_rank(matrix) != 2:
        raise ValueError("material basis is not identifiable")
    # Independent least-squares construction, not the candidate's retained inverse.
    left_inverse = np.linalg.lstsq(matrix, np.eye(3), rcond=None)[0]
    return matrix, left_inverse


def _spectral(attenuation, attenuation_bound, mu=MU) -> dict:
    matrix, left_inverse = _basis(mu)
    attenuation = np.asarray(attenuation, dtype=float)
    if attenuation.ndim < 1 or attenuation.shape[-1] != 3:
        raise ValueError("three attenuation channels required")
    bound = np.broadcast_to(np.asarray(attenuation_bound, dtype=float), attenuation.shape)
    if not np.isfinite(attenuation).all() or not np.isfinite(bound).all() or (bound < 0).any():
        raise ValueError("finite attenuation and nonnegative finite bounds required")
    mass = np.linalg.lstsq(matrix, attenuation.reshape(-1, 3).T, rcond=None)[0].T
    mass = mass.reshape(attenuation.shape[:-1] + (2,))
    mass_bound = bound @ np.abs(left_inverse).T
    residual = attenuation - mass @ matrix.T
    residual_bound = bound @ np.abs(np.eye(3) - matrix @ left_inverse).T
    accepted = ((np.abs(residual) <= residual_bound + ROUND_OFF).all(axis=-1)
                & (mass >= -mass_bound - ROUND_OFF).all(axis=-1))
    return {"accepted": accepted, "mass": mass, "mass_bound": mass_bound,
            "attenuation": attenuation, "attenuation_bound": bound,
            "residual": residual, "residual_bound": residual_bound}


def reference_pair(a0, b0, a1, b1, *, eps=EPS, drift_bound=DRIFT_BOUND, mu=MU) -> dict:
    """Independent double-ratio estimate and deterministic component bounds."""
    a0, b0, a1, b1 = _readings(a0, b0, a1, b1)
    log_noise, drift = _parameter_bounds(eps, drift_bound)
    attenuation = (np.log(b0) - np.log(a0) + np.log(a1) - np.log(b1)) / 2
    return _spectral(attenuation, drift / 2 + log_noise, mu)


def reference_blank(sample_a, reference_b, blank_a, blank_b, *,
                    eps=EPS, drift_bound=DRIFT_BOUND, mu=MU) -> dict:
    """Ordinary blank-corrected dual-beam control with its own acquired frame.

    The bound concerns relative path-gain change between the sample and blank
    frames.  The four coefficients have magnitude one, rather than one half.
    Equal epsilon does not imply equal specimen dose or photon precision.
    """
    sample_a, reference_b, blank_a, blank_b = _readings(
        sample_a, reference_b, blank_a, blank_b)
    log_noise, drift = _parameter_bounds(eps, drift_bound)
    attenuation = (np.log(reference_b) - np.log(sample_a)
                   + np.log(blank_a) - np.log(blank_b))
    return _spectral(attenuation, drift + 2 * log_noise, mu)


def ordinary_joint_fit(a0, b0, a1, b1, *, mu=MU) -> np.ndarray:
    """Fit all twelve log readings jointly with nine nuisance coordinates.

    For each energy the unknowns are two source/common-gain levels and one
    relative path gain.  The shared material coordinates are the other two
    columns.  This conventional fit receives exactly the candidate's readings.
    """
    readings = _readings(a0, b0, a1, b1)
    matrix, _ = _basis(mu)
    design = np.zeros((12, 11))
    for energy in range(3):
        row, col = 4 * energy, 2 + 3 * energy
        design[row, :2] = -matrix[energy]
        design[row + 3, :2] = -matrix[energy]
        design[row:row + 4, col:col + 3] = np.array(
            [[1, 0, .5], [1, 0, -.5], [0, 1, .5], [0, 1, -.5]])
    # (..., energy, read) ordering, independently assembled from the raw logs.
    observed = np.stack([np.log(a) for a in readings], axis=-1).reshape(-1, 12)
    fitted = np.linalg.lstsq(design, observed.T, rcond=None)[0][:2].T
    return fitted.reshape(readings[0].shape[:-1] + (2,))


def reference_geometry(size=4, cell_side_cm=CELL_SIDE_CM) -> np.ndarray:
    """Independent grid-crossing ray lengths; no per-cell slab code is reused.

    The inherited ideal geometry has nine angles and eleven offsets.  Segment
    midpoints assign intervals between sorted grid crossings to cells.  This is
    a mathematical ray model, not registration evidence for a physical swap.
    """
    if not isinstance(size, int) or size < 1 or not cell_side_cm > 0:
        raise ValueError("positive square grid required")
    extent = size * cell_side_cm / 2
    edges = np.linspace(-extent, extent, size + 1)
    rows = []
    for angle in np.linspace(0, math.pi, 9, endpoint=False):
        normal = np.array([math.cos(angle), math.sin(angle)])
        direction = np.array([-math.sin(angle), math.cos(angle)])
        for offset in np.linspace(-1.3 * extent, 1.3 * extent, 11):
            origin = normal * offset
            times = []
            for axis in range(2):
                if abs(direction[axis]) > 1e-12:
                    times.extend((edges - origin[axis]) / direction[axis])
            times = sorted(float(t) for t in times)
            lengths = np.zeros(size * size)
            for first, last in zip(times[:-1], times[1:]):
                if last <= first:
                    continue
                point = origin + direction * ((first + last) / 2)
                if np.all(point >= -extent) and np.all(point < extent):
                    cell = np.floor((point + extent) / cell_side_cm).astype(int)
                    if (cell >= 0).all() and (cell < size).all():
                        lengths[size * cell[1] + cell[0]] += last - first
            rows.append(lengths)
    return np.asarray(rows)


def _threshold_fields(density, bound, *, threshold=THRESHOLD,
                      cell_area=CELL_SIDE_CM ** 2) -> dict:
    threshold, cell_area = float(threshold), float(cell_area)
    if not math.isfinite(threshold) or threshold <= 0 or not math.isfinite(cell_area) or cell_area <= 0:
        raise ValueError("positive finite threshold and cell area required")
    lower = np.maximum(0., density[:, 1] - bound[:, 1])
    upper = density[:, 1] + bound[:, 1]
    above = lower > threshold
    below = upper <= threshold
    uncertain = ~(above | below)
    return {"above": above, "below": below, "uncertain": uncertain,
            "area_interval": np.array([np.count_nonzero(above),
                                        np.count_nonzero(~below)]) * cell_area}


def reference_spatial_threshold(attenuation, attenuation_bound, geometry, *,
                                threshold=THRESHOLD, cell_area=CELL_SIDE_CM ** 2,
                                mu=MU) -> dict:
    """Propagate spectral uncertainty into a new spatial threshold decision."""
    geometry = np.asarray(geometry, dtype=float)
    if geometry.ndim != 2 or not np.isfinite(geometry).all() or (geometry < 0).any():
        raise ValueError("finite nonnegative projection matrix required")
    if np.linalg.matrix_rank(geometry) != geometry.shape[1]:
        return {"accepted": False, "reason": "unidentifiable spatial geometry"}
    lines = _spectral(attenuation, attenuation_bound, mu)
    if lines["mass"].shape != (geometry.shape[0], 2):
        raise ValueError("one three-energy observation per ray required")
    if not bool(np.all(lines["accepted"])):
        return {"accepted": False, "reason": "spectral contract rejected"}
    inverse = np.linalg.lstsq(geometry, np.eye(geometry.shape[0]), rcond=None)[0]
    density = np.linalg.lstsq(geometry, lines["mass"], rcond=None)[0]
    bound = np.abs(inverse) @ lines["mass_bound"]
    residual = geometry @ density - lines["mass"]
    residual_bound = np.abs(np.eye(geometry.shape[0]) - geometry @ inverse) @ lines["mass_bound"]
    accepted = bool((density >= -bound - ROUND_OFF).all()
                    and (np.abs(residual) <= residual_bound + ROUND_OFF).all())
    return {"accepted": accepted, "density": density, "density_bound": bound,
            "geometry_rank": int(np.linalg.matrix_rank(geometry)),
            "geometry_condition": float(np.linalg.cond(geometry)),
            **_threshold_fields(density, bound, threshold=threshold, cell_area=cell_area)}


def _forward(attenuation, gain_a0, gain_b0, gain_a1, gain_b1, flux0, flux1,
             errors=None, *, reference_attenuation=0.) -> dict:
    """Verifier-only synthetic forward law, including a supplied swap semantic."""
    attenuation = np.asarray(attenuation, dtype=float)
    reference = np.asarray(reference_attenuation, dtype=float)
    values = (flux0 * gain_a0 * np.exp(-attenuation),
              flux0 * gain_b0 * np.exp(-reference),
              flux1 * gain_a1 * np.exp(-reference),
              flux1 * gain_b1 * np.exp(-attenuation))
    if errors is None:
        errors = np.zeros((4,) + attenuation.shape)
    return {key: np.asarray(value * (1 + error), dtype=float)
            for key, value, error in zip(OBS_KEYS, values, errors)}


def _acquire(rng, attenuation, *, eps, drift, error_corner=None) -> tuple[dict, dict, dict]:
    shape = np.asarray(attenuation).shape
    gain_a0, gain_b0 = np.exp(rng.uniform(-2, 2, (2,) + shape))
    common_change = rng.uniform(-1, 1, shape)
    ratio_change = np.broadcast_to(np.asarray(drift), shape)
    gain_a1 = gain_a0 * np.exp(common_change + ratio_change / 2)
    gain_b1 = gain_b0 * np.exp(common_change - ratio_change / 2)
    # Arbitrary signal levels are synthetic units, not photon or dose counts.
    flux0, flux1 = np.exp(rng.uniform(5, 12, (2,) + shape))
    errors = (rng.uniform(-eps, eps, (4,) + shape) if error_corner is None
              else np.broadcast_to(np.asarray(error_corner), (4,) + shape))
    pair = _forward(attenuation, gain_a0, gain_b0, gain_a1, gain_b1, flux0, flux1, errors)
    blank_error = rng.uniform(-eps, eps, (4,) + shape)
    # An alternative acquisition: its own sample/reference and blank/blank frames.
    blank_values = (flux0 * gain_a0 * np.exp(-attenuation), flux0 * gain_b0,
                    flux1 * gain_a1, flux1 * gain_b1)
    blank = {key: np.asarray(value * (1 + error))
             for key, value, error in zip(OBS_KEYS, blank_values, blank_error)}
    truth = {"attenuation": np.asarray(attenuation), "gain_a0": gain_a0,
             "gain_b0": gain_b0, "gain_a1": gain_a1, "gain_b1": gain_b1,
             "flux0": flux0, "flux1": flux1, "pair_relative_errors": errors,
             "blank_relative_errors": blank_error, "log_ratio_change": ratio_change}
    return pair, blank, truth


def build_challenge(seed=SEED) -> dict:
    """Generate the finite prospective family.  Do not call before source freeze."""
    if int(seed) != SEED:
        raise ValueError("this registered challenge does not permit seed selection")
    rng = np.random.Generator(np.random.PCG64(SEED))
    bulk = []
    corners = list(itertools.product((-1., 1.), repeat=4))
    for index in range(80):
        mass = np.array([rng.uniform(.25, 3.), rng.uniform(.005, .25)])
        if index < 32:
            family, eps, bound, drift, corner = "exact_fixed_gain", 0., 0., np.zeros(3), None
        elif index < 64:
            family, eps, bound = "bounded_error_and_drift", EPS, DRIFT_BOUND
            drift, corner = rng.uniform(-bound, bound, 3), None
        else:
            family, eps, bound = "declared_error_corners", EPS, DRIFT_BOUND
            sign = np.array([1., -1., 1.])
            drift = ((-1.) ** index) * bound * sign
            corner = np.asarray(corners[index - 64])[:, None] * sign[None, :] * eps
        pair, blank, nuisance = _acquire(rng, MU @ mass, eps=eps, drift=drift, error_corner=corner)
        bulk.append({"id": f"K1_{index:03d}", "family": family, "eps": eps,
                     "drift_bound": bound, "pair": pair, "blank": blank,
                     "truth_mass": mass, "nuisance": nuisance})
    geometry = reference_geometry()
    spatial = []
    for index in range(12):
        density = np.empty((16, 2))
        density[:, 0] = rng.uniform(1.8, 3., 16)
        high = np.zeros(16, dtype=bool)
        high[rng.permutation(16)[:1 + index % 15]] = True
        density[:, 1] = np.where(high, rng.uniform(.17, .21, 16), rng.uniform(.01, .03, 16))
        family = "separated_threshold"
        if index >= 8:
            family = "threshold_boundary"
            density[np.arange(index % 3, 16, 3), 1] = THRESHOLD
        attenuation = (geometry @ density) @ MU.T
        drift = rng.uniform(-DRIFT_BOUND, DRIFT_BOUND, attenuation.shape)
        pair, blank, nuisance = _acquire(rng, attenuation, eps=EPS, drift=drift)
        spatial.append({"id": f"K2_{index:03d}", "family": family, "eps": EPS,
                        "drift_bound": DRIFT_BOUND, "pair": pair, "blank": blank,
                        "truth_density": density, "nuisance": nuisance})
    return {"seed": SEED, "bulk": bulk, "spatial": spatial, "geometry": geometry}


def _digest_observations(observations) -> str:
    digest = hashlib.sha256()
    for key in OBS_KEYS:
        value = np.ascontiguousarray(observations[key], dtype="<f8")
        digest.update(key.encode("ascii"))
        digest.update(json.dumps(value.shape).encode("ascii"))
        digest.update(value.tobytes())
    return digest.hexdigest()


def _copy_args(observations) -> list[np.ndarray]:
    return [np.array(observations[key], dtype=float, copy=True) for key in OBS_KEYS]


def _close(first, second) -> bool:
    return bool(np.allclose(np.asarray(first), np.asarray(second),
                           rtol=NUMERIC_RTOL, atol=NUMERIC_ATOL))


def _acceptance(result) -> np.ndarray:
    accepted = np.asarray(result["accepted"])
    if accepted.size == 0 or accepted.dtype.kind != "b":
        raise TypeError("acceptance evidence must be a nonempty Boolean scalar or array")
    return accepted


def _all_accepted(result) -> bool:
    return bool(_acceptance(result).all())


def _pair_match(result, reference) -> bool:
    return bool(_all_accepted(result)
                and _acceptance(result).shape == _acceptance(reference).shape
                and _close(result["mass"], reference["mass"])
                and _close(result["mass_bound"], reference["mass_bound"])
                and _close(result["attenuation"], reference["attenuation"]))


def _spatial_match(result, reference) -> bool:
    if (not _all_accepted(result) or not reference["accepted"]
            or _acceptance(result).shape != ()):
        return False
    density = np.asarray(result["density"], dtype=float).reshape(-1, 2)
    bound = np.asarray(result["density_bound"], dtype=float).reshape(-1, 2)
    return bool(_close(density, reference["density"])
                and _close(bound, reference["density_bound"])
                and all(np.array_equal(np.asarray(result[key]).reshape(-1), reference[key])
                        for key in ("above", "below", "uncertain"))
                and _close(result["area_interval"], reference["area_interval"]))


def _refusal(callback, observations, **kwargs) -> tuple[bool, str]:
    try:
        result = callback(*_copy_args(observations), **kwargs)
    except ValueError as error:
        return True, f"ValueError: {error}"
    except Exception as error:
        return False, f"unexpected {type(error).__name__}: {error}"
    try:
        refused = not _all_accepted(result)
        return refused, "returned refusal" if refused else "accepted"
    except Exception as error:
        return False, f"invalid returned acceptance: {type(error).__name__}: {error}"


def _json_ready(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _negative_controls(pair_decoder, spatial_decoder, geometry, *, checks=None, limitations=None) -> dict:
    """Named limitations are expected failures of scope, not successes in nature."""
    checks = [] if checks is None else checks
    limitations = [] if limitations is None else limitations
    mass, delta = np.array([1., .08]), np.array([.20, .03])
    attenuation, shift = MU @ mass, MU @ delta
    ordinary_signal = _forward(attenuation, 1., 1., 1., 1., 12000., 8000.)
    for key in OBS_KEYS:
        broken = {name: value.copy() for name, value in ordinary_signal.items()}
        broken[key][0] = 0.
        passed, detail = _refusal(pair_decoder, broken, eps=EPS, drift_bound=DRIFT_BOUND)
        checks.append({"id": f"nonpositive_{key}", "passed": passed, "detail": detail})
    broken = {name: value.copy() for name, value in ordinary_signal.items()}
    broken["a0"][1] = np.nan
    passed, detail = _refusal(pair_decoder, broken, eps=EPS, drift_bound=DRIFT_BOUND)
    checks.append({"id": "nonfinite_observation", "passed": passed, "detail": detail})
    normal = np.cross(MU[:, 0], MU[:, 1])
    normal /= np.linalg.norm(normal)
    extra_basis = MU @ np.array([.1, .02]) + .01 * normal
    extra = _forward(attenuation + extra_basis, 1., 1., 1., 1., 12000., 8000.)
    passed, detail = _refusal(pair_decoder, extra, eps=EPS, drift_bound=DRIFT_BOUND)
    checks.append({"id": "extra_unmodeled_spectral_component", "passed": passed,
                   "detail": detail, "authored_extra_attenuation": extra_basis})

    # New construction versus the old single-ratio scope: fixed unequal gains.
    causal = _forward(attenuation, np.exp(-shift), 1., np.exp(-shift), 1., 12000., 8000.)
    causal_result = pair_decoder(*_copy_args(causal), eps=EPS, drift_bound=DRIFT_BOUND)
    old_result = _spectral(np.log(causal["b0"]) - np.log(causal["a0"]),
                           math.log1p(EPS) - math.log1p(-EPS))
    causal_pass = (_all_accepted(causal_result) and _close(causal_result["mass"], mass)
                   and _all_accepted(old_result) and _close(old_result["mass"], mass + delta)
                   and (np.abs(old_result["mass"] - mass) > old_result["mass_bound"] + NUMERIC_ATOL).any())
    checks.append({"id": "fixed_unequal_gain_scope_expansion", "passed": bool(causal_pass),
                   "paired_mass": causal_result["mass"], "old_single_ratio_mass": old_result["mass"],
                   "truth_mass": mass, "old_scope_was_common_gain": True})

    witnesses = [
        ("coherent_out_of_bound_relative_gain_change",
         _forward(attenuation, np.exp(-shift), 1., 1., np.exp(-shift), 12000., 8000.),
         mass + delta, {"actual_max_log_ratio_change": float(np.max(np.abs(2 * shift)))}),
        ("coherent_coefficient_mismatch",
         _forward((MU @ np.diag([1.08, 1.20])) @ mass, 1., 1., 1., 1., 12000., 8000.),
         np.array([1.08, 1.20]) * mass, {"coefficient_column_scales": [1.08, 1.20]}),
        ("nonblank_reference_in_material_span",
         _forward(attenuation, 1., 1., 1., 1., 12000., 8000.,
                  reference_attenuation=MU @ np.array([.10, .02])),
         mass - np.array([.10, .02]), {"true_reference_mass": [.10, .02]})]
    for name, observations, apparent_mass, extra_record in witnesses:
        result = pair_decoder(*_copy_args(observations), eps=EPS, drift_bound=DRIFT_BOUND)
        reference = reference_pair(*_copy_args(observations), eps=EPS, drift_bound=DRIFT_BOUND)
        exposed = (_pair_match(result, reference) and _close(result["mass"], apparent_mass)
                   and (np.abs(np.asarray(result["mass"]) - mass)
                        > np.asarray(result["mass_bound"]) + NUMERIC_ATOL).any())
        limitations.append({"id": name, "expected_undetected_wrong_answer_observed": bool(exposed),
                            "truth_mass": mass, "reported_mass": result["mass"],
                            "reported_bound": result["mass_bound"], **extra_record})

    density_a = np.column_stack([np.full(16, 2.5), np.full(16, .02)])
    density_a[5, 1] = .08
    density_b = density_a.copy()
    density_b[5, 1] = .14
    atten_a, atten_b = (geometry @ density_a) @ MU.T, (geometry @ density_b) @ MU.T
    coherent_shift = atten_b - atten_a
    common = _forward(atten_b, 1., 1., 1., 1., 12000., 8000.)
    world_a = _forward(atten_a, np.exp(-coherent_shift), 1., 1., np.exp(-coherent_shift), 12000., 8000.)
    same_observations = all(_close(common[key], world_a[key]) for key in OBS_KEYS)
    # Exactly one candidate call: no world identity enters a supposedly common policy.
    common_result = spatial_decoder(*_copy_args(common), geometry=geometry.copy(), eps=EPS,
                                    drift_bound=DRIFT_BOUND, threshold=THRESHOLD,
                                    cell_area=CELL_SIDE_CM ** 2)
    reported_above = np.asarray(common_result["above"], dtype=bool).reshape(-1)
    interval = np.asarray(common_result["area_interval"], dtype=float)
    truth_area_a = float(np.count_nonzero(density_a[:, 1] > THRESHOLD) * CELL_SIDE_CM ** 2)
    truth_area_b = float(np.count_nonzero(density_b[:, 1] > THRESHOLD) * CELL_SIDE_CM ** 2)
    alias_exposed = bool(same_observations and _all_accepted(common_result) and reported_above[5]
                         and not interval[0] - NUMERIC_ATOL <= truth_area_a <= interval[1] + NUMERIC_ATOL
                         and interval[0] - NUMERIC_ATOL <= truth_area_b <= interval[1] + NUMERIC_ATOL)
    limitations.append({"id": "spatial_decision_alias_outside_drift_contract",
                        "expected_undetected_wrong_answer_observed": alias_exposed,
                        "same_observations_within_numeric_tolerance": bool(same_observations),
                        "candidate_calls": 1, "true_area_world_a": truth_area_a,
                        "true_area_world_b": truth_area_b, "common_reported_area_interval": interval,
                        "actual_max_log_ratio_change_world_a": float(np.max(np.abs(2 * coherent_shift)))})
    deficient = geometry.copy()
    deficient[:, 0] = 0.
    passed, detail = _refusal(spatial_decoder, common, geometry=deficient, eps=EPS,
                              drift_bound=DRIFT_BOUND, threshold=THRESHOLD,
                              cell_area=CELL_SIDE_CM ** 2)
    checks.append({"id": "rank_deficient_geometry", "passed": passed, "detail": detail})
    return {"checks": checks, "limitations": limitations,
            "passed": bool(all(row["passed"] for row in checks)
                           and all(row["expected_undetected_wrong_answer_observed"] for row in limitations))}


def run_verification(pair_decoder: Callable, spatial_decoder: Callable, *,
                     fresh_pair_decoder: Callable | None = None,
                     fresh_spatial_decoder: Callable | None = None) -> dict:
    """Run once after freeze; return a receipt without writing or overwriting files.

    Required callback keys and the prospective acceptance rules are specified in
    VERIFIER_CONTRACT.md.  A failed callback remains a failed registered case.
    The parent runner owns source freezing, a fresh output directory and exit code.
    """
    challenge = build_challenge()
    bulk_rows, spatial_rows = [], []
    for case in challenge["bulk"]:
        row = {"id": case["id"], "family": case["family"],
               "pair_sha256": _digest_observations(case["pair"]),
               "blank_sha256": _digest_observations(case["blank"]), "passed": False}
        try:
            kwargs = {"eps": case["eps"], "drift_bound": case["drift_bound"]}
            reference = reference_pair(*_copy_args(case["pair"]), **kwargs)
            candidate = pair_decoder(*_copy_args(case["pair"]), **kwargs)
            ordinary = ordinary_joint_fit(*_copy_args(case["pair"]))
            blank = reference_blank(*_copy_args(case["blank"]), **kwargs)
            error = np.abs(np.asarray(candidate["mass"]) - case["truth_mass"])
            coverage = bool((error <= np.asarray(candidate["mass_bound"]) + NUMERIC_ATOL).all())
            blank_coverage = bool(_all_accepted(blank)
                                  and (np.abs(blank["mass"] - case["truth_mass"])
                                       <= blank["mass_bound"] + NUMERIC_ATOL).all())
            fresh_match = None
            if fresh_pair_decoder is not None:
                fresh_match = _pair_match(fresh_pair_decoder(*_copy_args(case["pair"]), **kwargs), reference)
            row.update({"truth_mass": case["truth_mass"], "reported_mass": candidate["mass"],
                        "reported_bound": candidate["mass_bound"],
                        "all_components_covered": coverage,
                        "ordinary_same_observation_max_difference": float(np.max(np.abs(ordinary - candidate["mass"]))),
                        "blank_all_components_covered": blank_coverage,
                        "blank_mass": blank["mass"], "blank_bound": blank["mass_bound"],
                        "fresh_equal_content_matches": fresh_match,
                        "passed": bool(_pair_match(candidate, reference) and coverage
                                       and _close(ordinary, candidate["mass"])
                                       and _all_accepted(blank) and blank_coverage
                                       and fresh_match is not False)})
        except Exception as error:
            row["error"] = f"{type(error).__name__}: {error}"
        bulk_rows.append(row)

    geometry = challenge["geometry"]
    for case in challenge["spatial"]:
        row = {"id": case["id"], "family": case["family"],
               "pair_sha256": _digest_observations(case["pair"]),
               "blank_sha256": _digest_observations(case["blank"]), "passed": False}
        try:
            pair_kwargs = {"eps": case["eps"], "drift_bound": case["drift_bound"]}
            spatial_kwargs = {**pair_kwargs, "geometry": geometry.copy(),
                              "threshold": THRESHOLD, "cell_area": CELL_SIDE_CM ** 2}
            lines = reference_pair(*_copy_args(case["pair"]), **pair_kwargs)
            reference = reference_spatial_threshold(lines["attenuation"], lines["attenuation_bound"], geometry)
            candidate = spatial_decoder(*_copy_args(case["pair"]), **spatial_kwargs)
            density = np.asarray(candidate["density"], dtype=float).reshape(16, 2)
            bound = np.asarray(candidate["density_bound"], dtype=float).reshape(16, 2)
            error = np.abs(density - case["truth_density"])
            coverage = bool((error <= bound + NUMERIC_ATOL).all())
            above = np.asarray(candidate["above"], dtype=bool).reshape(16)
            below = np.asarray(candidate["below"], dtype=bool).reshape(16)
            uncertain = np.asarray(candidate["uncertain"], dtype=bool).reshape(16)
            truth_above = case["truth_density"][:, 1] > THRESHOLD
            truth_area = float(np.count_nonzero(truth_above) * CELL_SIDE_CM ** 2)
            area = np.asarray(candidate["area_interval"], dtype=float)
            decisions_sound = bool((~above | truth_above).all() and (~below | ~truth_above).all()
                                   and area[0] - NUMERIC_ATOL <= truth_area <= area[1] + NUMERIC_ATOL)
            required_completion = bool((~uncertain).all() if case["family"] == "separated_threshold"
                                       else uncertain.any())
            ordinary_lines = ordinary_joint_fit(*_copy_args(case["pair"]))
            ordinary_density = np.linalg.lstsq(geometry, ordinary_lines, rcond=None)[0]
            blank_lines = reference_blank(*_copy_args(case["blank"]), **pair_kwargs)
            blank = reference_spatial_threshold(blank_lines["attenuation"], blank_lines["attenuation_bound"], geometry)
            blank_coverage = bool(blank["accepted"] and
                                  (np.abs(blank["density"] - case["truth_density"])
                                   <= blank["density_bound"] + NUMERIC_ATOL).all())
            fresh_match = None
            if fresh_spatial_decoder is not None:
                fresh_kwargs = {**spatial_kwargs, "geometry": geometry.copy()}
                fresh_match = _spatial_match(fresh_spatial_decoder(*_copy_args(case["pair"]), **fresh_kwargs), reference)
            row.update({"truth_density": case["truth_density"], "density": density, "density_bound": bound,
                        "all_components_covered": coverage, "decisions_sound": decisions_sound,
                        "required_completion_or_abstention": required_completion,
                        "above": above, "below": below, "uncertain": uncertain,
                        "true_contaminated_area_cm2": truth_area, "area_interval_cm2": area,
                        "ordinary_same_observation_max_difference": float(np.max(np.abs(ordinary_density - density))),
                        "blank_all_components_covered": blank_coverage,
                        "blank_area_interval_cm2": blank.get("area_interval"),
                        "blank_uncertain_cells": int(np.count_nonzero(blank.get("uncertain", []))),
                        "fresh_equal_content_matches": fresh_match,
                        "passed": bool(_spatial_match(candidate, reference) and coverage and decisions_sound
                                       and required_completion and _close(ordinary_density, density)
                                       and blank_coverage and fresh_match is not False)})
        except Exception as error:
            row["error"] = f"{type(error).__name__}: {error}"
        spatial_rows.append(row)
    control_rows, limitation_rows = [], []
    try:
        controls = _negative_controls(pair_decoder, spatial_decoder, geometry,
                                      checks=control_rows, limitations=limitation_rows)
    except Exception as error:
        for identifier in CONTROL_IDS:
            if identifier not in {row["id"] for row in control_rows}:
                control_rows.append({"id": identifier, "passed": False,
                                     "status": "not_completed_after_execution_error"})
        for identifier in LIMITATION_IDS:
            if identifier not in {row["id"] for row in limitation_rows}:
                limitation_rows.append({"id": identifier,
                                        "expected_undetected_wrong_answer_observed": False,
                                        "status": "not_completed_after_execution_error"})
        controls = {"passed": False, "error": f"{type(error).__name__}: {error}",
                    "checks": control_rows, "limitations": limitation_rows}
    controls["registered_counts"] = {"checks": len(CONTROL_IDS), "limitations": len(LIMITATION_IDS)}
    retained_checked = fresh_pair_decoder is not None and fresh_spatial_decoder is not None
    accepted = bool(all(row["passed"] for row in bulk_rows + spatial_rows)
                    and controls["passed"] and retained_checked)
    result = {"schema": SCHEMA, "seed": SEED,
              "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "parameters": {"mu_cm2_g": MU, "energies_kev": ENERGIES_KEV,
                             "corrected_read_relative_error": EPS,
                             "log_path_ratio_change_bound": DRIFT_BOUND,
                             "copper_threshold_g_cm3": THRESHOLD,
                             "cell_area_cm2": CELL_SIDE_CM ** 2,
                             "numeric_atol": NUMERIC_ATOL, "numeric_rtol": NUMERIC_RTOL},
              "registered_counts": {"bulk_cases": 80, "spatial_fields": 12,
                                    "rays_per_field": int(len(geometry))},
              "bulk": bulk_rows, "spatial": spatial_rows, "controls": controls,
              "retained_vs_fresh_equal_content_checked": retained_checked,
              "numerical_contract_accepted": accepted,
              "claims": {"conditional_synthetic_numerical_contract": accepted,
                         "physical_measurement_validation": False,
                         "new_physical_K1_or_K2": False,
                         "advantage_over_same_observation_ordinary_method": False,
                         "measured_photon_or_specimen_dose_saving": False,
                         "commercial_viability_or_new_industry": False,
                         "external_blinding_or_external_certification": False},
              "independence": "Separate implementation on a shared host; public authored family; no external blinding.",
              "cost_scope": "Generated signal units are not photons; economic accounting and qualification are separate."}
    return _json_ready(result)
