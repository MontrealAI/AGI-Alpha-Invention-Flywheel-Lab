import copy
import unittest

from omega.market_buyer import decide, to_receipt, verify_quote_receipt


def offer(ident, product='self_hosted', price=29900, *, capability=1, effort=0, trust=10000, reliability=10000):
    return {'id': ident, 'product': product, 'price_cents': price, 'capability': capability,
            'effort_cents': effort, 'trust_bps': trust, 'reliability_bps': reliability}


def persona(**changes):
    result = {'id': 'synthetic-buyer-1', 'budget_cents': 100000, 'value_cents': 100000,
              'software_setup_cents': 0, 'webinar_learning_cents': 0, 'founder_access_cents': 0,
              'switching_cents': 0, 'buyer_compute_cents': 0, 'webinar_setup_reduction_cents': 0,
              'private_session_prerequisites_met': False, 'required_capability': 1,
              'outside_options': []}
    result.update(changes)
    return result


def outside(ident='free', *, price=0, effort=0, capability=1, reliability=10000):
    return {'id': ident, 'price_cents': price, 'effort_cents': effort, 'capability': capability,
            'trust_bps': 10000, 'reliability_bps': reliability}


class BuyerChoiceTests(unittest.TestCase):
    def test_strong_free_and_equal_content_reuse_win(self):
        p = persona(outside_options=[outside('free_core'), outside('ordinary_equal_content')])
        result = decide(p, [offer('paid')])
        self.assertEqual(result['selected_offer_ids'], [])
        self.assertEqual(result['buyer_net_benefit_microUSD'], 1_000_000_000)
        self.assertEqual(result['increment_over_best_outside_microUSD'], 0)

    def test_full_outcome_is_counted_once_across_all_routes(self):
        p = persona(outside_options=[outside('free_core')])
        result = decide(p, [offer('software', price=0), offer('webinar', 'group_webinar', 0)])
        for row in result['alternatives']:
            self.assertLessEqual(row['value_before_fees_microUSD'], p['value_cents'] * 10000)
        self.assertFalse(result['selected_offer_ids'])

    def test_complement_can_justify_whole_bundle(self):
        p = persona(software_setup_cents=40000, webinar_learning_cents=0,
                    webinar_setup_reduction_cents=40000,
                    outside_options=[outside(effort=80000)])
        offerings = [offer('software', price=20000),
                     offer('webinar', 'group_webinar', 5000, effort=1000, reliability=5000)]
        result = decide(p, offerings)
        self.assertEqual(result['selected_offer_ids'], ['software', 'webinar'])
        self.assertEqual(result['buyer_net_benefit_microUSD'], 54000 * 10000)
        self.assertEqual(result['selected_detail']['complementary_setup_saving_microUSD'], 20000 * 10000)
        p['budget_cents'] = 21000
        constrained = decide(p, offerings)
        self.assertNotEqual(constrained['selected_offer_ids'], ['software', 'webinar'])
        self.assertLessEqual(constrained['selected_detail']['cash_outlay_microUSD'], 21000 * 10000)

    def test_complement_bound_never_creates_negative_adoption_cost(self):
        p = persona(software_setup_cents=5000, webinar_setup_reduction_cents=999999)
        result = decide(p, [offer('s', price=1000), offer('w', 'group_webinar', 1000)])
        rows = [r for r in result['alternatives'] if len(r['offers']) == 2]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['adoption_operating_cost_microUSD'], 0)

    def test_joint_cash_budget_counts_compute_and_outside_price(self):
        p = persona(budget_cents=29900, buyer_compute_cents=100)
        self.assertEqual(decide(p, [offer('software')])['selected_id'], 'no_purchase')
        p = persona(budget_cents=100, buyer_compute_cents=60, outside_options=[outside(price=50)])
        self.assertEqual(decide(p, [])['selected_id'], 'no_purchase')

    def test_zero_and_negative_utility_choose_no_purchase(self):
        p = persona(value_cents=29900)
        self.assertEqual(decide(p, [offer('s')])['selected_id'], 'no_purchase')
        p['value_cents'] = 29899
        self.assertEqual(decide(p, [offer('s')])['selected_id'], 'no_purchase')

    def test_trust_reliability_and_effort_are_costed(self):
        p = persona(value_cents=100000, switching_cents=200, buyer_compute_cents=300)
        result = decide(p, [offer('s', price=10000, effort=100, trust=8000, reliability=5000)])
        self.assertEqual(result['value_before_fees_microUSD'], 40000 * 10000)
        self.assertEqual(result['buyer_net_benefit_microUSD'], (40000 - 10000 - 200 - 300 - 100) * 10000)

    def test_private_access_requires_prerequisites_and_is_incremental(self):
        p = persona(budget_cents=2500000, founder_access_cents=2200000,
                    outside_options=[outside('free_core')])
        offerings = [offer('private', 'founder_private', 2000000)]
        self.assertFalse(decide(p, offerings)['selected_offer_ids'])
        p['private_session_prerequisites_met'] = True
        result = decide(p, offerings)
        self.assertEqual(result['selected_offer_ids'], ['private'])
        self.assertEqual(result['value_before_fees_microUSD'], (100000 + 2200000) * 10000)
        self.assertEqual(result['selected_detail']['founder_access_value_microUSD'], 2200000 * 10000)

    def test_sessions_alone_never_deliver_the_ordinary_outcome(self):
        p = persona(budget_cents=2500000, private_session_prerequisites_met=True)
        offerings = [offer('webinar', 'group_webinar', 100),
                     offer('private', 'founder_private', 100)]
        result = decide(p, offerings)
        self.assertEqual(result['selected_id'], 'no_purchase')
        self.assertTrue(all(r['value_before_fees_microUSD'] == 0 for r in result['alternatives']))
        p['founder_access_cents'] = 1000
        access = decide(p, offerings)
        self.assertEqual(access['selected_offer_ids'], ['private'])
        self.assertEqual(access['value_before_fees_microUSD'], 1000 * 10000)
        self.assertEqual(access['selected_detail']['ordinary_outcome_value_microUSD'], 0)

    def test_webinar_can_ease_one_complete_outside_method(self):
        p = persona(webinar_setup_reduction_cents=60000,
                    outside_options=[outside('free_core', effort=40000)])
        offerings = [offer('webinar', 'group_webinar', 10000)]
        result = decide(p, offerings)
        self.assertEqual(result['selected_offer_ids'], ['webinar'])
        self.assertEqual(result['selected_detail']['outside_id'], 'free_core')
        self.assertEqual(result['selected_detail']['complementary_setup_saving_microUSD'], 40000 * 10000)
        self.assertEqual(result['buyer_net_benefit_microUSD'], 90000 * 10000)
        p['software_setup_cents'] = 30000
        result = decide(p, offerings + [offer('software', price=0)])
        complete = next(r for r in result['alternatives']
                        if len(r['offers']) == 2 and r['adoption_operating_cost_microUSD'] == 30000 * 10000)
        self.assertEqual(complete['value_before_fees_microUSD'], 100000 * 10000)
        # Both learning burdens are incurred, but only the larger one is eased.
        self.assertEqual(complete['net_utility_microUSD'], 60000 * 10000)

    def test_unqualified_webinar_cannot_reduce_process_learning(self):
        p = persona(webinar_setup_reduction_cents=50000,
                    outside_options=[outside('free_process', effort=40000)])
        result = decide(p, [offer('water_webinar', 'group_webinar', 100, capability=0)])
        self.assertFalse(result['selected_offer_ids'])

    def test_workflow_capability_and_free_routes_are_matched(self):
        p = persona(required_capability=1)
        self.assertEqual(decide(p, [offer('water', capability=0)])['selected_id'], 'no_purchase')
        p['outside_options'] = [outside('free_process', capability=1)]
        self.assertFalse(decide(p, [offer('paid_process', capability=1)])['selected_offer_ids'])

    def test_quote_and_explicit_consent_receipts_bind_price(self):
        p, offerings = persona(), [offer('software')]
        receipt = to_receipt(p, offerings, 'software', consent=True, choice_id='quarter0-buyer1')
        self.assertTrue(verify_quote_receipt(p, offerings, receipt)['accepted'])
        p2 = copy.deepcopy(p); p2['budget_cents'] -= 1
        with self.assertRaises(ValueError):
            verify_quote_receipt(p2, offerings, receipt)
        changed = copy.deepcopy(offerings); changed[0]['price_cents'] += 1
        with self.assertRaises(ValueError):
            verify_quote_receipt(p, changed, receipt)
        with self.assertRaises(ValueError):
            verify_quote_receipt(p, offerings, to_receipt(p, offerings, 'software', consent=False))
        with self.assertRaises(ValueError):
            to_receipt(p, offerings, 'software', consent=1)

    def test_version_bundles_never_buy_same_product_twice(self):
        p = persona()
        result = decide(p, [offer('old', price=10000, capability=0), offer('new', price=20000)])
        self.assertEqual(result['selected_offer_ids'], ['new'])
        self.assertTrue(all(len({x['product'] for x in row['offers']}) == len(row['offers'])
                            for row in result['alternatives']))


if __name__ == '__main__':
    unittest.main()
