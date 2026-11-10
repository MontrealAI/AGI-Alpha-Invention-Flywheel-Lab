# SPDX-License-Identifier: Apache-2.0
"""Boundary tests for customer local model setup; no external inference."""
import http.server
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError, Runtime
from bridge.onboarding import LocalConnectionService, PRESETS
from bridge.services import AccessRuntime


class LocalOnboardingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "private"
        self.calls = []
        def send(url, headers, body=None, timeout=60):
            self.calls.append((url, headers, body))
            return {"models": [{"name": "local-model:small"}], "data": [{"id": "local-model"}]}
        self.base = Runtime({"local_only": True}, sender=send)
        self.runtime = AccessRuntime(self.base, {"local_only": True})
        self.service = LocalConnectionService(self.runtime, self.root)

    def tearDown(self):
        self.runtime.close()
        self.temp.cleanup()

    def config(self, **changes):
        return dict({"engine": "ollama", "model": "local-model:small", "consent": True}, **changes)

    def test_constructor_and_presets_do_not_create_private_files_or_network(self):
        self.assertFalse(self.root.exists())
        result = self.service.presets()
        self.assertEqual(set(PRESETS), {x["id"] for x in result["engines"]})
        self.assertEqual(result["host"], "127.0.0.1")
        self.assertEqual(self.calls, [])
        self.assertFalse(self.root.exists())

    def test_all_presets_discover_only_numeric_loopback_without_credentials(self):
        for engine, preset in PRESETS.items():
            with self.subTest(engine=engine):
                result = self.service.discover({"engine": engine})
                url, headers, body = self.calls[-1]
                self.assertTrue(url.startswith(f"http://127.0.0.1:{preset['port']}"))
                self.assertNotIn("Authorization", headers)
                self.assertIsNone(body)
                self.assertFalse(result["models"][0]["configured"])

    def test_discovery_rejects_endpoint_or_key_injection_before_dispatch(self):
        attempts = [
            {"engine": "https://evil.example"}, {"engine": "ollama", "base_url": "https://evil.example"},
            {"engine": "ollama", "key_env": "SECRET"}, {"engine": "ollama", "port": "11434"},
            {"engine": "ollama", "port": True}, {"engine": "ollama", "port": 0},
            {"engine": "ollama", "port": 65536}, {"engine": []},
        ]
        for data in attempts:
            with self.subTest(data=data), self.assertRaises(BridgeError):
                self.service.discover(data)
        self.assertEqual(self.calls, [])

    def test_configuration_preserves_budget_spending_local_only_and_run_history(self):
        budget = self.base.budget
        self.base._runs["past"] = threading.Event()
        result = self.service.connect(self.config())
        self.assertIs(self.base.budget, budget)
        self.assertFalse(self.base.allow_paid)
        self.assertTrue(self.base.local_only)
        self.assertIn("past", self.base._runs)
        self.assertTrue(result["connected"])
        self.assertFalse(result["inference_verified"])
        model = self.base.provider("local-ollama").models["local-model:small"]
        self.assertFalse(model.json_mode)
        self.assertFalse(model.streaming)
        self.assertFalse(model.tool_calling)
        self.assertEqual(model.input_price, 0)
        self.assertEqual(self.calls, [])

    def test_explicit_features_and_custom_port_survive_restart(self):
        self.service.connect(self.config(port=11440, json_mode=True, streaming=True,
                                         tool_calling=True, max_output_tokens=2048, context_window=32768))
        new_base = Runtime({"local_only": True})
        restored = LocalConnectionService(new_base, self.root)
        provider = new_base.provider("local-ollama")
        self.assertEqual(provider.base, "http://127.0.0.1:11440")
        model = provider.models["local-model:small"]
        self.assertTrue(model.json_mode and model.streaming and model.tool_calling)
        self.assertEqual(model.context_window, 32768)
        self.assertEqual(restored.presets()["settings_saved"], ["ollama"])

    def test_saved_file_contains_only_non_secret_validated_settings(self):
        self.service.connect(self.config())
        saved = json.loads(self.service.path.read_text())
        self.assertEqual(saved["connections"][0]["engine"], "ollama")
        for disallowed in ("key_env", "api_key", "base_url", "allow_paid_requests", "providers"):
            self.assertNotIn(disallowed, saved["connections"][0])
            with self.subTest(field=disallowed), self.assertRaises(BridgeError):
                self.service.connect(self.config(**{disallowed: "untrusted"}))
        if sys.platform != "win32":
            self.assertEqual(self.service.path.stat().st_mode & 0o777, 0o600)

    def test_multiple_models_on_same_engine_survive_and_port_change_invalidates_them(self):
        self.service.connect(self.config())
        self.service.connect(self.config(model="second-model", json_mode=True))
        models = self.base.provider("local-ollama").models
        self.assertEqual(set(models), {"local-model:small", "second-model"})
        self.assertFalse(models["local-model:small"].json_mode)
        self.assertTrue(models["second-model"].json_mode)
        restored = LocalConnectionService(Runtime(), self.root)
        self.assertEqual(set(restored.base.provider("local-ollama").models), set(models))
        self.service.connect(self.config(model="third-model", port=11440))
        self.assertEqual(set(self.base.provider("local-ollama").models), {"third-model"})
        restored = LocalConnectionService(Runtime(), self.root)
        self.assertEqual(set(restored.base.provider("local-ollama").models), {"third-model"})

    def test_invalid_consent_capabilities_limits_and_models_fail_closed(self):
        cases = [{"consent": False}, {"consent": "true"}, {"model": "../bad?"}, {"model": []},
                 {"json_mode": "true"}, {"streaming": 1}, {"tool_calling": None},
                 {"max_output_tokens": True}, {"max_output_tokens": 0}, {"context_window": False},
                 {"context_window": 4}, {"save": "yes"}]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(BridgeError):
                self.service.connect(self.config(**change))
        self.assertEqual(self.base.providers, {})
        self.assertFalse(self.root.exists())

    def test_busy_runtime_refuses_connect_and_disconnect(self):
        self.service.connect(self.config())
        original = self.base.provider("local-ollama")
        self.base._active.add("running")
        for action in (lambda: self.service.connect(self.config(port=11440)),
                       lambda: self.service.disconnect({"engine": "ollama"})):
            with self.assertRaises(BridgeError) as caught:
                action()
            self.assertEqual(caught.exception.code, "LOCAL_SETUP_BUSY")
        self.assertIs(self.base.provider("local-ollama"), original)

    def test_connection_replacement_or_removal_during_request_preparation_prevents_dispatch(self):
        for action in ("connect", "disconnect"):
            with self.subTest(action=action):
                self.service.connect(self.config())
                previous = self.base.provider("local-ollama")
                original_request = previous.request
                def request(*args, **kwargs):
                    result = original_request(*args, **kwargs)
                    if action == "connect":
                        self.service.connect(self.config(port=11440))
                    else:
                        self.service.disconnect({"engine": "ollama"})
                    return result
                with patch.object(previous, "request", side_effect=request), self.assertRaises(BridgeError) as caught:
                    self.base.generate({"provider": "local-ollama", "model": "local-model:small", "prompt": "hello", "run_id": "preparing-" + action})
                self.assertEqual(caught.exception.code, "PROVIDER_CHANGED")
                self.assertEqual(self.calls, [])
                self.assertEqual(self.base._active, set())

    def test_do_not_overwrite_provider_from_private_configuration(self):
        original = Runtime({"providers": {"local-ollama": {"kind": "ollama", "base_url": "http://127.0.0.1:11434", "models": {}}}}).provider("local-ollama")
        self.base.providers[original.id] = original
        with self.assertRaises(BridgeError):
            self.service.connect(self.config())
        with self.assertRaises(BridgeError):
            self.service.disconnect({"engine": "ollama"})
        self.assertIs(self.base.provider(original.id), original)

    def test_disconnect_and_session_only_do_not_restore_old_setting(self):
        self.service.connect(self.config())
        self.service.connect(self.config(save=False, port=11440))
        restored = LocalConnectionService(Runtime(), self.root)
        self.assertEqual(restored.base.providers, {})
        self.service.disconnect({"engine": "ollama"})
        self.assertEqual(self.base.providers, {})

    def test_tampered_saved_settings_cannot_enable_remote_or_secret_configuration(self):
        self.service.connect(self.config())
        saved = json.loads(self.service.path.read_text())
        saved["connections"][0]["base_url"] = "https://evil.example"
        self.service.path.write_text(json.dumps(saved))
        new_base = Runtime()
        with self.assertRaises(BridgeError):
            LocalConnectionService(new_base, self.root)
        self.assertEqual(new_base.providers, {})

    def test_restore_is_atomic_when_later_record_invalid(self):
        self.service.connect(self.config())
        saved = json.loads(self.service.path.read_text())
        saved["connections"].append({"engine": "remote", "model": "bad"})
        self.service.path.write_text(json.dumps(saved))
        new_base = Runtime()
        with self.assertRaises(BridgeError):
            LocalConnectionService(new_base, self.root)
        self.assertEqual(new_base.providers, {})

    def test_symlink_settings_or_root_rejected(self):
        if not hasattr(Path, "symlink_to"):
            self.skipTest("Symlinks unavailable")
        elsewhere = Path(self.temp.name) / "elsewhere"
        elsewhere.mkdir()
        self.root.symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaises(BridgeError):
            LocalConnectionService(self.runtime, self.root)
        self.root.unlink()
        self.root.mkdir()
        (self.root / "local-model-connections.json").symlink_to(elsewhere / "nonexistent")
        with self.assertRaises(BridgeError):
            LocalConnectionService(self.runtime, self.root)


