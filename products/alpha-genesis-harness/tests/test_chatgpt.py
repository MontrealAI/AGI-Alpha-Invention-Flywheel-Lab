# SPDX-License-Identifier: Apache-2.0
"""Offline contract/security checks. These are not live ChatGPT Pro qualification."""
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError
from bridge.chatgpt import ChatGPTPlanService, CredentialStore, ISSUER, RESOURCE, SCOPES, TOKEN, verify_identity


def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class FakeTransport:
    def __init__(self):
        self.calls = []
        self.token_response = {"access_token": "synthetic-access-credential", "refresh_token": "synthetic-refresh-credential",
                               "id_token": "synthetic-id-credential", "scope": SCOPES, "token_type": "Bearer", "expires_in": 3600}
        self.stream = [{"type": "response.output_text.delta", "delta": "Useful result"},
                       {"type": "response.completed", "response": {"status": "completed", "usage": {"input_tokens": 12, "output_tokens": 3}}}]

    def json(self, url, token=None, form=None):
        self.calls.append((url, token, form))
        if url == TOKEN:
            return dict(self.token_response)
        if url.endswith("/.well-known/openid-configuration"):
            return {"issuer": ISSUER, "jwks_uri": ISSUER + "/jwks", "revocation_endpoint": ISSUER + "/revoke"}
        if url.endswith("/revoke"):
            return {}
        if url == RESOURCE + "/models":
            return {"models": [{"slug": "account-model", "display_name": "Account model", "visibility": "list"},
                               {"slug": "hidden-model", "visibility": "hidden"}]}
        raise AssertionError("Unexpected request")

    def events(self, token, body, cancel):
        self.calls.append((RESOURCE + "/responses", token, body))
        yield from self.stream


def verified_identity(*args, **kwargs):
    return {"subject": "synthetic-user", "email": "fixture@example.invalid", "issuer": ISSUER}


