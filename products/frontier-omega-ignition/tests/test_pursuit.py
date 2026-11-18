"""Exercise pursuit recovery, operator decisions and source-bound negative evidence reuse."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ignition.controller import Controller
from ignition import commercial_handoff, pursuit
from ignition.store import Conflict, PRODUCT, Store


class PursuitRecovery(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.ctrl = Controller(Store(self.root / "private"))
        plan = json.loads((PRODUCT / "examples/public-research.shortlist").read_text())
        plan["candidates"] = [dict(plan["candidates"][0], mission_file="example.json")]
        self.file = self.root / "test.shortlist"
        self.file.write_text(json.dumps(plan))
        (self.root / "example.json").write_bytes((PRODUCT / "examples/evidence_action.json").read_bytes())

    def run_pursuit(self):
        return pursuit.pursue(self.ctrl, self.file, "control-study")

    def test_freeze_restart_and_replacement(self):
        first = self.run_pursuit()
        self.ctrl = Controller(Store(self.root / "private"))
        self.assertEqual(first, self.run_pursuit())
        a, = first["attempts"]
        self.assertEqual(a["commercial_state"], "identified")
        self.assertIsNone(first["collected_revenue"])
        recipient = self.ctrl.store.root / "recipients" / a["recipient"]["file"]
        receipt = commercial_handoff.status(self.ctrl.store, a["mission_id"], a["version"])
        self.assertEqual(len(receipt["history"]), 1)
        self.assertIn("research note", receipt["history"][0]["event"]["evidence"]["public_need"]["source"])
        recipient.write_bytes(b"changed after export")
        with self.assertRaises(Conflict):
            self.run_pursuit()
        plan = json.loads(self.file.read_text())
        plan["selection_basis"] = "A changed decision"
        self.file.write_text(json.dumps(plan))
        with self.assertRaises(Conflict):
            self.run_pursuit()

    def test_operator_withhold_during_execution_wins(self):
        advance = self.ctrl.advance

        def concurrent_observation(rid, rev):
            saved = advance(rid, rev)
            card = pursuit.read_shortlist(self.file)["candidates"][0]
            observed = commercial_handoff.status(self.ctrl.store, rid, rev)
            pursuit._observe(self.ctrl, rid, rev, card, "withheld", {"purpose": "authored test"},
                             {"reason": "Reviewer declined", "reopen_condition": "Wait for new evidence"}, observed)
            return dict(saved, field_decision={"disposition": "ready_for_beneficiary_review",
                                               "reason": "authored control", "next_action": "check report"})

        with patch.object(self.ctrl, "advance", side_effect=concurrent_observation):
            report = self.run_pursuit()
        self.assertEqual(report["result"], "shortlist_exhausted")
        self.assertEqual(report["attempts"][0]["commercial_state"], "withheld")
        self.assertEqual(report["attempts"][0]["next_action"], "Wait for new evidence")


    def test_scoped_negative_successor_and_revocation(self):
        (self.root / "example.json").write_bytes((PRODUCT / "examples/quantum.json").read_bytes())
        prior = self.run_pursuit()["attempts"][0]
        self.assertEqual(prior["technical_status"], "verified")
        self.assertEqual(prior["commercial_state"], "withheld")
        with patch.object(self.ctrl, "create", side_effect=AssertionError("unexpected new experiment")):
            successor = pursuit.pursue(self.ctrl, self.file, "successor", reuse_from="control-study")
            a, = successor["attempts"]
            self.assertFalse(a["new_measurement"])
            self.assertEqual(a["reused_from"]["mission_id"], prior["mission_id"])
            self.assertEqual(a["reused_from"]["recipient_sha256"], prior["recipient"]["sha256"])
            self.assertEqual(pursuit.pursue(self.ctrl, self.file, "successor", reuse_from="control-study"), successor)
        with self.assertRaises(Conflict):
            pursuit.pursue(self.ctrl, self.file, "successor")
        self.ctrl.set_operation(prior["mission_id"], prior["version"], "pause")
        with patch.object(self.ctrl, "create", side_effect=RuntimeError("fresh execution selected")):
            with self.assertRaisesRegex(RuntimeError, "fresh execution selected"):
                pursuit.pursue(self.ctrl, self.file, "successor", reuse_from="control-study")
        self.ctrl.set_operation(prior["mission_id"], prior["version"], "resume")
        with patch.object(self.ctrl, "create", side_effect=RuntimeError("fresh selection persisted")):
            with self.assertRaisesRegex(RuntimeError, "fresh selection persisted"):
                pursuit.pursue(self.ctrl, self.file, "successor", reuse_from="control-study")

    def test_reuse_source_date_and_grant_are_binding(self):
        quantum = json.loads((PRODUCT / "examples/quantum.json").read_text())
        (self.root / "example.json").write_text(json.dumps(quantum))
        self.run_pursuit()
        original = json.loads(self.file.read_text())
        amended = json.loads(self.file.read_text())
        amended["candidates"][0]["observed_on"] = "2026-11-19"
        self.file.write_text(json.dumps(amended))
        with patch.object(self.ctrl, "create", side_effect=RuntimeError("new source needs a fresh experiment")):
            with self.assertRaisesRegex(RuntimeError, "new source needs a fresh experiment"):
                pursuit.pursue(self.ctrl, self.file, "after-source-change", reuse_from="control-study")
        self.file.write_text(json.dumps(original))
        quantum["mission"]["authority"].pop("allow_program_reuse")
        (self.root / "example.json").write_text(json.dumps(quantum))
        with patch.object(self.ctrl, "create", side_effect=RuntimeError("no reuse permission")):
            with self.assertRaisesRegex(RuntimeError, "no reuse permission"):
                pursuit.pursue(self.ctrl, self.file, "no-grant", reuse_from="control-study")

    def test_prior_operator_withhold_cannot_substitute_for_the_experiment(self):
        (self.root / "example.json").write_bytes((PRODUCT / "examples/quantum.json").read_bytes())
        advance = self.ctrl.advance
        def reviewed(rid, rev):
            state = advance(rid, rev)
            card = pursuit.read_shortlist(self.file)["candidates"][0]
            observed = commercial_handoff.status(self.ctrl.store, rid, rev)
            pursuit._observe(self.ctrl, rid, rev, card, "withheld", {"review": "operator decision"},
                             {"reason": "Human review", "reopen_condition": "Await another review"}, observed)
            return state
        with patch.object(self.ctrl, "advance", side_effect=reviewed):
            self.run_pursuit()
        with patch.object(self.ctrl, "create", side_effect=RuntimeError("fresh experiment selected")):
            with self.assertRaisesRegex(RuntimeError, "fresh experiment selected"):
                pursuit.pursue(self.ctrl, self.file, "independent-successor", reuse_from="control-study")
