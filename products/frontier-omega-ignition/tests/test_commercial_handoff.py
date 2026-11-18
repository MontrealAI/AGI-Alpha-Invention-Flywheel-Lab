"""Synthetic evidence tests the importer and makes no commercial assertion."""
import copy
import hashlib
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from action_study import desk
from ignition import commercial_handoff as handoff
from ignition.controller import Controller
from ignition.evidence_specialist import template as mission_template
from ignition.store import Conflict, StateError, Store


class CommercialHandoffTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ctrl = Controller(Store(self.root / "private"))
        self.mission = mission_template(desk.example("ztf-persistence"))
        self.rid, self.rev = self.ctrl.create({"request_id": "initial-commercial", "mission": self.mission})

    def source(self, kind):
        path = self.root / kind
        path.write_text("Synthetic evidence for " + kind)
        return path

    def prepare(self, stage):
        event = handoff.template(self.ctrl.store, self.rid, self.rev, stage)
        event.update(counterparty="Synthetic counterparty", reviewer="Fixture reviewer")
        for field, value in list(event["details"].items()):
            if not value:
                event["details"][field] = "Fixture " + field
        files = {}
        for kind, source in event["evidence"].items():
            path = files[kind] = self.source(kind)
            source.update(source="Fixture " + kind, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        if stage == "offered":
            self.ctrl.advance(self.rid, self.rev)
            event["details"].update(amount="480.00", currency="CAD",
                                    artifact_sha256=hashlib.sha256(self.ctrl.deliver(self.rid, self.rev)).hexdigest())
        return event, files

    def apply(self, stage):
        event, files = self.prepare(stage)
        return handoff.record(self.ctrl, self.rid, self.rev, event, files)

    def test_full_sequence_remains_observed_and_unpaid_after_restart(self):
        for stage in ("identified", "validated", "offered", "accepted", "delivered", "settlement_reported"):
            result = self.apply(stage)
            self.assertIsNone(result["collected_revenue"])
        self.ctrl = Controller(Store(self.root / "private"))
        saved = handoff.status(self.ctrl.store, self.rid, self.rev)
        self.assertEqual(saved, result)
        self.assertEqual(saved["commercial_state"], "delivered")
        self.assertEqual(saved["settlement"], "pending_independent_reconciliation")
        self.assertEqual(len(saved["history"]), 6)
        with self.assertRaises(Conflict):
            handoff.template(self.ctrl.store, self.rid, self.rev, "paid")

    def test_concurrent_retries_and_wrong_upstream_sources(self):
        event, files = self.prepare("identified")
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: handoff.record(self.ctrl, self.rid, self.rev, event, files), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(results[0]["history"]), 1)
        with self.assertRaises(Conflict):
            handoff.template(self.ctrl.store, self.rid, self.rev, "delivered")
        event, files = self.prepare("validated")
        for key, wrong in (("counterparty", "Different"), ("previous_sha256", "8" * 64), ("version", True)):
            with self.subTest(key=key), self.assertRaises(Conflict):
                handoff.record(self.ctrl, self.rid, self.rev, dict(event, **{key: wrong}), files)
        files["funding_and_demand"].write_text("Other bytes")
        with self.assertRaises(StateError):
            handoff.record(self.ctrl, self.rid, self.rev, event, files)
        with self.assertRaises(StateError):
            handoff.record(self.ctrl, self.rid, self.rev, dict(event, stage="paid"), files)
        self.assertEqual(len(handoff.status(self.ctrl.store, self.rid, self.rev)["history"]), 1)

    def test_actual_export_recipient_and_terms_required(self):
        self.apply("identified")
        self.apply("validated")
        event, files = self.prepare("offered")
        for key, wrong in (("amount", "-1.00"), ("acceptance_criteria", "Weaker test"), ("artifact_sha256", "f" * 64)):
            modified = copy.deepcopy(event)
            modified["details"][key] = wrong
            with self.subTest(key=key), self.assertRaises(StateError):
                handoff.record(self.ctrl, self.rid, self.rev, modified, files)
        handoff.record(self.ctrl, self.rid, self.rev, event, files)
        event, files = self.prepare("accepted")
        event["details"]["recipient"] = "Unrelated recipient"
        with self.assertRaises(Conflict):
            handoff.record(self.ctrl, self.rid, self.rev, event, files)
        self.apply("accepted")
        self.apply("delivered")
        event, files = self.prepare("settlement_reported")
        for key, wrong in (("offer_sha256", "f" * 64), ("currency", "USD"), ("amount", "99.00")):
            modified = copy.deepcopy(event)
            modified["details"][key] = wrong
            with self.subTest(key=key), self.assertRaises(Conflict):
                handoff.record(self.ctrl, self.rid, self.rev, modified, files)

    def test_pause_and_stop_prevent_writes(self):
        event, files = self.prepare("identified")
        store = self.ctrl.store
        store.set_operation(self.rid, self.rev, "pause")
        with self.assertRaises(Conflict):
            handoff.record(self.ctrl, self.rid, self.rev, event, files)
        store.set_operation(self.rid, self.rev, "resume")
        with self.assertRaises(Conflict):
            handoff.record(self.ctrl, self.rid, self.rev, event, files)
        self.apply("identified")
        store.set_operation(self.rid, self.rev, "stop")
        event, files = self.prepare("validated")
        with self.assertRaises(Conflict):
            handoff.record(self.ctrl, self.rid, self.rev, event, files)
        self.assertEqual(handoff.status(store, self.rid, self.rev)["commercial_state"], "identified")

    def test_control_change_during_export_rolls_back_commercial_event(self):
        self.apply("identified")
        self.apply("validated")
        event, files = self.prepare("offered")
        original = self.ctrl.deliver
        store = self.ctrl.store

        def pause_after_export(*args):
            data = original(*args)
            store.set_operation(self.rid, self.rev, "pause")
            store.set_operation(self.rid, self.rev, "resume")
            return data

        with patch.object(self.ctrl, "deliver", side_effect=pause_after_export), self.assertRaises(Conflict):
            handoff.record(self.ctrl, self.rid, self.rev, event, files)
        self.assertEqual(handoff.status(store, self.rid, self.rev)["commercial_state"], "validated")

    def test_withhold_amend_and_keep_prior_history(self):
        event, files = self.prepare("identified")
        self.apply("withheld")
        with self.assertRaises(Conflict):
            handoff.record(self.ctrl, self.rid, self.rev, event, files)
        revision_two = self.ctrl.create({"request_id": "reopen-commercial", "version": 1, "mission": self.mission}, self.rid)[1]
        with self.assertRaises(Conflict):
            handoff.record(self.ctrl, self.rid, self.rev, event, files)
        self.assertEqual(handoff.status(self.ctrl.store, self.rid, 1)["commercial_state"], "withheld")
        self.assertEqual(handoff.status(self.ctrl.store, self.rid, revision_two)["commercial_state"], "unassessed")


if __name__ == "__main__":
    unittest.main()
