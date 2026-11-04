"""Prospective policy regressions. Buyer and channel draws use development seeds."""
from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from connected_enterprise.channels import ChannelBook, default_contracts
from mechanism_harness import cart_program, reach_policy as p
from mechanism_harness.market_cases import market


class ReachPolicyTests(unittest.TestCase):
    def setUp(self):
        self.trial = dict(
            arm='pilot', day=90, available_microUSD=18_250_000, earned_microUSD=6_250_000,
            warm_settled=5, first_invoice_microUSD=0, first_exclusive_settled=0,
            first_exclusive_collections_microUSD=0, first_paid_variable_costs_microUSD=0,
            warm_contribution_microUSD=40_000_000)

    def decision(self, **changes):
        return p.decide(**{**self.trial, **changes})

    def renewal(self, **changes):
        return self.decision(**{'day': 118, 'first_invoice_microUSD': 6_250_000,
                                'first_exclusive_settled': 1, 'first_exclusive_collections_microUSD': 10_000_000,
                                'first_paid_variable_costs_microUSD': 3_749_999, **changes})

    def test_registered_warm_and_organic_schedules_are_disjoint(self):
        self.assertEqual([i for day in range(365) for i in p.warm(day)], list(range(1, 28)))
        self.assertEqual([day for day in range(365) if p.warm(day)], list(range(5, 84, 3)))
        self.assertEqual([day for day in range(365) if p.organic(day)], list(range(92, 170, 7)))
        self.assertEqual([b for day in range(365) for b in p.organic(day)], list(p.ORGANIC_ROSTER))
        self.assertEqual(len({x['id'] for x in p.population()}), 24)
        last_warm_job = 7 + 27
        fresh_jobs = {36 + 4 * n + k for n in range(24) for k in range(4)}
        self.assertEqual(len(fresh_jobs), 96)
        self.assertGreater(min(fresh_jobs), last_warm_job)
        self.assertLess(max(fresh_jobs), p.JOBS_PER_SERVICE)

    def test_overlap_deduplicates_today_and_excludes_entire_organic_roster(self):
        rows = [{'customer_id': b, 'source_plan_id': 'dev-plan', 'exposure_id': f'dev-{i}'}
                for i, b in enumerate(('reach-005', 'reach-011', 'reach-023'))]
        # Today belongs to 005, 011 has a later scheduled organic contact.
        routed = p.route(127, p.organic(127), rows)
        self.assertEqual([(r['customer_id'], r['source'], r['paid_exclusive']) for r in routed],
                         [('reach-005', 'organic', False), ('reach-011', 'paid', False),
                          ('reach-023', 'paid', True)])
        with self.assertRaisesRegex(ValueError, 'UNIQUE_SOURCE_BOUND'):
            p.route(127, p.organic(127), rows + [rows[0]])
        with self.assertRaisesRegex(ValueError, 'REGISTERED_ORGANIC'):
            p.route(127, [], rows)

    def test_default_invoice_terms_and_failed_activation_spend_apply(self):
        self.assertEqual(p.contracts('central')['pilot'], default_contracts()['pilot'])
        failed = p.contracts('failed_activation')['pilot']
        self.assertEqual(failed, {**default_contracts()['pilot'], 'activation_reliability_bps': 0})
        book = ChannelBook(71, {'pilot': failed})
        contract = book.purchase('pilot', 0, 'development-plan')
        self.assertEqual(contract['invoice_microUSD'], 6_250_000)
        self.assertEqual((contract['activation_day'], contract['expiry_day']), (2, 23))
        for day in range(24):
            self.assertEqual(book.expose(day, p.population()), [])
        instance = book.export()['instances']['development-plan']
        self.assertEqual((instance['state'], instance['activation_attempts'], instance['failure_credit_due_microUSD']),
                         ('FAILED', 2, 0))

    def test_wallet_and_valuation_are_stable_across_visits(self):
        m = market(72)
        program = cart_program.null_program(m)
        program['menu'] = [{'outcome_id': 'first', 'price_cents': 100}]
        first = p.profile(m, program, 'reach-016', 96, 'central', 0, seed=73)
        lifetime = p.lifetime_budget(m, 'reach-016', seed=73)
        self.assertEqual(first['budget_cents'] * 2, lifetime)
        repeat = p.profile(m, program, 'reach-016', 110, 'central', lifetime - 9, seed=73)
        self.assertEqual(repeat, {**first, 'budget_cents': 9})
        self.assertTrue(cart_program.oracle_choose(m, program, repeat)['declined'])
        for scenario in ('weak', 'no_demand', 'copycat', 'failed_activation'):
            private = p.profile(m, program, 'reach-016', 110, scenario, 0, seed=73)
            if scenario in ('no_demand', 'copycat'):
                self.assertTrue(cart_program.oracle_choose(m, program, private)['declined'])
            if scenario == 'weak':
                self.assertEqual(private['values'], [v // 2 for v in first['values']])
            if scenario == 'failed_activation':
                self.assertEqual(private, first)
        with self.assertRaisesRegex(ValueError, 'WALLET_OVERSPENT'):
            p.profile(m, program, 'reach-016', 110, 'central', lifetime + 1, seed=73)

    def test_retention_requires_prior_collection_and_paid_contact_qualification(self):
        with patch.object(p, '_draw', return_value=6000):
            self.assertTrue(p.qualification('reach-020', 100, 0, seed=74))
            self.assertFalse(p.qualification('reach-020', 100, 1, seed=74))
        with patch.object(p, '_draw', return_value=7500):
            self.assertFalse(p.qualification('reach-020', 100, 0, seed=74))

    def test_cold_gate_declines_even_with_full_seed(self):
        cold = self.decision(available_microUSD=100_000_000_000, earned_microUSD=0)
        self.assertEqual(cold['reason'], 'INSUFFICIENT_UNRESTRICTED_EARNINGS')
        self.assertEqual(self.decision(warm_settled=0)['reason'], 'NO_WARM_COLLECTION')

    def test_liquid_maintenance_and_positive_trial_estimate_required(self):
        trial = self.decision()
        self.assertEqual((trial['action'], trial['expected_net_microUSD']), ('BUY', 5_550_000))
        self.assertEqual(self.decision(available_microUSD=18_249_999)['action'], 'SKIP')
        self.assertEqual(self.decision(warm_contribution_microUSD=26_125_000)['reason'],
                         'NONPOSITIVE_EXPECTED_NET')
        self.assertEqual(self.decision(arm='organic')['reason'], 'ORGANIC_CONTROL')

    def test_renewal_requires_positive_exclusive_receipt_net_of_every_paid_cost(self):
        self.assertEqual((self.renewal()['action'], self.renewal()['expected_net_microUSD']), ('BUY', 1))
        zero = self.renewal(first_paid_variable_costs_microUSD=3_750_000)
        self.assertEqual((zero['action'], zero['attributed_pretax_microUSD']), ('SKIP', 0))
        overlap_only = self.renewal(first_exclusive_settled=0, first_exclusive_collections_microUSD=0)
        self.assertEqual(overlap_only['reason'], 'NO_EXCLUSIVE_COLLECTION')
        self.assertEqual(self.decision(day=118)['reason'], 'FIRST_INVOICE_ABSENT')
        self.assertEqual(self.renewal(earned_microUSD=0)['action'], 'SKIP')
        self.assertEqual(self.renewal(available_microUSD=6_250_000)['action'], 'SKIP')
        self.assertEqual(self.renewal(arm='organic')['action'], 'SKIP')

    def test_no_scenario_seed_private_future_or_counterfactual_in_decision(self):
        self.assertEqual(set(inspect.signature(p.decide).parameters), set(self.trial))
        with self.assertRaises(TypeError):
            self.decision(matched_organic_profit=100)
        with self.assertRaisesRegex(ValueError, 'DUE_PRIOR_TRANCHE'):
            self.decision(first_invoice_microUSD=6_250_000)
        with self.assertRaisesRegex(ValueError, 'DUE_PRIOR_TRANCHE'):
            self.decision(day=118, first_exclusive_settled=1, first_exclusive_collections_microUSD=100)
        with self.assertRaisesRegex(ValueError, 'DUE_PRIOR_TRANCHE'):
            self.renewal(first_exclusive_settled=0)
        with self.assertRaisesRegex(ValueError, 'INTEGER_REACH'):
            self.decision(earned_microUSD=True)
        with self.assertRaisesRegex(ValueError, 'REGISTERED_TRANCHE'):
            self.decision(day=119)


if __name__ == '__main__':
    unittest.main()