class LocalOnboardingLoopbackTests(unittest.TestCase):
    def test_discovery_connection_and_generation_use_real_loopback_http(self):
        requests = []
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_GET(self):
                requests.append(("GET", self.path))
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                self.wfile.write(b'{"data":[{"id":"installed-test-model"}]}')
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append(("POST", self.path, body["model"]))
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                self.wfile.write(b'{"choices":[{"message":{"content":"fixture-output"},"finish_reason":"stop"}],"usage":{"prompt_tokens":4,"completion_tokens":2}}')
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with tempfile.TemporaryDirectory() as temp:
                runtime = Runtime({"local_only": True})
                service = LocalConnectionService(runtime, Path(temp) / "private")
                catalog = service.discover({"engine": "custom", "port": server.server_port})
                self.assertEqual(catalog["models"][0]["id"], "installed-test-model")
                service.connect({"engine": "custom", "port": server.server_port, "model": "installed-test-model", "consent": True})
                result = runtime.generate({"provider": "local-custom", "model": "installed-test-model", "prompt": "fixture", "run_id": "onboarding-test"})
                self.assertEqual(result["text"], "fixture-output")
                self.assertEqual(requests, [("GET", "/v1/models"), ("POST", "/v1/chat/completions", "installed-test-model")])
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == "__main__":
    unittest.main()
