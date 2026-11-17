"""Independent checks of the direct source-locked public integrity construction."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "direct_manifest.py"


def load():
    spec = importlib.util.spec_from_file_location("ignition_fixed_direct", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FixedManifestQualification(unittest.TestCase):
    def test_accepted_portable_receiver_observed_file_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "recipient"
            proc = subprocess.run([sys.executable, "-B", str(SCRIPT), "--output", str(target),
                                   "--strong-conventional"], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            receipt = json.loads((target / "RESULT.json").read_text())
            self.assertEqual(receipt["status"], "ENGINEERING_ACCEPTED")
            self.assertEqual(receipt["model_calls"], 0)
            self.assertEqual(receipt["case_count"], 5)
            self.assertEqual(receipt["receiver"]["verify"], "PASS")
            self.assertEqual(len(receipt["receiver"]["cases"]), 3)
            self.assertEqual(receipt["receiver"]["negative_cases"], 2)
            self.assertEqual(receipt["competent_conventional"]["outcome"], "tie_on_frozen_cases")
            self.assertEqual(receipt["competent_conventional"]["passed_cases"], 5)
            self.assertEqual(receipt["evaluator_control_outcome"], "tie")
            self.assertIsNone(receipt["trailing_365_profit"])
            with zipfile.ZipFile(target / "receiver.zip") as artifact:
                self.assertIsNone(artifact.testzip())
                self.assertIn("run.py", artifact.namelist())

    def test_existing_destination_is_immutable(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "already-exists"
            target.mkdir()
            marker = target / "protected"
            marker.write_text("original")
            proc = subprocess.run([sys.executable, "-B", str(SCRIPT), "--output", str(target)],
                                  capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("FRESH_OUTPUT_DIRECTORY_REQUIRED", proc.stderr)
            self.assertEqual(marker.read_text(), "original")
            self.assertEqual(sorted(p.name for p in target.iterdir()), ["protected"])

    def test_changed_public_fixture_is_rejected_before_output(self):
        m = load()
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp) / "integrity.json"
            fake.write_bytes(m.FIXTURE.read_bytes().replace(b'"id": "integrity"',
                                                           b'"id": "invented"'))
            m.FIXTURE = fake
            with self.assertRaisesRegex(ValueError, "SOURCE_LOCK_MISMATCH|FIXTURE_CONTENT_MISMATCH"):
                m.source_lock()

    def test_unsupported_model_invented_scope_not_silently_accepted(self):
        m = load()
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp) / "unsafe.json"
            fixture = json.loads(m.FIXTURE.read_bytes())
            fixture["mission"]["construction_spec"]["kind"] = "unsupported"
            fake.write_text(json.dumps(fixture))
            m.FIXTURE = fake
            m.source_lock = lambda: {"test": "source_scope_intentionally_injected"}
            output = Path(temp) / "receiver"
            with self.assertRaisesRegex(ValueError, "DIRECT_MANIFEST_ONLY"):
                m.qualify(output, strong_conventional=False)
            self.assertFalse(output.exists())

    def test_poisoned_independent_oracle_cannot_self_approve(self):
        m = load()
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp) / "poisoned.json"
            fixture = json.loads(m.FIXTURE.read_bytes())
            fixture["mission"]["construction_spec"]["cases"][0]["expected"]["matched"] = []
            fake.write_text(json.dumps(fixture))
            m.FIXTURE = fake
            m.source_lock = lambda: {"test": "source_scope_intentionally_injected"}
            output = Path(temp) / "receiver"
            with self.assertRaisesRegex(ValueError, "FROZEN_INDEPENDENT_ACCEPTANCE_FAILED"):
                m.qualify(output, strong_conventional=False)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
