"""Adversarial and mathematical sanity checks for Goal Genesis Ω C_1d."""
import copy
import unittest

from research.goal_genesis_omega import c1d_verify as proof


class ExactMathTests(unittest.TestCase):
    def test_uniform_function_oracle(self):
        for n in (2,3,7,16):
            exact,info=proof.evaluate_exact([1.0]*n)
            self.assertEqual(exact,2)
            self.assertEqual(info["cells"],n)

    def test_signed_extremal_variant(self):
        val,_=proof.evaluate_exact([1.0,-1.0,1.0])
        self.assertEqual(val,18)

    def test_scale_invariance(self):
        v=[1.0,2.5,-0.25,3.0,-0.5]
        a,_=proof.evaluate_exact(v)
        b,_=proof.evaluate_exact([2*x for x in v])
        self.assertEqual(a,b)

    def test_malformed_and_forged_witnesses(self):
        for sample in ([],[1.0],[1.0,float("nan")],[1.0,-1.0],
                       [1,1],[0.0,0.0]):
            with self.subTest(sample=repr(sample)):
                with self.assertRaises(ValueError):
                    proof.evaluate_exact(sample)

    def test_minimax_gradient_matches_finite_differences(self):
        import numpy as np
        from research.goal_genesis_omega.c1d_search import smooth
        rng=np.random.default_rng(22)
        x=rng.normal(size=11)*.4
        value,grad=smooth(x,10.0)
        for i in range(len(x)):
            h=1e-6
            plus=x.copy();minus=x.copy();plus[i]+=h;minus[i]-=h
            predicted=(smooth(plus,10.0)[0]-smooth(minus,10.0)[0])/(2*h)
            self.assertLess(abs(predicted-grad[i]),1e-6)

    def test_corrupted_external_certificate_is_rejected(self):
        import tempfile
        from pathlib import Path
        from research.goal_genesis_omega.c1d_search import read_upstream
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"seed.json"
            path.write_text('{"values":[1,2,3]}')
            with self.assertRaisesRegex(ValueError,"PINNED_SOURCE_HASH_MISMATCH"):
                read_upstream(path)

    def test_claims_cannot_change_external_best(self):
        self.assertTrue(proof.BEST > 1)
        self.assertTrue(proof.BEST < 1.455)
        self.assertEqual(proof.BEST.numerator,9900630255081376929482866688)


if __name__=="__main__":
    unittest.main()
