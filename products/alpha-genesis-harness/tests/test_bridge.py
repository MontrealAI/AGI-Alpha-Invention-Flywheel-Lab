# SPDX-License-Identifier: Apache-2.0
"""Protocol fixtures and local HTTP boundary tests; ZERO live model/provider qualification."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from decimal import Decimal
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError, Budget, Provider, Runtime, retrieve_source, strict_json, transport
from bridge.server import HarnessServer, NativeMechanism


def configuration(kind="openai", *, attempts=1, budget=100, remote=False):
    base = "https://api.example.com/v1" if remote else "http://127.0.0.1:11434"
    return {"session_budget_usd": budget, "allow_paid_requests": True, "max_attempts": attempts,
            "providers": {"test": {"kind": kind, "base_url": base, "key_env": "HARNESS_TEST_KEY",
                                   "models": {"model-a": {"input_per_million": 10, "output_per_million": 20,
                                                         "max_output_tokens": 8192, "json_mode": kind != "anthropic"}}}}}


def request(ident="one", **kw):
    return dict({"provider": "test", "model": "model-a", "prompt": "Find a testable arrangement.",
                 "max_output_tokens": 64, "run_id": ident}, **kw)


def response(kind="openai"):
    if kind == "openai":
        return {"choices": [{"message": {"content": "A proposal, not verification."}}], "usage": {"prompt_tokens": 10, "completion_tokens": 12}}
    if kind == "anthropic":
        return {"content": [{"type": "text", "text": "A proposal, not verification."}], "usage": {"input_tokens": 10, "output_tokens": 12}}
    if kind == "gemini":
        return {"candidates": [{"content": {"parts": [{"text": "A proposal, not verification."}]}}], "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 10, "thoughtsTokenCount": 2}}
    return {"message": {"content": "A proposal, not verification."}, "prompt_eval_count": 10, "eval_count": 12}


class AdapterContractTests(unittest.TestCase):
    def test_all_four_wire_protocols_and_usage(self):
        suffixes = {"openai": "/chat/completions", "anthropic": "/messages", "gemini": "/models/model-a:generateContent", "ollama": "/api/chat"}
        for kind in suffixes:
            with self.subTest(kind=kind):
                calls = []
                def sender(url, headers, body=None, **_):
                    calls.append((url, headers, body))
                    return response(kind)
                runtime = Runtime(configuration(kind), sender)
                result = runtime.generate(request())
                self.assertTrue(calls[0][0].endswith(suffixes[kind]))
                self.assertEqual(result["usage"], {"input_tokens": 10, "output_tokens": 12})
                self.assertEqual(result["cost"]["amount"], 0.00034)
                self.assertEqual(runtime.budget.view()["reserved"], 0)
                self.assertEqual(runtime.budget.view()["committed"], 0.00034)
                self.assertNotIn("tools", calls[0][2])

    def test_headers_and_json_output_fields(self):
        with patch.dict(os.environ, {"HARNESS_TEST_KEY": "fixture-secret-only"}):
            for kind in ["openai", "anthropic", "gemini", "ollama"]:
                p = Runtime(configuration(kind)).providers["test"]
                header = p.headers()
                if kind == "anthropic":
                    self.assertEqual(header["x-api-key"], "fixture-secret-only")
                    self.assertEqual(header["anthropic-version"], "2026-10-21")
                elif kind == "gemini":
                    self.assertEqual(header["x-goog-api-key"], "fixture-secret-only")
                else:
                    self.assertEqual(header["Authorization"], "Bearer fixture-secret-only")
                if kind != "anthropic":
                    _, body = p.request("model-a", "Return JSON", 20, True)
                    self.assertTrue(any(key in body for key in ["format", "response_format", "generationConfig"]))
                else:
                    with self.assertRaises(BridgeError):
                        p.request("model-a", "Return JSON", 20, True)

    def test_missing_usage_keeps_conservative_reservation(self):
        raw = response()
        del raw["usage"]
        r = Runtime(configuration(), lambda *a, **kw: raw)
        result = r.generate(request())
        self.assertIsNone(result["usage"]["input_tokens"])
        self.assertEqual(result["cost"]["basis"], "reserved_unknown")
        self.assertGreater(result["cost"]["accounted"], 0.04)

    def test_invalid_response_and_unexpected_exception_keep_cost(self):
        for value in [None, [], {"choices": []}, dict(response(), usage=[]), dict(response(), usage={"prompt_tokens": True, "completion_tokens": -1})]:
            with self.subTest(value=value):
                r = Runtime(configuration(), lambda *a, **kw: value)
                try:
                    result = r.generate(request())
                    self.assertEqual(result["cost"]["basis"], "reserved_unknown")
                except BridgeError:
                    pass
                self.assertGreater(r.budget.view()["committed"], 0.04)
                self.assertEqual(r.budget.view()["reserved"], 0)
        def bad_sender(*_, **__):
            raise AttributeError("internal fixture failure")
        r = Runtime(configuration(), bad_sender)
        with self.assertRaises(BridgeError):
            r.generate(request())
        self.assertGreater(r.budget.view()["committed"], 0.04)

    def test_missing_credentials_and_remote_permission_preflight(self):
        config = configuration(remote=True)
        with patch.dict(os.environ, {}, clear=True):
            r = Runtime(config, lambda *_, **__: self.fail("Must not dispatch"))
            with self.assertRaisesRegex(BridgeError, "credentials"):
                r.generate(request())
            self.assertEqual(r.budget.view()["committed"], 0)
        config["allow_paid_requests"] = False
        with patch.dict(os.environ, {"HARNESS_TEST_KEY": "fixture-only"}):
            r = Runtime(config, lambda *_, **__: self.fail("Must not dispatch"))
            with self.assertRaisesRegex(BridgeError, "disabled"):
                r.generate(request())

    def test_duplicate_run_id_refuses_second_dispatch(self):
        r = Runtime(configuration(), lambda *a, **kw: response())
        r.generate(request())
        with self.assertRaisesRegex(BridgeError, "already been used"):
            r.generate(request())
        self.assertEqual(r.budget.view()["committed"], 0.00034)

    def test_budget_reservation_is_atomic(self):
        budget = Budget("1")
        barrier = threading.Barrier(2)
        outcomes = []
        def reserve():
            barrier.wait()
            try:
                budget.reserve(Decimal("0.75"))
                outcomes.append(True)
            except BridgeError:
                outcomes.append(False)
        threads = [threading.Thread(target=reserve) for _ in range(2)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(sorted(outcomes), [False, True])
        self.assertEqual(budget.view()["reserved"], 0.75)

    def test_insufficient_budget_sends_nothing(self):
        r = Runtime(configuration(budget=0), lambda *a, **kw: self.fail("Must not dispatch"))
        with self.assertRaisesRegex(BridgeError, "exceed"):
            r.generate(request())

    def test_retry_reserves_failed_attempt_then_success(self):
        attempts = []
        def sender(*a, **kw):
            attempts.append(1)
            if len(attempts) == 1:
                raise BridgeError("PROVIDER_HTTP", "Provider HTTP 503.", 502)
            return response()
        r = Runtime(configuration(attempts=2), sender)
        result = r.generate(request())
        self.assertEqual(result["cost"]["attempts"], 2)
        self.assertGreater(result["cost"]["accounted"], result["cost"]["amount"])
        self.assertEqual(r.budget.view()["reserved"], 0)

    def test_cancel_in_flight_discards_result_and_preserves_cost(self):
        entered, release = threading.Event(), threading.Event()
        def sender(*a, **kw):
            entered.set()
            release.wait(3)
            return response()
        r = Runtime(configuration(), sender)
        codes = []
        def generate():
            try:
                r.generate(request())
            except BridgeError as e:
                codes.append(e.code)
        thread = threading.Thread(target=generate)
        thread.start()
        self.assertTrue(entered.wait(3))
        self.assertTrue(r.cancel("one")["cancelled"])
        release.set()
        thread.join(3)
        self.assertEqual(codes, ["CANCELLED_ACCOUNTED"])
        self.assertEqual(r.budget.view()["committed"], 0.00034)
        self.assertEqual(r.budget.view()["reserved"], 0)

    def test_usage_overrun_locks_future_dispatch(self):
        raw = response()
        raw["usage"]["prompt_tokens"] = 100000
        r = Runtime(configuration(), lambda *a, **kw: raw)
        r.generate(request())
        self.assertTrue(r.budget.view()["locked"])
        with self.assertRaises(BridgeError):
            r.generate(request("two"))

    def test_configured_concurrency_bound_and_finished_cancellation(self):
        entered, release = threading.Event(), threading.Event()
        def sender(*a, **kw):
            entered.set()
            release.wait(3)
            return response()
        config = configuration()
        config["max_concurrent_requests"] = 1
        r = Runtime(config, sender)
        worker = threading.Thread(target=lambda: r.generate(request()))
        worker.start()
        self.assertTrue(entered.wait(3))
        with self.assertRaisesRegex(BridgeError, "simultaneous"):
            r.generate(request("two"))
        release.set()
        worker.join(3)
        self.assertFalse(r.cancel("one")["cancelled"])
        self.assertEqual(r.budget.view()["committed"], 0.00034)

    def test_provider_response_secret_is_redacted(self):
        raw = response()
        raw["choices"][0]["message"]["content"] = "fixture-secret"
        with patch.dict(os.environ, {"HARNESS_TEST_KEY": "fixture-secret"}):
            r = Runtime(configuration(), lambda *a, **kw: raw)
            self.assertNotIn("fixture-secret", r.generate(request())["text"])
            self.assertNotIn("fixture-secret", json.dumps(r.status()))

    def test_unsafe_configuration_and_json_rejected(self):
        for base in ["http://example.com/v1", "https://x:y@example.com", "https://example.com?key=secret"]:
            config = configuration()
            config["providers"]["test"]["base_url"] = base
            with self.assertRaises(BridgeError): Runtime(config)
        config = configuration("ollama")
        config["providers"]["test"]["base_url"] = "https://example.com"
        with self.assertRaises(BridgeError): Runtime(config)
        for raw in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}']:
            with self.assertRaises(BridgeError): strict_json(raw)

    def test_model_discovery_reports_first_page_not_capabilities(self):
        for kind, fixture in [("openai", {"data": [{"id": "model-a"}]}),
                              ("anthropic", {"data": [{"id": "model-a"}], "has_more": True}),
                              ("gemini", {"models": [{"name": "models/model-a"}]}),
                              ("ollama", {"models": [{"name": "model-a"}]})]:
            r = Runtime(configuration(kind), lambda *a, **kw: fixture)
            result = r.discover("test")
            self.assertEqual(result["models"][0], {"id": "model-a", "configured": True})
            self.assertIn("does not prove", result["scope"])


class SourceTests(unittest.TestCase):
    def test_reject_private_mixed_dns_unknown_host_and_userinfo(self):
        addresses = ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1"]
        for address in addresses:
            with self.subTest(address=address), self.assertRaises(BridgeError):
                retrieve_source("https://docs.example.com/a", {"docs.example.com"},
                                resolver=lambda *a, **kw: [(socket.AF_INET, 1, 6, "", (address, 443))])
        for url in ["http://docs.example.com", "https://evil.example/a", "https://user:pass@docs.example.com", "https://docs.example.com:8443/a"]:
            with self.assertRaises(BridgeError): retrieve_source(url, {"docs.example.com"})

    def test_source_identity_and_query_target_are_exact(self):
        requests = []
        class Response:
            status = 200
            def getheader(self, name, default=None):
                return "text/plain; charset=utf-8" if name == "Content-Type" else default
            def read(self, _): return b"changed source"
        class Connection:
            def __init__(self, host, address, timeout):
                self.args = host, address, timeout
            def request(self, method, target, headers): requests.append((self.args, target, headers))
            def getresponse(self): return Response()
            def close(self): pass
        url = "https://docs.example.com/paper?version=2"
        result = retrieve_source(url, {"docs.example.com"}, "0"*64,
                                 resolver=lambda *a, **kw: [(2, 1, 6, "", ("8.8.8.8", 443))], connector=Connection)
        self.assertEqual(requests[0][1], "/paper?version=2")
        self.assertEqual(requests[0][0][1], "8.8.8.8")
        self.assertEqual(result["url"], url)
        self.assertEqual(result["sha256"], hashlib.sha256(b"changed source").hexdigest())
        self.assertTrue(result["changed"])
        self.assertEqual(result["trust"], "UNTRUSTED_SOURCE_CONTENT")


class LocalProviderTransportTests(unittest.TestCase):
    def test_real_loopback_http_wire_and_redirect_refusal(self):
        calls = []
        class Fixture(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                raw = self.rfile.read(int(self.headers["Content-Length"]))
                calls.append({"path": self.path, "body": json.loads(raw), "auth": self.headers.get("Authorization")})
                if self.path == "/redirect":
                    self.send_response(302)
                    self.send_header("Location", "/secret-collector")
                    self.end_headers()
                    return
                payload = json.dumps(response()).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = "http://127.0.0.1:" + str(server.server_port)
            config = configuration()
            config["providers"]["test"]["base_url"] = base
            with patch.dict(os.environ, {"HARNESS_TEST_KEY": "fixture-only-not-a-real-key"}):
                runtime = Runtime(config)
                result = runtime.generate(request())
                self.assertEqual(result["usage"]["output_tokens"], 12)
                self.assertEqual(calls[0]["path"], "/chat/completions")
                self.assertEqual(calls[0]["body"]["max_completion_tokens"], 64)
                self.assertEqual(calls[0]["auth"], "Bearer fixture-only-not-a-real-key")
                with self.assertRaisesRegex(BridgeError, "HTTP 302"):
                    transport(base + "/redirect", {"Authorization": "Bearer fixture-only-not-a-real-key"}, {})
                self.assertEqual(len(calls), 2)
                self.assertNotIn("/secret-collector", [c["path"] for c in calls])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)


class HTTPBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        Path(self.directory.name, "index.html").write_text("<h1>Fixture</h1>")
        self.server = HarnessServer(("127.0.0.1", 0), Runtime(), self.directory.name)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(3)
        self.directory.cleanup()

    def call(self, method, path, headers=None, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_session_and_token_same_origin(self):
        self.assertEqual(self.call("GET", "/api/session")[0], 403)
        status, headers, raw = self.call("GET", "/api/session", {"X-Harness-Client": "browser"})
        self.assertEqual(status, 200)
        token = json.loads(raw)["token"]
        self.assertEqual(self.call("GET", "/api/status", {"X-Harness-Token": token})[0], 200)
        self.assertEqual(self.call("GET", "/api/status", {"X-Harness-Token": token, "Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.call("GET", "/api/session", {"X-Harness-Client": "browser", "Sec-Fetch-Site": "cross-site"})[0], 403)
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_dns_rebinding_host_and_path_rejected(self):
        self.assertEqual(self.call("GET", "/", {"Host": "evil.example"})[0], 403)
        self.assertEqual(self.call("GET", "/../../bridge/config.example.json")[0], 404)
        self.assertEqual(self.call("GET", "/api/status")[0], 403)
        self.assertEqual(self.call("OPTIONS", "/api/generate")[0], 403)

    def test_post_requires_token_and_json(self):
        self.assertEqual(self.call("POST", "/api/generate", {"Content-Type": "application/json"}, "{}")[0], 403)
        headers = {"X-Harness-Token": self.server.token, "Content-Type": "text/plain"}
        self.assertEqual(self.call("POST", "/api/generate", headers, "{}")[0], 415)
        headers["Content-Type"] = "application/json"
        self.assertEqual(self.call("POST", "/api/generate", headers, '{"x":1,"x":2}')[0], 400)

    def test_static_application_is_self_contained_and_framing_denied(self):
        status, headers, raw = self.call("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Fixture", raw)
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("connect-src 'self'", headers["Content-Security-Policy"])


class NativeBoundaryTests(unittest.TestCase):
    def test_existing_composer_is_read_only_and_scope_is_explicit(self):
        native = NativeMechanism()
        if not native.available():
            self.skipTest("Canonical research source is intentionally absent from standalone distribution")
        spec = {"schema": "agi-alpha/mechanism-harness/v1",
                "purpose": {"initial": ["input"], "goal": ["output"], "max_cost": 10, "max_steps": 3,
                            "max_states": 100, "allowed_effects": ["pure"]},
                "mechanisms": [{"id": "convert", "requires": ["input"], "provides": ["output"], "cost": 2,
                                "effect": "pure", "origin": "developer_supplied"}], "candidate_bridges": []}
        before = native.source.read_bytes()
        result = native.compose(spec)
        self.assertTrue(result["check"]["accepted"])
        self.assertEqual(result["check"]["authority"], [])
        self.assertIsNone(result["check"]["current_proof"])
        self.assertEqual(result["source_sha256"], hashlib.sha256(before).hexdigest())
        self.assertEqual(native.source.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
