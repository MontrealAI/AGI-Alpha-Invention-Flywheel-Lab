import copy
import unittest
from commercial.portfolio_growth import NativeProjection, audit_projection, default_policy, price_choice, run_world, money, guarded_growth_budget


class Growth011Tests(unittest.TestCase):
    def service(self, cost=5):
        return {'id': 'authored_test', 'technical_qualified': True, 'human_first_cost': money(100),
                'human_repeat_cost': money(80), 'agent_cost': money(cost), 'source_sha256': 'a' * 64,
                'qualification_scope': 'Authored functional test, not commercial evidence.'}

    def public(self, **changes):
        x = {'reputation': .82, 'rival_reputation': .8, 'rival_price_fraction': .65, 'repeat_customer_share': 0.}
        return x | changes

    def test_private_information_is_not_a_seller_input(self):
        with self.assertRaises(ValueError):
            price_choice(self.service(), default_policy()['scenarios'][0], default_policy(), self.public(hidden_reservation=999))

    def test_first_and_repeat_human_costs_are_not_double_charged(self):
        r = price_choice(self.service(), default_policy()['scenarios'][0], default_policy(), self.public())
        q = r['selected']
        self.assertEqual(q['first_price'], int(money(100) * q['factor']))
        self.assertEqual(q['repeat_price'], int(money(80) * q['factor']))
        self.assertEqual(r['deviation_residual'], 0)
        self.assertTrue(any(c['factor'] == .95 for c in r['curve']))
        self.assertTrue(any(c['factor'] > 1 for c in r['curve']))
        self.assertTrue(any(c['factor'] < .5 for c in r['curve']))

    def test_no_bid_does_not_buy_unprofitable_growth(self):
        p = default_policy();p['horizon_months'] = 6
        r = run_world([self.service(10000)], p, p['scenarios'][0], 1, 'earned_reinvestment', retain=True)
        self.assertEqual(r['paid_jobs'], 0)
        self.assertEqual(r['new_customers'], 0)
        self.assertEqual(r['earned_funded_cycles'], 0)
        self.assertTrue(all(x['operating_complete_cost'] == p['maintenance_monthly'] for x in r['monthly']))

    def test_seed_is_not_earned_and_invoice_is_not_collected_cash(self):
        p = default_policy(); b = NativeProjection(p, p['scenarios'][0])
        try:
            b.native('invoice', 'uncollected', money(1000), month=0)
            self.assertEqual(b.state()['unrestrictedEarned'], 0)
            with self.assertRaises(ValueError):
                b.native('earned_work', 'seed-misuse', money(1), month=0, expected_net=1, artifact_sha256='b' * 64)
        finally:b.close()

    def test_unqualified_tail_release_rejected(self):
        p = default_policy();b = NativeProjection(p, p['scenarios'][0])
        try:
            b.native('invoice', 'invoice', money(100), month=0)
            b.native('settlement', 'settlement', money(100), month=0)
            with self.assertRaises(ValueError):b.expire(1, 1)
            b.expire(2, 2)
            with self.assertRaises(ValueError):b.expire(2, 2)
            self.assertTrue(audit_projection(p, b.events, b.state(), p['scenarios'][0])['accepted'])
        finally:b.close()

    def test_native_event_replay_rejects_summary_and_collection_mutations(self):
        p = default_policy();b = NativeProjection(p, p['scenarios'][0])
        try:
            b.native('invoice', 'invoice', money(100), month=0)
            b.native('settlement', 'settlement', money(90), month=1)
            with self.assertRaises(ValueError):b.native('settlement', 'settlement', money(90), month=1)
            forged = copy.deepcopy(b.state());forged['cash'] += 1
            with self.assertRaises(ValueError):audit_projection(p, b.events, forged, p['scenarios'][0])
            events = copy.deepcopy(b.events);events[-1]['amount'] += 1
            with self.assertRaises(ValueError):audit_projection(p, events, b.state(), p['scenarios'][0])
        finally:b.close()

    def test_earned_commitments_precede_cost_and_onboarding_is_once(self):
        p = default_policy();p['horizon_months'] = 16
        r = run_world([self.service()], p, p['scenarios'][0], 1, 'earned_reinvestment', retain=True)
        self.assertGreater(r['repeat_jobs'], 0)
        self.assertEqual(r['new_customers'], r['one_time_onboardings'])
        self.assertEqual(sum(x['simulated_jobs_produced'] for x in r['monthly']), r['one_time_onboardings'] + r['repeat_jobs'])
        for month in r['monthly']:
            for category in month['categories']:
                if not category.get('no_bid'):
                    self.assertEqual(category['provider_onboarding_cost'], category['new_customers'] * p['onboarding_cost'])
        for e in r['native_projection_events']:
            if e['op'] == 'earned_work':
                self.assertGreaterEqual(e['before']['unrestrictedEarned'], e['amount'])
                self.assertGreater(e['extra']['expected_net'], 0)

    def test_target_is_trailing_year_not_annualized_or_cumulative(self):
        p = default_policy();p['horizon_months'] = 11;p['target_trailing_year_revenue'] = 1
        r = run_world([self.service()], p, p['scenarios'][0], 1, 'earned_reinvestment')
        self.assertGreater(r['annualized_run_rate'], 1)
        self.assertIsNone(r['target_month'])

    def test_frozen_seed_replay_is_deterministic(self):
        p = default_policy();p['horizon_months'] = 8
        a = run_world([self.service()], p, p['scenarios'][1], 7, 'hold_capacity')
        b = run_world([self.service()], p, p['scenarios'][1], 7, 'hold_capacity')
        self.assertEqual(a, b)

    def test_guarded_growth_keeps_pending_obligations_and_operating_windows(self):
        p = default_policy();s = p['scenarios'][1]
        state = {'unrestrictedEarned': money(1000), 'available': money(1000)}
        history = [{'collections': money(250), 'operating_complete_cost': money(200)}]
        quote = guarded_growth_budget(state, history, [{'invoice': money(500)}], s, p)
        self.assertGreaterEqual(quote['buffer'], money(800))
        self.assertLess(quote['spendable_earned'], money(200))
        self.assertEqual(guarded_growth_budget(state, [{'collections': 0, 'operating_complete_cost': money(200)}], [], s, p)['spendable_earned'], 0)


if __name__ == '__main__':unittest.main()
