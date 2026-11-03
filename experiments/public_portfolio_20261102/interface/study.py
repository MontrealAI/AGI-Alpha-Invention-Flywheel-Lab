"""Finite, preregistered computational studies; fixtures are authored, not measured."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from .instrument import MU_CM2_G, compile_interface, conventional, estimate, ray_matrix, reconstruct


def _observations(masses, rng, noisy=True, shifted=False):
    shape = masses.shape[:-1] + (3,)
    index = np.arange(np.prod(shape)).reshape(shape)
    gain = (0.1 + 2.8 * (0.5 + 0.5 * np.sin(index * 0.37))) if shifted else rng.uniform(0.5, 1.5, shape)
    dark = rng.uniform(0, 20000 if shifted else 2000, shape)
    reference = 1e6 * gain
    sample = reference * np.exp(-masses @ MU_CM2_G.T)
    eps = 0.0001
    if noisy:
        sample *= 1 + rng.uniform(-eps, eps, shape)
        reference *= 1 + rng.uniform(-eps, eps, shape)
    return sample + dark, reference + dark, dark


def _jsonable(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def run_experiment(output_dir):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("nonempty output directory; preserve previous results")
    started = time.perf_counter()
    cpu_started = time.process_time()
    rng = np.random.default_rng(2026110203101)
    k1 = []
    for label, noisy, shifted in [("analytic", False, False), ("bounded_noise", True, False), ("drift_shift", True, True)]:
        truth = rng.uniform([0.05, 0.02], [1.5, 0.4], (64, 2))
        sample, reference, dark = _observations(truth, rng, noisy, shifted)
        retained = estimate(sample, reference, dark)
        ordinary = conventional(sample, reference, dark)
        error = np.abs(retained["mass_areal_density_g_cm2"] - truth)
        no_reference = -np.log((sample - dark) / 1e6) @ compile_interface()["decoder"].T
        no_dark = estimate(sample, reference, np.zeros_like(dark))
        k1.append({"arm": label, "cases": 64, "accepted": int(retained["accepted"].sum()),
                   "bound_covered": int((error <= retained["component_error_bound_g_cm2"]).all(axis=1).sum()),
                   "max_component_error_g_cm2": error.max(axis=0),
                   "declared_component_bound_g_cm2": retained["component_error_bound_g_cm2"],
                   "ordinary_max_difference": float(np.max(np.abs(ordinary - retained["mass_areal_density_g_cm2"]))),
                   "no_reference_max_error": float(np.max(np.abs(no_reference - truth))),
                   "no_dark_max_error": float(np.max(np.abs(no_dark["mass_areal_density_g_cm2"] - truth)))})
        if label == "drift_shift":
            (output / "K1_ARTIFACT.json").write_text(json.dumps(_jsonable({"truth_role": "authored evaluator fixture, never an estimator input",
                       "sample": sample, "reference": reference, "dark": dark, "truth": truth, "output": retained}), indent=2) + "\n")
    rng_k2 = np.random.default_rng(2026110203102)
    geometry = ray_matrix()
    k2 = []
    for case in range(16):
        density = rng_k2.uniform([2.4, 0.1], [2.7, 0.3], (16, 2))
        defective_pixel = int(rng_k2.integers(16))
        density[defective_pixel] *= rng_k2.uniform(0.1, 0.3)
        sample, reference, dark = _observations(geometry @ density, rng_k2, True, True)
        retained = reconstruct(sample, reference, dark, geometry)
        fresh = reconstruct(sample, reference, dark, geometry, inherit=False)
        ordinary_lines = conventional(sample, reference, dark)
        ordinary = np.linalg.lstsq(geometry, ordinary_lines, rcond=None)[0].reshape(4, 4, 2)
        error = np.abs(retained["density_g_cm3"] - density.reshape(4, 4, 2))
        predicted_pixel = int(np.argmin(retained["density_g_cm3"].sum(axis=-1)))
        k2.append({"case": case, "accepted": retained["accepted"], "localized_pixel": predicted_pixel == defective_pixel,
                   "bound_covered": bool((error <= retained["component_error_bound_g_cm3"]).all()),
                   "max_error_g_cm3": float(error.max()),
                   "ordinary_max_difference": float(np.max(np.abs(ordinary - retained["density_g_cm3"]))),
                   "no_inheritance_max_difference": float(np.max(np.abs(fresh["density_g_cm3"] - retained["density_g_cm3"])))})
        if case == 0:
            (output / "K2_ARTIFACT.json").write_text(json.dumps(_jsonable({"projection_matrix_cm": geometry,
                "sample": sample, "reference": reference, "dark": dark, "truth_density_g_cm3": density.reshape(4, 4, 2),
                "defective_pixel": defective_pixel, "output": retained}), indent=2) + "\n")
    base_mass = np.array([0.8, 0.1])
    sample, reference, dark = _observations(base_mass, rng, False, False)
    nonpositive = estimate(dark, reference, dark)
    third_material_sample = (sample - dark) * np.exp(-np.array([1.958, 0.3717, 0.1964])) + dark
    third_material = estimate(third_material_sample, reference, dark)
    # A coherent mismatch is exactly observationally equivalent to extra material.
    delta_mass = np.array([0.2, 0.03])
    mismatch_sample = (sample - dark) * np.exp(-MU_CM2_G @ delta_mass) + dark
    mismatch = estimate(mismatch_sample, reference, dark)
    rank_deficient = reconstruct(sample[None, :], reference[None, :], dark[None, :], np.ones((1, 16)))
    failure_cases = {"nonpositive_corrected_signal_rejected": not bool(nonpositive["accepted"]),
        "large_unmodeled_iron_rejected": not bool(third_material["accepted"]),
        "rank_deficient_geometry_rejected": not rank_deficient["accepted"],
        "coherent_gain_mismatch_accepted": bool(mismatch["accepted"]),
        "coherent_gain_mismatch_error_g_cm2": mismatch["mass_areal_density_g_cm2"] - base_mass,
        "coherent_gain_mismatch_is_outside_contract": True,
        "universal_physical_fault_detection": False}
    source = Path(__file__).parent
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.glob("*.py"))}
    result = {"experiment": "public-portfolio-20261102-interface-v1", "model": "NIST-coefficient ideal monochromatic Beer-Lambert",
        "source_sha256": hashes, "preregistration_sha256": hashlib.sha256((source / "PREREGISTRATION.json").read_bytes()).hexdigest(),
        "K1": k1, "K2": k2, "K2_geometry": {"rays": len(geometry), "pixels": 16,
            "rank": int(np.linalg.matrix_rank(geometry)), "condition_number": float(np.linalg.cond(geometry))},
        "failure_cases": failure_cases, "claims": {"actual_computational_artifacts": True,
            "physical_validation": False, "new_scientific_method": False, "retained_algorithmic_advantage": False,
            "industry_creation": "unresolved; incumbent already implements core interface", "actual_commerce": False},
        "human_intervention": {"during_automated_run_minutes": 0,
            "upstream_user_direction_minutes": "unmeasured", "physical_qualification_minutes": "unperformed"},
        "resource_measurement": {"wall_seconds": time.perf_counter() - started,
                                 "cpu_seconds": time.process_time() - cpu_started}}
    result = _jsonable(result)
    (output / "RESULTS.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    results = run_experiment(args.output)
    print(json.dumps({"K1_accepted": sum(a["accepted"] for a in results["K1"]),
                      "K2_accepted": sum(a["accepted"] for a in results["K2"]),
                      "failure_cases": results["failure_cases"]}, indent=2))
