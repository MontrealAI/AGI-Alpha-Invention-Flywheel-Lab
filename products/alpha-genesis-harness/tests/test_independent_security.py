# SPDX-License-Identifier: Apache-2.0
"""Adversarial tests authored separately from the integration implementations.

All providers and credentials used here are synthetic. No live inference occurs.
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import json
import tempfile
import time
import threading
import http.client
import io
import zipfile
import subprocess
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.instruments import evaluate
from bridge.adapters import BridgeError, Runtime
from bridge.streaming import StreamAccumulator
from bridge.chatgpt import ChatGPTPlanService
from bridge.workflows import WorkflowService, digest
from bridge.server import HarnessServer
from bridge.services import AccessRuntime


def instrument(expression, inputs=()):
    return {"name": "Independent contract probe", "inputs": list(inputs), "outputs": {"result": expression}}


class IndependentInstrumentBoundaryTests(unittest.TestCase):
    def test_undeclared_input_root_cannot_be_read(self):
        with self.assertRaises(ValueError):
            evaluate(instrument({"field": "private.extra"}, ["public"]),
                     {"public": 1, "private": {"extra": "not in the input contract"}})

    def test_declared_nested_input_remains_usable(self):
        result = evaluate(instrument({"field": "public.reading"}, ["public"]), {"public": {"reading": 23}})
        self.assertEqual(result["output"], {"result": 23})

    def test_unsafe_integer_valued_float_cannot_bypass_portable_range(self):
        for value in [9007199254740992.0, -9007199254740992.0, 1e50]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                evaluate(instrument(value), {})

    def test_intermediate_overflow_cannot_be_hidden_by_cancellation(self):
        for op, args in [("add", [9007199254740991, 2, -2]), ("mul", [9007199254740991, 2, 0])]:
            with self.subTest(op=op), self.assertRaises(ValueError):
                evaluate(instrument({"op": op, "args": args}), {})

    def test_json_numeric_equality_does_not_depend_on_python_decoder_type(self):
        for left, right, expected in [(1, 1.0, True), (0.0, 0, True), (1, True, False), ("1", 1, False)]:
            with self.subTest(left=left, right=right):
                result = evaluate(instrument({"op": "eq", "args": [left, right]}), {})
                self.assertIs(result["output"]["result"], expected)

    def test_unsupported_program_and_missing_input_fail_closed(self):
        for spec, values in [(instrument({"op": "exec", "args": ["print('not executed')"]}), {}),
                             (instrument({"field": "x"}, ["x"]), {})]:
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                evaluate(spec, values)

    def test_declared_operation_budget_stops_actual_evaluation(self):
        with self.assertRaises(ValueError):
            evaluate(instrument({"op": "add", "args": [1, 2, 3, 4]}), {}, max_operations=2)


class IndependentProviderBoundaryTests(unittest.TestCase):
    def configuration(self, *, budget=1, secret=False):
        return {"session_budget_usd": budget, "providers": {"local": {
            "kind": "openai", "base_url": "http://127.0.0.1:2",
            "key_env": "HARNESS_INDEPENDENT_FIXTURE_KEY" if secret else "",
            "models": {"fixture": {"input_per_million": 10, "output_per_million": 20,
                                     "max_output_tokens": 100, "streaming": True, "tool_calling": True}}}}}

    def request(self, **more):
        return dict(provider="local", model="fixture", prompt="hello", run_id="independent", max_output_tokens=10, **more)

    def response(self, text="hello"):
        return {"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 2, "completion_tokens": 3}}

    def test_a_known_response_is_not_double_charged_when_final_observer_fails(self):
        def streamer(*_, **kw):
            kw["on_text"]("hello")
            return self.response()
        def broken_observer(_):
            raise RuntimeError("Synthetic display failure")
        with patch.dict("os.environ", {"HARNESS_INDEPENDENT_FIXTURE_KEY": "synthetic-tail-key-longer-than-five"}):
            runtime = Runtime(self.configuration(secret=True), streamer=streamer)
            try:
                runtime.generate(self.request(stream=True), on_event=broken_observer)
            except BridgeError:
                pass
        self.assertEqual(runtime.budget.view()["committed"], 0.00008)
        self.assertEqual(runtime.budget.view()["reserved"], 0)

    def test_split_credential_is_not_emitted_in_progress_or_result(self):
        key = "synthetic-secret-tail-12345"
        events = []
        def streamer(*_, **kw):
            for char in "prefix " + key + " suffix":
                kw["on_text"](char)
            return self.response("prefix " + key + " suffix")
        with patch.dict("os.environ", {"HARNESS_INDEPENDENT_FIXTURE_KEY": key}):
            runtime = Runtime(self.configuration(secret=True), streamer=streamer)
            result = runtime.generate(self.request(stream=True), on_event=events.append)
        self.assertNotIn(key, "".join(e["text"] for e in events))
        self.assertNotIn(key, json.dumps(result))
        self.assertIn("[credential redacted]", "".join(e["text"] for e in events))

    def test_transmitted_tool_schema_is_part_of_the_pre_dispatch_guard(self):
        tools = [{"name": "safe", "description": "x" * 10000,
                  "parameters": {"type": "object", "properties": {}}}]
        runtime = Runtime(self.configuration(budget=0.05), sender=lambda *a, **k: self.fail("Must not dispatch underfunded schema"))
        with self.assertRaises(BridgeError):
            runtime.generate(self.request(tools=tools))
        self.assertEqual(runtime.budget.view()["committed"], 0)

    def test_unsolicited_function_is_rejected_without_execution(self):
        value = self.response()
        value["choices"][0]["message"]["tool_calls"] = [{"id": "one", "function": {"name": "run_shell", "arguments": "{}"}}]
        runtime = Runtime(self.configuration(), sender=lambda *a, **k: value)
        with self.assertRaises(BridgeError) as failure:
            runtime.generate(self.request())
        self.assertEqual(failure.exception.code, "TOOL_REFUSED")
        self.assertGreater(runtime.budget.view()["committed"], 0)

    def test_partial_stream_cannot_be_promoted_to_a_completed_response(self):
        for kind, event in [
            ("openai", {"choices": [{"delta": {"content": "partial"}}]}),
            ("responses", {"type": "response.output_text.delta", "delta": "partial"}),
            ("gemini", {"candidates": [{"content": {"parts": [{"text": "partial"}]}}]}),
            ("ollama", {"message": {"content": "partial"}, "done": False}),
        ]:
            with self.subTest(kind=kind):
                accumulator = StreamAccumulator(kind)
                accumulator.feed(event)
                with self.assertRaises(BridgeError):
                    accumulator.finish()

    def test_facade_local_only_remains_authoritative_with_an_injected_runtime(self):
        config = self.configuration(secret=True)
        config["allow_paid_requests"] = True
        config["providers"]["local"]["base_url"] = "https://provider.invalid/v1"
        calls = []
        def sender(*a, **kw):
            calls.append(1)
            return self.response() if kw.get("body") else {"data": [{"id": "fixture"}]}
        with patch.dict("os.environ", {"HARNESS_INDEPENDENT_FIXTURE_KEY": "synthetic-facade-secret"}):
            runtime = AccessRuntime(Runtime(config, sender=sender), {"local_only": True})
            self.assertTrue(runtime.status()["local_only"])
            for operation in [lambda: runtime.generate(self.request()), lambda: runtime.discover("local")]:
                with self.assertRaises(BridgeError):
                    operation()
        self.assertEqual(calls, [])

    def test_explicit_local_only_rejects_remote_configuration(self):
        config = self.configuration()
        config["local_only"] = True
        config["allow_paid_requests"] = True
        config["providers"]["local"]["base_url"] = "https://provider.invalid/v1"
        with self.assertRaises(BridgeError):
            Runtime(config, sender=lambda *a, **k: self.fail("Remote sender must not run"))


class IndependentChatGPTBoundaryTests(unittest.TestCase):
    def service(self, folder, transport=None, **config):
        return ChatGPTPlanService(dict(allow_plan_usage=True, distribution="open-source-local", **config),
                                  storage_path=Path(folder) / "auth", transport=transport,
                                  browser_open=lambda _: self.fail("No live sign-in in independent tests"))

    @staticmethod
    def seed(service):
        with service.store.locked():
            service.store.write({"schema": 1, "host_id": "urn:uuid:00000000-0000-4000-8000-000000000000", "active": "fixture-client",
                "accounts": {"fixture-client": {"client_id": "fixture-client", "subject": "fixture-subject",
                    "access_token": "synthetic-access", "refresh_token": "synthetic-refresh", "id_token": "synthetic-identity",
                    "expires_at": time.time() + 3600, "scopes": ["resource.invoke", "chatgpt.tokens.use.direct"]}}})

    def test_nonstring_values_do_not_satisfy_commercial_approval_gate(self):
        for value in [None, False, 0, [], {}]:
            with self.subTest(reference=value), tempfile.TemporaryDirectory() as folder:
                service = ChatGPTPlanService({"allow_plan_usage": True, "distribution": "commercial", "commercial_approval_reference": value}, storage_path=Path(folder) / "auth")
                with self.assertRaises(BridgeError):
                    service.gate()
                self.assertFalse(service.store.path.exists())

    def test_disabled_connection_never_invokes_transport(self):
        class NeverTransport:
            def json(self, *a, **k):
                raise AssertionError("Disabled ChatGPT integration must not contact OpenAI")
        with tempfile.TemporaryDirectory() as folder:
            service = ChatGPTPlanService({}, storage_path=Path(folder) / "auth", transport=NeverTransport())
            with self.assertRaises(BridgeError):
                service.discover()
            self.assertFalse(service.status()["enabled"])
            self.assertFalse(service.store.path.exists())

    def test_wrong_callback_state_cannot_exchange_a_code(self):
        class NeverTransport:
            def json(self, *a, **k):
                raise AssertionError("Wrong OAuth state must not reach token exchange")
        with tempfile.TemporaryDirectory() as folder:
            service = self.service(folder, NeverTransport())
            with self.assertRaises(BridgeError):
                service.complete_callback({"status": "pending", "state": "expected"}, {"state": "wrong", "code": "synthetic", "client_id": "fixture-client"})
            self.assertFalse(service.store.path.exists())

    def test_missing_terminal_status_does_not_qualify_inference(self):
        class MalformedTransport:
            def json(self, url, **kwargs):
                return {"models": [{"slug": "fixture-model", "visibility": "list"}]}
            def events(self, token, body, cancel):
                yield {"type": "response.output_text.delta", "delta": "A fabricated partial proposal"}
                yield {"type": "response.completed", "response": {}}
        with tempfile.TemporaryDirectory() as folder:
            service = self.service(folder, MalformedTransport())
            self.seed(service)
            with self.assertRaises(BridgeError):
                service.generate({"model": "fixture-model", "prompt": "Test", "run_id": "terminal"})
            self.assertEqual(service.requests_started, 1)
            self.assertFalse(service._active)

    def test_credential_file_symlink_does_not_read_an_outside_record(self):
        with tempfile.TemporaryDirectory() as folder:
            service = self.service(folder)
            self.seed(service)
            outside = Path(folder) / "outside.json"
            outside.write_text("{not an auth record}")
            service.store.path.unlink()
            service.store.path.symlink_to(outside)
            with self.assertRaises(BridgeError):
                service.status()
            self.assertEqual(outside.read_text(), "{not an auth record}")


class FixtureWorkflowRuntime:
    def __init__(self, reply, entered=None, release=None):
        self.reply, self.entered, self.release = reply, entered, release
        self.calls = 0
    def status(self):
        return {"providers": [{"id": "local", "local": True}]}
    def provider(self, ident):
        if ident != "local":
            raise BridgeError("PROVIDER", "Unknown test fixture")
        return SimpleNamespace(remote=False)
    def generate(self, data):
        self.calls += 1
        if self.entered:
            self.entered.set()
        if self.release and not self.release.wait(5):
            raise RuntimeError("Independent test release did not arrive")
        return {"text": json.dumps(self.reply), "provider": "local", "model": "fixture", "usage": {}, "cost": {"amount": None}}
    def cancel(self, ident):
        return {"cancelled": True}


class IndependentWorkflowBoundaryTests(unittest.TestCase):
    @staticmethod
    def spec():
        return {"objective": "Construct a reusable arithmetic artifact", "roles": {"builder": {"provider": "local", "model": "fixture"}},
                "acceptance": [{"artifact": "instrument.json", "kind": "instrument", "input": {"x": 3}, "expected": {"result": 6}}],
                "max_iterations": 2, "max_actions": 8}
    @staticmethod
    def reply(expr=None):
        return {"summary": "Synthetic fixture, no real model", "actions": [{"tool": "construct_instrument", "name": "instrument.json",
            "spec": {"name": "Double", "inputs": ["x"], "outputs": {"result": expr or {"op": "mul", "args": [{"field": "x"}, 2]}}}}], "done": True}

    def test_callers_cannot_mutate_the_frozen_acceptance_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            service = WorkflowService(FixtureWorkflowRuntime(self.reply()), Path(folder) / "workspace")
            spec = self.spec()
            created = service.create(spec)
            spec["acceptance"][0]["expected"]["result"] = 999
            created["spec"]["acceptance"][0]["expected"]["result"] = 999
            result = service.step(created["id"])
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["spec"]["acceptance"][0]["expected"]["result"], 6)

    def test_model_cannot_supply_its_own_verification_override(self):
        reply = self.reply()
        reply["verification"] = {"passed": True}
        with tempfile.TemporaryDirectory() as folder:
            service = WorkflowService(FixtureWorkflowRuntime(reply), Path(folder) / "workspace")
            created = service.create(self.spec())
            result = service.step(created["id"])
            self.assertFalse(result["verification"]["passed"])
            self.assertEqual(result["artifacts"], {})
            self.assertTrue(any(e["kind"] == "response_refused" for e in result["events"]))

    def test_changed_artifact_cannot_export_or_inherit_old_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "workspace"
            service = WorkflowService(FixtureWorkflowRuntime(self.reply()), root)
            ident = service.create(self.spec())["id"]
            self.assertEqual(service.step(ident)["status"], "complete")
            (root / ident / ".objects" / service.get(ident)["artifacts"]["instrument.json"]["sha256"]).write_text("{}")
            for operation in [lambda: service.export(ident), lambda: service.reuse(ident, {"x": 5})]:
                with self.assertRaises(BridgeError):
                    operation()

    def test_rehashed_untrusted_export_cannot_import_an_arbitrary_runner(self):
        with tempfile.TemporaryDirectory() as folder:
            service = WorkflowService(FixtureWorkflowRuntime(self.reply()), Path(folder) / "workspace")
            ident = service.create(self.spec())["id"]
            service.step(ident)
            value = service.export(ident)
            value["files"]["unexpected.py"] = "print('untrusted program')"
            import hashlib
            raw = value["files"]["unexpected.py"].encode()
            value["state"]["artifacts"]["unexpected.py"] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "kind": "trusted_runner"}
            value["sha256"] = digest({k: v for k, v in value.items() if k != "sha256"})
            with self.assertRaises(BridgeError):
                service.import_archive(value)

    def test_final_cancel_discards_late_proposal_without_writing_artifacts(self):
        entered, release = threading.Event(), threading.Event()
        runtime = FixtureWorkflowRuntime(self.reply(), entered, release)
        with tempfile.TemporaryDirectory() as folder:
            service = WorkflowService(runtime, Path(folder) / "workspace")
            ident = service.create(self.spec())["id"]
            worker = threading.Thread(target=lambda: service.step(ident))
            worker.start()
            self.assertTrue(entered.wait(3))
            self.assertEqual(service.cancel(ident)["status"], "cancelled")
            release.set()
            worker.join(3)
            self.assertFalse(worker.is_alive())
            result = service.get(ident)
            self.assertEqual(result["status"], "cancelled")
            self.assertEqual(result["artifacts"], {})
            self.assertTrue(any(e["kind"] == "late_result_discarded" for e in result["events"]))

    def test_second_process_cannot_acquire_a_live_workspace(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "workspace"
            service = WorkflowService(FixtureWorkflowRuntime(self.reply()), root)
            command = [sys.executable, "-c", "from bridge.workflows import WorkflowService; from bridge.adapters import Runtime,BridgeError; import sys\ntry:\n WorkflowService(Runtime(),sys.argv[1])\n print('UNSAFE_SECOND_OWNER')\nexcept BridgeError as error:\n print(error.code)", str(root)]
            result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "WORKFLOW_OWNED")

    def test_same_process_instances_share_inflight_ownership(self):
        entered, release = threading.Event(), threading.Event()
        runtime = FixtureWorkflowRuntime(self.reply(), entered, release)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "workspace"
            first = WorkflowService(runtime, root)
            second = WorkflowService(runtime, root)
            ident = first.create(self.spec())["id"]
            worker = threading.Thread(target=lambda: first.step(ident))
            worker.start()
            self.assertTrue(entered.wait(3))
            try:
                with self.assertRaises(BridgeError) as error:
                    second.step(ident)
                self.assertEqual(error.exception.code, "WORKFLOW_BUSY")
            finally:
                release.set()
                worker.join(3)
            self.assertFalse(worker.is_alive())
            self.assertEqual(runtime.calls, 1)
            self.assertEqual(second.get(ident)["status"], "complete")

    def test_abrupt_exit_during_repair_preserves_a_resumable_previous_checkpoint(self):
        script = """
