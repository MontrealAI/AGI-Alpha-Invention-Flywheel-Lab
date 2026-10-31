"""Common service envelope is paid once; extra capability work remains charged."""
import copy
import unittest
from connected_enterprise.engine import default_config,validate_config
from connected_enterprise.mechanism_choice import MODES,COST_FIELDS,validate_policy,order_plan,execute_funded

def policy():
 costs={m:dict.fromkeys(COST_FIELDS,0) for m in MODES if m!='hold'}
 costs['ordinary_reuse'].update(retrieval=10000,verification=200000)
 costs['critic_retain'].update(discovery=1000000,integration=500000,verification=300000,maintenance=10000,retrieval=10000,failed_attempts=100000)
 return {'mode':'optimize','costs':costs,'accept_collect_bps':9700,'future_equivalent_jobs':0,'public_basis':'Authored conservative common service envelope, no measured savings',
 'cost_contract':{'schema':'connected-method-cost-contract/v1','basis':'COMMON_COMPLETE_PRODUCTION_REPLACEMENT','production_envelope_microUSD':1500000,'covered_operations':['produce','acceptance_check']}}

class CommonCost(unittest.TestCase):
 def test_common_zero_increment_still_paid_base(self):
  p=policy();validate_policy(p);cfg=default_config();cfg['mechanism_policy']=p;validate_config(cfg)
  plan=order_plan(p,'job',{'service_id':'reconciliation','method':'generated_schema','price_microUSD':10000000},None,2500000)
  self.assertEqual(plan['mode'],'conventional');self.assertEqual(plan['cost'],0)
  self.assertEqual(plan['problem']['jobs'][0]['base_cost'],2500000)
 def test_wrong_baseline_rejected(self):
  cfg=default_config();cfg['mechanism_policy']=policy();cfg['mechanism_policy']['cost_contract']['production_envelope_microUSD']+=1
  with self.assertRaises(ValueError):validate_config(cfg)
 def test_double_execution_rejected(self):
  p=policy();p['costs']['generated']['execution']=1
  with self.assertRaises(ValueError):validate_policy(p)
 def test_free_extra_work_rejected(self):
  for mode,key in [('ordinary_reuse','retrieval'),('ordinary_reuse','verification'),('critic_retain','verification'),('critic_retain','maintenance')]:
   p=policy();p['costs'][mode][key]=0
   with self.assertRaises(ValueError):validate_policy(p)
 def test_standalone_common_envelope_forbidden(self):
  p=policy()
  with self.assertRaisesRegex(ValueError,'NATIVE_PRODUCTION_PREPAYMENT'):
   execute_funded(None,None,None,{},'job',ident='x',day=0,mode='conventional',costs=p['costs']['conventional'],cost_contract=p['cost_contract'])
 def test_direct_does_not_reexecute_unused_memory(self):
  from unittest.mock import patch
  from commercial.ledger import digest
  p=policy();costs=p['costs']['conventional'];memory={'unused':'authenticated context not consumed'};offer={'service_id':'reconciliation'}
  receipt={'amount':1500000,'funding':'SEED'}
  request={'operation':'spend','id':'order-resources','kind':'production_contract','day':0,'amount':1500000,'work':{'job_id':'job','offer':offer,'production_envelope_microUSD':1500000,'method_plan':{'mode':'conventional','costs':costs,'memory':memory,'cost_contract':p['cost_contract']}}}
  class Account:
   def export(self):return {'connected_journal':{'entries':[{'request':request,'status':'COMPLETE','receipt':receipt}]}}
  with patch('connected_enterprise.mechanism_choice.checked_memory',side_effect=AssertionError('Unfunded memory work')),patch('connected_enterprise.mechanism_choice.execute_offer',return_value={'accepted':True}):
   result=execute_funded(None,{'jobs':[{'id':'job','service_id':'reconciliation'}]},Account(),offer,'job',ident='x',day=0,mode='conventional',costs=costs,memory=memory,prepaid_order='order',cost_contract=p['cost_contract'])
   self.assertTrue(result['accepted']);self.assertEqual(result['cost'],0)
   request['work']['production_envelope_microUSD']-=1
   with self.assertRaisesRegex(ValueError,'COMMON_PRODUCTION_PREPAYMENT_CHANGED'):
    execute_funded(None,{'jobs':[{'id':'job','service_id':'reconciliation'}]},Account(),offer,'job',ident='x',day=0,mode='conventional',costs=costs,memory=memory,prepaid_order='order',cost_contract=p['cost_contract'])
 def test_legacy_zero_increment_not_implicitly_enabled(self):
  p=policy();del p['cost_contract']
  with self.assertRaises(ValueError):validate_policy(p)

if __name__=='__main__':unittest.main()
