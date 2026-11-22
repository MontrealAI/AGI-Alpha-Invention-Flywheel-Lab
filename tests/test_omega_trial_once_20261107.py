"""Registered first-invoice versus renewal-policy ablation; no original accounts."""
from __future__ import annotations

from copy import deepcopy
import unittest

from connected_enterprise.channels import default_contracts
from mechanism_harness import reach_policy, reach_verify


class _ReadOnlyLedger:
    def __init__(self, prefix):
        self._prefix = prefix
    def prefix(self):
        return self._prefix
    def spend(self, *args, **kwargs):
        raise AssertionError("A registered one-tranche control cannot spend on a second right")


class TrialOnceDecisionTests(unittest.TestCase):
    def setUp(self):
        self.invoice = 6_250_000
        self.prefix = {
            'sequence': 73,
            'actions_sha256': 'dated-prefix-fixture-only',
            'available_microUSD': 80_000_000,
            'earned_microUSD': 30_000_000,
        }
        self.first_observations = {
            'warm_settled': 2,
            'first_invoice_microUSD': 0,
            'first_exclusive_settled': 0,
            'first_exclusive_collections_microUSD': 0,
            'first_paid_variable_costs_microUSD': 0,
            'warm_contribution_microUSD': 50_000_000,
        }
        self.renewal_observations = dict(
            self.first_observations,
            first_invoice_microUSD=self.invoice,
            first_exclusive_settled=1,
            first_exclusive_collections_microUSD=20_000_000,
            first_paid_variable_costs_microUSD=3_000_000,
        )

    def decide(self, arm, day, obs):
        return reach_policy.decide(
            arm, day,
            self.prefix['available_microUSD'],
            self.prefix['earned_microUSD'],
            **obs,
        )

    def test_same_first_tranche_and_unchanged_original_incumbent(self):
        pilot = self.decide('pilot', 90, self.first_observations)
        trial = self.decide('trial_once', 90, self.first_observations)
        organic = self.decide('organic', 90, self.first_observations)
        self.assertEqual((pilot['action'], pilot['reason']), ('BUY', 'FUNDED_TRIAL'))
        self.assertEqual((trial['action'], trial['reason']), ('BUY', 'FUNDED_TRIAL'))
        self.assertEqual(trial['observed'], pilot['observed'])
        self.assertEqual(trial['expected_net_microUSD'], pilot['expected_net_microUSD'])
        self.assertEqual((organic['action'], organic['reason']), ('SKIP', 'ORGANIC_CONTROL'))
        renewed = self.decide('pilot', 118, self.renewal_observations)
        self.assertEqual((renewed['action'], renewed['reason']), ('BUY', 'FUNDED_RENEWAL'))
        self.assertGreater(renewed['expected_net_microUSD'], 0)
        once = self.decide('trial_once', 118, self.renewal_observations)
        self.assertEqual((once['action'], once['reason']), ('SKIP', 'REGISTERED_ONE_TRANCHE'))
        self.assertEqual(once['observed'], renewed['observed'])
        self.assertEqual(once['expected_net_microUSD'], renewed['expected_net_microUSD'])
        self.assertEqual(self.decide('organic', 118, self.renewal_observations)['action'], 'SKIP')

    def test_auditor_refuses_forged_second_investment_despite_profitable_evidence(self):
        # These are private-free input observations, not fabricated sale receipts:
        # test-only rows deliberately exercise the independent reconstruction.
        rows = [
            {'day': 10, 'source': 'warm', 'status': 'SETTLED',
             'collections_microUSD': 30_000_000,
             'production_microUSD': 4_000_000, 'fee_microUSD': 1_000_000},
            {'day': 13, 'source': 'warm', 'status': 'SETTLED',
             'collections_microUSD': 30_000_000,
             'production_microUSD': 4_000_000, 'fee_microUSD': 1_000_000},
            {'day': 105, 'source': 'paid', 'source_plan_id': 'first-plan',
             'buyer': 'reach-018', 'status': 'SETTLED',
             'quote_microUSD': 100_000, 'production_microUSD': 2_000_000,
             'fee_microUSD': 100_000, 'collections_microUSD': 20_000_000},
        ]
        first = {'amount': self.invoice, 'plan_id': 'first-plan'}
        observation = reach_verify._attribution(rows, first)
        self.assertEqual(observation['first_exclusive_settled'], 1)
        self.assertGreater(observation['first_exclusive_collections_microUSD'] -
                           observation['first_paid_variable_costs_microUSD'] -
                           observation['first_invoice_microUSD'], 0)
        policy = self.decide('trial_once', 118, observation)
        self.assertEqual(policy['action'], 'SKIP')
        terms = {'arm': 'trial_once',
                 'supplier_contracts': {'pilot': default_contracts()['pilot']},
                 'source_sha256': 'fixed-unit-source'}
        record = {'day': 118, 'prefix': self.prefix, 'policy': policy,
                  'funding': None, 'purchase': None}
        cursor = _ReadOnlyLedger(self.prefix)
        self.assertIsNone(reach_verify._audit_decision(
            record, 118, terms, rows, first, cursor,
            {'purchase_receipts': {}}, set()))
        forged = deepcopy(record)
        forged['policy']['action'] = 'BUY'
        forged['funding'] = {'amount': self.invoice, 'plan_id': 'forged-second-plan'}
        with self.assertRaises(ValueError):
            reach_verify._audit_decision(
                forged, 118, terms, rows, first, cursor,
                {'purchase_receipts': {}}, set())
        forged = deepcopy(record)
        forged['purchase'] = {'source_plan_id': 'forged-second-plan'}
        with self.assertRaises(ValueError):
            reach_verify._audit_decision(
                forged, 118, terms, rows, first, cursor,
                {'purchase_receipts': {'forged-second-plan': forged['purchase']}}, set())


if __name__ == '__main__':
    unittest.main()
