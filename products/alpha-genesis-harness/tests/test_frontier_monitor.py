# SPDX-License-Identifier: Apache-2.0
"""Persistent consent, source identity, periodic observation and refusal tests."""
import copy
import hashlib
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.adapters import BridgeError, Runtime
from bridge.frontier_monitor import FrontierMonitorService, HISTORY_LIMIT
from bridge.genesis_next import GenesisNextService
from bridge.workflow_demo import FixtureRuntime
from bridge.workflows import WorkflowService
from bridge.server import HarnessServer


class FetchFixture:
    def __init__(self):
        self.calls = []
        self.text = "Original declared source"
        self.error = None

    def __call__(self, url, hosts, previous):
        self.calls.append((url, hosts, previous))
        if self.error:
            raise self.error
        return {"url": url, "sha256": hashlib.sha256(self.text.encode()).hexdigest(),
                "retrieved_at": "2026-01-01T00:00:00+00:00", "text": self.text}


class FrontierMonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = FixtureRuntime([])
        self.runtime.local_only = False
        self.runtime.source_hosts = frozenset({"frontier.example"})
        self.workflows = WorkflowService(self.runtime, Path(self.temp.name) / "workspace")
        self.genesis = GenesisNextService(self.workflows)
        self.fetch = FetchFixture()
        self.monitor = FrontierMonitorService(self.workflows, self.genesis, fetcher=self.fetch)

    def tearDown(self):
        self.monitor.close()
        self.workflows.close()
        self.temp.cleanup()

    def add(self, **values):
        data = {"url": "https://frontier.example/model-card", "title": "Source release notes",
                "capability_ids": ["dependency-evidence-reuse"], "interval_seconds": 3600, "authorize": True}
        return self.monitor.add({**data, **values})["job"]

    def poll(self, job):
        return self.monitor.poll({"job_id": job["id"]})

    def test_add_is_paused_and_never_fetches(self):
        job = self.add()
        self.assertFalse(job["enabled"])
        self.assertFalse(job["consent"]["resume_after_restart"])
        self.assertFalse(self.fetch.calls)
        self.assertFalse(self.monitor.status()["worker_running"])

    def test_explicit_consent_and_valid_associations_required(self):
        for change in ({"authorize": False}, {"authorize": 1}, {"resume_after_restart": "yes"},
                       {"capability_ids": []}, {"capability_ids": ["../code"]}, {"interval_seconds": 1},
                       {"interval_seconds": True}, {"interval_seconds": float("inf")}):
            with self.subTest(change=change), self.assertRaises(BridgeError):
                self.add(**change)
        self.assertFalse(self.fetch.calls)

    def test_local_only_refuses_add_poll_and_start_before_dispatch(self):
        job = self.add()
        self.runtime.local_only = True
        for action in (lambda: self.add(url="https://frontier.example/another"), lambda: self.poll(job),
                       lambda: self.monitor.start({"job_id": job["id"]})):
            with self.assertRaises(BridgeError) as error:
                action()
            self.assertEqual(error.exception.code, "LOCAL_ONLY")
        self.assertFalse(self.fetch.calls)

    def test_access_runtime_config_local_only_also_refuses(self):
        self.runtime.config = {"local_only": True}
        with self.assertRaises(BridgeError):
            self.add()
        self.assertFalse(self.fetch.calls)

    def test_exact_host_https_and_credential_boundary(self):
        for url in ("http://frontier.example/a", "https://sub.frontier.example/a", "https://other.example/a",
                    "https://user:password@frontier.example/a", "https://frontier.example/a#private",
                    "https://frontier.example:8443/a", "https://frontier.example/a\nHeader: inject"):
            with self.subTest(url=url), self.assertRaises(BridgeError):
                self.add(url=url)
        self.assertFalse(self.fetch.calls)

    def test_removed_allowlist_host_refuses_saved_job(self):
        job = self.add()
        self.runtime.source_hosts = frozenset()
        with self.assertRaises(BridgeError):
            self.poll(job)
        self.assertFalse(self.fetch.calls)

    def test_initial_unchanged_changed_replay_only_reported_evidence(self):
        job = self.add()
        initial = self.poll(job)
        same = self.poll(job)
        self.fetch.text = "A new reported capability, not established truth"
        changed = self.poll(job)
        self.assertEqual(initial["observation"]["status"], "INITIAL_OBSERVATION")
        self.assertEqual(same["observation"]["status"], "UNCHANGED")
        self.assertFalse(same["observation"]["replayed"])
        self.assertEqual(changed["observation"]["status"], "CHANGED")
        self.assertTrue(changed["observation"]["replayed"])
        state = self.genesis.status()
        self.assertEqual(len(state["frontier_events"]), 2)
        self.assertTrue(all(e["evidence_status"] == "reported" for e in state["frontier_events"]))
        self.assertTrue(all(o["status"] == "reconsider" for o in state["opportunities"]))
        self.assertFalse(any(c["status"] == "independently_verified" for c in state["capabilities"]))
        self.assertEqual(changed["state"]["jobs"][0]["change_count"], 1)

    def test_source_text_is_not_retained_in_state_or_status(self):
        self.fetch.text = "Untrusted source content should remain transient"
        self.poll(self.add())
        self.assertNotIn(self.fetch.text, self.monitor.path.read_text())
        self.assertNotIn(self.fetch.text, json.dumps(self.monitor.status()))

    def test_failures_preserve_last_good_identity_and_compact_history(self):
        job = self.add()
        initial = self.poll(job)["observation"]["sha256"]
        self.fetch.error = BridgeError("SOURCE_HTTP", "Sensitive remote body never retained")
        for _ in range(HISTORY_LIMIT + 3):
            result = self.poll(job)
        state = result["state"]["jobs"][0]
        self.assertEqual(state["last_sha256"], initial)
        self.assertEqual(state["failure_count"], HISTORY_LIMIT + 3)
        self.assertEqual(len(state["history"]), HISTORY_LIMIT)
        self.assertGreater(state["history_omitted"], 0)
        self.assertNotIn("Sensitive remote", self.monitor.path.read_text())

    def test_replay_failure_is_pending_and_retried_without_fake_reactivation(self):
        job = self.add()
        with patch.object(self.genesis, "replay", side_effect=BridgeError("FAIL", "test")):
            first = self.poll(job)
        self.assertFalse(first["observation"]["replayed"])
        self.assertIsNone(first["state"]["jobs"][0]["last_replayed_sha256"])
        second = self.poll(job)
        self.assertEqual(second["observation"]["status"], "UNCHANGED")
        self.assertTrue(second["observation"]["replayed"])
        self.assertEqual(len(self.genesis.status()["frontier_events"]), 1)

    def test_tampered_persistent_consent_is_rejected(self):
        self.add()
        value = json.loads(self.monitor.path.read_text())
        value["state"]["jobs"][0]["consent"]["resume_after_restart"] = True
        self.monitor.path.write_text(json.dumps(value))
        with self.assertRaises(BridgeError) as error:
            self.monitor.status()
        self.assertEqual(error.exception.code, "MONITOR_INTEGRITY")

    def test_duplicate_monitor_cannot_create_second_background_owner(self):
        with self.assertRaises(BridgeError) as error:
            FrontierMonitorService(self.workflows, self.genesis, fetcher=self.fetch)
        self.assertEqual(error.exception.code, "MONITOR_OWNED")

    def test_stop_during_fetch_discards_replay(self):
        job = self.add()
        entered, release = threading.Event(), threading.Event()
        def blocking(*args):
            entered.set()
            release.wait(3)
            return self.fetch(*args)
        self.monitor.fetcher = blocking
        result = []
        thread = threading.Thread(target=lambda: result.append(self.poll(job)))
        thread.start()
        self.assertTrue(entered.wait(2))
        self.monitor.stop({"job_id": job["id"]})
        release.set()
        thread.join(3)
        self.assertEqual(result[0]["observation"]["status"], "DISCARDED")
        self.assertFalse(self.genesis.status()["frontier_events"])

    def test_removed_job_cannot_commit_an_inflight_observation(self):
        job = self.add()
        entered, release = threading.Event(), threading.Event()
        def blocking(*args):
            entered.set()
            release.wait(3)
            return self.fetch(*args)
        self.monitor.fetcher = blocking
        result = []
        thread = threading.Thread(target=lambda: result.append(self.poll(job)))
        thread.start()
        self.assertTrue(entered.wait(2))
        self.monitor.remove({"job_id": job["id"]})
        release.set()
        thread.join(3)
        self.assertEqual(result[0]["observation"]["status"], "DISCARDED")
        self.assertFalse(self.monitor.status()["jobs"])
        self.assertFalse(self.genesis.status()["frontier_events"])

    def test_close_during_fetch_never_commits_late_result(self):
        job = self.add()
        entered, release = threading.Event(), threading.Event()
        def blocking(*args):
            entered.set()
            release.wait(3)
            return self.fetch(*args)
        self.monitor.fetcher = blocking
        thread = threading.Thread(target=lambda: self.poll(job))
        thread.start()
        self.assertTrue(entered.wait(2))
        before = self.monitor.path.read_bytes()
        self.monitor.close()
        release.set()
        thread.join(3)
        self.assertEqual(self.monitor.path.read_bytes(), before)
        self.assertFalse(self.genesis.status()["frontier_events"])

    def test_restart_without_resume_consent_keeps_configuration_paused(self):
        job = self.add()
        with patch.object(self.monitor, "_ensure_worker"):
            self.monitor.start({"job_id": job["id"]})
        self.monitor.close()
        self.monitor = FrontierMonitorService(self.workflows, self.genesis, fetcher=self.fetch)
        state = self.monitor.status()
        self.assertEqual(len(state["jobs"]), 1)
        self.assertFalse(state["jobs"][0]["enabled"])
        self.assertFalse(state["worker_running"])
        self.assertFalse(self.fetch.calls)

    def test_periodic_worker_operates_once_then_respects_next_due(self):
        job = self.add()
        self.monitor.start({"job_id": job["id"]})
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not self.fetch.calls:
            time.sleep(0.01)
        self.assertEqual(len(self.fetch.calls), 1)
        self.monitor.stop({"job_id": job["id"]})
        time.sleep(0.02)
        self.assertEqual(len(self.fetch.calls), 1)

    def test_stored_explicit_restart_consent_resumes_worker(self):
        job = self.add(resume_after_restart=True)
        with patch.object(self.monitor, "_ensure_worker"):
            self.monitor.start({"job_id": job["id"]})
        self.monitor.close()
        self.monitor = FrontierMonitorService(self.workflows, self.genesis, fetcher=self.fetch)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not self.fetch.calls:
            time.sleep(0.01)
        self.assertEqual(len(self.fetch.calls), 1)
        self.assertTrue(self.monitor.status()["jobs"][0]["enabled"])

    def test_paused_scheduled_request_cannot_dispatch_after_due_list_snapshot(self):
        job = self.add()
        with self.assertRaises(BridgeError):
            self.monitor.poll({"job_id": job["id"]}, _scheduled=True)
        self.assertFalse(self.fetch.calls)

    def test_real_public_address_transport_refuses_loopback_without_http(self):
        self.runtime.source_hosts = frozenset({"127.0.0.1"})
        job = self.add(url="https://127.0.0.1/private")
        from bridge.adapters import retrieve_source
        self.monitor.fetcher = retrieve_source
        result = self.poll(job)
        self.assertEqual(result["observation"], {"status": "FAILED", "error_code": "SOURCE_URL"})
        self.assertFalse(self.genesis.status()["frontier_events"])


class FrontierMonitorHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = HarnessServer(("127.0.0.1", 0), Runtime({"source_hosts": ["frontier.example"]}),
                                    workspace=Path(self.temp.name) / "workspace")
        self.server.frontier_monitor.fetcher = FetchFixture()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.temp.cleanup()

    def request(self, action, data=None, *, authenticated=True, origin=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        headers = {"Content-Type": "application/json"}
        if authenticated:
            headers["X-Harness-Token"] = self.server.token
        if origin is not None:
            headers["Origin"] = origin
        connection.request("GET" if data is None else "POST", "/api/frontier-monitor/" + action,
                           None if data is None else json.dumps(data), headers)
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result

    def test_http_origin_and_token_cannot_be_bypassed(self):
        status, _ = self.request("status", authenticated=False)
        self.assertEqual(status, 403)
        status, _ = self.request("status", origin="https://foreign.example")
        self.assertEqual(status, 403)
        status, _ = self.request("promote", {})
        self.assertEqual(status, 404)

    def test_http_complete_add_poll_status_remove(self):
        status, added = self.request("add", {"title": "HTTP observed source", "url": "https://frontier.example/current",
                                            "capability_ids": ["dependency-evidence-reuse"], "authorize": True})
        self.assertEqual(status, 200)
        ident = added["job"]["id"]
        status, result = self.request("poll", {"job_id": ident})
        self.assertEqual(status, 200)
        self.assertEqual(result["observation"]["status"], "INITIAL_OBSERVATION")
        self.assertTrue(result["observation"]["replayed"])
        status, result = self.request("status")
        self.assertEqual(status, 200)
        self.assertEqual(result["jobs"][0]["poll_count"], 1)
        status, result = self.request("remove", {"job_id": ident})
        self.assertEqual(status, 200)
        self.assertEqual(result["state"]["jobs"], [])


if __name__ == "__main__":
    unittest.main()
