"""Frozen P0-202 selected-source positive and original-owner negative controls."""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from commercial.ledger import digest
from connected_enterprise.finance import source_identity, source_paths_for_manifest
from reference import target_identity_before_and_after

OWNER_SHA = "9866d004c412fc05c9f6292cf898307f177359df"
FINANCE_SHA = "02c81396ad90dbd31efbfeeb1a973fbbdb428bb4"
DEFAULT = {"schema": "agi-alpha/default-legacy-native/v1"}
PRODUCTION = {"schema": "production060/native-services/v1"}
INVENTORY = {"schema": "inventory061/native-services/v1"}
CASES = [(DEFAULT, 42), (PRODUCTION, 48), (INVENTORY, 61)]


def blob_sha(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def isolated_selected(root: Path, schema: dict) -> Path:
    selected = source_paths_for_manifest(schema)
    for name in selected:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    return root


class SelectedTargetReferenceTest(unittest.TestCase):
    def test_01_real_main_finance_blob_pinned(self):
        self.assertEqual(blob_sha(ROOT / "connected_enterprise/finance.py"), FINANCE_SHA)

    def test_02_exact_manifest_selected_closures(self):
        for manifest, count in CASES:
            with self.subTest(schema=manifest["schema"]):
                paths = source_paths_for_manifest(manifest)
                self.assertEqual(len(paths), count)
                self.assertEqual(len(paths), len(set(paths)))
                state = source_identity(ROOT, manifest)
                self.assertEqual(len(state["files"]), count)
                self.assertEqual(state["sha256"], digest(state["files"]))
                self.assertEqual(target_identity_before_and_after(ROOT, manifest), state)
        self.assertIn("production060/service.py", source_paths_for_manifest(PRODUCTION))
        self.assertIn("inventory061/quality_constructor.py", source_paths_for_manifest(INVENTORY))
        self.assertNotIn("production060/service.py", source_paths_for_manifest(DEFAULT))
        self.assertNotIn("inventory061/quality_constructor.py", source_paths_for_manifest(DEFAULT))

    def test_03_production_producer_mutation_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_selected(Path(tmp), PRODUCTION)
            before = source_identity(root, PRODUCTION)
            default = source_identity(root, DEFAULT)
            target = root / "production060/service.py"
            target.write_bytes(target.read_bytes() + b"\n# temporary authorized-test perturbation\n")
            self.assertNotEqual(before, source_identity(root, PRODUCTION))
            self.assertEqual(default, source_identity(root, DEFAULT))

    def test_04_inventory_producer_mutation_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_selected(Path(tmp), INVENTORY)
            before = source_identity(root, INVENTORY)
            default = source_identity(root, DEFAULT)
            target = root / "inventory061/quality_constructor.py"
            target.write_bytes(target.read_bytes() + b"\n# temporary inventory perturbation\n")
            self.assertNotEqual(before, source_identity(root, INVENTORY))
            self.assertEqual(default, source_identity(root, DEFAULT))

    def test_05_omitted_manifest_is_not_active_service_identity(self):
        legacy = source_identity(ROOT)
        self.assertEqual(legacy, source_identity(ROOT, DEFAULT))
        self.assertNotEqual(legacy, source_identity(ROOT, PRODUCTION))
        self.assertNotEqual(legacy, source_identity(ROOT, INVENTORY))

    def test_06_irrelevant_files_and_missing_selected_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_selected(Path(tmp), PRODUCTION)
            before = source_identity(root, PRODUCTION)
            (root / "unrelated-note.txt").write_text("outside selected closure")
            self.assertEqual(before, source_identity(root, PRODUCTION))
            (root / "production060/service.py").unlink()
            with self.assertRaisesRegex(ValueError, "REGULAR_CONNECTED_FINANCE_SOURCE_REQUIRED"):
                source_identity(root, PRODUCTION)

    def test_07_selected_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_selected(Path(tmp), PRODUCTION)
            target = root / "production060/service.py"
            target.unlink()
            target.symlink_to(ROOT / "production060/service.py")
            with self.assertRaisesRegex(ValueError, "REGULAR_CONNECTED_FINANCE_SOURCE_REQUIRED"):
                source_identity(root, PRODUCTION)

    def test_08_reference_detects_change_across_hypothetical_signing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_selected(Path(tmp), INVENTORY)
            target = root / "inventory061/quality_constructor.py"
            def change():
                target.write_bytes(target.read_bytes() + b"\n# changed after target selection\n")
            with self.assertRaisesRegex(ValueError, "SELECTED_TARGET_CHANGED_DURING_AUTHORIZATION"):
                target_identity_before_and_after(root, INVENTORY, change)
            with self.assertRaisesRegex(ValueError, "EXPLICIT_SELECTED_SERVICE_MANIFEST_REQUIRED"):
                target_identity_before_and_after(root, None)

    def test_09_pinned_original_owner_was_missing_manifest_at_both_checks(self):
        owner = os.environ.get("P0202_OWNER_ROOT")
        if not owner:
            self.fail("PINNED_PR40_OWNER_CHECKOUT_REQUIRED_NOT_A_SOFT_SKIP")
        path = Path(owner) / "connected_enterprise/upgrades.py"
        self.assertEqual(blob_sha(path), OWNER_SHA)
        module = ast.parse(path.read_text())
        fn = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "authorize_upgrade")
        calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and
                 isinstance(n.func, ast.Name) and n.func.id == "source_identity"]
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(len(n.args) == 1 and not n.keywords for n in calls))
        self.assertIn("manifest", [a.arg for a in fn.args.kwonlyargs if isinstance(a, ast.arg)])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SelectedTargetReferenceTest)
    report = unittest.TextTestRunner(verbosity=2).run(suite)
    result = {"schema": "agi-alpha/p0-selected-target-20261120/v1",
              "source_main": "f0987aa48d5c9136b28540f54eabf5367e63bbe6",
              "original_owner": "ced6c1cb004887dcdafaea59a2976020be649f8e",
              "tests_run": report.testsRun, "errors": len(report.errors),
              "failures": len(report.failures), "skipped": len(report.skipped),
              "accepted": report.wasSuccessful(),
              "evidence_scope": "SOURCE_CLOSURE_ONLY_NO_SIGNER_NO_ACCOUNT_NO_MIGRATION"}
    if os.environ.get("P0202_REPORT"):
        Path(os.environ["P0202_REPORT"]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    sys.exit(0 if report.wasSuccessful() else 1)
