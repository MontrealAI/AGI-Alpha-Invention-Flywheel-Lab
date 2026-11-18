import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from ignition.controller import Controller
from ignition.quantum_specialist import PRESET
from ignition.store import Conflict, StateError, Store


class QuantumMission(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.ctrl = Controller(Store(self.root / "state"))
        doc = json.loads(PRESET.read_text())
        self.body = {key: doc[key] for key in ("mission", "sources")}
        self.body["request_id"] = "quantum-recipient-check"
        self.mission = self.body["mission"]

    def test_strong_control_export_and_source_invalidation(self):
        self.mission["beneficiary"] = "private marker 9F32"
        self.mission["resources"]["quantum_multiplier"][
            "minimum_cnot_improvement_bps"
        ] = 30
        rid, revision = self.ctrl.create(self.body)
        state = self.ctrl.advance(rid, revision)
        self.assertEqual(state["status"], "verified", state["error"])
        result = state["quantum_result"]
        self.assertIs(result["requested_cnot_threshold_met"], True)
        self.assertIs(result["material_cnot_advantage_over_strongest_control"], False)
        self.assertEqual(
            (result["strongest_conventional_cnot"], result["followup_cnot"]), (518, 516)
        )
        self.assertEqual(
            result["independent_truth_table"]["exhaustive_input_pairs_at_zero_target"],
            2**24,
        )
        self.assertEqual(state["field_decision"]["disposition"], "withhold")
        self.assertIsNone(result["payment_received"])
        self.assertIsNone(result["beneficiary_acceptance"])
        with self.assertRaises(StateError):
            self.ctrl.deliver(rid, revision, {"submit": True}, trial=True)
        exported = self.ctrl.deliver(rid, revision)
        self.assertEqual(
            hashlib.sha256(exported).hexdigest(), state["artifact"]["sha256"]
        )
        with ZipFile(io.BytesIO(exported)) as package:
            self.assertEqual(
                json.loads(package.read("REQUEST.json"))[
                    "minimum_cnot_improvement_bps"
                ],
                30,
            )
            for name in package.namelist():
                self.assertNotIn(b"private marker 9F32", package.read(name))
            package.extractall(self.root / "recipient")
        run = subprocess.run(
            [sys.executable, "-IB", str(self.root / "recipient" / "replay.py")],
            cwd=self.root,
            env={},
            check=True,
            capture_output=True,
        )
        actual = json.loads(run.stdout)
        self.assertEqual(actual["circuits"], result["circuits"])
        self.assertTrue(actual["requested_cnot_threshold_met"])
        with patch("ignition.quantum_specialist.identity", return_value="changed"):
            view = self.ctrl.view(rid)
            self.assertEqual(view["status"], "stale")
            self.assertNotIn("quantum_result", view)
            self.assertNotIn("field_decision", view)
            with self.assertRaises(Conflict):
                self.ctrl.deliver(rid, revision)

    def test_rejects_scope_expansion_threshold_bool_and_duplicate_routes(self):
        self.mission["requirements"].append("Submit competition entry.")
        rid, revision = self.ctrl.create(self.body)
        self.assertEqual(self.ctrl.advance(rid, revision)["status"], "blocked")
        self.mission["requirements"].pop()
        self.body["request_id"] += "-invalid"
        self.mission["resources"]["quantum_multiplier"][
            "minimum_cnot_improvement_bps"
        ] = True
        rid, revision = self.ctrl.create(self.body)
        self.assertEqual(self.ctrl.advance(rid, revision)["status"], "blocked")
        self.mission["resources"]["scroll_normalization"] = "robust-uint8-cpu"
        with self.assertRaises(StateError):
            self.ctrl.create(self.body)


if __name__ == "__main__":
    unittest.main()
