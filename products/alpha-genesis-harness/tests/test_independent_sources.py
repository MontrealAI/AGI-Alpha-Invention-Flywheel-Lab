# SPDX-License-Identifier: Apache-2.0
"""Independent source-tool boundary probes; no external transport is opened."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError, retrieve_source
from bridge.workflows import WorkflowService, portable_digest
from test_independent_security import FixtureWorkflowRuntime


class IndependentSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = FixtureWorkflowRuntime({"actions": []})
        self.runtime.source_hosts = {"source.example"}
        self.service = WorkflowService(self.runtime, Path(self.temp.name) / "work")
        self.spec = {"objective": "Retain bounded source evidence", "local_only": False,
                     "roles": {"builder": {"provider": "local", "model": "fixture"}},
                     "tool_permissions": ["retrieve_source", "run_instrument"],
                     "acceptance": [{"artifact": "source.json", "kind": "instrument", "input": {}, "expected": {"value": 1}}]}
        self.source = {"url": "https://source.example/page", "sha256": hashlib.sha256(b"Untrusted source").hexdigest(),
                       "text": "Untrusted source", "retrieved_at": "2026-11-10T00:00:00Z", "trust": "UNTRUSTED_SOURCE_CONTENT"}

    def tearDown(self):
        self.service.close()
        self.temp.cleanup()

    def action(self, **extra):
        return {"tool": "retrieve_source", "name": "source.json", "url": self.source["url"], **extra}

    def run_action(self, action):
        self.runtime.reply = {"actions": [action]}
        return self.service.step(self.service.create(self.spec)["id"])

    def export_source(self):
        with patch("bridge.workflows.retrieve_source", return_value=self.source):
            state = self.run_action(self.action())
        return state, self.service.export(state["id"])

    def test_status_only_local_mode_refuses_fetch_even_with_explicit_permission(self):
        self.runtime.status = lambda: {"local_only": True, "providers": [{"id": "local", "local": True}]}
        with patch("bridge.workflows.retrieve_source") as fetch:
            result = self.run_action(self.action())
        fetch.assert_not_called()
        self.assertEqual(result["artifacts"], {})

    def test_model_cannot_override_allowlist_or_retrieval_headers(self):
        for extra in [{"allowed_hosts": ["untrusted.example"]}, {"headers": {"Authorization": "fabricated"}}, {"local_only": False}]:
            with self.subTest(extra=extra), patch("bridge.workflows.retrieve_source") as fetch:
                state = self.run_action(self.action(**extra))
                fetch.assert_not_called()
                self.assertEqual(state["artifacts"], {})

    def test_exact_host_and_public_dns_guards_apply_to_workflow_actions(self):
        def guarded(url, hosts):
            return retrieve_source(url, hosts,
                resolver=lambda *a, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
                connector=lambda *a: self.fail("Refused source URL must not open a socket"))
        for url in ["https://source.example.evil/page", "https://source.example/page", "https://user@source.example/page"]:
            with self.subTest(url=url), patch("bridge.workflows.retrieve_source", side_effect=guarded):
                state = self.run_action(self.action(url=url))
                self.assertEqual(state["artifacts"], {})
                self.assertFalse(state["verification"]["passed"])

    def test_source_kind_never_executes_as_an_instrument(self):
        state, exported = self.export_source()
        self.assertEqual(state["artifacts"]["source.json"]["kind"], "source")
        self.assertFalse(state["verification"]["passed"])
        internal = self.service._load(state["id"])
        with self.assertRaises(BridgeError):
            self.service._tool(internal, {"tool": "run_instrument", "name": "source.json", "input": {}})
        self.assertEqual(json.loads(exported["files"]["source.json"]), self.source)

    def test_source_import_retains_untrusted_bytes_without_network_or_verification(self):
        _, exported = self.export_source()
        with patch("bridge.workflows.retrieve_source") as fetch:
            imported = self.service.import_archive(exported)
        fetch.assert_not_called()
        self.assertEqual(imported["status"], "paused")
        self.assertFalse(imported["verification"]["passed"])
        self.assertEqual(imported["artifacts"]["source.json"]["kind"], "source")
        self.assertEqual(self.service.export(imported["id"])["files"], exported["files"])

    def test_rehashed_source_kind_cannot_smuggle_an_executable_filename(self):
        _, exported = self.export_source()
        exported["files"]["source.py"] = exported["files"].pop("source.json")
        exported["state"]["artifacts"]["source.py"] = exported["state"]["artifacts"].pop("source.json")
        exported["sha256"] = portable_digest({k: v for k, v in exported.items() if k != "sha256"})
        with self.assertRaises(BridgeError):
            self.service.import_archive(exported)


if __name__ == "__main__":
    unittest.main()
