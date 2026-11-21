"""CLI rejection regressions for observed audit/control receipt defects.

No network or local CSV data are needed: provenance and cohort failures must be
rejected before source-data access. Full data semantics run after fetch in CI.
"""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WrapperIntegrityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.successor = json.loads((ROOT / "evidence/successor.json").read_text())
        cls.baseline = json.loads((ROOT / "independent/SUCCESSOR_BASELINES.json").read_text())

    def audit_rejected(self, mutate, reason):
        payload = deepcopy(self.successor)
        mutate(payload)
        with tempfile.TemporaryDirectory(prefix="frontier-audit-rejection-") as directory:
            directory = Path(directory)
            source = directory / "successor.json"
            source.write_text(json.dumps(payload))
            output = directory / "verdict.json"
            command = [sys.executable, "-B", str(ROOT / "audit.py"), "--data-dir", str(directory / "absent-data"),
                       "--first", str(ROOT / "evidence/first_portfolio.json"), "--successor", str(source),
                       "--output", str(output)]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn(reason, completed.stderr)
            self.assertFalse(output.exists(), "Rejected audit must not leave an accepted result")

    def transfer_rejected(self, mutate_successor, mutate_baseline, reason):
        successor, baseline = deepcopy(self.successor), deepcopy(self.baseline)
        mutate_successor(successor)
        mutate_baseline(baseline)
        with tempfile.TemporaryDirectory(prefix="frontier-transfer-rejection-") as directory:
            directory = Path(directory)
            successor_path, baseline_path = directory / "successor.json", directory / "baseline.json"
            successor_path.write_text(json.dumps(successor))
            baseline_path.write_text(json.dumps(baseline))
            output = directory / "verdict.json"
            command = [sys.executable, "-B", str(ROOT / "transfer_check.py"), "--successor", str(successor_path),
                       "--baseline", str(baseline_path), "--output", str(output), "--repeats", "1"]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn(reason, completed.stderr)
            self.assertFalse(output.exists(), "Rejected transfer must not leave an accepted result")

    def test_audit_rejects_retained_asset_provenance(self):
        self.audit_rejected(lambda x: x.update(retained_cover_sha256="0" * 64), "SUCCESSOR_RETAINED_SOURCE_MISMATCH")

    def test_audit_rejects_case_asset_provenance(self):
        self.audit_rejected(lambda x: x["results"][0].update(retained_asset_sha256="0" * 64),
                            "SUCCESSOR_CASE_RETAINED_SOURCE_MISMATCH")

    def test_audit_rejects_adapter_provenance(self):
        self.audit_rejected(lambda x: x.update(adapter_sha256="0" * 64), "SUCCESSOR_ADAPTER_SOURCE_MISMATCH")

    def test_audit_rejects_case_adapter_provenance(self):
        self.audit_rejected(lambda x: x["results"][0].update(adapter_sha256="0" * 64),
                            "SUCCESSOR_CASE_ADAPTER_SOURCE_MISMATCH")

    def test_audit_rejects_protocol_provenance(self):
        self.audit_rejected(lambda x: x.update(protocol_sha256="0" * 64), "SUCCESSOR_PROTOCOL_MISMATCH")

    def copied_audit_freeze_rejected(self, freeze_path, field, reason):
        # Only a disposable copy is changed; actual frozen sources/receipts stay intact.
        paths = ["audit.py", "cover.py", "portfolio.py", "PROTOCOL.json", "successor.py",
                 "evidence/FIRST_ASSET_FREEZE.json", "evidence/first_portfolio.json",
                 "evidence/successor_source_freeze.json", "independent/PROTOCOL.json",
                 "independent/PROTOCOL_FREEZE.json", "independent/verify_certificate.py"]
        with tempfile.TemporaryDirectory(prefix="frontier-freeze-rejection-") as directory:
            directory = Path(directory)
            for name in paths:
                destination = directory / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, destination)
            receipt_path = directory / freeze_path
            payload = json.loads(receipt_path.read_text())
            payload[field] = "0" * 64
            receipt_path.write_text(json.dumps(payload))
            output = directory / "verdict.json"
            command = [sys.executable, "-S", "-B", str(directory / "audit.py"),
                       "--data-dir", str(directory / "absent-data"),
                       "--first", str(directory / "evidence/first_portfolio.json"),
                       "--successor", str(ROOT / "evidence/successor.json"), "--output", str(output)]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn(reason, completed.stderr)
            self.assertFalse(output.exists())

    def test_audit_rejects_changed_successor_freeze(self):
        self.copied_audit_freeze_rejected("evidence/successor_source_freeze.json", "source_sha256",
                                          "FROZEN_SUCCESSOR_ADAPTER_CHANGED")

    def test_audit_rejects_changed_protocol_freeze(self):
        self.copied_audit_freeze_rejected("independent/PROTOCOL_FREEZE.json", "protocol_sha256",
                                          "FROZEN_INDEPENDENT_PROTOCOL_CHANGED")

    def test_transfer_rejects_empty_successor(self):
        self.transfer_rejected(lambda x: x.update(results=[]), lambda x: None, "SUCCESSOR_CASE_SEQUENCE")

    def test_transfer_rejects_duplicate_successor(self):
        self.transfer_rejected(lambda x: x["results"].__setitem__(1, deepcopy(x["results"][0])),
                               lambda x: None, "SUCCESSOR_CASE_SEQUENCE")

    def test_transfer_rejects_missing_baseline_cases(self):
        self.transfer_rejected(lambda x: None, lambda x: x.update(cases=[]), "BASELINE_CASE_DENOMINATOR")

    def test_transfer_rejects_duplicate_baseline_cases(self):
        self.transfer_rejected(lambda x: None, lambda x: x["cases"].__setitem__(1, deepcopy(x["cases"][0])),
                               "BASELINE_CASE_SEQUENCE")

    def test_transfer_rejects_changed_baseline_source(self):
        self.transfer_rejected(lambda x: None, lambda x: x.update(source_sha256="0" * 64), "BASELINE_SOURCE_BINDING")

    def test_transfer_rejects_changed_data_binding(self):
        self.transfer_rejected(lambda x: None, lambda x: x["cases"][0].update(source_sha256="0" * 64), "BASELINE_DATA_BINDING")

    def test_transfer_rejects_changed_problem(self):
        self.transfer_rejected(lambda x: None, lambda x: x["cases"][0].update(mathematical_problem_sha256="0" * 64),
                               "BASELINE_PROBLEM_BINDING")

    def test_transfer_rejects_absent_exact_runs(self):
        self.transfer_rejected(lambda x: None, lambda x: x["cases"][0]["methods"][1].update(runs=[]),
                               "BASELINE_RUN_DENOMINATOR")

    def test_transfer_rejects_false_exact_selection(self):
        self.transfer_rejected(lambda x: None,
                               lambda x: x["cases"][0]["methods"][1]["runs"][0]["verdict"].update(selected_indices=[]),
                               "BASELINE_SELECTION_CARDINALITY")


if __name__ == "__main__":
    unittest.main()
