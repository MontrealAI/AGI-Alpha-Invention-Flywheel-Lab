import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from ignition.controller import Controller
from ignition.endpoint_specialist import PRESET
from ignition.store import Conflict, StateError, Store


class EndpointMission(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.controller = Controller(Store(self.root / "state"))
        self.mission = json.loads(PRESET.read_bytes())["mission"]
        self.mission["beneficiary"] = "Unpublished private operator details"

    def submit(self, amend=None):
        body = {"mission": self.mission, "request_id": "initial-endpoint"}
        if amend:
            body.update(version=amend[1], request_id="amend-endpoint")
        rid, version = self.controller.create(body, amend[0] if amend else None)
        return rid, version, self.controller.advance(rid, version)

    def test_export_and_amend(self):
        self.mission["resources"]["execution_strategy"] = "direct"
        rid, version, state = self.submit()
        self.assertEqual(state["status"], "verified", state["error"])
        self.assertEqual(state["endpoint_result"]["decision"], "supported")
        data = self.controller.deliver(rid, version)
        self.assertEqual(self.controller.deliver(rid, version), data)
        with ZipFile(io.BytesIO(data)) as archive:
            for name in archive.namelist():
                self.assertNotIn(self.mission["beneficiary"].encode(), archive.read(name))
            archive.extractall(self.root / "kit")
        script = self.root / "kit/endpoint_lab/replay_delivery.py"
        replay = subprocess.run([sys.executable, "-IB", str(script)], capture_output=True, check=True)
        self.assertTrue(json.loads(replay.stdout)["verification"]["checked"])
        paper = self.root / "kit/decision.json"
        decision = json.loads(paper.read_bytes())
        decision["deployment_authorized"] = True
        paper.write_text(json.dumps(decision))
        self.assertNotEqual(subprocess.run([sys.executable, "-IB", str(script)], capture_output=True).returncode, 0)
        self.mission["resources"]["endpoint_lab"]["require_price"] = True
        _, rev, new = self.submit((rid, version))
        self.assertEqual(new["status"], "verified", new["error"])
        self.assertEqual(self.controller.deliver(rid, rev, {}, trial=True)["decision"], "withheld")
        with self.assertRaises(Conflict):
            self.controller.deliver(rid, version)

    def test_scope_and_source_binding(self):
        self.mission["requirements"].append("Purchase the configuration for the lab.")
        rid, rev, state = self.submit()
        self.assertEqual(state["status"], "blocked")
        self.assertIsNone(state["artifact"])
        self.mission["requirements"].pop()
        _, rev, state = self.submit((rid, rev))
        self.assertEqual(state["routing"]["route"], "direct")
        for changes in ({"return_value": "changed"}, {"side_effect": FileNotFoundError}):
            with patch("ignition.endpoint_specialist.identity", **changes):
                view = self.controller.view(rid)
                self.assertEqual(view["status"], "stale")
                self.assertNotIn("endpoint_result", view)
                with self.assertRaises(Conflict):
                    self.controller.deliver(rid, rev)
        with self.assertRaises(StateError):
            self.controller.deliver(rid, rev, {"require_price": True}, trial=True)


    def test_review_date_is_the_actual_snapshot(self):
        self.mission["time"] = {"as_of": "2026-11-18"}
        _, _, run = self.submit()
        self.assertEqual(run["status"], "blocked")
        self.assertIn("2026-11-17", run["error"])
