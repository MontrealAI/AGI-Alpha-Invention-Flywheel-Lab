import copy,hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from commercial.ledger import digest
from adaptive_enterprise.allocation import allocate,default_riskpolicy
from adaptive_enterprise.strategies import offer_catalog
from connected_enterprise.joint_planning import category_upfront_caps,validate_allocation_policy
from connected_enterprise.strategic_commerce import allocate_actions,rederive_actions,select,cash_opportunity_diagnostic
from connected_enterprise.refusal_recourse import recourse,selective_decision,SELECTIVE_SCHEMA
from portfolio25.pricing import SCENARIOS
ROOT=Path(__file__).resolve().parents[1]

def fixture():
 obs={'scope':'SIMULATED','state_digest':'a'*64,'summary':{'available':1000,'unrestrictedEarned':100}}
 risk=default_riskpolicy();risk.update(scenarios={'s':10000},worst_loss_limit=1000,downside_penalty_bps=0,authorized_allocation=1000)
 def option(ident,kind,cost,net):return {'id':ident,'kind':kind,'upfront_cost':cost,'later_liabilities':{'s':0},'future_net_cash':{'s':cost+net},'benefit_ids':[ident+'-benefit'],'requires':[],'exclusive_group':None,'authorized':True,'evidence':'declared-test-contract','execution':{'funding':'EARNED'}}
 options=[option('capacity-1','capacity',30,40),option('capacity-2','capacity',30,35),option('channel','acquisition',40,80)]
 return obs,risk,options

def delivery(ident,obs,anchor=100):
 sc=copy.deepcopy(SCENARIOS[0]);sc.update(id='s',weight=1,accept_prob=1,collect_prob=1,repeat_horizon=0,cost_shock=1)
 p={'schema':'connected-strategic-commerce/v1','public_basis':'Declared finite unit-test public beliefs.','price_bps':[5000],'rival_price_bps':[10000],'rival_cost_bps':0,'rival_response':'observed_quote','scenarios':[sc],'demand_model':'connected_range','connected_beliefs':{'s':{'min_value_bps':20000,'max_value_bps':20000,'min_budget_microUSD':1000,'max_budget_microUSD':1000,'rival_available_bps':0}},'ranking_arithmetic':'exact-rational-v1'}
 pub={'anchor':anchor,'public_rival_price':anchor,'base_cost':1,'payment_bps':0,'payment_fixed':0,'available':obs['summary']['available'],'reserve_buffer':0,'quote_cost':0,'native_state_digest':obs['state_digest'],'profit_tax_bps':0}
 offer=next(o for o in offer_catalog() if o['service_id']=='reconciliation' and o['method']=='canonical')
 return {'id':ident,'customer_id':ident,'onboarding':0,'exclusive_group':ident,'selection':select(p,None,'job-'+ident,offer,None,pub),'requires':[]}

