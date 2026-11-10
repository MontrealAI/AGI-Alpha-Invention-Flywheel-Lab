# SPDX-License-Identifier: Apache-2.0
"""Platform qualifier boundary tests. Fixtures are not native-platform qualification."""
from __future__ import annotations

from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT / "scripts"))
import qualify_platform as q
from test_qualification import archive_fixture, SOURCE


class NativeQualificationBoundaryTests(unittest.TestCase):
    def launchers(self, root):
        product = Path(root) / "product with spaces"
        product.mkdir()
        for name in ("Launch-HARNESS.cmd", "Launch-HARNESS.command", "Launch-HARNESS.sh"):
            (product / name).write_text("native launcher fixture\n")
        return product

    def test_native_launchers_use_exact_files_and_explicit_private_workspace(self):
        with tempfile.TemporaryDirectory() as root:
            product = self.launchers(root)
            workspace = Path(root) / "private workspace"
            mac = q.native_launcher(product, workspace, 8765, "Darwin")
            self.assertEqual(mac[:2], ["/bin/sh", str(product / "Launch-HARNESS.command")])
            self.assertEqual(mac[-2:], ["--workspace", str(workspace)])
            windows = q.native_launcher(product, workspace, 8765, "Windows")
            self.assertEqual(windows[1:4], ["/d", "/s", "/c"])
            self.assertTrue(windows[-1].startswith("Launch-HARNESS.cmd --port 8765 --no-browser"))
            linux = q.native_launcher(product, workspace, 8765, "Linux")
            self.assertEqual(linux[1], str(product / "Launch-HARNESS.sh"))

    def test_windows_shell_metacharacters_are_refused_before_launch(self):
        with tempfile.TemporaryDirectory() as root:
            product = self.launchers(root)
            for character in ('%', '!', '&', '|', '<', '>', '^', '"', '\n'):
                with self.subTest(character=character), self.assertRaisesRegex(ValueError, "shell-safe"):
                    q.native_launcher(product, Path(root) / ("unsafe" + character + "path"), 8765, "Windows")

    def test_missing_or_unsupported_launcher_never_falls_back_to_direct_python(self):
        with tempfile.TemporaryDirectory() as root:
            product = self.launchers(root)
            (product / "Launch-HARNESS.command").unlink()
            with self.assertRaisesRegex(ValueError, "lacks"):
                q.native_launcher(product, Path(root), 8765, "Darwin")
            with self.assertRaisesRegex(ValueError, "No native"):
                q.native_launcher(product, Path(root), 8765, "Unsupported")

    def test_platform_subprocesses_do_not_inherit_credentials(self):
        secrets = {name: "not-a-real-secret" for name in ("GH_TOKEN", "GITHUB_TOKEN", "HARNESS_OPENAI_API_KEY", "AWS_SECRET_ACCESS_KEY", "CHATGPT_ACCESS_TOKEN")}
        with patch.dict(os.environ, {**secrets, "Path": "native-path", "SYSTEMROOT": "native-system"}, clear=True):
            environment = q.private_environment()
        self.assertTrue(set(secrets).isdisjoint(environment))
        self.assertEqual(environment["Path"], "native-path")
        self.assertEqual(environment["SYSTEMROOT"], "native-system")
        self.assertEqual(environment["PYTHONDONTWRITEBYTECODE"], "1")

    def test_byte_mismatch_prevents_all_launches(self):
        with tempfile.TemporaryDirectory() as root:
            archive = Path(root) / "bad.zip"
            archive.write_bytes(b"unexpected archive")
            with patch.object(q.subprocess, "Popen") as start:
                with self.assertRaisesRegex(ValueError, "digest"):
                    q.qualify(archive, "a" * 64, SOURCE, Path(root) / "result", Path(root), Path(root))
                start.assert_not_called()

    def test_authentication_failure_retains_http_code_without_response_payload(self):
        process = Mock()
        process.poll.return_value = None
        responses = [(200, {"token": "private-token-must-not-be-reported"}), (403, {}),
                     (400, {"error": {"code": "LOCAL_SETUP_INPUT", "message": "do not retain arbitrary response"}})]
        with patch.object(q, "request", side_effect=responses):
            with self.assertRaisesRegex(ValueError, "HTTP 400; LOCAL_SETUP_INPUT") as caught:
                q.authenticate(8765, process)
        self.assertNotIn("private-token", str(caught.exception))
        self.assertNotIn("arbitrary response", str(caught.exception))

    def test_zero_exit_does_not_convert_wrong_platform_receipt_to_pass(self):
        self._wrong_receipt_case()

    def test_generated_temp_directory_is_canonical_before_workspace_validation(self):
        self._wrong_receipt_case(symbolic_parent=True)

    def _wrong_receipt_case(self, symbolic_parent=False):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            package = archive_fixture(extra_files={
                "Launch-HARNESS.sh": b"echo fixture\n", "Launch-HARNESS.cmd": b"echo fixture\n", "Launch-HARNESS.command": b"echo fixture\n",
                "tests/visual/package.json": b'{"dependencies":{"playwright-core":"1.62.1"}}',
                "evidence/UI_BROWSER_REPLAY.cjs": b"// inert fixture\n",
            })
            archive = root / "archive.zip"
            archive.write_bytes(package)
            modules = root / "node_modules"
            (modules / "playwright-core").mkdir(parents=True)
            (modules / "playwright-core/package.json").write_text('{"version":"1.62.1"}')
            browser = root / "browser"
            browser.write_text("inert executable fixture")
            output = root / "result"
            temporary_override = nullcontext()
            if symbolic_parent:
                (root / "real-temporary").mkdir()
                alias = root / "temporary-alias"
                try:
                    alias.symlink_to(root / "real-temporary", target_is_directory=True)
                except OSError:
                    self.skipTest("This host cannot create the symlink-parent fixture")
                temporary_override = patch.object(q.tempfile, "TemporaryDirectory", return_value=nullcontext(str(alias)))
            original_launcher = q.native_launcher
            def checked_launcher(product, workspace, port):
                self.assertFalse(any(item.is_symlink() for item in [workspace, *workspace.parents]),
                                 "Generated private workspace must reach the unchanged product guard canonically")
                return original_launcher(product, workspace, port)
            def wrong_receipt(command, **kwargs):
                (output / "browser").mkdir()
                (output / "browser/BROWSER-VERIFICATION.json").write_text(json.dumps({"status": "PASS", "platform": "invented", "source_revision": SOURCE,
                    "server_mode": "external-native-launcher", "exports": [{"file": "fixture.json"}]}))
                return subprocess.CompletedProcess(command, 0, "fixture", "")
            with temporary_override, patch.object(q, "native_launcher", side_effect=checked_launcher), patch.object(q.platform, "platform", return_value="platform-fixture"), patch.object(q.platform, "machine", return_value="fixture"), \
                 patch.object(q, "free_port", return_value=8765), patch.object(q, "authenticate", return_value={"fixture": True}), \
                 patch.object(q, "launcher_interpreter", return_value={"fixture": True}), patch.object(q, "stop_owned_process"), \
                 patch.object(q.subprocess, "Popen", return_value=Mock()), patch.object(q.subprocess, "run", side_effect=wrong_receipt):
                with self.assertRaisesRegex(ValueError, "exact platform"):
                    q.qualify(archive, hashlib.sha256(package).hexdigest(), SOURCE, output, modules, browser, "node")
            receipt = json.loads((output / "PLATFORM-QUALIFICATION.json").read_text())
            self.assertEqual(receipt["status"], "FAIL")
            self.assertEqual(receipt["browser_returncode"], 0)


if __name__ == "__main__":
    unittest.main()
