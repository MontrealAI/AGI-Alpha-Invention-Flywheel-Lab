"""Independent checks for frozen COMPLETE-ARRANGEMENTS242 conditional research."""
import unittest

from enterprise.complete_arrangements242 import (
    STRESS_CASES, compare, evaluate, policy_names, registered_cases,
)
from enterprise.mixed_bundle240 import frozen_case, optimize_mixed_bundle


class CompleteArrangements242Tests(unittest.TestCase):
    def test_frozen_source_cases_and_immutable_policy_set(self):
        cases = registered_cases()
        self.assertEqual(list(cases), ["BASE", "PRICE_WAR", "NO_ARRIVAL", "NONPAYMENT", "REPEAT"])
        self.assertEqual(cases["BASE"], frozen_case())
        self.assertEqual(len(policy_names()), 20)
        self.assertEqual(len(set(policy_names())), 20)
        self.assertEqual(cases["PRICE_WAR"]["quotes"][0]["rival"]["price"], 5)
        self.assertEqual(cases["PRICE_WAR"]["quotes"][1]["rival"]["price"], 10)

    def test_independent_exact_arithmetic_standalone_b_beats_failed_bundle(self):
        case = registered_cases()["BASE"]
        parent = optimize_mixed_bundle(case["publics"], case["quotes"],
                                       case["regime"], case["model"])
        self.assertEqual(parent["decision"], "NO_BID_NONPOSITIVE_COMPLETE_CONTRIBUTION")
        b = evaluate("STANDALONE_B@0.95", case)
        # Seven source factors all choose B from us over the rival, human and
        # self-service at this exact authored standalone price.
        self.assertEqual(b["price"], 47.5)
        self.assertEqual(b["initial_choice_probability"], 1)
        self.assertEqual(b["initial_win_probability"], 1)
        self.assertEqual(b["initial_attempt_cost"], 21)
        self.assertAlmostEqual(b["contribution"], 25.5)
        self.assertLess(evaluate("STANDALONE_A@0.95", case)["contribution"], 0)
        self.assertTrue(all(evaluate("BUNDLE@" + str(f), case)["contribution"] < 0
                            for f in (.70, .80, .90, .95, 1., 1.05, 1.10)))

    def test_price_war_removes_standalone_b_conditional_edge(self):
        base, war = (registered_cases()[k] for k in ("BASE", "PRICE_WAR"))
        self.assertGreater(evaluate("STANDALONE_B@0.95", base)["contribution"], 0)
        self.assertEqual(evaluate("STANDALONE_B@0.95", war)["initial_choice_probability"], 0)
        self.assertEqual(evaluate("STANDALONE_B@0.95", war)["contribution"], -21)

    def test_no_arrival_is_not_free_quote_and_no_bid_is_zero(self):
        case = registered_cases()["NO_ARRIVAL"]
        self.assertEqual(evaluate("STANDALONE_B@0.95", case)["contribution"], -21)
        self.assertEqual(evaluate("RECURRING_B@0.95", case)["contribution"], -21)
        self.assertLess(evaluate("BUNDLE@0.95", case)["contribution"], 0)
        self.assertEqual(evaluate("NO_BID", case)["contribution"], 0)
        self.assertIsNone(evaluate("NO_BID", case)["price"])

    def test_three_cycle_recurring_revenue_requires_authored_repeat(self):
        cases = registered_cases()
        base_one = evaluate("STANDALONE_B@0.95", cases["BASE"])
        base_rec = evaluate("RECURRING_B@0.95", cases["BASE"])
        self.assertAlmostEqual(base_rec["contribution"], base_one["contribution"])
        repeat = evaluate("RECURRING_B@0.95", cases["REPEAT"])
        self.assertAlmostEqual(repeat["contribution"], 63.66)
        self.assertEqual(len(repeat["renewal_scores"]), 2)
        self.assertAlmostEqual(repeat["renewal_scores"][0]["conditional_reach_probability"], .8)
        self.assertAlmostEqual(repeat["renewal_scores"][1]["conditional_reach_probability"], .64)
        self.assertEqual(repeat["native_financial_authority"], [])

    def test_adverse_nonpayment_is_not_hidden(self):
        cases = registered_cases()
        base = evaluate("STANDALONE_B@0.95", cases["BASE"])
        nonpay = evaluate("STANDALONE_B@0.95", cases["NONPAYMENT"])
        self.assertLess(nonpay["contribution"], base["contribution"])
        self.assertAlmostEqual(nonpay["conditional_collected_net_receipt"], 47.5 * .3 * .9)

    def test_robust_selection_can_refuse_entire_authored_market(self):
        result = compare()
        self.assertEqual(result["robust_development_policy"], "NO_BID")
        self.assertEqual(result["robust_development_worst_case"], 0)
        self.assertEqual(result["conditional_base_best"], "STANDALONE_B@0.95")
        self.assertTrue(result["price_selected_before_adverse_case"])
        self.assertEqual(result["actual_paid_orders"], 0)
        self.assertEqual(result["actual_collected_revenue_usd"], 0)
        self.assertIsNone(result["native_trailing_365_profit_usd"])
        self.assertIsNone(result["observed_buyer_demand"])
        self.assertIsNone(result["actual_host_model_billing_usd"])
        self.assertEqual(result["native_financial_authority"], [])

    def test_candidates_have_same_declared_prices_in_every_world(self):
        result = compare()
        self.assertEqual(len(result["policy_comparisons"]), 20)
        for row in result["policy_comparisons"]:
            self.assertEqual(set(row["case_scores"]), set(registered_cases()))
            self.assertEqual(set(STRESS_CASES), {"BASE", "PRICE_WAR", "NO_ARRIVAL", "NONPAYMENT"})
            self.assertEqual(len({detail["price"] for detail in row["case_details"].values()}), 1)
            self.assertTrue(all(detail["native_financial_authority"] == []
                                for detail in row["case_details"].values()))

    def test_unregistered_policy_or_invalid_case_rejected(self):
        case = registered_cases()["BASE"]
        for policy in ("FREE_MONEY", "BUNDLE@10", "STANDALONE_C@0.95",
                       "RECURRING_B@0.96", "STANDALONE_B@nan", ""):
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                evaluate(policy, case)
        invalid = registered_cases()["BASE"]
        invalid["regime"]["arrival_probability"] = 1.5
        with self.assertRaises(ValueError):
            evaluate("NO_BID", invalid)


if __name__ == "__main__":
    unittest.main()
