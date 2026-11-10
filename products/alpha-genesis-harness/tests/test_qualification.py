# SPDX-License-Identifier: Apache-2.0
"""Independent release-boundary regressions. All archives/credentials here are synthetic.

These tests execute harmless local archive fixtures and temporary Git repositories;
they make no network requests and do not claim product/provider qualification.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT / "scripts"))
import package_release as packaging
import qualify_archive as qualification

SOURCE = "a" * 40
ROOT = "ALPHA_GENESIS_HARNESS_0.3.0"
FAKE_SECRET_NAMES = ["GH_TOKEN", "GITHUB_TOKEN", "HARNESS_OPENAI_API_KEY", "AWS_SECRET_ACCESS_KEY", "OPENAI_API_KEY"]


def archive_fixture(marker="VERIFIED_SNAPSHOT", *, should_fail=False, extra_test_failure=False, extra_files=None, strategy_mode=None):
    """A separately authored tiny archive satisfying the integrity schema only."""
    files = {name: b"synthetic release-boundary fixture\n" for name in packaging.REQUIRED}
    files["VERSION.json"] = b'{"version":"0.3.0"}\n'
    if should_fail:
        node = "throw new Error('REPLACEMENT_MUST_NOT_EXECUTE');\n"
        python = "raise AssertionError('REPLACEMENT_MUST_NOT_EXECUTE')\n"
    else:
        node = ("const test=require('node:test');const assert=require('node:assert/strict');\n"
                "test('immutable archive sentinel and credential boundary',()=>{\n"
                f"for(const key of {json.dumps(FAKE_SECRET_NAMES)})assert.equal(process.env[key],undefined);\n"
                f"console.log('{marker}');}});\n")
        python = ("import os, unittest\nclass Boundary(unittest.TestCase):\n"
                  "    def test_environment(self):\n"
                  f"        for key in {FAKE_SECRET_NAMES!r}:\n"
                  "            self.assertNotIn(key, os.environ)\n"
                  f"        print('{marker}')\n")
    files["tests/sentinel.test.cjs"] = node.encode()
    files["tests/test_bridge.py"] = python.encode()
    if extra_test_failure:
        files["tests/test_new_service.py"] = b"import unittest\nclass NewService(unittest.TestCase):\n    def test_required_component(self):\n        self.fail('NEW_SERVICE_MUST_BE_CHECKED')\n"
    if strategy_mode is not None:
        files["bridge/__init__.py"] = b""
        strategy = ("import argparse, json, os\nfrom pathlib import Path\n"
                    "parser=argparse.ArgumentParser()\n"
                    "parser.add_argument('--workspace',type=Path,required=True)\n"
                    "parser.add_argument('--output',type=Path,required=True)\n"
                    "args=parser.parse_args()\n"
                    f"assert all(name not in os.environ for name in {FAKE_SECRET_NAMES!r})\n"
                    "assert not args.workspace.exists()\n"
                    "assert args.workspace.parent == Path.cwd().parent\n"
                    "args.workspace.mkdir()\n"
                    "assert args.output.is_absolute()\n")
        if strategy_mode == "fail":
            strategy += "raise SystemExit('STRATEGY_FIXTURE_FAILURE')\n"
        else:
            strategy += ("args.output.write_text(json.dumps({'schema':'synthetic-archive-strategy-boundary/v1',"
                         "'marker':'EXTRACTED_STRATEGY_EXECUTED','workspace':str(args.workspace)})+'\\n')\n"
                         "print('EXTRACTED_STRATEGY_EXECUTED')\n")
        files["bridge/strategy_demo.py"] = strategy.encode()
    if extra_files:
        files.update(extra_files)
    manifest = {"schema": "alpha-genesis-harness-release/v1", "version": "0.3.0", "build_mode": "source-bound",
                "source_revision": SOURCE, "source_product_tree": "b" * 40, "source_matches_commit": True,
                "files": [{"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                          for name, data in sorted(files.items())]}
    files[packaging.MANIFEST_NAME] = json.dumps(manifest).encode()
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, data in files.items():
            bundle.writestr(ROOT + "/" + name, data)
    return result.getvalue()


class ArchiveQualificationBoundaryTests(unittest.TestCase):
    def test_zero_exit_status_does_not_hide_a_failed_omega_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            archive, output = Path(folder) / "download.zip", Path(folder) / "receipt"
            entries = {name: b"independent inert fixture\n" for name in (
                "bridge/genesis_next.py", "docs/OMEGA-GENESIS-NEXT.md", "evidence/OMEGA-PROTOCOL.md",
                "tests/test_genesis_next.py", "tests/test_genesis_next_independent.py",
                "evidence/OMEGA-FRESH-SUCCESSOR-PROTOCOL.md", "scripts/qualify_genesis_successor.py")}
            raw = archive_fixture(extra_files=entries, strategy_mode="pass")
            archive.write_bytes(raw)
            def zero_exit(command, **kwargs):
                if "bridge.genesis_next" in command:
                    (output / "OMEGA-DEMONSTRATION.json").write_text(json.dumps({"experiment": {"qualification": {"correctness": "FAIL"}}}))
                if "run" in command and "scripts/qualify_genesis_successor.py" in command:
                    (output / "OMEGA-FRESH-SUCCESSOR.json").write_text('{"status":"PASS"}')
                return subprocess.CompletedProcess(command, 0, "", "")
            with patch.object(qualification.subprocess, "run", side_effect=zero_exit):
                with self.assertRaisesRegex(ValueError, "fixed correctness requirements"):
                    qualification.qualify(archive, hashlib.sha256(raw).hexdigest(), SOURCE, output)
            receipt = json.loads((output / "QUALIFICATION.json").read_text())
            self.assertEqual(receipt["verdict"], "INVALID")
            self.assertTrue(all(operation["returncode"] == 0 for operation in receipt["operations"]))
            self.assertTrue(any("bridge.strategy_demo" in operation["command"] for operation in receipt["operations"]))

    def test_omega_source_without_independent_qualification_cannot_execute(self):
        with tempfile.TemporaryDirectory() as folder:
            archive, output = Path(folder) / "download.zip", Path(folder) / "receipt"
            raw = archive_fixture(extra_files={"bridge/genesis_next.py": b"raise AssertionError('MUST_NOT_EXECUTE')\n"})
            archive.write_bytes(raw)
            with patch.object(qualification.subprocess, "run") as run:
                with self.assertRaisesRegex(ValueError, "qualification dependency"):
                    qualification.qualify(archive, hashlib.sha256(raw).hexdigest(), SOURCE, output)
                run.assert_not_called()
            receipt = json.loads((output / "QUALIFICATION.json").read_text())
            self.assertEqual(receipt["verdict"], "INVALID")

    def test_explicit_dom_qualification_cannot_silently_skip_missing_packaged_suite(self):
        with tempfile.TemporaryDirectory() as folder:
            archive, output = Path(folder) / "download.zip", Path(folder) / "receipt"
            raw = archive_fixture()
            archive.write_bytes(raw)
            modules = Path(folder) / "node_modules"
            (modules / "jsdom").mkdir(parents=True)
            (modules / "jsdom/package.json").write_text('{"version":"26.1.0"}')
            with patch.object(qualification.subprocess, "run") as run:
                with self.assertRaises((FileNotFoundError, ValueError)):
                    qualification.qualify(archive, hashlib.sha256(raw).hexdigest(), SOURCE, output, modules)
                run.assert_not_called()
            receipt = json.loads((output / "QUALIFICATION.json").read_text())
            self.assertEqual(receipt["verdict"], "INVALID")
            self.assertEqual(receipt["dom_qualification"], "REQUESTED")

    def test_new_component_tests_cannot_be_omitted_from_extracted_qualification(self):
        if shutil.which("node") is None:
            self.skipTest("Node is required for the extracted-byte operation")
        with tempfile.TemporaryDirectory() as folder:
            archive, output = Path(folder) / "download.zip", Path(folder) / "receipt"
            raw = archive_fixture(extra_test_failure=True)
            archive.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "Extracted operation 2 failed"):
                qualification.qualify(archive, hashlib.sha256(raw).hexdigest(), SOURCE, output)
            receipt = json.loads((output / "QUALIFICATION.json").read_text())
            self.assertEqual(receipt["verdict"], "INVALID")
            self.assertIn("NEW_SERVICE_MUST_BE_CHECKED", (output / "operation-2.stderr.txt").read_text())

    def test_verified_snapshot_is_executed_even_if_path_is_replaced(self):
        if shutil.which("node") is None:
            self.skipTest("Node is required for the extracted-byte operation")
        with tempfile.TemporaryDirectory() as folder:
            archive, output = Path(folder) / "download.zip", Path(folder) / "receipt"
            original = archive_fixture()
            replacement = archive_fixture("REPLACED", should_fail=True)
            archive.write_bytes(original)
            real_verify = qualification.verify_snapshot
            captured = []
            def replace_after_verify(snapshot, *args, **kwargs):
                captured.append(snapshot)
                result = real_verify(snapshot, *args, **kwargs)
                archive.write_bytes(replacement)
                return result
            with patch.object(qualification, "verify_snapshot", side_effect=replace_after_verify):
                receipt = qualification.qualify(archive, hashlib.sha256(original).hexdigest(), SOURCE, output)
            self.assertEqual(captured, [original])
            self.assertEqual(archive.read_bytes(), replacement)
            self.assertEqual(receipt["verdict"], "PASSED IN SCOPE")
            self.assertEqual(receipt["archive_sha256"], hashlib.sha256(original).hexdigest())
            logs = "".join(p.read_text() for p in output.glob("*.txt"))
            self.assertIn("VERIFIED_SNAPSHOT", logs)
            self.assertNotIn("REPLACEMENT_MUST_NOT_EXECUTE", logs)

    def test_actual_child_processes_receive_no_caller_credentials(self):
        if shutil.which("node") is None:
            self.skipTest("Node is required for the extracted-byte operation")
        with tempfile.TemporaryDirectory() as folder:
            archive, output = Path(folder) / "download.zip", Path(folder) / "receipt"
            raw = archive_fixture("CHILD_ENVIRONMENT_CHECKED")
            archive.write_bytes(raw)
            fixtures = {name: "INERT_TEST_VALUE_NOT_A_CREDENTIAL" for name in FAKE_SECRET_NAMES}
            with patch.dict(os.environ, fixtures):
                result = qualification.qualify(archive, hashlib.sha256(raw).hexdigest(), SOURCE, output)
            self.assertEqual(result["verdict"], "PASSED IN SCOPE")
            self.assertEqual(len(result["operations"]), 2)
            self.assertTrue(all(step["returncode"] == 0 for step in result["operations"]))
            for log in output.glob("*.txt"):
                self.assertNotIn("INERT_TEST_VALUE_NOT_A_CREDENTIAL", log.read_text())

    def test_extracted_strategy_demonstration_is_run_and_failure_is_not_ignored(self):
        if shutil.which("node") is None:
            self.skipTest("Node is required for the extracted-byte operation")
        for mode in ("pass", "fail"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                archive, output = Path(folder) / "download.zip", Path(folder) / "receipt"
                raw = archive_fixture(strategy_mode=mode)
                archive.write_bytes(raw)
                fixtures = {name: "INERT_TEST_VALUE_NOT_A_CREDENTIAL" for name in FAKE_SECRET_NAMES}
                with patch.dict(os.environ, fixtures):
                    if mode == "fail":
                        with self.assertRaisesRegex(ValueError, "Extracted operation 3 failed"):
                            qualification.qualify(archive, hashlib.sha256(raw).hexdigest(), SOURCE, output)
                    else:
                        qualification.qualify(archive, hashlib.sha256(raw).hexdigest(), SOURCE, output)
                receipt = json.loads((output / "QUALIFICATION.json").read_text())
                self.assertEqual(len(receipt["operations"]), 3)
                command = receipt["operations"][-1]["command"]
                self.assertEqual(command[:4], [sys.executable, "-B", "-m", "bridge.strategy_demo"])
                self.assertEqual(command[-2:], ["--output", str(output.resolve() / "STRATEGY-DEMONSTRATION.json")])
                if mode == "pass":
                    self.assertEqual(receipt["verdict"], "PASSED IN SCOPE")
                    evidence = json.loads((output / "STRATEGY-DEMONSTRATION.json").read_text())
                    self.assertEqual(evidence["marker"], "EXTRACTED_STRATEGY_EXECUTED")
                    self.assertIn("EXTRACTED_STRATEGY_EXECUTED", (output / "operation-3.stdout.txt").read_text())
                else:
                    self.assertEqual(receipt["verdict"], "INVALID")
                    self.assertNotEqual(receipt["operations"][-1]["returncode"], 0)
                    self.assertIn("STRATEGY_FIXTURE_FAILURE", (output / "operation-3.stderr.txt").read_text())

    def test_processing_bound_applies_before_validation_or_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            archive, output = Path(folder) / "large.zip", Path(folder) / "receipt"
            archive.write_bytes(b"x" * 65)
            with patch.object(qualification, "MAX_ARCHIVE", 64), patch.object(qualification, "verify_snapshot") as verify:
                with self.assertRaisesRegex(ValueError, "processing envelope"):
                    qualification.qualify(archive, hashlib.sha256(archive.read_bytes()).hexdigest(), SOURCE, output)
                verify.assert_not_called()
            self.assertFalse(output.exists())

    def test_external_archive_identity_mismatch_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            archive, output = Path(folder) / "download.zip", Path(folder) / "receipt"
            archive.write_bytes(archive_fixture())
            with patch.object(qualification.subprocess, "run") as run:
                with self.assertRaisesRegex(ValueError, "externally supplied"):
                    qualification.qualify(archive, "0" * 64, SOURCE, output)
                run.assert_not_called()
            self.assertFalse(output.exists())


class PreviewSourceBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name) / "repository"
        self.product = self.root / "products/alpha-genesis-harness"
        (self.product / "app").mkdir(parents=True)
        (self.product / "scripts").mkdir()
        (self.product / "bridge").mkdir()
        self.script = self.product / "scripts/publish_preview.py"
        shutil.copyfile(PRODUCT / "scripts/publish_preview.py", self.script)
        self.original = {}
        for name in ["index.html", "app.js", "engine.js", "styles.css"]:
            data = ("committed public asset: " + name + "\n").encode()
            (self.product / "app" / name).write_bytes(data)
            self.original[name] = data
        (self.product / "bridge/private-config.json").write_text('{"fixture":"MUST_NOT_PUBLISH"}')
        self.git("init", "-q")
        self.git("add", ".")
        self.commit()
        self.sha = self.git("rev-parse", "HEAD").strip()

    def tearDown(self):
        self.folder.cleanup()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE, text=True)

    def commit(self):
        self.git("-c", "user.name=Independent release fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture")

    def run_preview(self, sha, output):
        return subprocess.run([sys.executable, str(self.script), "--source-revision", sha, "--output", str(output)],
                              capture_output=True, text=True)

    def test_preview_uses_selected_commit_not_working_tree_and_excludes_private_paths(self):
        (self.product / "app/app.js").write_text("DIRTY_WORKTREE_MUST_NOT_PUBLISH")
        (self.product / "app/index.html").unlink()
        output = Path(self.folder.name) / "public"
        result = self.run_preview(self.sha, output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(p.name for p in output.iterdir()), set(self.original) | {"preview-manifest.json"})
        manifest = json.loads((output / "preview-manifest.json").read_text())
        self.assertEqual(manifest["source_revision"], self.sha)
        for name, data in self.original.items():
            self.assertEqual((output / name).read_bytes(), data)
            self.assertEqual(manifest["files"][name]["sha256"], hashlib.sha256(data).hexdigest())
        self.assertNotIn("MUST_NOT_PUBLISH", "".join(p.read_text() for p in output.iterdir()))

    def test_nonexistent_revision_and_committed_symlink_are_rejected(self):
        output = Path(self.folder.name) / "public"
        self.assertNotEqual(self.run_preview("f" * 40, output).returncode, 0)
        self.assertFalse(output.exists())
        target = self.product / "app/app.js"
        target.unlink()
        target.symlink_to("../bridge/private-config.json")
        self.git("add", ".")
        self.commit()
        symlink_sha = self.git("rev-parse", "HEAD").strip()
        result = self.run_preview(symlink_sha, output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Ordinary committed app file required", result.stderr)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
