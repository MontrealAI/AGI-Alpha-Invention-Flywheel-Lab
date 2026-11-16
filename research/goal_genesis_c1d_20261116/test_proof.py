"""Adversarial tests of two independent integer proof checkers."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from verify_exact import verify as big_int_verify, INCUMBENT as incumbent_a
from verify_ntt import verify as ntt_verify, INCUMBENT as incumbent_b, square_mod, all_coeffs_ntt

DIR=Path(__file__).resolve().parent

class ExactC1DTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.certificate=json.loads((DIR/'certificate4800.json').read_text())

    def test_two_independent_full_certificate_verifiers_agree(self):
        a=big_int_verify(self.certificate)
        b=ntt_verify(self.certificate)
        self.assertEqual(a['new_bound_num']+'/'+a['new_bound_den'],b['fraction'])
        self.assertEqual(a['all_knot_coefficients'],b['knots'])
        self.assertEqual(a['max_knot'],b['max_knot'])
        self.assertLess(float(a['new_bound_decimal']),float(a['incumbent_decimal']))
        self.assertEqual(incumbent_a,incumbent_b)

    def test_simple_exact_signed_convolutions(self):
        cases=([2,3],[3,-1,2],[-2,0,3,0,1],[1]*16,[0,4,0,0,-1])
        for w in cases:
            direct=[sum(w[i]*w[k-i] for i in range(len(w)) if 0<=k-i<len(w))
                    for k in range(2*len(w)-1)]
            from verify_exact import conv_kronecker
            a,_=conv_kronecker(w)
            b=all_coeffs_ntt(w)
            self.assertEqual(direct,a)
            self.assertEqual(direct,b)

    def test_tamper_claimed_numerator_rejected(self):
        d=copy.deepcopy(self.certificate);d['exact_num']-=1
        for ver in (big_int_verify,ntt_verify):
            with self.subTest(ver=ver.__module__),self.assertRaises(ValueError):ver(d)

    def test_tamper_unreported_coefficient_rejected(self):
        d=copy.deepcopy(self.certificate);d['weights_int'][173]+=3000
        for ver in (big_int_verify,ntt_verify):
            with self.subTest(ver=ver.__module__),self.assertRaises(ValueError):ver(d)

    def test_tamper_maximizer_and_peak_rejected(self):
        for key in ['max_knot','max_abs_coefficient']:
            d=copy.deepcopy(self.certificate);d[key]+=1
            for ver in (big_int_verify,ntt_verify):
                with self.subTest(key=key,ver=ver.__module__),self.assertRaises(ValueError):ver(d)

    def test_wrong_length_rejected(self):
        d=copy.deepcopy(self.certificate);d['n']+=1
        for ver in (big_int_verify,ntt_verify):
            with self.subTest(ver=ver.__module__),self.assertRaises(ValueError):ver(d)

    def test_boolean_fraction_and_zero_rejected(self):
        for bad in (True,3.5,'3',None):
            d=copy.deepcopy(self.certificate);d['weights_int'][0]=bad
            for ver in (big_int_verify,ntt_verify):
                with self.subTest(ver=ver.__module__,bad=bad),self.assertRaises(ValueError):ver(d)
        d=copy.deepcopy(self.certificate);d['weights_int']=[0]*d['n']
        for ver in (big_int_verify,ntt_verify):
            with self.subTest(ver=ver.__module__),self.assertRaises(ValueError):ver(d)

    def test_trivial_nonimproving_case_rejected(self):
        d=copy.deepcopy(self.certificate)
        d['weights_int']=[1]*d['n']
        d['exact_num']=None;d['exact_den']=None
        d['max_knot']=None;d['max_abs_coefficient']=None
        for ver in (big_int_verify,ntt_verify):
            with self.subTest(ver=ver.__module__),self.assertRaises(ValueError):ver(d)

    def test_independent_standard_library_invocation(self):
        for script in ('verify_exact.py','verify_ntt.py'):
            p=subprocess.run([sys.executable,'-S',str(DIR/script),str(DIR/'certificate4800.json')],
              text=True,capture_output=True,check=False)
            self.assertEqual(p.returncode,0,script+'\n'+p.stderr)
            self.assertIn('PASS_',p.stdout)

if __name__=='__main__':unittest.main()
