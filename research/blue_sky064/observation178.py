"""Prospective two-load observation contract for the Blue Sky 064 passive surface.

This does not measure physical forces. A mathematical interval certificate applies
only IF the supplied observations and externally established worst-case force
error bound are valid. No real physical/buyer/financial qualification is implied.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

SCHEMA = "agi-alpha/blue-sky-two-load-observation178/v1"
KEYS = ("low", "high")
FORCES = ("static_force_N", "dynamic_force_N")


def _number(value, *, positive=False, nonnegative=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("FINITE_NONBOOLEAN_FORCE_OR_ERROR_REQUIRED")
    number = float(value)
    if (positive and number <= 0) or (nonnegative and number < 0):
        raise ValueError("POSITIVE_FORCE_NONNEGATIVE_ERROR_REQUIRED")
    return number


def _readings(readings):
    if not isinstance(readings, dict) or set(readings) != set(KEYS):
        raise ValueError("TWO_DISTINCT_REGISTERED_LOADS_REQUIRED")
    out = {}
    for load in KEYS:
        row = readings[load]
        if not isinstance(row, dict) or set(row) != set(FORCES):
            raise ValueError("TWO_PHASE_FORCES_PER_LOAD_REQUIRED")
        out[load] = {phase: _number(row[phase], positive=True) for phase in FORCES}
    return out


def _down(value):
    if not math.isfinite(value):
        raise ValueError("FINITE_INTERVAL_REQUIRED")
    return math.nextafter(value, -math.inf)


def _up(value):
    if not math.isfinite(value):
        raise ValueError("FINITE_INTERVAL_REQUIRED")
    return math.nextafter(value, math.inf)


def _ratio(static, dynamic, epsilon):
    if static <= epsilon or dynamic <= epsilon:
        raise ValueError("POSITIVE_DENOMINATORS_AND_FORCE_INTERVALS_REQUIRED")
    lower = _down(_down(static - epsilon) / _up(dynamic + epsilon))
    upper = _up(_up(static + epsilon) / _down(dynamic - epsilon))
    return [lower, upper]


def assess(readings, epsilon_N, threshold):
    """Conservative static/dynamic ratio-difference interval at two loads.

    Four independent absolute-force errors are each bounded by epsilon_N.
    No independence/probability assumption is used. Values are source or input
    predictions until physically measured and independently calibrated.
    """
    rows = _readings(readings)
    epsilon = _number(epsilon_N, nonnegative=True)
    required = _number(threshold, nonnegative=True)
    lo = _ratio(rows["low"]["static_force_N"],
                rows["low"]["dynamic_force_N"], epsilon)
    hi = _ratio(rows["high"]["static_force_N"],
                rows["high"]["dynamic_force_N"], epsilon)
    change = [_down(hi[0] - lo[1]), _up(hi[1] - lo[0])]
    verdict = ("CONDITIONALLY_CERTIFIED" if change[0] >= required else
               "CONDITIONALLY_REFUTED" if change[1] < required else
               "INDETERMINATE")
    return {
        "threshold": required,
        "epsilon_N": epsilon,
        "ratio_intervals": {"low": lo, "high": hi},
        "change_interval": change,
        "conditional_math_verdict": verdict,
        "real_physical_observation_or_authority_established": False,
        "scope": "BOUNDED_FORCE_ERROR_IF_EXTERNALLY_ESTABLISHED_NOT_PHYSICAL_VALIDATION",
    }


def maximum_certifying_error(readings, threshold, *, iterations=100):
    rows = _readings(readings)
    required = _number(threshold, nonnegative=True)
    if type(iterations) is not int or not 10 <= iterations <= 200:
        raise ValueError("FINITE_NUMERIC_BISECTION_PROTOCOL_REQUIRED")
    zero = assess(rows, 0., required)
    if zero["conditional_math_verdict"] != "CONDITIONALLY_CERTIFIED":
        return {"maximum_epsilon_N_lower_bound": None, "reason": "NOMINAL_ALREADY_FAILS"}
    limit = min(row[k] for row in rows.values() for k in FORCES)
    low, high = 0., limit
    for _ in range(iterations):
        middle = low + (high - low) / 2.
        if middle <= low or middle >= high:
            break
        try:
            accepted = assess(rows, middle, required)["conditional_math_verdict"] == "CONDITIONALLY_CERTIFIED"
        except ValueError:
            accepted = False
        if accepted:
            low = middle
        else:
            high = middle
    return {
        "maximum_epsilon_N_lower_bound": low,
        "first_noncertifying_bound_N": high,
        "iterations_budget": iterations,
        "reason": "CONDITIONAL_ON_MODELED_FORCES_ONLY",
    }


def _areas(matrix):
    if not isinstance(matrix, dict) or set(matrix) != set(KEYS):
        raise ValueError("TWO_LOAD_TWO_FAMILY_AREA_MATRIX_REQUIRED")
    result = {}
    for load in KEYS:
        row = matrix[load]
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            raise ValueError("TWO_FAMILIES_PER_LOAD_REQUIRED")
        result[load] = [_number(v, nonnegative=True) for v in row]
    return result


def decompose_family_effective_forces(readings, areas, epsilon_N):
    """Linear diagnostic only, NOT a physical transfer or acceptance result."""
    r = _readings(readings)
    a = _areas(areas)
    e = _number(epsilon_N, nonnegative=True)
    a1,b1 = a["low"]
    a2,b2 = a["high"]
    determinant = a1*b2 - a2*b1
    if not math.isfinite(determinant) or determinant == 0.:
        raise ValueError("TWO_LOAD_FAMILY_MATRIX_RANK_DEFICIENT")
    # Validate against near-singular matrices; a spurious large inverse must not
    # become a credible material-property identification result.
    scale = max(a1*b2, a2*b1)
    if scale == 0. or abs(determinant) <= 64*math.ulp(scale):
        raise ValueError("TWO_LOAD_FAMILY_MATRIX_NUMERICALLY_UNIDENTIFIABLE")
    result = {}
    for phase in FORCES:
        y1 = r["low"][phase]
        y2 = r["high"][phase]
        c1 = (b2*y1 - b1*y2) / determinant
        c2 = (-a2*y1 + a1*y2) / determinant
        d1 = e * (b2+b1) / abs(determinant)
        d2 = e * (a2+a1) / abs(determinant)
        result[phase] = {
            "family_A_effective_N_per_mm2": [_down(c1-d1), _up(c1+d1)],
            "family_B_effective_N_per_mm2": [_down(c2-d2), _up(c2+d2)],
        }
    return {
        "determinant_mm4": determinant,
        "phase_coefficients": result,
        "source_model_only": True,
        "transfer_or_calibrated_measurement_established": False,
    }


def modeled_source_contract():
    """Use the old immutable source & registration; never generate new trials."""
    from research.blue_sky064.probe import load_inputs, mixed_composition, FIXTURE_SHA256, REGISTRATION_HASHES
    fixture, registrations = load_inputs()
    reg = registrations["MIXED_REGISTRATION.json"]
    old = mixed_composition(fixture, reg)
    states = old["prescribed_before_after"]
    if len(states) != 2 or reg["test_indentation_mm"] != [0.01,0.10]:
        raise ValueError("UNCHANGED_TWO_LOAD_REGISTRATION_REQUIRED")
    observations = {
        load: {"static_force_N": st["static_force_N"],
               "dynamic_force_N": st["dynamic_force_N"]}
        for load,st in zip(KEYS,states)
    }
    area_matrix = {load: st["family_area_mm2"] for load,st in zip(KEYS,states)}
    threshold = reg["necessary_construction_target"]["increase_in_static_dynamic_ratio_at_least"]
    at_zero = assess(observations, 0., threshold)
    return {
        "schema": SCHEMA,
        "mode": "PUBLIC_SOURCE_DERIVED_MODELED_MEASUREMENT_REQUIREMENT",
        "source_fixture_sha256": FIXTURE_SHA256,
        "registered_input_sha256": REGISTRATION_HASHES["MIXED_REGISTRATION.json"],
        "registered_indentation_mm": reg["test_indentation_mm"],
        "registered_threshold": threshold,
        "conditional_predicted_forces_N": observations,
        "conditional_predicted_normal_forces_N": [st["normal_force_N"] for st in states],
        "area_matrix_mm2": area_matrix,
        "zero_error_interval": at_zero,
        "maximum_certifying_absolute_force_error": maximum_certifying_error(observations, threshold),
        "linear_family_identification_diagnostic": decompose_family_effective_forces(
            observations, area_matrix, 0.),
        "source_calibration_independent_interval_worst_change": old["independent_interval_worst_ratio_increase"],
        "source_calibration_robust_pass": old["interval_function_pass"],
        "future_measurement_contract": "TWO_LOAD_FOUR_PHASE_SPECIMEN_READINGS_PLUS_INDEPENDENT_FORCE_ERROR_BOUND",
        "actual_physical_device_or_measurement": False,
        "actual_beneficiary_acceptance": False,
        "actual_paid_commerce": False,
        "economic_costs_and_host_billing": "UNKNOWN",
        "decision": "HOLD_OBTAIN_ASSEMBLY_MEASUREMENTS_AND_COMPLETE_ALTERNATIVE",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    out = args.output
    if (not out.is_absolute() or out.exists()
            or any(p.is_symlink() for p in [out, *out.parents])
            or not out.parent.is_dir()):
        raise SystemExit("NEW_REGULAR_ABSOLUTE_REPORT_REQUIRED")
    payload = modeled_source_contract()
    with out.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"output": str(out), "decision": payload["decision"],
                      "actual_physical_device_or_measurement": False}, sort_keys=True))


if __name__ == "__main__":
    main()
