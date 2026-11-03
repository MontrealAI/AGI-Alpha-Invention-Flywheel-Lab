"""Isolation controls for composition, not new financial or market evidence."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from enterprise078.runtime import OVERRIDES
from scripts.enterprise078_scale_runtime import materialize, scale_payload

ROOT = Path(__file__).resolve().parents[1]


class ScaleRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.destination = self.base / "composed"

    def test_exact_science_scale_and_current_native_are_separate(self):
        before = {name: (ROOT / name).read_bytes() for name in OVERRIDES}
        receipt = materialize(ROOT, self.destination)
        frozen = json.loads((ROOT / "enterprise078/FROZEN.json").read_text())
        for name, expected in frozen["files"].items():
            self.assertEqual(hashlib.sha256((self.destination / name).read_bytes()).hexdigest(), expected)
        for name, raw in scale_payload(ROOT).items():
            self.assertEqual((self.destination / name).read_bytes(), raw)
        for name, raw in before.items():
            self.assertEqual((ROOT / name).read_bytes(), raw)
            self.assertNotEqual((self.destination / name).read_bytes(), raw)
        self.assertEqual(receipt["scale_files"], 11)
        self.assertEqual(len([p for p in self.destination.rglob("*") if p.is_file()]), 317)
        self.assertFalse(receipt["account_state_read_or_copied"])
        self.assertFalse((self.destination / "enterprise078/runtime.py").exists())

    def test_imports_and_public_source_export_use_staged_original_bytes(self):
        materialize(ROOT, self.destination)
        exported = self.base / "exported"
        command = """
import json
from pathlib import Path
import commercial.ledger, connected_enterprise.finance, enterprise078_scale.operator
from enterprise078_scale.run import copy_source
modules = (commercial.ledger, connected_enterprise.finance, enterprise078_scale.operator)
assert all(Path(m.__file__).resolve().is_relative_to(Path.cwd()) for m in modules)
copy_source(Path(__import__('sys').argv[1]))
"""
        env = {**os.environ, "PYTHONPATH": str(self.destination), "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"}
        subprocess.run([sys.executable, "-c", command, str(exported)], cwd=self.destination, env=env, check=True)
        frozen = json.loads((ROOT / "enterprise078/FROZEN.json").read_text())
        exported_manifest = json.loads((exported / "SOURCE.json").read_text())
        # The frozen runner deliberately packages the active service closure,
        # not unused scale.py/test_enterprise078.py from the science freeze.
        omitted = {"enterprise078/scale.py", "enterprise078/test_enterprise078.py"}
        self.assertEqual(set(frozen["files"]) - set(exported_manifest["files"]), omitted)
        for name, expected in frozen["files"].items():
            if name not in omitted:
                self.assertEqual(exported_manifest["files"][name], expected)
        for name, raw in scale_payload(ROOT).items():
            self.assertEqual((exported / name).read_bytes(), raw)

    def test_existing_destination_remains_untouched(self):
        self.destination.mkdir()
        (self.destination / "owned").write_text("retain")
        with self.assertRaisesRegex(ValueError, "NEW_SCALE_RUNTIME_REQUIRED"):
            materialize(ROOT, self.destination)
        self.assertEqual((self.destination / "owned").read_text(), "retain")

    def test_symlink_parent_is_refused(self):
        (self.base / "alias").symlink_to(self.base, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "UNALIASED"):
            materialize(ROOT, self.base / "alias" / "stage")
        self.assertFalse((self.base / "stage").exists())

    def test_checkout_destination_is_refused(self):
        with self.assertRaisesRegex(ValueError, "OUTSIDE_CHECKOUT"):
            materialize(ROOT, ROOT / "not-a-valid-runtime")

    def test_parent_alias_cannot_bypass_checkout_boundary(self):
        alias = ROOT.parent / "unused" / ".." / ROOT.name / "not-a-valid-runtime"
        with self.assertRaisesRegex(ValueError, "UNALIASED"):
            materialize(ROOT, alias)

    def test_partial_scientific_stage_is_not_promoted(self):
        def interrupted(root, destination):
            destination.mkdir()
            (destination / "partial.py").write_text("incomplete")
            raise ValueError("INJECTED_PARTIAL_STAGE")
        with patch("scripts.enterprise078_scale_runtime.materialize_science", side_effect=interrupted):
            with self.assertRaisesRegex(ValueError, "INJECTED_PARTIAL_STAGE"):
                materialize(ROOT, self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.base.glob(".e078-composition-*")), [])

    def test_changed_scale_source_is_refused_before_scientific_staging(self):
        from scripts import enterprise078_scale_runtime as runtime
        original = runtime.regular_bytes
        def changed(path):
            raw = original(path)
            return raw + b"changed" if path.name == "account.py" else raw
        with patch.object(runtime, "regular_bytes", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "FROZEN_SCALE_BYTES_CHANGED"):
                materialize(ROOT, self.destination)
        self.assertFalse(self.destination.exists())


if __name__ == "__main__":
    unittest.main()
