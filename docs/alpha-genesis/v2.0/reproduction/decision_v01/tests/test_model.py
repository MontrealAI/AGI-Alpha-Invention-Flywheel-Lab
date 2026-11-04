import unittest
from dataclasses import replace
from fractions import Fraction
from itertools import product

from genesis_frontier import Config, Planner, State


class DecisionModelTests(unittest.TestCase):
    def test_baseline_scenario_policy_and_exact_value(self):
        p = Planner(Config())
        val, first = p.choose()
        self.assertEqual(first, "probe")
        self.assertEqual(val, Fraction(3441, 100))
        self.assertEqual(p.greedy_no_experiment()[0], 30)

    def test_prior_updated_without_oracle_access(self):
        p=Planner(Config())
        branches=p.outcomes(p.initial(), "probe")
        self.assertEqual(len(branches), 2)
        positive, negative = branches
        self.assertEqual(positive[0], Fraction(38,100))
        self.assertEqual(negative[0], Fraction(62,100))
        self.assertEqual(positive[2].p_good, Fraction(63,76))
        self.assertEqual(negative[2].p_good, Fraction(7,124))
        self.assertEqual(p.choose(positive[2])[1], "construct")
        self.assertTrue(p.choose(negative[2])[1].startswith("frontier:"))

    def test_strong_accessible_frontier_is_selected(self):
        p=Planner(replace(Config(), frontier_net_delivery=(28, 30)))
        self.assertIn(p.choose()[1], ("frontier:A", "frontier:B"))
        self.assertEqual(p.choose()[0], 58)

    def test_maintenance_costs_remove_invention(self):
        p=Planner(replace(Config(), maintenance_per_delivery=25))
        self.assertIn(p.choose()[1], ("frontier:A", "frontier:B"))
        self.assertEqual(p.choose()[0], 30)

    def test_no_profitable_action_is_stop(self):
        p=Planner(replace(Config(), frontier_net_delivery=(-5,-5), specialist_net_delivery=(-6,-6), constructed_net_delivery=(-4,-4), maintenance_per_delivery=25))
        self.assertEqual(p.choose(), (0, "stop"))

    def test_permission_is_not_inferred_from_release_news(self):
        p=Planner(replace(Config(), frontier_access=False))
        self.assertFalse(any(a.startswith("frontier:") for a in p.actions(p.initial())))
        with self.assertRaises(ValueError):
            p.outcomes(p.initial(), "frontier:A")

    def test_protected_cash_is_enforced(self):
        p=Planner(replace(Config(), starting_cash=20, protected_reserve=10, construction_cost=12))
        self.assertNotIn("construct", p.actions(p.initial()))
        for a in p.actions(p.initial()):
            for probability, reward, ns in p.outcomes(p.initial(), a):
                self.assertGreaterEqual(ns.cash, 10)

    def test_no_duplicate_deliveries(self):
        p=Planner(Config())
        s=p.outcomes(p.initial(),"frontier:A")[0][2]
        self.assertFalse(any(a.endswith(":A") for a in p.actions(s)))

    def test_no_false_qualification_after_failed_construction(self):
        p=Planner(Config())
        after=p.outcomes(p.initial(),"construct")
        failed=next(s for prob,reward,s in after if s.construction==-1)
        self.assertFalse(any(a.startswith("own:") for a in p.actions(failed)))
        self.assertNotIn("construct",p.actions(failed))

    def test_only_qualified_assets_enable_new_operations(self):
        p=Planner(Config())
        self.assertNotIn("own:A", p.actions(p.initial()))
        good=next(s for prob,reward,s in p.outcomes(p.initial(),"construct") if s.construction==1)
        self.assertIn("own:A",p.actions(good))
        self.assertIn("own:B",p.actions(good))

    def test_probabilities_are_normalized_at_every_branch(self):
        for prior, sens, fp in product((Fraction(0),Fraction(1,2),Fraction(1)), (Fraction(0),Fraction(3,4),Fraction(1)), (Fraction(0),Fraction(1,4),Fraction(1))):
            p=Planner(replace(Config(), initial_p_good=prior, signal_sensitivity=sens, signal_false_positive=fp))
            for action in ("probe", "construct"):
                outcomes=p.outcomes(p.initial(),action)
                self.assertEqual(sum((x[0] for x in outcomes),Fraction(0)), 1)
                for prob, reward, state in outcomes:
                    self.assertTrue(0 <= state.p_good <= 1)

    def test_unauthorized_action_rejected(self):
        p=Planner(Config())
        with self.assertRaises(ValueError):
            p.outcomes(p.initial(), "change_ground_truth")
        with self.assertRaises(ValueError):
            p.outcomes(p.initial(), "own:A")

    def test_fraction_and_float_configs_are_parsed_exactly(self):
        c=Config.from_dict({"initial_p_good":"0.35","signal_false_positive":0.1})
        self.assertEqual(c.initial_p_good,Fraction(7,20))
        self.assertEqual(c.signal_false_positive,Fraction(1,10))

    def test_completely_uninformative_probe_never_selected(self):
        p=Planner(replace(Config(), signal_sensitivity=Fraction(1,2), signal_false_positive=Fraction(1,2)))
        self.assertNotEqual(p.choose()[1],"probe")

    def test_negative_value_asset_not_used_when_available(self):
        p=Planner(replace(Config(), maintenance_per_delivery=100))
        good=next(s for prob,r,s in p.outcomes(p.initial(),"construct") if s.construction==1)
        a=p.choose(good)[1]
        self.assertIn(a,("frontier:A","frontier:B"))

    def test_independent_bruteforce_enumerator_for_short_horizon(self):
        # A deliberately separate recursion from the optimized memoized routine;
        # it exhausts the explicit finite tree of actions and observations.
        def enumerate_actions(p,s):
            if s.remaining==0 or s.delivered==3:
                return Fraction(0)
            best=Fraction(0)
            for action in p.actions(s):
                if action=="stop":
                    continue
                total=Fraction(0)
                for prob, reward, nxt in p.outcomes(s,action):
                    total+=prob*(reward+enumerate_actions(p,nxt))
                if total>best:
                    best=total
            return best
        for prior in (Fraction(1,4),Fraction(1,2),Fraction(3,4)):
            c=replace(Config(), horizon=3, initial_p_good=prior)
            p=Planner(c)
            self.assertEqual(p.choose()[0],enumerate_actions(p,p.initial()))

    def test_more_costly_build_is_not_automatically_preferred(self):
        p=Planner(replace(Config(),construction_cost=15))
        self.assertNotEqual(p.choose()[1],"construct")

    def test_non_entry_when_all_available_profits_are_nonpositive(self):
        c=replace(Config(),frontier_access=False,specialist_net_delivery=(0,0),constructed_net_delivery=(0,0),probe_cost=0,construction_cost=1)
        p=Planner(c)
        self.assertEqual(p.choose()[1],"stop")

    def test_belief_is_not_ground_truth_until_assumed_qualification(self):
        p=Planner(Config())
        observed=p.outcomes(p.initial(),"probe")
        self.assertTrue(all(0<b[2].p_good<1 for b in observed))
        assert all(b[2].construction==0 for b in observed)


if __name__ == "__main__":
    unittest.main()
