# SPDX-License-Identifier: Apache-2.0
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError
from bridge.proof_to_market import assess, CATEGORIES


def fixture():
    return {"desired_result": "Shared HARNESS verification capability",
            "acceptance": "Independent acceptance cases pass", "currency": "CAD",
            "missing_capabilities": ["dependency-evidence-reuse"],
            "participants": [{"id": "operator", "role": "prospective customer", "benefit_minor": 20000,
                              "contribution_minor": 10000, "outside_option_minor": 5000}],
            "costs": [{"id": c, "category": c, "amount_minor": 10000 if c == "construction" else 0,
                       "period": 0, "basis": "Explicit synthetic assumption"} for c in sorted(CATEGORIES)],
            "funding": [{"id": "owner", "kind": "owner", "amount_minor": 10000, "period": 0,
                         "terms": "Hypothetical, not an executed agreement"}],
            "milestones": [{"id": "proof", "deliverable": "Verifier", "acceptance": "Adversarial checks pass",
                            "status": "proposed", "evidence": []}],
            "alternatives": [{"id": "ordinary", "route": "purchase", "description": "Existing exact cache",
                              "feasible": True, "total_cost_minor": 9000}], "commercial_records": []}


class ProofToMarketTests(unittest.TestCase):
    def test_feasible_assumptions_cannot_become_actual_market_or_cash(self):
        result = assess(fixture())
        self.assertEqual(result["economic_feasibility"], "CONDITIONAL_ON_DECLARED_ASSUMPTIONS")
        self.assertEqual(result["commercial_validation"], "NOT_ESTABLISHED")
        self.assertIsNone(result["verified_earned_revenue_minor"])
        self.assertIsNone(result["available_reinvestable_surplus_minor"])
        self.assertEqual(result["prospective_funding_minor"], 10000)
        self.assertEqual(result["known_cost_minor"], 10000)
        self.assertEqual(result["alternatives"][0]["total_cost_minor"], 9000)

    def test_member_contribution_is_not_counted_twice_as_funding(self):
        plan = fixture()
        plan["funding"] = []
        result = assess(plan)
        self.assertEqual(result["prospective_funding_minor"], 0)
        self.assertEqual(result["peak_funding_gap_minor"], 10000)

    def test_late_funding_and_unmeasured_costs_remain_unresolved(self):
        plan = fixture()
        plan["funding"][0]["period"] = 1
        plan["costs"][0]["amount_minor"] = None
        result = assess(plan)
        self.assertEqual(result["peak_funding_gap_minor"], 10000)
        self.assertTrue(result["unknown_cost_ids"])
        self.assertEqual(result["economic_feasibility"], "UNRESOLVED")

    def test_outside_option_can_reject_shared_development(self):
        plan = fixture()
        plan["participants"][0]["outside_option_minor"] = 30000
        result = assess(plan)
        self.assertFalse(result["participants"][0]["individually_rational_under_assumptions"])
        self.assertEqual(result["economic_feasibility"], "UNRESOLVED")

    def test_pipeline_stages_are_separate_and_recorded_claims_remain_unverified(self):
        plan = fixture()
        plan["commercial_records"] = [{"id": stage, "stage": stage, "amount_minor": 10000,
                                       "evidence_reference": "operator-supplied-reference"}
                                      for stage in ("forecast", "interest", "commitment", "invoiced", "collected", "earned")]
        result = assess(plan)
        self.assertEqual(result["operator_recorded_pipeline_minor"]["earned"], 10000)
        self.assertIsNone(result["verified_earned_revenue_minor"])
        self.assertEqual(result["commercial_validation"], "NOT_ESTABLISHED")

    def test_missing_evidence_and_bad_money_are_rejected(self):
        plan = fixture()
        plan["milestones"][0]["status"] = "accepted"
        with self.assertRaises(BridgeError):
            assess(plan)
        for value in (True, -1, 2.5, "100"):
            plan = fixture()
            plan["costs"][0]["amount_minor"] = value
            with self.subTest(value=value), self.assertRaises(BridgeError):
                assess(plan)
        plan = fixture()
        plan["execute_payment"] = True
        with self.assertRaises(BridgeError):
            assess(plan)


if __name__ == "__main__":
    unittest.main()
