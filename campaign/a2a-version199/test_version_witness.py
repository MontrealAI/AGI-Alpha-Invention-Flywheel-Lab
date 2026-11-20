"""P199 frozen independent negative witness against the *original* A2A198 HTTP handler.

Successful tests for V2-V4 establish accepted requests that the official v1-only
version-negotiation rule would reject. Green here means reproduced negative,
NOT owner implementation compliance, third-party SDK compatibility or commerce.
"""
from __future__ import annotations
import http.client
import importlib.util
import json
import os
from pathlib import Path
import threading
import unittest


def original_module(path, name):
    p = Path(path).resolve(strict=True)
    spec = importlib.util.spec_from_file_location(name, p)
    if spec is None or spec.loader is None:
        raise RuntimeError("PINNED_ORIGINAL_MODULE_REQUIRED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def v1_request():
    return {
        "jsonrpc": "2.0", "id": "p199-fixed-request", "method": "SendMessage",
        "params": {"message": {"messageId": "p199-fixed-message",
                               "role": "ROLE_USER", "parts": [{"mediaType": "application/json", "data": {
            "contract": {"id_field": "id", "rules": [
                {"from": "name", "to": "customer", "op": "strip"},
                {"from": "country", "to": "region", "op": "upper"}]},
            "source_rows": [{"id": "p199", "name": "  Marie  ", "country": "ca"}]
        }}]}}
    }


class OriginalHTTPVersionWitness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = original_module(os.environ["P199_ADAPTER"], "pinned_a2a198_adapter")
        cls.gate = cls.bridge.load_gate(os.environ["P199_GATE"])
        cls.server = cls.bridge.ThreadingHTTPServer(
            ("127.0.0.1", 0), cls.bridge.handler(cls.gate, 8795))
        cls.server.RequestHandlerClass = cls.bridge.handler(cls.gate, cls.server.server_port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=4)
        cls.server.server_close()

    def send(self, version):
        raw = json.dumps(v1_request(), allow_nan=False, separators=(",", ":")).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if version is not None:
            headers["A2A-Version"] = version
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=4)
        try:
            conn.request("POST", "/a2a", body=raw, headers=headers)
            response = conn.getresponse()
            status = response.status
            result = json.loads(response.read())
            return status, result
        finally:
            conn.close()

    def assert_original_accepts(self, version, label):
        status, result = self.send(version)
        self.assertEqual(status, 200, label)
        self.assertEqual(result.get("jsonrpc"), "2.0", label)
        self.assertEqual(result.get("id"), "p199-fixed-request", label)
        self.assertNotIn("error", result, label)
        response = result["result"]["message"]["parts"][0]["data"]
        self.assertIs(response["receipt"]["accepted"], True)
        self.assertEqual(response["delivery"][0]["customer"], "Marie")
        print("P199_" + label + ": ORIGINAL_ACCEPTED_V1_SEMANTICS", flush=True)
        return result

    def test_V1_explicit_1_0_positive_control(self):
        self.assert_original_accepts("1.0", "V1")

    def test_V2_absent_version_wrongly_receives_v1_response(self):
        # Official A2A §3.6: absent version means 0.3; this server advertises 1.0 only.
        self.assert_original_accepts(None, "V2_NEGATIVE")

    def test_V3_explicit_0_3_wrongly_receives_v1_response(self):
        self.assert_original_accepts("0.3", "V3_NEGATIVE")

    def test_V4_explicit_2_0_wrongly_receives_v1_response(self):
        self.assert_original_accepts("2.0", "V4_NEGATIVE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
