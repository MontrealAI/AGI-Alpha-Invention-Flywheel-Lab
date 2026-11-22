"""Offline, independent adversarial tests for the pre-frozen EIT237 physical-source protocol."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import unittest

import numpy as np

from research.eit_chest_sparse237.probe import (
    COLS, FIXED, HELPER_BLOB, ROWS, SOURCE_SHA, SPARSE_K, Refusal,
    choose_greedy_rows, classify, evaluate, validate_matrices,
)


def fixture():
    """A clearly labeled SYNTHETIC regression, never counted as real physical data."""
    data = {}
    for idx, label in enumerate(("a", "b", "c", "d")):
        for rep in (1, 2):
            a = np.zeros((ROWS, COLS), dtype=np.float64)
            a[7, :] = idx * 10 + (0.01 if rep == 2 else 0)
            data[(label, rep)] = a
    return data


class Sparse237Tests(unittest.TestCase):
    def test_registration_shape_and_source_identity(self):
        self.assertEqual(ROWS, 79)
        self.assertEqual(COLS, 16)
        self.assertEqual(SPARSE_K, 8)
        self.assertEqual(len(FIXED), 8)
        self.assertEqual(len(SOURCE_SHA), 64)
        self.assertEqual(len(HELPER_BLOB), 40)

    def test_two_fold_synthetic_example_compares_four_policies(self):
        out = evaluate(fixture())
        self.assertEqual(out["arms"]["greedy8"]["correct"], 8)
        self.assertEqual(out["arms"]["full79"]["correct"], 8)
        self.assertTrue(out["registered_sparse_criterion_met"])
        self.assertEqual(set(out["arms"]),
                         {"greedy8", "full79", "fixed8", "random8"})
        self.assertLess(out["arms"]["fixed8"]["correct"], 8)
        for arm in out["arms"].values():
            self.assertEqual(arm["denominator"], 8)
            self.assertEqual(len(arm["all_predictions"]), 8)

    def test_greedy_uses_only_train_and_fixed_tie_order(self):
        a = fixture()
        train = {x: a[(x, 1)] for x in ("a", "b", "c", "d")}
        selected = choose_greedy_rows(train)
        self.assertIn(7, selected)
        self.assertEqual(len(set(selected)), 8)
        self.assertEqual(selected, tuple(sorted(selected)))
        for x in ("a", "b", "c", "d"):
            a[(x, 2)] = np.full((ROWS, COLS), 10**3 + len(x), dtype=np.float64)
        self.assertEqual(selected, choose_greedy_rows(train))
        self.assertEqual(selected,
                         choose_greedy_rows({x: a[(x, 1)] for x in train}))

    def test_tied_observations_fail_instead_of_fabricating_classification(self):
        a = fixture()
        for key in a:
            a[key] = np.zeros((ROWS, COLS), dtype=np.float64)
        out = evaluate(a)
        self.assertFalse(out["registered_sparse_criterion_met"])
        self.assertEqual(out["arms"]["greedy8"]["correct"], 2)
        self.assertEqual(out["arms"]["greedy8"]["minimum_squared_distance_margin"], 0)
        self.assertEqual(out["selected_patterns_by_fold"]["1_to_2"]["greedy8"],
                         list(range(8)))

    def test_missing_extra_and_invalid_repetition_fail_closed(self):
        for k in ("missing", "extra", "bad_repeat"):
            a = fixture()
            if k == "missing":
                del a[("a", 2)]
            elif k == "extra":
                a[("x", 1)] = a[("a", 1)].copy()
            else:
                a[("a", 3)] = a.pop(("a", 2))
            with self.subTest(k=k), self.assertRaisesRegex(
                    Refusal, "REQUIRED"):
                validate_matrices(a)

    def test_nan_complex_and_shape_refuse(self):
        for k in ("nan", "inf", "complex", "shape"):
            a = fixture()
            if k == "nan":
                a[("a", 1)][0, 0] = float("nan")
            elif k == "inf":
                a[("a", 1)][0, 0] = float("inf")
            elif k == "complex":
                a[("a", 1)] = a[("a", 1)].astype(np.complex128)
            else:
                a[("a", 1)] = a[("a", 1)][:78]
            with self.subTest(k=k), self.assertRaisesRegex(
                    Refusal, "ARRAY_INVALID"):
                validate_matrices(a)

    def test_direct_classification_ties_choose_sorted_name_and_zero_margin(self):
        a = np.zeros((ROWS, COLS))
        ref = {"z": a, "a": a.copy(), "t": a.copy(), "b": a.copy()}
        predicted, margin = classify(ref, a, (0, 1))
        self.assertEqual(predicted, "a")
        self.assertEqual(margin, 0.0)

    def test_repeated_evaluation_stable_frozen_rows_and_predictions(self):
        a = fixture()
        self.assertEqual(evaluate(a), evaluate(copy.deepcopy(a)))

    def test_greedy_not_hardcoded_nominal_row(self):
        a = fixture()
        for v in a.values():
            v[3, :] = v[7, :]
            v[7, :] = 0
        out = evaluate(a)
        self.assertIn(3, out["selected_patterns_by_fold"]["1_to_2"]["greedy8"])
        self.assertTrue(out["registered_sparse_criterion_met"])

    def test_protocol_prior_to_implementation_has_complete_denominator(self):
        content = Path("research/eit_chest_sparse237/PROTOCOL.md").read_text()
        self.assertIn("prior to EIT237 implementation", content)
        self.assertIn("all eight", content.lower())
        self.assertIn("NO BID / NO DEPLOY", content)
        self.assertIn("Random(237)", content)
        self.assertIn(SOURCE_SHA, content)
        self.assertIn("four", content.lower())


if __name__ == "__main__":
    unittest.main()
