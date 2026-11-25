from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError, Runtime
from bridge.native_intelligence import NativeIntelligenceService, PROVIDERS
from bridge.server import HarnessServer
from bridge.services import AccessRuntime


MODEL = "local-fixture-text"
CREDENTIAL = "fixture-only-credential-not-live"
PROVIDER_ROUTES = {
    "openai": ("https://api.openai.com/v1", "/responses", "Authorization", "Bearer " + CREDENTIAL),
    "anthropic": ("https://api.anthropic.com/v1", "/messages", "x-api-key", CREDENTIAL),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta", f"/models/{MODEL}:generateContent", "x-goog-api-key", CREDENTIAL),
    "xai": ("https://api.x.ai/v1", "/chat/completions", "Authorization", "Bearer " + CREDENTIAL),
    "mistral": ("https://api.mistral.ai/v1", "/chat/completions", "Authorization", "Bearer " + CREDENTIAL),
    "deepseek": ("https://api.deepseek.com", "/chat/completions", "Authorization", "Bearer " + CREDENTIAL),
}


class FixtureSender:
    """Capture native HTTP protocol inputs. No network or credentialed usage."""

    def __init__(self):
        self.calls = []
        self.fail = None
        self.challenge_passes = True
        self.usage_known = True

    def __call__(self, url, headers, body=None, **limits):
        self.calls.append((url, dict(headers), body))
        if self.fail is not None:
            raise self.fail
        if body is None:
            if "generativelanguage.googleapis.com" in url:
                return {"models": [{"name": f"models/{MODEL}", "supportedGenerationMethods": ["generateContent"]},
                                   {"name": "models/embed", "supportedGenerationMethods": ["embedContent"]},
                                   {"name": f"models/{CREDENTIAL}", "supportedGenerationMethods": ["generateContent"]}]}
            return {"data": [{"id": MODEL}, {"id": CREDENTIAL}]}
        marker = re.search(r"FRONTIER-[0-9a-f]+", json.dumps(body))
        content = marker[0] if marker and self.challenge_passes else (
            "bad-challenge" if marker else json.dumps({"observed": True, "echo": CREDENTIAL}))
        if url.endswith("/responses"):
            return {"status": "completed", "model": MODEL, "output": [
                {"type": "message", "content": [{"type": "output_text", "text": content}]}],
                "usage": {"input_tokens": 5, "output_tokens": 4} if self.usage_known else {}}
        if url.endswith("/messages"):
            return {"model": MODEL, "stop_reason": "end_turn", "content": [{"type": "text", "text": content}],
                    "usage": {"input_tokens": 5, "output_tokens": 4}}
        if url.endswith(":generateContent"):
            return {"modelVersion": MODEL, "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": content}]}}],
                    "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 4}}
        return {"model": MODEL, "choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 4}}


def discovery(provider="openai", **changes):
    return {"provider": provider, "credential": CREDENTIAL, "project": "proj_fixture" if provider == "openai" else "Example workspace",
            "organization": "org-test" if provider == "openai" else "", "consent": True, **changes}


def verification(setup, **changes):
    return {"setup_id": setup, "model": MODEL, "input_rate": "1", "output_rate": "3", "budget_usd": "0.1",
            "max_output_tokens": 512, "max_turns": 3, "expiry_hours": 1, "consent": True, **changes}


class NativeIntelligenceTests(unittest.TestCase):
    def setUp(self):
        workspace = TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name)
        self.sender = FixtureSender()
        self.now = datetime(2026, 11, 25, 16, tzinfo=timezone.utc)
        base = Runtime({"local_only": True}, sender=self.sender)
        self.runtime = AccessRuntime(base, {"local_only": True})
        self.addCleanup(self.runtime.close)
        self.service = NativeIntelligenceService(self.runtime, self.root, clock=lambda: self.now)
        self.addCleanup(self.service.close)

    def approve(self, provider="openai", **limits):
        preflight = self.service.discover(discovery(provider))
        return self.service.verify(verification(preflight["setup_id"], **limits))["profile"]

    def test_setup_exercises_each_fixed_native_protocol_and_leaves_default_local_only(self):
        self.assertEqual(self.service.status()["profiles"], [])
        self.assertFalse(self.service.root.exists())
        self.assertFalse(self.sender.calls)
        self.assertEqual(set(PROVIDERS), set(PROVIDER_ROUTES))
        for name, (base, operation, header, value) in PROVIDER_ROUTES.items():
            with self.subTest(provider=name):
                found = self.service.discover(discovery(name))
                self.assertEqual(found["state"], "awaiting_verification")
                self.assertEqual(found["models"], (MODEL,))
                self.assertEqual(self.sender.calls[-1][0], base + "/models")
                self.assertEqual(self.sender.calls[-1][1][header], value)
                self.assertIsNone(self.sender.calls[-1][2])
                self.assertNotIn(CREDENTIAL, json.dumps(found))
                verified = self.service.verify(verification(found["setup_id"]))
                self.assertEqual(verified["state"], "ready")
                self.assertEqual(self.sender.calls[-1][0], base + operation)
                headers, request = self.sender.calls[-1][1:]
                self.assertEqual(headers[header], value)
                if name == "openai":
                    self.assertEqual(headers["OpenAI-Project"], "proj_fixture")
                    self.assertEqual(headers["OpenAI-Organization"], "org-test")
                    self.assertEqual(request["store"], False)
                self.assertNotIn("fixture-only-credential", json.dumps(verified))
                self.assertEqual(verified["profile"]["verification"]["model"], MODEL)
                self.assertEqual(verified["profile"]["usage"]["estimate"]["committed"], 0.000017)
        self.assertTrue(self.runtime.status()["local_only"])
        self.assertFalse(self.runtime.base.allow_paid)
        self.assertEqual(self.runtime.base.providers, {})

    def test_missing_consent_wrong_policy_and_replay_refuse_before_inference(self):
        for data in (discovery(consent=False), discovery(url="http://untrusted.invalid"),
                     discovery(project="wrong"), discovery(credential="Bearer controller"),
                     discovery(credential="sk-admin-fixture-unapproved"), discovery("unsupported")):
            with self.assertRaises(BridgeError):
                self.service.discover(data)
        self.assertFalse(self.sender.calls)
        setup = self.service.discover(discovery())["setup_id"]
        for settings in ({"consent": False}, {"budget_usd": "0"}, {"input_rate": "0", "output_rate": "0"},
                         {"max_turns": 0}, {"model": "untested-model"}, {"budget_usd": "1e999999999"}):
            with self.assertRaises(BridgeError):
                self.service.verify(verification(setup, **settings))
        self.assertEqual(len(self.sender.calls), 1)
        self.service.verify(verification(setup))
        with self.assertRaises(BridgeError):
            self.service.verify(verification(setup))
        self.assertEqual(len(self.sender.calls), 2)

    def test_private_restart_preserves_the_same_profile_budget_and_rejects_revoked_or_expired_grants(self):
        profile = self.approve(budget_usd="0.012")
        identifier = profile["id"]
        first = self.service.get_route(identifier)
        self.assertTrue(first.valid())
        request = {"provider": first.provider, "model": first.model, "prompt": "Use this specific authorized mission.",
                   "max_output_tokens": 128, "run_id": "fixture_mission_123"}
        self.sender.usage_known = False
        result = first.runtime.generate(request)
        self.assertNotIn(CREDENTIAL, result["text"])
        self.assertGreater(result["cost"]["accounted"], 0)
        before_restart = first.runtime.budget.view()
        self.service.close()
        second_service = NativeIntelligenceService(self.runtime, self.root, clock=lambda: self.now)
        self.addCleanup(second_service.close)
        second = second_service.get_route(identifier)
        self.assertEqual((second.provider, second.model, second.binding), (first.provider, first.model, first.binding))
        self.assertFalse(first.valid())
        self.assertEqual(second.runtime.budget.view(), before_restart)
        self.assertEqual(second_service.redact(f"value={CREDENTIAL}"), "value=[credential redacted]")
        if os.name != "nt":
            self.assertEqual(second_service.store.path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(second_service.root.stat().st_mode & 0o777, 0o700)
        self.now += timedelta(hours=1, seconds=1)
        self.assertFalse(second.valid())
        with self.assertRaises(BridgeError) as expired:
            second_service.get_route(identifier)
        self.assertEqual(expired.exception.code, "INTELLIGENCE_EXPIRED")
        second_service.disconnect({"profile_id": identifier, "consent": True})
        self.assertEqual(second_service.status()["profiles"], [])
        self.assertNotIn(CREDENTIAL.encode(), second_service.store.path.read_bytes())
        self.assertEqual(second_service.redact(CREDENTIAL), "[credential redacted]")
        with self.assertRaises(BridgeError):
            second.runtime.generate(dict(request, run_id="fixture_mission_revoked"))
        self.assertEqual(len(self.sender.calls), 3)

    def test_failed_sent_test_preserves_cost_but_never_saves_a_profile(self):
        self.sender.challenge_passes = False
        self.sender.usage_known = False
        setup = self.service.discover(discovery())["setup_id"]
        with self.assertRaises(BridgeError) as rejected:
            self.service.verify(verification(setup))
        self.assertEqual(rejected.exception.code, "INTELLIGENCE_VERIFICATION")
        snapshot = self.service.status()
        self.assertEqual(snapshot["profiles"], [])
        self.assertEqual(snapshot["recent_tests"][0]["state"], "failed")
        self.assertGreater(snapshot["recent_tests"][0]["usage"]["committed"], 0)
        self.assertNotIn(CREDENTIAL.encode(), self.service.store.path.read_bytes())

    def test_distinct_discovery_errors_hide_remote_content(self):
        for remote, expected in ((BridgeError("PROVIDER_AUTH", "Provider HTTP 401. ignored " + CREDENTIAL), "INTELLIGENCE_CREDENTIAL"),
                                 (BridgeError("PROVIDER_AUTH", "Provider HTTP 403. ignored " + CREDENTIAL), "INTELLIGENCE_PERMISSION"),
                                 (BridgeError("PROVIDER_QUOTA", CREDENTIAL), "INTELLIGENCE_QUOTA"),
                                 (BridgeError("PROVIDER_CONNECTION", CREDENTIAL), "INTELLIGENCE_CONNECTION")):
            self.sender.fail = remote
            with self.assertRaises(BridgeError) as raised:
                self.service.discover(discovery())
            self.assertEqual(raised.exception.code, expected)
            self.assertNotIn(CREDENTIAL, raised.exception.message)

    def test_loopback_http_requires_the_native_boundary_even_with_a_paired_origin(self):
        server = HarnessServer(("127.0.0.1", 0), self.runtime.base, config={"local_only": True}, workspace=self.root)
        worker = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        worker.start()

        def post(path, data, **headers):
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
            try:
                connection.request("POST", path, json.dumps(data), headers={"Content-Type": "application/json", **headers})
                response = connection.getresponse()
                return response.status, json.loads(response.read())
            finally:
                connection.close()

        try:
            path = "/api/frontier-intelligence/discover"
            for headers in ({}, {"X-Harness-Token": server.token, "Origin": "https://montrealai.github.io"},
                            {"X-Harness-Token": server.token, "Host": "example.invalid"}):
                self.assertEqual(post(path, discovery(), **headers)[0], 403)
            self.assertFalse(self.sender.calls)
            headers = {"X-Harness-Token": server.token}
            status, found = post(path, discovery(), **headers)
            self.assertEqual(status, 200)
            status, verified = post("/api/frontier-intelligence/verify", verification(found["setup_id"]), **headers)
            self.assertEqual(status, 200)
            listing = post("/api/frontier-intelligence/status", {}, **headers)[1]
            self.assertEqual(listing["profiles"][0]["id"], verified["profile"]["id"])
            self.assertNotIn(CREDENTIAL, json.dumps(listing))
            self.assertEqual(len(self.sender.calls), 2)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(2)


if __name__ == "__main__":
    unittest.main()
