import copy,math,unittest
from .instrument import analyze,compile_design,session
from .forward import make_case,voltages
from .check import check_prediction
class Tests(unittest.TestCase):
 def obs(self):return make_case('both','noise',0,97000,[.001,-.001,.0005,-.0005])
 def test_forward_matches_independent_series_law(self):
  for r in (2.,10.,31.):
   for c in (1.,4.):
    for f in (.3,.5,.7):
     v2,v4,e=voltages(r,c,f,.001)
     self.assertAlmostEqual(v2,.001*(r+c),places=12);self.assertAlmostEqual(v4,.001*r*f,places=12);self.assertLess(e,1e-12)
 def test_classification_and_bounds(self):
  c=self.obs();p=analyze(c['observation']);self.assertTrue(check_prediction(c,p)['complete_correct'])
 def test_stable_offsets_cancel(self):
  c=self.obs();obs=copy.deepcopy(c['observation']);old=analyze(obs)
  for phase in obs.values():
   for x in phase['records']:x['v2']+=10.;x['v4']-=5.
  new=analyze(obs);self.assertEqual(old['classifications'],new['classifications']);check_prediction(c,new)
 def test_missing_voltage_abstains(self):
  c=self.obs()
  for s in c['observation'].values():
   for x in s['records']:x['v4']=None
  self.assertEqual(set(analyze(c['observation'])['classifications'].values()),{'ambiguous'})
 def test_invalid_gain_refuses(self):
  c=self.obs();c['observation']['after']['gain_range']=[0,1]
  self.assertEqual(analyze(c['observation'])['classifications']['sample'],'ambiguous')
 def test_nan_refuses(self):
  c=self.obs();c['observation']['after']['voltage_error']=float('nan')
  self.assertEqual(analyze(c['observation'])['classifications']['sample'],'ambiguous')
 def test_zero_current_refuses(self):
  c=self.obs()
  for x in c['observation']['after']['records']:x['current']=0
  self.assertEqual(analyze(c['observation'])['classifications']['sample'],'ambiguous')
 def test_reversal_inconsistency_refuses(self):
  c=self.obs();c['observation']['after']['records'][0]['v2']+=1
  self.assertEqual(analyze(c['observation'])['classifications']['sample'],'ambiguous')
 def test_checker_rejects_wrong_class(self):
  c=self.obs();p=analyze(c['observation']);p['classifications']['sample']='unchanged'
  with self.assertRaises(AssertionError):check_prediction(c,p)
 def test_checker_rejects_wrong_interval(self):
  c=self.obs();p=analyze(c['observation']);p['after']['bulk']=[0,1]
  with self.assertRaises(AssertionError):check_prediction(c,p)
 def test_design_has_hard_limits(self):
  d=compile_design({'maximum_current_A':.001,'maximum_specimen_power_W':.00001,'maximum_bulk_ohm':40,'current_menu_A':[.00025,.0005,.001]})
  self.assertEqual(d['currents_A'][0],.0005)
 def test_no_safe_menu_refuses(self):
  with self.assertRaises(ValueError):compile_design({'maximum_current_A':0,'maximum_specimen_power_W':1,'maximum_bulk_ohm':10,'current_menu_A':[1]})
if __name__=='__main__':unittest.main()

class ReplayTests(unittest.TestCase):
 def test_missing_observation_not_repaired_by_renaming_tool(self):
  from .replay import replay_missing_sense
  c=make_case('both','channels',0,97004,[.001,-.001])['observation']
  self.assertFalse(replay_missing_sense(c,c)['reopened'])
 def test_new_observations_reopen_only_declared_obstacle(self):
  from .replay import replay_missing_sense
  c=make_case('both','noise',0,97004,[.001,-.001])['observation'];missing=copy.deepcopy(c)
  for s in missing.values():
   for r in s['records']:r['v4']=None
  self.assertTrue(replay_missing_sense(missing,c)['reopened'])

class RegistrationTests(unittest.TestCase):
 def test_development_confirmation_seed_sets_disjoint(self):
  a={970000+t*1000+f*100+r for t in range(4) for f in range(3) for r in range(12)}
  b={980000+t*1000+f*100+r for t in range(4) for f in range(3) for r in range(12)}
  self.assertFalse(a&b);self.assertEqual(len(a),144);self.assertEqual(len(b),144)

