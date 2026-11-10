# SPDX-License-Identifier: Apache-2.0
"""Codex protocol fixtures; no installed CLI invocation or authenticated inference."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError
from bridge.chatgpt import ChatGPTPlanService
from bridge.codex import CodexService
from bridge.codex_permissions import PROFILE
from test_chatgpt import FakeTransport, seed


class CapturedInput(io.StringIO):
    def close(self):
        self.saved = self.getvalue()
        super().close()


class ProcessFixture:
    def __init__(self, messages):
        self.stdin = CapturedInput()
        self.stdout = io.StringIO("\n".join(json.dumps(x) for x in messages) + "\n")
        self.done = False

    def poll(self): return 0 if self.done else None
    def terminate(self): self.done = True
    def kill(self): self.done = True
    def wait(self, timeout): return 0


class CodexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.transport = FakeTransport()
        self.plan = ChatGPTPlanService({"allow_plan_usage": True, "distribution": "open-source-local"}, Path(self.temp.name) / "auth", self.transport)
        seed(self.plan)
        self.messages = [{"id": 0, "result": {}}, {"id": 1, "result": {"thread": {"id": "thread-one"}, "activePermissionProfile": {"id": PROFILE}}},
                         {"id": 2, "result": {"turn": {"id": "turn-one"}}},
                         {"method": "item/agentMessage/delta", "params": {"threadId": "thread-one", "turnId": "turn-one", "delta": "Constructed useful output"}},
                         {"method": "turn/completed", "params": {"threadId": "thread-one", "turn": {"id": "turn-one", "status": "completed"}}}]
        self.calls = []
        def factory(command, **kwargs):
            self.calls.append((command, kwargs))
            Path(kwargs["cwd"], "result.txt").write_text("Useful constructed output\n")
            self.process = ProcessFixture(self.messages)
            return self.process
        self.service = CodexService({"allow_execution": True, "allow_workspace_write": True, "executable": sys.executable},
                                    self.plan, Path(self.temp.name) / "work", factory, sandbox_validator=lambda _: None,
                                    runtime_probe=lambda *args: None)

    def tearDown(self):
        self.service.close()
        self.plan.close()
        self.temp.cleanup()

    def request(self):
        return {"model": "account-model", "prompt": "Construct a text output", "run_id": "codex-run"}

    def test_explicit_consent_and_shared_plan_gate(self):
        self.service.config["allow_execution"] = False
        with self.assertRaises(BridgeError): self.service.generate(self.request())
        self.assertEqual(self.calls, [])
        self.service.config["allow_execution"] = True
        self.plan.config["distribution"] = "commercial"
        with self.assertRaises(BridgeError): self.service.generate(self.request())
        self.assertEqual(self.calls, [])

    def test_handshake_sandbox_credentials_and_constructed_artifact(self):
        result = self.service.generate(self.request())
        command, options = self.calls[0]
        self.assertEqual(command[1:4], ["app-server", "--listen", "stdio://"])
        self.assertNotIn("synthetic-access-credential", " ".join(command))
        self.assertEqual(options["env"]["ACCESS_TOKEN"], "synthetic-access-credential")
        self.assertNotIn("OPENAI_API_KEY", options["env"])
        self.assertFalse(Path(options["env"]["CODEX_HOME"]).is_relative_to(Path(options["cwd"])))
        sent = [json.loads(line) for line in self.process.stdin.saved.splitlines()]
        self.assertEqual([row["method"] for row in sent], ["initialize", "initialized", "thread/start", "turn/start"])
        self.assertNotIn("sandboxPolicy", sent[-1]["params"])
        self.assertEqual(sent[-1]["params"]["permissions"], PROFILE)
        self.assertIn('":root"="deny"', " ".join(command))
        self.assertIn(".network.enabled=false", " ".join(command))
        self.assertEqual(sent[-1]["params"]["approvalPolicy"], "never")
        self.assertEqual(result["artifacts"][0]["path"], "result.txt")
        self.assertIsNone(result["cost"]["amount"])
        self.assertTrue(self.process.done)

    def test_wrong_turn_and_incomplete_cannot_pass(self):
        self.messages[-1]["params"]["turn"]["id"] = "other-turn"
        with self.assertRaises(BridgeError): self.service.generate(self.request())
        self.assertFalse(self.service._active)
        self.assertFalse(self.plan._active)

    def test_approval_is_declined(self):
        self.messages.insert(3, {"id": 33, "method": "item/commandExecution/requestApproval", "params": {}})
        self.service.generate(self.request())
        sent = [json.loads(line) for line in self.process.stdin.saved.splitlines()]
        self.assertEqual([row for row in sent if row.get("id") == 33][0]["result"], {"decision": "decline"})

    def test_symlink_artifact_not_followed(self):
        directory = Path(self.temp.name) / "artifact-work"
        directory.mkdir()
        secret = Path(self.temp.name) / "outside.txt"
        secret.write_text("outside-private-data")
        (directory / "link.txt").symlink_to(secret)
        self.assertIsNone(self.service._read_artifact(directory, Path("link.txt")))

    def test_resume_after_restart_preserves_thread_workspace_and_policy(self):
        self.service.config["allow_workspace_write"] = False
        first = self.service.generate(self.request())
        restarted = CodexService({**self.service.config, "allow_workspace_write": True}, self.plan,
                                  self.service.root, self.service.process_factory, sandbox_validator=lambda _: None,
                                  runtime_probe=lambda *args: None)
        result = restarted.resume({**self.request(), "run_id": "resume-one", "resume_run_id": "codex-run"})
        sent = [json.loads(line) for line in self.process.stdin.saved.splitlines()]
        self.assertEqual(sent[2]["method"], "thread/resume")
        self.assertEqual(sent[2]["params"]["threadId"], "thread-one")
        self.assertEqual(sent[3]["params"]["permissions"], PROFILE)
        command = " ".join(self.calls[-1][0])
        self.assertIn(json.dumps(result["workspace"]) + '="read"', command)
        self.assertNotIn(json.dumps(result["workspace"]) + '="write"', command)
        self.assertEqual(result["workspace"], first["workspace"])
        self.assertEqual(result["resume_run_id"], "codex-run")
        another = CodexService(restarted.config, self.plan, self.service.root, self.service.process_factory, sandbox_validator=lambda _: None,
                               runtime_probe=lambda *args: None)
        with self.assertRaises(BridgeError):
            another.resume({**self.request(), "run_id": "resume-one", "resume_run_id": "codex-run"})

    def test_resume_tampering_account_and_policy_changes_refused(self):
        self.service.generate(self.request())
        started = self.plan.requests_started
        seed(self.plan, "other-account")
        with self.assertRaises(BridgeError):
            self.service.resume({**self.request(), "run_id": "wrong-account", "resume_run_id": "codex-run"})
        seed(self.plan)
        self.service.config["allow_workspace_write"] = False
        with self.assertRaises(BridgeError):
            self.service.resume({**self.request(), "run_id": "wrong-policy", "resume_run_id": "codex-run"})
        self.service.config["allow_workspace_write"] = True
        path = self.service.root / ".harness-checkpoints" / "codex-run.json"
        envelope = json.loads(path.read_text())
        envelope["payload"]["thread_id"] = "attacker-thread"
        path.write_text(json.dumps(envelope))
        with self.assertRaises(BridgeError):
            self.service.resume({**self.request(), "run_id": "tampered", "resume_run_id": "codex-run"})
        self.assertEqual(self.plan.requests_started, started)

    def test_interrupted_turn_checkpoint_can_resume(self):
        self.messages[-1]["params"]["turn"]["status"] = "interrupted"
        with self.assertRaises(BridgeError): self.service.generate(self.request())
        self.assertEqual(self.service._checkpoint("codex-run")["status"], "interrupted")
        self.messages[-1]["params"]["turn"]["status"] = "completed"
        result = self.service.resume({**self.request(), "run_id": "after-interruption", "resume_run_id": "codex-run"})
        self.assertEqual(result["thread_id"], "thread-one")

    def test_account_change_during_catalog_refuses_process_launch(self):
        seed(self.plan, "other-account")
        seed(self.plan)
        original = self.transport.json
        def switch(url, **kwargs):
            if url.endswith("/models"):
                self.plan.select_account("other-account")
            return original(url, **kwargs)
        self.transport.json = switch
        with self.assertRaises(BridgeError): self.service.generate(self.request())
        self.assertEqual(self.calls, [])
        self.assertEqual(self.plan.requests_started, 0)


if __name__ == "__main__":
    unittest.main()
