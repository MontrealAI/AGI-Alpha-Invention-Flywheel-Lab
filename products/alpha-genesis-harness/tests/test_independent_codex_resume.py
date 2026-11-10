# SPDX-License-Identifier: Apache-2.0
"""Independent Codex continuation adversaries using synthetic JSON-RPC only."""
from __future__ import annotations

import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError
from bridge.chatgpt import ChatGPTPlanService
from bridge.codex import CodexService
from bridge.codex_permissions import PROFILE, verify_runtime_sandbox


class InputCapture(io.StringIO):
    def close(self):
        self.recorded = self.getvalue()
        super().close()


class SyntheticProcess:
    def __init__(self, profile=PROFILE, events=None):
        events = events if events is not None else [{"id": 0, "result": {}}, {"id": 1, "result": {"thread": {"id": "review-thread"}, "activePermissionProfile": {"id": profile}}},
                  {"id": 2, "result": {"turn": {"id": "review-turn"}}},
                  {"method": "item/agentMessage/delta", "params": {"threadId": "review-thread", "turnId": "review-turn", "delta": "Synthetic accepted terminal text"}},
                  {"method": "turn/completed", "params": {"threadId": "review-thread", "turn": {"id": "review-turn", "status": "completed"}}}]
        self.stdout = io.StringIO("\n".join(map(json.dumps, events)) + "\n")
        self.stdin = InputCapture()
        self.stopped = False
    def poll(self): return 0 if self.stopped else None
    def terminate(self): self.stopped = True
    def kill(self): self.stopped = True
    def wait(self, timeout): return 0


class IndependentCodexResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.catalog_callback = None
        owner = self
        class Catalog:
            def json(self, url, **kw):
                if owner.catalog_callback:
                    owner.catalog_callback()
                return {"models": [{"slug": name, "visibility": "list"} for name in ["fixture-model", "other-model"]]}
        self.plan = ChatGPTPlanService({"allow_plan_usage": True, "distribution": "open-source-local"},
                                      storage_path=self.root / "auth", transport=Catalog())
        with self.plan.store.locked():
            self.plan.store.write({"schema": 1, "host_id": "urn:uuid:00000000-0000-4000-8000-000000000000", "active": "review-client",
                "accounts": {"review-client": {"client_id": "review-client", "subject": "review-subject", "access_token": "synthetic-review-token",
                    "expires_at": time.time() + 3600, "scopes": ["resource.invoke", "chatgpt.tokens.use.direct"]}}})
        self.calls = []
        self.launch_after_invalidation = []
        self.authorization_invalidated = False
        self.cancel_on_launch = None
        self.thread_profile = PROFILE
        def factory(command, **kw):
            process = SyntheticProcess(profile=self.thread_profile)
            self.launch_after_invalidation.append(self.authorization_invalidated)
            self.calls.append((command, kw, process))
            if self.cancel_on_launch:
                self.service.cancel(self.cancel_on_launch)
            return process
        self.factory = factory
        self.service = self.new_service()

    def tearDown(self):
        self.service.close()
        self.plan.close()
        self.temp.cleanup()

    def new_service(self, *, writable=False, root=None):
        return CodexService({"allow_execution": True, "allow_workspace_write": writable, "executable": sys.executable},
                            plan_service=self.plan, workspace_root=root or self.root / "work", process_factory=self.factory,
                            sandbox_validator=lambda binary: None, runtime_probe=lambda *args: None)

    @staticmethod
    def request(run_id="first", resume=False, **extra):
        return {"model": "fixture-model", "prompt": "Continue the synthetic work", "run_id": run_id,
                **({"resume_run_id": "first"} if resume else {}), **extra}

    def test_reopened_service_resumes_original_thread_workspace_and_readonly_rights(self):
        first = self.service.generate(self.request())
        second = self.new_service(writable=True)
        continued = second.resume(self.request("second", True))
        self.assertEqual(continued["workspace"], first["workspace"])
        self.assertEqual(continued["thread_id"], first["thread_id"])
        self.assertEqual(self.calls[0][1]["env"]["CODEX_HOME"], self.calls[1][1]["env"]["CODEX_HOME"])
        messages = [json.loads(line) for line in self.calls[-1][2].stdin.recorded.splitlines()]
        self.assertIn("thread/resume", [m.get("method") for m in messages])
        for message in messages:
            if message.get("method") in {"thread/resume", "turn/start"}:
                self.assertEqual(message["params"]["permissions"], PROFILE)
                self.assertNotIn("sandboxPolicy", message["params"])
                self.assertNotIn("sandbox", message["params"])
        command = self.calls[-1][0]
        filesystem = next(arg for arg in command if arg.startswith(f"permissions.{PROFILE}.filesystem="))
        self.assertIn(json.dumps(continued["workspace"]) + '="read"', filesystem)
        self.assertNotIn('="write"', filesystem)
        self.assertIn('\":root\"="deny"', filesystem)
        self.assertIn(f"permissions.{PROFILE}.network.enabled=false", command)
        self.assertFalse(any(arg.startswith("sandbox_mode=") for arg in command))
        self.assertEqual(self.plan.requests_started, 2)
        second.close()

    def test_persisted_runtime_configuration_is_outside_the_agent_write_grant(self):
        self.service = self.new_service(writable=True)
        self.service.generate(self.request())
        command, launch, process = self.calls[0]
        home = Path(launch["env"]["CODEX_HOME"]).resolve()
        filesystem = next(arg for arg in command if arg.startswith(f"permissions.{PROFILE}.filesystem="))
        self.assertIn(json.dumps(launch["cwd"]) + '="write"', filesystem)
        self.assertEqual(filesystem.count('="write"'), 1)
        self.assertFalse(home.is_relative_to(Path(launch["cwd"]).resolve()), "Agent could poison trusted runtime configuration for resume")
        self.assertEqual(self.service._checkpoint("first")["codex_home"], str(home))

    def test_modified_checkpoint_is_rejected_before_new_process_or_allowance_count(self):
        self.service.generate(self.request())
        path = self.root / "work" / ".harness-checkpoints" / "first.json"
        envelope = json.loads(path.read_text())
        envelope["payload"]["sandbox"] = "workspace-write"
        envelope["payload"]["thread_id"] = "forged-thread"
        path.write_text(json.dumps(envelope))
        with self.assertRaises(BridgeError):
            self.new_service(writable=True).resume(self.request("second", True))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.plan.requests_started, 1)

    def test_original_model_and_account_bindings_are_enforced(self):
        self.service.generate(self.request())
        with self.assertRaises(BridgeError):
            self.service.resume(self.request("changed-model", True, model="other-model"))
        with self.plan.store.locked():
            state = self.plan.store.read()
            state["accounts"]["review-client"]["subject"] = "different-subject"
            self.plan.store.write(state)
        with self.assertRaises(BridgeError):
            self.service.resume(self.request("changed-account", True))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.plan.requests_started, 1)

    def test_copied_checkpoint_cannot_silently_relocate_original_workspace(self):
        self.service.generate(self.request())
        moved = self.root / "moved-work"
        shutil.copytree(self.root / "work", moved)
        with self.assertRaises(BridgeError):
            self.new_service(root=moved).resume(self.request("relocated", True))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.plan.requests_started, 1)

    def test_account_changed_during_catalog_lookup_cannot_launch_old_token(self):
        def switch():
            with self.plan.store.locked():
                state = self.plan.store.read()
                state["active"] = "different-client"
                self.plan.store.write(state)
        self.catalog_callback = switch
        with self.assertRaises(BridgeError):
            self.service.generate(self.request())
        self.assertEqual(self.calls, [])
        self.assertEqual(self.plan.requests_started, 0)

    def test_incompatible_sandbox_is_rejected_before_catalog_or_process(self):
        def reject(binary):
            raise BridgeError("CODEX_SANDBOX_UNSUPPORTED", "Synthetic incompatible sandbox", 409)
        def unexpected_catalog():
            self.fail("Sandbox rejection must happen before remote model discovery")
        self.service.sandbox_validator = reject
        self.catalog_callback = unexpected_catalog
        with self.assertRaises(BridgeError) as raised:
            self.service.generate(self.request())
        self.assertEqual(raised.exception.code, "CODEX_SANDBOX_UNSUPPORTED")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.plan.requests_started, 0)

    def test_native_sandbox_failure_prevents_credential_process_and_count(self):
        def refuse(*args):
            raise BridgeError("CODEX_SANDBOX_UNAVAILABLE", "Synthetic native sandbox failure", 409)
        self.service.runtime_probe = refuse
        with self.assertRaises(BridgeError) as raised:
            self.service.generate(self.request())
        self.assertEqual(raised.exception.code, "CODEX_SANDBOX_UNAVAILABLE")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.plan.requests_started, 0)
        self.assertFalse(self.plan._active)

    def test_unconfirmed_permission_profile_cannot_start_a_turn(self):
        for profile in [None, "unrestricted"]:
            with self.subTest(profile=profile):
                self.thread_profile = profile
                with self.assertRaises(BridgeError) as raised:
                    self.service.generate(self.request("profile-" + str(profile)))
                self.assertEqual(raised.exception.code, "CODEX_PROFILE")
                messages = [json.loads(line) for line in self.calls[-1][2].stdin.recorded.splitlines()]
                self.assertNotIn("turn/start", [m.get("method") for m in messages])
                self.assertTrue(self.calls[-1][2].stopped)

    def test_signout_during_native_probe_cannot_launch_old_credentials(self):
        self.service.runtime_probe = lambda *args: self.plan.disconnect(revoke_remote=False)
        with self.assertRaises(BridgeError):
            self.service.generate(self.request())
        self.assertEqual(self.calls, [])
        self.assertEqual(self.plan.requests_started, 0)

    def test_native_probe_uses_synthetic_token_and_loopback_provider_only(self):
        work, home = self.root / "probe-work", self.root / "probe-home"
        work.mkdir()
        home.mkdir()
        captured = {}
        checks = {"read_allowed": True, "outside_denied": True, "write_allowed": False,
                  "network_denied": True, "credential_env_hidden": True}
        def probe_factory(command, **kw):
            captured.update(command=command, **kw)
            captured["process"] = SyntheticProcess(events=[{"id": 0, "result": {}},
                {"id": 1, "result": {"data": [{"id": PROFILE, "allowed": True}]}},
                {"id": 2, "result": {"exitCode": 0, "stdout": json.dumps(checks)}}])
            return captured["process"]
        original_command = self.service._command(work, False)
        with patch.dict("os.environ", {"ACCESS_TOKEN": "synthetic-parent-token", "OPENAI_API_KEY": "synthetic-parent-api-key"}):
            result = verify_runtime_sandbox(original_command, work, home, False, probe_factory)
        self.assertEqual(result["status"], "PASS")
        base = next(a for a in captured["command"] if a.startswith("model_providers.openai_chatgpt_plan.base_url="))
        self.assertEqual(base, 'model_providers.openai_chatgpt_plan.base_url="http://127.0.0.1:9/v1"')
        self.assertNotEqual(captured["command"], original_command)
        self.assertEqual(captured["env"]["ACCESS_TOKEN"], "HARNESS_SYNTHETIC_ENV_SENTINEL")
        self.assertNotIn("OPENAI_API_KEY", captured["env"])
        sent = captured["process"].stdin.recorded
        self.assertNotIn('"turn/start"', sent)
        self.assertNotIn('"thread/start"', sent)
        self.assertEqual(list(work.iterdir()), [])
        self.assertFalse(list(self.root.glob(".harness-probe-*")))

    def test_checkpoint_is_reloaded_after_exclusive_workspace_lock(self):
        self.service.generate(self.request())
        original_lock = self.service._workspace_lock
        def predecessor_finishes(workspace_id):
            # A different process can commit between an unlocked read and lock
            # acquisition. Its recorded attempt must not disappear or replay.
            saved = self.service._checkpoint(workspace_id)
            saved["attempt_ids"].append("second")
            self.service._checkpoint(workspace_id, saved)
            return original_lock(workspace_id)
        self.service._workspace_lock = predecessor_finishes
        with self.assertRaises(BridgeError):
            self.service.resume(self.request("second", True))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.plan.requests_started, 1)

    def test_account_invalidation_cannot_finish_before_a_new_process_launch(self):
        underlying = self.plan._lock
        owner = self
        class ReleaseSchedule:
            armed = True
            def __enter__(self):
                underlying.acquire()
                return self
            def __exit__(self, *exc):
                underlying.release()
                if self.armed and owner.plan.requests_started:
                    self.armed = False
                    owner.plan.disconnect(revoke_remote=False)
                    owner.authorization_invalidated = True
        self.plan._lock = ReleaseSchedule()
        try:
            self.service.generate(self.request())
        except BridgeError:
            pass  # Cancellation after a serialized spawn is acceptable.
        self.assertFalse(any(self.launch_after_invalidation), "Old authorization was passed to a child after sign-out completed")

    def test_cancelled_turn_keeps_an_interrupted_checkpoint_for_explicit_resume(self):
        def cancel_after_turn_starts(event):
            if event.get("type") == "progress":
                self.service.cancel("first")
        with self.assertRaises(BridgeError):
            self.service.generate(self.request(), on_event=cancel_after_turn_starts)
        checkpoint = self.service._checkpoint("first")
        self.assertEqual(checkpoint["status"], "interrupted")
        self.assertEqual(checkpoint["thread_id"], "review-thread")
        result = self.new_service().resume(self.request("recovery", True))
        self.assertEqual(result["thread_id"], "review-thread")
        self.assertEqual(self.service._checkpoint("first")["status"], "completed")
        self.assertEqual(self.plan.requests_started, 2)

    def test_cancellation_before_handshake_cannot_start_a_turn(self):
        self.cancel_on_launch = "first"
        with self.assertRaises(BridgeError):
            self.service.generate(self.request())
        messages = [json.loads(line) for line in self.calls[0][2].stdin.recorded.splitlines()]
        self.assertNotIn("thread/start", [m.get("method") for m in messages])
        self.assertNotIn("turn/start", [m.get("method") for m in messages])
        self.assertTrue(self.calls[0][2].stopped)
        self.assertEqual(self.plan.requests_started, 1)


if __name__ == "__main__":
    unittest.main()
