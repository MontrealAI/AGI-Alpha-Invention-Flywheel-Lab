import unittest
from dataclasses import replace
from connected_enterprise.renewable_market068 import Scenario, MICRO, simulate, cases, digest, renewed_work_identity

class MarketRenewal068Tests(unittest.TestCase):
    def test_new_organizations_enter_each_month(self):
        r=simulate(replace(Scenario(),months=3))['rows']
        self.assertEqual([v['eligible_organizations'] for v in r],[502000,504000,506000])
        self.assertTrue(all(v['new_customers']>0 for v in r))
    def test_repeat_deliveries_need_no_new_marketing(self):
        r=simulate(replace(Scenario(),months=3,opening_customers=1000,
                           monthly_marketing_target_micro=0,prior_profit_reinvestment_bps=0))['rows']
        self.assertTrue(all(x['accepted_deliveries']>0 for x in r))
        self.assertTrue(all(x['new_customers']==0 for x in r))
    def test_no_income_from_uncontacted_job_stock(self):
        r=simulate(replace(Scenario(),months=2,opening_customers=0,
                           monthly_marketing_target_micro=0,prior_profit_reinvestment_bps=0))['rows']
        self.assertTrue(all(x['revenue_micro']==0 for x in r))
    def test_true_prepayment_stop_at_100k(self):
        r=simulate(replace(Scenario(),months=13,opening_equity_micro=100_000*MICRO))['rows']
        self.assertEqual(r[0]['status'],'STOP_NOT_ENOUGH_CASH_FOR_FIXED_COST')
        self.assertEqual(r[-1]['status'],'HALTED_PREPAYMENT_REQUIRED')
        self.assertTrue(all(x['trailing_12_profit_micro'] is None for x in r))
    def test_budget_prevents_nonexistent_orders(self):
        r=simulate(replace(Scenario(),months=3,buyer_value_ceiling_micro=80*MICRO))['rows']
        self.assertTrue(all(x['accepted_deliveries']==0 and x['new_customers']==0 for x in r))
    def test_monthly_buyer_budget_is_explicit_and_conserved(self):
        r=simulate(replace(Scenario(),months=3,opening_customers=100))['rows']
        for x in r:
            self.assertEqual(x['externally_assumed_buyer_budget_micro'],
                             x['buyer_budget_committed_micro']+x['buyer_budget_unused_micro'])
        x=simulate(replace(Scenario(),months=3,opening_customers=100,
                            employer_external_budget_per_customer_month_micro=0))['rows']
        self.assertTrue(all(y['accepted_deliveries']==0 for y in x))
    def test_contact_rights_are_conserved(self):
        r=simulate(replace(Scenario(),months=24))['rows']
        for x in r:
            if 'active_customers' not in x:continue
            total=sum(x[k] for k in ('active_customers','never_contacted','warm_followup_pending',
                                     'dormant_eligible','dormant_unavailable','exhausted_contact_rights'))
            self.assertEqual(total,x['eligible_organizations'])
            self.assertLessEqual(x['cold_contacts'],x['eligible_organizations'])
    def test_period_specific_work_ids_are_not_replayed_old_work(self):
        source='a'*64
        old=renewed_work_identity('C1','reconciliation',1,0,source)
        new=renewed_work_identity('C1','reconciliation',2,0,source)
        self.assertNotEqual(old,new)
        self.assertNotEqual(old,renewed_work_identity('C1','reconciliation',1,0,'b'*64))
        self.assertEqual(old,renewed_work_identity('C1','reconciliation',1,0,source))
        with self.assertRaises(ValueError): renewed_work_identity('C1','reconciliation',1,0,'not-sha')
    def test_successive_months_not_fresh_account_reseeds(self):
        r=simulate(replace(Scenario(),months=4))['rows']
        self.assertEqual(r[0]['opening_cash_micro'],20_000_000*MICRO)
        for a,b in zip(r,r[1:]):self.assertEqual(a['closing_cash_micro'],b['opening_cash_micro'])
    def test_cash_revenue_and_cost_match(self):
        a=Scenario();r=simulate(a)['rows']
        self.assertEqual(r[-1]['closing_cash_micro'],a.opening_equity_micro+sum(x['profit_micro'] for x in r))
        for x in r:
            self.assertEqual(x['profit_micro'],x['revenue_micro']-x['expense_micro'])
            self.assertGreaterEqual(x['cash_available_after_tail_micro'],0)
            self.assertLessEqual(x['accepted_deliveries'],x['admitted_attempts'])
            self.assertLessEqual(x['admitted_attempts'],x['underlying_serviceable_packets_month'])
    def test_no_collection_not_fictional_cash(self):
        r=simulate(replace(Scenario(),months=4,collection_bps=0))['rows']
        for x in r:
            if 'collections_micro' in x:self.assertEqual(x['collections_micro'],0)
    def test_reactivation_is_not_a_new_cold_organization(self):
        x=simulate(replace(Scenario(),months=12,opening_customers=200000,monthly_retention_bps=5000))['rows']
        self.assertTrue(any(r.get('reactivated',0)>0 for r in x))
    def test_no_total_market_cap_from_original_loaded_cohort(self):
        a=replace(Scenario(),opening_customers=0,new_eligible_organizations_per_month=10000,months=12)
        r=simulate(a)['rows']
        self.assertEqual(r[-1]['eligible_organizations'],620000)
        self.assertGreater(r[-1]['active_customers'],0)
    def test_outreach_allocation_has_no_free_onboarding(self):
        r=simulate(replace(Scenario(),months=2))['rows']
        for x in r:
            self.assertEqual(x['onboarding_micro'],x['new_customers']*Scenario().onboarding_micro)
            self.assertEqual(x['outreach_micro'],x['cold_contacts']*Scenario().cold_contact_micro+
                x['followup_contacts']*Scenario().followup_contact_micro+x['winback_contacts']*Scenario().winback_contact_micro)
    def test_no_success_claim_before_full_year(self):
        r=simulate(replace(Scenario(),months=11))
        self.assertTrue(all(x['trailing_12_profit_micro'] is None for x in r['rows']))
    def test_high_ai_cost_reduces_net(self):
        low=simulate(replace(Scenario(),months=12))['rows'][-1]['trailing_12_profit_micro']
        high=simulate(replace(Scenario(),months=12,first_attempt_micro=30*MICRO,accepted_completion_micro=30*MICRO))['rows'][-1]['trailing_12_profit_micro']
        self.assertTrue(high is None or high < low)
    def test_input_hash_and_finance_scenarios_are_separate(self):
        a=replace(Scenario(),months=12)
        x=simulate(a);y=simulate(a)
        self.assertEqual(digest(x),digest(y))
        self.assertNotEqual(x['input_sha256'],simulate(replace(a,opening_equity_micro=100_000*MICRO))['input_sha256'])
    def test_negative_and_invalid_inputs_refused(self):
        with self.assertRaises(ValueError):simulate(replace(Scenario(),monthly_retention_bps=10001))
        with self.assertRaises(ValueError):simulate(replace(Scenario(),months=0))
    def test_two_million_reachable_is_a_sensitivity_not_a_paid_order(self):
        r=simulate(replace(Scenario(),eligible_organizations=2_000_000))
        self.assertIsNotNone(r['trailing_12_milestone_months']['3000000000'])
        self.assertIn('CONDITIONAL',r['evidence'])
    def test_no_annual_profit_when_stopped(self):
        r=simulate(replace(Scenario(),months=24,opening_equity_micro=0))['rows']
        self.assertTrue(all(x['trailing_12_profit_micro'] is None for x in r))
    def test_stress_cases_run_without_invented_revenue(self):
        s=cases()
        self.assertIn('no_collection',s['cases'])
        self.assertIsNone(s['cases']['small_100k_no_extra_finance']['first_3b_month'])

if __name__=='__main__':unittest.main()
