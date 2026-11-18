import copy
import unittest
from unittest.mock import patch

from action_study import desk


class DecisionContract(unittest.TestCase):
    def test_ztf_deadline_early_window_and_source_withdrawal(self):
        task = desk.example("ztf-persistence")
        receipt = desk.case(task)
        row, = receipt["attempts"][-1]["evidence"]
        self.assertEqual((row["record_id"], row["rfid"]), ("3587249065815015015", 505120158))
        self.assertEqual(row["delta_from_baseline_mag"], -1.069727)
        self.assertEqual(desk.verify(receipt, task), receipt["sha256"])
        short = {**task, "sources": ["fink"]}
        self.assertEqual(desk.case(short)["decision"]["state"], "incomplete")
        with self.assertRaises(ValueError):
            desk.verify(receipt, short)
        task["scope"] = dict(task["scope"], clock="received")
        self.assertEqual(desk.case(task)["decision"]["state"], "unavailable")
        task["scope"]["as_of"] = "2026-11-18T06:00:00Z"
        self.assertEqual(desk.case(task)["decision"]["finding"], "persisted")

    def test_coverage_retraction_and_receipt_clock(self):
        task = desk.example("gw-status")
        receipt = desk.case(task)
        self.assertEqual(receipt["decision"]["action"], "withdraw_shadow_review")
        task["scope"]["as_of"] = "2024-04-20T05:06:22Z"
        r = desk.case(task)
        self.assertEqual(r["decision"]["action"], "retain_shadow_review")
        absence = r["attempts"][-1]["retraction_search"]
        self.assertEqual((absence["state"], absence["coverage"]["inspected"]), (desk.NEGATIVE, 3))
        task["scope"]["clock"] = "received"
        self.assertEqual(desk.case(task)["decision"]["state"], "incomplete")
        task["sources"] = []
        self.assertEqual(desk.case(task)["decision"]["state"], "unavailable")

    def test_new_mission_no_decorative_citations_and_contradictions(self):
        task = desk.example("engineering-qualification")
        receipt = desk.case(task)
        self.assertEqual(receipt["decision"]["action"], "qualify_B_next")
        changed = copy.deepcopy(receipt)
        changed["decision"]["action"] = "approve_deployment"
        changed["sha256"] = desk.digest({k:v for k,v in changed.items() if k != "sha256"})
        with self.assertRaises(ValueError):
            desk.verify(changed, task)
        rules = desk.PROFILES[task["profile"]]
        pos = dict(receipt["attempts"][-1], finding="A", reason="synthetic conflicting qualified reports")
        with patch.object(desk.adapter(task["profile"]), "inspect_source", side_effect=[pos, dict(pos, finding="B")]):
            task["crosscheck"] = True
            self.assertEqual(desk.case(task)["decision"]["state"], "contradictory")
        with self.assertRaises(ValueError):
            desk.checked_attempt(dict(pos, evidence=[]), rules)
        with self.assertRaises(ValueError):
            desk.checked_attempt(dict(pos, state=desk.NEGATIVE, finding=None), rules)

    def test_closed_sources_and_scopes(self):
        task = desk.example("gw-status")
        for bad in (dict(task, sources=["https://example.org"]), dict(task, evidence=[]),
                    dict(task, scope=dict(task["scope"], as_of="yesterday")), dict(task, crosscheck=1)):
            with self.assertRaises(ValueError):
                desk.case(bad)
