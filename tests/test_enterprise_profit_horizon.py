import copy
import unittest
from enterprise.profit_horizon import reconcile, identity, cost_sensitivity


def fixture(months=60):
    config = {'money_unit': 'cents', 'currency': 'USD', 'opening_cash_cents': 1000, 'months': months, 'settlement_months': 1}
    monthly = []
    for m in range(1, months+1):
        monthly.append({'month': m, 'cumulative_recognized_revenue_cents': m*200,
            'cumulative_cost_cents': m*50, 'cumulative_collected_revenue_cents': (m-1)*200,
            'cumulative_profit_cents': m*150, 'cash_cents': 1000+(m-1)*200-m*50,
            'restricted_cash_cents': 20, 'available_cash_cents': 980+(m-1)*200-m*50,
            'collected_revenue_cents': 0 if m==1 else 200,
            'executed_projection_attempts': 3, 'accepted_projection_work_products': 2, 'collected_projection_jobs': 2})
    run = {'scope': 'CONDITIONAL_SCALE_PROJECTION', 'config_sha256': identity(config), 'seed': 1,
        'months_completed': months, 'monthly': monthly, 'cumulative_cost_cents': months*50,
        'cumulative_collected_revenue_cents': (months-1)*200, 'cumulative_profit_cents': months*150,
        'ending_cash_cents': 1000+(months-1)*200-months*50, 'restricted_cash_cents': 20,
        'terminal_receivables_cents': 200, 'ending_unrestricted_cash_cents': 980+(months-1)*200-months*50,
        'cash_survival': True, 'terminal_reason': 'HORIZON_COMPLETED'}
    return run, config


class ProfitHorizonTests(unittest.TestCase):
    def test_exact_60_minus_48_and_components(self):
        r,c=fixture(); out=reconcile(r,c,1800)
        self.assertEqual(out['latest_complete_12_month_period']['accrual_profit_cents'],1800)
        self.assertEqual(out['first_trailing_12_profit_crossing_month'],12)
        self.assertEqual(out['settled_projection_jobs_by_recorded_month'],118)

    def test_does_not_call_cumulative_profit_annual(self):
        r,c=fixture(); out=reconcile(r,c,2000)
        self.assertEqual(out['cumulative_profit_cents'],9000)
        self.assertIsNone(out['first_trailing_12_profit_crossing_month'])

    def test_no_short_cohort_annualization(self):
        r,c=fixture(11); out=reconcile(r,c,1)
        self.assertIsNone(out['latest_complete_12_month_period'])
        self.assertIsNone(out['first_trailing_12_profit_crossing_month'])

    def test_accrual_and_cash_differ_under_growing_receivables(self):
        r,c=fixture(12); out=reconcile(r,c)
        self.assertEqual(out['latest_complete_12_month_period']['accrual_profit_cents'],1800)
        self.assertEqual(out['latest_complete_12_month_period']['net_collected_less_expenses_cents'],1600)

    def test_failure_is_not_horizon_non_crossing(self):
        r,c=fixture(15); c['months']=60; r['config_sha256']=identity(c); r['cash_survival']=False
        r['terminal_reason']='OPERATING_CASH_FAILURE'; out=reconcile(r,c,9999)
        self.assertEqual(out['crossing_status'],'FAILED_BEFORE_HORIZON')

    def test_partial_failure_cost_preserved(self):
        r,c=fixture(15); c['months']=60; r['config_sha256']=identity(c); r['cash_survival']=False
        r['cumulative_cost_cents']+=10; r['cumulative_profit_cents']-=10
        r['ending_cash_cents']-=10; r['ending_unrestricted_cash_cents']-=10
        self.assertEqual(reconcile(r,c)['terminal_partial_month_residual']['cost_cents'],10)

    def test_bad_rows_fail_closed(self):
        for field,value in [('month',2),('cumulative_profit_cents',0),('cash_cents',1000),
                            ('available_cash_cents',0),('collected_revenue_cents',200),
                            ('accepted_projection_work_products',4),('cumulative_cost_cents',True)]:
            with self.subTest(field=field):
                r,c=fixture(); r['monthly'][0][field]=value
                with self.assertRaises(ValueError): reconcile(r,c)

    def test_terminal_tampering(self):
        for field in ['config_sha256','ending_cash_cents','cumulative_profit_cents','ending_unrestricted_cash_cents']:
            with self.subTest(field=field):
                r,c=fixture(); r[field]='bad' if field=='config_sha256' else r[field]+1
                with self.assertRaises(ValueError): reconcile(r,c)

    def test_no_mutation(self):
        r,c=fixture(); original=copy.deepcopy((r,c)); reconcile(r,c)
        self.assertEqual((r,c),original)

    def test_first_crossing_precedes_final_and_equality_counts(self):
        r,c=fixture(); out=reconcile(r,c,1800)
        self.assertEqual(out['first_trailing_12_profit_crossing_month'],12)
        self.assertEqual(len(out['profit_periods']),49)

    def test_negative_profits_remain_losses(self):
        period={'cost_cents':200,'accrual_profit_cents':-50}
        self.assertEqual(cost_sensitivity(period,2500,3500)['profit_after_sensitivity_cents'],-100)

    def test_rounded_cost_and_tax_no_double_count(self):
        self.assertEqual(cost_sensitivity({'cost_cents':101,'accrual_profit_cents':100},2500,2000)['profit_after_sensitivity_cents'],59)

    def test_no_pooling_worlds(self):
        results=[reconcile(*fixture(),target_cents=2000) for _ in range(8)]
        self.assertFalse(any(x['first_trailing_12_profit_crossing_month'] for x in results))

    def test_positive_integer_target_required(self):
        for target in [0,-1,True,1.5]:
            with self.assertRaises(ValueError): reconcile(*fixture(),target_cents=target)


if __name__=='__main__':unittest.main()
