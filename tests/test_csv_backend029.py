import copy,json,shutil,tempfile,unittest
from pathlib import Path
from adaptive_enterprise.instruments import prepare_services,execute_offer
from adaptive_enterprise.strategies import offer_catalog
from connected_enterprise.csv_backend029 import contract,execute_service,validate_contract
from connected_enterprise.mechanism_choice import order_plan,csv_costs,execute_funded,audit_execution
from connected_enterprise.finance import JournalAccount
from scripts.run_funded_csv028 import policy
ROOT=Path(__file__).resolve().parents[1]
def configured(root,arm='replanned',diagnostic=True):
 p=policy();p['csv_backend']=contract(root,arm);p['costs']['csv_backend']=csv_costs(p['csv_backend']);p['mode']='diagnostic_csv_backend' if diagnostic else 'optimize';return p
class Backend(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)/'source';shutil.copytree(ROOT,cls.root,ignore=shutil.ignore_patterns('__pycache__','.csv029*','.canonical-csv029*'))
  cls.manifest=prepare_services(cls.root,'inputs',cohort_seed=2910311834);cls.job=next(j for j in cls.manifest['jobs'] if j['service_id']=='reconciliation' and j['id'].endswith('-008'))
  cls.offer=next(o for o in offer_catalog() if o['service_id']=='reconciliation' and o['method']=='generated_schema')
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.a=JournalAccount(self.root,self.manifest,Path(self.t.name)/'account',opening=100000000,working=1000000,contract='csv029-test')
 def tearDown(self):self.a.close();self.t.cleanup()
 def execute(self,arm='replanned',fund=True):
  p=configured(self.root,arm);plan=order_plan(p,self.job['id'],self.offer,None,1500000)
  if fund:self.a.spend('order-resources','production_contract',1500000+plan['cost'],0,{'job_id':self.job['id'],'offer':self.offer,'method_plan':plan,'production_envelope_microUSD':1500000},1,allow_seed=True)
  return execute_funded(self.root,self.manifest,self.a,self.offer,self.job['id'],ident='method',day=0,mode=plan['mode'],costs=plan['costs'],memory=None,prepaid_order='order',cost_contract=p['cost_contract'],backend=plan['backend'])
 def test_actual_native_prepaid_backend_and_independent_replay(self):
  r=self.execute();self.assertTrue(r['accepted']);self.assertTrue(audit_execution(self.root,self.manifest,self.a,r)['accepted']);self.assertEqual(r['cost'],100000)
  rows=self.a.export()['connected_journal']['entries'];self.assertEqual(len(rows),1);self.assertEqual(rows[0]['request']['amount'],1600000)
 def test_no_prepaid_execution(self):
  with self.assertRaisesRegex(ValueError,'PREPAYMENT_REQUIRED'):self.execute(fund=False)
 def test_optimized_choice_declines_costlier_equivalent_csv(self):
  p=configured(self.root,diagnostic=False);plan=order_plan(p,self.job['id'],self.offer,None,1500000);self.assertEqual(plan['mode'],'conventional');self.assertIn('csv_backend',plan['problem']['costs']);self.assertNotIn('backend',plan)
 def test_joint_price_choice_includes_csv_without_forcing_it(self):
  from connected_enterprise.strategic_commerce import select
  from scripts.run_commoncost026 import joint_policy
  public={'anchor':25000000,'public_rival_price':20000000,'base_cost':2000000,'payment_bps':290,'payment_fixed':300000,'available':100000000,'reserve_buffer':200000,'quote_cost':50000,'native_state_digest':'0'*64,'profit_tax_bps':2000}
  result=select(joint_policy(),configured(self.root,diagnostic=False),self.job['id'],self.offer,None,public)
  self.assertIn('csv_backend',{r['mode'] for r in result['candidates']});self.assertEqual(result['method_plan']['mode'],'conventional')
 def test_changed_native_cost_or_backend_rejected(self):
  r=self.execute();r['backend']['extra_cost_microUSD']=0
  with self.assertRaises(ValueError):audit_execution(self.root,self.manifest,self.a,r)
 def test_paid_error_cannot_switch_prepaid_backend(self):
  r=self.execute();r['error']='forced diagnostic failure';r['accepted']=False;r['backend']=contract(self.root,'inherited')
  with self.assertRaisesRegex(ValueError,'CSV_BACKEND_SOURCE_OR_COST_CHANGED'):audit_execution(self.root,self.manifest,self.a,r)
 def test_actual_source_tamper_rejected(self):
  b=contract(self.root,'direct');p=self.root/'connected_enterprise/csv_backend029.py';old=p.read_bytes()
  try:
   p.write_bytes(old+b'\n# changed\n')
   with self.assertRaises(ValueError):validate_contract(self.root,b)
  finally:p.write_bytes(old)
 def test_unsupported_scope_not_admitted(self):
  offer=copy.deepcopy(self.offer);offer['scope']='intake_readiness';plan=order_plan(configured(self.root),self.job['id'],offer,None,1500000);self.assertNotEqual(plan['mode'],'csv_backend')
 def test_all_operator_controls_match_native_semantics(self):
  fields=['artifact','actual_execution_artifact_sha256','useful_outcome_sha256','native_delivered_artifact_sha256']
  ordinary=execute_offer(self.root,self.manifest,self.offer,self.job['id'],context={'mode':'conventional'})
  for arm in ('direct','equal_content','replanned','inherited'):
   r=execute_service(self.root,self.manifest,self.offer,self.job['id'],'conventional',contract(self.root,arm));self.assertTrue(r['accepted']);self.assertEqual({k:r[k] for k in fields},{k:ordinary[k] for k in fields})
if __name__=='__main__':unittest.main()
