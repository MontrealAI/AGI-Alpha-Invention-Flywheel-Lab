"""Falsifiers for auditable commercial-revolution witness, not invented real receipts."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from flywheel_wheel.revolution import (RevolutionError, canonical, digest, integer,
                                       settled_orders, witness_from_rederived, main)


def fixture():
    actions = [
        {'op': 'event', 'seq': 0, 'day': 12, 'args': {'id': 'order-0001', 'action': 'release'}},
        {'op': 'finish', 'seq': 1, 'day': 24, 'args': {'id': 'connected014-resource-sample', 'amount': 3000000}},
        {'op': 'event', 'seq': 2, 'day': 63, 'args': {'id': 'order-0002', 'action': 'release'}},
    ]
    summary = {'collections': 12000000, 'profit': 1200000, 'unrestrictedEarned': 1700000}
    receipt = {'funding': 'EARNED', 'plan_id': 'connected014-resource-sample', 'amount': 3000000,
               'day': 24, 'native_event_sequence': 1, 'native_actions_sha256': digest(actions[:2])}
    orders = [
        {'id': 'order-0001', 'qualified_time': 2, 'acceptance_time': 5, 'collection_time': 12,
         'outcome': 'SETTLED', 'price': 7000000, 'complete_cost': 800000,
         'service_receipt': {'accepted': True}},
        {'id': 'order-0002', 'qualified_time': 43, 'acceptance_time': 45, 'collection_time': 63,
         'outcome': 'SETTLED', 'price': 5000000, 'complete_cost': 600000,
         'service_receipt': {'accepted': True},
         'acquisition_source_plan_id': 'connected014-resource-sample'},
    ]
    investment = {'id': 'acquisition-001', 'kind': 'acquisition',
                  'plan_id': 'connected014-resource-sample', 'cost': 3000000,
                  'purchased_time': 24, 'funding_receipt': receipt}
    result = {'schema': 'agi-alpha/connected014-result/v1', 'scope': 'CONDITIONAL_SIMULATION',
              'complete': True, 'orders': orders, 'investments': [investment], 'summary': summary,
              'owned_account': {'ledger': {'actions': actions, 'actions_sha256': digest(actions),
                                           'summary': summary}}}
    grow = {'scope': 'SIMULATED_EXACT_NATIVE_RECORDS',
            'native_actions_sha256': digest(actions),
            'cohorts': {'investment_attribution': [{
                'investment_id': 'acquisition-001', 'kind': 'acquisition',
                'plan_id': 'connected014-resource-sample', 'cost_microUSD': 3000000,
                'subsequent_collected_order_ids': ['order-0002'],
                'attributed_collections_microUSD': 5000000}]}}
    return result, grow


class RevolutionTests(unittest.TestCase):
    def test_real_source_linked_simulated_revolution(self):
        r,g=fixture();w=witness_from_rederived(r,g,'261031-001-growth')
        self.assertEqual(w['status'],'SOURCE_LINKED_SIMULATED_REVOLUTION_WITNESSED')
        self.assertEqual(w['closed_source_linked_revolutions'],1)
        self.assertEqual([x['stage'] for x in w['investments'][0]['trace']],
                         ['EARLIER_ACCEPTED_COLLECTION','EARNED_FUNDED_NATIVE_RESOURCE_COMMITMENT',
                          'SUBSEQUENT_ACCEPTED_AND_COLLECTED_WORK'])
        self.assertFalse(w['funding_authority']);self.assertIsNone(w['actual_profit_microUSD'])
        self.assertEqual(w['causal_extra_profit'],'NOT_ESTABLISHED_WITHOUT_MATCHED_COUNTERFACTUAL')

    def test_no_investment_is_not_closed_revolution(self):
        r,g=fixture();r['investments']=[];g['cohorts']['investment_attribution']=[]
        w=witness_from_rederived(r,g,'case-0')
        self.assertEqual(w['status'],'NO_EARNED_FINANCED_INVESTMENT_IN_THIS_WORLD')
        self.assertEqual(w['closed_source_linked_revolutions'],0)

    def test_seed_financed_investment_does_not_claim_earned_flywheel(self):
        r,g=fixture();r['investments'][0]['funding_receipt']['funding']='SEED'
        w=witness_from_rederived(r,g,'case-0')
        self.assertEqual(w['earned_investments'],0)
        self.assertEqual(w['closed_source_linked_revolutions'],0)

    def test_no_later_collected_order_means_open_loop(self):
        r,g=fixture();r['orders'][1]['outcome']='REFUNDED';r['orders'][1]['collection_time']=None
        r['owned_account']['ledger']['actions']=r['owned_account']['ledger']['actions'][:2]
        r['owned_account']['ledger']['actions_sha256']=digest(r['owned_account']['ledger']['actions'])
        g['native_actions_sha256']=r['owned_account']['ledger']['actions_sha256']
        g['cohorts']['investment_attribution'][0]['subsequent_collected_order_ids']=[]
        g['cohorts']['investment_attribution'][0]['attributed_collections_microUSD']=0
        w=witness_from_rederived(r,g,'case-0')
        self.assertEqual(w['status'],'EARNED_INVESTMENT_WITHOUT_COMPLETE_LINK')

    def test_no_prior_collection_means_no_closed_loop(self):
        r,g=fixture();r['orders'][0]['outcome']='REFUNDED';r['orders'][0]['collection_time']=None
        r['owned_account']['ledger']['actions']=r['owned_account']['ledger']['actions'][1:]
        for i,a in enumerate(r['owned_account']['ledger']['actions']):a['seq']=i
        r['investments'][0]['funding_receipt']['native_event_sequence']=0
        r['investments'][0]['funding_receipt']['native_actions_sha256']=digest(r['owned_account']['ledger']['actions'][:1])
        r['owned_account']['ledger']['actions_sha256']=digest(r['owned_account']['ledger']['actions'])
        g['native_actions_sha256']=r['owned_account']['ledger']['actions_sha256']
        w=witness_from_rederived(r,g,'case-0')
        self.assertEqual(w['closed_source_linked_revolutions'],0)

    def test_later_unaccepted_work_cannot_close(self):
        r,g=fixture();r['orders'][1]['service_receipt']['accepted']=False
        with self.assertRaisesRegex(RevolutionError,'SETTLEMENT_WITHOUT_ACCEPTED'):
            witness_from_rederived(r,g,'case-0')

    def test_invented_simulated_collection_without_release_is_rejected(self):
        r,g=fixture();r['orders'][1]['collection_time']=64
        with self.assertRaisesRegex(RevolutionError,'SETTLEMENT_WITHOUT_NATIVE_RELEASE'):
            witness_from_rederived(r,g,'case-0')

    def test_invalid_native_receipt_prefix(self):
        r,g=fixture();r['investments'][0]['funding_receipt']['native_actions_sha256']='f'*64
        with self.assertRaisesRegex(RevolutionError,'EARNED_NATIVE_PREFIX_CHANGED'):
            witness_from_rederived(r,g,'case-0')

    def test_falsified_investment_after_native_action(self):
        r,g=fixture();r['investments'][0]['purchased_time']=25
        with self.assertRaisesRegex(RevolutionError,'EARNED_NATIVE_RECEIPT_TERMS_CHANGED'):
            witness_from_rederived(r,g,'case-0')

    def test_attribution_double_count_forgery(self):
        r,g=fixture();g['cohorts']['investment_attribution'][0]['attributed_collections_microUSD']=9_000_000
        with self.assertRaisesRegex(RevolutionError,'ATTRIBUTION_COLLECTIONS_CHANGED'):
            witness_from_rederived(r,g,'case-0')

    def test_native_actions_digest_binding(self):
        r,g=fixture();g['native_actions_sha256']='0'*64
        with self.assertRaisesRegex(RevolutionError,'NATIVE_ACTION_BINDING_MISMATCH'):
            witness_from_rederived(r,g,'case-0')

    def test_profit_is_not_cash_authority(self):
        r,g=fixture();r['summary']['profit']=9_000_000_000
        self.assertFalse(witness_from_rederived(r,g,'case-0')['funding_authority'])

    def test_no_real_commerce_from_simulated_witness(self):
        r,g=fixture();w=witness_from_rederived(r,g,'case-0')
        self.assertEqual(w['actual_customers'],0)
        self.assertEqual(w['actual_collections_microUSD'],0)
        self.assertIsNone(w['current_successor_proof'])
        self.assertEqual(w['authority'],[])

    def test_invalid_world_name_rejected(self):
        r,g=fixture()
        for name in ('../other','x/y','', 'x'*161):
            with self.subTest(name=name),self.assertRaises(RevolutionError):
                witness_from_rederived(r,g,name)

    def test_no_untrusted_native_execution(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch('flywheel_wheel.revolution.live_witness') as call:
                self.assertEqual(main(['--enterprise',d,'--world','case-0','--output',str(Path(d)/'view')]),2)
                call.assert_not_called()

    def test_untrusted_world_namespace_in_live_witness_refused(self):
        from flywheel_wheel.revolution import live_witness
        with self.assertRaises(RevolutionError):live_witness('/tmp','../other')

    def test_integer_guard_rejects_boolean(self):
        self.assertFalse(integer(True))
        self.assertFalse(integer(2.0))
        self.assertTrue(integer(2))

if __name__=='__main__':unittest.main()
