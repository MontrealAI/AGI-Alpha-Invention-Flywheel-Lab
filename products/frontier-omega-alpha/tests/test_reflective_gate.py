"""Regression and adversarial controls for the scoped source-fault challenge."""

import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "research" / "reflective_gate.py"
spec = importlib.util.spec_from_file_location("reflective_gate", MODULE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

HASH = hashlib.sha256(b"registered-protocol").hexdigest()


def registered_plan(hosts=("math.mit.edu",)):
    return {
        "schema": gate.PROTOCOL_SCHEMA,
        "stages": [{
            "id": f"cohort-{i}",
            "files": {
                "audit": {"file": f"audit-{i}.log", "url": f"https://{host}/audit-{i}.log"},
                "check": {"file": f"check-{i}.log", "url": f"https://{host}/check-{i}.log"},
            },
        } for i, host in enumerate(hosts)]
    }


def registered_report(plan, profile="f" * 64):
    return {
        "protocol_sha256": HASH,
        "technical_verdict": "receipt-agreement",
        "retained_profile_sha256": profile,
        "stages": [{"acceptance_matrix_matched": True, "cases": [{"name": "positive"}, {"name": "negative"}]} for _ in plan["stages"]],
        "economic": {"status": "unproven", "payment": None},
    }


class ReflectiveGateTests(unittest.TestCase):
    def setUp(self):
        self.plan = registered_plan(("math.mit.edu", "math.mit.edu"))
        self.report = registered_report(self.plan)

    def gate(self, plan=None, report=None, replay=True, budget=1):
        return gate.analyze(
            plan or self.plan, report or self.report, protocol_sha256=HASH,
            independent_receipt_replay=replay,
            max_faulty_source_groups=budget,
        )

    def test_technical_agreement_is_not_kernel_proof(self):
        result = self.gate()
        self.assertTrue(result["proven"]["receipt_agreement"])
        self.assertIn("underlying theorem correctness by independent Lean kernel execution", result["not_proven"])
        self.assertFalse(result["operational_authority_granted"])

    def test_one_publisher_is_not_multiple_fault_domains(self):
        finding = self.gate()["challenge_records"][0]
        self.assertEqual(finding["evidence"]["publisher_host_count"], 1)
        self.assertEqual(finding["evidence"]["necessary_groups_for_t_fault_correction"], 3)
        self.assertEqual(finding["evidence"]["correction_claim"], "necessary_group_count_failed")

    def test_more_hosts_is_not_sufficient_for_source_correction(self):
        plan = registered_plan(("one.example", "two.example", "three.example"))
        result = self.gate(plan=plan, report=registered_report(plan))
        self.assertEqual(result["challenge_records"][0]["evidence"]["correction_claim"],
                         "necessary_group_count_only_not_certified")
        self.assertIn("correction of an entire faulty upstream source group", result["not_proven"])

    def test_failed_replay_cannot_be_promoted(self):
        result = self.gate(replay=False)
        self.assertEqual(result["technical_status"], "unverified_or_failed")
        self.assertFalse(result["proven"]["parser_reloaded"])
        self.assertFalse(result["proven"]["receipt_agreement"])

    def test_digest_mismatch_cannot_be_promoted(self):
        report = registered_report(self.plan)
        report["protocol_sha256"] = "0" * 64
        self.assertFalse(self.gate(report=report)["proven"]["receipt_agreement"])

    def test_missing_stage_cannot_be_promoted(self):
        report = registered_report(self.plan)
        report["stages"].pop()
        self.assertFalse(self.gate(report=report)["proven"]["receipt_agreement"])

    def test_false_case_matrix_cannot_be_promoted(self):
        report = registered_report(self.plan)
        report["stages"][0]["acceptance_matrix_matched"] = False
        self.assertFalse(self.gate(report=report)["proven"]["receipt_agreement"])

    def test_retained_profile_does_not_imply_causal_gain(self):
        result = self.gate()
        self.assertTrue(result["proven"]["parser_reloaded"])
        self.assertIn("causal successor invention improvement", result["not_proven"])
        self.assertIn("no-reuse", result["challenge_records"][1]["discriminating_test"])

    def test_spurious_payment_field_never_establishes_revenue(self):
        report = registered_report(self.plan)
        report["economic"] = {"status": "realized", "payment": 1e12}
        result = self.gate(report=report)
        self.assertIn("real buyer acceptance or payment", result["not_proven"])
        self.assertIn("HOLD", result["decision"])

    def test_no_url_query_or_fragment_allowed_in_fault_domains(self):
        plan = registered_plan(("one.example",))
        plan["stages"][0]["files"]["audit"]["url"] += "?secret=yes"
        with self.assertRaises(ValueError):
            self.gate(plan=plan, report=registered_report(plan))

    def test_fault_budget_zero_is_only_necessary_group_test(self):
        result = self.gate(budget=0)
        self.assertEqual(result["challenge_records"][0]["evidence"]["necessary_groups_for_t_fault_correction"], 1)
        self.assertNotIn("certified", result["challenge_records"][0]["evidence"]["correction_claim"].replace("not_certified", ""))

    def test_invalid_protocol_rejected(self):
        plan = registered_plan()
        plan["schema"] = "general-science-v99"
        with self.assertRaises(ValueError):
            self.gate(plan=plan, report=registered_report(plan))

    def test_no_automatic_execution_authority(self):
        result = self.gate()
        self.assertFalse(result["operational_authority_granted"])
        self.assertEqual(len(result["challenge_records"]), 3)
        self.assertTrue(all(option["authority"] for option in result["response_options"]))


if __name__ == "__main__":
    unittest.main()
