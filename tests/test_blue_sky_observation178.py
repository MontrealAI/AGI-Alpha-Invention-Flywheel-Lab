"""Independent, source-bound and adversarial engineering controls for observation178."""
from __future__ import annotations
import itertools
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from research.blue_sky064.observation178 import (
    assess, decompose_family_effective_forces, maximum_certifying_error,
    modeled_source_contract,
)

ROOT = Path(__file__).resolve().parents[1]


def observations():
    return {
        "low": {"static_force_N": 2., "dynamic_force_N": 1.},
        "high": {"static_force_N": 5., "dynamic_force_N": 3.},
    }


class TwoLoadObservation178Tests(unittest.TestCase):
    def test_source_pinned_model_requirement_is_not_physical_confirmation(self):
        report = modeled_source_contract()
        self.assertFalse(report["actual_physical_device_or_measurement"])
        self.assertFalse(report["actual_beneficiary_acceptance"])
        self.assertFalse(report["actual_paid_commerce"])
        self.assertFalse(report["source_calibration_robust_pass"])
        self.assertEqual(report["registered_indentation_mm"], [0.01, 0.1])
        self.assertEqual(report["registered_threshold"], 0.05)
        self.assertAlmostEqual(
            report["zero_error_interval"]["change_interval"][0], 0.17212125749297225, places=10)
        error = report["maximum_certifying_absolute_force_error"]["maximum_epsilon_N_lower_bound"]
        self.assertAlmostEqual(error, 0.0024261742567738, places=10)
        self.assertEqual(report["decision"], "HOLD_OBTAIN_ASSEMBLY_MEASUREMENTS_AND_COMPLETE_ALTERNATIVE")

    def test_nominal_certificate_still_fails_with_excess_force_error(self):
        p = modeled_source_contract()
        r, t = p["conditional_predicted_forces_N"], p["registered_threshold"]
        self.assertEqual(assess(r, 0.002, t)["conditional_math_verdict"], "CONDITIONALLY_CERTIFIED")
        self.assertNotEqual(assess(r, 0.003, t)["conditional_math_verdict"], "CONDITIONALLY_CERTIFIED")
        self.assertFalse(assess(r, 0., t)["real_physical_observation_or_authority_established"])

    def test_all_sixteen_endpoint_combinations_inside_reported_change_interval(self):
        r = observations()
        e = 0.1
        b = assess(r, e, 0.05)
        fs0, fd0, fs1, fd1 = 2., 1., 5., 3.
        for signs in itertools.product((-1, 1), repeat=4):
            a,b0,c,d = [v + s*e for v,s in zip((fs0,fd0,fs1,fd1), signs)]
            observed = c/d - a/b0
            self.assertGreaterEqual(observed, b["change_interval"][0])
            self.assertLessEqual(observed, b["change_interval"][1])
        self.assertFalse(b["real_physical_observation_or_authority_established"])

    def test_refuted_and_indeterminate_are_distinct_from_certain_yes(self):
        x = {"low": {"static_force_N": 2., "dynamic_force_N": 1.},
             "high": {"static_force_N": 1., "dynamic_force_N": 1.}}
        self.assertEqual(assess(x, 0., .05)["conditional_math_verdict"], "CONDITIONALLY_REFUTED")
        x["high"]["static_force_N"] = 2.05
        self.assertEqual(assess(x, .1, .05)["conditional_math_verdict"], "INDETERMINATE")

    def test_registered_four_readings_are_mandatory_and_not_spoofable(self):
        invalid = [
            {"low": observations()["low"]},
            {"low": observations()["low"], "high": observations()["high"], "extra": {}},
            {"low": {"static_force_N": 2.}, "high": observations()["high"]},
            {"low": {"static_force_N": True, "dynamic_force_N": 1.}, "high": observations()["high"]},
            {"low": {"static_force_N": float("nan"), "dynamic_force_N": 1.}, "high": observations()["high"]},
            {"low": {"static_force_N": 0., "dynamic_force_N": 1.}, "high": observations()["high"]},
        ]
        for bad in invalid:
            with self.subTest(bad=str(bad)), self.assertRaises(ValueError):
                assess(bad, 0., .05)
        for invalid_error in [True, -0.1, float("inf"), float("nan"), "0"]:
            with self.subTest(error=str(invalid_error)), self.assertRaises(ValueError):
                assess(observations(), invalid_error, .05)
        for invalid_threshold in [True, -0.1, None, float("nan")]:
            with self.subTest(threshold=str(invalid_threshold)), self.assertRaises(ValueError):
                assess(observations(), 0., invalid_threshold)
        with self.assertRaisesRegex(ValueError, "POSITIVE_DENOMINATORS"):
            assess(observations(), 1., .05)

    def test_repeated_only_low_and_only_high_controls_have_no_family_identification(self):
        for same in ([1., 0.], [1., 1.], [0., 1.]):
            with self.subTest(same=same), self.assertRaisesRegex(ValueError, "RANK_DEFICIENT"):
                decompose_family_effective_forces(observations(), {"low": same, "high": same}, .1)
        with self.assertRaises(ValueError):
            decompose_family_effective_forces(observations(), {"low": [1., 0.]}, .1)

    def test_two_load_decomposition_recovers_conditional_effective_families(self):
        # A-only low, A+B high; 2N/1N and 3N/2N known coefficients.
        r = observations()
        areas = {"low": [1., 0.], "high": [1., 1.]}
        result = decompose_family_effective_forces(r, areas, .1)
        self.assertFalse(result["transfer_or_calibrated_measurement_established"])
        for phase, a,b in [("static_force_N",2.,3.),("dynamic_force_N",1.,2.)]:
            intervals = result["phase_coefficients"][phase]
            self.assertLessEqual(intervals["family_A_effective_N_per_mm2"][0], a)
            self.assertGreaterEqual(intervals["family_A_effective_N_per_mm2"][1], a)
            self.assertLessEqual(intervals["family_B_effective_N_per_mm2"][0], b)
            self.assertGreaterEqual(intervals["family_B_effective_N_per_mm2"][1], b)
        self.assertAlmostEqual(result["determinant_mm4"],1.)

    def test_measurement_errors_enclose_every_extreme_family_solution(self):
        areas = {"low": [1., 0.], "high": [1., 1.]}
        epsilon = 0.1
        band = decompose_family_effective_forces(observations(), areas, epsilon)
        for phase in ("static_force_N", "dynamic_force_N"):
            y1, y2 = observations()["low"][phase], observations()["high"][phase]
            for signed_e1, signed_e2 in itertools.product((-epsilon, epsilon), repeat=2):
                a = y1+signed_e1
                b = y2+signed_e2-a
                a_interval = band["phase_coefficients"][phase]["family_A_effective_N_per_mm2"]
                b_interval = band["phase_coefficients"][phase]["family_B_effective_N_per_mm2"]
                self.assertLessEqual(a_interval[0], a)
                self.assertGreaterEqual(a_interval[1], a)
                self.assertLessEqual(b_interval[0], b)
                self.assertGreaterEqual(b_interval[1], b)

    def test_no_nominal_pass_produces_no_certifying_precision(self):
        not_enough = {"low": {"static_force_N": 1.0, "dynamic_force_N": 1.0},
                      "high": {"static_force_N": 1.01, "dynamic_force_N": 1.0}}
        result = maximum_certifying_error(not_enough, .05)
        self.assertIsNone(result["maximum_epsilon_N_lower_bound"])
        self.assertEqual(result["reason"], "NOMINAL_ALREADY_FAILS")
        with self.assertRaises(ValueError):
            maximum_certifying_error(observations(), .05, iterations=0)

    def test_cli_new_absolute_report_and_explicit_modeled_only_qualification(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "source-model.json"
            cmd = [sys.executable, "-B", "-m", "research.blue_sky064.observation178",
                   "--output", str(out)]
            run = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=40)
            self.assertEqual(run.returncode,0,run.stderr)
            report=json.loads(out.read_text())
            self.assertFalse(report["actual_physical_device_or_measurement"])
            self.assertIn("SOURCE_DERIVED",report["mode"])
            second=subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=40)
            self.assertNotEqual(second.returncode,0)
            self.assertIn("NEW_REGULAR_ABSOLUTE_REPORT_REQUIRED",second.stderr)


if __name__ == "__main__":
    unittest.main()
