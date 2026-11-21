# SPDX-License-Identifier: Apache-2.0
"""Independent authored integration cases; no live invention or economic claims."""
import copy
import hashlib
import http.client
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bridge.adapters import BridgeError, Runtime
from bridge import frontier_mission as mission
from bridge import frontier_builder as builder
from bridge.frontier_monitor import FrontierMonitorService
from bridge.server import HarnessServer
from bridge.workflows import WorkflowService


AS_OF = "2026-11-21T12:00:00+00:00"
QUOTE = "tools may make new useful work possible"
FIRST_CODE = "def solve(data): return sorted(set(data['items']))"
SECOND_CODE = "def solve(data): return {str(x): data['items'].count(x) for x in sorted(set(data['items']))}"


def registration():
    sources = {}
    for ident, kind, body in (("past", "historical", "Earlier authors proposed that " + QUOTE + "."),
                              ("current", "current", "The configured local computation route is available.")):
        sources[ident] = {"title": ident, "url": "https://example.com/" + ident, "kind": kind,
                          "published_at": "1962" if ident == "past" else "2026-11-21",
                          "observed_at": "2026-11-21T10:00:00Z",
                          "snapshot": {"body": body, "sha256": hashlib.sha256(body.encode()).hexdigest(),
                                       "scope": "excerpt"}}
    catalog = {"schema": "frontier-foresight/v1", "id": "integration-fixture", "version": "1",
               "recorded_at": "2026-11-21T10:00:00Z", "sources": sources,
               "claims": {"vision": {"source": "past", "source_sha256": sources["past"]["snapshot"]["sha256"],
                                     "quote": QUOTE, "kind": "scenario",
                                     "statement": "An authored fixture vision; no historical attribution is claimed."}},
               "conditions": {"local": {"description": "The configured local route is available."}},
               "outcomes": {}}
    observation = {"id": "local-check", "condition": "local", "source": "current",
                   "source_sha256": sources["current"]["snapshot"]["sha256"],
                   "quote": sources["current"]["snapshot"]["body"], "kind": "observed", "status": "satisfied",
                   "observed_at": "2026-11-21T11:00:00Z", "expires_at": "2026-11-22T11:00:00Z"}
    return {"ambition": "Find useful new operations from attributable evidence.", "beneficiary": "Fixture operator",
            "catalog": catalog, "observations": [observation], "as_of": AS_OF,
            "route": {"provider": "fixture", "model": "fixture-model"},
            "max_attempts": 2, "max_output_tokens": 3072}


def discovery(stage="first", *, selection=0, quote=QUOTE):
    outcomes = [("Return unique sorted input records.", "canonical-records"),
                ("Count occurrences of each record.", "inventory-counts"),
                ("Select a maximum-value feasible schedule.", "capacity-scheduling")]
    if stage == "second":
        outcomes = outcomes[1:] + outcomes[:1]
    return {"opportunities": [{"outcome": outcome, "family": family,
             "missing_means": "Construct a complete input-to-output instrument.",
             "alternative": "Compare ordinary conventional software with the same acceptance.",
             "falsification": "The conventional route already meets the complete useful outcome.",
             "value_hypothesis": "A potential internal benefit requiring operational measurement.",
             "rival_future": "No advantage over existing software appears.", "claim": "vision", "quote": quote}
            for outcome, family in outcomes], "selection": selection,
            "rationale": "Authored protocol fixture only; not an autonomous discovery."}


def contract(stage="first"):
    selected = discovery(stage)["opportunities"][0]
    values = [([3, 1, 3], [1, 3]), ([92817, -7, 92817], [-7, 92817]), ([0, 4, 0, 2], [0, 2, 4])]
    if stage == "second":
        values = [([2, 2, 3], {"2": 2, "3": 1}), ([62819, 62819, -5], {"-5": 1, "62819": 2}),
                  ([1, 1, 1, 9], {"1": 3, "9": 1})]
    rows = [{"input": {"items": values}, "expected": output} for values, output in values]
    return {"objective": selected["outcome"], "family": selected["family"],
            "acceptance": "Return the complete exact result for the stated objective on every valid JSON input.",
            "development": rows[:1], "qualification": rows[1:],
            "review": {"reviewer": "Independent authored test fixture",
                       "basis": "Manually enumerated finite examples with different output semantics.",
                       "limitations": "No real beneficiary, scientific discovery, economic or human productivity evidence."}}


