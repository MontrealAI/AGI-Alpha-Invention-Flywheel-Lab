"""Independent exhaustive small-population oracle and adversarial input tests."""
import itertools
from fractions import Fraction
import unittest
from audit_sampling import detection_probability, minimum_sample, evidence_table


def independent_oracle(n, k, q):
    """Enumerate every equally likely q-subset, without using the formula."""
    picked = list(itertools.combinations(range(n), q))
    detected = sum(bool(set(sample) & set(range(k))) for sample in picked)
    return Fraction(detected, len(picked))


class AuditMathTests(unittest.TestCase):
    def test_independent_exact_oracle_all_small_populations(self):
        for n in range(1, 9):
            for k in range(n + 1):
                for q in range(n + 1):
                    with self.subTest(n=n, k=k, q=q):
                        self.assertEqual(detection_probability(n, k, q), independent_oracle(n, k, q))

    def test_binary_search_minimality(self):
        for n in (1, 2, 7, 31):
            for k in range(n + 1):
                for goal in (Fraction(0), Fraction(1, 10), Fraction(1, 2), Fraction(99, 100), Fraction(1)):
                    with self.subTest(n=n, k=k, goal=goal):
                        q = minimum_sample(n, k, goal)
                        if q is None:
                            self.assertEqual(k, 0)
                            self.assertGreater(goal, 0)
                        else:
                            self.assertGreaterEqual(detection_probability(n, k, q), goal)
                            if q:
                                self.assertLess(detection_probability(n, k, q-1), goal)

    def test_disclosed_large_cases(self):
        values = {r["substituted"]: r["audit_count"] for r in evidence_table()["rows"]}
        self.assertEqual(values, {1: 9900, 10: 3689, 100: 448, 500: 90, 1000: 44})

    def test_zero_cheating_cannot_be_detected(self):
        self.assertIsNone(minimum_sample(10000, 0, Fraction(1, 2)))
        self.assertEqual(detection_probability(100, 0, 100), Fraction(0))

    def test_adversarial_inputs_rejected(self):
        for args in ((0,0,0),(4,5,0),(4,0,5),(-1,0,0),(2,-1,0),(True,1,1)):
            with self.subTest(args=args), self.assertRaises((ValueError,TypeError)):
                detection_probability(*args)
        with self.assertRaises(TypeError):
            minimum_sample(10, 2, .99)
        with self.assertRaises(ValueError):
            minimum_sample(10, 2, Fraction(101,100))


if __name__ == "__main__":
    unittest.main()
