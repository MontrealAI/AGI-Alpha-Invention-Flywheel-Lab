import itertools
import json
from fractions import Fraction
from pathlib import Path
import unittest

from companion import admission, arrangement, cost, evaluate, event, funding_requirement, quantities, renewal_screen


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


    def test_prefix_requirement_is_necessary_and_sufficient(self):
        options = [("receipt", 1), ("receipt", 3), ("outflow", 1), ("outflow", 3), ("financing", 2)]
        for opening_reserve, actions, reserves in itertools.product((0, 2), itertools.product(options, repeat=3),
                                                                    itertools.product((0, 2), repeat=3)):
            plan = [event("opening", reserve=opening_reserve)]
            for index, ((kind, amount), reserve) in enumerate(zip(actions, reserves)):
                plan.append(event(str(index), reserve=reserve, **{kind: amount}))
            result = funding_requirement(plan)
            candidates = range(sum(row["cash_outflow"] for row in plan) + max(row["reserve_after"] for row in plan) + 1)
            feasible = []
            for initial in candidates:
                cash = initial
                valid = True
                for row in plan:
                    cash += row["settled_receipt"] + row["financing_received"] - row["cash_outflow"]
                    valid = valid and cash >= row["reserve_after"]
                if valid:
                    feasible.append(initial)
            self.assertEqual(result["minimum_opening_cash"], min(feasible))

    def test_construction_targets_meet_the_goal_and_near_misses_do_not(self):
        targets = evaluate()["construction_targets"]
        self.assertEqual(targets["baseline_complete_cost_gap"], 20)
        expected = {"baseline": 0, "fixed_cost_ten": 20, "variable_cost_five": 20, "seventeen_buyers": 21}
        for name, profit in expected.items():
            self.assertEqual(targets["cases"][name]["forced_delivery_profit"], profit)
            self.assertEqual(targets["cases"][name]["meets_desired_profit"], profit >= 20)
        for n, fixed, variable, profit in ((10, 11, 7, 19), (10, 30, 6, 10), (16, 30, 7, 18)):
            row = arrangement(n, fixed, variable, True, price=10, price_cap=10)
            self.assertEqual(row["forced_delivery_profit"], profit)
            self.assertLess(profit, targets["desired_profit"])

    def test_event_order_and_received_financing_cannot_be_netted_away(self):
        outgoing = event("pay", outflow=100)
        incoming = event("collect", receipt=100)
        finance = event("receive financing", financing=100)
        opening = event("opening")
        self.assertEqual(funding_requirement([opening, outgoing, incoming])["minimum_opening_cash"], 100)
        self.assertEqual(funding_requirement([opening, incoming, outgoing])["minimum_opening_cash"], 0)
        self.assertEqual(funding_requirement([opening, outgoing, finance])["minimum_opening_cash"], 100)
        self.assertEqual(funding_requirement([opening, finance, outgoing])["minimum_opening_cash"], 0)
        self.assertEqual(funding_requirement([event("opening", reserve=7)])["minimum_opening_cash"], 7)
        self.assertEqual(funding_requirement([opening, finance])["net_nonfinancing_cash_flow"], 0)
        protected_before_collection = [opening, outgoing, event("reserve due before collection", reserve=15),
                                       event("collect", receipt=120, reserve=15),
                                       event("successor payment", outflow=110, reserve=15)]
        self.assertEqual(funding_requirement(protected_before_collection)["minimum_opening_cash"], 115)
        for invalid in ([], [incoming], [opening, event("netted", receipt=100, outflow=100)],
                        [opening, event("netted funding", financing=100, outflow=100)],
                        [opening, event("negative", outflow=-1)],
                        [opening, {**event("promise"), "financing_committed": 100}]):
            with self.assertRaises(ValueError):
                funding_requirement(invalid)

    def test_same_profit_and_positive_terminal_cash_do_not_fund_every_prefix(self):
        cases = evaluate()["funded_renewal"]["funding"]["cases"]
        expected = {"settled_before_successor": 100, "reserve_fifteen": 105,
                    "delayed_collection_with_reserve": 225}
        for name, required in expected.items():
            row = cases[name]
            self.assertEqual(row["minimum_opening_cash"], required)
            self.assertEqual(row["recognized_profit"], 55)
            self.assertEqual(row["hypothetical_terminal_cash_at_reference_if_all_events_occur"], 155)
            self.assertEqual(row["recognized_revenue"] - row["recognized_expense"], 55)
            self.assertEqual(row["fundable_at_reference_opening"], required <= 100)
            self.assertEqual(row["financing_received"], 0)

    def test_renewal_deadline_examples_and_exact_boundaries(self):
        cases = evaluate()["funded_renewal"]["deadline"]["cases"]
        self.assertEqual(cases["base_misses_deadline"]["earliest_qualification_time"], 7)
        self.assertFalse(cases["base_misses_deadline"]["can_qualify_by_deadline"])
        for name in ("ten_more_available_units", "one_less_qualification_period"):
            self.assertEqual(cases[name]["earliest_qualification_time"], 6)
            self.assertTrue(cases[name]["can_qualify_by_deadline"])
        fractional = renewal_screen(0, 1, 2, 1, 2)
        self.assertEqual(fractional["earliest_qualification_time"], "3/2")
        self.assertTrue(fractional["can_qualify_by_deadline"])
        self.assertFalse(renewal_screen(0, 1, 2, 1, 1)["can_qualify_by_deadline"])

    def test_renewal_formula_matches_cash_at_latest_start(self):
        for opening, upfront, rate, delay, deadline in itertools.product((0, 2, 4), (0, 2, 4, 6),
                                                                       range(4), range(5), range(6)):
            row = renewal_screen(opening, upfront, rate, delay, deadline)
            possible = delay <= deadline and opening + rate * (deadline - delay) >= upfront
            self.assertEqual(row["can_qualify_by_deadline"], possible)
            if row["earliest_qualification_time"] is not None:
                self.assertEqual(Fraction(row["earliest_qualification_time"]) <= deadline, possible)
        zero = renewal_screen(20, 60, 0, 3, 6)
        self.assertIsNone(zero["earliest_qualification_time"])
        self.assertFalse(zero["can_qualify_by_deadline"])
        self.assertTrue(renewal_screen(60, 60, 0, 3, 3)["can_qualify_by_deadline"])
        self.assertFalse(renewal_screen(60, 60, 0, 4, 3)["can_qualify_by_deadline"])
        for arguments in ((20, 60, -1, 3, 6), (20, 60, 10, -1, 6), (True, 60, 10, 3, 6)):
            with self.assertRaises(ValueError):
                renewal_screen(*arguments)


if __name__ == "__main__":
    unittest.main()
