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
                     "/api/proof-to-market/assess", "/api/upgrade-foundry/register", "/api/upgrade-foundry/construct",
                     "/api/upgrade-foundry/qualify", "/api/upgrade-foundry/activate", "/api/upgrade-foundry/evaluate",
                     "/api/upgrade-foundry/rollback", "/api/upgrade-foundry/cancel", "/api/upgrade-foundry/export",
                     "/api/frontier-monitor/add", "/api/frontier-monitor/poll", "/api/frontier-monitor/start",
                     "/api/frontier-monitor/stop", "/api/frontier-monitor/remove"):
            self.assertEqual(self.call(path, token=False)[0], 403)
            self.assertEqual(self.call(path, origin="https://foreign.example")[0], 403)
        self.assertEqual(self.call("/api/genesis-next/status", method="GET", token=False)[0], 403)
        self.assertEqual(self.call("/api/genesis-next/_save")[0], 404)
        self.assertEqual(self.call("/api/local-models/__init__")[0], 404)
        self.assertEqual(self.call("/api/upgrade-foundry/_save")[0], 404)
        self.assertEqual(self.call("/api/frontier-monitor/close")[0], 404)
        for path in ("/api/upgrade-foundry/status", "/api/frontier-monitor/status"):
            self.assertEqual(self.call(path, method="GET", token=False)[0], 403)
            self.assertEqual(self.call(path, method="GET", origin="https://foreign.example")[0], 403)
        self.assertFalse(self.workspace.exists())

    def test_foundry_local_only_refuses_construction_before_service_creation(self):
        status, result = self.call("/api/upgrade-foundry/construct", {"experiment_id": "untrusted", "authorize": True})
        self.assertNotEqual(status, 200)
        self.assertEqual(result["error"]["code"], "LOCAL_ONLY")
        self.assertIsNone(self.server._upgrade_foundry)
        self.assertFalse(self.workspace.exists())

    def test_monitor_local_only_refuses_network_and_leaves_no_jobs(self):
        status, result = self.call("/api/frontier-monitor/add", {
            "url": "https://example.com/news", "title": "Source", "capability_ids": ["example"], "authorize": True})
        self.assertNotEqual(status, 200)
        self.assertEqual(result["error"]["code"], "LOCAL_ONLY")
        status, result = self.call("/api/frontier-monitor/status", method="GET")
        self.assertEqual(status, 200, result)
        self.assertTrue(result["local_only"])
        self.assertFalse(result["worker_running"])
        self.assertEqual(result["jobs"], [])

    def test_retained_execution_dispatches_only_to_sandbox_service(self):
        from unittest.mock import Mock
        service = Mock()
        service.evaluate_retained.return_value = {"status": "BLOCKED", "reason": "sandbox required"}
        self.server._upgrade_foundry = service
        data = {"instrument": {"untrusted": True}, "inputs": {"x": 3}}
        status, result = self.call("/api/upgrade-foundry/evaluate", data)
        self.assertEqual(status, 200, result)
        service.evaluate_retained.assert_called_once_with(data)
        service.evaluate.assert_not_called()

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
