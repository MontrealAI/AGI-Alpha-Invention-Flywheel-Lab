"""Native bound $100k → $1B TTM PROFIT conditional scale falsifiers."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from enterprise.scale import default_config,simulate_scale,validate_config,_identity
from connected_enterprise.scale_profit036 import (
    validate_protocol, daily_spread, summarize_existing_projection, execute,
    identity, OPENING_CENTS, TARGET_CENTS, SCHEMA, RESULT,
)

P=Path(__file__).resolve().parents[1]/'campaign/scale-profit-036/PROTOCOL.json'

def protocol():return json.loads(P.read_text())
def projection(name,seed=2610313701):return summarize_existing_projection(default_config()|protocol()['cases'][name],seed)
def anchor():return {'schema':'agi-alpha/scale-profit036-native-anchor/v1','native_profit_target_attained':False,'source_sha256':'a'*64,'worlds':[]}

class ScaleProfitTests(unittest.TestCase):
    def test_exact_frozen_protocol_and_target(self):
        p=protocol();self.assertEqual(validate_protocol(p),p)
        self.assertEqual(p['months'],60)
        self.assertEqual(p['opening_cents'],10_000_000)
        self.assertEqual(p['target_profit_cents'],100_000_000_000)
        self.assertEqual(p['seeds'],[2610313701,2610313702,2610313703,2610313704])

    def test_no_hidden_starting_customers_or_capital(self):
        for field,value in [('initial_customers',1),('opening_cash_cents',OPENING_CENTS+1),('months',61)]:
            with self.subTest(field=field):
                p=protocol();p['cases']['partner_distribution'][field]=value
                with self.assertRaisesRegex(ValueError,'NO_HIDDEN'):validate_protocol(p)

    def test_refuses_revenue_target_instead_of_profit(self):
        p=protocol();p['target_profit_cents']=1_000_000_000
        with self.assertRaisesRegex(ValueError,'ONE_BILLION_PROFIT'):validate_protocol(p)

    def test_refuses_unknown_additional_case(self):
        p=protocol();p['cases']['invented_success']={}
        with self.assertRaises(ValueError):validate_protocol(p)

    def test_refuses_replaced_seed_or_optional_stop(self):
        p=protocol();p['seeds'][-1]=99
        with self.assertRaisesRegex(ValueError,'EXACT_FIXED'):validate_protocol(p)
        p=protocol();p['stopping_rule']='STOP_AT_FIRST_WIN'
        with self.assertRaisesRegex(ValueError,'STOPPING'):validate_protocol(p)

    def test_no_default_code_behavior_change(self):
        c=default_config();c['months']=2
        self.assertEqual(_identity(simulate_scale(c,371)),'37cf1a5ecc99b3432e5c46cf40163a0058e5ada2845c2a5fa459d46afab2b508')

    def test_optin_fees_not_double_charged_or_booked_as_revenue(self):
        c=default_config()|protocol()['cases']['partner_distribution'];c['months']=5
        r=simulate_scale(c,2610313701)
        monthly=r['monthly']
        self.assertEqual(sum(m['tax_proxy_from_receipts_cents'] for m in monthly),sum(m['collected_revenue_cents']*2500//10000 for m in monthly))
        self.assertEqual(r['ending_cash_cents'],c['opening_cash_cents']+r['cumulative_collected_revenue_cents']-r['cumulative_cost_cents'])
        self.assertGreater(sum(m['processor_fees_net_settled_cents'] for m in monthly),0)
        self.assertGreater(sum(m['tax_proxy_from_receipts_cents'] for m in monthly),0)

    def test_no_processor_credit_from_receivables(self):
        c=default_config()|protocol()['cases']['partner_distribution'];c['months']=3
        r=simulate_scale(c,2610313701)
        for m in r['monthly']:
            self.assertEqual(m['cash_cents'],OPENING_CENTS+m['cumulative_collected_revenue_cents']-m['cumulative_cost_cents'])
            self.assertEqual(m['available_cash_cents'],m['cash_cents']-m['restricted_cash_cents'])
            self.assertGreaterEqual(m['available_cash_cents'],0)

    def test_cash_tax_proxy_not_a_statutory_tax_model(self):
        p=protocol(); self.assertEqual({x['cash_receipt_tax_proxy_bps'] for x in p['cases'].values()},{2500})
        self.assertTrue(all('tax/levy proxy' in x['assumptions'] for x in p['cases'].values()))

    def test_invalid_optin_boolean_fee_contract(self):
        c=default_config()|protocol()['cases']['partner_distribution'];c['net_settlement_fees']=1
        with self.assertRaisesRegex(ValueError,'EXPLICIT_NET_SETTLEMENT'):validate_config(c)

    def test_invalid_tax_envelope(self):
        for invalid in [True,-1,10001,0.25]:
            c=default_config()|protocol()['cases']['partner_distribution'];c['cash_receipt_tax_proxy_bps']=invalid
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):validate_config(c)

    def test_no_365_day_result_from_short_cohort(self):
        c=default_config()|protocol()['cases']['low_ticket_incumbent'];c['months']=2
        a=summarize_existing_projection(c,2610313701)
        self.assertEqual(a['months_completed'],2)
        self.assertTrue(all(m['ttm_365day_profit_cents'] is None for m in a['monthly']))
        self.assertIsNone(a['first_attainment_month_under_hypotheses'])

    def test_profit_and_cash_are_separate_conditions(self):
        a=projection('partner_distribution')
        self.assertTrue(a['source_pricing_and_demands_are_unvalidated'])
        for m in a['monthly']:
            if m['profit_target_attained_under_hypotheses']:
                self.assertGreaterEqual(m['ttm_365day_profit_cents'],TARGET_CENTS)
                self.assertGreaterEqual(m['ttm_365day_cash_contribution_cents'],TARGET_CENTS)
                self.assertGreater(m['available_cash_cents'],0)

    def test_first_attainment_not_redefined_as_annual_run_rate(self):
        p=projection('partner_distribution')
        self.assertGreaterEqual(p['first_attainment_month_under_hypotheses'],12)
        self.assertTrue(p['monthly'][-1]['ttm_365day_profit_cents'] is not None)

    def test_partner_success_is_clearly_only_conditional(self):
        p=protocol(); result=execute(p,anchor())
        self.assertEqual(result['economic_success'],'NOT_ESTABLISHED_CONDITIONAL_PROJECTIONS_ONLY')
        self.assertEqual(result['native_annual_profit'],'NOT_ESTABLISHED')
        self.assertEqual(result['target_profit_cents'],TARGET_CENTS)
        self.assertEqual(result['opening_cash_cents'],OPENING_CENTS)
        self.assertEqual(result['additional_capital_injected_cents'],0)
        self.assertEqual(result['summary']['partner_distribution']['conditional_profit_target_crossings'],4)
        self.assertEqual(result['summary']['partner_disrupted']['conditional_profit_target_crossings'],0)
        self.assertEqual(result['summary']['partner_no_referrals']['conditional_profit_target_crossings'],0)

    def test_disrupted_is_not_silently_censored_as_a_win(self):
        r=projection('partner_disrupted')
        self.assertFalse(r['cash_survival'])
        self.assertLess(r['months_completed'],60)
        self.assertIsNone(r['first_attainment_month_under_hypotheses'])
        self.assertIn('OPERATING_CASH',r['terminal_reason'])

    def test_source_model_not_called_to_execute_live_customers(self):
        x=projection('partner_distribution')
        self.assertEqual(x['scope'],'CONDITIONAL_60_MONTH_AGGREGATE_NOT_NATIVE_EXECUTION')
        self.assertEqual(x['source_model'],'enterprise.scale.simulate_scale')

    def test_zero_byte_loss_conservation_signed_daily(self):
        for value in [0,1,-1,345,-351,10**15,-10**15]:
            with self.subTest(value=value):
                p=daily_spread(value,31);self.assertEqual(len(p),31);self.assertEqual(sum(p),value)

    def test_rolling_observer_uses_real_calendar_days(self):
        a=projection('low_ticket_incumbent')
        self.assertEqual(a['monthly'][11]['days_covered'],365)
        self.assertIsNotNone(a['monthly'][11]['ttm_365day_profit_cents'])
        self.assertIsNone(a['monthly'][10]['ttm_365day_profit_cents'])
        # November 2026 through October 2028 spans leap February 2028.
        self.assertEqual(a['monthly'][23]['days_covered'],731)

    def test_expected_failure_when_unfunded_setup(self):
        c=default_config()|protocol()['cases']['partner_distribution'];c['setup_cost_cents']=10_000_001
        p=summarize_existing_projection(c,2610313701)
        self.assertFalse(p['cash_survival'])
        self.assertEqual(p['months_completed'],0)
        self.assertIsNone(p['peak_365day_profit_cents'])

    def test_no_input_mutation_or_backfilled_account(self):
        p=protocol();prior=copy.deepcopy(p)
        execute(p,anchor());self.assertEqual(p,prior)

    def test_any_forged_native_success_anchor_refused(self):
        a=anchor();a['native_profit_target_attained']=True
        with self.assertRaisesRegex(ValueError,'REDERIVED_NATIVE'):execute(protocol(),a)

    def test_no_unknown_cost_default_allowed(self):
        p=protocol();p['cases']['partner_distribution']['attempt_cost_cents']=0
        with self.assertRaisesRegex(ValueError,'NONZERO_COMPLETE'):validate_protocol(p)

if __name__ == '__main__':unittest.main()
