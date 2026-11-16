import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from engine import SpecificationError, explore, validate
from audit import AuditError, audit, apply_verified

GOOD=json.loads((ROOT/'examples'/'escrow.json').read_text())
BUG=json.loads((ROOT/'examples'/'escrow_bug.json').read_text())


class TestProofOmega(unittest.TestCase):
    def test_exact_exhaustive_proof_and_independent_audit(self):
        result=explore(GOOD)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['state_count'],4)
        self.assertEqual(result['edge_count'],3)
        self.assertEqual(audit(GOOD,result)['status'],'AUDIT_PASS')
    def test_bug_yields_counterexample(self):
        result=explore(BUG)
        self.assertEqual(result['status'],'FAIL')
        self.assertEqual(result['counterexample']['actions'],['reserve','settle'])
        self.assertIn('invariant:conservation',result['counterexample']['violations'])
    def test_forged_certificate_omitted_states_rejected(self):
        cert=explore(GOOD)
        cert['states'].pop()
        with self.assertRaises(AuditError): audit(GOOD,cert)
    def test_forged_certificate_omitted_edge_rejected(self):
        cert=explore(GOOD)
        cert['edges'].pop()
        with self.assertRaises(AuditError): audit(GOOD,cert)
    def test_sha_bound_certificate_rejects_changed_policy(self):
        cert=explore(GOOD)
        altered=copy.deepcopy(GOOD)
        altered['name']='different'
        with self.assertRaises(AuditError): audit(altered,cert)
    def test_stopping_early_must_never_pass(self):
        res=explore(GOOD,max_states=1)
        self.assertEqual(res['status'],'HOLD_LIMIT')
        with self.assertRaises(AuditError): audit(GOOD,res)
    def test_reachable_graph_enforces_actions(self):
        cert=explore(GOOD)
        first=apply_verified(GOOD,cert,GOOD['initial'],'reserve')
        self.assertEqual(first['escrow'],1)
        third=apply_verified(GOOD,cert,first,'settle')
        self.assertEqual(third['seller'],1)
        with self.assertRaises(AuditError): apply_verified(GOOD,cert,third,'settle')
    def test_uncertified_state_rejected(self):
        cert=explore(GOOD)
        state=dict(GOOD['initial']);state['seller']=1
        with self.assertRaises(AuditError): apply_verified(GOOD,cert,state,'reserve')
    def test_injection_expression_rejected(self):
        bad=copy.deepcopy(GOOD)
        bad['actions'][0]['when']=['__import__','os']
        with self.assertRaises(SpecificationError): validate(bad)
    def test_bad_type_rejected(self):
        bad=copy.deepcopy(GOOD)
        bad['initial']['buyer']=True
        with self.assertRaises(SpecificationError): validate(bad)

if __name__=='__main__': unittest.main()

# Additional compiled-executable conformance tests are imported by unittest discovery
# from a second TestCase. Only the repository-owned synthetic fixtures execute locally.
class TestBoundedBinaryConformance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import shutil
        import subprocess
        import tempfile
        if not (cc := (shutil.which('cc') or shutil.which('gcc'))):
            raise unittest.SkipTest('C compiler unavailable')
        cls.tmp = tempfile.TemporaryDirectory()
        cls.good = Path(cls.tmp.name) / 'good'
        cls.bad = Path(cls.tmp.name) / 'bad'
        src = ROOT / 'examples' / 'escrow_oracle.c'
        subprocess.run([cc, '-O2', '-o', str(cls.good), str(src)], check=True)
        subprocess.run([cc, '-DBAD_ESCROW', '-O2', '-o', str(cls.bad), str(src)], check=True)
        cls.cert = explore(GOOD)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'tmp'):
            cls.tmp.cleanup()

    def test_compiled_good_is_exact_on_all_reachable_actions(self):
        from binary_contract import binary_conformance
        result = binary_conformance(GOOD,self.cert,self.good,unsafe_local=True)
        self.assertEqual(result['status'],'PASS_BOUNDED_EXECUTABLE_CONFORMANCE')
        self.assertEqual(result['cases'],12)

    def test_compiled_bad_has_specific_witness(self):
        from binary_contract import binary_conformance
        result = binary_conformance(GOOD,self.cert,self.bad,unsafe_local=True)
        self.assertEqual(result['status'],'FAIL_MISMATCH')
        self.assertEqual(result['mismatches'][0]['request']['action'],'settle')

    def test_compiled_untrusted_no_docker_refuses(self):
        from binary_contract import binary_conformance, ContractError
        from unittest.mock import patch
        import binary_contract
        with patch.object(binary_contract.shutil,'which',return_value=None):
            with self.assertRaises(ContractError):
                binary_conformance(GOOD,self.cert,self.good)

    def test_compiled_bounded_cap_never_passes(self):
        from binary_contract import binary_conformance, ContractError
        with self.assertRaises(ContractError):
            binary_conformance(GOOD,self.cert,self.good,max_cases=1)
