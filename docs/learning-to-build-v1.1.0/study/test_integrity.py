#!/usr/bin/env python3
"""Targeted regressions for the two defects found during independent review.

Run with: python3 -m unittest test_integrity.py -v
All mutations occur in disposable copies. The registered protocol is never edited.
"""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


def run_script(root, name, *args):
    command = [sys.executable]
    if sys.flags.optimize:
        command.append("-O")
    command.extend([str(root/name), *map(str, args)])
    return subprocess.run(command, text=True, capture_output=True)


def set_path(value, path, replacement):
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement


class RegisteredEvidenceIntegrity(unittest.TestCase):
    def test_genuine_report_is_accepted(self):
        result = run_script(ROOT, "check.py", "--evidence", ROOT/"evidence")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["accepted"])

    def test_changed_protocol_is_rejected_even_with_rehashed_report(self):
        mutations = [
            (("financial_model", "constructor_replay", "fresh_construction"), 700),
            (("financial_model", "receipt"), 1),
        ]
        for path, replacement in mutations:
            with self.subTest(path=path), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for name in ("study.py", "check.py", "PROTOCOL.json"):
                    shutil.copy2(ROOT/name, root/name)
                shutil.copytree(ROOT/"evidence", root/"evidence")
                protocol = json.loads((root/"PROTOCOL.json").read_text())
                set_path(protocol, path, replacement)
                (root/"PROTOCOL.json").write_text(json.dumps(protocol, indent=2)+"\n")
                report_path = root/"evidence"/"RESULTS.json"
                report = json.loads(report_path.read_text())
                report["protocol_sha256"] = hashlib.sha256((root/"PROTOCOL.json").read_bytes()).hexdigest()
                report_path.write_text(json.dumps(report, indent=2)+"\n")
                for script, option in (("study.py", "--output"), ("check.py", "--evidence")):
                    with self.subTest(script=script):
                        result = run_script(root, script, option, root/"evidence")
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn("exact registered protocol hash required", result.stderr)

    def test_forged_report_claims_and_missing_rows_are_rejected(self):
        original = json.loads((ROOT/"evidence"/"RESULTS.json").read_text())
        all_false = {key: False for key in original["adversarial_checks"]}
        mutations = [
            (("technical", 0, "compiled_matches"), 0),
            (("technical", 0, "ordinary_matches"), -1),
            (("technical", 1, "source_artifact_reuse"), "accepted"),
            (("technical", 0, "spec_sha256"), "0"*64),
            (("technical", 0, "program_sha256"), "0"*64),
            (("route_decisions",), 0),
            (("equal_content_decision_ties",), 0),
            (("fresh_successor_tasks",), 99),
            (("adversarial_checks",), all_false),
            (("retention",), []),
            (("retention",), original["retention"][:-1]),
            (("retention", 0, "net_saving_after_acquisition"), 999),
            (("technical",), original["technical"][:-1]),
            # JSON equality must not silently equate a boolean flag with integer 1.
            (("adversarial_checks", "wrong_schema_rejected"), 1),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)/"evidence"
            shutil.copytree(ROOT/"evidence", evidence)
            for path, replacement in mutations:
                with self.subTest(path=path, replacement=replacement):
                    report = copy.deepcopy(original)
                    set_path(report, path, replacement)
                    (evidence/"RESULTS.json").write_text(json.dumps(report, indent=2)+"\n")
                    result = run_script(ROOT, "check.py", "--evidence", evidence)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("reported RESULTS.json does not match", result.stderr)


if __name__ == "__main__":
    unittest.main()