class CategoryBudgetUnitTests(unittest.TestCase):
 def test_category_caps_bind_sum_not_each_individual_invoice(self):
  obs,risk,options=fixture();before=copy.deepcopy((obs,risk,options))
  all_actions=allocate(obs,options,risk,allow_seed=True)
  self.assertEqual(all_actions['selected'],['capacity-1','capacity-2','channel'])
  caps={'acquisition':50,'capacity':50};limited=allocate(obs,options,risk,allow_seed=True,category_upfront_caps=caps)
  self.assertEqual(limited['selected'],['capacity-1','channel']);self.assertEqual(limited['category_upfront_caps'],caps)
  self.assertEqual((obs,risk,options),before);self.assertEqual(limited['upfront_cost'],70)
 def test_default_result_bytes_remain_legacy_when_unset(self):
  obs,risk,options=fixture();r=allocate(obs,options,risk,allow_seed=True)
  self.assertEqual(r,allocate(obs,options,risk,allow_seed=True,category_upfront_caps=None));self.assertNotIn('category_upfront_caps',r)
  self.assertEqual(digest(r),'5fcd6ffcd898575bfeea48d15e6932854c0fa5c7fed95b1e8bba2a6e823ead43')
 def test_derivation_uses_current_eligible_earnings_after_operating_only(self):
  obs,risk,_=fixture();policy={'risk':risk,'max_customers':1,'category_budgets_bps':{'acquisition':3333,'capacity':6667}}
  self.assertEqual(category_upfront_caps(policy,obs,7),{'acquisition':30,'capacity':62})
  self.assertEqual(category_upfront_caps(policy,obs,101),{'acquisition':0,'capacity':0})
  obs['summary']['profit']=10**15;obs['summary']['available']=2
  self.assertEqual(category_upfront_caps(policy,obs,7),{'acquisition':30,'capacity':62})
  self.assertIsNone(category_upfront_caps({'risk':risk,'max_customers':1},obs,7))
 def test_invalid_shares_and_caps_fail_closed(self):
  obs,risk,options=fixture()
  for shares in ({'acquisition':5000},{'acquisition':-1,'capacity':10001},{'acquisition':5000,'capacity':4999},{'acquisition':True,'capacity':9999},{'delivery':5000,'capacity':5000}):
   with self.assertRaises(ValueError):validate_allocation_policy({'risk':risk,'max_customers':1,'category_budgets_bps':shares})
  for caps in ({},{'acquisition':1,'capacity':True},{'acquisition':-1,'capacity':2}):
   with self.assertRaises(ValueError):allocate(obs,options,risk,allow_seed=True,category_upfront_caps=caps)
 def test_zero_cap_holds_cash_and_hash_binds_same_selected_actions(self):
  obs,risk,options=fixture();zero=allocate(obs,options,risk,allow_seed=True,category_upfront_caps={'acquisition':0,'capacity':0})
  self.assertEqual(zero['selected'],[]);self.assertEqual(zero['reserve_amount'],0);self.assertIsNone(zero['authorized_digest'])
  one=allocate(obs,options[:1],risk,allow_seed=True,category_upfront_caps={'acquisition':0,'capacity':30});two=allocate(obs,options[:1],risk,allow_seed=True,category_upfront_caps={'acquisition':0,'capacity':31})
  self.assertEqual(one['selected'],two['selected']);self.assertNotEqual(one['plan_id'],two['plan_id'])
 def test_caps_never_relax_total_cash_earned_liability_or_risk(self):
  obs,risk,options=fixture();caps={'acquisition':1000,'capacity':1000}
  obs['summary']['available']=29;self.assertEqual(allocate(obs,options,risk,allow_seed=True,category_upfront_caps=caps)['selected'],[])
  obs['summary'].update(available=1000,unrestrictedEarned=29);self.assertEqual(allocate(obs,options,risk,allow_seed=True,category_upfront_caps=caps)['selected'],[])
  obs['summary']['unrestrictedEarned']=100;options[0]['later_liabilities']['s']=1000
  self.assertNotIn('capacity-1',allocate(obs,options,risk,allow_seed=True,category_upfront_caps=caps)['selected'])
  options[0]['later_liabilities']['s']=0;options[0]['future_net_cash']['s']=-100;small=copy.deepcopy(risk);small['worst_loss_limit']=1
  self.assertNotIn('capacity-1',allocate(obs,[options[0]],small,allow_seed=True,category_upfront_caps=caps)['selected'])
 def test_duplicate_and_mandatory_constraints_are_preserved(self):
  obs,risk,options=fixture();caps={'acquisition':50,'capacity':50}
  with self.assertRaisesRegex(ValueError,'DUPLICATE_ALLOCATION_ACTION'):allocate(obs,options+[copy.deepcopy(options[0])],risk,allow_seed=True,category_upfront_caps=caps)
  kept=allocate(obs,options,risk,allow_seed=True,category_upfront_caps=caps,mandatory_ids=['capacity-2']);self.assertIn('capacity-2',kept['selected']);self.assertNotIn('capacity-1',kept['selected'])
  blocked=allocate(obs,options,risk,allow_seed=True,category_upfront_caps={'acquisition':0,'capacity':0},mandatory_ids=['capacity-2']);self.assertEqual(blocked['optimality_scope'],'NONE');self.assertIsNone(blocked['authorized_digest'])
 def test_game_feasible_set_obeys_caps(self):
  obs,risk,options=fixture();game={'schema':'connected-finite-follower-regret/v1','public_basis':'Finite no-change unit-test forecast response.','max_response_states':1000,'scenarios':{'s':{'budget':0,'responses':[{'id':'unchanged','haircut_bps':{},'capture_bps':0,'cost':0}]}}}
  r=allocate(obs,options,risk,allow_seed=True,category_upfront_caps={'acquisition':50,'capacity':50},strategic_game=game)
  self.assertEqual(r['selected'],['capacity-1','channel']);self.assertIn('strategic_game_certificate',r)
 def test_recourse_keeps_caps_investments_and_accepted_orders(self):
  obs,risk,options=fixture();ds=[delivery('a',obs,120),delivery('b',obs,110),delivery('c',obs,100)]
  original=allocate_actions(obs,ds,options,risk,max_delivery_slots=2,category_upfront_caps={'acquisition':50,'capacity':50});rederive_actions(original)
  picks=[o for o in original['decision']['selected_options'] if o['kind']=='delivery'];self.assertEqual(len(picks),2)
  bycustomer={o['execution']['customer_id']:o for o in picks}
  responses=[{'customer_id':'a','option_id':bycustomer['a']['id'],'accepted':True},{'customer_id':'b','option_id':bycustomer['b']['id'],'accepted':False}]
  renewed=recourse(original,responses);rederive_actions(renewed)
  self.assertEqual(renewed['category_upfront_caps'],original['category_upfront_caps']);self.assertIn(bycustomer['a']['id'],renewed['decision']['selected'])
  for option in original['decision']['selected_options']:
   if option['kind']!='delivery':self.assertIn(option['id'],renewed['decision']['selected'])
  self.assertTrue(any(o['kind']=='delivery' and o['execution']['customer_id']=='c' for o in renewed['decision']['selected_options']))
  selective_decision(original,{'schema':SELECTIVE_SCHEMA,'daily_planning_cost':1,'daily_evaluation_cost':1},['a','b','c'])
 def test_record_tampering_and_cash_diagnostics_fail_closed(self):
  obs,risk,options=fixture();record=allocate_actions(obs,[],options,risk,category_upfront_caps={'acquisition':50,'capacity':50})
  bad=copy.deepcopy(record);bad['category_upfront_caps']['capacity']+=1
  with self.assertRaisesRegex(ValueError,'JOINT_ALLOCATION_CHANGED'):rederive_actions(bad)
  with self.assertRaisesRegex(ValueError,'CATEGORY_BUDGET_CASH_DIAGNOSTIC_UNAVAILABLE'):cash_opportunity_diagnostic(record,relaxed_available=2000,declared_allocation_ceiling=2000)
  with self.assertRaisesRegex(ValueError,'CATEGORY_BUDGET_CASH_DIAGNOSTIC_UNAVAILABLE'):allocate(obs,options,risk,allow_seed=True,category_upfront_caps={'acquisition':50,'capacity':50},_diagnostic_cash_limit=2000)

