"""EIT184 frozen synthetic/negative controls (not real physical confirmations)."""
import unittest
import numpy as np

from research.eit_physical_control183.control import SHAPE, Refusal
from research.eit_nuisance184.control import nuisance_control


class EIT184ControlTests(unittest.TestCase):
    def setUp(self):
        self.x = np.linspace(-0.9, 0.9, np.prod(SHAPE), dtype=float).reshape(SHAPE)
        self.i = np.ones(SHAPE, dtype=float)

    def analyze(self, y):
        return nuisance_control(self.i, self.x, self.i.copy(), y)

    def test_exact_gain_only_explanation(self):
        v = self.analyze(1.3 * self.x)
        self.assertLess(v["all_data_gain_rms"], 1e-13)
        self.assertLess(v["leave_column_out_gain_rms"], 1e-13)
        self.assertAlmostEqual(v["all_data_gain_coefficient"], 1.3)

    def test_exact_gain_and_offset_explanation(self):
        v = self.analyze(1.25 * self.x + 0.03)
        self.assertLess(v["all_data_gain_offset_rms"], 1e-13)
        self.assertLess(v["leave_column_out_gain_offset_rms"], 1e-13)
        self.assertAlmostEqual(v["all_data_affine_gain"], 1.25)
        self.assertAlmostEqual(v["all_data_affine_offset"], 0.03)

    def test_fold_drift_not_mistaken_for_in_sample_fit(self):
        y = 1.25 * self.x + 0.03
        y[:, 0] += 0.1
        v = self.analyze(y)
        self.assertGreater(v["leave_column_out_gain_offset_rms"],
                           v["all_data_gain_offset_rms"])
        self.assertEqual(v["held_out_columns_once_each"], list(range(16)))

    def test_original_raw_comparator_uses_all_readings(self):
        y = self.x.copy()
        y[0, 0] += 0.16
        v = self.analyze(y)
        self.assertAlmostEqual(v["observed_raw_rms"], 0.16 / np.sqrt(1264))
        self.assertEqual(v["readings_per_case"], 1264)

    def test_finite_original_contrast_required(self):
        with self.assertRaisesRegex(Refusal, "NO_FINITE_NONZERO_CONTRAST"):
            self.analyze(self.x.copy())

    def test_zero_gain_design_refused(self):
        with self.assertRaisesRegex(Refusal, "DEGENERATE_NUISANCE_DESIGN"):
            nuisance_control(self.i, np.zeros(SHAPE), self.i, np.ones(SHAPE))

    def test_constant_baseline_affine_rank_refused(self):
        with self.assertRaisesRegex(Refusal, "DEGENERATE_NUISANCE_DESIGN"):
            nuisance_control(self.i, np.ones(SHAPE), self.i, np.ones(SHAPE) * 1.2)

    def test_mismatched_current_refused(self):
        i2 = self.i.copy()
        i2[5, 3] += 1
        with self.assertRaisesRegex(Refusal, "EXCITATIONS_NOT_IDENTICAL"):
            nuisance_control(self.i, self.x, i2, self.x + 0.1)

    def test_nonfinite_voltage_refused(self):
        y = self.x.copy()
        y[1, 7] = np.nan
        with self.assertRaisesRegex(Refusal, "INCOMPATIBLE_PAIR_ARRAY"):
            self.analyze(y)

    def test_wrong_shape_refused(self):
        with self.assertRaisesRegex(Refusal, "INCOMPATIBLE_PAIR_ARRAY"):
            nuisance_control(self.i[:, :15], self.x, self.i, self.x + 0.1)


if __name__ == "__main__":
    unittest.main()
