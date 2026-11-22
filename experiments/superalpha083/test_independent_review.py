"""Fast, fail-closed unit tests. Run: python -m unittest -v test_independent_review.py"""
import json
from pathlib import Path
import subprocess
import sys
import unittest

import independent_review as review

ROOT = Path(__file__).resolve().parent


class IndependentVerifierTests(unittest.TestCase):
    def test_field_arithmetic(self):
        self.assertEqual(review.field_self_test()["independent_product_cross_checks"], 65536)
        self.assertEqual(review.polynomial_mul(0x80, 2), 0x1D)

    def test_exact_subset_ranks_for_cauchy_mds_code(self):
        identity = [[int(i == j) for j in range(8)] for i in range(8)]
        parity = [[review.INV[i ^ (16 + j)] for i in range(8)] for j in range(6)]
        ranks = review.subset_ranks(identity + parity)
        self.assertEqual(ranks, [min(mask.bit_count(), 8) for mask in range(1 << 14)])
        minimum, _ = review.independent_min_helpers(ranks)
        self.assertEqual(minimum, [8] * 14)

    def test_nonbinary_span_coefficients(self):
        rows = [[2, 0, 0, 0, 0, 0, 0, 0], [1, 3, 0, 0, 0, 0, 0, 0]]
        target = [review.MUL[5][2] ^ review.MUL[7][1], review.MUL[7][3], 0, 0, 0, 0, 0, 0]
        self.assertEqual(review.linear_combination(rows, target), [5, 7])
        with self.assertRaises(ValueError):
            review.linear_combination(rows, [0, 0, 1, 0, 0, 0, 0, 0])

    def test_seven_corruptions_fail_closed(self):
        original = json.loads((ROOT / "RESULT.json").read_text())
        tests = review.mutation_tests(ROOT, original)
        self.assertTrue(tests["passed"])
        self.assertEqual(tests["test_count"], 7)

    def test_python_optimization_cannot_disable_validation(self):
        result = subprocess.run([sys.executable, "-O", str(ROOT / "independent_review.py")],
                                capture_output=True, text=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("validation assertions are required", result.stderr)


if __name__ == "__main__":
    unittest.main()
