"""Independent semantic oracles and economically meaningful failure cases."""
from dataclasses import replace
from fractions import Fraction
from itertools import product
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import companion as c


class ProductiveCompositionTests(unittest.TestCase):
    def setUp(self):
        self.contract = c.powerset_contract(2)

    def test_pinned_obstruction_and_scope(self):
        result = c.pinned_v3_witness()
        self.assertEqual(result["same_service_union_cart_price"], 1341)
        self.assertEqual(result["quote_minus_cart"], 213)
        self.assertIn("Static public arithmetic", result["scope"])

    def test_dynamic_program_matches_full_three_service_cart_oracle(self):
        result = c.closure_study()
        self.assertEqual(result["menus"], 2187)
        self.assertEqual(result["enumerated_carts"], 279936)
        self.assertEqual(result["buyer_budget_cases"], 413343)
        self.assertEqual(result["subadditive_inequalities"], 139968)
        self.assertEqual(result["coordinate_monotonicity_cases"], 15309)
        self.assertTrue(result["all_checks_pass"])

    def test_duplicate_and_free_purchases_do_not_create_resources(self):
        menu = {1: 0, 2: 3, 3: 4}
        expected = c.cheapest_cart_prices(menu, self.contract)
        repeated = {}
        for multiplicities in product(range(3), repeat=3):
            union, cost = 0, 0
            for count, (mask, price) in zip(multiplicities, menu.items()):
                if count:
                    union |= mask
                    cost += count * price
            repeated[union] = min(repeated.get(union, cost), cost)
        self.assertEqual(expected, repeated)
        self.assertEqual(expected[3], 3)

    def test_fractional_prices_remain_exact(self):
        menu = {1: Fraction(1, 3), 2: Fraction(1, 7), 3: Fraction(1, 2)}
        self.assertEqual(c.cheapest_cart_prices(menu, self.contract)[3], Fraction(10, 21))
        self.assertEqual(c.cheapest_cart_prices(menu, self.contract), c.exhaustive_cart_prices(menu, self.contract))

    def test_partial_menu_does_not_invent_unreachable_outcomes(self):
        self.assertEqual(c.cheapest_cart_prices({1: 2}, self.contract), {0: 0, 1: 2})
        self.assertEqual(c.cheapest_cart_prices({}, self.contract), {0: 0})
        self.assertEqual(c.cheapest_cart_prices({1: 2, 2: 3}, self.contract)[3], 5)

    def test_missing_union_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing union"):
            c.cheapest_cart_prices({1: 2, 2: 3}, replace(self.contract, outcomes=(0, 1, 2)))

    def test_composition_needs_acceptance_and_rights(self):
        for name in ("composition_authorized", "union_preserves_acceptance_and_rights",
                     "repeated_services_add_no_value", "one_aggregate_checkout"):
            with self.assertRaisesRegex(ValueError, "rights"):
                c.cheapest_cart_prices({1: 1}, replace(self.contract, **{name: False}))

    def test_negative_inexact_and_nonentry_charges_fail_closed(self):
        for invalid in (-1, 0.5, True, float("nan")):
            with self.assertRaises(ValueError):
                c.cheapest_cart_prices({1: invalid}, self.contract)
        with self.assertRaisesRegex(ValueError, "non-entry"):
            c.cheapest_cart_prices({0: 1}, self.contract)
        with self.assertRaisesRegex(ValueError, "undeclared"):
            c.cheapest_cart_prices({4: 1}, self.contract)


