"""Safety, source-binding and policy-selection regressions for design search041."""
import copy
import unittest

from connected_enterprise.design_flywheel import (
    example_spec, validate, find_native_successor,
    choose_from_development, discover_applicable_designs, _covered,
)


def order(name, customer, service, price, cost, qualified, collected, source=None):
    return {"id": name, "customer_id": customer, "offer": {"service_id": service},
            "price": price, "complete_cost": cost, "outcome": "SETTLED",
            "qualified_time": qualified, "acceptance_time": qualified + 1,
            "collection_time": collected, "acquisition_source_plan_id": source,
            "capacity_source_plan_id": None}


def investment():
    return {"kind": "acquisition", "id": "channel-4", "plan_id": "earned-plan-4",
            "purchased_time": 80, "activation_time": 96, "expiry_time": 300,
            "cost": 2, "funding_receipt": {"funding": "EARNED"}}


def case():
    return {"orders": [
        order("original", "SIM-customer-000", "reconciliation", 20, 10, 10, 40),
        order("successor", "SIM-customer-005", "kpi_variance", 40, 12, 120, 160, "earned-plan-4")
    ], "investments": [investment()]}


class NativeDesignSearch041Tests(unittest.TestCase):
    def test_exposed_spec_is_valid_and_preserves_identical_external_market(self):
        spec = validate(example_spec())
        self.assertEqual(len(spec["designs"]), 3)
        self.assertEqual({d["arm"] for d in spec["designs"]},
                         {"baseline", "growth", "competitive_growth"})
        self.assertEqual(len({spec["config"]["arrival_bps"]}), 1)

    def test_disallows_author_control_of_buyer_demand_to_select_favorable_worlds(self):
        spec = example_spec()
        spec["designs"][1]["policies"]["arrival_bps"] = 10000
        with self.assertRaisesRegex(ValueError, "ONLY_AUTHORIZED_NATIVE_POLICY_ALTERNATIVES"):
            validate(spec)

    def test_requires_fresh_seed_and_baseline(self):
        spec = example_spec()
        spec["confirmation_seed"] = spec["development_seed"]
        with self.assertRaisesRegex(ValueError, "DISTINCT_NONNEGATIVE"):
            validate(spec)
        spec = example_spec()
        spec["incumbent"] = "earned_distribution"
        with self.assertRaisesRegex(ValueError, "STRONG_EXPLICIT"):
            validate(spec)

    def test_source_linked_earned_investment_enables_better_new_outcome(self):
        w = find_native_successor(case())
        self.assertEqual(w["native_plan_id"], "earned-plan-4")
        self.assertEqual(w["successor_paid_order"], "successor")
        self.assertEqual(w["binding_constraint_changed"], "customer_access")
        self.assertTrue(w["strictly_better_per_order_margin"])
        self.assertEqual(w["net_after_native_investment_microUSD"], 26)
        self.assertTrue(w["positive_incremental_collected_contribution"])

    def test_rejects_future_or_unfunded_or_unlinked_expansion(self):
        original = case()
        for mutation in (
            lambda v: v["investments"][0]["funding_receipt"].update(funding="SEED"),
            lambda v: v["orders"][1].update(acquisition_source_plan_id="other"),
            lambda v: v["orders"][1].update(qualified_time=70),
            lambda v: v["orders"][1].update(outcome="REFUNDED"),
            lambda v: v["orders"][0].update(collection_time=90),
        ):
            bad = copy.deepcopy(original)
            mutation(bad)
            self.assertIsNone(find_native_successor(bad))

    def test_investment_payback_counts_losing_settlements_and_refunds(self):
        for outcome in ("SETTLED", "REFUNDED", "QUALITY_REJECTED"):
            with self.subTest(outcome=outcome):
                bad = case()
                loss = order("loss", "SIM-customer-006", "reconciliation",
                             5, 55, 128, 170, "earned-plan-4")
                loss["outcome"] = outcome
                if outcome != "SETTLED":
                    loss["collection_time"] = None
                bad["orders"].append(loss)
                witness = find_native_successor(bad)
                self.assertIsNotNone(witness)
                self.assertFalse(witness["positive_incremental_collected_contribution"])
                self.assertLess(witness["net_after_native_investment_microUSD"], 0)
                self.assertEqual(witness["source_linked_delivery_cost_microUSD"], 67)
                self.assertEqual(witness["source_linked_total_order_contribution_microUSD"],
                                 28 + (5 if outcome == "SETTLED" else 0) - 55)

    def test_unrelated_losses_do_not_create_fictitious_investment_attribution(self):
        scenario = case()
        scenario["orders"].append(order("unrelated", "SIM-customer-006",
                                        "reconciliation", 5, 55, 128, 170, "other-plan"))
        witness = find_native_successor(scenario)
        self.assertTrue(witness["positive_incremental_collected_contribution"])
        self.assertEqual(witness["net_after_native_investment_microUSD"], 26)
        self.assertEqual(witness["source_linked_paid_order_ids"], ["successor"])

    def test_better_is_not_assumed_from_a_new_customer_alone(self):
        bad = case()
        bad["orders"][1]["complete_cost"] = 38
        w = find_native_successor(bad)
        self.assertIsNotNone(w)
        self.assertFalse(w["strictly_better_per_order_margin"])
        self.assertFalse(w["positive_incremental_collected_contribution"])

    def test_profit_is_not_available_liquidity_or_safe_reserves(self):
        s = {"complete": True, "summary": {"payables": 0, "investmentStopped": False,
            "cash": 90, "custodyReserve": 50, "tailReserve": 50, "workingCapital": 1,
            "profit": 200, "available": 0}}
        self.assertFalse(_covered(s))

    def test_development_only_selects_stronger_realized_profit_or_no_bid(self):
        spec = example_spec()
        def observed(profit, covered):
            return {"audit_accepted": True, "observed": {
                "profit_microUSD": profit, "obligations_covered": covered}}
        dev = {"incumbent": observed(20, True), "earned_distribution": observed(75, True),
               "competitive_distribution": observed(900, False)}
        self.assertEqual(choose_from_development(spec, dev)["selected"], "earned_distribution")
        dev["earned_distribution"] = observed(-3, True)
        self.assertEqual(choose_from_development(spec, dev)["selected"], "incumbent")
        for key in dev:
            dev[key] = observed(-1, True)
        self.assertIsNone(choose_from_development(spec, dev)["selected"])


    def test_machine_constructs_only_constraint_relevant_native_designs(self):
        spec = example_spec()
        def incumbent(*, unreached=0, rival=0, capacity=0, profit=100, earned=50):
            return {"audit_accepted": True, "observed": {
                "obligations_covered": True, "settled_orders": 2,
                "profit_microUSD": profit, "unrestricted_earned_microUSD": earned,
                "constraints": {
                    "unreached_buyers": unreached, "unserved_buyers": unreached,
                    "capacity_declines": capacity, "inventory_declines": 0,
                    "rival_choices": rival, "nonpayment_or_rejected": 0}}}
        access = discover_applicable_designs(spec, incumbent(unreached=4))
        self.assertIn("customer_access", access["diagnosed_constraints"])
        self.assertEqual(access["selected_development_ids"],
                         ["incumbent", "earned_distribution", "competitive_distribution"])
        pressure = discover_applicable_designs(spec, incumbent(rival=3))
        self.assertEqual(pressure["selected_development_ids"],
                         ["incumbent", "competitive_distribution"])
        capacity = discover_applicable_designs(spec, incumbent(capacity=3))
        self.assertIn("production_capacity", capacity["diagnosed_constraints"])
        self.assertEqual(capacity["selected_development_ids"],
                         ["incumbent", "earned_distribution", "competitive_distribution"])
        exhausted = discover_applicable_designs(spec, incumbent())
        self.assertEqual(exhausted["selected_development_ids"], ["incumbent"])
        losing = discover_applicable_designs(spec, incumbent(unreached=4, profit=-5, earned=0))
        self.assertEqual(losing["selected_development_ids"], ["incumbent"])
        with self.assertRaisesRegex(ValueError, "AUDITED_INCUMBENT"):
            discover_applicable_designs(spec, {"audit_accepted": False, "observed": {}})
        corrupted = incumbent(unreached=4)
        corrupted["observed"]["constraints"]["unreached_buyers"] = -10
        with self.assertRaisesRegex(ValueError, "COMPLETE_NONNEGATIVE"):
            discover_applicable_designs(spec, corrupted)

    def test_unrun_interventions_are_not_eligible_for_adoption(self):
        spec = example_spec()
        dev = {"incumbent": {"audit_accepted": True, "observed": {
            "obligations_covered": True, "profit_microUSD": 14}}}
        result = choose_from_development(spec, dev)
        self.assertEqual(result["selected"], "incumbent")
        self.assertEqual(result["observed_ranking"], [[14, "incumbent"]])

    def test_unapproved_audit_prevents_adaptive_selection(self):
        spec = example_spec()
        dev = {d["id"]: {"audit_accepted": True, "observed": {
            "profit_microUSD": 2, "obligations_covered": True}} for d in spec["designs"]}
        dev["earned_distribution"]["audit_accepted"] = False
        with self.assertRaisesRegex(ValueError, "INDEPENDENT_NATIVE_AUDIT"):
            choose_from_development(spec, dev)


if __name__ == "__main__":
    unittest.main()