class CategoryBudgetNativeTests(unittest.TestCase):
 def test_actual_capped_invoices_exact_account_audit_and_resume(self):
  from adaptive_enterprise.instruments import prepare_complete_offer_services
  from connected_enterprise.engine import run_world,fresh_account_config
  from connected_enterprise.verify import audit
  spec=importlib.util.spec_from_file_location('category_fixture050',ROOT/'tests/test_connected_composed_window049.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory(prefix='.category-budget050-',dir=ROOT) as temporary:
   folder=Path(temporary);m=prepare_complete_offer_services(ROOT,str(folder.relative_to(ROOT)/'jobs'),cohort_seed=261101050,packet_jobs=24,packet_rows=12)
   exact,m=fresh_account_config(m,root=ROOT);cfg=module.config(m,False);cfg.update(horizon_days=8,monetary_policy=exact['monetary_policy'],cash_diagnostic_available=exact['opening']);cfg['strategic_allocation_policy']['category_budgets_bps']={'acquisition':5000,'capacity':5000}
   result=run_world(ROOT,m,cfg,261101050,'competitive_growth',folder/'world');self.assertTrue(audit(ROOT,m,result)['accepted']);self.assertTrue(result['investments'])
   self.assertTrue(audit(ROOT,m,json.loads(json.dumps(result,sort_keys=True)))['accepted'])
   diagnostics=result['capital_metrics']['decision_local_cash_opportunities'];self.assertEqual(len(diagnostics),8)
   self.assertTrue(all(d['diagnostic']=={'status':'UNAVAILABLE','reason':'CATEGORY_BUDGET_CASH_DIAGNOSTIC_UNAVAILABLE'} for d in diagnostics))
   for wrapper in result['joint_actions'].values():
    record=wrapper['allocation'];caps=category_upfront_caps(cfg['strategic_allocation_policy'],record['observation'],wrapper['operating_envelope']);self.assertEqual(record['category_upfront_caps'],caps)
    for kind,cap in caps.items():self.assertLessEqual(sum(o['upfront_cost'] for o in record['decision']['selected_options'] if o['kind']==kind),cap)
   bad=copy.deepcopy(result);old_id=next(iter(bad['joint_actions']));wrapper=bad['joint_actions'].pop(old_id);record=wrapper['allocation'];forged=copy.deepcopy(record['category_upfront_caps']);forged['capacity']+=1
   wrapper['allocation']=allocate_actions(record['observation'],record['deliveries'],record['investments'],record['riskpolicy'],allow_seed=record['allow_seed'],max_delivery_slots=record['max_delivery_slots'],earned_deduction=record['earned_deduction'],strategic_game=record.get('strategic_game'),category_upfront_caps=forged)
   wrapper['id']=digest(wrapper['allocation']);bad['joint_actions'][wrapper['id']]=wrapper
   with self.assertRaisesRegex(ValueError,'CATEGORY_BUDGET_CAPS_NOT_FROM_CURRENT_EARNINGS'):audit(ROOT,m,bad)
   again=run_world(ROOT,m,cfg,261101050,'competitive_growth',folder/'world');self.assertEqual(result['owned_account'],again['owned_account']);self.assertEqual(result['capital_metrics'],again['capital_metrics']);self.assertTrue(audit(ROOT,m,again)['accepted'])

if __name__=='__main__':unittest.main()
