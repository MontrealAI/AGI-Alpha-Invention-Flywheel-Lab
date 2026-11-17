import base64
import copy
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ignition.construction import ConstructionError, build, build_view, execute, freeze_contract
from ignition.delivery import export_bundle
from ignition.evaluation import evaluate


def mapping():
    definition = {"columns": [{"source": "legacy_id", "target": "id", "type": "integer"},
                              {"source": "active", "target": "enabled", "type": "boolean"}], "extra_fields": "reject"}
    spec = {"kind": "record_migration", "purpose": "Migrate a supplier catalogue", "definition": definition,
            "cases": [{"name": "row", "input": {"rows": [{"legacy_id": "4", "active": "false"}]},
                       "expected": {"rows": [{"id": 4, "enabled": False}]}},
                      {"name": "bad", "input": {"rows": [{"legacy_id": "004", "active": "false"}]},
                       "error": "invalid_value"}]}
    return spec, {"kind": spec["kind"], "program": copy.deepcopy(definition)}


def manifests():
    data = b"a real delivered byte stream\n"
    definition = {"manifest": {"docs/note.txt": hashlib.sha256(data).hexdigest()}}
    case = {"name": "all match", "input": {"files": {"docs/note.txt": base64.b64encode(data).decode()}},
            "expected": {"ok": True, "matched": ["docs/note.txt"], "unexpected": [], "changed": [], "missing": []}}
    spec = {"kind": "manifest_audit", "purpose": "Inspect the received research package",
            "definition": definition, "cases": [case]}
    return spec, {"kind": spec["kind"], "program": copy.deepcopy(definition)}


def synthesis():
    def row(code, label):
        return {"code": code, "region": label}
    def target(code, label):
        return {"id": int(code), "region": label.split("/")[0], "key": code + ":" + label}
    def pair(code, label):
        return {"input": {"rows": [row(code, label)]}, "expected": {"rows": [target(code, label)]}}
    definition = {"input_fields": ["code", "region"], "extra_fields": "reject",
                  "targets": [{"name": "id", "type": "integer"}, {"name": "region", "type": "text"},
                              {"name": "key", "type": "text"}],
                  "demonstrations": [pair("11", "QC/a"), pair("12", "ON/b")]}
    cases = [{"name": "fresh", **pair("13", "AB/c")}, {"name": "another fresh row", **pair("14", "BC/d/e")}]
    spec = {"kind": "record_migration", "purpose": "Transform legacy codes into an editorial routing index",
            "definition": definition, "cases": cases}
    proposal = {"kind": spec["kind"], "program": {"columns": [
        {"source": "code", "target": "id", "type": "integer"},
        {"source": "region", "target": "region", "type": "text", "split": {"separator": "/", "index": 0}},
        {"sources": ["code", "region"], "separator": ":", "target": "key", "type": "text"}],
        "extra_fields": "reject", "input_fields": ["code", "region"]}}
    return spec, proposal


