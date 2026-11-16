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

    def test_claims_cannot_change_external_best(self):
        self.assertTrue(proof.BEST > 1)
        self.assertTrue(proof.BEST < 1.46)


if __name__=="__main__":
    unittest.main()
