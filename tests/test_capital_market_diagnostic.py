import unittest
from unittest.mock import patch
from connected_enterprise.capital_lifecycle import capital_metrics
class MarketDiagnostic(unittest.TestCase):
 def run_case(self,available,required):
  summary=dict(cash=available,available=available,unrestrictedEarned=0,tailReserve=0,custodyReserve=0,workingCapital=0,payables=0)
  context={'profile':'public-declared-context'}
  problem=dict(policy={},method_policy=None,job_id='job',offer={},memory=None,public={'available':available},market_context=context)
  result={'owned_account':{'ledger':{'actions':[]}},'summary':summary,'decisions':[],'config':{},'joint_actions':{'one':{'time':0,'allocation':{'deliveries':[{'customer_id':'buyer','selection':{'decision':{'selected':None},'problem':problem}}]}}}}
  with patch('connected_enterprise.strategic_commerce.select',return_value={'decision':{'selected':{'required_current_cash':required}}}) as select:
   metrics=capital_metrics(result)
  self.assertEqual(select.call_args.kwargs['market_context'],context)
  self.assertGreaterEqual(select.call_args.args[5]['available'],available)
  return metrics['individually_cash_infeasible_positive_quotes']
 def test_same_market_and_no_false_positive_when_cash_ample(self):self.assertEqual(self.run_case(5000,27),[])
 def test_actual_cash_is_never_reduced_by_diagnostic(self):self.assertEqual(self.run_case(10**18,10**17),[])
 def test_narrow_isolated_quote_cash_failure_preserved(self):self.assertEqual(self.run_case(20,27)[0]['positive_option_cash_required'],27)
if __name__=='__main__':unittest.main()
