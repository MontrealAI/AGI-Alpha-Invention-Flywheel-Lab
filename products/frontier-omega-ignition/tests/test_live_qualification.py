import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from ignition.construction import build, freeze_contract
from ignition.delivery import export_bundle
from ignition.evaluation import evaluate
from qualify_live import EXAMPLE, MODEL_ALIAS, STAGES, check_portable, result_status


class HostedQualificationTests(unittest.TestCase):
    def test_explicitly_completed_live_routes_only(self):
        state = {"status": "verified", "evaluation": {"status": "pass"}}
        calls = [{"stage": stage, "mode": "local", "status": "completed", "reported_model": MODEL_ALIAS,
                  "response_sha256": "a"*64, "application_model_calls": 1} for stage in sorted(STAGES)]
        self.assertEqual(result_status(state, calls, True), "PASS")
        self.assertEqual(result_status(state, calls, False), "FAIL")
        self.assertEqual(result_status(state, calls[:2], True), "FAIL")
        for change in ({"mode": "manual"}, {"reported_model": "other"}, {"application_model_calls": 0},
                       {"status": "failed"}, {"response_sha256": None}):
            self.assertEqual(result_status(state, calls[:-1]+[{**calls[-1], **change}], True), "FAIL")
        self.assertEqual(result_status({**state, "status": "deferred"}, calls, True), "FAIL")

    def test_release_reproduction_uses_only_fixed_executables(self):
        spec = json.loads(EXAMPLE.read_text())["mission"]["construction_spec"]
        contract = freeze_contract(spec)
        cols = [{"source": "id", "target": "record_id", "type": "text"},
                {"source": "id", "target": "area", "type": "text", "split": {"separator": "-", "index": 0}},
                {"source": "name", "target": "headline", "type": "text"},
                {"source": "status", "target": "decision", "type": "text"}]
        artifact = build(contract, {"kind": "record_migration", "program": {
            "columns": cols, "input_fields": ["id", "name", "status"], "extra_fields": "reject"}})
        archive = export_bundle(contract, artifact, evaluate(contract, artifact))
        with tempfile.TemporaryDirectory() as tmp:
            p = check_portable(archive, Path(tmp))
            self.assertEqual((p["verified_exit"], p["example_exit"]), (0, 0))
        changed = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(archive)) as src, zipfile.ZipFile(changed, "w") as dst:
            for name in src.namelist():
                dst.writestr(name, b"raise RuntimeError('replaced')" if name == "run.py" else src.read(name))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "implementation differs"):
                check_portable(changed.getvalue(), Path(tmp))
