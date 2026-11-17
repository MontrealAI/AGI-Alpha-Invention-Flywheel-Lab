import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from ignition.construction import build, freeze_contract
from ignition.delivery import export_bundle
from ignition.evaluation import evaluate
from qualify_live import EXAMPLE, MODEL_ALIAS, STAGES, acquired_investigation, check_portable, result_status, run_direct
from ignition.provider import LocalProvider


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

    def test_live_source_use_needs_lineage_and_dated_feed_pair(self):
        pair = [{"feed":"code", "source_response_sha256":"a", "role":"Published release"},
                {"feed":"code", "source_response_sha256":"b", "role":"Earlier snapshot; capability at this revision requires testing"}]
        state = {"source_result":{"feeds":["code"], "sources":pair}, "research":{
            "signals":[{"id":"S2","source_response_sha256":"a"}],
            "candidates":[{"id":"C1", "usable_sources":["S2"]}]}}
        calls = [{"mode":"local","status":"completed","reported_model":MODEL_ALIAS,"stage": stage}
                 for stage in ("discover","challenge")]
        self.assertEqual(acquired_investigation(state,calls)["status"], "PASS")
        state["research"]["candidates"][0]["usable_sources"] = ["S1"]
        self.assertEqual(acquired_investigation(state,calls)["status"], "FAIL")
        state["source_result"]["sources"] = []
        self.assertEqual(acquired_investigation(state,calls)["status"], "BLOCKED")

    def test_direct_model_control_does_not_receive_withheld_cases(self):
        columns = [{"source":"id","target":"record_id","type":"text"},
                   {"source":"id","target":"area","type":"text","split":{"separator":"-","index":0}},
                   {"source":"name","target":"headline","type":"text"},{"source":"status","target":"decision","type":"text"}]
        captured = []
        def sender(url, headers, body, timeout):
            captured.append(body["messages"][0]["content"])
            program = {"kind":"record_migration","program":{"columns":columns,"extra_fields":"reject"}}
            return {"model":MODEL_ALIAS,"choices":[{"finish_reason":"stop","message":{"content":json.dumps(program)}}]}
        model = LocalProvider("llama-cpp", MODEL_ALIAS, 8090, sender=sender)
        record = {}
        with tempfile.TemporaryDirectory() as tmp:
            run_direct(Path(tmp), model, record)
        self.assertEqual(record["status"], "PASS")
        self.assertEqual(len(captured),1)
        self.assertNotIn("Withheld actual observatory card",captured[0])
        self.assertEqual(record["portable"]["verified_exit"],0)

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
