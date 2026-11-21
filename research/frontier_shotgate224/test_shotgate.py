"""Independent formula and fail-closed regressions for frozen shotgate224."""
from __future__ import annotations
import itertools
import math
import unittest
import numpy as np

from shotgate import (
    checked_distribution, hellinger_squared, required_shots_necessary,
    risk_lower_bound, frame_one_shot_error, helstrom_one_shot_error
)


def exact_equal_prior_bayes_error(p, q, n):
    """Enumerate complete finite categorical sequences; no normal approximation."""
    result = 0.0
    for outcome in itertools.product(range(len(p)), repeat=n):
        pp = math.prod(p[i] for i in outcome)
        qq = math.prod(q[i] for i in outcome)
        result += min(pp, qq) / 2
    return result


class ShotGateFormulaTests(unittest.TestCase):
    def test_indistinguishable(self):
        p = np.array([.5, .5])
        self.assertEqual(hellinger_squared(p, p), 0.0)
        self.assertIsNone(required_shots_necessary(0))
        for n in (1, 2, 10**6):
            self.assertEqual(risk_lower_bound(0,n), .5)
        self.assertAlmostEqual(frame_one_shot_error(p,p), .5)

    def test_disjoint(self):
        p,q=np.array([1.,0.]),np.array([0.,1.])
        self.assertEqual(hellinger_squared(p,q),1.)
        self.assertEqual(required_shots_necessary(1),1)
        self.assertEqual(risk_lower_bound(1,1),0)
        self.assertEqual(exact_equal_prior_bayes_error(p,q,3),0)

    def test_exhaustive_small_worlds(self):
        for pp,qq in ((.75,.25),(.9,.1),(.55,.45),(.99,.01)):
            p=np.array([pp,1-pp])
            q=np.array([qq,1-qq])
            h2=hellinger_squared(p,q)
            self.assertTrue(0 < h2 < 1)
            last=1.
            for n in (1,2,3,4):
                exact=exact_equal_prior_bayes_error(p,q,n)
                bound=risk_lower_bound(h2,n)
                self.assertLessEqual(bound,exact+1e-12)
                self.assertLessEqual(bound,last+1e-12)
                last=bound
            necessary=required_shots_necessary(h2)
            self.assertGreaterEqual(necessary,1)
            if necessary > 1:
                self.assertGreater(risk_lower_bound(h2, necessary-1),
                                   .05-1e-10)

    def test_helstrom_ordinary_reference(self):
        rho=np.diag([1.,0.]).astype(complex)
        sigma=np.diag([0.,1.]).astype(complex)
        self.assertAlmostEqual(helstrom_one_shot_error(rho,sigma),0)
        rho2=np.diag([.8,.2]).astype(complex)
        sigma2=np.diag([.2,.8]).astype(complex)
        self.assertAlmostEqual(helstrom_one_shot_error(rho2,sigma2),.2)
        self.assertAlmostEqual(helstrom_one_shot_error(rho2,rho2),.5)
        # A noncommuting qubit state pair: |0> vs |+>.
        plus=np.array([[.5,.5],[.5,.5]],complex)
        expected=0.5*(1-1/math.sqrt(2))
        self.assertAlmostEqual(helstrom_one_shot_error(rho,plus),expected)

    def test_fail_closed_bad_inputs(self):
        for v in ([.2,.2],[1.0001,-.0001],[float("nan"),1],[0,0]):
            with self.assertRaises(ValueError):
                checked_distribution(v)
        for a in (0,.5,1):
            with self.assertRaises(ValueError):
                required_shots_necessary(.3,a)
        for n in (0,-1):
            with self.assertRaises(ValueError):
                risk_lower_bound(.3,n)

    def test_small_float_artifact_only(self):
        p=checked_distribution([.3,-1e-12,.7])
        self.assertAlmostEqual(float(p.sum()),1.)
        self.assertTrue(np.all(p>=0))


if __name__=="__main__":
    unittest.main()
