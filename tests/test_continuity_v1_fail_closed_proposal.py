"""Prospective v1 fail-closed repair: source events and authority stay intact.

These are synthetic, public-source, owner-review tests. They do not assert
live recovery, genuine consent, authentication, funds, or buyer benefit.
"""
import unittest

from continuity_omega.demo import case_for
from continuity_omega.engine import construct, digest, DrillRejected, outstanding, restored_anomalies
from continuity_omega.checker import audit


def partially_fulfilled_case():
    case = case_for()
    original = case["source_events"]
    case["source_events"] = [
        dict(original[0]),
        dict(original[1]),
        dict(original[3]),
        {"sequence": 4, "type": "FULFILL", "order_id": "LBL-100", "quantity": 100},
    ]
    for i, event in enumerate(case["source_events"], 1):
        event["sequence"] = i
    case["source_seal"] = digest(case["source_events"])
    case["restored_snapshot"] = [
        {"order_id": "LBL-100", "quantity": 1100},
        {"order_id": "LBL-200", "quantity": 800},
    ]
    return case


class RestorationV1FailClosedProposal(unittest.TestCase):
    def test_baseline_synthetic_drill_still_passes_without_real_world_claim(self):
        case = case_for()
        handoff, passport = construct(case)
        result = audit(case, handoff, passport)
        self.assertEqual(result["verdict"], "PASS_SYNTHETIC_ONLY")
        self.assertFalse(passport["evidence_boundary"]["real_customer_acceptance"])

    def test_cancelled_work_correctly_absent_from_outstanding_view(self):
        case = case_for()
        case["restored_snapshot"] = [
            {"order_id": "LBL-100", "quantity": 1000},
            {"order_id": "LBL-200", "quantity": 800},
        ]
        handoff, passport = construct(case)
        anomalies = passport["restoration_findings"]
        self.assertFalse(any(row["order_id"] == "LBL-300" for row in anomalies))
        self.assertEqual(audit(case, handoff, passport)["verdict"], "PASS_SYNTHETIC_ONLY")

    def test_fully_completed_order_absence_is_not_missing_obligation(self):
        case = case_for()
        case["source_events"].append({
            "sequence": 6, "type": "FULFILL", "order_id": "LBL-200", "quantity": 800,
        })
        case["source_seal"] = digest(case["source_events"])
        case["restored_snapshot"] = [
            {"order_id": "LBL-100", "quantity": 1000},
        ]
        # Force the original quoted supplier P as the only admissible choice
        # at the smaller 1100-unit volume; avoids an unrelated quote failure.
        case["suppliers"][1]["capacity_units"] = 1000
        handoff, passport = construct(case)
        self.assertEqual(handoff["required_units"], 1100)
        self.assertFalse(any(row["order_id"] in ("LBL-200", "LBL-300")
                             for row in passport["restoration_findings"]))
        self.assertEqual(audit(case, handoff, passport)["verdict"], "PASS_SYNTHETIC_ONLY")

    def test_partial_fulfillment_refused_by_v1_constructor(self):
        case = partially_fulfilled_case()
        with self.assertRaisesRegex(DrillRejected, "restoration fulfillment provenance"):
            construct(case)
        _, state = outstanding(case["source_events"], case["objective"]["product"])
        issues = restored_anomalies(state, case["restored_snapshot"])
        self.assertIn("FULFILLMENT_PROVENANCE_UNSUPPORTED_V1",
                      [r["issue"] for r in issues])

    def test_independent_replay_rejects_unwitnessed_partial_even_if_producer_bypassed(self):
        baseline = case_for()
        handoff, passport = construct(baseline)
        case = partially_fulfilled_case()
        # An attacker or older producer might send superficially consistent
        # gross-only recovery records; do not depend on its constructor.
        result = audit(case, handoff, passport)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("RESTORED_FULFILLMENT_PROVENANCE_UNPROVEN_V1",
                      result["failures"])

    def test_resurrected_completed_order_is_diagnosed(self):
        case = case_for()
        case["source_events"].append({
            "sequence": 6, "type": "FULFILL", "order_id": "LBL-200", "quantity": 800,
        })
        case["source_seal"] = digest(case["source_events"])
        _, state = outstanding(case["source_events"], case["objective"]["product"])
        restored = [
            {"order_id": "LBL-100", "quantity": 1100},
            {"order_id": "LBL-200", "quantity": 800},
        ]
        issues = restored_anomalies(state, restored)
        self.assertIn("COMPLETED_ORDER_REAPPEARED", [r["issue"] for r in issues])


if __name__ == "__main__":
    unittest.main()
