import copy
import math
import unittest

from commercial.market import competitor_response, default_policy, price_quote, public_seller_observation, select_contribution_candidate


class PrivateInformation:
    def __float__(self):
        raise AssertionError('Seller accessed a private realized value')

    def __bool__(self):
        raise AssertionError('Seller branched on private future information')

    def __repr__(self):
        raise AssertionError('Seller exposed private future information')


class Commercial010PricingAuditTests(unittest.TestCase):
    def candidate(self, multiplier, profit, win, *, cash=500_000_000, survival=1., breaches=0, go=1.):
        return {'price_multiplier_bps': multiplier, 'expected_complete_profit': profit,
                'expected_available_cash': cash, 'cash_survival_fraction': survival,
                'win_probability': win, 'payable_breach_runs': breaches,
                'go_fraction': go}

    def test_lower_win_probability_can_maximize_complete_contribution(self):
        policy = default_policy()
        curve = [self.candidate(9500, 800_000_000, .95),
                 self.candidate(10500, 1_000_000_000, .55, go=.5),
                 self.candidate(15000, 100_000_000, .2, go=0.)]
        result = select_contribution_candidate(curve, policy)
        self.assertEqual(result['selected_multiplier_bps'], 10500)
        self.assertEqual(result['selected_payoff']['win_probability'], .55)
        self.assertEqual(result['seller_grid_profitable_deviation_residual'], 0)
        self.assertEqual(len(result['candidate_curve']), len(curve) + 1)
        self.assertIn('not Nash', result['solution_scope'])

    def test_selection_respects_cash_and_obligations_instead_of_all_go(self):
        curve = [self.candidate(15000, 3_000_000_000, .4, survival=.9),
                 self.candidate(12000, 2_000_000_000, .5, breaches=1),
                 self.candidate(10000, 1_500_000_000, .7, cash=-1),
                 self.candidate(10500, 1_000_000_000, .6, go=.25)]
        result = select_contribution_candidate(curve, default_policy())
        self.assertEqual(result['selected_multiplier_bps'], 10500)

    def test_no_bid_preserves_cash_when_every_offer_has_lower_complete_profit(self):
        policy = default_policy()
        curve = [self.candidate(9500, -policy['setup_cost'] - 1, .8),
                 self.candidate(15000, -policy['setup_cost'] - 2, .1)]
        result = select_contribution_candidate(curve, policy)
        self.assertIsNone(result['selected_multiplier_bps'])
        self.assertEqual(result['selected_payoff']['expected_complete_profit'], -policy['setup_cost'])

    def test_untested_price_and_ambiguous_payoffs_fail_explicitly(self):
        policy = default_policy()
        mutations = [
            ('price_multiplier_bps', 100),
            ('price_multiplier_bps', None),
            ('win_probability', -1.),
            ('win_probability', 1.1),
            ('cash_survival_fraction', 2.),
            ('cash_survival_fraction', -1.),
            ('payable_breach_runs', -1),
            ('payable_breach_runs', True),
            ('expected_complete_profit', math.nan),
        ]
        for key, value in mutations:
            candidate = self.candidate(9500, 1_000_000_000, .8)
            candidate[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                select_contribution_candidate([candidate], policy)
        candidate = self.candidate(9500, 1_000_000_000, .8)
        del candidate['payable_breach_runs']
        with self.assertRaises(ValueError):
            select_contribution_candidate([candidate], policy)

    def test_public_observation_cannot_read_or_expose_private_values_or_future_draws(self):
        world = default_policy()['worlds'][0]
        buyer = {'id': 'SIM-buyer', 'purchases': 1, 'onboarded': True, 'trust': .97,
                 'value': PrivateInformation(), 'budget': PrivateInformation(),
                 'future_arrival': PrivateInformation(), 'future_dispute': PrivateInformation()}
        snapshot = {'cash': 1000, 'unrestrictedEarned': 100}
        observed = public_seller_observation(world, [buyer], snapshot)
        self.assertEqual(set(observed['buyer_public_history'][0]), {'id', 'purchases', 'onboarded', 'trust'})
        other = copy.copy(buyer)
        other.update(value=-10**20, budget=10**20, future_arrival=False, future_dispute=True)
        self.assertEqual(public_seller_observation(world, [other], snapshot), observed)
        self.assertIn('No private', observed['information_limit'])

    def test_rival_response_payoff_and_residual_match_an_independent_grid(self):
        values = [20., 50., 100., 300.]
        own_price, own_trust, rival_trust, rival_cost, human, premium = 145., .98, .9, 5., 139., 10.
        diy_cost, diy_trust, onboarding, switching = 30., .85, 10., 5.
        response = competitor_response(values, own_price, own_trust, rival_trust, rival_cost, human, premium,
                                       diy_cost, diy_trust, onboarding, switching)
        payoffs = []
        for quality in [.90, .95, .99]:
            cost = rival_cost * (1 + 5 * (quality - .90))
            for price in [human * x for x in [.10, .20, .35, .50, .65, .80, .95, 1.05, 1.20]] + [cost * 1.05]:
                quantity = sum(quality * rival_trust * v - price - switching + premium >
                               max(own_trust * .99 * v - own_price - onboarding + premium,
                                   0., .97 * v - human, .99 * diy_trust * v - diy_cost + premium)
                               for v in values)
                payoffs.append(((price - cost) * quantity, price, quality, quantity, cost))
        optimum = max(payoffs, key=lambda item: (item[0], item[1]))
        self.assertEqual(response['expected_payoff'], optimum[0])
        self.assertEqual(response['price'], optimum[1])
        self.assertEqual(response['quality'], optimum[2])
        self.assertEqual(response['estimated_customers'], optimum[3])
        self.assertEqual(response['grid_best_response_residual'], 0)
        self.assertIn('not a Nash', response['scope'])

    def test_adaptive_prices_use_only_public_one_time_onboarding_state_and_human_anchor(self):
        policy = default_policy()
        for candidate in policy['adaptive_price_candidates']:
            first = price_quote(policy, candidate['id'], False)
            repeat = price_quote(policy, candidate['id'], True)
            self.assertEqual(first, policy['human_benchmark'] * candidate['first_bps'] // 10000)
            self.assertEqual(repeat, (policy['human_benchmark'] - policy['human_onboarding_component']) * candidate['repeat_bps'] // 10000)
        for value in [None, 1, 'yes']:
            with self.subTest(onboarded=value), self.assertRaises(ValueError):
                price_quote(policy, 9500, value)
        for value in [100, -1, True, 'unregistered-adaptive-price']:
            with self.subTest(candidate=value), self.assertRaises(ValueError):
                price_quote(policy, value, False)


if __name__ == '__main__':
    unittest.main()
