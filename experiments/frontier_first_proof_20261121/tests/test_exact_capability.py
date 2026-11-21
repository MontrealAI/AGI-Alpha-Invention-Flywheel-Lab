"""Finite correctness tests against independent enumeration and proof checks."""
from copy import deepcopy
import itertools
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "independent"))
from cover import canonical_problem, solve_cover
from verify_certificate import verify, Rejected


class ExactCapabilityTest(unittest.TestCase):
    def test_exhaustive_reference_and_independent_certificates(self):
        rng = random.Random(20261121)
        for case in range(250):
            n, m = rng.randint(1, 10), rng.randint(0, 12)
            rows = [sorted(rng.sample(range(n), rng.randint(1, n))) for _ in range(m)]
            expected = next(k for k in range(n+1)
                if any(all(set(c) & set(r) for r in rows) for c in itertools.combinations(range(n), k)))
            labels = [str(i) for i in range(n)]
            result = solve_cover(labels, rows)
            self.assertEqual(result["cardinality"], expected, case)
            self.assertTrue(verify(canonical_problem(labels, rows), result["certificate"])["accepted"])

    def test_empty_and_infeasible_are_distinct(self):
        result = solve_cover([], [])
        self.assertEqual(result["cardinality"], 0)
        self.assertTrue(verify(canonical_problem([], []), result["certificate"])["accepted"])
        self.assertEqual(solve_cover(["x"], [[]])["status"], "INFEASIBLE")

    def test_input_rejections(self):
        for labels, rows in [(["x", "x"], []), (["x"], [[True]]), (["x"], [[-1]]),
                             (["x"], [[1]]), (["x"], [[0, 0]]), ([""], [])]:
            with self.assertRaises(ValueError):
                solve_cover(labels, rows)

    def test_problem_binding_and_false_selection_rejected(self):
        p = canonical_problem(["a", "b", "c"], [[0], [1, 2]])
        cert = solve_cover(p["option_ids"], p["requirements"])["certificate"]
        altered = deepcopy(p)
        altered["option_ids"][0] = "other"
        with self.assertRaises(Rejected):
            verify(altered, cert)
        altered = deepcopy(cert)
        altered["selected"] = [1, 2]
        with self.assertRaises(Rejected):
            verify(p, altered)

    def test_false_lower_bound_rejected(self):
        p = canonical_problem(["a", "b", "c"], [[0, 1], [1, 2]])
        cert = {"schema": "frontier-min-cover-proof/v1", "problem_sha256": "",
                "optimum": 2, "selected": [0, 2], "root": 0,
                "nodes": [{"type": "packing", "rows": [0, 1]}]}
        from verify_certificate import canonical_hash
        cert["problem_sha256"] = canonical_hash(p)
        with self.assertRaises(Rejected):
            verify(p, cert)


if __name__ == "__main__":
    unittest.main()
