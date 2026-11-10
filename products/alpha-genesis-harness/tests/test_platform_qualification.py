# SPDX-License-Identifier: Apache-2.0
"""Platform qualifier boundary tests. Fixtures are not native-platform qualification."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock
from contextlib import nullcontext

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

    def test_zero_exit_does_not_convert_wrong_platform_receipt_to_pass(self):
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
            def wrong_receipt(command, **kwargs):
                if '--help' in command:
                    return subprocess.CompletedProcess(command,0,'usage: fixture --workspace','')
                if '--test' in command:
                    return subprocess.CompletedProcess(command,0,'fixture','')
                (output / "BROWSER-VERIFICATION.json").write_text(json.dumps({"status": "PASS", "platform": "invented", "source_revision": SOURCE,
                    "server_mode": "external-native-launcher", "exports": [{"file": "fixture.json"}]}))
                return subprocess.CompletedProcess(command, 0, "fixture", "")
            with patch.object(q.platform, "platform", return_value="platform-fixture"), patch.object(q.platform, "machine", return_value="fixture"), \
                 patch.object(q, "free_port", return_value=8765), patch.object(q, "authenticate", return_value={"fixture": True}), \
                 patch.object(q, "launcher_interpreter", return_value={"fixture": True}), patch.object(q, "stop_owned_process"), \
                 patch.object(q.subprocess, "Popen", return_value=Mock()), patch.object(q.subprocess, "run", side_effect=wrong_receipt):
                with self.assertRaisesRegex(ValueError, "exact platform"):
                    q.qualify(archive, hashlib.sha256(package).hexdigest(), SOURCE, output, modules, browser, "node")
            receipt = json.loads((output / ("PLATFORM-"+q.platform.system()+"-VERIFICATION.json")).read_text())
            self.assertEqual(receipt["status"], "FAIL")
            self.assertEqual(receipt["browser_returncode"], 0)

    def test_authentication_records_authorization_outcomes_without_retaining_token(self):
        token='synthetic-local-session-token-123456789'
        with patch.object(q,'request',side_effect=[(200,{'token':token}),(403,{'error':'denied'}),(200,{'providers':[], 'workflow_engine_available':True})]) as requests:
            result=q.authenticate(8765,Mock(poll=Mock(return_value=None)))
        self.assertEqual(result['authenticated_status'],200)
        self.assertEqual(result['unauthenticated_status'],403)
        self.assertNotIn(token,json.dumps(result))
        self.assertEqual(requests.call_args_list[-1].args[2],{'X-Harness-Token':token})
        with patch.object(q,'request',side_effect=[(200,{'token':token}),(200,{})]):
            with self.assertRaisesRegex(ValueError,'not refused'):
                q.authenticate(8765,Mock(poll=Mock(return_value=None)))

    def native_run_fixture(self, cleanup_failure=None):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); actual=root/'actual';actual.mkdir(); alias=root/'alias';alias.symlink_to(actual,target_is_directory=True)
            package=archive_fixture(extra_files={
                'Launch-HARNESS.sh':b'fixture', 'Launch-HARNESS.cmd':b'fixture','Launch-HARNESS.command':b'fixture',
                'tests/visual/package.json':b'{"dependencies":{"playwright-core":"1.62.1"}}',
                'evidence/UI_BROWSER_REPLAY.cjs':b'// fixture'})
            archive=root/'archive.zip';archive.write_bytes(package)
            modules=root/'node_modules';(modules/'playwright-core').mkdir(parents=True)
            (modules/'playwright-core/package.json').write_text('{"version":"1.62.1"}')
            browser=root/'chromium';browser.write_text('fixture')
            output=root/'result'; export=b'{"experiments":[{"id":"synthetic"}]}'
            report={'status':'PASS','platform':'linux','source_revision':SOURCE,'server_mode':'external-native-launcher',
                    'errors':[],'screenshots':['HARNESS-fixture.png'],
                    'exports':[{'file':'GENESIS-NEXT-browser-export.json','bytes':len(export),'sha256':hashlib.sha256(export).hexdigest()}]}
            def execute(command,**kwargs):
                self.assertTrue(set(('GH_TOKEN','HARNESS_OPENAI_API_KEY')).isdisjoint(kwargs['env']))
                if '--help' in command:return subprocess.CompletedProcess(command,0,'usage: fixture --workspace','')
                if '--test' in command:return subprocess.CompletedProcess(command,0,'# tests 1','')
                self.assertEqual(kwargs['env']['HARNESS_BASE_URL'],'http://127.0.0.1:8765')
                (output/'BROWSER-VERIFICATION.json').write_text(json.dumps(report))
                (output/'HARNESS-fixture.png').write_bytes(b'\x89PNG\r\n\x1a\nfixture')
                (output/'GENESIS-NEXT-browser-export.json').write_bytes(export)
                return subprocess.CompletedProcess(command,0,'{}','')
            with patch.object(q.platform,'system',return_value='Linux'), patch.object(q.platform,'platform',return_value='Linux-synthetic'), patch.object(q.tempfile,'TemporaryDirectory',return_value=nullcontext(str(alias))), \
                 patch.object(q,'free_port',return_value=8765), patch.object(q,'authenticate',return_value={'bootstrap':'PASS','unauthenticated_status':403,'authenticated_status':200}), \
                 patch.object(q,'launcher_interpreter',return_value={'version':'3.12','executable':'synthetic'}), patch.object(q,'stop_owned_process') as stop, \
                 patch.object(q.subprocess,'Popen',return_value=Mock()) as start, patch.object(q.subprocess,'run',side_effect=execute):
                if cleanup_failure:
                    failure=RuntimeError('synthetic cleanup failed')
                    stop.side_effect=[failure,None] if cleanup_failure=='first' else [None,failure]
                    with self.assertRaisesRegex(RuntimeError,'synthetic cleanup failed'):
                        q.qualify(archive,hashlib.sha256(package).hexdigest(),SOURCE,output,modules,browser,'node')
                    receipt=json.loads((output/'PLATFORM-Linux-VERIFICATION.json').read_text())
                    self.assertEqual(receipt['status'],'FAIL')
                    self.assertEqual(receipt['error'],'synthetic cleanup failed')
                    self.assertEqual(len(receipt['operations']),3)
                    return
                receipt=q.qualify(archive,hashlib.sha256(package).hexdigest(),SOURCE,output,modules,browser,'node')
            self.assertEqual(receipt['status'],'PASS');self.assertEqual(len(receipt['operations']),3)
            self.assertEqual(receipt['operations'][0]['command'][:2],['node','--test'])
            self.assertIn('--help',receipt['operations'][1]['command'])
            self.assertEqual(receipt['operations'][2]['command'],['node','evidence/UI_BROWSER_REPLAY.cjs'])
            self.assertIn(str(actual/'private-workspace'),start.call_args.args[0])
            self.assertEqual((output/'Linux-GENESIS-NEXT-browser-export.json').read_bytes(),export)
            self.assertTrue((output/'Linux-HARNESS-fixture.png').is_file())
            self.assertTrue((output/'PLATFORM-Linux-VERIFICATION.json').is_file())
            self.assertFalse((output/'BROWSER-VERIFICATION.json').exists())
            self.assertEqual(receipt['browser_report'],report)

    def test_native_run_preserves_core_checks_resolves_temp_root_and_flattens_exports(self):
        self.native_run_fixture()

    def test_owned_process_cleanup_failure_never_emits_platform_pass(self):
        self.native_run_fixture('first')

    def test_final_cleanup_failure_never_emits_platform_pass(self):
        self.native_run_fixture('final')

    def test_browser_export_digest_mismatch_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'HARNESS-test.png').write_bytes(b'\x89PNG\r\n\x1a\nfixture');(root/'export.json').write_text('{}')
            report={'screenshots':['HARNESS-test.png'],'exports':[{'file':'export.json','bytes':2,'sha256':'0'*64}]}
            with self.assertRaisesRegex(ValueError,'hash or size'):
                q.validate_browser_files(report,root)


if __name__ == "__main__":
    unittest.main()
