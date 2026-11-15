"""EIT182: frozen machine-precision falsifier; no public data fetching or history rewriting."""
import unittest
import numpy as np
from research.eit_repeat180 import analyze_arrays


class EIT182PrecisionControls(unittest.TestCase):
    def setUp(self):
        # Same sample geometry as immutable EIT180 original failed controls.
        self.x = np.arange(36, dtype=float).reshape(12, 3) / 5. + 1.
        self.currents = np.ones_like(self.x)

    def evaluate(self, x, y):
        return analyze_arrays(self.currents, self.currents, x, y)

    def test_01_ordinary_global_gain_roundoff_is_not_incremental_structure(self):
        x = self.x
        r = self.evaluate(x, 1.7 * x)
        self.assertEqual(r["ordinary_best_name"], "O1_global_gain")
        self.assertEqual(r["decision"], "REJECT_INCREMENTAL_STRUCTURE")
        self.assertTrue(r["ordinary_at_machine_precision"])
        self.assertLessEqual(r["models"]["O1_global_gain"]["holdout"]["rms"],
                             r["ordinary_precision_floor"])

    def test_02_ordinary_global_affine_roundoff_is_not_incremental_structure(self):
        x = self.x
        r = self.evaluate(x, 1.3 * x + 7.)
        self.assertEqual(r["ordinary_best_name"], "O2_global_affine")
        self.assertEqual(r["decision"], "REJECT_INCREMENTAL_STRUCTURE")
        self.assertTrue(r["ordinary_at_machine_precision"])
        self.assertLessEqual(r["models"]["O2_global_affine"]["holdout"]["rms"],
                             r["ordinary_precision_floor"])

    def test_03_gain_roundoff_guard_is_scale_relative_in_both_directions(self):
        for factor in (1.e-9, 1.e9):
            with self.subTest(factor=factor):
                x = self.x * factor
                r = self.evaluate(x, 1.7*x)
                self.assertEqual(r["decision"], "REJECT_INCREMENTAL_STRUCTURE")
                self.assertTrue(r["ordinary_at_machine_precision"])
                self.assertGreater(r["ordinary_precision_floor"], 0.)

    def test_04_actual_channel_structure_still_detected(self):
        x = self.x
        y = x * np.array([0.5, 1.0, 1.7])[None, :] + np.array([3., -2., 5.])[None, :]
        r = self.evaluate(x, y)
        self.assertEqual(r["decision"], "CONDITIONAL_REPEAT_STRUCTURE_ONLY")
        self.assertFalse(r["ordinary_at_machine_precision"])
        self.assertGreater(r["models"][r["ordinary_best_name"]]["holdout"]["rms"],
                           r["ordinary_precision_floor"])
        self.assertGreaterEqual(r["incremental_heldout_rms_reduction_over_best_ordinary"], .10)


if __name__ == "__main__":
    unittest.main()
