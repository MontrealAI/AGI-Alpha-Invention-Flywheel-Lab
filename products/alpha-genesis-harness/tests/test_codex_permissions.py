# SPDX-License-Identifier: Apache-2.0
"""Permission-profile protocol and negative probe contracts; no real model calls."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError
from bridge.codex_permissions import PROFILE, permission_overrides, verify_profile_protocol, verify_runtime_sandbox
from test_codex import ProcessFixture


class PermissionTests(unittest.TestCase):
    def test_named_profile_is_deny_default_with_exact_root(self):
        values = permission_overrides("/tmp/synthetic-work", True, sys.executable)
        rendered = " ".join(values)
        self.assertIn('":root"="deny"', rendered)
        self.assertIn('":minimal"="read"', rendered)
        self.assertIn('"/tmp/synthetic-work"="write"', rendered)
        self.assertIn(".network.enabled=false", rendered)
        self.assertNotIn("sandbox_mode", rendered)

    def test_schema_export_opts_into_experimental_profile_contract(self):
        calls = []
        class Result: returncode = 0
        def run(args, **kwargs):
            calls.append((args, kwargs))
            directory = Path(args[-1], "v2")
            directory.mkdir()
            for name, field in (("ThreadStartParams", "permissions"), ("ThreadResumeParams", "permissions"),
                                ("TurnStartParams", "permissions"), ("CommandExecParams", "permissionProfile"),
                                ("ThreadStartResponse", "activePermissionProfile")):
                (directory / (name + ".json")).write_text(json.dumps({"properties": {field: {}}}))
            return Result()
        with patch("bridge.codex_permissions.subprocess.run", run):
            verify_profile_protocol(sys.executable)
        self.assertIn("--experimental", calls[0][0])
        self.assertNotIn("ACCESS_TOKEN", calls[0][1]["env"])

    def probe(self, change=None, exit_code=0):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        work, home = root / "work", root / "runtime"
        work.mkdir(); home.mkdir()
        checks = {"read_allowed": True, "outside_denied": True, "write_allowed": True,
                  "network_denied": True, "credential_env_hidden": True}
        if change: checks.update(change)
        captured = {}
        def factory(command, **kwargs):
            captured.update(kwargs)
            marker = next(work.glob(".harness-probe-*"))
            marker.with_name(marker.name + "-write").write_text("HARNESS_WRITE")
            process = ProcessFixture([{"id": 0, "result": {}},
                          {"id": 1, "result": {"data": [{"id": PROFILE, "allowed": True}]}},
                          {"id": 2, "result": {"exitCode": exit_code, "stdout": json.dumps(checks)}}])
            captured["process"] = process
            return process
        result = verify_runtime_sandbox([sys.executable], work, home, True, factory)
        self.assertEqual(list(work.iterdir()), [])
        sent = [json.loads(line) for line in captured["process"].stdin.saved.splitlines()]
        self.assertEqual([row["method"] for row in sent], ["initialize", "initialized", "permissionProfile/list", "command/exec"])
        self.assertEqual(sent[-1]["params"]["permissionProfile"], PROFILE)
        self.assertEqual(captured["env"]["ACCESS_TOKEN"], "HARNESS_SYNTHETIC_ENV_SENTINEL")
        self.assertNotIn("turn/start", captured["process"].stdin.saved)
        return result

    def test_all_boundaries_must_pass_before_credential_execution(self):
        self.assertEqual(self.probe()["status"], "PASS")
        for field in ("read_allowed", "outside_denied", "network_denied", "credential_env_hidden", "write_allowed"):
            with self.subTest(field=field), self.assertRaises(BridgeError):
                self.probe({field: False})

    def test_native_sandbox_failure_is_not_a_permission_bypass(self):
        with self.assertRaises(BridgeError) as error:
            self.probe(exit_code=1)
        self.assertEqual(error.exception.code, "CODEX_SANDBOX_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