class StrategicChoiceTests(unittest.TestCase):
    def setUp(self):
        self.contract = c.powerset_contract(2)
        self.menu = {1: 6, 2: 6, 3: 13}

    def test_cart_strictly_improves_utility_but_single_tie_is_not_joint_revenue(self):
        buyer = c.Buyer((0, 7, 7, 14), 14)
        single = c.buyer_choice(self.menu, self.contract, buyer, mode="single")
        cart = c.buyer_choice(self.menu, self.contract, buyer)
        self.assertEqual((single.outcome, single.payment, single.utility_above_outside), (1, 6, 1))
        self.assertEqual((cart.outcome, cart.payment, cart.utility_above_outside), (3, 12, 2))

    def test_hard_budget_cannot_be_relaxed_for_a_profitable_cart(self):
        buyer = c.Buyer((0, 7, 7, 14), 11)
        choice = c.buyer_choice(self.menu, self.contract, buyer)
        self.assertEqual((choice.outcome, choice.payment), (1, 6))
        self.assertEqual(choice, c.exhaustive_buyer_choice(self.menu, self.contract, buyer))

    def test_outside_indifference_and_no_demand_mean_decline(self):
        for buyer in (c.Buyer((0, 6, 6, 12), 14), c.Buyer((0, 0, 0, 0), 14),
                      c.Buyer((0, 7, 7, 14), 14, 2)):
            self.assertEqual(c.buyer_choice(self.menu, self.contract, buyer), c.DECLINE)

    def test_pessimistic_ties_include_actual_union_dependent_cost(self):
        buyer = c.Buyer((0, 7, 7, 14), 14)
        costs = {0: 0, 1: 0, 2: 5, 3: 0}
        choice = c.buyer_choice(self.menu, self.contract, buyer, mode="single", costs=costs)
        self.assertEqual((choice.outcome, choice.seller_contribution), (2, 1))

    def test_unknown_outcome_values_or_costs_are_not_filled_in(self):
        with self.assertRaisesRegex(ValueError, "complete"):
            c.buyer_choice(self.menu, self.contract, c.Buyer((0, 7, 7), 14))
        with self.assertRaisesRegex(ValueError, "cost"):
            c.buyer_choice(self.menu, self.contract, c.Buyer((0, 7, 7, 14), 14), costs={0: 0, 1: 2})

    def test_full_finite_optimizer_and_independent_control_tie(self):
        result = c.finite_menu_study()
        self.assertEqual(result["menus"], 4096)
        self.assertEqual(sum(result[key] for key in ("cart_revenue_higher", "cart_revenue_lower", "revenue_ties")), 4096)
        self.assertEqual(result["quoted_joint_above_cart"], 560)
        for arm in result["optima"].values():
            self.assertEqual(arm["menu"], {"3": 13})
            self.assertEqual(arm["choice"]["payment"], 13)
        self.assertTrue(result["conventional_control_ties"])


