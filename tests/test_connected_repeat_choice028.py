"""Matched outside-option semantics, conditional continuation and cash authority."""
import copy
import unittest
from fractions import Fraction
from adaptive_enterprise.allocation import allocate
from connected_enterprise.repeat_choice import options,actual_choice,latent_atoms,evaluate,validate_public_state

CONTRACT={'schema':'connected-repeat-choice/v1','value_bps_atoms':[10000,15000],'budget_microUSD_atoms':[50000000,100000000],'self_service_fee_bps':3500,'self_service_effort_bps':1000,'self_service_quality_bps':8000,'self_service_success_bps':8500,'self_service_delay_hours':12,'switching_effort_microUSD':500000,'discount_bps':9800}
def public():
 outcomes=['us_paid','us_refund','self_success','self_failure','human','rival','decline']
 service={'job_id':'future-job','anchor':25000000,'rival_price':25000000,'base_cost':2000000}
 return {'anchor':25000000,'public_rival_price':25000000,'base_cost':2500000,'payment_bps':290,'payment_fixed':300000,'available':100000000,'reserve_buffer':1000000,'quote_cost':200000,'native_state_digest':'a'*64,'profit_tax_bps':2000,
  'repeat_state':{'customer_id':'c','spent_microUSD':0,'last_provider':None,'moment':0,'horizon_hours':336,'future_slots':dict.fromkeys(outcomes,1),'future_times':{**dict.fromkeys(outcomes,192),'decline':24},'retention_bps':9700,'arrival_bps':7000,'followup_eligible':True,'onboarding_credit':0,'same_service':service,'successor':{**service,'job_id':'next-job'},'observability':'Observed-only test fixture'}}
class RepeatChoice(unittest.TestCase):
 def test_actual_and_expected_share_exact_utility(self):
  c=copy.deepcopy(CONTRACT)
  for value in c['value_bps_atoms']:
   for budget in c['budget_microUSD_atoms']:
    rows=options(c,25000000,20000000,24000000,value,budget,None)
    actual=actual_choice(c,25000000,20000000,24000000,value,budget,None,lambda x:len(x))
    self.assertIn(actual,rows)
  c['self_service_fee_bps']=0
  rows=options(c,25000000,None,None,15000,0,None)
  self.assertEqual(rows[0]['provider'],'self_service');self.assertEqual(rows[0]['cash'],0)
 def test_effort_is_utility_not_cash(self):
  c=copy.deepcopy(CONTRACT);c.update(self_service_effort_bps=0,self_service_quality_bps=10000,self_service_success_bps=10000)
  row=options(c,10000000,None,None,15000,4000000,None)[0]
  self.assertEqual(row['provider'],'self_service');self.assertEqual(row['cash'],3500000)
  self.assertEqual(row['utility'],11500000)
 def test_public_spent_not_private_remaining(self):
  self.assertTrue(all(b>=0 for _,b,_ in latent_atoms(CONTRACT,60000000)))
  self.assertEqual(sum(w for _,_,w in latent_atoms(CONTRACT,60000000)),1)
  state=public()['repeat_state'];state['remaining_budget']=1
  with self.assertRaises(ValueError):validate_public_state(state)
 def test_one_opportunity_has_no_continuation(self):
  p=public();out=evaluate(CONTRACT,{'lookahead_opportunities':1,'price_bps':[5500,6999]},p,{'accept_prob':1,'collect_prob':1},15000000,3000000,19000000)
  self.assertEqual(out['continuation_delta'],0)
  # Sunk current evaluation costs cancel between bid/hold, not charged twice.
  p['quote_cost']+=1000000
  out2=evaluate(CONTRACT,{'lookahead_opportunities':1,'price_bps':[5500,6999]},p,{'accept_prob':1,'collect_prob':1},15000000,3000000,19000000)
  self.assertEqual(out['immediate_expected_net'],out2['immediate_expected_net'])
 def test_no_future_horizon_no_continuation(self):
  p=public();p['repeat_state']['horizon_hours']=1
  out=evaluate(CONTRACT,{'lookahead_opportunities':2,'price_bps':[5500,6999]},p,{'accept_prob':1,'collect_prob':1},15000000,3000000,19000000)
  self.assertEqual(out['continuation_delta'],0)
 def test_future_value_cannot_release_or_fund_cash(self):
  risk={'scenarios':{'central':10000},'worst_loss_limit':0,'downside_penalty_bps':0,'max_states':4,'authorized_allocation':100,'interactions':[]}
  obs={'scope':'SIMULATED','state_digest':'a'*64,'summary':{'available':10,'unrestrictedEarned':10}}
  option={'id':'delivery','kind':'delivery','upfront_cost':5,'later_liabilities':{'central':0},'future_net_cash':{'central':8},'benefit_ids':['j'],'requires':[],'exclusive_group':None,'authorized':True,'evidence':'source','execution':{'job_id':'j','customer_id':'c','payment_bps':0,'payment_fixed_microUSD':0,'onboarding_microUSD':0,'funding':'SEED_OR_EARNED','cash_lock':6,'ranking_only_scenario_value':{'central':1000000000}}}
  with self.assertRaises(ValueError):allocate(obs,[option],risk,allow_seed=True,max_delivery_slots=1)
  d=allocate(obs,[option],risk,allow_seed=True,max_delivery_slots=1,allow_ranking_only=True);self.assertEqual(d['selected'],[])
  obs['summary']['available']=11
  d=allocate(obs,[option],risk,allow_seed=True,max_delivery_slots=1,allow_ranking_only=True)
  self.assertEqual(d['reserve_amount'],11);self.assertEqual(d['expected_net'],3);self.assertEqual(d['predicted_scenario_cash'],{'central':3})
  self.assertEqual(d['ranking_only_expected_value'],'1000000000')

if __name__=='__main__':unittest.main()
