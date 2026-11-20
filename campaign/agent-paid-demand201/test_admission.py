"""Fixed T01--T14 prospectively registered in PREREGISTRATION.md."""
import unittest
from admission import SOURCES, OPTIONS, decimal_amount, volume_floor, report

class RegisteredAcceptance(unittest.TestCase):
    def test_T01_search_gross_floor(self):
        self.assertEqual(volume_floor('0.005')['gross_only_necessary_annual_units'], 600_000_000_000)
    def test_T02_decision_gross_floor(self):
        self.assertEqual(volume_floor('0.02')['gross_only_necessary_annual_units'], 150_000_000_000)
    def test_T03_accepted_outcome_gross_floor(self):
        self.assertEqual(volume_floor('10000')['gross_only_necessary_annual_units'], 300_000)
    def test_T04_positive_unit_cost_increases_required_units(self):
        r = volume_floor('0.02',variable_cost='0.01')
        self.assertEqual(r['conditional_variable_cost_necessary_annual_units'],300_000_000_000)
        self.assertGreater(r['conditional_variable_cost_necessary_annual_units'],r['gross_only_necessary_annual_units'])
    def test_T05_cost_above_price_cannot_profit(self):
        for c in ('0.02','0.021'):
            r = volume_floor('0.02',variable_cost=c)
            self.assertIsNone(r['conditional_variable_cost_necessary_annual_units'])
            self.assertEqual(r['variable_margin_status'],'NO_POSITIVE_PROFIT_AT_THIS_PRICE_AND_UNIT_COST')
    def test_T06_unknown_complete_cost_not_zero(self):
        for row in report()['alternatives'][:3]:
            self.assertIsNone(row['arithmetic']['conditional_variable_cost_necessary_annual_units'])
            self.assertEqual(row['arithmetic']['complete_cost_feasibility'],'UNKNOWN')
    def test_T07_missing_real_buyer_proof_refuses_all_routes(self):
        r=report()
        self.assertEqual([x['admit_to_native_commerce'] for x in r['alternatives'][:3]],[False]*3)
        self.assertEqual(r['selected_action'],'NO_DEPLOY_RETAIN_QUALIFIED_INCUMBENT')
    def test_T08_payto_sample_not_native_collections_or_buyers(self):
        r=report()
        self.assertEqual(r['observation']['observed_directory_october_2026']['reported_wallets'],13019)
        self.assertFalse(r['sampled_payto_transfers_are_our_sales'])
        self.assertFalse(r['sampled_wallets_are_confirmed_purchasers'])
        self.assertFalse(r['actual_montreal_ai_collections_verified_by_this_instrument'])
    def test_T09_directory_not_global_market_ceiling(self):
        self.assertFalse(report()['sampled_market_is_global_ceiling'])
        self.assertEqual(report()['observation']['observed_directory_october_2026']['raw_source_sha256'],None)
    def test_T10_competitor_quote_cannot_be_multiplied_into_sales(self):
        r=report()
        self.assertEqual(r['observation']['quoted_competitor_2026_11_12']['quoted_x402_price_usd'],'0.005')
        self.assertEqual(r['alternatives'][0]['type'],'external_competitor_quoted_price')
        self.assertIsNone(r['actual_trailing_365_profit_usd'])
    def test_T11_nonentry_no_imaginary_profit(self):
        row=report()['alternatives'][3]
        self.assertEqual(row['new_operating_profit_usd'],'0')
        self.assertEqual(row['new_orders'],0)
    def test_T12_strict_decimal_rejects_nonfinite_and_float(self):
        for bad in ('NaN','-0.01','0','Infinity','not-money',True,0.01,float('nan')):
            with self.subTest(bad=repr(bad)),self.assertRaises(ValueError):
                volume_floor(bad)
    def test_T13_wallets_are_not_unique_buyers(self):
        r=report()
        self.assertFalse(r['real_human_or_agent_buyer_identity_verified'])
        self.assertEqual(r['observation']['observed_directory_october_2026']['coverage'],
                         'listed directory payTo addresses; classified transfers, not all x402')
    def test_T14_costed_arithmetic_does_not_change_commercial_evidence(self):
        self.assertIsInstance(volume_floor('10000',variable_cost='1000')['conditional_variable_cost_necessary_annual_units'],int)
        self.assertFalse(report()['complete_cost_proven'])
        self.assertFalse(report()['alternatives'][2]['admit_to_native_commerce'])

if __name__=='__main__':unittest.main()
