"""Independent adversarial controls for registered FRAMECOST226 math and source."""
from __future__ import annotations

import itertools
import math
import sys
from pathlib import Path
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
from evaluate import (TARGET, NOISE_LEVELS, bounded_n, pair_stats,
    response_noise, validate_probabilities, verify_pins)


def exact_equal_prior_error(p, q, n):
    outcomes = list(itertools.product(range(len(p)),repeat=n))
    return 0.5*sum(min(math.prod(p[i] for i in sample),
                       math.prod(q[i] for i in sample)) for sample in outcomes)


class FrozenMath(unittest.TestCase):
    def test_pinned_owner_source_and_protocol(self):
        self.assertEqual(len(verify_pins()),5)
        self.assertEqual(NOISE_LEVELS,(0.0,0.01,0.05))
        self.assertEqual(TARGET,0.05)

    def test_invalid_distributions_fail(self):
        for p,q in [([0.1,0.1],[0.5,0.5]),
                    ([-0.1,1.1],[0.5,0.5]),
                    ([float("nan"),0],[0.5,0.5]),
                    ([1,0],[1])]:
            with self.subTest(p=p,q=q), self.assertRaises(ValueError):
                validate_probabilities(p,q)
        for value in (-0.01,1.0,float("nan")):
            with self.subTest(epsilon=value),self.assertRaises(ValueError):
                response_noise(np.array([1.,0.]),value)

    def test_disjoint_and_identical_do_not_invent_shots(self):
        certain=pair_stats([1,0],[0,1],0.0,0.0)
        self.assertEqual((certain["status"],certain["necessary_shots"],
                          certain["sufficient_shots"]),("finite",1,1))
        identical=pair_stats([.3,.7],[.3,.7],.5,0.0)
        self.assertTrue(identical["status"].startswith("indistinguishable"))
        self.assertIsNone(identical["sufficient_shots"])
        self.assertIsNone(identical["necessary_shots"])

    def test_bound_is_proven_for_exact_enumerated_small_binary_world(self):
        p=[.95,.05]
        q=[.05,.95]
        r=pair_stats(p,q,.05,0.0)
        self.assertEqual(r["status"],"finite")
        nlo,nhi=r["necessary_shots"],r["sufficient_shots"]
        self.assertTrue(1 <= nlo <= nhi <= 5)
        for n in range(1,nhi+1):
            exact=exact_equal_prior_error(p,q,n)
            self.assertGreaterEqual(exact+1e-12, (1-math.sqrt(1-r["bc"]**(2*n)))/2)
            self.assertLessEqual(exact, r["bc"]**n/2+1e-12)
        self.assertLessEqual(exact_equal_prior_error(p,q,nhi), TARGET+1e-12)
        if nlo>1:
            self.assertGreater(exact_equal_prior_error(p,q,nlo-1), TARGET-1e-12)

    def test_uniform_reporting_noise_never_makes_pair_appear_easier(self):
        p=np.array([.999,.001,0.,0.])
        q=np.array([.001,.999,0.,0.])
        series=[pair_stats(p,q,0.001,eps) for eps in NOISE_LEVELS]
        self.assertTrue(all(series[i+1]["tv"]<=series[i]["tv"]+1e-12 for i in (0,1)))
        self.assertTrue(all(series[i+1]["bc"]>=series[i]["bc"]-1e-12 for i in (0,1)))
        self.assertTrue(all(series[i+1]["sufficient_shots"]>=series[i]["sufficient_shots"] for i in (0,1)))

    def test_cannot_claim_better_than_ideal_helstrom(self):
        with self.assertRaises(AssertionError):
            pair_stats([1.,0.],[0.,1.],0.49,0.0)


    def test_sufficient_bound_refuses_near_integer_optimism(self):
        # BC just above sqrt(0.1) means two shots DO NOT satisfy the
        # sufficient 5% error certificate: ceil(log(0.1)/log(BC)) = 3.
        target_bc=math.sqrt(0.1)*(1+1e-12)
        x=(1+math.sqrt(1-target_bc**2))/2
        r=pair_stats([x,1-x],[1-x,x],0.0,0.0)
        self.assertEqual(r["status"],"finite")
        self.assertGreaterEqual(r["sufficient_shots"],3)
        self.assertLessEqual(r["bc"]**r["sufficient_shots"],0.1+1e-14)

    def test_no_optimistic_count_for_numerically_unresolved_pair(self):
        r=pair_stats([.5+1e-11,.5-1e-11],[.5-1e-11,.5+1e-11],.499999,0)
        self.assertIn("indistinguishable",r["status"])
        self.assertIsNone(r["necessary_shots"])

if __name__=="__main__":
    unittest.main()
