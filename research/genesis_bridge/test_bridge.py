import copy,json,pathlib,tempfile,unittest
from unittest.mock import patch
from . import core
from .core import ROOT,read,request,digest,execute,accept,probe,plan,retain,reuse,verify_sources
from .demo import fixture_request,CONTEXT,run_demo
class BridgeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();cls.root=pathlib.Path(cls.temp.name)
  cls.cases=read(ROOT/'campaign/genesis-execution-bridge/FIXTURES.json')
  cls.q,cls.f=fixture_request(cls.cases[0]);cls.r,cls.a=execute(cls.q,cls.root/'good',cls.f)
  cls.observation=read(ROOT/'campaign/genesis-execution-bridge/OBSERVATION.json')
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def out(self):return self.root/self.id().split('.')[-1]
 def test_valid_pass(self):self.assertEqual(self.a['status'],'PASS')
 def test_metadata_only(self):self.assertIsNone(plan(self.observation,[])['proposal'])
 def test_fake_release_capability(self):
  o={**self.observation,'access':'assumed_access_in_demo','provides':['accepted_analysis','local_kelvin_kernel']}
  self.assertIsNone(plan(o,[])['proposal'])
 def test_restricted_metadata(self):self.assertIsNone(plan({**self.observation,'access':'restricted'},[])['proposal'])
 def test_forged_probe(self):
  p={'request':self.q,'fixture':self.f,'execution':copy.deepcopy(self.r),'capability':'local_kelvin_kernel'}
  p['execution']['worker']['output']['classifications']['sample']='unchanged'
  with self.assertRaises(ValueError):plan(self.observation,[p])
 def test_failed_canary(self):
  p={'request':self.q,'fixture':self.f,'execution':{**self.r,'status':'FAIL','error':'failed'},'capability':'local_kelvin_kernel'}
  self.assertIsNone(plan(self.observation,[p])['proposal'])
 def test_noncanary_probe(self):
  q,f=fixture_request(self.cases[1])
  with self.assertRaises(ValueError):probe(q,f,self.out())
 def test_unknown_operation(self):
  with self.assertRaises(ValueError):request('shell','x',CONTEXT,{'cmd':'echo bad'})
 def test_overwrite_refused(self):
  with self.assertRaises(FileExistsError):execute(self.q,self.root/'good',self.f)
 def test_swapped_task(self):
  with self.assertRaises(ValueError):accept({**self.q,'task_id':'other'},self.r,self.f)
 def test_swapped_input(self):
  q=copy.deepcopy(self.q);q['input']=self.cases[1]['observation']
  with self.assertRaises(ValueError):accept(q,self.r,self.f)
 def test_swapped_context(self):
  q=copy.deepcopy(self.q);q['context']['domain']='physical'
  with self.assertRaises(ValueError):accept(q,self.r,self.f)
 def test_swapped_checker_contract(self):
  q=copy.deepcopy(self.q);q['acceptance_contract']['scope']='anything'
  with self.assertRaises(ValueError):accept(q,self.r,self.f)
 def test_changed_source(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t);(p/'campaign/genesis-execution-bridge').mkdir(parents=True);(p/'source.py').write_text('bad')
   (p/core.LOCK).write_text(json.dumps({'sha256':{'source.py':'0'*64}}))
   with self.assertRaises(ValueError):verify_sources(p)
 def test_changed_checker_source(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t);(p/'campaign/genesis-execution-bridge').mkdir(parents=True);(p/'check.py').write_text('return True')
   (p/core.LOCK).write_text(json.dumps({'sha256':{'check.py':'0'*64}}))
   with self.assertRaises(ValueError):verify_sources(p)
 def test_output_tamper(self):
  r=copy.deepcopy(self.r);r['worker']['output']['classifications']['sample']='unchanged'
  with self.assertRaises(ValueError):accept(self.q,r,self.f)
 def test_rehashed_false_output(self):
  r=copy.deepcopy(self.r);r['worker']['output']['classifications']['sample']='unchanged';r['worker']['output_sha256']=digest(r['worker']['output'])
  with self.assertRaises(AssertionError):accept(self.q,r,self.f)
 def test_receipt_tamper(self):
  r=copy.deepcopy(self.r);r['binding']['task_id']='fake'
  with self.assertRaises(ValueError):accept(self.q,r,self.f)
 def test_exit_status_tamper(self):
  r=copy.deepcopy(self.r);r['exit_code']=1
  with self.assertRaises(ValueError):accept(self.q,r,self.f)
 def test_runtime_tamper(self):
  r=copy.deepcopy(self.r);r['worker']['python_version']='fictional'
  with self.assertRaises(ValueError):accept(self.q,r,self.f)
 def test_cpu_over_limit(self):
  r=copy.deepcopy(self.r);r['worker']['cpu_seconds']=999
  with self.assertRaises(ValueError):accept(self.q,r,self.f)
 def test_rss_over_bound(self):
  r=copy.deepcopy(self.r);r['worker']['max_rss_kib']=999999999
  with self.assertRaises(ValueError):accept(self.q,r,self.f)
 def test_rss_wrong_type(self):
  r=copy.deepcopy(self.r);r['worker']['max_rss_kib']=True
  with self.assertRaises(ValueError):accept(self.q,r,self.f)
 def test_wall_over_limit(self):
  r=copy.deepcopy(self.r);r['wall_seconds']=99
  with self.assertRaises(ValueError):accept(self.q,r,self.f)
 def test_missing_observation_abstains(self):
  q=copy.deepcopy(self.q)
  for phase in ('baseline','after'):
   for r in q['input'][phase]['records']:r['v4']=None
  f={**self.f,'request_sha256':digest(q)};r,a=execute(q,self.out(),f)
  self.assertEqual(a['status'],'ABSTAIN')
  with self.assertRaises(ValueError):retain(q,r,f)
 def test_missing_bounds_abstains(self):
  q=copy.deepcopy(self.q);del q['input']['after']['gain_range'];f={**self.f,'request_sha256':digest(q)}
  _,a=execute(q,self.out(),f);self.assertIn(a['status'],('ABSTAIN','FAIL'))
 def test_nonfinite_request(self):
  q=copy.deepcopy(self.q);q['input']['after']['voltage_error']=float('nan')
  with self.assertRaises(ValueError):execute(q,self.out(),self.f)
 def test_invalid_resource_limit(self):
  q=copy.deepcopy(self.q);q['limits']['wall_seconds']=0
  with self.assertRaises(ValueError):execute(q,self.out(),self.f)
 def test_actual_wall_failure(self):
  q=copy.deepcopy(self.q);q['limits']['wall_seconds']=1e-9;f={**self.f,'request_sha256':digest(q)}
  r,a=execute(q,self.out(),f);self.assertEqual(a['status'],'FAIL');self.assertIsNone(r['exit_code'])
 def test_replay_changed_calibration_abstains(self):
  old=copy.deepcopy(self.q['input']);new=copy.deepcopy(old)
  for phase in ('baseline','after'):
   for r in old[phase]['records']:r['v4']=None
  new['after']['gain_range']=[.9,1.1]
  q,f=fixture_request(self.cases[0],'replay',{'previous':old,'current':new})
  _,a=execute(q,self.out(),f);self.assertIn(a['status'],('ABSTAIN','FAIL'))
 def test_replay_missing_still_abstains(self):
  old=copy.deepcopy(self.q['input'])
  for phase in ('baseline','after'):
   for r in old[phase]['records']:r['v4']=None
  q,f=fixture_request(self.cases[0],'replay',{'previous':old,'current':old})
  _,a=execute(q,self.out(),f);self.assertIn(a['status'],('ABSTAIN','FAIL'))
 def test_wrong_retention_type(self):
  r=copy.deepcopy(self.r);r['status']='FAIL';r['error']='failed'
  with self.assertRaises(ValueError):retain(self.q,r,self.f)
 def test_reuse_changed_context(self):
  m=retain(self.q,self.r,self.f);q,f=fixture_request(self.cases[1]);q['context']={**CONTEXT,'gain_model':'changed'}
  with self.assertRaises(ValueError):reuse(m,self.q,self.r,self.f,q,self.out(),f)
 def test_fixture_truth_tamper(self):
  f=copy.deepcopy(self.f);f['truth']['baseline']['bulk']=20.001
  with self.assertRaises(ValueError):accept(self.q,self.r,f)
 def test_fixture_registration_tamper(self):
  f=copy.deepcopy(self.f);f['registration']='unrelated'
  with self.assertRaises(ValueError):accept(self.q,self.r,f)
 def test_symlink_output_ancestor(self):
  alias=self.root/'alias';alias.symlink_to(self.root,target_is_directory=True)
  with self.assertRaises(ValueError):execute(self.q,alias/'new',self.f)
 def test_replay_cached_current_refused(self):
  old=copy.deepcopy(self.q['input'])
  for phase in ('baseline','after'):
   for r in old[phase]['records']:r['v4']=None
  q,f=fixture_request(self.cases[0],'replay',{'previous':old,'current':self.q['input']})
  r,a=execute(q,self.out(),f);m=retain(q,r,f)
  nxt=copy.deepcopy(self.q);nxt['task_id']='renamed'
  with self.assertRaises(ValueError):reuse(m,q,r,f,nxt,self.out()/'cached',self.f)
 def test_reuse_cached_answer_refused(self):
  m=retain(self.q,self.r,self.f)
  with self.assertRaises(ValueError):reuse(m,self.q,self.r,self.f,self.q,self.out(),self.f)
 def test_monkeypatched_checker_not_used(self):
  r=copy.deepcopy(self.r);r['worker']['output']['classifications']['sample']='WRONG';r['worker']['output_sha256']=digest(r['worker']['output'])
  with patch('research.genesis097.check.check_prediction',return_value={'abstained':False}):
   with self.assertRaises(AssertionError):accept(self.q,r,self.f)
 def test_design_acquisition_mismatch(self):
  design={'maximum_current_A':.001,'maximum_specimen_power_W':.001,'maximum_bulk_ohm':40,'current_menu_A':[.0005,.001]}
  dq=request('compile','design-001',CONTEXT,design);df={'request_sha256':digest(dq)};dr,da=execute(dq,self.out(),df)
  q=copy.deepcopy(self.q);q['design_proof']={'request':dq,'execution':dr,'fixture':df}
  q['input']['baseline']['records']=q['input']['baseline']['records'][:4]
  f={**self.f,'request_sha256':digest(q)}
  _,a=execute(q,self.out()/'analysis',f);self.assertEqual(a['status'],'FAIL')
 def test_end_to_end(self):
  r=run_demo(self.out());self.assertTrue(r['same_kernel_equal_outputs']);self.assertEqual(len(r['successors']),12)
  self.assertEqual({x['acceptance'] for x in r['successors']},{'PASS'})
  self.assertNotIn('accepted_analysis',r['actual_capabilities_after_route'])
if __name__=='__main__':unittest.main()
