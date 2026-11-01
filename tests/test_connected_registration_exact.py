import copy,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from connected_enterprise.engine import default_config
from connected_enterprise.registration import SCHEMA,native_engine,validate
from connected_enterprise.runner import _service_manifest
ROOT=Path(__file__).resolve().parents[1]
def registration():
 cfg=default_config();cfg.update(horizon_days=3,customer_pool=4,opening=100_000_000_000,arrival_bps=10000,retention_bps=10000,nonpayment_bps=0,clearing_hours=1,monetary_policy='exact-integer-v2')
 return {'schema':SCHEMA,'label':'exact-registration-048','evidence_role':'development','seeds':[2611010480],'configs':{'central':cfg},'arms':['baseline','growth'],'control_arm':'baseline','candidate_arm':'growth','service_cohort_seed':2611010480,'workers':1}
class ManifestSelectionTests(unittest.TestCase):
 def test_legacy_manifest_and_inputs_unchanged(self):
  m={'jobs':[]};c={'central':default_config()};self.assertEqual(_service_manifest(m,c),m);self.assertNotIn('native_engine',m)
 def test_exact_engine_is_derived_from_complete_source_bound_configuration(self):
  r=registration();m={'jobs':[]};self.assertEqual(native_engine(r['configs']),'exact-permanent-v2');self.assertEqual(_service_manifest(m,r['configs']),{'jobs':[],'native_engine':'exact-permanent-v2'});self.assertEqual(m,{'jobs':[]})
 def test_mixed_native_engines_rejected_before_accounts(self):
  r=registration();r['configs']['adverse']=default_config()
  with self.assertRaisesRegex(ValueError,'ONE_SOURCE_BOUND_SERVICE_MANIFEST_ENGINE_REQUIRED'):validate(r)
 def test_prospective_engines_remain_distinct(self):
  from connected_enterprise.capital_lifecycle import default_policy
  c=default_config();c['prospective_policy']=default_policy();self.assertEqual(native_engine({'central':c}),'prospective-v1')
  c['monetary_policy']='exact-integer-v2';self.assertEqual(native_engine({'central':c}),'exact-prospective-v2')
class ExactRegisteredOperationTests(unittest.TestCase):
 @classmethod
 def invoke(cls,*args):
  return subprocess.run([sys.executable,'-m','connected_enterprise',*args],cwd=ROOT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=180)
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='exact-registration048-');cls.output=Path(cls.temp.name)/'operation';p=Path(cls.temp.name)/'INPUT.json';p.write_text(json.dumps(registration()))
  for args in [('register','--config',str(p),'--output',str(cls.output)),('operate','--max-events','2','--output',str(cls.output))]:
   r=cls.invoke(*args)
   if r.returncode:raise AssertionError(r.stderr)
  cls.partial={p.parent.name:json.loads(p.read_text()) for p in (cls.output/'worlds').glob('*/RESULT.json')}
  r=cls.invoke('resume','--output',str(cls.output))
  if r.returncode:raise AssertionError(r.stderr)
  cls.results={p.parent.name:json.loads(p.read_text()) for p in (cls.output/'worlds').glob('*/RESULT.json')}
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def test_exact_register_operate_same_account_resume_and_full_origin_audit(self):
  manifest=json.loads((self.output/'SERVICES.json').read_text());self.assertEqual(manifest['native_engine'],'exact-permanent-v2')
  origin=json.loads((self.output/'source/service-inputs/MANIFEST.json').read_text());self.assertEqual({k:v for k,v in manifest.items() if k!='native_engine'},origin)
  for name,partial in self.partial.items():
   final=self.results[name];self.assertFalse(partial['complete']);self.assertTrue(final['complete']);self.assertEqual(partial['owned_account']['ledger']['config'],final['owned_account']['ledger']['config']);prefix=partial['owned_account']['ledger']['actions'];self.assertEqual(prefix,final['owned_account']['ledger']['actions'][:len(prefix)])
   for ident,proof in partial['owned_account']['action_proofs'].items():self.assertEqual(proof,final['owned_account']['action_proofs'][ident])
  r=self.invoke('audit','--output',str(self.output));self.assertEqual(r.returncode,0,r.stderr);self.assertTrue(json.loads(r.stdout)['accepted'])
 def test_manifest_engine_downgrade_and_wrong_version_fail_before_resume_or_audit(self):
  path=self.output/'SERVICES.json';saved=path.read_bytes();original=json.loads(saved)
  try:
   for engine in (None,'legacy-permanent-v1','exact-prospective-v2'):
    changed=copy.deepcopy(original)
    if engine is None:changed.pop('native_engine')
    else:changed['native_engine']=engine
    path.write_text(json.dumps(changed))
    for command in ('resume','audit'):
     r=self.invoke(command,'--output',str(self.output));self.assertNotEqual(r.returncode,0);self.assertIn('SOURCE_BOUND_SERVICE_MANIFEST_ENGINE_CHANGED',r.stderr)
  finally:path.write_bytes(saved)