from pathlib import Path
import os, sys
sys.path.insert(0, 'tests')
from test_independent_security import FixtureWorkflowRuntime, IndependentWorkflowBoundaryTests
from bridge.workflows import WorkflowService
fixture = FixtureWorkflowRuntime(IndependentWorkflowBoundaryTests.reply(1))
service = WorkflowService(fixture, Path(sys.argv[1]))
spec = IndependentWorkflowBoundaryTests.spec()
spec["max_iterations"] = 3
ident = service.create(spec)["id"]
service.step(ident)
print(ident, flush=True)
fixture.reply = IndependentWorkflowBoundaryTests.reply()
original = service._save
saves = []
def interrupted_save(state):
    saves.append(1)
    if len(saves) == 2:
        os._exit(77)
    original(state)
service._save = interrupted_save
service.step(ident)
raise SystemExit(88)
"""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "workspace"
            result = subprocess.run([sys.executable, "-c", script, str(root)], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 77, result.stderr)
            ident = result.stdout.strip()
            service = WorkflowService(FixtureWorkflowRuntime(self.reply()), root)
            reopened = service.get(ident)
            self.assertEqual(reopened["status"], "interrupted")
            service.resume(ident, background=False)
            recovered = service.step(ident)
            self.assertEqual(recovered["status"], "complete")
            self.assertTrue(recovered["verification"]["passed"])

    def test_numeric_acceptance_is_independent_of_int_float_serialization(self):
        with tempfile.TemporaryDirectory() as folder:
            reply = self.reply({"op": "div", "args": [{"field": "x"}, 2]})
            service = WorkflowService(FixtureWorkflowRuntime(reply), Path(folder) / "workspace")
            spec = self.spec()
            spec["acceptance"][0].update(input={"x": 12}, expected={"result": 6})
            ident = service.create(spec)["id"]
            result = service.step(ident)
            self.assertEqual(result["status"], "complete")
            self.assertTrue(result["verification"]["passed"])


class IndependentHTTPBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.server = HarnessServer(("127.0.0.1", 0), config={"local_only": True}, workspace=self.root / "workspace")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(3)
        self.temp.cleanup()

    def post(self, path, data, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        defaults = {"Content-Type": "application/json", "X-Harness-Token": self.server.token}
        defaults.update(headers or {})
        connection.request("POST", path, json.dumps(data), headers=defaults)
        response = connection.getresponse()
        result = response.status, response.read()
        connection.close()
        return result

    def test_foreign_origin_cannot_start_workflow_even_with_a_session_token(self):
        status, raw = self.post("/api/workflows/create", IndependentWorkflowBoundaryTests.spec(), {"Origin": "https://foreign.invalid"})
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(raw)["error"]["code"], "ORIGIN")
        self.assertFalse((self.root / "workspace").exists())

    def test_local_only_disconnect_clears_tokens_without_network(self):
        class NeverTransport:
            def json(self, *a, **kw):
                raise AssertionError("Local-only disconnect must make zero network requests")
        plan = ChatGPTPlanService({"allow_plan_usage": True, "distribution": "open-source-local"},
                                  storage_path=self.root / "auth", transport=NeverTransport())
        IndependentChatGPTBoundaryTests.seed(plan)
        self.server.runtime._services["chatgpt"] = plan
        status, raw = self.post("/api/chatgpt/disconnect", {})
        self.assertEqual(status, 200, raw)
        self.assertFalse(json.loads(raw)["remote_revocation_confirmed"])
        with plan.store.locked():
            stored = plan.store.read()
        self.assertNotIn("access_token", stored["accounts"]["fixture-client"])

    def test_import_has_a_larger_envelope_without_expanding_generation_requests(self):
        runtime = FixtureWorkflowRuntime({"actions": [{"tool": "write_document", "name": "a.txt", "content": "a" * 600000}]})
        service = WorkflowService(runtime, self.root / "workspace")
        self.server._workflows = service
        spec = {"objective": "Large portable documents", "roles": {"builder": {"provider": "local", "model": "fixture"}},
                "acceptance": [{"artifact": "a.txt", "kind": "document", "min_chars": 600000},
                               {"artifact": "b.txt", "kind": "document", "min_chars": 600000}]}
        ident = service.create(spec)["id"]
        self.assertEqual(service.step(ident)["status"], "ready")
        runtime.reply = {"actions": [{"tool": "write_document", "name": "b.txt", "content": "b" * 600000}]}
        self.assertEqual(service.step(ident)["status"], "complete")
        exported = service.export(ident)
        self.assertGreater(len(json.dumps(exported)), 1048576)
        status, raw = self.post("/api/workflows/import", {"archive": exported})
        self.assertEqual(status, 200, raw[:500])
        self.assertEqual(json.loads(raw)["status"], "paused")
        # The ordinary endpoint rejects by declared size before reading a body.
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request("POST", "/api/generate", headers={"Content-Type": "application/json", "X-Harness-Token": self.server.token, "Content-Length": "1048577"})
        response = connection.getresponse()
        self.assertEqual(response.status, 413)
        response.read()
        connection.close()

    def test_zip_download_uses_verified_artifacts_and_refuses_later_tampering(self):
        service = WorkflowService(FixtureWorkflowRuntime(IndependentWorkflowBoundaryTests.reply()), self.root / "workspace")
        self.server._workflows = service
        ident = service.create(IndependentWorkflowBoundaryTests.spec())["id"]
        service.step(ident)
        status, raw = self.post("/api/workflows/download", {"run_id": ident})
        self.assertEqual(status, 200, raw[:100])
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            self.assertEqual(set(archive.namelist()), {"artifacts/instrument.json", "artifacts/RUN_INSTRUMENT.py", "WORKFLOW-EXPORT.json"})
            self.assertFalse(any("integrity-key" in name or "state.json" in name for name in archive.namelist()))
            exported = json.loads(archive.read("WORKFLOW-EXPORT.json"))
            self.assertEqual(exported["files"]["instrument.json"].encode(), archive.read("artifacts/instrument.json"))
        (self.root / "workspace" / ident / ".objects" / service.get(ident)["artifacts"]["instrument.json"]["sha256"]).write_text("{}")
        status, raw = self.post("/api/workflows/download", {"run_id": ident})
        self.assertNotEqual(status, 200)
        self.assertEqual(json.loads(raw)["error"]["code"], "WORKFLOW_INTEGRITY")


if __name__ == "__main__":
    unittest.main()
