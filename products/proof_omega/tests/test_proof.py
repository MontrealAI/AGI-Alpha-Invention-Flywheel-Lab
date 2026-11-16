import copy
import json
import tempfile
import unittest
from pathlib import Path
import z3
from products.proof_omega.checker import check,bundle,verify,load_json,Rejected

ROOT=Path(__file__).resolve().parents[1]
class ProofTests(unittest.TestCase):
    def setUp(self):
        self.c={'schema':1,'function':'f','inputs':{'x':[-10,10]},'expected':'x','output_range':[-10,10]}
    def test_examples_prove_and_bugs_fail(self):
        for name in ['fee','withdraw']:
            c=load_json(ROOT/'examples'/f'{name}.contract.json')
            self.assertEqual(check((ROOT/'examples'/f'{name}_reference.py').read_text(),c)[0]['status'],'PROVED_SCOPED')
            self.assertEqual(check((ROOT/'examples'/f'{name}_bug.py').read_text(),c)[0]['status'],'COUNTEREXAMPLE')
    def test_no_import(self):
        with self.assertRaises(Rejected):check('import os\ndef f(x): return x',self.c)
    def test_no_call(self):
        with self.assertRaises(Rejected):check('def f(x): return abs(x)',self.c)
    def test_no_side_effect(self):
        with self.assertRaises(Rejected):check('def f(x):\n x=0\n return x',self.c)
    def test_no_decorator(self):
        with self.assertRaises(Rejected):check('@evil\ndef f(x): return x',self.c)
    def test_no_defaults(self):
        with self.assertRaises(Rejected):check('def f(x=0): return x',self.c)
    def test_no_annotation(self):
        with self.assertRaises(Rejected):check('def f(x:int): return x',self.c)
    def test_no_float(self):
        with self.assertRaises(Rejected):check('def f(x): return x / 2',self.c)
    def test_no_bool_integer(self):
        with self.assertRaises(Rejected):check('def f(x): return True',self.c)
    def test_no_bool_return(self):
        with self.assertRaises(Rejected):check('def f(x): return x > 0',self.c)
    def test_no_zero_division(self):
        with self.assertRaises(Rejected):check('def f(x): return x // 0',self.c)
    def test_no_variable_division(self):
        with self.assertRaises(Rejected):check('def f(x): return x // x',self.c)
    def test_no_negative_division(self):
        with self.assertRaises(Rejected):check('def f(x): return x // -2',self.c)
    def test_empty_domain(self):
        self.c['inputs']['x']=[3,2]
        with self.assertRaises(Rejected):check('def f(x): return x',self.c)
    def test_missing_variable(self):
        with self.assertRaises(Rejected):check('def f(x): return y',self.c)
    def test_range_violation(self):
        self.c['output_range']=[0,10]
        self.assertEqual(check('def f(x): return x',self.c)[0]['status'],'COUNTEREXAMPLE')
    def test_integer_truthiness_rejected(self):
        with self.assertRaises(Rejected):check('def f(x): return x if x else 0',self.c)
    def test_negative_floor_mod_python_parity(self):
        # Only developer-authored fixtures are evaluated by Python here, never submitted source.
        for x in range(-10,11):
            for divisor in [2,3,7]:
                self.c['inputs']['x']=[x,x]
                for op, expected in [(' // ',x//divisor),(' % ',x%divisor)]:
                    self.c['expected']=str(expected)
                    self.assertEqual(check('def f(x): return x'+op+str(divisor),self.c)[0]['status'],'PROVED_SCOPED')
    def test_independent_solver_replay(self):
        result,ob=check('def f(x): return x',self.c)
        s=z3.Solver();s.from_string(ob)
        self.assertEqual(s.check(),z3.unsat)
    def test_bundle_and_forged_source(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'proof';bundle('def f(x): return x',self.c,p)
            self.assertEqual(verify(p)['status'],'PROVED_SCOPED')
            (p/'candidate.py').write_text('def f(x): return x+1')
            with self.assertRaises(Rejected):verify(p)
    def test_forged_obligation(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'proof';bundle('def f(x): return x',self.c,p)
            (p/'obligation.smt2').write_text('(assert false)\n(check-sat)')
            with self.assertRaises(Rejected):verify(p)
    def test_extra_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'proof';bundle('def f(x): return x',self.c,p);(p/'x').write_text('x')
            with self.assertRaises(Rejected):verify(p)
    def test_duplicate_json(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';p.write_text('{"a":1,"a":2}')
            with self.assertRaises(Rejected):load_json(p)
    def test_unknown_fails_closed(self):
        from unittest.mock import patch
        with patch.object(type(z3.Solver()),'check',return_value=z3.unknown),patch.object(type(z3.Solver()),'reason_unknown',return_value='timeout'):
            self.assertEqual(check('def f(x): return x',self.c)[0]['status'],'UNKNOWN')

if __name__=='__main__':unittest.main()