def seed(service, ident="oaiapp_fixture", expiry=None):
    with service.store.locked():
        state = service.store.read()
        state["accounts"][ident] = {"client_id": ident, "subject": ident + "-subject", "email": "fixture@example.invalid",
                                    "access_token": "synthetic-access-credential", "refresh_token": "synthetic-refresh-credential",
                                    "id_token": "synthetic-id-credential", "scopes": SCOPES.split(), "expires_at": expiry or time.time() + 3600}
        state["active"] = ident
        service.store.write(state)


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.transport = FakeTransport()
        self.urls = []
        self.service = ChatGPTPlanService({"allow_plan_usage": True, "distribution": "open-source-local"},
                     Path(self.temp.name) / "auth", self.transport, lambda url: self.urls.append(url) or True, verified_identity)

    def tearDown(self):
        self.service.close()
        self.temp.cleanup()

    def request(self, run_id="test-one"):
        return {"run_id": run_id, "model": "account-model", "prompt": "Build a useful result", "max_output_tokens": 128}

    def test_default_off_and_commercial_approval_gate(self):
        disabled = ChatGPTPlanService(storage_path=Path(self.temp.name) / "absent", transport=self.transport)
        self.assertFalse(disabled.status()["enabled"])
        self.assertFalse(disabled.store.directory.exists())
        for value in (None, False, 0, [], {}, "", " "):
            self.service.config = {"allow_plan_usage": True, "commercial_approval_reference": value}
            with self.assertRaises(BridgeError):
                self.service.discover()
        self.assertEqual(self.transport.calls, [])

    def test_browser_pkce_callback_and_reuse_host_registration(self):
        attempt = self.service.start_sign_in()
        query = parse_qs(urlsplit(self.urls[-1]).query)
        pending = dict(self.service.pending)
        self.assertEqual(query["client_id"], ["dynamic_agent_client"])
        self.assertEqual(query["scope"], [SCOPES])
        self.assertEqual(query["code_challenge"], [b64(hashlib.sha256(pending["verifier"].encode()).digest())])
        callback = urlsplit(query["redirect_uri"][0])
        conn = http.client.HTTPConnection(callback.hostname, callback.port, timeout=3)
        conn.request("GET", callback.path + "?state=" + query["state"][0] + "&code=fixture-code&client_id=oaiapp_new")
        response = conn.getresponse()
        self.assertEqual(response.status, 200)
        response.read()
        conn.close()
        self.assertTrue(self.service.status()["ready"])
        self.assertEqual(self.service.status()["pending"]["status"], "complete")
        exchange = self.transport.calls[0][2]
        self.assertEqual(exchange["client_id"], "oaiapp_new")
        self.assertEqual(exchange["redirect_uri"], query["redirect_uri"][0])
        self.service.start_sign_in("oaiapp_new")
        second = parse_qs(urlsplit(self.urls[-1]).query)
        self.assertEqual(second["ext_agent_host_id"], query["ext_agent_host_id"])
        self.assertEqual(second["client_id"], ["oaiapp_new"])
        self.assertNotIn("agent_name_hint", second)
        self.assertNotIn("synthetic-id-credential", json.dumps(self.service.status()))

    def test_consent_refusal_and_wrong_state_never_exchange(self):
        self.service.start_sign_in()
        pending = self.service.pending
        for values in ({"state": "wrong", "code": "x"}, {"state": pending["state"], "error": "access_denied"}):
            with self.assertRaises(BridgeError):
                self.service.complete_callback(pending, values)
        self.assertEqual(self.transport.calls, [])

    def test_missing_scope_keeps_identity_without_plan_permission(self):
        self.transport.token_response["scope"] = "openid email profile"
        self.service.start_sign_in()
        pending = self.service.pending
        self.service.complete_callback(pending, {"state": pending["state"], "code": "code", "client_id": "oaiapp_new"})
        status = self.service.status()
        self.assertTrue(status["accounts"][0]["connected"])
        self.assertFalse(status["ready"])
        with self.assertRaises(BridgeError):
            self.service.generate(self.request())

    def test_real_request_contract_and_separate_usage(self):
        seed(self.service)
        progress = []
        result = self.service.generate(self.request(), on_event=progress.append)
        body = self.transport.calls[-1][2]
        self.assertEqual(set(body), {"model", "input", "store", "stream"})
        self.assertFalse(body["store"])
        self.assertTrue(body["stream"])
        self.assertIsNone(result["cost"]["amount"])
        self.assertEqual(result["usage"], {"input_tokens": 12, "output_tokens": 3})
        self.assertEqual(progress[-1]["delta"], "Useful result")
        with self.assertRaisesRegex(BridgeError, "already used"):
            self.service.generate(self.request())

    def test_interrupted_incomplete_failed_and_quota_streams(self):
        seed(self.service)
        for index, tail in enumerate((None, {"type": "response.incomplete"},
                     {"type": "response.completed", "response": {}},
                     {"type": "response.failed", "response": {"error": {"code": "subscription_sharing_usage_limit_exceeded"}}})):
            self.transport.stream = [{"type": "response.output_text.delta", "delta": "Partial"}] + ([tail] if tail else [])
            with self.assertRaises(BridgeError):
                self.service.generate(self.request("case" + str(index)))
        self.assertFalse(self.service.status()["ready"])
        before = len(self.transport.calls)
        with self.assertRaises(BridgeError):
            self.service.generate(self.request("after-quota"))
        self.assertEqual(len(self.transport.calls), before)

    def test_secret_split_over_deltas_never_streams_raw(self):
        seed(self.service)
        self.transport.stream = [{"type": "response.output_text.delta", "delta": "synthetic-access-"},
                                 {"type": "response.output_text.delta", "delta": "credential"}, self.transport.stream[-1]]
        progress = []
        result = self.service.generate(self.request(), on_event=progress.append)
        self.assertEqual(result["text"], "[credential redacted]")
        self.assertNotIn("synthetic-access-", json.dumps(progress))

    def test_refresh_rotates_once_and_persists_across_instances(self):
        seed(self.service, expiry=1)
        self.transport.token_response.pop("id_token")
        self.transport.token_response.update(access_token="rotated-access", refresh_token="rotated-refresh")
        barrier = threading.Barrier(2)
        values = []
        def read():
            barrier.wait()
            values.append(self.service._account()["access_token"])
        threads = [threading.Thread(target=read) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(3)
        self.assertEqual(values, ["rotated-access", "rotated-access"])
        self.assertEqual(sum(url == TOKEN for url, _, _ in self.transport.calls), 1)
        form = self.transport.calls[0][2]
        self.assertEqual(form["client_id"], "oaiapp_fixture")
        self.assertNotIn("scope", form)
        other = ChatGPTPlanService(self.service.config, self.service.store.directory, self.transport)
        self.assertEqual(other._account()["refresh_token"], "rotated-refresh")

    def test_invalid_refresh_clears_tokens_but_temporary_failure_keeps_them(self):
        for code, cleared in (("CHATGPT_CONNECTION", False), ("invalid_grant", True)):
            seed(self.service, expiry=1)
            def fail(*args, **kwargs):
                raise BridgeError(code, "Fixture", 503)
            self.transport.json = fail
            with self.assertRaises(BridgeError): self.service._account()
            account = self.service._state()["accounts"]["oaiapp_fixture"]
            self.assertEqual("access_token" not in account, cleared)
            self.assertEqual(account["client_id"], "oaiapp_fixture")

    def test_account_switch_during_discovery_cancels_before_inference(self):
        seed(self.service, "oaiapp_other")
        seed(self.service)
        original = self.transport.json
        def switch(url, **kwargs):
            if url.endswith("/models"):
                self.service.select_account("oaiapp_other")
            return original(url, **kwargs)
        self.transport.json = switch
        with self.assertRaises(BridgeError): self.service.generate(self.request())
        self.assertFalse(any(url.endswith("/responses") for url, _, _ in self.transport.calls))

    def test_disconnect_revocation_and_offline_local_clear(self):
        seed(self.service)
        self.assertTrue(self.service.disconnect()["remote_revocation_confirmed"])
        self.assertNotIn("access_token", self.service._state()["accounts"]["oaiapp_fixture"])
        seed(self.service)
        self.transport.calls.clear()
        self.assertFalse(self.service.disconnect(revoke_remote=False)["remote_revocation_confirmed"])
        self.assertEqual(self.transport.calls, [])


class IdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa
        except ImportError:
            raise unittest.SkipTest("Optional cryptography is required for signed identity tests")
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def token(self, **overrides):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        payload = {"iss": ISSUER, "sub": "fixture-user", "aud": "issued-client", "iat": 100, "exp": 1000, "nonce": "expected-nonce"}
        payload.update(overrides)
        raw = b64(json.dumps({"alg": "RS256", "kid": "fixture"}).encode()) + "." + b64(json.dumps(payload).encode())
        return raw + "." + b64(self.key.sign(raw.encode(), padding.PKCS1v15(), hashes.SHA256()))

    def transport(self):
        numbers = self.key.public_key().public_numbers()
        key = {"kid": "fixture", "kty": "RSA", "use": "sig", "n": b64(numbers.n.to_bytes(256, "big")), "e": b64(numbers.e.to_bytes(3, "big"))}
        class Transport:
            def json(self, url):
                return {"keys": [key]} if url.endswith("/jwks") else {"issuer": ISSUER, "jwks_uri": ISSUER + "/jwks"}
        return Transport()

    def test_rs256_signature_identity_and_claims(self):
        actual = verify_identity(self.token(), "issued-client", "expected-nonce", self.transport(), now=500)
        self.assertEqual(actual["subject"], "fixture-user")
        for changes in ({"aud": "attacker-client"}, {"nonce": "wrong"}, {"exp": 1}, {"iss": "https://evil.invalid"}, {"iat": 9999}, {"aud": ["issued-client", "other"]}):
            with self.assertRaises(BridgeError):
                verify_identity(self.token(**changes), "issued-client", "expected-nonce", self.transport(), now=500)
        bad = self.token().split(".")
        bad[1] = b64(b'{"sub":"attacker"}')
        with self.assertRaises(BridgeError):
            verify_identity(".".join(bad), "issued-client", "expected-nonce", self.transport(), now=500)


if __name__ == "__main__":
    unittest.main()
