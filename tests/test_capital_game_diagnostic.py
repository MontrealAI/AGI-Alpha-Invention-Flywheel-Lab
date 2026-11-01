"""Optional unsupported analysis must not invalidate completed operating work."""
import copy
import unittest
from unittest.mock import patch
from connected_enterprise.capital_lifecycle import capital_metrics

class GameDiagnosticReporting(unittest.TestCase):
 def fixture(self,game=True):
  summary=dict(cash=100,available=90,unrestrictedEarned=0,tailReserve=0,custodyReserve=0,workingCapital=10,payables=0)
  record={'observation':{'summary':summary},'deliveries':[]}
  if game:record['strategic_game']={'schema':'source-bound-game'}
  return {'owned_account':{'ledger':{'actions':[]}},'summary':summary,'decisions':[],
   'config':{'cash_diagnostic_available':1000,'strategic_allocation_policy':{'risk':{'authorized_allocation':500}}},
   'joint_actions':{'one':{'time':0,'allocation':record,'operating_envelope':10}}}
 def test_game_reports_unavailable_without_counterfactual_or_operation_failure(self):
  result=self.fixture();before=copy.deepcopy(result)
  with patch('connected_enterprise.strategic_commerce.cash_opportunity_diagnostic',side_effect=ValueError('STRATEGIC_GAME_CASH_DIAGNOSTIC_UNAVAILABLE')) as diagnostic:
   metrics=capital_metrics(result)
  diagnostic.assert_not_called();self.assertEqual(result,before)
  row=metrics['decision_local_cash_opportunities'][0]
  self.assertEqual(row,{'time':0,'diagnostic':{'status':'UNAVAILABLE','reason':'STRATEGIC_GAME_CASH_DIAGNOSTIC_UNAVAILABLE'}})
 def test_supported_diagnostic_preserved(self):
  expected={'status':'EXACT','incremental_value':23}
  with patch('connected_enterprise.strategic_commerce.cash_opportunity_diagnostic',return_value=expected) as diagnostic:
   metrics=capital_metrics(self.fixture(False))
  self.assertEqual(metrics['decision_local_cash_opportunities'],[{'time':0,'diagnostic':expected}]);diagnostic.assert_called_once()
 def test_unrelated_diagnostic_failure_is_not_suppressed(self):
  with patch('connected_enterprise.strategic_commerce.cash_opportunity_diagnostic',side_effect=ValueError('BAD_NATIVE_PREFIX')):
   with self.assertRaisesRegex(ValueError,'BAD_NATIVE_PREFIX'):capital_metrics(self.fixture(False))
 def test_unrequested_diagnostic_remains_absent(self):
  result=self.fixture();del result['config']['cash_diagnostic_available']
  with patch('connected_enterprise.strategic_commerce.cash_opportunity_diagnostic') as diagnostic:
   self.assertEqual(capital_metrics(result)['decision_local_cash_opportunities'],[])
  diagnostic.assert_not_called()
if __name__=='__main__':unittest.main()
