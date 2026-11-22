import copy,json,tempfile,unittest
from pathlib import Path
from .construct import produce,learning_loop
from .verify import verify,validate_request
from .sqlite_referee import check
from .service import prepare_manifest,load_contracts
ROOT=Path(__file__).resolve().parents[1]

class ContractTests(unittest.TestCase):
 def request(self): return {'id':'dev-K1','kind':'preparation','family':'both_capabilities','samples':2,'components':2,'quantity':4}
 def test_complete_output(self):
  r=self.request();self.assertTrue(verify(r,produce(r))['accepted'])
 def test_duplicate_component(self):
  r=self.request();a=produce(r);a['rows'][1]=copy.deepcopy(a['rows'][0]);self.assertFalse(verify(r,a)['accepted'])
 def test_wrong_quantity(self):
  r=self.request();a=produce(r);a['rows'][0]['quantity']+=1;self.assertFalse(verify(r,a)['accepted'])
 def test_changed_request_identity(self):
  r=self.request();a=produce(r);a['id']='different';self.assertFalse(verify(r,a)['accepted'])
 def test_incomplete_samples(self):
  r=self.request();a=produce(r);a['rows'].pop();self.assertFalse(verify(r,a)['accepted'])
 def test_wrong_trace_response(self):
  r=self.request();a=produce(r);a['rows'][0]['trace'][0]['response']='unknown';self.assertFalse(verify(r,a)['accepted'])
 def test_unsupported_response_refused(self):
  r={'id':'nuisance','kind':'characterization','family':'both_capabilities','hidden_threshold':31,'response_model':'nonmonotone'};self.assertFalse(verify(r,produce(r))['accepted'])
 def test_new_hypothesis_and_refusal(self):
  p,trace=learning_loop('stale_readback','ordinary_equal_content_controller');self.assertIsNone(p['policy']);self.assertTrue(any(x['stage']=='expand_hypothesis_space' for x in trace))
 def test_independent_sqlite_referee(self): self.assertTrue(check()['expected_match'])
 def test_existing_calibration_not_mutated(self):
  r=self.request();before=copy.deepcopy(r);produce(r);self.assertEqual(r,before)
 def test_incompatible_retention_refused(self):
  with self.assertRaises(ValueError): produce(self.request(),retained={'family':'reliable_readback','policy':'read_before_retry'})
 def test_ordinary_equal_information(self):
  r=self.request();a=produce(r,'observation_selected_controller');b=produce(r,'ordinary_equal_content_controller');self.assertEqual(a['output'],b['output']);self.assertEqual(a['rows'],b['rows'])
 def test_manifest_binds_request_and_arm_namespace(self):
  m=prepare_manifest(ROOT,[{'id':'dev-K1','delivery_path':'enterprise078/deliveries/test/dev.json'}]);self.assertIn('dev-K1',load_contracts(ROOT,m));m['jobs'][0]['request']['quantity']+=1
  with self.assertRaises(ValueError): load_contracts(ROOT,m)
 def test_duplicate_delivery_refused(self):
  with self.assertRaises(ValueError): prepare_manifest(ROOT,[{'id':'dev-K1','delivery_path':'enterprise078/deliveries/test/a.json'},{'id':'gateway-K1','delivery_path':'enterprise078/deliveries/test/a.json'}])
if __name__=='__main__': unittest.main()
