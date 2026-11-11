"""Frozen adversarial review130: do not omit source-linked failed/loss orders.

Synthetic micro-units and timestamps; no new customer, original account, sale, or
re-run of the original design041 development/confirmation fixture.
"""
import copy
import unittest

from connected_enterprise.design_flywheel import find_native_successor, _public


PLAN = "earned-plan-4"


def order(name, customer, *, price, cost, qualified, collected, source=None, outcome="SETTLED"):
    return {
        "id": name, "customer_id": customer, "offer": {"service_id": "kpi_variance"},
        "price": price, "complete_cost": cost, "outcome": outcome,
        "qualified_time": qualified, "acceptance_time": qualified + 1,
        "collection_time": collected, "acquisition_source_plan_id": source,
        "capacity_source_plan_id": None,
    }


def base_case():
    return {
        "orders": [
            order("prior", "customer-0", price=20, cost=10, qualified=10, collected=40),
            order("paid-successor", "customer-5", price=40, cost=12,
                  qualified=120, collected=160, source=PLAN),
        ],
        "investments": [{
            "kind": "acquisition", "id": "channel-4", "plan_id": PLAN,
            "purchased_time": 80, "activation_time": 96, "expiry_time": 300,
            "cost": 2, "funding_receipt": {"funding": "EARNED"},
        }],
    }


def refunded(name="failed", source=PLAN):
    return order(name, "customer-6", price=150, cost=90, qualified=140,
                 collected=None, source=source, outcome="REFUNDED")


class NativeAttribution130(unittest.TestCase):
    def test_original_successful_linked_orders_remain_positive(self):
        witness = find_native_successor(base_case())
        self.assertEqual(witness["net_after_native_investment_microUSD"], 26)
        self.assertTrue(witness["positive_incremental_collected_contribution"])
        self.assertEqual(witness["successor_paid_order"], "paid-successor")

    def test_linked_refunded_loss_must_reverse_positive_witness(self):
        case = base_case()
        case["orders"].append(refunded())
        witness = find_native_successor(case)
        self.assertIsNotNone(witness, "A collected successor exists, but must not be profitable")
        self.assertEqual(witness["net_after_native_investment_microUSD"], -64)
        self.assertFalse(witness["positive_incremental_collected_contribution"])
        self.assertIn("failed", witness["source_linked_unsettled_order_ids"])

    def test_linked_settled_negative_margin_cannot_be_omitted(self):
        case = base_case()
        case["orders"].append(order("loss", "customer-7", price=5, cost=75,
                                    qualified=135, collected=175, source=PLAN))
        witness = find_native_successor(case)
        self.assertIsNotNone(witness)
        self.assertEqual(witness["net_after_native_investment_microUSD"], -44)
        self.assertFalse(witness["positive_incremental_collected_contribution"])
        self.assertIn("loss", witness["source_linked_paid_order_ids"])

    def test_unlinked_refund_does_not_change_attributed_contribution(self):
        case = base_case()
        case["orders"].append(refunded(source="other-unrelated-investment"))
        witness = find_native_successor(case)
        self.assertEqual(witness["net_after_native_investment_microUSD"], 26)
        self.assertEqual(witness["source_linked_unsettled_order_ids"], [])

    def test_public_successor_gate_fails_with_attributed_losses(self):
        case = base_case()
        case["orders"].append(refunded())
        witness = find_native_successor(case)
        observed = {
            "obligations_covered": True, "profit_microUSD": 1200,
            "source_linked_successor": witness,
        }
        records = {"incumbent": {"observed": copy.deepcopy(observed)}}
        public = _public(
            {"incumbent": "incumbent", "designs": [{"id": "incumbent"}]},
            {"sha256": "synthetic-source"},
            records, {"selected": "incumbent"}, records,
            {"schema": "synthetic-independent-review"},
        )
        self.assertFalse(public["confirmed_positive_funded_successor_opportunity"])


if __name__ == "__main__":
    unittest.main()
