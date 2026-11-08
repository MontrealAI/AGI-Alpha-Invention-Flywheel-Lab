"""Frozen boundary checks for the independently source-owned KTC decision probe."""
import unittest
import numpy as np
from research.eit_decision102.decision import (
    N_TARGETS, decisions, confusion, proxy_verdict, _diagnostic_counts
)


class EITDecision102Tests(unittest.TestCase):
    def make_rows(self):
        # Deterministic 21x8 with positive and negative cases for each class.
        return [tuple((i+k) % 2 for k in range(8)) for i in range(N_TARGETS)]

    def test_eight_fixed_quadrant_labels(self):
        a = np.zeros((256, 256), dtype=np.float64)
        a[0:5, 0:164] = 1  # exactly 820 label-1 pixels in top-left? No: 5x164 crosses 128
        a[:, :] = 0
        a[0:5, 0:128] = 1
        a[5:7, 0:90] = 1  # 640+180 = 820 of 16384
        a[128:138, 128:256] = 2
        self.assertEqual(decisions(a), (1, 0, 0, 0, 0, 0, 0, 1))

    def test_one_pixel_below_threshold(self):
        a = np.zeros((256, 256))
        a[:5, :128] = 1
        a[5, :179 if False else 128] = 1 # overwrite to construct explicit 819
        a[5:7, :] = 0
        a[5, :128] = 1
        a[6, :51] = 1  # 640+128+51=819
        self.assertEqual(decisions(a)[0], 0)

    def test_invalid_image_and_boolean_refusal(self):
        good = np.zeros((256, 256))
        for a in (np.zeros((32, 32)), np.full((256, 256), float("nan")),
                  np.full((256, 256), 3), np.zeros((256, 256), dtype=bool)):
            with self.assertRaises(ValueError):
                decisions(a)
        self.assertEqual(len(decisions(good)), 8)

    def test_exact_source_binary_denominator(self):
        truth = self.make_rows()
        same = confusion(truth, truth)
        self.assertEqual(same["denominator"], 168)
        self.assertEqual(same["correct"], 168)
        self.assertEqual(same["macro_balanced_accuracy"], 1.0)
        self.assertTrue(same["informative_frozen_task"])
        self.assertTrue(all(x["positive"] >= 8 and x["negative"] >= 8
                            for x in same["by_label"]))

    def test_foreground_and_background_errors(self):
        truth = self.make_rows()
        guesses = [tuple(1-v for v in row) for row in truth]
        result = confusion(truth, guesses)
        self.assertEqual(result["correct"], 0)
        self.assertEqual(result["macro_balanced_accuracy"], 0.0)
        self.assertEqual(sum(x["FP"]+x["FN"] for x in result["by_label"]), 168)

    def test_uninformative_proxy_abstains(self):
        truth = [tuple([0]*8) for _ in range(21)]
        stats = confusion(truth, truth)
        self.assertFalse(stats["informative_frozen_task"])
        self.assertIsNone(stats["macro_balanced_accuracy"])
        self.assertEqual(proxy_verdict({"full76":stats,"direct40":stats,
                                        "impute40":stats,"no_measure_absent":stats,
                                        "no_measure_present":stats})[0],
                         "UNINFORMATIVE_FROZEN_TASK_NO_DEPLOY")

    def test_zero_measure_has_no_artificial_skill(self):
        truth = self.make_rows()
        rows = [{"truth":r,"full76":r,"direct40":r,"impute40":r} for r in truth]
        stats = _diagnostic_counts(rows)
        self.assertAlmostEqual(stats["no_measure_absent"]["macro_balanced_accuracy"], .5)
        self.assertAlmostEqual(stats["no_measure_present"]["macro_balanced_accuracy"], .5)
        self.assertEqual(stats["direct40"]["disagreements_with_full76"], 0)
        self.assertEqual(proxy_verdict(stats)[0],
                         "CONDITIONAL_EXPOSED_PROXY_SCREEN_PASS_NO_DEPLOY")

    def test_fail_closed_on_malformed_denominators(self):
        t = self.make_rows()
        for truth,pred in ((t[:-1], t[:-1]), (t, t[:-1]),
                           (t, [tuple([0]*7) for _ in t]),
                           (t, [tuple([False]*8) for _ in t]),
                           (t, [tuple([2]*8) for _ in t])):
            with self.assertRaises(ValueError):
                confusion(truth, pred)

    def test_no_retuning_for_negative_strategy(self):
        t = self.make_rows()
        pred = [tuple([0]*8) for _ in t]
        stats = _diagnostic_counts([
            {"truth":r,"full76":r,"direct40":v,"impute40":v}
            for r,v in zip(t,pred)])
        self.assertEqual(proxy_verdict(stats), ("REJECT_PROXY_SCREEN_NO_DEPLOY", []))

    def test_held_out_task_is_always_noncommercial(self):
        # The acceptance function cannot book revenue, approve devices or
        # change financial identity; it returns a bounded research verdict only.
        stats = _diagnostic_counts([
            {"truth":r,"full76":r,"direct40":r,"impute40":r}
            for r in self.make_rows()])
        verdict, eligible = proxy_verdict(stats)
        self.assertTrue(verdict.endswith("NO_DEPLOY"))
        self.assertEqual(sorted(eligible), ["direct40", "impute40"])


if __name__ == "__main__":
    unittest.main()
