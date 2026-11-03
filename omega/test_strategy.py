"""Causality, voluntariness, exact finite optimization and funding invariants."""
import unittest
from dataclasses import replace
from fractions import Fraction
from omega.strategy import (Action, Costs, PRODUCTS, PRICES, World, Game,
                            make_game, solve, execute, buyer_choice, operating_step)

class StrategyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = make_game()
        cls.expected = solve(cls.game)
        cls.no_research = solve(cls.game,'no_research')

    def test_exact_distribution_and_signal_independence(self):
        g = self.game
        self.assertEqual(len(g.worlds),16)
        self.assertEqual(sum(w.prior for w in g.worlds),1)
        for r in {w.regime for w in g.worlds}:
            for s in ('positive','negative'):
                group = [w for w in g.worlds if w.regime == r and w.signal == s]
                self.assertEqual(sum(w.prior for w in group if w.adverse)/sum(w.prior for w in group),Fraction(1,4))

    def test_expected_beats_feasible_no_research_and_nonentry(self):
        self.assertIsInstance(self.expected.expected_profit_cents,Fraction)
        self.assertGreaterEqual(self.expected.expected_profit_cents,self.no_research.expected_profit_cents)
        self.assertGreaterEqual(self.expected.expected_profit_cents,0)
        self.assertEqual(self.expected.finite_model_optimality_gap_cents,0)
        self.assertLess(self.expected.worst_profit_cents,0)  # Rational != guaranteed profit.

    def test_paid_information_is_optional_and_paid_before_signal(self):
        self.assertEqual(self.expected.root.action.kind,'research')
        for w in self.game.worlds:
            first = execute(self.game,self.expected,w.id)['trace'][0]
            self.assertEqual(first['cash_cost_cents'],self.game.costs.research_cents)
            self.assertEqual(first['mature_available_cents'],self.game.capital_cents-self.game.costs.research_cents)
        for w in self.game.worlds:
            rows = execute(self.game,self.no_research,w.id)['trace']
            self.assertNotIn('research',[r['action']['kind'] for r in rows])
        expensive = replace(self.game,costs=replace(self.game.costs,research_cents=100000000))
        self.assertNotEqual(solve(expensive).root.action.kind,'research')

    def test_same_public_history_same_action_not_world_oracle(self):
        decisions = {}
        for w in self.game.worlds:
            history = []
            for row in execute(self.game,self.expected,w.id)['trace']:
                key = repr(history)
                self.assertEqual(decisions.setdefault(key,row['action']),row['action'])
                history.append((row['action'],row.get('observation')))

    def test_negative_signal_and_adverse_outcome_can_stop(self):
        self.assertEqual(self.expected.root.children['negative'].action.kind,'stop')
        for w in self.game.worlds:
            if w.adverse and w.signal == 'positive':
                rows = execute(self.game,self.expected,w.id)['trace']
                self.assertEqual(rows[-1]['action']['kind'],'stop')
                self.assertLess(rows[-1]['quarter'],self.game.quarters)

    def test_robust_and_low_capital_nonentry(self):
        self.assertEqual(solve(self.game,'robust').root.action.kind,'stop')
        low = make_game(capital_cents=100000)
        p = solve(low)
        self.assertEqual(p.root.action.kind,'stop')
        self.assertEqual(p.expected_profit_cents,0)
        for w in low.worlds:
            self.assertEqual(execute(low,p,w.id)['working_available_cents'],100000)

    def test_order_preflight_holds_and_no_unpaid_costs(self):
        g = replace(self.game,costs=replace(self.game.costs,outreach_cents=0))
        w = next(w for w in g.worlds if w.regime == 'rare_founder_access' and not w.adverse)
        _,cash,profit,_,row = operating_step(g,w,0,('founder_private',),100000,Action('operate',(),('founder_private',)))
        self.assertEqual(row['orders'][0]['status'],'liquidity_hold')
        self.assertEqual(row['cash_cost_cents'],0)
        self.assertEqual(cash,100000)
        self.assertEqual(profit,0)

    def test_all_world_replays_funded_and_cash_economic_distinct(self):
        for w in self.game.worlds:
            result = execute(self.game,self.expected,w.id)
            self.assertGreaterEqual(result['working_available_cents'],0)
            self.assertEqual(result['realized_profit_cents'],result['realized_cash_profit_cents']-result['noncash_founder_opportunity_cents'])
            reserve = sum(r.get('new_residual_reserve_cents',0) for r in result['trace'])
            self.assertEqual(result['working_available_cents'],self.game.capital_cents+result['realized_cash_profit_cents']-reserve)

    def test_voluntary_full_outcome_outside_options_and_no_demand(self):
        w = next(w for w in self.game.worlds if w.regime == 'commodity' and w.adverse)
        for prospect in range(3):
            d = buyer_choice(self.game,w,prospect,PRODUCTS)
            self.assertEqual(d['choice'],'no_purchase')
            self.assertTrue(d['same_ordinary_outcome_available_from_outside_options'])
        w = next(w for w in self.game.worlds if w.regime == 'rare_founder_access')
        self.assertEqual(buyer_choice(self.game,w,0,PRODUCTS)['choice'],'founder_private')
        low_value = replace(self.game,founder_value_cents=100000)
        self.assertNotEqual(buyer_choice(low_value,w,0,PRODUCTS)['choice'],'founder_private')
        self.assertNotEqual(buyer_choice(self.game,w,1,PRODUCTS)['choice'],'founder_private')

    def test_outside_alternative_is_hidden_from_policy_observation(self):
        normal = next(w for w in self.game.worlds if w.regime == 'commodity' and not w.adverse)
        adverse = next(w for w in self.game.worlds if w.regime == 'commodity' and w.adverse)
        a = Action('operate',('self_hosted',),('self_hosted',))
        n = operating_step(self.game,normal,0,(),self.game.capital_cents,a)
        d = operating_step(self.game,adverse,0,(),self.game.capital_cents,a)
        self.assertEqual(n[3],d[3])
        self.assertEqual(n[3][0],('declined',)*3)
        self.assertNotEqual(n[4]['buyer_decisions'][0]['choice'],d[4]['buyer_decisions'][0]['choice'])
        self.assertEqual(n[1],d[1])
        for row in (n[4],d[4]):
            for buyer in row['buyer_decisions']:
                self.assertEqual(buyer['utilities_cents']['open_core'],buyer['utilities_cents']['self_service_incumbent'])

    def test_authored_workload_and_exception_sensitivities(self):
        c = self.game.costs
        self.assertEqual(c.founder_total_minutes,105)
        self.assertEqual(c.opportunity('founder_private'),35000)
        self.assertEqual(c.webinar_facilitation_cents,51370)
        stress = replace(c,exception_minutes_per_order=12,dispute_minutes_per_refund=20)
        self.assertEqual(stress.opportunity('founder_private',True),45667)
        self.assertEqual(stress.order('founder_private'),c.order('founder_private'))
        self.assertEqual(replace(c,founder_total_minutes=30).opportunity('founder_private'),10000)

    def test_horizon_one_against_independent_enumeration(self):
        g = make_game(quarters=1)
        candidates = [Fraction(0)]
        for p in PRODUCTS:
            a = Action('operate',(p,),(p,))
            candidates.append(sum(w.prior*operating_step(g,w,0,(),g.capital_cents,a)[2] for w in g.worlds))
        self.assertEqual(solve(g,'no_research').expected_profit_cents,max(candidates))

    def test_staged_build_and_pivot_are_legal(self):
        g = self.game
        w = next(w for w in g.worlds if w.regime == 'training' and not w.adverse)
        built,cash,_,_,_ = operating_step(g,w,0,(),g.capital_cents,Action('operate',('self_hosted',),('self_hosted',)))
        built,cash,_,_,row = operating_step(g,w,1,built,cash,Action('operate',('group_webinar',),('group_webinar',)))
        self.assertEqual(set(built),{'self_hosted','group_webinar'})
        self.assertEqual(row['action']['offers'],['group_webinar'])
        self.assertEqual(len(row['orders']),3)
        self.assertEqual(row['session_cost_cents'],g.costs.webinar_platform_cents+g.costs.webinar_unknown_base_cents+g.costs.webinar_facilitation_cents)

if __name__ == '__main__': unittest.main()
