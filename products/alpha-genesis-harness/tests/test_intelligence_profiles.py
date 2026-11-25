# SPDX-License-Identifier: Apache-2.0
"""Qualification of the paired local selection boundary and real loopback transport."""
import http.server
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError, Provider, Runtime, transport
from bridge.intelligence_profiles import IntelligenceProfiles
from bridge.onboarding import LocalConnectionService
from bridge.services import AccessRuntime


def configured(port, name="Installed model", url=None, credential=None):
    result = {"kind": "openai", "label": name, "base_url": url or f"http://127.0.0.1:{port}/v1",
              "output_limit_field": "max_tokens", "models": {"local-model": {
                  "input_per_million": 0, "output_per_million": 0,
                  "max_output_tokens": 768, "json_schema": not (url or "").startswith("https://"), "streaming": True,
              }}}
    if credential:
        result["key_env"] = credential
    return result


def completion(answer, body=None):
    value = {"answer": answer}
    schema = (body or {}).get("response_format", {}).get("json_schema", {}).get("schema", {})
    marker = schema.get("properties", {}).get("check", {}).get("const")
    if marker:
        value["check"] = marker
    return {"choices": [{"message": {"content": json.dumps(value)}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 24, "completion_tokens": 6}}


class IntelligenceProfileTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.workspace = Path(self.directory.name) / "private"
        self.requests = []
        self.model_digest = "a" * 64
        self.answer = 42
        self.after_completion = lambda: None
        self.accept_return = None
        self.config = {"providers": {"native-local": configured(38461),
                                     "another-local": configured(38462),
                                     "private-native": configured(58461, credential="FRONTIER_NATIVE_ONLY_SECRET"),
                                     "remote-native": configured(443, url="https://inference.example.com/v1")}}
        self.base, self.profiles = self.profile(self.config)

    def profile(self, config):
        base = Runtime(config, sender=self.send)
        access = AccessRuntime(base, config)
        self.addCleanup(access.close)
        return base, IntelligenceProfiles(LocalConnectionService(access, self.workspace))

    def send(self, url, headers, body=None, timeout=60):
        self.requests.append((url, headers, body, timeout))
        if body is not None:
            self.after_completion()
            if self.accept_return:
                raise self.accept_return
            return completion(self.answer, body)
        if url.endswith("/api/tags"):
            return {"models": [
                {"name": "verified-local", "digest": "b" * 64, "size": 4_000_000},
                {"name": "upstream", "size": 4, "remote_host": "https://unapproved.example.invalid"},
                {"model": "remote-alias", "size": 4, "remote_model": "upstream"},
                {"name": "route:cloud", "size": 50}, {"name": "stub", "size": 0},
            ]}
        if ":38461/" in url or ":38462/" in url:
            return {"data": [{"id": "local-model", "digest": self.model_digest}, {"id": "unconfigured-model"}]}
        raise BridgeError("PROVIDER_CONNECTION", "Test server unavailable.", 502)

    def choice(self, *, engine="configured", label=None):
        result = self.profiles.discover({"consent": True})
        return next(row["id"] for row in result["candidates"] if row["engine"] == engine
                    and (label is None or label == row["label"]))

    def test_status_has_no_network_or_storage_side_effects(self):
        self.assertEqual(self.profiles.status()["selection"], None)
        self.assertEqual(set(self.profiles.status()["modes"]), {"local", "hybrid"})
        self.assertIsNone(self.profiles.current())
        self.assertEqual(self.requests, [])
        self.assertFalse(self.workspace.exists())

    def test_catalog_respects_fixed_routes_and_native_scope(self):
        result = self.profiles.discover({"consent": True})
        self.assertEqual({row["model"] for row in result["candidates"]}, {"local-model", "verified-local"})
        self.assertEqual({url for url, _, _, _ in self.requests}, {
            "http://127.0.0.1:11434/api/tags", "http://127.0.0.1:1234/v1/models", "http://127.0.0.1:8080/v1/models",
            "http://127.0.0.1:8000/v1/models", "http://127.0.0.1:38461/v1/models", "http://127.0.0.1:38462/v1/models",
        })
        self.assertTrue(all(body is None and "Authorization" not in headers and timeout <= 2
                            for _, headers, body, timeout in self.requests))
        self.assertFalse(self.workspace.exists())

    def test_activation_requires_a_returned_choice_and_local_consent(self):
        for body in ({}, {"consent": 1}, {"consent": True, "port": 22}, {"consent": True, "url": "localhost"}):
            with self.assertRaises(BridgeError):
                self.profiles.discover(body)
        for body in ({}, {"id": "a model", "consent": True, "mode": "local"},
                     {"id": "x", "consent": True, "mode": "paid"}):
            with self.assertRaises(BridgeError):
                self.profiles.connect(body)
        self.assertEqual(self.requests, [])

    def test_configured_authority_reserves_automatic_ports(self):
        protected = {"providers": {
            "native-auth": configured(1234, url="http://localhost:1234/v1", credential="FRONTIER_NATIVE_ONLY_SECRET"),
            "native-anonymous": configured(1234),
            "native-other": configured(8000, url="http://127.0.0.1:8000/approved/v1"),
        }}
        _, profile = self.profile(protected)
        profile.discover({"consent": True})
        paths = {url for url, _, _, _ in self.requests}
        self.assertNotIn("http://127.0.0.1:1234/v1/models", paths)
        self.assertNotIn("http://127.0.0.1:8000/v1/models", paths)
        self.assertIn("http://127.0.0.1:8000/approved/v1/models", paths)

    def test_unaliased_model_paths_stay_on_connector_and_exact_model_is_requested(self):
        raw_model = "/private/models/example.gguf"
        dispatched = []

        def sender(url, headers, body=None, timeout=60):
            if url.endswith(":8080/v1/models"):
                return {"data": [{"id": raw_model}]}
            if url.endswith(":8080/v1/chat/completions"):
                dispatched.append(body)
                return completion(42, body)
            raise BridgeError("PROVIDER_CONNECTION", "Test server unavailable.", 502)

        access = AccessRuntime(Runtime({}, sender=sender), {})
        self.addCleanup(access.close)
        profile = IntelligenceProfiles(LocalConnectionService(access, self.workspace))
        candidate = profile.discover({"consent": True})["candidates"][0]
        self.assertEqual(candidate["model"], "example.gguf")
        chosen = profile.connect({"id": candidate["id"], "consent": True, "mode": "local"})["selection"]
        self.assertEqual(chosen["model_label"], "example.gguf")
        self.assertTrue(chosen["model"].startswith("frontier-model-"))
        self.assertNotIn("/private/models", profile.path.read_text())
        access.generate({"provider": chosen["provider"], "model": chosen["model"], "run_id": "profile-unaliased",
                         "prompt": "A separate permitted mission", "max_output_tokens": 64})
        self.assertEqual([body["model"] for body in dispatched], [raw_model, raw_model])

    def test_ordinary_connection_reports_only_demonstrated_request_formats(self):
        formats = []

        def sender(url, headers, body=None, timeout=60):
            if url.endswith(":8080/v1/models"):
                return {"data": [{"id": "local-model"}]}
            if url.endswith(":8080/v1/chat/completions"):
                formats.append(body.get("response_format", {}).get("type"))
                if formats[-1] == "json_object":
                    raise BridgeError("PROVIDER_HTTP", "Provider HTTP 422. Unsupported format.", 502)
                return completion(42)
            raise BridgeError("PROVIDER_CONNECTION", "Test server unavailable.", 502)

        access = AccessRuntime(Runtime({}, sender=sender), {})
        self.addCleanup(access.close)
        profile = IntelligenceProfiles(LocalConnectionService(access, self.workspace))
        candidate = profile.discover({"consent": True})["candidates"][0]
        chosen = profile.connect({"id": candidate["id"], "consent": True, "mode": "local"})["selection"]
        self.assertEqual(formats, ["json_schema", "json_object", None])
        self.assertEqual(chosen["verification"]["format"], "prompt_json")
        adapter_model = access.base.provider(chosen["provider"]).models[chosen["model"]]
        self.assertFalse(adapter_model.json_schema)
        self.assertFalse(adapter_model.json_mode)

    def test_saved_choice_is_qualified_on_demand_and_routed_without_fallback(self):
        token = self.choice()
        route = self.profiles.connect({"id": token, "consent": True, "mode": "hybrid"})["selection"]
        self.assertTrue(route["ready"])
        self.assertEqual(route["mode"], "hybrid")
        self.assertEqual(route["verification"]["format"], "json_schema")
        self.assertTrue(route["provider"].startswith("frontier-local-"))
        self.assertFalse(self.base.provider(route["provider"]).models[route["model"]].streaming)
        calls = sum(item[2] is not None for item in self.requests)
        self.assertEqual(calls, 1)
        duplicate = self.profiles.connect({"id": token, "consent": True, "mode": "hybrid"})
        self.assertEqual(duplicate["selection"], route)
        self.assertEqual(sum(item[2] is not None for item in self.requests), 1)
        _, restored = self.profile(self.config)
        self.assertIsNone(restored.current())
        self.assertFalse(restored.status()["selection"]["ready"])
        self.assertEqual(sum(item[2] is not None for item in self.requests), 1)
        selected = restored.reconnect({"consent": True})["selection"]
        self.assertEqual(selected["provider"], route["provider"])
        self.assertTrue(selected["ready"])
        self.assertEqual(sum(item[2] is not None for item in self.requests), 2)
        rechecked = restored.reconnect({"consent": True})["selection"]
        self.assertEqual(rechecked["provider"], route["provider"])
        self.assertEqual(sum(item[2] is not None for item in self.requests), 3)
        settings = self.profiles.path.read_text()
        self.assertNotIn("127.0.0.1", settings)
        self.assertNotIn("key", settings.casefold())
        self.assertNotIn("Connection check", settings)

    def test_wrong_probe_result_does_not_save_or_grant_mission_authority(self):
        token = self.choice()
        self.answer = 41
        with self.assertRaisesRegex(BridgeError, "did not complete"):
            self.profiles.connect({"id": token, "consent": True, "mode": "local"})
        self.assertIsNone(self.profiles.current())
        self.assertFalse(self.workspace.exists())
        self.assertFalse(self.base._active)
        self.assertEqual(set(self.base.providers), set(self.config["providers"]))
        self.assertEqual(sum(item[2] is not None for item in self.requests), 1)

    def test_model_digest_changes_refuse_stale_choice_before_model_dispatch(self):
        token = self.choice()
        self.model_digest = "c" * 64
        with self.assertRaisesRegex(BridgeError, "model changed"):
            self.profiles.connect({"id": token, "consent": True, "mode": "local"})
        self.assertTrue(all(item[2] is None for item in self.requests))

    def test_revocation_after_probe_withholds_installation_and_saved_authority(self):
        token = self.choice()
        revoked = threading.Event()
        self.after_completion = revoked.set

        def admit():
            if revoked.is_set():
                raise BridgeError("MISSION_LEASE_EXPIRED", "Expired fixture permission.", 403)

        with self.assertRaisesRegex(BridgeError, "Expired fixture"):
            self.profiles.connect({"id": token, "consent": True, "mode": "local"}, admit=admit)
        self.assertTrue(revoked.is_set())
        self.assertFalse(self.profiles.path.exists())
        self.assertFalse(any(key.startswith("frontier-local-") for key in self.base.providers))
        self.assertIsNone(self.profiles.current())

    def test_endpoint_changes_create_distinct_provider_id_and_never_reconnect_old_route(self):
        token = self.choice()
        old = self.profiles.connect({"id": token, "consent": True, "mode": "local"})["selection"]
        changed = {"providers": {"native-local": configured(38462)}}
        base, profiles = self.profile(changed)
        with self.assertRaisesRegex(BridgeError, "exact model is no longer listed"):
            profiles.reconnect({"consent": True})
        results = profiles.discover({"consent": True})
        new_token = next(row["id"] for row in results["candidates"] if row["engine"] == "configured")
        new = profiles.connect({"id": new_token, "consent": True, "mode": "local"})["selection"]
        self.assertEqual(new["model"], old["model"])
        self.assertNotEqual(new["provider"], old["provider"])
        self.assertNotIn(old["provider"], base.providers)

    def test_replaced_native_provider_object_revokes_in_memory_readiness(self):
        token = self.choice()
        self.profiles.connect({"id": token, "consent": True, "mode": "local"})
        self.base.providers["native-local"] = Provider("native-local", configured(38462))
        self.assertIsNone(self.profiles.current())

    def test_active_call_refuses_probe_and_remembered_choice_can_be_removed(self):
        token = self.choice()
        self.base._active.add("active-fixture")
        try:
            with self.assertRaisesRegex(BridgeError, "Finish active inference"):
                self.profiles.connect({"id": token, "consent": True, "mode": "local"})
        finally:
            self.base._active.clear()
        current = self.profiles.connect({"id": token, "consent": True, "mode": "local"})["selection"]
        self.assertEqual(self.profiles.disconnect({"consent": True}), {"selection": None})
        self.assertFalse(self.profiles.path.exists())
        self.assertNotIn(current["provider"], self.base.providers)
        self.assertIn("native-local", self.base.providers)


class IntelligenceLoopbackTests(unittest.TestCase):
    def test_actual_loopback_inventory_probe_and_selected_harness_generation(self):
        seen = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def send(self, value):
                data = json.dumps(value).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                seen.append(("GET", self.path, None))
                self.send({"data": [{"id": "local-model"}]})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                seen.append(("POST", self.path, body))
                self.send(completion(42, body))

        with http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server, tempfile.TemporaryDirectory() as temp:
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            config = {"local_only": True, "providers": {"native-local": configured(server.server_port)}}

            def sender(url, *args, **kw):
                if not url.startswith(f"http://127.0.0.1:{server.server_port}/"):
                    raise BridgeError("PROVIDER_CONNECTION", "Fixed baseline routes disabled in this transport fixture.", 502)
                return transport(url, *args, **kw)

            access = AccessRuntime(Runtime(config, sender=sender), config)
            try:
                profiles = IntelligenceProfiles(LocalConnectionService(access, Path(temp) / "private"))
                catalog = profiles.discover({"consent": True})
                chosen = profiles.connect({"id": catalog["candidates"][0]["id"], "consent": True, "mode": "local"})["selection"]
                result = access.generate({"provider": chosen["provider"], "model": chosen["model"], "run_id": "e2e-profile",
                                          "prompt": "A separate permitted mission", "max_output_tokens": 64})
                self.assertEqual(json.loads(result["text"]), {"answer": 42})
                self.assertEqual([(method, path) for method, path, _ in seen], [
                    ("GET", "/v1/models"), ("GET", "/v1/models"),
                    ("POST", "/v1/chat/completions"), ("POST", "/v1/chat/completions"),
                ])
                self.assertEqual(seen[2][2]["response_format"]["type"], "json_schema")
                self.assertNotIn("A separate permitted mission", json.dumps(seen[2][2]))
            finally:
                access.close()
                server.shutdown()
                worker.join()
