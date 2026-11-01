"""Safety, source-binding and policy-selection regressions for design search041."""
import copy
import unittest

from connected_enterprise.design_flywheel import (
    example_spec, validate, find_native_successor,
    choose_from_development, discover_applicable_designs, _covered, _public,
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



    def test_source_linked_loss_must_reduce_scoped_investment_surplus(self):
        v = case()
        v["orders"] = [
            v["orders"][0],
            order("gain", "buyer1", "kpi_variance", 28, 0, 120, 160, "earned-plan-4"),
            order("loss", "buyer2", "evidence_matrix", 1, 26, 124, 166, "earned-plan-4"),
        ]
        v["investments"][0]["cost"] = 4
        w = find_native_successor(v)
        self.assertEqual(w["net_after_native_investment_microUSD"], -1)
        self.assertFalse(w["positive_incremental_collected_contribution"])

    def test_all_required_capacity_and_acquisition_invoices_are_charged(self):
        v = case()
        v["orders"][1]["price"] = 40
        v["orders"][1]["complete_cost"] = 18
        v["orders"][1]["capacity_source_plan_id"] = "earned-capacity"
        v["investments"][0]["cost"] = 15
        v["investments"].append({
            "kind": "capacity", "id": "slot-1", "plan_id": "earned-capacity",
            "purchased_time": 80, "activation_time": 96, "expiry_time": 300,
            "cost": 15, "funding_receipt": {"funding": "EARNED"},
        })
        w = find_native_successor(v)
        self.assertEqual(w["all_required_invoices_microUSD"], 30)
        self.assertEqual(w["net_after_native_investment_microUSD"], -8)
        self.assertFalse(w["positive_incremental_collected_contribution"])

    def test_refunded_work_costs_count_without_credited_collection(self):
        v = case()
        refunded = order("refund", "buyer3", "evidence_matrix", 100, 35,
                         130, 190, "earned-plan-4")
        refunded["outcome"] = "REFUNDED"
        refunded["collection_time"] = None
        v["orders"].append(refunded)
        w = find_native_successor(v)
        self.assertEqual(w["net_after_native_investment_microUSD"], -9)
        self.assertEqual(w["source_linked_uncollected_order_ids"], ["refund"])

    def test_second_enabler_must_have_source_bound_earned_funding(self):
        v = case()
        v["orders"][1]["capacity_source_plan_id"] = "other-plan"
        self.assertIsNone(find_native_successor(v))
        v["investments"].append({
            "kind": "capacity", "id": "slot-2", "plan_id": "other-plan",
            "purchased_time": 80, "activation_time": 96, "expiry_time": 300,
            "cost": 2, "funding_receipt": {"funding": "SEED"},
        })
        self.assertIsNone(find_native_successor(v))

    def test_shared_enabler_refund_cannot_hide_outside_anchor_order(self):
        v = case()
        v["orders"][1]["price"] = 70
        v["orders"][1]["complete_cost"] = 10
        v["orders"][1]["capacity_source_plan_id"] = "shared-capacity"
        v["investments"][0]["cost"] = 5
        v["investments"].append({
            "kind": "capacity", "id": "slot-shared", "plan_id": "shared-capacity",
            "purchased_time": 80, "activation_time": 96, "expiry_time": 300,
            "cost": 5, "funding_receipt": {"funding": "EARNED"},
        })
        loss = order("capacity-only-refund", "buyer4", "evidence_matrix", 100, 80,
                     135, 195)
        loss.update(outcome="REFUNDED", collection_time=None,
                    capacity_source_plan_id="shared-capacity")
        v["orders"].append(loss)
        w = find_native_successor(v)
        self.assertEqual(w["all_required_native_plan_ids"],
                         ["earned-plan-4", "shared-capacity"])
        self.assertEqual(w["source_linked_uncollected_order_ids"],
                         ["capacity-only-refund"])
        self.assertEqual(w["net_after_native_investment_microUSD"], -30)
        self.assertFalse(w["positive_incremental_collected_contribution"])
        self.assertEqual(w["source_link_scope"],
                         "COMPLETE_CONNECTED_NATIVE_ENABLER_COMPONENT")

    def test_transitive_joint_enabler_loss_cannot_be_left_out(self):
        v = case()
        v["orders"][1].update(price=120, complete_cost=10,
                              capacity_source_plan_id="shared-capacity")
        v["investments"][0]["cost"] = 5
        for name, plan in (("slot-1", "shared-capacity"), ("slot-2", "third-plan")):
            v["investments"].append({
                "kind": "capacity", "id": name, "plan_id": plan,
                "purchased_time": 80, "activation_time": 96, "expiry_time": 300,
                "cost": 5, "funding_receipt": {"funding": "EARNED"},
            })
        bridge = order("bridge", "buyer6", "reconciliation", 5, 3, 130, 170)
        bridge.update(capacity_source_plan_id="shared-capacity",
                      capacity_source_plan_ids=["third-plan"])
        loss = order("third-only-refund", "buyer7", "evidence_matrix", 100, 150, 135, 190)
        loss.update(outcome="REFUNDED", collection_time=None,
                    capacity_source_plan_id="third-plan")
        v["orders"].extend([bridge, loss])
        w = find_native_successor(v)
        self.assertEqual(w["all_required_native_plan_ids"],
                         ["earned-plan-4", "shared-capacity", "third-plan"])
        self.assertEqual(w["net_after_native_investment_microUSD"], -53)
        self.assertFalse(w["positive_incremental_collected_contribution"])

    def test_unrelated_refund_not_charged_to_unconnected_enabler(self):
        v = case()
        unrelated = order("unrelated", "buyer9", "evidence_matrix", 100, 999, 130, 190)
        unrelated.update(outcome="REFUNDED", collection_time=None)
        v["orders"].append(unrelated)
        w = find_native_successor(v)
        self.assertEqual(w["net_after_native_investment_microUSD"], 26)
        self.assertNotIn("unrelated", w["source_linked_uncollected_order_ids"])

    def test_duplicate_source_plan_inventory_rejected(self):
        v = case()
        v["investments"].append(dict(v["investments"][0]))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_NATIVE_PLAN_INVENTORY"):
            find_native_successor(v)


    def test_heldout_loss_vetoes_development_winner_and_retained_method(self):
        spec = example_spec()
        def row(profit, funded=True, covered=True):
            return {"observed": {"profit_microUSD": profit,
                "obligations_covered": covered,
                "source_linked_successor": (
                    {"positive_incremental_collected_contribution": True} if funded else None)}}
        development = {"incumbent": row(10), "earned_distribution": row(20)}
        selection = {"selected": "earned_distribution"}
        def report(inc, contender):
            return _public(spec, {"sha256": "frozen-source"}, development, selection,
                {"incumbent": inc, "earned_distribution": contender}, {})
        losing = report(row(16), row(8))
        self.assertEqual(losing["selection"]["selected"], "earned_distribution")
        self.assertEqual(losing["heldout_recommendation"]["recommended_policy"], "incumbent")
        self.assertFalse(losing["heldout_recommendation"]["challenger_accepted"])
        self.assertTrue(losing["confirmed_positive_funded_successor_opportunity"])
        self.assertFalse(losing["comparative_advantage_on_one_fresh_seed"])
        self.assertIsNone(losing["retained_mechanism"])
        tied = report(row(16), row(16))
        self.assertFalse(tied["heldout_recommendation"]["challenger_accepted"])
        self.assertEqual(tied["heldout_recommendation"]["recommended_policy"], "incumbent")
        winning = report(row(8), row(16))
        self.assertTrue(winning["heldout_recommendation"]["challenger_accepted"])
        self.assertEqual(winning["heldout_recommendation"]["recommended_policy"], "earned_distribution")
        self.assertTrue(winning["confirmed_positive_funded_successor_opportunity"])
        self.assertIsNotNone(winning["retained_mechanism"])
        self.assertEqual(winning["heldout_recommendation"]["native_financial_action_authority"], [])
        unviable = report(row(-8, covered=False), row(-2))
        self.assertIsNone(unviable["heldout_recommendation"]["recommended_policy"])
        self.assertFalse(unviable["heldout_recommendation"]["challenger_accepted"])

    def test_incumbent_successor_is_not_rebranded_as_new_method(self):
        spec = example_spec()
        incumbent = {"observed": {"profit_microUSD": 11, "obligations_covered": True,
            "source_linked_successor": {"positive_incremental_collected_contribution": True}}}
        report = _public(spec, {"sha256": "frozen-source"},
            {"incumbent": incumbent}, {"selected": "incumbent"},
            {"incumbent": incumbent}, {})
        self.assertEqual(report["heldout_recommendation"]["recommended_policy"], "incumbent")
        self.assertIsNone(report["heldout_recommendation"]["development_candidate"])
        self.assertTrue(report["confirmed_positive_funded_successor_opportunity"])
        self.assertFalse(report["comparative_advantage_on_one_fresh_seed"])
        self.assertIsNone(report["retained_mechanism"])
        no_bid = _public(spec, {"sha256": "frozen-source"},
            {"incumbent": incumbent}, {"selected": None}, {}, {})
        self.assertIsNone(no_bid["heldout_recommendation"]["recommended_policy"])


if __name__ == "__main__":
    unittest.main()