class FundingAndInheritanceTests(unittest.TestCase):
    def test_joint_route_has_same_cost_but_unique_feasibility_at_six(self):
        result = c.staged_arrangement()
        routes = result["routes"]
        self.assertEqual([routes[name]["minimum_opening_cash"] for name in c.ROUTES], [9, 7, 9, 5])
        self.assertTrue(result["joint_construction_only_feasible_at_reference_capital"])
        self.assertEqual(routes["connector_and_staging"]["notional_cash_path"], [6, 4, 1, 7, 3, 9])
        self.assertEqual({row["complete_plan_surplus"] for row in routes.values()}, {3})

    def test_lifecycle_burden_changes_liquidity_and_profit_separately(self):
        for h in (0, Fraction(1, 2), 1, Fraction(3, 2), 3):
            result = c.cash_arithmetic(c.route_steps("connector_and_staging", lifecycle_burden=h), 6)
            self.assertEqual(result["minimum_opening_cash"], 5 + h)
            self.assertEqual(result["complete_plan_surplus"], 3 - h)
            self.assertEqual(result["feasible"], h <= 1)
        with self.assertRaises(ValueError):
            c.route_steps("connector_and_staging", lifecycle_burden=-1)

    def test_profit_does_not_erase_liquidity_or_protected_obligations(self):
        result = c.cash_arithmetic(c.route_steps("connector_and_staging"), 6, protected_reserve=2)
        self.assertFalse(result["feasible"])
        self.assertEqual(result["minimum_opening_cash"], 7)
        self.assertEqual(result["complete_plan_surplus"], 3)
        self.assertEqual(result["first_liquidity_shortfall"], "first production and checks")

    def test_future_receipt_cannot_pay_an_earlier_cost(self):
        late = c.cash_arithmetic([c.CashStep("production", -9), c.CashStep("settlement", 12)], 6)
        self.assertFalse(late["feasible"])
        self.assertEqual(late["notional_closing_cash"], 9)
        self.assertEqual(late["first_liquidity_shortfall"], "production")

    def test_nonentry_and_more_capital_can_change_the_best_arrangement(self):
        below = c.arrangement_enumeration(4)
        reference = c.arrangement_enumeration(6)
        larger = c.arrangement_enumeration(9)
        self.assertEqual(below["best_registered_feasible_arrangement"]["route"], "nonentry")
        self.assertEqual(reference["candidates"], 480)
        self.assertEqual(reference["financeable_complete_contracts"], 28)
        self.assertEqual(reference["positive_surplus_contracts"], 6)
        self.assertEqual(reference["best_registered_feasible_arrangement"]["surplus"], 3)
        self.assertEqual(reference["best_registered_feasible_arrangement"]["prices"], [6, 6])
        self.assertEqual(larger["best_registered_feasible_arrangement"]["route"], "ordinary_monolithic")
        self.assertEqual(larger["best_registered_feasible_arrangement"]["surplus"], 4)

    def test_milestone_must_use_collected_cash_not_joint_quote(self):
        result = c.staged_arrangement()["successor_cash_eligibility"]
        self.assertEqual(result["naive_projected_closing_cash"], 10)
        self.assertEqual(result["actual_closing_cash"], 9)
        self.assertEqual(result["cash_shortfall"], 1)
        self.assertFalse(result["actual_requirement_satisfied"])
        self.assertEqual(result["actual_first_episode_surplus"], 3)

    def test_reuse_does_not_erase_original_acquisition_or_beat_equal_content(self):
        result = c.successor_comparison()
        retained = result["arms"]["retained_connector"]
        rebuild = result["arms"]["rebuild_connector"]
        self.assertEqual(retained, result["arms"]["ordinary_equal_content_reuse"])
        self.assertEqual(retained["second_episode"]["complete_plan_surplus"], 5)
        self.assertEqual(rebuild["second_episode"]["complete_plan_surplus"], 3)
        self.assertEqual(retained["two_episode_declared_cost"], 16)
        self.assertEqual(rebuild["two_episode_declared_cost"], 18)
        self.assertEqual(retained["two_episode_surplus"], 8)
        self.assertEqual(rebuild["two_episode_surplus"], 6)
        self.assertEqual(result["first_episode_acquisition_cost_retained_in_history"], 2)
        self.assertFalse(result["inventor_improvement_established"])

    def test_adaptive_ordinary_continuation_beats_fixed_staged_ablation(self):
        result = c.successor_comparison()["stronger_adaptive_continuation"]
        self.assertTrue(result["second_episode"]["feasible"])
        self.assertEqual(result["second_episode"]["complete_plan_surplus"], 6)
        self.assertEqual(result["second_episode"]["notional_closing_cash"], 15)
        self.assertEqual(result["two_episode_surplus"], 9)
        self.assertTrue(result["ordinary_same_content_constructor_can_take_same_route"])


class ReproductionTests(unittest.TestCase):
    def test_evaluation_is_json_safe_and_expected_source_is_bound(self):
        result = c.evaluate()
        self.assertEqual(json.loads(json.dumps(result, sort_keys=True, allow_nan=False)), result)
        self.assertIn("8cd375784c24b879ae1eb4835c6af4fb925cbf4c", result["pinned_v3_witness"]["source"])
        self.assertFalse(any(result["claims"].values()))

    def test_output_refuses_overwrite_before_recomputation(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "result.json"
            destination.write_text("preserved evidence", encoding="utf-8")
            with patch.object(c, "evaluate", side_effect=AssertionError("must not recalculate")):
                with self.assertRaises(FileExistsError):
                    c.write_results(destination)
            self.assertEqual(destination.read_text(encoding="utf-8"), "preserved evidence")


if __name__ == "__main__":
    unittest.main()
