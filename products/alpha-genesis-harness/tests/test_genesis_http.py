# SPDX-License-Identifier: Apache-2.0
"""Exercise the actual authenticated loopback routes without model calls."""
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import Runtime
from bridge.server import HarnessServer
from test_proof_to_market import fixture


class GenesisHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name) / "work"
        self.server = HarnessServer(("127.0.0.1", 0), Runtime({"local_only": True}),
                                    config={"local_only": True}, workspace=self.workspace)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(3)
        self.temp.cleanup()

    def call(self, path, data=None, method="POST", token=True, origin=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=20)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Harness-Token"] = self.server.token
        if origin:
            headers["Origin"] = origin
        connection.request(method, path, None if method == "GET" else json.dumps(data or {}), headers)
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result

    def test_new_routes_require_session_and_cannot_call_private_methods(self):
        for path in ("/api/genesis-next/demo", "/api/genesis-next/opportunity", "/api/local-models/connect",
                     "/api/proof-to-market/assess"):
            self.assertEqual(self.call(path, token=False)[0], 403)
            self.assertEqual(self.call(path, origin="https://foreign.example")[0], 403)
        self.assertEqual(self.call("/api/genesis-next/status", method="GET", token=False)[0], 403)
        self.assertEqual(self.call("/api/genesis-next/_save")[0], 404)
        self.assertEqual(self.call("/api/local-models/__init__")[0], 404)
        self.assertFalse(self.workspace.exists())

    def test_status_and_local_presets_do_not_need_terminal_configuration(self):
        status, result = self.call("/api/status", method="GET")
        self.assertEqual(status, 200)
        self.assertTrue(result["local_only"])
        self.assertTrue(result["genesis_next_available"])
        status, presets = self.call("/api/local-models/presets")
        self.assertEqual(status, 200)
        self.assertEqual(len(presets["engines"]), 6)
        self.assertFalse(self.workspace.exists())

    def test_local_connection_restore_and_disconnect_preserve_permissions(self):
        status, result = self.call("/api/local-models/connect", {"engine": "ollama", "model": "local-test", "consent": True})
        self.assertEqual(status, 200, result)
        self.assertFalse(result["inference_verified"])
        self.assertTrue(result["status"]["local_only"])
        self.assertEqual(self.call("/api/local-models/disconnect", {"engine": "ollama"})[0], 200)

    def test_omega_workflow_and_export_are_reachable_without_network(self):
        status, state = self.call("/api/genesis-next/status", method="GET")
        self.assertEqual(status, 200, state)
        self.assertTrue(state["capabilities"])
        status, result = self.call("/api/genesis-next/opportunity", {
            "title": "Reuse verified experiments", "required_capabilities": ["dependency-evidence-reuse"],
            "blocking_conditions": ["Missing evidence index"]})
        self.assertEqual(status, 200, result)
        self.assertEqual(self.call("/api/genesis-next/discover")[0], 200)
        self.assertNotEqual(self.call("/api/genesis-next/demo", {"authorize": False})[0], 200)
        status, exported = self.call("/api/genesis-next/export")
        self.assertEqual(status, 200, exported)
        self.assertIn("sha256", exported)

    def test_proof_market_endpoint_remains_nontransactional(self):
        status, result = self.call("/api/proof-to-market/assess", fixture())
        self.assertEqual(status, 200, result)
        self.assertEqual(result["commercial_validation"], "NOT_ESTABLISHED")
        self.assertIsNone(result["available_reinvestable_surplus_minor"])


if __name__ == "__main__":
    unittest.main()
