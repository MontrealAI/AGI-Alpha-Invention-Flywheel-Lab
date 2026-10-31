import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from adaptive_enterprise.instruments import prepare_services
from adaptive_enterprise.strategies import offer_catalog
from connected_enterprise.finance import JournalAccount
from connected_enterprise.funded_csv_adapter028 import run_funded,binding
from connected_enterprise.native_csv_manifest028 import qualify
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('runner028',ROOT/'scripts/run_funded_csv028.py');runner=importlib.util.module_from_spec(s);s.loader.exec_module(runner)

class Funded(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)/'source'
  shutil.copytree(ROOT,cls.root,ignore=shutil.ignore_patterns('__pycache__','*inputs*'))
  cls.manifest=prepare_services(cls.root,'test-inputs',cohort_seed=2810311806)
  cls.jobs={int(j['id'].split('-')[-1]):j for j in cls.manifest['jobs'] if j['service_id']=='reconciliation'}
  cls.spec=json.loads((cls.root/'campaign/mechanism-harness-027/EXISTING_OPERATIONS.json').read_text())
  cls.plan=json.loads((cls.root/'campaign/mechanism-harness-027/PLAN.json').read_text())
  cls.offer=next(o for o in offer_catalog() if o['service_id']=='reconciliation' and o['method']=='generated_schema')
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def setUp(self):
  self.tmpcase=tempfile.TemporaryDirectory();self.directory=Path(self.tmpcase.name)
  self.account=JournalAccount(self.root,self.manifest,self.directory/'state.sqlite',opening=100000000,working=1000000,contract='csv028-test')
 def tearDown(self):self.account.close();self.tmpcase.cleanup()
 def run_case(self,arm='replanned',index=8,allow_seed=True,spec=None,plan=None,ident='case'):
  return run_funded(self.root,self.account,spec or self.spec,plan or self.plan,None,self.directory/(ident+'-out'),arm=arm,ident=ident,allow_seed=allow_seed,
      native_manifest=self.manifest,native_job_id=self.jobs[index]['id'],native_policy=runner.policy(),native_offer=self.offer)
 def test_actual_output_matches_native_manifest(self):
  r=self.run_case();self.assertTrue(r['accepted']);self.assertTrue(r['native_manifest_qualification']['accepted']);self.assertTrue(r['native_audit_accepted']);self.assertEqual(r['native_selected_mode'],'conventional')
  self.assertEqual(r['native_cost_microUSD'],1600000)
 def test_equal_content_direct_and_inherited_match(self):
  rows=[self.run_case(arm=arm,ident=arm) for arm in ('direct','equal_content','replanned','inherited')]
  self.assertEqual(len({r['artifact_sha256'] for r in rows}),1)
  self.assertEqual(len({r['native_manifest_qualification']['semantic_sha256'] for r in rows}),1)
 def test_missing_facts_refusal_independently_reproduced(self):
  r=self.run_case(index=15);self.assertFalse(r['accepted']);self.assertTrue(r['independent_refusal']['verified']);self.assertTrue(r['native_audit_accepted']);self.assertIsNone(r['native_manifest_qualification'])
 def test_unfunded_stops_before_execution(self):
  with self.assertRaisesRegex(ValueError,'INSUFFICIENT'):self.run_case(allow_seed=False)
  self.assertFalse((self.directory/'case-out').exists())
 def test_duplicate_never_reexecutes_on_one_payment(self):
  self.run_case()
  with self.assertRaisesRegex(ValueError,'ALREADY_ATTEMPTED'):self.run_case()
 def test_unqualified_bridge_refuses(self):
  from mechanism_harness.core import compose
  spec=copy.deepcopy(self.spec);spec['candidate_bridges']=[{'id':'magic','requires':['raw_public_exports'],'provides':['independently_checked_delivery'],'cost':1,'effect':'pure','origin':'machine_proposed'}]
  with self.assertRaises(ValueError):self.run_case(spec=spec,plan=compose(spec))
  self.assertFalse((self.directory/'case-out').exists())
 def test_effect_label_not_permission(self):
  spec=copy.deepcopy(self.spec);spec['purpose']['allowed_effects']=['public_read'];spec['mechanisms'][0]['effect']='public_read'
  with self.assertRaises(ValueError):self.run_case(spec=spec)
 def test_actual_copied_source_changed(self):
  p=self.root/'mechanism_harness/operating027.py';old=p.read_bytes()
  try:
   p.write_bytes(old+b'\n# mutation\n')
   with self.assertRaisesRegex(ValueError,'EXECUTING_SOURCE'):self.run_case()
  finally:p.write_bytes(old)
 def test_symbolic_cost_not_native_money(self):
  plan=copy.deepcopy(self.plan);plan['cost_units']=1
  with self.assertRaises(ValueError):self.run_case(plan=plan)
  rows=self.account.export()['connected_journal']['entries'];self.assertEqual(sum(e['request']['amount'] for e in rows),50000)
 def test_package_closure_includes_dependency(self):
  from connected_enterprise.runner import source_paths
  paths=set(source_paths(self.root));self.assertIn('mechanism_harness/operating027.py',paths);self.assertIn('mechanism_harness/study027.py',paths)
  p=self.root/'mechanism_harness/study027.py';old=p.read_bytes()
  try:
   p.unlink()
   with self.assertRaisesRegex(ValueError,'DEPENDENCY_MISSING'):source_paths(self.root)
  finally:p.write_bytes(old)
 def test_wrong_service_rejected(self):
  other=next(j for j in self.manifest['jobs'] if j['service_id']=='kpi_variance')
  with self.assertRaisesRegex(ValueError,'RECONCILIATION_JOB'):
   run_funded(self.root,self.account,self.spec,self.plan,None,self.directory/'wrong',arm='direct',ident='wrong',allow_seed=True,native_manifest=self.manifest,native_job_id=other['id'],native_policy=runner.policy(),native_offer=self.offer)

if __name__=='__main__':unittest.main()
