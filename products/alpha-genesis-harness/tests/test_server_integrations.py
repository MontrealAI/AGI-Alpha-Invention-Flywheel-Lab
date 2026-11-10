# SPDX-License-Identifier: Apache-2.0
"""Local HTTP integration checks, with no external model calls or credentials."""
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import Runtime
from bridge.server import HarnessServer
from bridge.services import AccessRuntime
from bridge.adapters import BridgeError


class IntegrationHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = HarnessServer(("127.0.0.1", 0), Runtime(),
                                    config={"local_only": True}, workspace=Path(self.temp.name) / "work")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(3)
        self.temp.cleanup()

    def call(self, path, body=None, *, authorized=True, origin=None):
        headers = {"Content-Type": "application/json"}
        if authorized:
            headers["X-Harness-Token"] = self.server.token
        if origin:
            headers["Origin"] = origin
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        connection.request("POST", path, json.dumps(body or {}), headers)
        response = connection.getresponse()
        value = response.status, response.read().decode()
        connection.close()
        return value

    def test_new_actions_require_session_before_initializing_private_storage(self):
        for path in ["/api/workflows/create", "/api/workflows/export", "/api/capabilities",
                     "/api/chatgpt/connect", "/api/codex/generate", "/api/generate-stream"]:
            with self.subTest(path=path):
                self.assertEqual(self.call(path, authorized=False)[0], 403)
                self.assertEqual(self.call(path, origin="https://foreign.example")[0], 403)
        self.assertIsNone(self.server._workflows)
        self.assertEqual(self.server.runtime._services, {})
        self.assertFalse((Path(self.temp.name) / "work").exists())

    def test_local_only_blocks_all_remote_paths_before_dispatch(self):
        with patch("bridge.server.retrieve_source", side_effect=AssertionError("network forbidden")), \
             patch.object(self.server.runtime, "service", side_effect=AssertionError("connection forbidden")):
            for path, body in [("/api/source", {"url": "https://developers.openai.com"}),
                               ("/api/chatgpt/connect", {}), ("/api/chatgpt/models", {}),
                               ("/api/codex/generate", {}),
                               ("/api/generate", {"provider": "chatgpt"}),
                               ("/api/models", {"provider": "codex"})]:
                status, raw = self.call(path, body)
                self.assertEqual(status, 403, raw)
                self.assertEqual(json.loads(raw)["error"]["code"], "LOCAL_ONLY")

    def test_workflow_names_cannot_invoke_arbitrary_attributes(self):
        self.assertEqual(self.call("/api/workflows/__init__")[0], 404)
        self.assertEqual(self.call("/api/workflows/__dict__")[0], 404)
        self.assertIsNone(self.server._workflows)

    def test_stream_delivers_progress_and_terminal_event(self):
        class StreamRuntime(Runtime):
            def provider(self, ident):
                from types import SimpleNamespace
                return SimpleNamespace(remote=False)
            def generate(self, data, on_event=None):
                on_event({"type": "text_delta", "text": "working"})
                return {"text": "complete", "run_id": data["run_id"]}
        self.server.runtime.base = StreamRuntime()
        status, raw = self.call("/api/generate-stream", {"provider": "fixture", "run_id": "stream-1"})
        events = [json.loads(line) for line in raw.splitlines()]
        self.assertEqual(status, 200)
        self.assertEqual(events[0], {"type": "text_delta", "text": "working"})
        self.assertEqual(events[-1]["type"], "completed")
        self.assertEqual(events[-1]["result"]["text"], "complete")

    def test_stream_permission_failure_remains_explicit(self):
        status, raw = self.call("/api/generate-stream", {"provider": "chatgpt", "run_id": "plan-1"})
        self.assertEqual(status, 200)  # stream status lives in its terminal event
        event = json.loads(raw)
        self.assertEqual(event["type"], "error")
        self.assertEqual(event["error"]["code"], "LOCAL_ONLY")

    def test_embedding_cannot_bypass_facade_local_only_with_an_authorized_base(self):
        config = {"allow_paid_requests": True, "providers": {"remote": {
            "kind": "openai", "base_url": "https://api.example.com/v1", "models": {}}}}
        base = Runtime(config, sender=lambda *a, **kw: self.fail("Unexpected network"))
        runtime = AccessRuntime(base, {"local_only": True})
        self.assertFalse(runtime.status()["providers"][0]["ready"])
        for call in [lambda: runtime.discover("remote"),
                     lambda: runtime.generate({"provider": "remote"})]:
            with self.assertRaises(BridgeError) as caught:
                call()
            self.assertEqual(caught.exception.code, "LOCAL_ONLY")


if __name__ == "__main__":
    unittest.main()