class AuthoredRuntime:
    """Explicit fixture transport for orchestration and actual sandbox checks."""
    local_only = True

    def __init__(self):
        self.responses, self.calls = [], []
        self.connection = SimpleNamespace(remote=False, kind="openai", models={"fixture-model":
            SimpleNamespace(json_schema=True, json_mode=True, streaming=False)})

    def provider(self, _ident):
        return self.connection

    def generate(self, request):
        self.calls.append(copy.deepcopy(request))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return {"text": json.dumps(response), "usage": {"input_tokens": 150, "output_tokens": 50},
                "reported_model": "AUTHORED_FIXTURE", "qualification": "AUTHORED_FIXTURE_NOT_LIVE_MODEL",
                "cost": {"amount": None, "complete_cost_known": False}}

    def redact(self, text):
        return text


class FrontierMissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.clock = patch.object(mission, "now", return_value=AS_OF)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.runtime = AuthoredRuntime()
        self.workflows = WorkflowService(self.runtime, Path(self.temp.name) / "workspace")
        self.addCleanup(self.workflows.close)
        self.service = mission.FrontierMissionService(self.workflows)

    def register(self):
        return self.service.register(registration())["id"]

    def ready(self, ident, stage="first"):
        self.runtime.responses.append(discovery(stage))
        self.service.discover({"id": ident, "stage": stage})
        return self.service.contract({"id": ident, "stage": stage, "contract": contract(stage)})

    def build_first(self, ident):
        self.ready(ident)
        self.runtime.responses.append({"source": FIRST_CODE, "rationale": "Authored engineering fixture."})
        result = self.service.build({"id": ident})
        if result["builds"]["first"].get("qualification", {}).get("cases", [{}])[0].get("error", {}).get("code") == "SANDBOX_UNAVAILABLE":
            self.skipTest(builder.sandbox.SUPPORT)
        self.assertTrue(result["builds"]["first"]["qualified"], result["builds"]["first"])
        return result

    def test_source_first_discovery_precedes_any_acceptance_contract(self):
        ident = self.register()
        with self.assertRaises(BridgeError):
            self.service.contract({"id": ident, "contract": contract()})
        self.assertEqual(self.runtime.calls, [])
        self.runtime.responses.append(discovery())
        found = self.service.discover({"id": ident})
        self.assertEqual(found["status"], "needs_first_contract")
        self.assertEqual(found["contracts"], {})
        prompt = self.runtime.calls[0]["prompt"]
        self.assertIn(QUOTE, prompt)
        self.assertNotIn("92817", prompt)
        self.assertNotIn("Return unique sorted input records.", prompt)
        self.assertTrue(found["discoveries"]["first"]["opportunities"][0]["quotation_verified"])
        self.assertEqual(found["discoveries"]["first"]["provenance"], "AUTHORED_FIXTURE_NOT_LIVE_MODEL")

    def test_selected_hallucinated_quotation_is_rejected_with_attempt_evidence(self):
        ident = self.register()
        self.runtime.responses.append(discovery(quote="This invented quotation has no source support."))
        rejected = self.service.discover({"id": ident})
        self.assertEqual(rejected["status"], "discovery_failed")
        self.assertEqual(rejected["discoveries"], {})
        self.assertEqual(rejected["events"][-1]["error_code"], "FRONTIER_EVIDENCE")
        self.assertEqual(rejected["events"][-1]["model_usage"]["output_tokens"], 50)
        self.assertNotIn("first", rejected["builds"])

    def test_abstention_is_preserved_and_cannot_reach_construction(self):
        ident = self.register()
        self.runtime.responses.append(discovery(selection=None))
        result = self.service.discover({"id": ident})
        self.assertEqual(result["status"], "abstained")
        with self.assertRaises(BridgeError):
            self.service.contract({"id": ident, "contract": contract()})
        with self.assertRaises(BridgeError):
            self.service.build({"id": ident})
        self.assertEqual(len(self.runtime.calls), 1)

    def test_first_frozen_then_distinct_second_code_is_constructed_in_both_arms(self):
        ident = self.register()
        with self.assertRaises(BridgeError):
            self.service.discover({"id": ident, "stage": "second"})
        first = self.build_first(ident)
        first_hash = first["builds"]["first"]["source_sha256"]
        self.assertIsNotNone(first["builds"]["first"]["frozen"])
        self.ready(ident, "second")
        for arm in ("with_asset", "without_asset"):
            self.runtime.responses.append({"source": SECOND_CODE, "rationale": "A different authored counting implementation."})
            result = self.service.build({"id": ident, "arm": arm})
            self.assertTrue(result["builds"][arm]["qualified"], result["builds"][arm])
            self.assertNotEqual(result["builds"][arm]["source_sha256"], first_hash)
        self.assertEqual(result["builds"]["with_asset"]["retained_sha256"], first_hash)
        self.assertIsNone(result["builds"]["without_asset"]["retained_sha256"])
        self.assertIn(FIRST_CODE, self.runtime.calls[-2]["prompt"])
        self.assertNotIn(FIRST_CODE, self.runtime.calls[-1]["prompt"])
        self.assertIn("rational_affine", self.runtime.calls[-1]["prompt"])
        for request in self.runtime.calls:
            self.assertNotIn("92817", request["prompt"])
            self.assertNotIn("62819", request["prompt"])
        compared = self.service.compare({"id": ident})
        verdicts = compared["comparison"]["verdicts"]
        self.assertTrue(verdicts["all_registered_arms_passed"])
        self.assertEqual(verdicts["capability_transfer_advantage"], "NOT_ESTABLISHED")
        self.assertEqual(verdicts["economic_benefit"], "NOT_ESTABLISHED")
        self.assertEqual(verdicts["inventor_improvement"], "NOT_ESTABLISHED")
        self.assertIsNone(compared["comparison"]["conventional"])

    def test_same_task_successor_is_rejected_before_second_construction(self):
        ident = self.register()
        self.build_first(ident)
        self.runtime.responses.append(discovery("first"))
        rejected = self.service.discover({"id": ident, "stage": "second"})
        self.assertEqual(rejected["status"], "discovery_failed")
        self.assertEqual(rejected["events"][-1]["error_code"], "FRONTIER_TRANSFER")
        self.assertNotIn("second", rejected["contracts"])

    def test_interrupted_construction_checkpoint_cannot_silently_rerun(self):
        ident = self.register()
        self.ready(ident)
        def interrupt(_runtime, _route, _contract, **kwargs):
            kwargs["on_checkpoint"]({"status": "model_pending", "qualified": False,
                                      "attempts": [{"dispatch": "pending", "run_id": "lost-completion"}],
                                      "source_sha256": None})
            raise RuntimeError("Authored interruption before receiving a result")
        with patch.object(builder, "construct", side_effect=interrupt):
            result = self.service.build({"id": ident})
        self.assertEqual(result["builds"]["first"]["status"], "interrupted_or_error")
        self.assertEqual(result["builds"]["first"]["attempts"][0]["run_id"], "lost-completion")
        restarted = mission.FrontierMissionService(self.workflows)
        with self.assertRaises(BridgeError):
            restarted.build({"id": ident})
        self.assertEqual(len(self.runtime.calls), 1)

    def test_interrupted_discovery_checkpoint_requires_explicit_recovery(self):
        ident = self.register()
        self.runtime.responses.append(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            self.service.discover({"id": ident})
        self.assertEqual(self.service.get({"id": ident})["events"][-1]["status"], "running")
        self.runtime.responses.append(discovery())
        restarted = mission.FrontierMissionService(self.workflows)
        with self.assertRaises(BridgeError):
            restarted.discover({"id": ident})
        self.assertEqual(len(self.runtime.calls), 1)

    def test_retracted_evidence_preserves_first_asset_but_blocks_successor(self):
        ident = self.register()
        first = self.build_first(ident)
        old_hash = first["builds"]["first"]["source_sha256"]
        source = registration()["catalog"]["sources"]["past"]
        updated = self.service.observe({"id": ident, "as_of": AS_OF,
            "source_states": {"past": {"status": "retracted", "sha256": source["snapshot"]["sha256"]}}})
        self.assertEqual(updated["status"], "evidence_changed_review_required")
        self.assertEqual(updated["builds"]["first"]["source_sha256"], old_hash)
        before = len(self.runtime.calls)
        with self.assertRaises(BridgeError):
            self.service.discover({"id": ident, "stage": "second"})
        self.assertEqual(len(self.runtime.calls), before)

    def test_expired_observation_without_manual_refresh_cannot_advance_successor(self):
        ident = self.register()
        self.build_first(ident)
        before = len(self.runtime.calls)
        self.runtime.responses.append(discovery("second"))
        with patch.object(mission, "now", return_value="2026-11-23T12:00:00+00:00"):
            with self.assertRaises(BridgeError):
                self.service.discover({"id": ident, "stage": "second"})
        self.assertEqual(len(self.runtime.calls), before)

    def test_authenticated_state_tampering_is_rejected(self):
        ident = self.register()
        path = self.service._path(ident)
        envelope = json.loads(path.read_text())
        envelope["state"]["status"] = "first_qualified"
        path.write_text(json.dumps(envelope))
        with self.assertRaises(BridgeError) as raised:
            self.service.get({"id": ident})
        self.assertEqual(raised.exception.code, "FRONTIER_INTEGRITY")

    def test_remote_connection_is_refused_before_registration_or_dispatch(self):
        self.runtime.connection.remote = True
        with self.assertRaises(BridgeError) as raised:
            self.register()
        self.assertEqual(raised.exception.code, "FRONTIER_LOCAL")
        self.assertEqual(self.runtime.calls, [])
        self.assertEqual(self.service.status()["missions"], [])

    def test_local_connection_changed_to_remote_cannot_dispatch_discovery(self):
        ident = self.register()
        self.runtime.connection.remote = True
        self.runtime.responses.append(discovery())
        with self.assertRaises(BridgeError):
            self.service.discover({"id": ident})
        self.assertEqual(self.runtime.calls, [])

    def monitor(self, content_hash):
        self.runtime.local_only = False  # Public observation consent, still a local model.
        self.runtime.source_hosts = frozenset({"example.com"})
        observation = {"url": "https://example.com/past", "sha256": content_hash, "retrieved_at": AS_OF}
        monitor = FrontierMonitorService(self.workflows, SimpleNamespace(replay=lambda _data: None),
                                         fetcher=lambda *_args: dict(observation), frontier_missions=self.service)
        self.addCleanup(monitor.close)
        job = monitor.add({"url": observation["url"], "title": "Fixture public source",
                           "capability_ids": ["fixture-future-work"], "authorize": True})["job"]
        return monitor, job, observation

    def test_monitor_changes_reopen_dependent_mission_and_unchanged_polls_are_idempotent(self):
        ident = self.register()
        self.build_first(ident)
        source_hash = registration()["catalog"]["sources"]["past"]["snapshot"]["sha256"]
        monitor, job, observation = self.monitor(source_hash)
        monitor.poll({"job_id": job["id"]})
        self.assertEqual(self.service.get({"id": ident})["status"], "first_qualified")
        observation["sha256"] = hashlib.sha256(b"Changed fixture evidence").hexdigest()
        monitor.poll({"job_id": job["id"]})
        revised = self.service.get({"id": ident})
        self.assertEqual(revised["status"], "evidence_changed_review_required")
        previous_revision = revised["revision"]
        monitor.poll({"job_id": job["id"]})
        self.assertEqual(self.service.get({"id": ident})["revision"], previous_revision)

    def test_monitor_initial_poll_already_different_from_registered_source_reopens_mission(self):
        ident = self.register()
        self.build_first(ident)
        monitor, job, _ = self.monitor(hashlib.sha256(b"Changed before monitor creation").hexdigest())
        monitor.poll({"job_id": job["id"]})
        self.assertEqual(self.service.get({"id": ident})["status"], "evidence_changed_review_required")

    def test_contract_is_immutable_and_public_view_hides_qualification(self):
        ident = self.register()
        ready = self.ready(ident)
        self.assertEqual(ready["contracts"]["first"]["qualification"]["count"], 2)
        self.assertTrue(ready["contracts"]["first"]["qualification"]["withheld"])
        self.assertNotIn("92817", json.dumps(ready))
        revised = contract()
        revised["qualification"][0]["expected"] = []
        with self.assertRaises(BridgeError):
            self.service.contract({"id": ident, "contract": revised})
        exported = self.service.export({"id": ident})
        self.assertTrue(exported["contains_withheld_cases"])
        self.assertEqual(exported["state"]["contracts"]["first"]["qualification"], contract()["qualification"])

    def test_transfer_registration_view_does_not_expose_second_holdout(self):
        ident = self.register()
        self.build_first(ident)
        ready = self.ready(ident, "second")
        for view in (ready, self.service.get({"id": ident})):
            registered = view["transfer_registration"]
            self.assertEqual(set(registered), {"schema", "sha256", "contracts", "budget_sha256"})
            self.assertNotIn("spec", registered)
            self.assertNotIn("62819", json.dumps(view))
            self.assertTrue(view["contracts"]["second"]["qualification"]["withheld"])
        exported = self.service.export({"id": ident})
        self.assertEqual(exported["state"]["transfer_registration"]["spec"]["second"]["qualification"],
                         contract("second")["qualification"])

    def test_expired_evidence_after_all_arms_cannot_be_cleared_by_comparison(self):
        ident = self.register()
        first = self.build_first(ident)
        self.ready(ident, "second")
        for arm in ("with_asset", "without_asset"):
            self.runtime.responses.append({"source": SECOND_CODE, "rationale": "Authored comparison fixture."})
            self.assertTrue(self.service.build({"id": ident, "arm": arm})["builds"][arm]["qualified"])
        with patch.object(mission, "now", return_value="2026-11-23T12:00:00+00:00"):
            with self.assertRaises(BridgeError) as refused:
                self.service.compare({"id": ident})
        self.assertEqual(refused.exception.code, "FRONTIER_EVIDENCE")
        state = self.service.get({"id": ident})
        self.assertEqual(state["status"], "evidence_changed_review_required")
        self.assertIsNone(state["comparison"])
        self.assertEqual(state["builds"]["first"]["source_sha256"], first["builds"]["first"]["source_sha256"])
        self.assertTrue(all(build["qualified"] for build in state["builds"].values()))

    def blocked_discovery(self, ident):
        entered, release = threading.Event(), threading.Event()
        original = self.runtime.generate
        self.runtime.responses.append(discovery())
        def blocked(request):
            entered.set()
            if not release.wait(10):
                raise RuntimeError("Authored concurrency test did not release its response.")
            return original(request)
        self.runtime.generate = blocked
        errors = []
        def discover():
            try:
                self.service.discover({"id": ident})
            except BaseException as error:
                errors.append(error)
        worker = threading.Thread(target=discover, daemon=True)
        worker.start()
        self.assertTrue(entered.wait(2))
        self.addCleanup(release.set)
        return worker, release, errors

    def test_closed_owner_retains_process_lease_and_rejects_late_discovery(self):
        ident = self.register()
        worker, release, errors = self.blocked_discovery(ident)
        self.workflows.close()
        probe = """
import sys
from bridge.adapters import BridgeError
from bridge.workflows import WorkflowService
try:
    owned = WorkflowService(None, sys.argv[1])
except BridgeError as error:
    print(error.code)
else:
    owned.close()
    print('UNEXPECTEDLY_OPENED')
"""
        try:
            checked = subprocess.run([sys.executable, "-c", probe, str(self.workflows.root)],
                                     cwd=Path(__file__).resolve().parents[1], capture_output=True,
                                     text=True, timeout=5, check=False)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertEqual(checked.stdout.strip(), "WORKFLOW_OWNED")
        finally:
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        reopened = WorkflowService(AuthoredRuntime(), self.workflows.root)
        self.addCleanup(reopened.close)
        state = mission.FrontierMissionService(reopened).get({"id": ident})
        self.assertEqual(state["discoveries"], {})
        self.assertEqual(state["status"], "discovery_failed")
        self.assertEqual(state["events"][-1]["error_code"], "FRONTIER_CLOSED")

    def test_reopened_in_process_owner_shares_lock_and_preserves_new_observation(self):
        ident = self.register()
        worker, release, errors = self.blocked_discovery(ident)
        self.workflows.close()
        reopened = WorkflowService(AuthoredRuntime(), self.workflows.root)
        self.addCleanup(reopened.close)
        fresh = mission.FrontierMissionService(reopened)
        self.assertIs(reopened._locks, self.workflows._locks)
        lock = reopened._lock("frontier-" + ident)
        self.assertFalse(lock.acquire(blocking=False), "Active request lost its shared mission lock.")
        observed, observation_errors = threading.Event(), []
        source = registration()["catalog"]["sources"]["past"]["snapshot"]["sha256"]
        def update():
            try:
                fresh.observe({"id": ident, "as_of": AS_OF,
                    "source_states": {"past": {"sha256": source, "status": "retracted"}}})
                observed.set()
            except BaseException as error:
                observation_errors.append(error)
        observer = threading.Thread(target=update, daemon=True)
        observer.start()
        try:
            release.set()
            worker.join(3)
            observer.join(3)
        finally:
            release.set()
        self.assertFalse(worker.is_alive())
        self.assertFalse(observer.is_alive())
        self.assertEqual(errors + observation_errors, [])
        self.assertTrue(observed.is_set())
        state = fresh.get({"id": ident})
        self.assertEqual(state["source_states"]["past"]["status"], "retracted")
        self.assertEqual(state["discoveries"], {})


class FrontierMissionHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.clock = patch.object(mission, "now", return_value=AS_OF)
        self.clock.start()
        self.config = {"local_only": True, "allow_paid_requests": False, "providers": {"fixture": {
            "kind": "openai", "base_url": "http://127.0.0.1:12345/v1", "models": {"fixture-model": {
                "input_per_million": 0, "output_per_million": 0, "max_output_tokens": 4096,
                "json_mode": True, "json_schema": True, "streaming": True}}}}}
        self.server = HarnessServer(("127.0.0.1", 0), Runtime(self.config), config=self.config,
                                    workspace=Path(self.temp.name) / "workspace")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.clock.stop()
        self.temp.cleanup()

    def request(self, action, data=None, *, authenticated=True, origin=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        headers = {"Content-Type": "application/json"}
        if authenticated:
            headers["X-Harness-Token"] = self.server.token
        if origin is not None:
            headers["Origin"] = origin
        connection.request("GET" if data is None else "POST", "/api/frontier-missions/" + action,
                           None if data is None else json.dumps(data), headers)
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result

    def test_http_authentication_origin_and_registered_state(self):
        self.assertEqual(self.request("status", authenticated=False)[0], 403)
        self.assertEqual(self.request("status", origin="https://foreign.example")[0], 403)
        self.assertEqual(self.request("promote", {})[0], 404)
        status, registered = self.request("register", registration())
        self.assertEqual(status, 200, registered)
        ident = registered["id"]
        status, fetched = self.request("get", {"id": ident})
        self.assertEqual(status, 200)
        self.assertEqual(fetched["id"], ident)
        self.assertEqual(self.request("export", {"id": ident}, authenticated=False)[0], 403)
        status, inventory = self.request("status")
        self.assertEqual(status, 200)
        self.assertEqual(inventory["missions"][0]["id"], ident)


if __name__ == "__main__":
    unittest.main()
