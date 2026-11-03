import copy
import unittest
from dataclasses import replace
from fractions import Fraction
from omega import competitive as c
from omega import strategy


class CompetitiveTests(unittest.TestCase):
    def setUp(self):
        self.game = c.make_game()
        self.public = c.initial_public(self.game)

    def world(self, regime, adverse=False):
        return next(w for w in self.game.worlds if w.regime==regime and w.adverse==adverse)

    def test_decline_and_one_joint_budget(self):
        w=self.world('commodity',True)
        d=c.choose_bundle(self.game,w,0,strategy.PRODUCTS,19900)
        self.assertEqual(d['provider'],'decline')
        w=self.world('training')
        d=c.choose_bundle(self.game,w,1,strategy.PRODUCTS,already_spent_cents=49000)
        self.assertNotEqual(d['provider'],'us')
        self.assertLessEqual(d['price_cents'],1000)
        with self.assertRaises(ValueError): c.choose_bundle(self.game,w,0,('self_hosted',),already_spent_cents=50001)

    def test_complete_bundle_never_adds_ordinary_outcome_twice(self):
        w=self.world('training')
        d=c.choose_bundle(self.game,w,1,('self_hosted','group_webinar'))
        package=next(x for x in d['alternatives'] if len(x['products'])==2)
        self.assertEqual(package['price_cents'],39800)
        self.assertEqual(package['buyer_value_before_price_cents'],75000)
        self.assertTrue(d['ordinary_outcome_counted_once'])
        strong=c.choose_bundle(self.game,w,1,('self_hosted','group_webinar'),complement_cents=50000)
        self.assertEqual(strong['products'],['self_hosted','group_webinar'])
        self.assertLessEqual(strong['price_cents'],strong['budget_cents'])

    def test_fixed_prices_and_oneperson_cost_profiles(self):
        self.assertEqual(c.registration()['own_prices_cents'],strategy.PRICES)
        self.assertEqual(self.game.costs.packaging_hours,0)
        self.assertEqual(self.game.costs.ai_build_bill_cents,10000)
        self.assertEqual(self.game.costs.processing_cents[1],832)
        self.assertEqual(self.game.costs.webinar_facilitation_cents,0)
        self.assertEqual(self.game.costs.research_cents,100)
        self.assertEqual(c.make_game(operation='human_control').costs.packaging_hours,20)

    def test_hidden_evaluator_fields_rejected(self):
        for key in ('world_id','reached','future_sales','private_budget'):
            bad={**self.public,key:'oracle'}
            with self.subTest(key=key),self.assertRaises(ValueError): c.decide(bad)
        a=c.decide(self.public)
        self.assertEqual(a,c.decide(copy.deepcopy(self.public)))
        self.assertIsNone(a['native_authority'])

    def test_rival_response_is_exact_only_over_its_menu(self):
        p=dict(self.public,built_products=['self_hosted'])
        r=c.rival_best_response(self.game,p,['self_hosted'])
        profits=[Fraction(x['expected_profit_cents']) for x in r['alternatives']]
        self.assertEqual(Fraction(r['expected_profit_cents']),max(profits))
        self.assertGreaterEqual(Fraction(r['expected_profit_cents']),0)
        self.assertEqual(r,c.rival_best_response(self.game,copy.deepcopy(p),['self_hosted']))
        self.assertIn(None,[x['price_cents'] for x in r['alternatives']])

    def test_research_optional_and_refund_feedback_can_stop(self):
        poor=dict(self.public,available_cents=0)
        self.assertEqual(c.decide(poor)['action']['kind'],'stop')
        refunded=dict(self.public,observed_delivery_outcome='rejected_refunded')
        self.assertEqual(c.decide(refunded)['action']['kind'],'stop')
        exp=replace(self.game,costs=replace(self.game.costs,research_cents=10**10))
        self.assertNotEqual(c.decide(self.public,game=exp)['action']['kind'],'research')

    def test_equivalent_ordinary_content_reuse_has_no_invented_bonus(self):
        p=dict(self.public,content_available=True,research_signal='positive')
        a=c.decide(p,'joint'); b=c.decide(p,'ordinary_reuse')
        self.assertEqual(a['action'],b['action'])
        self.assertEqual(a['expected_remaining_profit_cents'],b['expected_remaining_profit_cents'])

    def test_no_research_arm_cannot_buy_signal(self):
        self.assertNotEqual(c.decide(self.public,'no_research')['action']['kind'],'research')
        self.assertEqual(c.decide(self.public,'nonentry')['action']['kind'],'stop')

    def test_reach_is_revealed_after_paid_action_and_never_mints_orders(self):
        p=dict(self.public,built_products=['founder_private'],research_signal='positive')
        decision=c.decide(p,'no_research')
        self.assertEqual(decision['action']['kind'],'operate')
        w=self.world('rare_founder_access')
        missing=c.realize(decision,w.id,False)
        self.assertEqual(missing['orders'],[])
        self.assertGreater(missing['cash_cost_cents'],0)
        found=c.realize(decision,w.id,True)
        self.assertGreater(len(found['orders']),0)
        self.assertTrue(all(o['buyer']['joint_choice'] for o in found['orders']))
        self.assertLessEqual(found['founder_minutes'],p['founder_minutes_available'])
        self.assertEqual(found['mature_available_cents'],p['available_cents']+found['cash_profit_cents']-found['new_residual_reserve_cents'])

    def test_tampered_predecision_refused(self):
        p=dict(self.public,built_products=['founder_private'],research_signal='positive')
        decision=c.decide(p,'no_research'); decision['public_sha256']='x'
        with self.assertRaises(ValueError): c.realize(decision,self.world('rare_founder_access').id,True)

    def test_unfunded_products_are_absent_from_buyer_menu(self):
        p=dict(self.public,built_products=['founder_private'],research_signal='positive',available_cents=2000)
        action={'kind':'operate','build':[],'offers':['founder_private']}
        r=c._row(self.game,p,action,{'price_cents':None},self.world('rare_founder_access'),True)
        self.assertEqual(r['orders'],[])
        self.assertTrue(all(x['provider']!='us' for x in r['buyer_decisions']))

    def test_realized_buyer_payoff_does_not_count_promised_refunded_outcome(self):
        choice=c.choose_bundle(self.game,self.world('training'),1,('self_hosted','group_webinar'),complement_cents=50000)
        accepted=c.buyer_payoff(choice,'accepted'); refunded=c.buyer_payoff(choice,'rejected_refunded')
        self.assertEqual(accepted['our_realized_outcome_value_cents'],110000)
        self.assertEqual(accepted['our_retained_fee_cents'],39800)
        self.assertEqual(accepted['our_realized_buyer_net_cents'],69200)
        self.assertEqual(refunded['our_realized_outcome_value_cents'],0)
        self.assertEqual(refunded['our_retained_fee_cents'],0)
        self.assertEqual(refunded['our_realized_buyer_net_cents'],-1000)
        self.assertEqual(accepted['our_incremental_buyer_net_cents'],69200-choice['best_outside_promised_net_cents'])

    def test_environment_cannot_contradict_completed_delivery(self):
        p=dict(self.public,built_products=['founder_private'],research_signal='positive',observed_delivery_outcome='accepted')
        d=c.decide(p,'no_research')
        w=next(w for w in self.game.worlds if w.signal=='positive' and w.adverse)
        with self.assertRaisesRegex(ValueError,'CONTRADICTS_COMPLETED_NATIVE_DELIVERY'):
            c.realize(d,w.id,True)

    def test_webinar_time_is_independent_of_valuation_and_not_autonomous(self):
        p=dict(self.public,built_products=['group_webinar'])
        a={'kind':'operate','build':[],'offers':['group_webinar']}
        r=c._row(self.game,p,a,{'price_cents':None},self.world('training'),False)
        self.assertEqual(r['founder_minutes'],330)
        self.assertEqual(r['session_opportunity_cents'],110000)
        self.assertEqual(r['session_cost_cents'],23700)
        self.assertIsNone(c._forecast(self.game,dict(p,founder_minutes_available=329),a))


if __name__=='__main__': unittest.main()
