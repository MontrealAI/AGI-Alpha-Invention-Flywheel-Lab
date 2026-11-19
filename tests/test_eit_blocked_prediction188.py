"""Frozen offline EIT188 analytic, leakage and refusal controls: no network."""
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from research.eit_physical_control183.control import Refusal
from research.eit_blocked_prediction188.compare import (
    GAMMAS, fixed_blocked_predictions, main,
)


def fixture():
    v0 = np.arange(1, 13, dtype=np.float64).reshape(4, 3)
    v1 = 2.0 * v0 + 1.0
    J = np.column_stack((np.arange(1, 13, dtype=np.float64),
                         np.linspace(-1, 2, 12, dtype=np.float64)))
    return J, v0, v1


class FrozenBlockedPrediction188Tests(unittest.TestCase):
    def test_all_sixteen_folds_schema_on_full_size_and_three_on_fixture(self):
        J, v0, v1 = fixture()
        r = fixed_blocked_predictions(J, v0, v1)
        self.assertEqual(r["all_fixed_columns"], [0, 1, 2])
        self.assertEqual(len(r["arms"]), 3 + 2 * len(GAMMAS))
        self.assertEqual([x["method"] for x in r["arms"][:3]],
                         ["zero", "gain_only", "gain_and_offset"])
        self.assertEqual(r["candidate_methods_in_fixed_order"][-1], "ridge_F_gamma_100")
        for arm in r["arms"]:
            self.assertEqual(arm["heldout_readings"], 12)
            self.assertEqual(arm["heldout_column_count"], 3)
            self.assertEqual(len(arm["all_fold_rms"]), 3)
            self.assertEqual(len(arm["all_fold_fit_details"]), 3)
            self.assertTrue(math.isfinite(arm["heldout_l2"]))
            self.assertAlmostEqual(arm["heldout_rms"], arm["heldout_l2"]/math.sqrt(12), 12)
        self.assertFalse(r["original_full_spatial_prior_reconstructed"])
        self.assertFalse(r["physical_uncertainty_calibrated"])
        self.assertIsNone(r["actual_buyer_payments_usd"])

    def test_exact_ordinary_gain_and_offset_baseline_is_not_crippled(self):
        J, v0, v1 = fixture()
        r = fixed_blocked_predictions(J, v0, v1)
        gain_offset = r["arms"][2]
        self.assertLess(gain_offset["heldout_rms"], 1e-12)
        self.assertGreater(r["arms"][0]["heldout_rms"], 0)
        self.assertGreater(r["arms"][1]["heldout_rms"], gain_offset["heldout_rms"])
        self.assertEqual(r["arms"][0]["rms_ratio_to_zero"], 1.0)

    def test_holdout_change_cannot_affect_its_own_training(self):
        J, v0, v1 = fixture()
        before = fixed_blocked_predictions(J, v0, v1)
        shifted = v1.copy()
        shifted[:, 0] += 17.0
        after = fixed_blocked_predictions(J, v0, shifted)
        for method in ("gain_only", "gain_and_offset"):
            a = next(x for x in before["arms"] if x["method"] == method)
            b = next(x for x in after["arms"] if x["method"] == method)
            self.assertEqual(a["all_fold_fit_details"][0],
                             b["all_fold_fit_details"][0])
            self.assertNotEqual(a["all_fold_rms"][0], b["all_fold_rms"][0])
        for order in ("C", "F"):
            for gamma in GAMMAS:
                name = f"ridge_{order}_gamma_{gamma:g}"
                a = next(x for x in before["arms"] if x["method"] == name)
                b = next(x for x in after["arms"] if x["method"] == name)
                self.assertEqual(a["all_fold_fit_details"][0]["fitted_coefficient_sha256"],
                                 b["all_fold_fit_details"][0]["fitted_coefficient_sha256"])
                self.assertNotEqual(a["all_fold_rms"][0], b["all_fold_rms"][0])

    def test_two_flatten_hypotheses_not_silently_collapsed(self):
        J, v0, v1 = fixture()
        actual = fixed_blocked_predictions(J, v0, v1)
        C = next(x for x in actual["arms"] if x["method"] == "ridge_C_gamma_1")
        F = next(x for x in actual["arms"] if x["method"] == "ridge_F_gamma_1")
        self.assertNotEqual(C["all_fold_rms"], F["all_fold_rms"])
        self.assertEqual(len(C["all_fold_fit_details"]), 3)
        self.assertTrue(all(f["training_readings"] == 8 and
                            f["heldout_readings"] == 4 for f in C["all_fold_fit_details"]))

    def test_rejects_bad_shapes_complex_nonfinite_inputs_and_zero_contrast(self):
        J, v0, v1 = fixture()
        for bad in (J.astype(complex), J * float("nan"), J[:-1, :]):
            with self.subTest(which=bad.shape, dtype=bad.dtype), self.assertRaises(Refusal):
                fixed_blocked_predictions(bad, v0, v1)
        with self.assertRaises(Refusal):
            fixed_blocked_predictions(J, v0, v1[:, :2])
        with self.assertRaisesRegex(Refusal, "EIT188_DEGENERATE_CONTRAST"):
            fixed_blocked_predictions(J, v0, v0)

    def test_rejects_rank_deficient_gain_or_offset_and_zero_J(self):
        J, v0, v1 = fixture()
        with self.assertRaisesRegex(Refusal, "EIT188_DEGENERATE_J"):
            fixed_blocked_predictions(J * 0, v0, v1)
        with self.assertRaisesRegex(Refusal, "EIT188_RANK_DEFICIENT_NUISANCE"):
            fixed_blocked_predictions(J, np.ones_like(v0), v1)
        with self.assertRaisesRegex(Refusal, "EIT188_ZERO_GAIN_TRAINING_DENOMINATOR"):
            fixed_blocked_predictions(J, np.zeros_like(v0), v1)

    def test_refuse_mutation_of_existing_output_without_network(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / "witness.json"
            output.write_text("historical unchanged")
            with patch("research.eit_blocked_prediction188.compare.download_exact",
                       side_effect=AssertionError("MUST_NOT_DOWNLOAD")):
                with self.assertRaisesRegex(Refusal, "OUTPUT_EXISTS_OR_SYMLINK"):
                    main(["--out", str(output)])
            self.assertEqual(output.read_text(), "historical unchanged")

    def test_new_path_requires_pinned_source_and_cannot_call_public_network_in_tests(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "new.json"
            with patch("research.eit_blocked_prediction188.compare.download_exact",
                       side_effect=Refusal("EXPECTED_OFFLINE")):
                with self.assertRaisesRegex(Refusal, "EXPECTED_OFFLINE"):
                    main(["--out", str(dest)])
            self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main()
