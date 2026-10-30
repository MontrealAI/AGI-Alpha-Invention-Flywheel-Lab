import unittest
from connected_enterprise.pricing import price


class ConnectedPricingTests(unittest.TestCase):
    def quote(self,choices,**changes):
        terms={'anchor':40_000_000,'legacy_price':35_000_000,'public_rival_price':30_000_000,'base_resource_cost':3_000_000,'payment_bps':290,'payment_fixed':300_000,'recent_own_choices':choices};terms.update(changes)
        return price(**terms)

    def test_public_declines_trigger_competitive_action(self):
        q=self.quote([False]);self.assertEqual(q['price'],29_750_000);self.assertTrue(q['competitive_response'])
        self.assertGreater(q['forecast_direct_contribution_microUSD'],1_000_000)
        self.assertEqual(q['public_terms']['public_rival_price'],30_000_000)

    def test_no_history_or_exact_threshold_retains_legacy(self):
        for history in [[],[True],[True,True,False,False,False]]:
            q=self.quote(history);self.assertEqual(q['price'],35_000_000);self.assertFalse(q['competitive_response'])
        self.assertFalse(self.quote([True,False])['competitive_response'])

    def test_fee_grossed_floor_and_decline_unprofitable_legacy(self):
        q=self.quote([False],public_rival_price=1_000_000)
        self.assertEqual(q['price'],q['floor']);self.assertEqual(q['reason'],'direct_resource_floor_under_public_competition')
        fee=(q['price']*290+9999)//10000+300_000
        self.assertGreaterEqual(q['price']-3_000_000-fee,1_000_000)
        prior=q['price']-1;prior_fee=(prior*290+9999)//10000+300_000
        self.assertLess(prior-3_000_000-prior_fee,1_000_000)
        self.assertIsNone(self.quote([False],legacy_price=3_000_000))
        self.assertIsNone(self.quote([],legacy_price=3_000_000))
        self.assertIsNone(self.quote([False],payment_bps=10000))

    def test_strict_public_inputs_reject_private_fields_and_boolean_money(self):
        for history in [[{'buyer_choice':'rival'}],[0],['False'],[None],{'seed':1}]:
            with self.assertRaises(ValueError):self.quote(history)
        for field,value in [('anchor',True),('legacy_price',0),('payment_bps',10001),('payment_fixed',-1),('base_resource_cost',float('inf'))]:
            with self.assertRaises(ValueError):self.quote([],**{field:value})
        with self.assertRaises(TypeError):price(1,1,1,0,0,0,[],private_value=100)

    def test_public_response_never_raises_legacy_to_capture_needed_profit(self):
        q=self.quote([False],public_rival_price=60_000_000)
        self.assertEqual(q['price'],35_000_000)
        self.assertLessEqual(q['price'],q['public_terms']['legacy_price'])


if __name__=='__main__':unittest.main()