class InvalidInputTests(unittest.TestCase):
 def test_nondictionary_observation_abstains(self):
  self.assertEqual(set(analyze(None)['classifications'].values()),{'ambiguous'})
 def test_nonreversal_refuses(self):
  c=make_case('both','noise',0,97001,[.001,-.001])['observation']
  c['after']['records'][1]['current']=.0005
  self.assertEqual(analyze(c)['classifications']['sample'],'ambiguous')
 def test_negative_design_limit_refuses(self):
  with self.assertRaises(ValueError):compile_design({'maximum_current_A':.001,'maximum_specimen_power_W':1,'maximum_bulk_ohm':-1,'current_menu_A':[.001]})

class AcceptanceIntegrityTests(unittest.TestCase):
 def case(self):return make_case('none','noise',0,97000,[.001,-.001,.0005,-.0005])
 def test_cross_pair_offset_change_refuses(self):
  c=self.case();p=c['observation']['after']
  for r in p['records'][2:]:r['v2']+=1;r['v4']+=1
  self.assertEqual(set(analyze(c['observation'])['classifications'].values()),{'ambiguous'})
 def test_no_bounds_cannot_claim(self):
  c=self.case();p=analyze(c['observation'])
  for q in ('baseline','after','difference'):p[q]={'bulk':None,'contact':None}
  with self.assertRaises(AssertionError):check_prediction(c,p)
 def test_nonfinite_difference_rejected(self):
  c=self.case();p=analyze(c['observation']);p['difference']['bulk']=[-float('inf'),float('inf')]
  with self.assertRaises(AssertionError):check_prediction(c,p)
 def test_empty_result_rejected(self):
  from .check import check_result
  with self.assertRaises(AssertionError):check_result({'rows':[],'arms':[]})

class BoundaryTests(unittest.TestCase):
 def observation(self,total,sense):
  return {'records':[{'current':.001,'v2':total,'v4':sense},{'current':-.001,'v2':-total,'v4':-sense}],'voltage_error':0,'current_error':0,'gain_range':[1,1],'sense_fraction_range':[.5,.5]}
 def test_decimal_exact_sample_threshold(self):
  p=analyze({'baseline':self.observation(.0026,.0003),'after':self.observation(.0031,.00055)})
  self.assertEqual(p['difference']['bulk'],[.5,.5]);self.assertEqual(p['classifications']['sample'],'unchanged')
 def test_both_signed_thresholds(self):
  for sign in (-1,1):
   a=self.observation(.002,.0005)
   b=self.observation(.00175 if sign<0 else .00225,.0005)
   p=analyze({'baseline':a,'after':b})
   self.assertNotEqual(p['classifications']['contact'],'changed')
 def test_next_representable_interval_classification(self):
  from .instrument import classify
  for threshold in (.5,.25):
   self.assertEqual(classify([threshold,threshold],threshold),'unchanged')
   value=math.nextafter(threshold,math.inf)
   self.assertEqual(classify([value,value],threshold),'changed')
   self.assertEqual(classify([-value,-value],threshold),'changed')

class OverflowTests(unittest.TestCase):
 def test_tiny_gain_abstains(self):
  o=BoundaryTests().observation(.002,.0005);o['gain_range']=[1e-320,1e-320]
  p=analyze({'baseline':o,'after':o})
  self.assertEqual(p['classifications'],{'sample':'ambiguous','contact':'ambiguous'})
  import json
  json.dumps(p,allow_nan=False)

class ReplayIdentityTests(unittest.TestCase):
 def test_replay_rejects_replaced_context(self):
  from .replay import replay_missing_sense
  c=make_case('both','noise',0,97004,[.001,-.001])['observation'];missing=copy.deepcopy(c)
  for phase in missing.values():phase['records'][0]['v4']=None
  for field in ('current','v2','v4'):
   changed=copy.deepcopy(c);changed['after']['records'][1][field]+=1
   self.assertFalse(replay_missing_sense(missing,changed)['reopened'])
  changed=copy.deepcopy(c);changed['after']['gain_range']=[.9,1.1]
  self.assertFalse(replay_missing_sense(missing,changed)['reopened'])
 def test_checker_decimal_boundary(self):
  o=BoundaryTests();p=analyze({'baseline':o.observation(.0026,.0003),'after':o.observation(.0031,.00055)})
  c={'truth':{'baseline':{'bulk':.6,'contact':2},'after':{'bulk':1.1,'contact':2}}}
  self.assertTrue(check_prediction(c,p)['complete_correct'])

class ResultRetentionTests(unittest.TestCase):
 def test_existing_output_not_overwritten(self):
  import tempfile,sys
  from pathlib import Path
  from unittest.mock import patch
  from . import experiment
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'result.json';p.write_text('preserved')
   with patch.object(sys,'argv',['experiment','--development','--output',str(p)]):
    with self.assertRaises(FileExistsError):experiment.main()
   self.assertEqual(p.read_text(),'preserved')
