# SPDX-License-Identifier: Apache-2.0
"""Adversarial protocol regression tests; no account access or live inference."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError
from bridge.chatgpt import ChatGPTPlanService, ISSUER, _error, verify_identity
import test_chatgpt as fixtures
from test_chatgpt import FakeTransport, b64, seed, verified_identity


class TerminalEventTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.transport = FakeTransport()
        self.service = ChatGPTPlanService(
            {"allow_plan_usage": True, "distribution": "open-source-local"},
            Path(self.temp.name) / "auth", self.transport,
            lambda _: True, verified_identity)
        seed(self.service)

    def tearDown(self):
        self.service.close()
        self.temp.cleanup()

    def request(self, ident):
        return {"run_id": ident, "model": "account-model", "prompt": "Test terminal handling"}

    def test_malformed_failures_are_controlled_failures_and_release_run(self):
        tails = [
            {"type": "response.failed", "response": None},
            {"type": "response.failed", "response": {"error": None}},
            {"type": "response.failed", "response": {"error": []}},
            {"type": "response.failed", "response": {"error": {"code": []}}},
            {"type": "error", "error": "unstructured_error"},
        ]
        for i, tail in enumerate(tails):
            with self.subTest(tail=tail):
                self.transport.stream = [tail]
                with self.assertRaises(BridgeError):
                    self.service.generate(self.request("malformed-" + str(i)))
                self.assertFalse(self.service._active)

    def test_null_usage_is_unknown_and_wrong_usage_type_is_rejected(self):
        for i, usage in enumerate((None, [], "invalid")):
            self.transport.stream = [
                {"type": "response.output_text.delta", "delta": "Result"},
                {"type": "response.completed", "response": {"status": "completed", "usage": usage}}]
            if usage is None:
                result = self.service.generate(self.request("usage-" + str(i)))
                self.assertEqual(result["usage"], {"input_tokens": None, "output_tokens": None})
            else:
                with self.assertRaisesRegex(BridgeError, "usage"):
                    self.service.generate(self.request("usage-" + str(i)))

    def test_late_provider_codes_preserve_recovery_status_and_parameters(self):
        cases = (("subscription_sharing_usage_unavailable", 503),
                 ("subscription_sharing_user_not_eligible", 403),
                 ("subscription_sharing_unsupported_capability", 400))
        for i, (code, status) in enumerate(cases):
            self.transport.stream = [{"type": "response.failed", "response": {
                "error": {"code": code, "param": "tools[0].type"}}}]
            with self.assertRaises(BridgeError) as raised:
                self.service.generate(self.request("provider-" + str(i)))
            self.assertEqual(raised.exception.code, code)
            self.assertEqual(raised.exception.status, status)
            self.assertEqual(raised.exception.diagnostics["error_param"], "tools[0].type")
        self.assertTrue(self.service.status()["ready"])

    def test_dynamic_registration_cannot_replace_an_existing_identity(self):
        before = self.service._state()["accounts"]["oaiapp_fixture"].copy()
        self.service.start_sign_in()
        pending = self.service.pending
        with self.assertRaisesRegex(BridgeError, "different validated identity"):
            self.service.complete_callback(pending, {
                "state": pending["state"], "code": "synthetic-code", "client_id": "oaiapp_fixture"})
        self.assertEqual(self.service._state()["accounts"]["oaiapp_fixture"], before)


class IdentityHardeningTests(unittest.TestCase):
    """Reuses the signing fixture so invalid claims still carry valid signatures."""
    setUpClass = classmethod(fixtures.IdentityTests.setUpClass.__func__)
    token = fixtures.IdentityTests.token
    transport = fixtures.IdentityTests.transport

    def test_malformed_not_before_and_audiences_fail_closed(self):
        for changes in ({"nbf": True}, {"nbf": []}, {"nbf": "500"},
                        {"aud": ["issued-client", "issued-client"], "azp": "issued-client"}):
            with self.subTest(changes=changes), self.assertRaises(BridgeError):
                verify_identity(self.token(**changes), "issued-client", "expected-nonce", self.transport(), now=500)

    def test_unsupported_critical_jws_headers_are_rejected(self):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        original = self.token().split(".")
        for extra in ({"crit": ["unimplemented"], "unimplemented": True}, {"b64": False}):
            header = {"alg": "RS256", "kid": "fixture", **extra}
            raw = b64(json.dumps(header).encode()) + "." + original[1]
            token = raw + "." + b64(self.key.sign(raw.encode(), padding.PKCS1v15(), hashes.SHA256()))
            with self.subTest(extra=extra), self.assertRaises(BridgeError):
                verify_identity(token, "issued-client", "expected-nonce", self.transport(), now=500)


class ErrorDiagnosticTests(unittest.TestCase):
    def test_direct_admission_shape_status_and_request_identifier_are_preserved(self):
        error = _error(b'{"detail":"private remote diagnostic"}', 403, "req_fixture")
        self.assertEqual(error.diagnostics, {"http_status": 403, "body_shape": "detail-object",
            "request_id": "req_fixture", "error_code": "CHATGPT_HTTP", "error_param": None})
        self.assertIn("req_fixture", error.message)
        self.assertNotIn("private remote diagnostic", error.message)

    def test_remote_diagnostics_do_not_echo_credentials_or_arbitrary_text(self):
        error = _error(b'{"error":{"code":"secret-token","param":"secret-token","message":"never echo"}}',
                       401, "secret-token", sensitive=["secret-token"])
        self.assertNotIn("secret-token", json.dumps(error.diagnostics) + error.message)
        self.assertNotIn("never echo", error.message)


if __name__ == "__main__":
    unittest.main()
