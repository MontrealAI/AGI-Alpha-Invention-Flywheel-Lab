# SPDX-License-Identifier: Apache-2.0
"""Queued authorization boundaries using synthetic accounts, never live tokens."""
import json
import io
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError
from bridge.chatgpt import ChatGPTPlanService, PlanTransport, RESOURCE
from bridge.codex import CodexService
from test_chatgpt import FakeTransport, seed


class ExecutionIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.transport = FakeTransport()
        self.plan = self.service()

    def service(self):
        def verify(token, client, nonce, transport, expected_subject):
            return {"subject": expected_subject or "synthetic-subject", "email": "fixture@example.invalid"}
        service = ChatGPTPlanService({"allow_plan_usage": True, "distribution": "open-source-local"},
            self.root / "auth", self.transport, browser_open=lambda _: True, identity_verifier=verify)
        self.addCleanup(service.close)
        return service

    def request(self, run_id="queued-one"):
        return {"run_id": run_id, "model": "account-model", "prompt": "Synthetic queued work"}

    def reauthorize(self, service):
        service.start_sign_in("oaiapp_fixture", reconsent=True)
        pending = service.pending
        service.complete_callback(pending, {"state": pending["state"], "code": "synthetic-code",
                                           "client_id": "oaiapp_fixture"})

    def test_identity_does_not_create_storage_or_refresh_and_hides_tokens(self):
        with self.assertRaises(BridgeError):
            self.plan.execution_identity()
        self.assertFalse(self.plan.store.directory.exists())
        seed(self.plan, expiry=1)
        identity = self.plan.execution_identity()
        self.assertEqual(self.transport.calls, [])
        for secret in ("synthetic-access-credential", "synthetic-refresh-credential",
                       "synthetic-id-credential", "fixture@example.invalid", "oaiapp_fixture-subject"):
            self.assertNotIn(secret, json.dumps(identity))
        self.transport.token_response.pop("id_token")
        self.transport.token_response.update(access_token="refreshed-access", refresh_token="refreshed-refresh")
        self.plan._account()
        self.assertEqual(self.plan.execution_identity(), identity)
        self.assertEqual(self.plan.requests_started, 0)

    def test_same_account_reselection_persists_epoch_and_refuses_stale_queue(self):
        seed(self.plan)
        identity = self.plan.execution_identity()
        other = self.service()
        self.assertEqual(other.execution_identity(), identity)
        other.select_account("oaiapp_fixture")
        self.assertNotEqual(self.plan.execution_identity(), identity)
        self.assertEqual(other.execution_identity(), self.plan.execution_identity())
        with self.assertRaises(BridgeError) as failure:
            self.plan.generate(self.request(), expected_execution_identity=identity)
        self.assertEqual(failure.exception.code, "CHATGPT_ACCOUNT_CHANGED")
        self.assertTrue(failure.exception.pre_dispatch)
        self.assertEqual(self.transport.calls, [])
        self.assertEqual(self.plan.requests_started, 0)
        self.assertEqual(self.plan._runs, {})
        self.assertEqual(self.plan._active, {})

    def test_disconnect_reauthorization_and_close_invalidate_waiting_authority(self):
        seed(self.plan)
        original = self.plan.execution_identity()
        other = self.service()
        other.disconnect(revoke_remote=False)
        with self.assertRaises(BridgeError):
            self.plan.execution_identity()
        self.assertEqual(self.transport.calls, [])
        self.reauthorize(other)
        renewed = self.plan.execution_identity()
        self.assertNotEqual(renewed, original)
        self.reauthorize(other)
        self.assertNotEqual(self.plan.execution_identity(), renewed)
        self.plan.close()
        with self.assertRaises(BridgeError) as failure:
            self.plan.execution_identity()
        self.assertEqual(failure.exception.code, "CHATGPT_CLOSED")
        self.assertEqual(self.plan.requests_started, 0)

    def test_epoch_change_during_catalog_prevents_inference_and_count(self):
        seed(self.plan)
        identity = self.plan.execution_identity()
        other = self.service()
        original = self.transport.json
        def catalog(url, **kwargs):
            if url == RESOURCE + "/models":
                other.select_account("oaiapp_fixture")
            return original(url, **kwargs)
        self.transport.json = catalog
        with self.assertRaises(BridgeError) as failure:
            self.plan.generate(self.request(), expected_execution_identity=identity)
        self.assertEqual(failure.exception.code, "CHATGPT_ACCOUNT_CHANGED")
        self.assertFalse(any(url.endswith("/responses") for url, _, _ in self.transport.calls))
        self.assertEqual(self.plan.requests_started, 0)
        self.assertEqual(self.plan._active, {})

    def test_codex_shares_identity_and_rechecks_after_probe_before_spawn(self):
        seed(self.plan)
        identity = self.plan.execution_identity()
        other = self.service()
        calls = []
        codex = CodexService({"allow_execution": True, "executable": sys.executable}, self.plan,
            self.root / "work", process_factory=lambda *a, **kw: calls.append((a, kw)),
            sandbox_validator=lambda _: None,
            runtime_probe=lambda *a: other.select_account("oaiapp_fixture"))
        self.addCleanup(codex.close)
        self.assertEqual(codex.max_concurrent, self.plan.max_concurrent)
        self.assertEqual(codex.max_concurrent, 1)
        self.assertEqual(codex.execution_identity(), identity)
        self.assertEqual(self.transport.calls, [])
        with self.assertRaises(BridgeError) as failure:
            codex.generate(self.request(), expected_execution_identity=identity)
        self.assertEqual(failure.exception.code, "CHATGPT_ACCOUNT_CHANGED")
        self.assertEqual(calls, [])
        self.assertEqual(self.plan.requests_started, 0)
        self.assertEqual(self.plan._active, {})
        codex.close()
        with self.assertRaises(BridgeError) as failure:
            codex.execution_identity()
        self.assertEqual(failure.exception.code, "CODEX_CLOSED")

    def selection_race(self):
        """Compete from a separate service at the final locked vault snapshot."""
        other = self.service()
        attempted, selected = threading.Event(), threading.Event()
        errors, threads = [], []
        original = self.plan.store.read
        armed = [False]
        def select():
            attempted.set()
            try:
                other.select_account("oaiapp_fixture")
            except Exception as error:
                errors.append(error)
            finally:
                selected.set()
        def read():
            state = original()
            if armed[0]:
                armed[0] = False
                thread = threading.Thread(target=select, daemon=True)
                threads.append(thread)
                thread.start()
                self.assertTrue(attempted.wait(2))
                self.assertFalse(selected.wait(.05), "Selection completed inside the dispatch authority transaction")
            return state
        self.plan.store.read = read
        def finished():
            for thread in threads:
                thread.join(2)
                self.assertFalse(thread.is_alive(), "Dispatch retained the vault lock")
            self.assertEqual(errors, [])
            self.assertTrue(selected.is_set())
        return armed, selected, finished

    def test_codex_shared_vault_serializes_selection_through_process_spawn(self):
        seed(self.plan)
        identity = self.plan.execution_identity()
        armed, selected, finished = self.selection_race()
        calls = []
        def spawn(*args, **kwargs):
            self.assertFalse(selected.is_set())
            calls.append(True)
            raise BridgeError("SYNTHETIC_PROCESS", "Synthetic spawn boundary reached")
        codex = CodexService({"allow_execution": True, "executable": sys.executable}, self.plan,
            self.root / "work", process_factory=spawn, sandbox_validator=lambda _: None,
            runtime_probe=lambda *args: armed.__setitem__(0, True))
        self.addCleanup(codex.close)
        with self.assertRaises(BridgeError) as failure:
            codex.generate(self.request(), expected_execution_identity=identity)
        self.assertEqual(failure.exception.code, "SYNTHETIC_PROCESS")
        self.assertFalse(getattr(failure.exception, "pre_dispatch", False))
        finished()
        self.assertEqual(calls, [True])
        self.assertEqual(self.plan.requests_started, 1)

    def test_chatgpt_shared_vault_covers_open_but_not_stream_reading(self):
        seed(self.plan)
        identity = self.plan.execution_identity()
        armed, selected, finished = self.selection_race()
        transport = PlanTransport()
        calls = []
        def catalog(url, **kwargs):
            result = self.transport.json(url, **kwargs)
            armed[0] = True
            return result
        transport.json = catalog
        owner = self
        class Response(io.BytesIO):
            headers = {"Content-Type": "text/event-stream"}
            def readline(self, *args):
                owner.assertTrue(selected.wait(2), "Stream reading retained the vault lock")
                return super().readline(*args)
        def opened(url, **kwargs):
            self.assertFalse(selected.is_set())
            calls.append(url)
            raw = "".join("data: " + json.dumps(event) + "\n\n" for event in self.transport.stream)
            return Response(raw.encode())
        transport.open = opened
        self.plan.transport = transport
        result = self.plan.generate(self.request(), expected_execution_identity=identity)
        finished()
        self.assertEqual(result["text"], "Useful result")
        self.assertEqual(calls, [RESOURCE + "/responses"])
        self.assertEqual(self.plan.requests_started, 1)

    def test_cancellation_before_registration_and_after_probe_has_no_dispatch(self):
        seed(self.plan)
        identity = self.plan.execution_identity()
        with self.assertRaises(BridgeError) as failure:
            self.plan.generate(self.request(), expected_execution_identity=identity,
                               cancelled_before_dispatch=lambda: True)
        self.assertTrue(failure.exception.pre_dispatch)
        self.assertEqual(self.plan._runs, {})
        cancelled = threading.Event()
        calls = []
        codex = CodexService({"allow_execution": True, "executable": sys.executable}, self.plan,
            self.root / "work", process_factory=lambda *a, **kw: calls.append(True),
            sandbox_validator=lambda _: None, runtime_probe=lambda *a: cancelled.set())
        self.addCleanup(codex.close)
        with self.assertRaises(BridgeError) as failure:
            codex.generate(self.request(), expected_execution_identity=identity,
                           cancelled_before_dispatch=cancelled.is_set)
        self.assertTrue(failure.exception.pre_dispatch)
        self.assertEqual(failure.exception.code, "CANCELLED")
        self.assertEqual(calls, [])
        self.assertEqual(self.plan.requests_started, 0)


if __name__ == "__main__":
    unittest.main()
