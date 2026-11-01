import copy,importlib.util,json,tempfile,unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch
from portfolio25.pricing import SCENARIOS
from adaptive_enterprise.allocation import default_riskpolicy
from adaptive_enterprise.strategies import offer_catalog
from connected_enterprise.strategic_commerce import select,rederive,allocate_actions,rederive_actions,_exact_belief_choice
ROOT=Path(__file__).resolve().parents[1]

def fixture(prices=None,base_cost=0):
 sc=copy.deepcopy(SCENARIOS[0]);sc.update(id='declared',weight=1,accept_prob=1,collect_prob=1,repeat_horizon=0,cost_shock=1)
 policy={'schema':'connected-strategic-commerce/v1','public_basis':'Finite authored arithmetic regression, no commercial calibration.','price_bps':[5000],'rival_price_bps':[10000],'rival_cost_bps':0,'rival_response':'observed_quote','scenarios':[sc],'ranking_arithmetic':'exact-rational-v1'}
 low,high=99990000009998,100000000009999
 profile={'id':'public-arithmetic','services':['reconciliation'],'price_grids':{'reconciliation':prices or [low,high]},'atoms':[{'weight_bps':9999,'budget_microUSD':high,'values':{'reconciliation':high+1}},{'weight_bps':1,'budget_microUSD':low,'values':{'reconciliation':low+1}}],'outside_options':[]}
 public={'anchor':200000000000000,'public_rival_price':200000000000000,'base_cost':base_cost,'payment_bps':0,'payment_fixed':0,'available':10**15,'reserve_buffer':0,'quote_cost':0,'native_state_digest':'a'*64,'profit_tax_bps':0}
 offer=next(o for o in offer_catalog() if o['service_id']=='reconciliation')
 return policy,offer,public,{'profile':profile,'observed_spend':0,'rival_available':True}

def pick(data):
 p,o,u,c=data
 return select(p,None,'job',o,None,u,market_context=c)

