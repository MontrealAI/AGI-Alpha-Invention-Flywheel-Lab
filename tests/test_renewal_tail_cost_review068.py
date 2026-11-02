import unittest
from dataclasses import replace
from connected_enterprise.renewable_market068 import MICRO, Scenario, simulate


def priced_case(**kwargs):
    s=replace(Scenario(),months=2,opening_customers=2,monthly_retention_bps=7500,
              annual_fixed_micro=0,new_eligible_organizations_per_month=0,
              monthly_marketing_target_micro=0,prior_profit_reinvestment_bps=0,
              customer_monthly_packets=1,customer_monthly_purchase_bps=10000,
              acceptance_bps=10000,collection_bps=10000,payment_bps=0,
              first_attempt_micro=MICRO,accepted_completion_micro=MICRO,
              quote_micro=10*MICRO,tail_per_accepted_micro=3*MICRO,
              full_human_office_cost_micro=100*MICRO,avoidable_human_cost_bps=10000,
              buyer_value_ceiling_micro=100*MICRO,income_tax_bps=0)
    return replace(s,**kwargs)


class AccruedSupportAndAdmissionReview068(unittest.TestCase):
    def test_support_cost_is_accrued_once_then_paid_when_due(self):
        a=priced_case()
        first,second=simulate(a)['rows']
        self.assertEqual(first['accepted_deliveries'],1)
        self.assertEqual(second['accepted_deliveries'],0)
        self.assertEqual(first['support_accrual_micro'],3*MICRO)
        self.assertEqual(first['profit_micro'],5*MICRO)
        self.assertEqual(first['protected_tail_micro'],3*MICRO)
        self.assertEqual(second['support_cash_settled_micro'],3*MICRO)
        self.assertEqual(second['support_accrual_micro'],0)
        self.assertEqual(second['closing_cash_micro'],first['closing_cash_micro']-3*MICRO)
        self.assertEqual(second['profit_micro'],0)
        for row in (first,second):
            cumulative=sum(x['profit_micro'] for x in (first,second) if x['month']<=row['month'])
            self.assertEqual(row['closing_cash_micro']-row['protected_tail_micro'],
                             a.opening_equity_micro+cumulative)

    def test_support_reserve_prevents_unfunded_contract_at_acceptance(self):
        a=priced_case(opening_customers=1,monthly_retention_bps=10000,
                      opening_equity_micro=10*MICRO,tail_per_accepted_micro=50*MICRO,
                      months=1)
        row=simulate(a)['rows'][0]
        self.assertEqual(row['admitted_attempts'],0)
        self.assertEqual(row['accepted_deliveries'],0)
        self.assertEqual(row['protected_tail_micro'],0)
        self.assertEqual(row['closing_cash_micro'],a.opening_equity_micro)
        self.assertEqual(row['unserved_requests'],1)

    def test_rolling_year_profit_deducts_support_residuals(self):
        a=priced_case(months=12,opening_customers=50,monthly_retention_bps=10000,
                      customer_monthly_packets=1,quote_micro=20*MICRO)
        without=simulate(replace(a,tail_per_accepted_micro=0))['rows']
        with_cost=simulate(replace(a,tail_per_accepted_micro=5*MICRO))['rows']
        self.assertEqual(sum(x['accepted_deliveries'] for x in without),
                         sum(x['accepted_deliveries'] for x in with_cost))
        self.assertEqual(without[-1]['trailing_12_profit_micro']-with_cost[-1]['trailing_12_profit_micro'],
                         12*50*5*MICRO)

    def test_fixed_cost_stop_pays_matured_support_before_halting(self):
        a=priced_case(months=4,opening_customers=1,monthly_retention_bps=10000,
                      opening_equity_micro=5*MICRO,annual_fixed_micro=24*MICRO,
                      tail_per_accepted_micro=MICRO,collection_bps=0)
        first,second,third,fourth=simulate(a)['rows']
        self.assertEqual(first['accepted_deliveries'],1)
        self.assertEqual(first['protected_tail_micro'],MICRO)
        self.assertEqual(second['status'],'STOP_NOT_ENOUGH_CASH_FOR_FIXED_COST')
        self.assertEqual(second['opening_cash_micro'],first['closing_cash_micro'])
        self.assertEqual(second['support_cash_settled_micro'],MICRO)
        self.assertEqual(second['protected_tail_micro'],0)
        self.assertEqual(second['closing_cash_micro'],0)
        self.assertEqual(second['closing_cash_micro'],
                         a.opening_equity_micro+first['profit_micro'])
        for row in (third,fourth):
            self.assertEqual(row['status'],'HALTED_PREPAYMENT_REQUIRED')
            self.assertEqual(row['closing_cash_micro'],second['closing_cash_micro'])
            self.assertEqual(row['protected_tail_micro'],0)
        self.assertEqual(sum(x.get('support_cash_settled_micro',0) for x in
                             (first,second,third,fourth)),MICRO)


if __name__=='__main__':
    unittest.main()
