import unittest
from dataclasses import replace
from connected_enterprise.renewable_market068 import Scenario, simulate, MICRO

class Growth069CashGuardTests(unittest.TestCase):
    @staticmethod
    def challenged():
        return replace(Scenario(),months=2,opening_equity_micro=1000*MICRO,
            opening_customers=1,eligible_organizations=100000,
            new_eligible_organizations_per_month=0,monthly_capacity_packets=1,
            annual_fixed_micro=0,monthly_marketing_target_micro=2000*MICRO,
            prior_profit_reinvestment_bps=0,cold_contact_micro=MICRO,
            onboarding_micro=0,monthly_retention_bps=10000,
            customer_monthly_purchase_bps=10000,acceptance_bps=10000,
            collection_bps=10000,payment_bps=0,tail_per_accepted_micro=100*MICRO)
    def test_new_tail_is_protected_before_marketing(self):
        rows=simulate(self.challenged())['rows']
        self.assertEqual(rows[0]['accepted_deliveries'],1)
        self.assertGreaterEqual(rows[0]['closing_cash_micro'],rows[0]['protected_tail_micro'])
        self.assertNotEqual(rows[0]['status'],'STOP_UNDERFUNDED_TAIL')
        self.assertNotEqual(rows[1]['status'],'HALTED_PREPAYMENT_REQUIRED')
    def test_no_implicit_financing_on_unfunded_large_tail(self):
        rows=simulate(replace(self.challenged(),tail_per_accepted_micro=2000*MICRO))['rows']
        self.assertEqual(rows[0]['accepted_deliveries'],0)
        self.assertEqual(rows[0]['collections_micro'],0)
        self.assertGreaterEqual(rows[0]['closing_cash_micro'],0)
    def test_cash_guard_funds_reserve_without_crediting_future_collections(self):
        rows=simulate(replace(self.challenged(),collection_bps=0))['rows']
        for row in rows:
            if row.get('accepted_deliveries',0):
                self.assertGreaterEqual(row['cash_available_after_tail_micro'],0)
            if 'collections_micro' in row:
                self.assertEqual(row['collections_micro'],0)
    def test_historical_economic_result_not_rewritten(self):
        result=simulate(replace(Scenario(),eligible_organizations=2_000_000))
        self.assertEqual(result['evidence'],'CONDITIONAL_AGGREGATE_NOT_NATIVE_OR_ACTUAL_COMMERCE')
        self.assertNotIn('actual_revenue',result)
    def test_genuine_cash_inability_still_refused(self):
        rows=simulate(replace(self.challenged(),opening_equity_micro=0))['rows']
        self.assertEqual(rows[0]['closing_cash_micro'],0)
        self.assertEqual(rows[0]['accepted_deliveries'],0)
        self.assertTrue(all(row.get('accepted_deliveries',0)==0 for row in rows))

if __name__=='__main__':
    unittest.main()
