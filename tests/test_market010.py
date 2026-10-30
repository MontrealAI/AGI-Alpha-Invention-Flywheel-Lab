import copy
import math
import unittest
from commercial.market import competitor_response, default_policy, validate_policy
from commercial.verdicts import verdicts


class Market010Tests(unittest.TestCase):
    def test_policy_requires_premium_prices_currency_and_fixed_confirmation(self):
        p = default_policy()
        self.assertEqual(validate_policy(p), p)
        for key, value in [('currency', 'CAD'), ('human_benchmark', 0), ('per_job_cost', float('nan')),
                           ('price_multipliers_bps', [100]), ('confirmation_seeds', [1]),
                           ('worlds', []), ('worlds', [None])]:
            q = copy.deepcopy(p)
            q[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_policy(q)

    def test_policy_timing_and_units_fail_explicitly(self):
        for value in [-1, True, math.inf, 26]:
            q = default_policy()
            q['worlds'][0]['settlement_delay'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_policy(q)
        p = default_policy()
        p['initial_discount_bps'] = 100
        with self.assertRaises(ValueError):
            validate_policy(p)

    def test_competitor_can_make_profitable_low_price_deviation(self):
        response = competitor_response([1000, 1100], 132.05, .99, .9, 20, 139)
        self.assertLess(response['price'], .65 * 139)
        self.assertGreater(response['expected_payoff'], 0)
        self.assertEqual(response['grid_best_response_residual'], 0)
        self.assertIn('not a Nash', response['scope'])

    def test_commercial_go_does_not_require_invention_or_live_money(self):
        v = verdicts(simulated_go=True, accepted_jobs=16, positive_service=True)
        self.assertEqual(v['simulated_commercial_flywheel']['verdict'], 'CONDITIONAL_SIMULATED_GO')
        for lane in ['observed_commercial_flywheel', 'capability_compounding_flywheel', 'blue_sky_enablement']:
            self.assertEqual(v[lane]['verdict'], 'NOT_ESTABLISHED')
        with self.assertRaises(ValueError):
            verdicts(simulated_go=True, accepted_jobs=0, positive_service=False)
        with self.assertRaises(ValueError):
            verdicts(simulated_go=True, accepted_jobs=16, positive_service=True, observed_evidence={'simulated': True})