class ConstructionTests(unittest.TestCase):
    def test_end_to_end_distinct_missions(self):
        for spec, proposal in (mapping(), manifests(), synthesis()):
            with self.subTest(kind=spec["kind"], purpose=spec["purpose"]):
                c = freeze_contract(spec)
                self.assertNotIn("cases", build_view(c))
                a = build(c, proposal)
                r = evaluate(c, a)
                self.assertEqual(r["status"], "pass", r["cases"])
                self.assertEqual(r["comparison"]["outcome"], "tie")
                self.assertEqual(execute(a, spec["cases"][0]["input"]), spec["cases"][0]["expected"])

    def test_object_input_is_not_an_authority(self):
        spec, proposal = mapping()
        c = freeze_contract(spec)
        proposal["program"]["execute"] = "touch /tmp/forbidden"
        with self.assertRaisesRegex(ConstructionError, "invalid_program"):
            build(c, proposal)
        with self.assertRaisesRegex(ConstructionError, "unsupported_kind"):
            freeze_contract({"purpose": "deploy arbitrary software", "kind": "deploy"})

    def test_migration_refuses_truncation_clamping_and_implicit_casts(self):
        s, p = mapping()
        a = build(freeze_contract(s), p)
        for value in ["-0", "01", 1.5, True, " 1", "1e3", str(2**53), None, []]:
            with self.subTest(value=value), self.assertRaisesRegex(ConstructionError, "invalid_value"):
                execute(a, {"rows": [{"legacy_id": value, "active": True}]})
        for bad, code in [({"active": True}, "missing_field"),
                          ({"legacy_id": 1, "active": False, "undeclared": True}, "extra_field")]:
            with self.assertRaisesRegex(ConstructionError, code):
                execute(a, {"rows": [s["cases"][0]["input"]["rows"][0], bad]})
        p["program"]["extra_fields"] = "drop"
        r = evaluate(freeze_contract(s), build(freeze_contract(s), p))
        self.assertEqual(r["status"], "fail")
        self.assertEqual(r["comparison"]["outcome"], "baseline_wins")

    def test_wrong_solution_cannot_approve_itself(self):
        s, p = synthesis()
        p["program"]["columns"][1]["split"]["index"] = 1
        c = freeze_contract(s)
        r = evaluate(c, build(c, p))
        self.assertEqual(r["status"], "fail")
        self.assertEqual(r["comparison"]["outcome"], "baseline_wins")

    def test_poisoned_oracle_is_quarantined(self):
        s, p = mapping()
        # JSON's integer zero differs from the Boolean false despite Python equality.
        s["cases"][0]["expected"]["rows"][0]["enabled"] = 0
        c = freeze_contract(s)
        r = evaluate(c, build(c, p))
        self.assertEqual(r["status"], "fail")
        self.assertFalse(r["comparison"]["oracles_agree"])
        self.assertEqual(r["comparison"]["outcome"], "incomparable")

    def test_example_ambiguity_and_holdout_leak(self):
        s, p = synthesis()
        for d in s["definition"]["demonstrations"]:
            row = d["input"]["rows"][0]
            row["shadow"] = row["code"]
        s["definition"]["input_fields"].append("shadow")
        p["program"]["input_fields"].append("shadow")
        for case in s["cases"]:
            case["input"]["rows"][0]["shadow"] = "different"
        c = freeze_contract(s)
        r = evaluate(c, build(c, p))
        self.assertEqual(r["comparison"]["outcome"], "incomparable")
        self.assertIn("ambiguous", r["comparison"]["reference_obstruction"])
        s["cases"][0] = {"name": "leaked", **s["definition"]["demonstrations"][0]}
        with self.assertRaisesRegex(ConstructionError, "reused"):
            freeze_contract(s)

    def test_manifest_tamper_missing_extra_and_bad_paths(self):
        s, p = manifests()
        a = build(freeze_contract(s), p)
        self.assertEqual(execute(a, {"files": {"extra": ""}}), {"matched": [], "changed": [],
                         "missing": ["docs/note.txt"], "unexpected": ["extra"], "ok": False})
        self.assertEqual(execute(a, {"files": {"docs/note.txt": ""}})["changed"], ["docs/note.txt"])
        for path in ("../x", "/x", "a//b", "https://host/x", "a\\b", "C:/x", "a\x00"):
            with self.subTest(path=path), self.assertRaisesRegex(ConstructionError, "invalid_path"):
                execute(a, {"files": {path: ""}})
        for bad in ("*not base64*", "ZE=="):
            with self.assertRaisesRegex(ConstructionError, "invalid_value"):
                execute(a, {"files": {"doc": bad}})

    def test_modified_artifact_contract_receipt_and_invalid_export(self):
        s, p = mapping()
        c = freeze_contract(s)
        a = build(c, p)
        r = evaluate(c, a)
        corrupt = copy.deepcopy(a)
        corrupt["program"]["columns"][0]["type"] = "text"
        with self.assertRaisesRegex(ConstructionError, "invalid_artifact"):
            execute(corrupt, s["cases"][0]["input"])
        s["purpose"] = "Different purpose"
        with self.assertRaisesRegex(ConstructionError, "stale_contract"):
            evaluate(freeze_contract(s), a)
        c["spec"]["purpose"] = s["purpose"]
        with self.assertRaisesRegex(ConstructionError, "stale_contract"):
            build(c, p)
        timing_tamper = copy.deepcopy(r)
        timing_tamper["telemetry_ns"]["candidate"] = -1
        original, _ = mapping()
        with self.assertRaisesRegex(ConstructionError, "stale_receipt"):
            export_bundle(freeze_contract(original), a, timing_tamper)
        r["comparison"]["outcome"] = "candidate_wins"
        c, p = mapping()
        with self.assertRaisesRegex(ConstructionError, "stale_receipt"):
            export_bundle(freeze_contract(c), a, r)

    def test_recipient_runs_export_outside_repository(self):
        s, p = manifests()
        c = freeze_contract(s)
        a = build(c, p)
        r = evaluate(c, a)
        archive = export_bundle(c, a, r, {"mode": "test"})
        self.assertEqual(archive, export_bundle(c, a, r, {"mode": "test"}))
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
                bundle.extractall(base)
            result = subprocess.run([sys.executable, "-I", "run.py", "verify"], cwd=base, capture_output=True, check=True)
            self.assertEqual(json.loads(result.stdout)["status"], "pass")
            run = [sys.executable, "-I", "run.py", "run"]
            result = subprocess.run(run, cwd=base, input=(base / "example-input.json").read_bytes(), capture_output=True, check=True)
            self.assertEqual(json.loads(result.stdout), s["cases"][0]["expected"])
            result = subprocess.run(run, cwd=base, input=b'{"files":{},"files":{}}', capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duplicate", result.stderr.decode())
            (base / "artifact.json").write_text("{}")
            self.assertNotEqual(subprocess.run(run, cwd=base, input=b"{}", capture_output=True).returncode, 0)

    def test_drop_policy_and_split_from_last(self):
        s, p = synthesis()
        p["program"]["extra_fields"] = "drop"
        p["program"]["columns"][1]["split"]["index"] = -1
        a = build(freeze_contract(s), p)
        out = execute(a, {"rows": [{"code": "25", "region": "one/two/three", "extra": "discard me"}]})
        self.assertEqual(out["rows"][0]["region"], "three")


if __name__ == "__main__":
    unittest.main()
