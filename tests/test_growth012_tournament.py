import copy
import unittest

from enterprise.tournament012 import milestone_frontier, paired_difference, scenario_config, summarize, next_action


class Tournament012Tests(unittest.TestCase):
    def world(self, seed=1, hit=None, profit=2, revenue=10, survival=True):
        return {'seed': seed, 'milestones': {'100': hit}, 'metrics': {'collections_microUSD': revenue, 'profit_microUSD': profit,
                'costs_microUSD': revenue - profit, 'paid_jobs': 1, 'earned_funded_deliveries': 1}, 'cash_survival': survival}

    def test_nonreaching_and_insolvent_worlds_remain_in_denominator(self):
        worlds = [self.world(hit=20), self.world(survival=False), self.world()]
        result = milestone_frontier(worlds, [100], 48)[0]
        self.assertEqual(result['attainment_fraction'], 1 / 3)
        self.assertEqual(result['nonreaching_runs'], 2)
        self.assertIsNone(result['unconditional_median_hours'])
        self.assertEqual(result['conditional_hitting_hours_quantiles']['0.5'], 20)
        self.assertEqual(result['empirical_restricted_time_hours'], 116 / 3)

    def test_unobserved_years_do_not_receive_extrapolated_probability(self):
        result = milestone_frontier([self.world(hit=1)], [100], 14 * 24)[0]
        self.assertEqual(result['attainment_fraction'], 1)
        self.assertTrue(all(x is None for x in result['attainment_by_year'].values()))
        self.assertEqual(result['longer_horizons_not_observed'], [1, 3, 5, 10])

    def test_unconditional_median_requires_population_half(self):
        result = milestone_frontier([self.world(hit=12), self.world(hit=24), self.world()], [100], 48)[0]
        self.assertEqual(result['unconditional_median_hours'], 24)

    def test_first_controller_comparison_keeps_business_config_equal(self):
        config = {'market_regime': 'ordinary', 'contacts_per_day': 8, 'settlement_hours': 48, 'retention_probability': .9}
        original = copy.deepcopy(config)
        cases = [scenario_config(config, 'ordinary', arm) for arm in ['baseline', 'simple', 'joint']]
        self.assertTrue(all(value[0] == original for value in cases))
        self.assertEqual([value[1] for value in cases], ['baseline', 'simple', 'joint'])
        self.assertEqual(config, original)

    def test_paired_comparison_rejects_misaligned_worlds(self):
        with self.assertRaisesRegex(ValueError, 'MATCHED_SEED'):
            paired_difference([self.world(seed=1)], [self.world(seed=2)])
        with self.assertRaisesRegex(ValueError, 'MATCHED_WORLD_COUNT'):
            paired_difference([self.world()], [])

    def test_loss_and_refusal_do_not_become_profit(self):
        result = summarize([self.world(profit=-8), self.world(profit=-2, survival=False)], [100], 48)
        self.assertEqual(result['profitable_world_fraction'], 0)
        self.assertEqual(result['cash_survival_fraction'], .5)
        self.assertEqual(result['profit_microUSD']['mean'], -5)

    def test_next_action_keeps_other_condition_failure_visible(self):
        report = {'paired_comparisons': {}, 'summary': {}}
        for family, profit in [('ordinary', 10), ('shock', -30)]:
            report['paired_comparisons'][family] = {'joint_channel': {'mean_delta_collections_microUSD': 20, 'mean_delta_profit_microUSD': profit}}
            report['summary'][family] = {'joint_channel': {'cash_survival_fraction': 1}}
        result = next_action(report)
        self.assertEqual(result['selected']['family'], 'ordinary')
        self.assertEqual(result['per_condition_rankings']['shock'][0]['mean_delta_profit_microUSD'], -30)
        self.assertEqual(result['ranked_executed_interventions'][0]['mean_delta_profit_microUSD'], -10)


if __name__ == '__main__':
    unittest.main()
