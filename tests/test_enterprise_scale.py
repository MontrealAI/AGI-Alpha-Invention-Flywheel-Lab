import copy
import unittest
from enterprise.scale import default_config, evaluate_scale, simulate_scale, validate_config


class ScaleTests(unittest.TestCase):
    def cfg(self):
        c = default_config()
        c['months'] = 18
        c['targets_annual_collected_cents'] = [1_000_000, 10**16]
        return c

    def test_replay_and_distinct_revenue_measures(self):
        c = self.cfg()
        a = simulate_scale(c, 100)
        self.assertEqual(a, simulate_scale(c, 100))
        self.assertEqual(a['scope'], 'CONDITIONAL_SCALE_PROJECTION')
        self.assertTrue(a['monthly'])
        for i, row in enumerate(a['monthly']):
            self.assertEqual(row['cash_cents'], c['opening_cash_cents'] + row['cumulative_collected_revenue_cents'] - row['cumulative_cost_cents'])
            self.assertEqual(row['annualized_collected_run_rate_cents'], row['collected_revenue_cents'] * 12)
            self.assertEqual(row['trailing_12_collected_revenue_cents'], sum(x['collected_revenue_cents'] for x in a['monthly'][max(0, i - 11):i + 1]))
            self.assertGreaterEqual(row['cash_cents'], row['restricted_cash_cents'])

    def test_positive_conditional_path_and_unreached_large_milestone(self):
        a = simulate_scale(self.cfg(), 100)
        self.assertTrue(a['cash_survival'])
        self.assertIsNotNone(a['milestones']['1000000'])
        self.assertIsNone(a['milestones'][str(10**16)])
        self.assertGreater(a['cumulative_collected_revenue_cents'], 0)

    def test_zero_demand_has_no_implicit_customers(self):
        c = self.cfg()
        c.update(initial_customers=0, choice_probability=0.)
        a = simulate_scale(c, 1)
        self.assertEqual(a['cumulative_collected_revenue_cents'], 0)
        self.assertTrue(all(r['active_customers'] == 0 for r in a['monthly']))
        self.assertTrue(all(t is None for t in a['milestones'].values()))

    def test_capacity_and_supplier_outage_constrain_work(self):
        c = self.cfg()
        c.update(initial_capacity_jobs=0, supplier_capacity_jobs=0)
        a = simulate_scale(c, 2)
        self.assertEqual(a['cumulative_collected_revenue_cents'], 0)
        self.assertTrue(all(r['executed_projection_attempts'] == 0 for r in a['monthly']))
        self.assertIn('supplier_capacity_or_outage', a['binding_constraints'])

    def test_market_is_finite(self):
        c = self.cfg()
        c.update(reachable_market_customers=20, initial_customers=20)
        a = simulate_scale(c, 3)
        self.assertTrue(all(r['ever_acquired_customers'] <= 20 for r in a['monthly']))
        self.assertTrue(all(r['new_activated'] == 0 for r in a['monthly']))

    def test_seed_capital_not_reset_or_auto_financed(self):
        c = self.cfg()
        c.update(opening_cash_cents=10, setup_cost_cents=1_000_000)
        a = simulate_scale(c, 4)
        self.assertFalse(a['cash_survival'])
        self.assertEqual(a['ending_cash_cents'], 10)
        self.assertEqual(a['months_completed'], 0)
        self.assertGreater(a['peak_additional_capital_needed_cents'], 0)

    def test_censored_quantiles_include_failures(self):
        c = self.cfg()
        result = evaluate_scale(c, [10, 11])
        for regime in result['regimes'].values():
            target = regime['milestones'][str(10**16)]
            self.assertEqual(target['reached'], 0)
            self.assertEqual(target['not_reached'], 2)
            self.assertIsNone(target['censored_quantiles_months']['p50'])
            self.assertEqual(target['times_months_including_right_censoring'], [None, None])

    def test_unknown_malformed_and_nonfinite_rejected(self):
        c = self.cfg()
        for key, value in [('currency', 'CAD'), ('choice_probability', 1.1), ('utilization_probability', float('nan')), ('months', True), ('targets_annual_collected_cents', [0]), ('targets_annual_collected_cents', [{}])]:
            bad = copy.deepcopy(c)
            bad[key] = value
            with self.assertRaises(ValueError):
                validate_config(bad)
        c['unused'] = 1
        with self.assertRaises(ValueError):
            validate_config(c)
        with self.assertRaises(ValueError):
            evaluate_scale(self.cfg(), [{}])

    def test_arbitrarily_large_positive_target_supported(self):
        c = self.cfg()
        c['targets_annual_collected_cents'] = [10**30]
        self.assertIsNone(simulate_scale(c, 5)['milestones'][str(10**30)])

    def test_anchor_is_provenance_not_growth_or_actual_cash(self):
        c = self.cfg()
        a = simulate_scale(c, 6)
        c['small_cohort_anchor'] = {'scope': 'SIMULATED', 'profit_usd': 1000000000}
        b = simulate_scale(c, 6)
        self.assertEqual(a['monthly'], b['monthly'])
        self.assertEqual(b['small_cohort_anchor']['profit_usd'], 1000000000)

    def test_tax_does_not_become_revenue(self):
        c = self.cfg()
        a = simulate_scale(c, 7)
        c['sales_tax_bps'] = 2000
        b = simulate_scale(c, 7)
        self.assertEqual(a['cumulative_collected_revenue_cents'], b['cumulative_collected_revenue_cents'])
        self.assertEqual(a['ending_cash_cents'], b['ending_cash_cents'])
        self.assertGreater(sum(r['tax_collected_and_remitted_cents'] for r in b['monthly']), 0)

    def test_no_collection_still_costs_work(self):
        c = self.cfg()
        c['collection_probability'] = 0.
        a = simulate_scale(c, 8)
        self.assertEqual(a['cumulative_collected_revenue_cents'], 0)
        self.assertGreater(a['cumulative_cost_cents'], c['setup_cost_cents'])
        self.assertTrue(any(r['uncollected_projection_jobs'] for r in a['monthly']))
