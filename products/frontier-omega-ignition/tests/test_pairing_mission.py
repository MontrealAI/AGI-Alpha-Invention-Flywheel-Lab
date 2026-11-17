import io
import json
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from ignition.controller import Controller
from ignition.pairing_specialist import PRESET
from ignition.store import Conflict, Store


class PairingMission(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.controller = Controller(Store(self.temp.name))
        self.mission = json.loads(PRESET.read_bytes())["mission"]

    def submit(self, key, parent=None, version=None):
        body = {"request_id": key, "mission": self.mission}
        if parent:
            body["version"] = version
        identifier, revision = self.controller.create(body, parent)
        return identifier, revision, self.controller.advance(identifier, revision)

    def test_complete_then_amend_preserves_distinct_scientific_verdict(self):
        cid, version, run = self.submit("positive-test")
        self.assertEqual(run["status"], "verified")
        self.assertTrue(run["pairing_result"]["qualifies"])
        self.assertEqual(run["pairing_result"]["audit"]["solved"],18)
        with ZipFile(io.BytesIO(self.controller.deliver(cid, version))) as bundle:
            self.assertEqual(json.loads(bundle.read("mission-decision.json")), run["pairing_result"])
            self.assertNotIn(self.mission["beneficiary"].encode(), bundle.read("mission-decision.json"))
        self.mission["resources"]["pairing_lab"].update(model="devstral", repository="django__django")
        _, next_version, amended = self.submit("django-test", cid, version)
        self.assertEqual(amended["status"], "verified")
        self.assertEqual(amended["pairing_result"]["verdict"], "audit_failed")
        self.assertEqual(amended["pairing_result"]["audit"]["solved"], 5)
        self.assertEqual(self.controller.deliver(cid, next_version, {}, trial=True), amended["pairing_result"])
        with self.assertRaises(Conflict):
            self.controller.deliver(cid, version)

    def test_recent_measurements_change_the_research_route(self):
        self.mission["resources"]["execution_strategy"] = "research"
        self.mission["time"] = {"as_of": "2026-10-13"}
        cid, version, old = self.submit("before-matrix")
        self.assertEqual(old["status"], "deferred")
        self.assertIsNone(old["artifact"])
        self.mission["time"] = {"as_of": "2026-11-17"}
        _, _, new = self.submit("after-matrix", cid, version)
        self.assertEqual(new["status"], "verified")
        self.assertEqual(new["opportunity_study"]["decision"]["candidate_id"], "paired-replay")
        self.assertEqual(new["opportunity_study"]["beneficiary"], self.mission["beneficiary"])

    def test_no_substitution_and_source_invalidation(self):
        self.mission["requirements"].append("Establish financial return on my private codebase")
        cid, _, state = self.submit("beyond-test")
        self.assertEqual(state["status"], "blocked")
        self.assertIsNone(state["artifact"])
        self.mission["requirements"].pop()
        cid, version, _ = self.submit("stale-source")
        with patch("ignition.pairing_specialist.identity", return_value="changed"):
            self.assertEqual(self.controller.view(cid)["status"], "stale")
            with self.assertRaises(Conflict):
                self.controller.deliver(cid, version)
