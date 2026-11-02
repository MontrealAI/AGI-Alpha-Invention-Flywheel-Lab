import argparse
import hashlib
import importlib.util
import itertools
import json
import math
import resource
import time
from fractions import Fraction as Q
from pathlib import Path

import numpy as np
from scipy.integrate import quad

BASE = Path(__file__).resolve().parents[1]
TRUTH = np.array([120., -40., 70., 25., -15., 10.])


def polynomial_derivative(order, t):
    return sum(((-1) ** k * Q(math.comb(6, k)) * Q(math.factorial(2 * k), math.factorial(2 * k - order)) * t ** (2 * k - order) for k in range(7) if 2 * k >= order), Q(0))


def derivative_integral(order):
    total = Q(0)
    for k in range(7):
        power = 2 * k - order
        if power >= 0 and power % 2 == 0:
            total += (-1) ** k * Q(math.comb(6, k)) * Q(math.factorial(2 * k), math.factorial(power)) * Q(2, power + 1)
    return total


def potential_derivative(point, widths, amplitude, orders):
    a, b, c = widths
    A = amplitude / (Q(360) / b ** 2 + Q(144) / c ** 2)
    result = A
    for axis, (coordinate, width, order) in enumerate(zip(point, widths, orders)):
        result *= polynomial_derivative(order + (2 if axis == 1 else 0), coordinate / width) / width ** order
    return result


def reference_stress(point, widths, amplitude, extra=None):
    if any(abs(v) >= w for v, w in zip(point, widths)):
        return [[Q(0) for j in range(3)] for i in range(3)]
    extra = [0, 0, 0] if extra is None else extra
    result = []
    for i in range(3):
        row = []
        for j in range(3):
            if i == j:
                value = Q(0)
                for k in range(3):
                    if k != i:
                        orders = list(extra)
                        orders[k] += 2
                        value += potential_derivative(point, widths, amplitude, orders)
            else:
                orders = list(extra)
                orders[i] += 1
                orders[j] += 1
                value = -potential_derivative(point, widths, amplitude, orders)
            row.append(value)
        result.append(row)
    return result


def tensor(vector):
    xx, yy, zz, xy, xz, yz = vector
    return np.array([[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]], dtype=float)


def reference_observation(directions, E, nu):
    columns = []
    for basis in np.eye(6):
        stress = tensor(basis)
        strain = np.empty((3, 3))
        for i in range(3):
            for j in range(3):
                strain[i, j] = ((stress[i, i] - nu * sum(stress[k, k] for k in range(3) if k != i)) / E) if i == j else (1 + nu) * stress[i, j] / E
        columns.append([float(np.asarray(q) @ strain @ np.asarray(q)) for q in directions])
    return np.array(columns).T


def operator_check(candidate, name, directions, target, E, nu, expected):
    expected_H = reference_observation(directions, E, nu)
    actual_H = candidate.observation(directions, E, nu)
    observation_error = float(np.max(np.abs(expected_H - actual_H)))
    measured = expected_H @ TRUTH
    result = candidate.certificate(actual_H, measured, target, 1e-6)
    identified = result["status"] == "IDENTIFIED_MODEL_ONLY"
    passed = identified == expected and observation_error < 1e-15
    row = {"case": name, "expected_identified": expected, "actual": result["status"], "independent_H_error": observation_error}
    if identified:
        truth = float(np.asarray(target) @ TRUTH)
        max_error = 0.
        for signs in itertools.product((-1, 1), repeat=len(directions)):
            perturbed = candidate.certificate(actual_H, measured + np.array(signs) * 1e-6, target, 1e-6)
            max_error = max(max_error, abs(perturbed["estimate_mpa"] - truth))
        passed = passed and abs(result["estimate_mpa"] - truth) < 1e-8 and max_error <= result["radius_mpa"] + 1e-8
        row.update(target_truth_mpa=truth, corner_maximum_error_mpa=max_error, reported_radius_mpa=result["radius_mpa"])
    else:
        witness = np.asarray(result["null_direction"])
        gap = float(np.max(np.abs(expected_H @ witness)))
        changed = abs(float(np.asarray(target) @ witness))
        passed = passed and gap < 1e-12 and changed > 1e-8
        row.update(independent_observation_gap=gap, target_change_per_unit=changed)
    row["pass"] = bool(passed)
    return row


