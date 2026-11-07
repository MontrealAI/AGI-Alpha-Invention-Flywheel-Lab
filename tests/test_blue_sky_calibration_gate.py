"""Adversarial checks for the finite, preregistered calibration-dependency gate."""
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest

from research.blue_sky064 import probe
from research.blue_sky064.calibration_gate import plan


class CalibrationGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture, cls.regs = probe.load_inputs()
        cls.registration = cls.regs["MIXED_REGISTRATION.json"]
        cls.families = [
            next(f for f in cls.fixture["calibration"] if f["id"] == name)
            for name in cls.registration["families"]
        ]
        cls.params = plan.source_parameters(cls.fixture, cls.registration)

    def test_frozen_public_source_and_eight_fitted_coefficients(self):
        self.assertEqual(len(self.params), 8)
        self.assertEqual(len({p["name"] for p in self.params}), 8)
        for p in self.params:
            self.assertLessEqual(p["low"], p["estimate"])
            self.assertLessEqual(p["estimate"], p["high"])

    def test_no_measurement_matches_existing_unmodified_source(self):
        control = probe.mixed_composition(self.fixture, self.registration)
        values = [p["estimate"] for p in self.params]
        self.assertAlmostEqual(
            plan.ratio_delta(values, self.families, self.registration),
            control["nominal_ratio_increase"], delta=1e-12
        )
        worst, best, corner = plan.enumerate_worst(
            plan.intervals_for_mask(self.params, 0, 0.50),
            self.families, self.registration
        )
        self.assertAlmostEqual(
            worst, control["independent_interval_worst_ratio_increase"],
            delta=1e-12
        )
        self.assertLessEqual(worst, best)
        self.assertEqual(len(corner), 8)

    def test_shared_hidden_coefficient_across_both_load_states(self):
        # For the same eight slopes, the ratio comparison uses the same
        # coefficient values at both indentation states, not an oracle that
        # chooses a different unknown coefficient at each state.
        values = [p["estimate"] for p in self.params]
        actual = plan.ratio_delta(values, self.families, self.registration)
        original = probe.mixed_composition(self.fixture, self.registration)
        self.assertAlmostEqual(
            actual, original["nominal_ratio_increase"], delta=1e-12
        )
        self.assertGreater(actual, 0.05)

    def test_zero_width_exact_measurement_is_point_value(self):
        intervals = plan.intervals_for_mask(self.params, 255, 0.0)
        self.assertTrue(all(lo == hi == p["estimate"]
                            for (lo, hi), p in zip(intervals, self.params)))
        worst, best, _ = plan.enumerate_worst(
            intervals, self.families, self.registration
        )
        nominal = plan.ratio_delta(
            [p["estimate"] for p in self.params],
            self.families, self.registration
        )
        self.assertAlmostEqual(worst, nominal, delta=1e-12)
        self.assertAlmostEqual(best, nominal, delta=1e-12)

    def test_frozen_fraction_narrows_without_changing_nominal(self):
        for q in plan.QS:
            for mask in (0, 1, 17, 136, 255):
                intervals = plan.intervals_for_mask(self.params, mask, q)
                for p, (lo, hi) in zip(self.params, intervals):
                    self.assertLessEqual(lo, p["estimate"])
                    self.assertLessEqual(p["estimate"], hi)
        for mask in (0, 1, 17, 136, 255):
            a = plan.intervals_for_mask(self.params, mask, 0.0)
            b = plan.intervals_for_mask(self.params, mask, 0.25)
            c = plan.intervals_for_mask(self.params, mask, 0.50)
            for ai, bi, ci in zip(a, b, c):
                self.assertGreaterEqual(ai[0], bi[0])
                self.assertGreaterEqual(bi[0], ci[0])
                self.assertLessEqual(ai[1], bi[1])
                self.assertLessEqual(bi[1], ci[1])

    def test_bad_types_and_invalid_measurement_masks_fail_closed(self):
        for bad in (-1, 256, 1.0, True, None):
            with self.subTest(mask=bad):
                with self.assertRaises(ValueError):
                    plan.intervals_for_mask(self.params, bad, 0.25)
        for bad in (0, 1, -0.1, 1.1, float("nan"), True, "0.25"):
            with self.subTest(q=bad):
                with self.assertRaises(ValueError):
                    plan.intervals_for_mask(self.params, 15, bad)

    def test_missing_dynamic_normalization_refuses(self):
        values = [p["estimate"] for p in self.params]
        values[2] = 0
        with self.assertRaises(ValueError):
            plan.ratio_delta(values, self.families, self.registration)
        with self.assertRaises(ValueError):
            plan.ratio_delta(values[:-1], self.families, self.registration)

    def test_wrong_observation_sequence_refuses(self):
        bad = copy.deepcopy(self.registration)
        bad["test_indentation_mm"] = [0.10, 0.01]
        with self.assertRaises(ValueError):
            plan.ratio_delta(
                [p["estimate"] for p in self.params], self.families, bad
            )

    def test_changed_source_fixture_is_not_accepted(self):
        original = Path(probe.__file__).with_name("public_calibration.json")
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "public_calibration.json"
            content = original.read_bytes().replace(b"Batch1_R496",
                                                    b"Batch1_R497")
            self.assertNotEqual(original.read_bytes(), content)
            target.write_bytes(content)
            with self.assertRaisesRegex(ValueError, "FROZEN_SOURCE"):
                probe.load_inputs(fixture_path=target)

    def test_all_768_frozen_subsets_have_256_shared_corners(self):
        output = plan.experiment()
        self.assertEqual(output["decision"],
                         "NO_DEPLOY_HOLD_PENDING_PHYSICAL_TRANSFER_AND_BUYER_EVIDENCE")
        self.assertEqual(output["physical_observations_added"], 0)
        self.assertIsNone(output["modeled_financial_account"])
        self.assertEqual(len(output["worlds"]), 3)
        for key, case in output["worlds"].items():
            rows = case["all_registered_subset_outcomes"]
            self.assertEqual(len(rows), 256)
            self.assertEqual(case["subset_count"], 256)
            self.assertEqual(case["corner_evaluations"], 65536)
            self.assertEqual(len({row["mask"] for row in rows}), 256)
            for k in range(9):
                self.assertEqual(case["by_cardinality"][str(k)]["tested"],
                                 math.comb(8, k))
            qualified = [r for r in rows if r["conditional_certificate"]]
            min_k = min((r["count"] for r in qualified), default=None)
            self.assertEqual(case["minimal_number_of_measurements"], min_k)
            self.assertEqual(case["no_measure_worst"], rows[0]["worst_delta"])
            self.assertEqual(case["all_eight_worst"], rows[255]["worst_delta"])
            for row in rows:
                self.assertEqual(len(row["worst_shared_corner"]), 8)
                self.assertEqual(row["conditional_certificate"],
                                 row["worst_delta"] >= 0.05)

    def test_more_ideal_measurement_information_cannot_worsen_certificate(self):
        output = plan.experiment()
        rows = [output["worlds"][str(q)]["all_registered_subset_outcomes"]
                for q in plan.QS]
        for mask in range(256):
            self.assertGreaterEqual(
                rows[0][mask]["worst_delta"] + 1e-12,
                rows[1][mask]["worst_delta"]
            )
            self.assertGreaterEqual(
                rows[1][mask]["worst_delta"] + 1e-12,
                rows[2][mask]["worst_delta"]
            )
        for mask in range(256):
            for index in range(8):
                if not mask & (1 << index):
                    larger = mask | (1 << index)
                    for row in rows:
                        self.assertGreaterEqual(
                            row[larger]["worst_delta"] + 1e-12,
                            row[mask]["worst_delta"]
                        )

    def test_finite_output_and_strict_no_deploy_scope(self):
        output = plan.experiment()
        self.assertEqual(output["real_collections_usd"], 0)
        self.assertEqual(output["real_buyers"], 0)
        self.assertEqual(output["complete_calibration_and_commercial_cost_usd"],
                         "UNKNOWN")
        self.assertEqual(output["host_and_model_billing_usd"], "UNKNOWN")
        json.dumps(output, allow_nan=False)
        for world in output["worlds"].values():
            self.assertEqual(world["strong_ordinary_baseline"],
                             "EXHAUSTIVE_ALL_SUBSETS_IDENTICAL")
            self.assertFalse(world["all_registered_subset_outcomes"][0]
                             ["conditional_certificate"])


if __name__ == "__main__":
    unittest.main()
