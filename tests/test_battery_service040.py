# Generic historical suites lack the separately pinned physics environment.
# The mandatory isolated campaign step requires all 14 battery tests, no skips.
import importlib.util
import os
import unittest
if importlib.util.find_spec('pybamm') is None:
    if os.environ.get('BATTERY_QUALIFICATION_REQUIRED') == '1':
        raise ImportError('MANDATORY_BATTERY_DEPENDENCY_MISSING')
    raise unittest.SkipTest('Battery physics/native tests run in mandatory isolated campaign environment')
import copy
import unittest
from battery_service.physics import SCHEMA,validate_request,validate_policy,evaluate,check_trace,independent_check,useful_digest,digest
R={'schema':SCHEMA,'parameter_set':'Ai2020','temperature_K':308.15,'initial_soc':.1,'target_soc':.8,'maximum_seconds':1800,'maximum_current_A':8,'maximum_voltage_V':4.2,'maximum_temperature_K':313.15,'minimum_anode_potential_V':.02}
class BatteryService(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.out=evaluate(R,{'kind':'anode','current_A':4})
 def test_actual_independent_physics(self):self.assertTrue(independent_check(R,self.out)['accepted'])
 def test_trace_tamper_rejected(self):
  o=copy.deepcopy(self.out);o['trace']['voltage_V'][0]+=1
  with self.assertRaisesRegex(ValueError,'BINDING'):check_trace(R,o)
 def test_resealed_fake_physics_rejected(self):
  o=copy.deepcopy(self.out);o['trace']['voltage_V'][10]-=.1;o['trace_sha256']=digest(o['trace'])
  with self.assertRaisesRegex(ValueError,'INDEPENDENT_(TRACE|PHYSICS_REPLAY)_CHANGED'):independent_check(R,o)
 def test_forged_nominal_capacity_rejected(self):
  o=copy.deepcopy(self.out);o['nominal_capacity_Ah']*=.1
  with self.assertRaisesRegex(ValueError,'CAPACITY_CHANGED'):check_trace(R,o)
 def test_no_free_topup(self):
  r={**R,'maximum_seconds':100};o=copy.deepcopy(self.out);o['request_sha256']=digest(r)
  self.assertIn('FULL_CHARGE_TIME_EXCEEDED',check_trace(r,o)['failures'])
 def test_post_target_tail_is_not_free_or_ignored(self):
  o=copy.deepcopy(self.out)
  for k,values in o['trace'].items():values.append(values[-1]+(60 if k=='seconds' else 0))
  o['trace_sha256']=digest(o['trace'])
  self.assertIn('POST_TARGET_EXECUTION',check_trace(R,o)['failures'])
 def test_resources_not_useful_output(self):
  o=copy.deepcopy(self.out);o['resources']['wall_seconds']+=100
  self.assertEqual(useful_digest(o),useful_digest(self.out))
 def test_model_dependency_not_interchangeable(self):
  o=copy.deepcopy(self.out);o['pybamm_version']='other'
  with self.assertRaisesRegex(ValueError,'DEPENDENCY'):check_trace(R,o)
 def test_request_and_policy_are_data_not_callbacks(self):
  with self.assertRaises(ValueError):validate_request({**R,'private_callback':'x'})
  with self.assertRaises(ValueError):validate_policy({'kind':'exec','code':'pass'})
  with self.assertRaises(ValueError):validate_policy({'kind':'cccv','current_A':float('nan')})
if __name__=='__main__':unittest.main()
