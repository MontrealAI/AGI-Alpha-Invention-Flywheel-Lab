"""Preregistered source-plan time-order negatives for native design041.

See campaign/native-design-provenance164/PROTOCOL.md at 96b1fa29.
Synthetic witness inputs only: no accounts, no signing material and no real commerce.
"""
import copy
import unittest

from connected_enterprise.design_flywheel import find_native_successor


def _order(ident, customer, service, *, q, p, c, price, cost, acquisition=None, capacity=None, extra=None, outcome="SETTLED"):
    return {
        "id": ident, "customer_id": customer, "offer": {"service_id": service},
        "price": price, "complete_cost": cost, "outcome": outcome,
        "qualified_time": q, "production_time": p, "acceptance_time": p + 1,
        "collection_time": c if outcome == "SETTLED" else None,
        "acquisition_source_plan_id": acquisition,
        "capacity_source_plan_id": capacity,
        "capacity_source_plan_ids": [] if extra is None else extra,
    }


def _plan(ident, kind, activation, expiry):
    return {
        "kind": kind, "id": "native-" + ident, "plan_id": ident,
        "purchased_time": 80, "activation_time": activation,
        "expiry_time": expiry, "cost": 3,
        "funding_receipt": {"funding": "EARNED"},
    }


def valid_component():
    return {
        "orders": [
            _order("first", "buyer-1", "reconciliation", q=10, p=11, c=40, price=20, cost=10),
            _order("later", "buyer-2", "evidence_matrix", q=120, p=121, c=160,
                   price=60, cost=10, acquisition="earned-acq", capacity="earned-cap"),
        ],
        "investments": [
            _plan("earned-acq", "acquisition", 96, 300),
            _plan("earned-cap", "capacity", 100, 300),
        ],
    }


class NativeDesignProvenanceTime164(unittest.TestCase):
    def assert_no_positive(self, result):
        try:
            witness = find_native_successor(result)
        except ValueError:
            return
        self.assertFalse(witness and witness["positive_incremental_collected_contribution"],
                         "PREMATURE_OR_EXPIRED_ASSET_ACCEPTED_AS_EARNED_SUCCESSOR")

    def test_valid_native_plan_activation_and_order_timing_survive(self):
        w = find_native_successor(valid_component())
        self.assertIsNotNone(w)
        self.assertTrue(w["positive_incremental_collected_contribution"])
        self.assertEqual(w["all_required_native_plan_ids"], ["earned-acq", "earned-cap"])
        self.assertEqual(w["net_after_native_investment_microUSD"], 44)

    def test_future_second_enabler_cannot_claim_successor(self):
        v = valid_component()
        v["investments"][1]["activation_time"] = 140
        self.assert_no_positive(v)

    def test_expired_second_enabler_cannot_claim_successor(self):
        v = valid_component()
        v["investments"][1]["expiry_time"] = 121
        self.assert_no_positive(v)

    def test_future_supplemental_capacity_link_cannot_claim_successor(self):
        v = valid_component()
        v["orders"][1]["capacity_source_plan_id"] = None
        v["orders"][1]["capacity_source_plan_ids"] = ["earned-cap"]
        v["investments"][1]["activation_time"] = 140
        self.assert_no_positive(v)

    def test_refunded_order_cannot_preuse_later_capacity(self):
        v = valid_component()
        v["orders"].append(
            _order("failed-before-activation", "buyer-3", "kpi_variance",
                   q=90, p=91, c=None, price=20, cost=1,
                   capacity="earned-cap", outcome="REFUNDED")
        )
        self.assert_no_positive(v)


if __name__ == "__main__":
    unittest.main()
