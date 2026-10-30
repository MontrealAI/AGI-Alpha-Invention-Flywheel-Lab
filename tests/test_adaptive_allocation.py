import copy
import unittest
from adaptive_enterprise.account import action_digest
from adaptive_enterprise.allocation import allocate, default_riskpolicy


def observation(available=1000, earned=1000):
    return {'scope': 'SIMULATED', 'state_digest': 'a' * 64,
            'summary': {'available': available, 'unrestrictedEarned': earned}}


def option(ident='delivery', upfront=100, central=300, adverse=200, later=20, benefit=None):
    return {'id': ident, 'kind': 'delivery', 'upfront_cost': upfront,
            'later_liabilities': {'central': later, 'adverse': later},
            'future_net_cash': {'central': central, 'adverse': adverse},
            'benefit_ids': [benefit or ident + '-customer-outcome'], 'requires': [],
            'exclusive_group': None, 'authorized': True, 'evidence': 'declared outcome/cost scenario',
            'execution': {'job': ident, 'job_id': 'fixture-job-' + ident,
                          'customer_id': 'fixture-customer-' + ident, 'payment_bps': 0,
                          'payment_fixed_microUSD': 0, 'onboarding_microUSD': 0}}


class AdaptiveAllocationTests(unittest.TestCase):
    def risk(self):
        r = default_riskpolicy()
        r.update(authorized_allocation=1000, worst_loss_limit=1000)
        return r

    def test_native_state_and_exact_action_digest_bound(self):
        plan = allocate(observation(), [option()], self.risk())
        self.assertEqual(plan['selected'], ['delivery'])
        self.assertEqual(plan['reserve_amount'], 120)
        self.assertEqual(plan['authorized_digest'], action_digest(plan, plan['expected_state_digest'], plan['reserve_amount'], plan['expected_net']))
        changed = copy.deepcopy(plan)
        changed['selected_options'][0]['execution']['job'] = 'different'
        self.assertNotEqual(plan['authorized_digest'], action_digest(changed, plan['expected_state_digest'], plan['reserve_amount'], plan['expected_net']))

    def test_future_receipts_cannot_fund_current_liability(self):
        plan = allocate(observation(100, 100), [option(upfront=80, central=100000, later=30)], self.risk())
        self.assertEqual(plan['decision'], 'RETAIN_CASH')
        self.assertEqual(plan['reserve_amount'], 0)
        self.assertEqual(allocate(observation(1000, 0), [option()], self.risk())['selected'], [])

    def test_signed_future_cash_is_reserved_and_downside_controlled(self):
        action = option(central=700, adverse=-150, later=20)
        plan = allocate(observation(), [action], self.risk())
        self.assertEqual(plan['predicted_scenario_cash']['adverse'], -250)
        self.assertEqual(plan['worst_later_reserve'], 150)
        risk = self.risk(); risk['worst_loss_limit'] = 200
        self.assertEqual(allocate(observation(), [action], risk)['selected'], [])

    def test_negative_interaction_can_change_selected_allocation(self):
        a, b = option('a'), option('b')
        risk = self.risk()
        both = allocate(observation(), [a, b], risk)
        self.assertEqual(both['selected'], ['a', 'b'])
        risk['interactions'] = [{'id': 'shared-support-contention', 'members': ['a', 'b'],
                                 'net_cash': {'central': -1000, 'adverse': -1000}, 'benefit_ids': ['coordination-cost']}]
        single = allocate(observation(), [a, b], risk)
        self.assertEqual(len(single['selected']), 1)

    def test_overlapping_customer_benefit_not_double_counted(self):
        actions = [option('bundle', benefit='customer-1-period-1'), option('component', benefit='customer-1-period-1')]
        self.assertEqual(len(allocate(observation(), actions, self.risk())['selected']), 1)
        risk = self.risk()
        risk['interactions'] = [{'id': 'duplicate-bundle-value', 'members': ['bundle', 'component'], 'net_cash': {'central': 1000, 'adverse': 1000}, 'benefit_ids': ['customer-1-period-1']}]
        self.assertEqual(len(allocate(observation(), actions, risk)['selected']), 1)

    def test_keep_cash_and_unknown_returns_are_valid(self):
        losing = option(central=50, adverse=20)
        unknown = option('unknown'); unknown['future_net_cash'] = None
        plan = allocate(observation(), [losing, unknown], self.risk())
        self.assertEqual(plan['selected'], [])
        self.assertEqual(plan['unknown_return_actions'], ['unknown'])
        self.assertIsNone(plan['authorized_digest'])

    def test_dependencies_exclusions_and_bounded_search(self):
        a, b = option('a'), option('b')
        b['requires'] = ['a']
        a['authorized'] = False
        self.assertEqual(allocate(observation(), [a, b], self.risk())['selected'], [])
        a['authorized'] = True
        a['exclusive_group'] = b['exclusive_group'] = 'same-capacity'
        self.assertEqual(allocate(observation(), [a, b], self.risk())['selected'], ['a'])
        risk = self.risk(); risk['max_states'] = 2
        self.assertIn('DECOMPOSE', allocate(observation(), [a, b], risk)['decision'])

    def test_malformed_nonfinite_duplicate_and_cycles_rejected(self):
        for changed in [dict(option(), upfront_cost=True), dict(option(), future_net_cash={'central': float('inf'), 'adverse': 0}), dict(option(), benefit_ids=[{}])]:
            with self.assertRaises(ValueError):
                allocate(observation(), [changed], self.risk())
        a, b = option('a'), option('b')
        a['requires'] = ['b']; b['requires'] = ['a']
        with self.assertRaises(ValueError):
            allocate(observation(), [a, b], self.risk())
        with self.assertRaises(ValueError):
            allocate(observation(), [a, a], self.risk())
