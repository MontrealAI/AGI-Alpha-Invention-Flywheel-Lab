import itertools
import json
from fractions import Fraction
from pathlib import Path
import unittest

from companion import admission, arrangement, cost, evaluate, quantities


class CompanionTests(unittest.TestCase):
    def test_published_results_reproduce_exactly(self):
        self.assertEqual(json.loads(Path(__file__).with_name("results.json").read_text()), evaluate())

    def test_joint_construction_and_strong_complete_tie(self):
        result = evaluate()
        rows = {(r["production"], r["arrangement"]): r for r in result["arrangements"]}
        expected = {("ordinary", "individual"): (320, -200, False),
                    ("ordinary", "pooled"): (140, -20, False),
                    ("new", "individual"): (370, -250, False),
                    ("new", "pooled"): (100, 20, True)}
        for key, (complete, profit, possible) in expected.items():
            self.assertEqual((rows[key]["complete_production_cost"], rows[key]["forced_delivery_profit"],
                              rows[key]["profitable_voluntary_price_exists"]), (complete, profit, possible))
        strong = result["strong_complete_alternative"]
        self.assertEqual(strong["candidate"], strong["ordinary_constructor"])
        self.assertEqual(strong["profit_difference"], 0)
        self.assertEqual(rows[("new", "pooled")]["buyer_surplus_if_accepted"], 10)

    def test_buyer_choice_and_exact_price_condition_on_small_grid(self):
        for n, fixed, variable, pooled, value in itertools.product(range(1, 9), range(0, 13, 3),
                                                                  range(0, 8), (False, True), range(0, 13)):
            row = arrangement(n, fixed, variable, pooled, price=value, value=value)
            self.assertFalse(row["strict_buyer_participation"])
            self.assertEqual(row["conditional_recognized_revenue"], 0)
            self.assertFalse(row["execute_this_offer"])
            repeated = [variable] * n + ([fixed] if pooled else [fixed] * n)
            complete = sum(repeated)
            self.assertEqual(row["complete_production_cost"], complete)
            feasible = row["profitable_voluntary_price_exists"]
            if feasible:
                witness = (Fraction(complete, n) + value) / 2
                self.assertLess(witness, value)
                self.assertGreater(n * witness, complete)
            else:
                self.assertLessEqual(n * value, complete)
        self.assertEqual(cost(0, 30, 7, True), 0)

    def test_collection_and_reservation_change_cash_not_profit(self):
        for collected in range(121):
            for reserve in range(collected + 1):
                q = quantities(100, 120, collected, 100, reserve)
                self.assertEqual(q["recognized_profit"], 20)
                self.assertEqual(q["cash"] + q["costs_expensed_and_paid"], 100 + collected)
                self.assertEqual(q["cash"], q["available_cash"] + reserve)
                self.assertEqual(q["uncollected_receivable"] + collected, 120)
                self.assertEqual(admission(q["available_cash"], 110)["fundable"], collected - reserve >= 110)
        late = evaluate()["failure_cases"]["late_collection"]
        held = evaluate()["failure_cases"]["protected_cash"]
        self.assertEqual(late["quantities"]["available_cash"], 0)
        self.assertEqual(held["quantities"]["available_cash"], 105)
        self.assertFalse(late["successor"]["fundable"])
        self.assertFalse(held["successor"]["fundable"])

    def test_value_demand_imitation_and_acceptance_fail_independently(self):
        cases = evaluate()["failure_cases"]
        self.assertEqual(cases["buyer_value_nine"]["profit_supremum_at_open_value_bound"], -10)
        self.assertEqual(cases["only_five_buyers"]["forced_delivery_profit"], -5)
        self.assertEqual(cases["imitation_price_seven"]["forced_delivery_profit"], -30)
        self.assertEqual(cases["imitation_price_seven"]["profit_upper_bound_under_response"], -30)
        self.assertFalse(cases["imitation_price_seven"]["profitable_voluntary_price_exists"])
        copied = arrangement(10, 30, 7, True, price=12, price_cap=7)
        self.assertEqual(copied["conditional_recognized_revenue"], 0)
        self.assertFalse(copied["execute_this_offer"])
        self.assertEqual(cases["acceptance_failed"]["quantities"]["recognized_profit"], -100)
        self.assertEqual(cases["acceptance_failed"]["offer"]["conditional_recognized_revenue"], 0)
        for key in ("buyer_value_nine", "only_five_buyers", "imitation_price_seven"):
            self.assertEqual(cases[key]["best_of_this_offer_and_non_entry"], 0)
            self.assertFalse(cases[key]["execute_this_offer"])

    def test_successor_funding_and_enablement_are_distinct(self):
        result = evaluate()
        cap = result["capability_successor"]
        self.assertFalse(cap["without_inherited_means"]["fundable"])
        self.assertTrue(cap["with_inherited_means"]["fundable"])
        self.assertFalse(cap["initial_funds_with_inherited_means"]["fundable"])
        self.assertTrue(cap["expanded_conventional_alternative"]["fundable"])
        self.assertEqual(cap["accepted_complete_history"]["cash"], 155)
        self.assertEqual(cap["accepted_complete_history"]["recognized_profit"], 55)
        fund = result["mere_financing_successor"]
        self.assertEqual(fund["without_inherited_means"], fund["with_inherited_means"])
        self.assertFalse(fund["initial_funds"]["fundable"])
        self.assertEqual(fund["accepted_complete_history"]["cash"], 135)
        self.assertEqual(fund["accepted_complete_history"]["recognized_profit"], 35)

    def test_equal_content_control_does_not_invent_policy_gain(self):
        control = evaluate()["crossed_discovery_negative_control"]
        cells = {(r["procedure"], r["inherited_artifact"]): r for r in control["cells"]}
        for inherited in (False, True):
            self.assertEqual(cells[("reference", inherited)]["continuation_cost"],
                             cells[("revised", inherited)]["continuation_cost"])
        for row in cells.values():
            self.assertEqual(row["continuation_cost"] + row["earlier_asset_construction"], 40)
        self.assertFalse(control["improved_inventor_established"])

    def test_invalid_inputs_cannot_create_unfunded_cash(self):
        for arguments in ((0, 0, 0, 1), (100, 120, 121, 100), (100, 120, 120, 100, 121)):
            with self.assertRaises(ValueError):
                quantities(*arguments)
        with self.assertRaises(ValueError):
            cost(-1, 30, 7, True)
        with self.assertRaises(ValueError):
            cost(True, 30, 7, True)
        with self.assertRaises(ValueError):
            admission(0, -1)


if __name__ == "__main__":
    unittest.main()