def run():
    before = time.monotonic()
    cpu0 = resource.getrusage(resource.RUSAGE_SELF)
    spec = importlib.util.spec_from_file_location("reviewed_n3_instrument", BASE / "n3" / "instrument.py")
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    rows = []
    axes = np.eye(3)
    xx = np.array([1., 0, 0, 0, 0, 0])
    difference = np.array([1., 0, -1., 0, 0, 0])
    xy = np.array([0., 0, 0, 1., 0, 0])
    for nu in (-.2, 0., .3):
        for label, target, expected in (("xx", xx, nu == 0), ("difference", difference, True)):
            rows.append(operator_check(candidate, f"normal_nu_{nu}_{label}", axes[[0, 2]], target, 200000., nu, expected))
    alpha, beta = math.radians(3.450991), math.radians(3.2238065)
    tilted = np.array([[math.cos(alpha), math.sin(alpha), 0.], [0., math.sin(beta), math.cos(beta)]])
    rows.append(operator_check(candidate, "tilted_missing_shear", tilted, difference, 200000., .3, False))
    rows.append(operator_check(candidate, "three_exact_axes_normal", axes, xx, 200000., .3, True))
    six = np.vstack([axes, [.6, .8, 0.], [.6, 0., .8], [0., .6, .8]])
    rows.append(operator_check(candidate, "six_rational_directions_normal", six, xx, 200000., .3, True))
    rows.append(operator_check(candidate, "six_rational_directions_shear", six, xy, 200000., .3, True))
    independent_tilt_strain = np.array([[1e-4, -1e-4 * math.cos(alpha) / (2 * math.sin(alpha)), 0.], [-1e-4 * math.cos(alpha) / (2 * math.sin(alpha)), 0., 0.], [0., 0., 0.]])
    tilt_reads = [float(q @ independent_tilt_strain @ q) for q in tilted]
    rows.append({"case": "analytic_tilted_direction_counterexample", "readings_strain": tilt_reads, "xx_minus_zz_change_strain": 1e-4, "pass": max(abs(v) for v in tilt_reads) < 1e-15})
    integral_zero = all(derivative_integral(k) == 0 for k in (2, 3, 4))
    boundary_smooth = all(polynomial_derivative(k, Q(side)) == 0 for k in range(6) for side in (-1, 1))
    rows.append({"case": "exact_polynomial_integrals_and_boundary", "derivative_integrals": {str(k): str(derivative_integral(k)) for k in (2, 3, 4)}, "boundary_derivatives_zero_through_order": 5, "pass": integral_zero and boundary_smooth})
    for widths_tuple in ((1, 1, 1), (1, Q(1, 2), 2), (2, 1, Q(1, 2))):
        widths = tuple(Q(v) for v in widths_tuple)
        for amplitude in (-100, 100):
            max_error, max_mean, divergence_exact = 0., 0., True
            for fractions in ((0, 0, 0), (Q(1, 3), Q(1, 4), -Q(1, 5)), (-Q(1, 5), Q(2, 7), Q(1, 3)), (Q(9, 10), -Q(4, 5), Q(7, 8))):
                point = tuple(v * w for v, w in zip(fractions, widths))
                truth = reference_stress(point, widths, Q(amplitude))
                actual = candidate.compact_stress(*[float(v) for v in point], [float(v) for v in widths], amplitude)
                max_error = max(max_error, float(np.max(np.abs(actual - np.array(truth, dtype=float)))))
                for i in range(3):
                    divergence = Q(0)
                    for j in range(3):
                        derivative = [0, 0, 0]
                        derivative[j] = 1
                        divergence += reference_stress(point, widths, Q(amplitude), derivative)[i][j]
                    divergence_exact = divergence_exact and divergence == 0
            a, b, c = (float(v) for v in widths)
            for i in range(3):
                for j in range(i, 3):
                    integral, error = quad(lambda y: candidate.compact_stress(a / 5, y, -2 * c / 7, (a, b, c), amplitude)[i, j], -b, b, epsabs=1e-9, epsrel=1e-10)
                    max_mean = max(max_mean, abs(integral / (2 * b)))
            boundary_max = max(float(np.max(np.abs(candidate.compact_stress(*(np.eye(3)[j] * sign * np.array([a, b, c])), (a, b, c), amplitude)))) for j in range(3) for sign in (-1, 1))
            center = candidate.compact_stress(0, 0, 0, (a, b, c), amplitude)
            strain = candidate.elastic_strain(center)
            independent_strain = np.diag([(center[i, i] - .3 * sum(center[k, k] for k in range(3) if k != i)) / 200000 for i in range(3)])
            energy = float(np.sum(center * strain) / 2)
            passed = max_error < 1e-9 and max_mean < 1e-9 and divergence_exact and boundary_max == 0 and abs(center[0, 0] - amplitude) < 1e-10 and np.max(np.abs(strain - independent_strain)) < 1e-15 and energy >= 0
            rows.append({"case": "compact_field", "halfwidths_mm": [a, b, c], "amplitude_mpa": amplitude, "reference_max_error_mpa": max_error, "independent_quadrature_mean_max_mpa": max_mean, "exact_reference_divergence_zero": bool(divergence_exact), "boundary_stress_max_mpa": boundary_max, "center_energy_density_mpa": energy, "pass": bool(passed)})
    series = np.array([4e-4, -1e-4, 7e-4, 2e-4])
    for offset in (-.002, 0., .002):
        centered = candidate.centered_rmse(series, series + offset)
        absolute = float(np.sqrt(np.mean((series - (series + offset)) ** 2)))
        rows.append({"case": "scoring_target_scope", "offset_strain": offset, "centered_rmse": centered, "absolute_rmse": absolute, "pass": centered < 1e-15 and abs(absolute - abs(offset)) < 1e-15})
    invalid = [
        ("bad_H_shape", lambda: candidate.certificate([[1, 2]], [0], xx)),
        ("empty_measurements", lambda: candidate.certificate(np.empty((0, 6)), [], xx)),
        ("unstable_material", lambda: candidate.observation(axes, 200000, .6)),
        ("nonsymmetric_stress", lambda: candidate.elastic_strain([[1, 1, 0], [0, 1, 0], [0, 0, 1]])),
        ("negative_width", lambda: candidate.compact_stress(0, 0, 0, (1, -1, 1))),
    ]
    for name, action in invalid:
        try:
            action()
            passed = False
        except ValueError:
            passed = True
        rows.append({"case": name, "pass": passed})
    cpu1 = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "reviewer": "independent_scientist", "scope": "FINITE_AUTHORED_MODEL_AND_SOURCE_SCOPE_REVIEW",
        "independence": "Exact Fraction polynomial/compliance references, direct tensor contractions, and adaptive quadrature are separate from candidate Polynomial/lstsq/Legendre construction. No candidate reference labels or raw measured strain values are used.",
        "registered_denominator": len(rows), "passed": sum(r["pass"] for r in rows), "failed": sum(not r["pass"] for r in rows), "cases": rows,
        "raw_measurement_rows_opened": 0, "physical_admission": False, "successor_physical_admission": False,
        "resource": {"wall_s": time.monotonic() - before, "process_cpu_s": cpu1.ru_utime + cpu1.ru_stime - cpu0.ru_utime - cpu0.ru_stime},
        "source_sha256": {str(p.relative_to(BASE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), BASE / "n3" / "instrument.py", BASE / "n3" / "CONTRACT.md"]},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Use a new attempt-specific output path")
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: result[k] for k in ("registered_denominator", "passed", "failed", "physical_admission")}))
    raise SystemExit(0 if result["failed"] == 0 else 1)