class ExactSelection048(unittest.TestCase):
 def test_rational_order_breaks_rounded_high_dollar_tie(self):
  data=fixture();exact=pick(data);legacy=copy.deepcopy(data);legacy[0].pop('ranking_arithmetic');old=pick(legacy)
  self.assertEqual(old['candidates'][0]['expected_net'],old['candidates'][1]['expected_net'])
  self.assertEqual(old['offer']['price_microUSD'],99990000009998)
  self.assertEqual(exact['offer']['price_microUSD'],100000000009999)
  self.assertEqual(Fraction(exact['candidates'][1]['expected_net_fraction'])-Fraction(exact['candidates'][0]['expected_net_fraction']),Fraction(1,10000))
  rederive(json.loads(json.dumps(exact)))
 def test_exact_scenario_floor_never_rounds_future_receipts_up(self):
  data=fixture([100000000000001]);data[3]['profile']['atoms'][0]['budget_microUSD']=100000000000001
  r=pick(data);row=r['candidates'][0]
  self.assertEqual(row['forecasts'][0]['net_after_modeled_tax'],99990000000001.0)
  obs={'scope':'SIMULATED','state_digest':'a'*64,'summary':{'available':10**15,'unrestrictedEarned':0}}
  risk=default_riskpolicy();risk.update(scenarios={'declared':10000},authorized_allocation=10**15)
  d={'id':'delivery','customer_id':'buyer','onboarding':0,'exclusive_group':'buyer','selection':r,'requires':[]}
  allocation=allocate_actions(obs,[d],[],risk);rederive_actions(allocation)
  self.assertEqual(allocation['decision']['predicted_scenario_cash']['declared'],99990000000000)
 def test_atoms_with_spent_budget_and_outside_ties_are_exact(self):
  data=fixture([10]);p=data[3]['profile'];p['atoms']=[{'weight_bps':10000,'budget_microUSD':11,'values':{'reconciliation':10}}]
  self.assertEqual(Fraction(pick(data)['candidates'][0]['forecasts'][0]['win_probability_fraction']),Fraction(1,2))
  data[3]['observed_spend']=2
  self.assertIsNone(pick(data)['offer'])
  self.assertEqual(pick(data)['candidates'][0]['forecasts'][0]['win_probability_fraction'],'0')
 def test_exact_interval_quote_uses_declared_values_only(self):
  data=fixture();p,o,u,_=data;p.update(demand_model='connected_range',connected_beliefs={'declared':{'min_value_bps':0,'max_value_bps':20000,'min_budget_microUSD':0,'max_budget_microUSD':10**15,'rival_available_bps':0}})
  expected=Fraction(3,4)*Fraction(9,10)
  self.assertEqual(_exact_belief_choice(10**14,2*10**14,u,p,p['scenarios'][0])[0],expected)
  r=select(p,None,'job',o,None,u);self.assertEqual(r['candidates'][0]['forecasts'][0]['win_probability_fraction'],str(expected))
 def test_all_costs_and_declared_probabilities_enter_exact_certificate(self):
  data=fixture([100]);data[2].update(base_cost=20,payment_bps=333,payment_fixed=2,quote_cost=7,profit_tax_bps=2300)
  data[0]['scenarios'][0].update(accept_prob=.97,collect_prob=.93)
  row=pick(data)['candidates'][0];paid=Fraction(97,100)*Fraction(93,100);cost=20+4+2
  expected=paid*100-cost-paid*(100-cost)*Fraction(23,100)-7
  self.assertEqual(Fraction(row['expected_net_fraction']),expected)
 def test_current_cash_remains_authoritative(self):
  data=fixture();data[2]['available']=1
  r=pick(data);self.assertIsNone(r['offer']);self.assertEqual(r['candidates'],[])
 def test_forged_fraction_or_rounded_display_is_rejected(self):
  r=pick(fixture())
  for key,value in [('expected_net_fraction','1000000000000000'),('expected_net',0)]:
   bad=copy.deepcopy(r);bad['candidates'][0][key]=value
   with self.assertRaisesRegex(ValueError,'STRATEGIC_COMMERCE_DECISION_CHANGED'):rederive(bad)
 def test_exact_mode_does_not_read_private_future_atom(self):
  with patch('connected_enterprise.complete_offer_market.private_atom',side_effect=AssertionError('private atom read')):
   self.assertIsNotNone(pick(fixture())['offer'])
  data=fixture();data[2]['actual_future_draw']=0
  with self.assertRaisesRegex(ValueError,'ONLY_EXPLICIT_PUBLIC_OBSERVATIONS_ALLOWED'):pick(data)
 def test_legacy_record_has_no_new_exact_fields(self):
  data=fixture();data[0].pop('ranking_arithmetic');r=pick(data)
  self.assertNotIn('ranking_arithmetic',r['decision']);self.assertNotIn('expected_net_fraction',r['candidates'][0]);rederive(r)
 def test_unsupported_models_and_repeat_semantics_stay_closed(self):
  p,o,u,c=fixture()
  with self.assertRaisesRegex(ValueError,'EXACT_LOGIT_FORECAST_UNAVAILABLE'):select(p,None,'job',o,None,u)
  bad=copy.deepcopy(p);bad['rival_response']='finite_best_response'
  with self.assertRaisesRegex(ValueError,'EXACT_RANKING_REQUIRES'):select(bad,None,'job',o,None,u,market_context=c)
  bad=copy.deepcopy(p);bad['scenarios'][0]['repeat_horizon']=1
  with self.assertRaisesRegex(ValueError,'SINGLE_ORDER_EXACT_PREPAID_COST_EDITION_REQUIRED'):select(bad,None,'job',o,None,u,market_context=c)
 def test_exact_probability_weights_cannot_hide_approximate_total(self):
  p,o,u,c=fixture();p['scenarios'][0]['weight']=.999999999
  with self.assertRaisesRegex(ValueError,'EXACT_SCENARIO_WEIGHTS_MUST_SUM_ONE'):select(p,None,'job',o,None,u,market_context=c)
 def test_native_operation_and_independent_audit(self):
  from adaptive_enterprise.instruments import prepare_complete_offer_services
  from connected_enterprise.engine import run_world
  from connected_enterprise.verify import audit
  spec=importlib.util.spec_from_file_location('exact048_operating_fixture',ROOT/'tests/test_connected_complete_offer.py')
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);operating_fixture=module.fixture
  with tempfile.TemporaryDirectory(prefix='.exact-selection-',dir=ROOT) as tmp:
   folder=Path(tmp);m=prepare_complete_offer_services(ROOT,str(folder.relative_to(ROOT)/'jobs'),cohort_seed=261101048,packet_jobs=8,packet_rows=12)
   cfg=operating_fixture(m,'menu');cfg['strategic_policy']['ranking_arithmetic']='exact-rational-v1'
   r=run_world(ROOT,m,cfg,261101048,'competitive_growth',folder/'world')
   self.assertTrue(r['orders']);self.assertTrue(audit(ROOT,m,r)['accepted'])
   resumed=run_world(ROOT,m,cfg,261101048,'competitive_growth',folder/'world')
   self.assertEqual(r['summary'],resumed['summary']);self.assertEqual(r['owned_account'],resumed['owned_account']);self.assertTrue(audit(ROOT,m,resumed)['accepted'])
   bad=copy.deepcopy(r);plan=next(iter(bad['joint_actions'].values()));row=plan['allocation']['deliveries'][0]['selection']['candidates'][0];row['expected_net_fraction']=str(Fraction(row['expected_net_fraction'])+1)
   with self.assertRaises(ValueError):audit(ROOT,m,bad)

if __name__=='__main__':unittest.main()
