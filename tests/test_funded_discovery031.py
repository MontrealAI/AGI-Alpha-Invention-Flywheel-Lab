import copy
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from adaptive_enterprise.instruments import prepare_services
from connected_enterprise.finance import JournalAccount
from connected_enterprise import funded_discovery031 as adapter
ROOT = Path(__file__).resolve().parents[1]

class FundedDiscovery(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.workspace=tempfile.TemporaryDirectory();cls.directory=Path(cls.workspace.name)
  cls.root=cls.directory/'source'
  shutil.copytree(ROOT,cls.root,ignore=shutil.ignore_patterns('__pycache__','*inputs*'))
  cls.manifest=prepare_services(cls.root,'test-inputs',cohort_seed=311031)
 @classmethod
 def tearDownClass(cls):cls.workspace.cleanup()
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.directory=Path(self.temp.name)
  self.account=JournalAccount(self.root,self.manifest,self.directory/'state.sqlite',opening=100_000_000,working=1_000_000,contract='discovery031-test')
 def tearDown(self):self.account.close();self.temp.cleanup()
 def run_case(self,**kw):
  return adapter.run_research(self.root,self.account,self.directory/'research',ident='test',enabled=True,**kw)
 def test_disabled_default_is_free(self):
  result=adapter.run_research(self.root,self.account,self.directory/'disabled',ident='disabled')
  self.assertEqual(result['native_cost_microUSD'],0);self.assertFalse((self.directory/'disabled').exists())
 def test_unfunded_does_not_call_acquisition(self):
  with patch.object(adapter.pipeline,'develop') as work:
   with self.assertRaisesRegex(ValueError,'FUNDS_INSUFFICIENT'):self.run_case()
   work.assert_not_called()
 def test_actual_chain_existing_account_and_equal_content_controls(self):
  self.account.cost('test:acquire',11,0)
  prior=self.account.export()['connected_journal']['entries'][0]
  self.assertEqual(prior['request']['operation'],'execute')
  self.assertNotIn('id',prior['request'])
  original=adapter.pipeline.develop
  def observe(*args,**kwargs):
   entries=self.account.export()['connected_journal']['entries']
   self.assertEqual(entries[-1]['status'],'COMPLETE')
   self.assertEqual(entries[-1]['request']['amount'],adapter.FEES['acquisition'])
   return original(*args,**kwargs)
  with patch.object(adapter.pipeline,'develop',side_effect=observe):result=self.run_case(allow_seed=True)
  self.assertFalse(result['acquisition']['before_passed']);self.assertTrue(result['acquisition']['after_passed'])
  self.assertIsNotNone(result['acquisition']['retained']);self.assertEqual(result['authority'],[])
  self.assertEqual(len(result['rows']),6)
  for index in range(2):
   rows=result['rows'][index*3:index*3+3]
   self.assertEqual(rows[1]['content_sha256'],rows[2]['content_sha256'])
   self.assertTrue(rows[1]['content_sha256'])
   self.assertEqual(rows[1]['candidates'],rows[2]['candidates'])
   self.assertEqual(rows[1]['native_cost_microUSD'],rows[2]['native_cost_microUSD'])
   self.assertTrue(rows[0]['accepted'])
  self.assertFalse(result['rows'][4]['accepted']) # extra action absent from acquired method
  self.assertFalse(result['rows'][5]['accepted'])
  entries=self.account.export()['connected_journal']['entries']
  research=[e for e in entries if e['request']['operation']=='spend']
  self.assertEqual(sum(e['request']['amount'] for e in research),result['native_cost_microUSD'])
  self.assertEqual(self.account.audit()['summary']['expenses'],result['native_cost_microUSD']+11)
  self.assertTrue(self.account.audit()['accepted'])
  with self.assertRaises(ValueError):self.run_case(allow_seed=True)
 def test_failed_acquisition_remains_charged_no_free_retry(self):
  with patch.object(adapter.pipeline,'develop',side_effect=ValueError('injected failure')):
   with self.assertRaisesRegex(ValueError,'injected failure'):self.run_case(allow_seed=True)
  self.assertEqual(sum(e['request']['amount'] for e in self.account.export()['connected_journal']['entries']),adapter.FEES['acquisition'])
  with self.assertRaises(ValueError):
   adapter.run_research(self.root,self.account,self.directory/'retry',ident='test',enabled=True,allow_seed=True)
 def test_prior_execute_does_not_bypass_paid_duplicate_guard(self):
  self.account.cost('same-id',7,0)
  adapter._pay(self.account,'same-id','acquisition',100,0,{'test':True},True)
  with self.assertRaisesRegex(ValueError,'ALREADY_ATTEMPTED'):
   adapter._pay(self.account,'same-id','acquisition',100,0,{'test':True},True)
  self.assertEqual(self.account.audit()['summary']['expenses'],107)
 def test_fake_account_rejected(self):
  with self.assertRaisesRegex(ValueError,'CANONICAL_JOURNAL'):
   adapter.run_research(ROOT,object(),self.directory/'fake',ident='fake',enabled=True)
 def test_fresh_structure_not_only_renaming(self):
  targets=adapter.fresh_tasks();self.assertEqual([len(t['phases']) for t in targets],[4,5])
  self.assertEqual(max(len(p['deps']) for p in targets[1]['phases']),2)
 def test_imported_source_mismatch_before_payment(self):
  with patch.object(adapter.pipeline, '__file__', str(self.root/'mechanisms/pipeline.py')):
   with self.assertRaisesRegex(ValueError,'IMPORTED_SOURCE_MISMATCH'):self.run_case(allow_seed=True)
  self.assertEqual(self.account.export()['connected_journal']['entries'],[])
 def test_source_mismatch_before_payment(self):
  path=self.root/'mechanisms/criticism.py';old=path.read_bytes()
  try:
   path.write_bytes(old+b'\n# changed\n')
   with self.assertRaisesRegex(ValueError,'EXECUTING_SOURCE_MISMATCH'):self.run_case(allow_seed=True)
   self.assertEqual(self.account.export()['connected_journal']['entries'],[])
  finally:path.write_bytes(old)
 def test_package_dependencies_fail_closed(self):
  from connected_enterprise.runner import source_paths
  self.assertTrue(set(adapter.DEPENDENCIES).issubset(source_paths(ROOT)))

if __name__=='__main__':unittest.main()
