"""Independent policy regressions on development cases and explicit unit worlds.

These tests never execute the preregistered evaluation seeds. Forced unit actions
and draws below test admission/causality boundaries, not empirical market demand.
"""
import copy
from dataclasses import asdict, replace
from fractions import Fraction
import math
import unittest
from unittest.mock import patch

from omega import market, market_buyer


def one_quarter(action):
    def policy(state, mode, rates):
        return (action if state.quarter == 0 else market.Action()), {'unit_fixture': True}
    return policy


class MarketStrategyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rates = market.Rates()
        cls.case = market.registered_cases(development=True)[0]
        cls.plan = market.simulate(cls.case, 'joint')

    def test_selector_can_only_receive_public_state_and_never_draws_truth(self):
        state = market.PublicState()
        with patch.object(market, '_draw', side_effect=AssertionError('policy accessed hidden draw')):
            selected = market.choose(state, 'joint')
            self.assertEqual(selected, market.choose(copy.deepcopy(state), 'joint'))
        for hidden in (self.case, asdict(state), {'future_sales': 1000}):
            with self.assertRaisesRegex(ValueError, 'PUBLIC_STATE_ONLY'):
                market.choose(hidden, 'joint')
        other_world = market.registered_cases(development=True)[3]
        other_plan = market.simulate(other_world, 'joint')
        self.assertNotEqual(asdict(self.case), asdict(other_world))
        for key in ('public_before', 'action', 'rationale', 'fixed_costs_cents'):
            self.assertEqual(self.plan['trace'][0][key], other_plan['trace'][0][key])

    def test_addressed_potential_outcomes_do_not_depend_on_prior_draw_count(self):
        first = market._draw(1103, 1, 2, 'payment')
        for event in ('delivery', 'unused-information', 'community:segment'):
            market._draw(1103, 0, 0, event)
        self.assertEqual(first, market._draw(1103, 1, 2, 'payment'))
        self.assertNotEqual(first, market._draw(1103, 1, 2, 'delivery'))

    def test_nonentry_preserves_seed_without_forced_cost_or_founder_work(self):
        plan = market.simulate(self.case, 'nonentry')
        self.assertEqual(plan['closing_available_cents'], 10_000_000)
        for key in ('recognized_revenue_cents', 'pretax_cash_expense_cents', 'tax_cents',
                    'accounting_profit_cents', 'economic_profit_cents', 'founder_minutes',
                    'accepted_complete_bundles', 'residual_cents'):
            self.assertEqual(plan[key], 0)
        self.assertEqual(plan['endpoint_hour'], 365 * 24)
        self.assertEqual(len(plan['trace']), 4)
        self.assertTrue(all(r['action']['kind'] == 'preserve' and not r['fixed_costs_cents']
                            and not r['bundles'] for r in plan['trace']))

    def test_resources_follow_selected_actions_and_reuse_is_not_recharged(self):
        state, rates = market.PublicState(), self.rates
        action = market.Action('operate', 29900, 'partner', ('self_hosted',), True)
        first = market.fixed_costs(action, state, rates)
        self.assertEqual(set(first), {'acquisition', 'security_compliance', 'launch', 'package_process'})
        self.assertEqual(first['acquisition'], 1200)
        reused = market.fixed_costs(replace(action, construct_process=False),
                                    replace(state, launched=True, capability=1), rates)
        self.assertEqual(set(reused), {'acquisition', 'security_compliance'})
        webinar = market.fixed_costs(replace(action, products=('group_webinar',)), state, rates)
        self.assertEqual(webinar['webinar_platform'], rates.webinar_platform_cents)
        self.assertEqual(webinar['webinar_material'], rates.webinar_material_cents)
        self.assertEqual(market.fixed_costs(market.Action(), state, rates), {})
        self.assertEqual(market.fixed_costs(market.Action('information'), state, rates),
                         {'information': market.task_cost('information', rates)})

    def test_task_money_rounds_exactly_even_above_float_integer_precision(self):
        rates = replace(self.rates, input_cents_per_million=10**18 + 1,
                        output_cents_per_million=10**18 + 3,
                        cpu_cents_per_hour=10**18 + 7, cost_multiplier_bps=10001)
        for name, quantity in market.TASKS.items():
            amount = (Fraction(quantity['input_tokens'], 1_000_000) * rates.input_cents_per_million
                      + Fraction(quantity['output_tokens'], 1_000_000) * rates.output_cents_per_million
                      + Fraction(quantity['cpu_seconds'], 3600) * rates.cpu_cents_per_hour)
            expected = math.ceil(amount * Fraction(rates.cost_multiplier_bps, 10000))
            self.assertEqual(market.task_cost(name, rates), expected)

    def test_price_channel_capability_menus_and_competent_simple_control(self):
        state = market.PublicState()
        joint = market.feasible_actions(state, 'joint')
        ordinary = market.feasible_actions(state, 'ordinary_reuse')
        self.assertEqual(joint, ordinary)
        operations = [a for a in joint if a.kind == 'operate']
        self.assertEqual({a.price_cents for a in operations}, {4900, 9900, 14900, 29900, 49900})
        self.assertEqual({a.channel for a in operations}, set(market.CHANNELS))
        self.assertEqual({a.construct_process for a in operations}, {False, True})
        simple = market.feasible_actions(state, 'simple')
        self.assertEqual(simple, (market.Action(), market.Action('operate', 29900, 'community', ('self_hosted',))))
        self.assertTrue(all(not a.construct_process for a in market.feasible_actions(state, 'existing')))
        self.assertTrue(all(not a.construct_process for a in market.feasible_actions(state, 'staged')))
        self.assertTrue(any(a.construct_process for a in market.feasible_actions(replace(state, quarter=1), 'staged')))
        self.assertTrue(all(not a.construct_process for a in market.feasible_actions(replace(state, capability=1), 'joint')))

    def test_free_core_keeps_full_capability_and_rival_is_an_outside_option(self):
        person = market.persona('process', 'development-process')
        outside = {r['id']: r for r in person['outside_options']}
        for name in ('free_core', 'ordinary_reuse'):
            self.assertEqual(outside[name]['price_cents'], 0)
            self.assertEqual(outside[name]['capability'], 1)
        state = market.PublicState()
        action = market.Action('operate', 29900, 'community', ('self_hosted',))
        self.assertEqual(market.quoted_offers(action, state)[0]['capability'], 0)
        self.assertFalse(market_buyer.decide(person, market.quoted_offers(action, state))['selected_offer_ids'])
        action = replace(action, construct_process=True)
        self.assertEqual(market_buyer.decide(person, market.quoted_offers(action, state))['selected_offer_ids'], ['self_hosted'])
        imitated = market.persona('process', 'development-process', rival_ready=True)
        self.assertFalse(market_buyer.decide(imitated, market.quoted_offers(action, state))['selected_offer_ids'])

    def test_information_is_paid_before_signal_and_contingent_operation(self):
        research = self.plan['trace'][0]
        operation = self.plan['trace'][1]
        self.assertEqual(research['action']['kind'], 'information')
        self.assertFalse(research['public_before']['information_bought'])
        self.assertTrue(operation['public_before']['information_bought'])
        self.assertEqual(research['cost_cents'], market.task_cost('information', self.rates))
        self.assertEqual(research['closing_available_cents'],
                         research['public_before']['available_cents'] - research['cost_cents'])
        self.assertEqual(operation['public_before']['available_cents'], research['closing_available_cents'])
        self.assertEqual(research['revenue_cents'], 0)
        self.assertFalse(research['bundles'])
        self.assertNotEqual(operation['public_before']['weights'], research['public_before']['weights'])
        self.assertEqual(research['signal_available_hour'], research['hour'] + self.rates.information_hours)
        self.assertGreaterEqual(operation['hour'], research['signal_available_hour'])

    def test_qualification_and_claim_maturity_have_separate_causal_times(self):
        first_operation = next(r for r in self.plan['trace'] if r['action']['kind'] == 'operate')
        self.assertTrue(first_operation['action']['construct_process'])
        self.assertEqual(first_operation['delivery_hour'], first_operation['hour'] + 72)
        self.assertEqual(first_operation['maturity_hour'], first_operation['delivery_hour'] + 721)
        for current, following in zip(self.plan['trace'], self.plan['trace'][1:]):
            if current['action']['kind'] == 'operate':
                self.assertLessEqual(current['maturity_hour'], following['hour'])

    def test_paid_information_can_consume_the_remaining_construction_window(self):
        rates = replace(self.rates, buyer_window_hours=72)
        state = market.PublicState()
        self.assertTrue(any(a.construct_process for a in market.feasible_actions(state, 'joint', rates)))
        after_information = replace(state, information_bought=True, elapsed_hours=1)
        self.assertFalse(any(a.construct_process for a in market.feasible_actions(after_information, 'joint', rates)))
        too_slow = replace(self.rates, process_qualification_hours=721)
        plan = market.simulate(self.case, 'joint', rates=too_slow)
        self.assertTrue(all(not r['action']['construct_process'] for r in plan['trace']))
        self.assertTrue(all('package_process' not in r['fixed_costs_cents'] for r in plan['trace']))

    def test_missed_buyer_window_still_allows_costless_withdrawal(self):
        expired = market.PublicState(elapsed_hours=self.rates.buyer_window_hours + 1)
        self.assertEqual(market.feasible_actions(expired, 'joint', self.rates), (market.Action(),))
        self.assertEqual(market.choose(expired, 'joint', self.rates)[0], market.Action())

    def test_finite_clock_rejects_future_maturity_credits_not_slow_technology(self):
        with self.assertRaisesRegex(ValueError, 'MATURITY_BEFORE_NEXT_DECISION'):
            replace(self.rates, buyer_window_hours=1440)
        self.assertEqual(replace(self.rates, buyer_window_hours=1439).buyer_window_hours + 721, 2160)
        # Slow construction remains an admissible negative case; it is skipped
        # rather than declared impossible or paid in advance of a closed window.
        self.assertEqual(replace(self.rates, process_qualification_hours=4000).process_qualification_hours, 4000)
        for bad in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                replace(self.rates, information_hours=bad)
            with self.assertRaises(ValueError):
                market.PublicState(elapsed_hours=bad)

    def test_ordinary_reuse_has_identical_content_resources_and_entire_path(self):
        ordinary = market.simulate(self.case, 'ordinary_reuse')
        expected = dict(self.plan, policy='ordinary_reuse')
        self.assertEqual(ordinary, expected)

    def test_positive_future_margin_cannot_finance_present_price_exposure(self):
        state = market.PublicState(available_cents=3000)
        action = market.Action('operate', 14900, 'community', ('self_hosted',))
        self.assertLess(sum(market.fixed_costs(action, state, self.rates).values()), state.available_cents)
        self.assertLess(market.forecast(action, state), 0)
        self.assertEqual(market.choose(state, 'joint')[0].kind, 'preserve')
        self.assertEqual(market.choose(replace(state, available_cents=0), 'joint')[0].kind, 'preserve')

    def test_interim_tail_buffer_prevents_a_second_unfunded_bundle(self):
        action = market.Action('operate', 14900, 'community', ('self_hosted',))
        fixed = sum(market.fixed_costs(action, market.PublicState(), self.rates).values())
        expense = sum(market.variable_costs('self_hosted', 14900, 'community').values())
        capital = fixed + 14900 + 2 * expense + 20
        case = market.Scenario('unit-liquidity-boundary', 1103, (0, 10000, 0, 0))
        with patch.object(market, 'choose', side_effect=one_quarter(action)), patch.object(market, '_draw', return_value=.5):
            plan = market.simulate(case, 'joint', capital_cents=capital)
        bundles = plan['trace'][0]['bundles']
        self.assertEqual([r['status'] for r in bundles], ['released'] + ['liquidity_deferred'] * 3)
        self.assertEqual(bundles[1]['required_cents'] - bundles[1]['available_cents'], 20)
        self.assertEqual(plan['accepted_complete_bundles'], 1)

    def test_private_time_is_paid_attempt_time_and_has_a_real_capacity_limit(self):
        action = market.Action('operate', 29900, 'targeted', ('founder_private',))
        case = market.Scenario('unit-private-capacity', 1103, (0, 10000, 0, 0))
        def draw(seed, quarter, prospect, event):
            return .001 if event == 'founder-access' else .5
        with patch.object(market, 'choose', side_effect=one_quarter(action)), patch.object(market, '_draw', side_effect=draw):
            plan = market.simulate(case, 'joint')
        maximum = self.rates.quarter_founder_minutes // self.rates.private_minutes
        self.assertEqual(len(plan['trace'][0]['bundles']), maximum)
        self.assertEqual(plan['founder_minutes'], maximum * self.rates.private_minutes)
        self.assertEqual(plan['noncash_founder_opportunity_cents'],
                         math.ceil(Fraction(plan['founder_minutes'] * self.rates.founder_cents_per_hour, 60)))
        self.assertEqual(plan['economic_profit_cents'], plan['accounting_profit_cents'] - plan['noncash_founder_opportunity_cents'])

    def test_offered_webinar_bears_preparation_cost_even_without_attendees(self):
        action = market.Action('operate', 29900, 'community', ('group_webinar',))
        case = market.Scenario('unit-empty-webinar', 1103, (10000, 0, 0, 0))
        with patch.object(market, 'choose', side_effect=one_quarter(action)), patch.object(market, '_draw', return_value=.5):
            plan = market.simulate(case, 'joint')
        row = plan['trace'][0]
        self.assertFalse(row['bundles'])
        self.assertEqual(row['founder_minutes'], self.rates.webinar_minutes)
        self.assertEqual(row['revenue_cents'], 0)
        self.assertGreaterEqual(row['cost_cents'], self.rates.webinar_platform_cents + self.rates.webinar_material_cents)

    def test_accepted_bundle_value_remains_an_expectation_not_realized_income(self):
        accepted = [b for r in self.plan['trace'] for b in r['bundles'] if b['status'] == 'released']
        self.assertTrue(accepted)
        revenue = 0
        for bundle in accepted:
            self.assertIs(bundle['realized_buyer_value_not_measured'], True)
            self.assertGreater(bundle['expected_buyer_net_microUSD'], 0)
            self.assertGreater(bundle['expected_increment_over_outside_microUSD'], 0)
            for item in bundle['items']:
                self.assertTrue(market_buyer.verify_quote_receipt(bundle['persona'], bundle['quotes'], item['choice'])['accepted'])
                revenue += item['price_cents']
        self.assertEqual(self.plan['recognized_revenue_cents'], revenue)
        self.assertEqual(self.plan['accepted_complete_bundles'], len(accepted))
        self.assertIn('REQUIRES_NATIVE_EXECUTION', self.plan['scope'])

    def test_public_policy_audit_rejects_changed_action_cost_and_buyer_quote(self):
        audit = market.audit_policy(self.plan)
        self.assertTrue(audit['accepted'])
        self.assertIn('HEURISTIC_ONLY', audit['optimality_claim'])
        changed = copy.deepcopy(self.plan)
        changed['trace'][0]['action']['kind'] = 'preserve'
        with self.assertRaisesRegex(ValueError, 'POLICY_CHANGED'):
            market.audit_policy(changed)
        changed = copy.deepcopy(self.plan)
        changed['trace'][0]['fixed_costs_cents']['information'] += 1
        with self.assertRaisesRegex(ValueError, 'COST_MUST_FOLLOW'):
            market.audit_policy(changed)
        changed = copy.deepcopy(self.plan)
        bundle = next(b for r in changed['trace'] for b in r['bundles'] if b.get('items'))
        bundle['quotes'][0]['price_cents'] += 1
        with self.assertRaises(ValueError):
            market.audit_policy(changed)


if __name__ == '__main__':
    unittest.main()
