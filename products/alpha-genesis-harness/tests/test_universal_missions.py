# SPDX-License-Identifier: Apache-2.0
"""End-to-end workflow checks with explicitly authored provider responses."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.adapters import BridgeError, Runtime
from bridge.output_schema import prepare_schema, validate_output
from bridge.universal_missions import UniversalMissionService
from bridge.workflow_demo import FixtureRuntime


def specification(**overrides):
    return {
        "ambition": "Mesurer l’écart à une cible et garder le calcul réutilisable.\n",
        "language": "fr", "provider": "fixture", "model": "authored-constructor",
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=3)).isoformat(),
        "max_turns": 5, "max_actions": 15, "max_output_tokens": 1024, **overrides,
    }


def propose(*actions, done=False):
    return {"summary": "Développons un instrument local et vérifions les résultats observés.",
            "actions": list(actions), "done": done}


def construct(correct=True):
    op = "sub" if correct else "add"
    return {"tool": "construct_instrument", "name": "difference.json", "spec": {
        "inputs": ["a", "b"],
        "outputs": {"difference": {"op": op, "args": [{"field": "a"}, {"field": "b"}]}},
    }}


def compute():
    return {"tool": "run_instrument", "name": "difference.json", "input": {"a": 7, "b": 4}}


class UniversalMissionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.workspace = Path(tmp.name) / "missions"

    def service(self, responses, **policy):
        runtime = FixtureRuntime(responses)
        service = UniversalMissionService(runtime, self.workspace, **policy)
        self.addCleanup(service.close)
        return service, runtime

    def test_multiturn_repairs_actual_result_and_stops_for_separate_acceptance(self):
        service, runtime = self.service([propose(construct(False), compute()), propose(construct(), compute(), done=True)])
        scope = specification(acceptance=[{"artifact": "difference.json", "kind": "instrument",
                                         "input": {"a": 7, "b": 4}, "expected": {"difference": 3}}])
        opened = service.submit(scope)
        failed = service.step(opened["id"])
        self.assertEqual(failed["status"], "ready")
        self.assertEqual(failed["verification"]["checks"][0]["actual"], {"difference": 11})
        result = service.step(opened["id"])
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["original_ambition"], scope["ambition"])
        self.assertEqual(result["objective"], scope["ambition"])
        self.assertEqual(result["language"], "fr")
        self.assertEqual(result["qualification"], "DEVELOPMENT_ONLY")
        self.assertTrue(result["verification"]["passed"])
        self.assertEqual(result["verification"]["checks"][0]["actual"], {"difference": 3})
        self.assertEqual(result["actions"], 4)
        self.assertIn('"difference":11', runtime.calls[1]["prompt"])
        self.assertEqual(service.capabilities()["capabilities"], [])
        self.assertEqual(set(service.export(opened["id"])["files"]), {"difference.json", "RUN_INSTRUMENT.py"})

    def test_authenticated_identity_is_idempotent_and_revision_preserves_original(self):
        service, runtime = self.service([])
        ident = "wf_" + "1" * 24
        intent = specification(ambition="  ligne\n" + "a" * 15_000 + " 🌌\n")
        first = service.submit(intent, ident)
        self.assertEqual(service.submit(intent, ident)["id"], first["id"])
        self.assertEqual(first["objective"], intent["ambition"])
        self.assertEqual(runtime.calls, [])
        with self.assertRaises(BridgeError) as failure:
            service.submit({**intent, "ambition": "A different intent"}, ident)
        self.assertEqual(failure.exception.code, "MISSION_IDENTITY_CONFLICT")
        result = service.revise(ident, specification(ambition="Solve a revised problem."))
        self.assertEqual(result["original_ambition"], intent["ambition"])
        self.assertEqual(result["parent_run_id"], ident)
        self.assertEqual(result["objective"], "Solve a revised problem.")

    def test_model_sees_operator_document_acceptance_even_when_ambition_omits_it(self):
        good = "Evidence checked. Release marker seven."
        write_without = {"tool": "write_document", "name": "report.md", "content": "Evidence checked."}
        write_with = {**write_without, "content": good}
        requirements = [{"artifact": "report.md", "kind": "document", "min_chars": 30,
                         "contains": ["Release marker seven."]}]
        service, runtime = self.service([propose(write_without), propose(write_with, done=True)])
        spec = specification(ambition="Prepare a local evidence summary.", acceptance=requirements)
        ident = service.submit(spec)["id"]
        self.assertFalse(service.step(ident)["verification"]["passed"])
        result = service.step(ident)
        for call in runtime.calls:
            payload = json.loads(call["prompt"].split("\nUNTRUSTED_MISSION_DATA\n", 1)[1])
            self.assertEqual(payload["operator_development_acceptance"], requirements)
        self.assertTrue(result["verification"]["passed"])
        self.assertEqual(result["status"], "needs_review")

    def test_import_requires_new_scope_and_never_restores_acceptance(self):
        service, _ = self.service([propose(construct(), compute(), done=True)])
        intent = specification()
        opened = service.submit(intent)
        service.step(opened["id"])
        archive = service.export(opened["id"])
        with self.assertRaises(BridgeError):
            service.import_archive(archive)
        with self.assertRaises(BridgeError):
            service.import_archive(archive, {**intent, "ambition": "A different intent"})
        restored = service.import_archive(archive, {**intent, "tools": ["read_artifact"]})
        self.assertNotEqual(restored["id"], opened["id"])
        self.assertEqual(restored["status"], "paused")
        self.assertFalse(restored["verification"]["passed"])
        self.assertEqual(restored["spec"]["tool_permissions"], ["read_artifact"])
        revision = service.revise(opened["id"], specification(ambition="Improve the calculation."))
        imported_revision = service.import_archive(service.export(revision["id"]), specification(ambition=revision["objective"]))
        self.assertEqual(imported_revision["original_ambition"], intent["ambition"])
        self.assertEqual(imported_revision["parent_run_id"], revision["id"])

    def test_repeated_computation_reuses_exact_settled_result(self):
        service, _ = self.service([propose(construct(), compute(), compute(), done=True)])
        result = service.step(service.submit(specification())["id"])
        completed = [event["detail"]["outcome"] for event in result["events"]
                     if event["kind"] == "tool_completed"]
        self.assertEqual(len(completed), 3)
        self.assertTrue(completed[1]["operation_executed"])
        self.assertEqual(completed[1]["output"], {"difference": 3})
        self.assertFalse(completed[2]["operation_executed"])
        self.assertEqual(completed[2]["prior_outcome"]["output"], {"difference": 3})

    def test_expiry_after_inference_discards_actual_response_without_applying_tools(self):
        clock = datetime(2026, 11, 25, 3, tzinfo=timezone.utc)
        service, runtime = self.service([propose(construct(), done=True)])
        originals = runtime.generate
        available = [clock]

        def generate(call):
            answer = originals(call)
            available[0] += timedelta(seconds=3)
            return answer

        runtime.generate = generate
        with patch("bridge.universal_missions.utc_now", side_effect=lambda: available[0]):
            created = service.submit(specification(expires_at=(clock + timedelta(seconds=2)).isoformat()))
            expired = service.step(created["id"])
        self.assertEqual(expired["status"], "expired")
        self.assertEqual(expired["model_calls"], 1)
        self.assertEqual(expired["actions"], 0)
        self.assertFalse(expired["artifacts"])
        self.assertIn("late_result_discarded", [event["kind"] for event in expired["events"]])

    def test_revocation_blocks_late_tools(self):
        service, runtime = self.service([propose(construct(), done=True)])
        entered, release = threading.Event(), threading.Event()
        original = runtime.generate

        def generate(call):
            entered.set()
            if not release.wait(4):
                raise RuntimeError("Test provider barrier")
            return original(call)

        runtime.generate = generate
        opened = service.submit(specification())
        ident = opened["id"]
        worker = threading.Thread(target=service.step, args=(ident,))
        worker.start()
        try:
            self.assertTrue(entered.wait(3))
            self.assertEqual(service.revoke(ident)["status"], "revoked")
        finally:
            release.set()
            worker.join(4)
        self.assertFalse(worker.is_alive())
        self.assertFalse(service.get(ident)["artifacts"])
        self.assertIn("late_result_discarded", [event["kind"] for event in service.get(ident)["events"]])

    def test_unsafe_or_unapproved_actions_never_dispatch(self):
        service, _ = self.service([propose({"tool": "send", "name": "report.md", "content": "external"}, done=True)])
        intent = specification()
        result = service.step(service.submit(intent)["id"])
        self.assertFalse(result["artifacts"])
        self.assertIn("tool_refused", [event["kind"] for event in result["events"]])
        with self.assertRaises(BridgeError):
            service.submit({**intent, "local_only": False})
        with self.assertRaises(BridgeError):
            service.submit({**intent, "tools": ["retrieve_source"]})

    def test_narrower_service_revokes_saved_remote_or_source_scope(self):
        old, _ = self.service([], allow_remote=True, allow_public_sources=True)
        intent = specification(local_only=False, tools=["retrieve_source"],
                               requirements={"public_sources": ["https://example.org/fixture"]})
        opened = old.submit(intent)
        old.pause(opened["id"])
        old.close()
        local, runtime = self.service([])
        self.assertEqual(local.get(opened["id"])["status"], "paused")
        self.assertEqual(local.resume(opened["id"])["status"], "revoked")
        self.assertEqual(runtime.calls, [])

    def test_new_transport_attempt_does_not_inherit_expired_authority(self):
        attempts = []

        def sender(*args, **kwargs):
            attempts.append((args, kwargs))
            raise BridgeError("PROVIDER_CONNECTION", "First attempt returned no response.", 502)

        runtime = Runtime({"max_attempts": 3, "providers": {"test-local": {
            "kind": "openai", "base_url": "http://127.0.0.1:38461/v1", "models": {
                "test-model": {"input_per_million": "0", "output_per_million": "0"},
            },
        }}}, sender=sender)
        request = {"provider": "test-local", "model": "test-model", "prompt": "Bounded local computation",
                   "max_output_tokens": 64, "run_id": "expired-transport"}
        with self.assertRaises(BridgeError) as stopped:
            runtime.generate(request, cancelled_before_dispatch=lambda: bool(attempts))
        self.assertEqual(stopped.exception.code, "CANCELLED")
        self.assertFalse(stopped.exception.pre_dispatch)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(runtime.budget.view()["reserved"], 0)

    def test_noaa_12_hour_intent_refused_at_runtime(self):
        point = {"issued_at": "2024-11-29T00:00:00Z", "valid_at": "2024-11-29T12:00:00Z",
                 "latitude": "45.50", "longitude": "-73.50"}
        expected = {"version": "1.0.0", "source": "NOAA GFS public archive",
                    "quantity": "air_temperature_at_2m", "result_kind": "model_forecast",
                    "unit": "K", "time_basis": "UTC", "grid_degrees": "0.25", **point}
        call = {"tool": "invoke_capability", "name": "forecast-scope.json", "capability_id": "noaa-archive",
                "input": point}
        service, _ = self.service([propose(call, done=True)])
        intent = specification(ambition="Obtenir une prévision pour le 29 novembre 2024 à midi UTC, initialisée à 00 UTC.",
                               tools=["invoke_capability"], requirements={"capabilities": {"noaa-archive": expected}})
        opened = service.submit(intent)
        schema = prepare_schema(service._response_schema(opened, "builder"))
        validate_output(propose(call, done=True), schema)
        result = service.step(opened["id"])
        outcome = next(event["detail"]["outcome"] for event in result["events"] if event["kind"] == "tool_completed")
        self.assertFalse(outcome["operation_executed"])
        self.assertFalse(outcome["observed"]["executed"])
        self.assertEqual(outcome["observed"]["decision"]["status"], "INCOMPATIBLE")
        self.assertEqual(outcome["reason"], "NOAA_F024_REQUIRES_EXACTLY_24_HOURS")

    def test_composition_refuses_mismatched_units_and_provenance(self):
        action = {"tool": "assess_composition", "name": "compatibility.json", "links": [{
            "producer": "noaa-archive", "output": "temperature", "consumer": "endpoint-screen", "input": "batch",
            "producer_step": 0, "consumer_step": 1,
        }]}
        service, _ = self.service([propose(action)])
        opened = service.submit(specification(tools=["assess_composition"]))
        validate_output(propose(action), prepare_schema(service._response_schema(opened, "builder")))
        result = service.step(opened["id"])
        observed = next(event["detail"]["outcome"] for event in result["events"] if event["kind"] == "tool_completed")
        self.assertEqual(observed["status"], "INCOMPATIBLE")
        self.assertEqual(observed["reason"], "TYPED_INTERFACE_MISMATCH")
        self.assertFalse(observed["operation_executed"])

    def test_construct_and_execute_readonly_table_on_bound_inputs(self):
        build = {"tool": "construct_table", "name": "counts.json", "schema": {"events": {"v": "INTEGER"}},
                 "sql": "SELECT SUM(v) FROM events"}
        run = {"tool": "run_table", "name": "counts.json", "input": {"dataset": "event-series"}}
        rows = [{"v": value} for value in (13, 8, -2, 11)]
        service, _ = self.service([propose(build), propose(run, done=True)])
        opened = service.submit(specification(requirements={"approved_tables": {"event-series": {"events": rows}}}))
        schema = prepare_schema(service._response_schema(opened, "builder"))
        validate_output(propose(build, run), schema)
        service.step(opened["id"])
        result = service.step(opened["id"])
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["artifacts"]["counts.json"]["kind"], "table_instrument")
        outcome = [event["detail"]["outcome"] for event in result["events"] if event["kind"] == "tool_completed"][-1]
        self.assertTrue(outcome["operation_executed"])
        self.assertEqual(outcome["rows"], [[sum(row["v"] for row in rows)]])

    def test_restart_after_process_interrupt_preserves_action_and_requires_explicit_resume(self):
        marker = self.workspace.parent / "provider-dispatched"
        ident = "wf_" + "2" * 24
        initial = """import json
from pathlib import Path
import sys
import threading
sys.path.insert(0, sys.argv[1])
from bridge.universal_missions import UniversalMissionService
from bridge.workflow_demo import FixtureRuntime
root, marker, ident, spec, first = sys.argv[2:]
class InterruptedProvider(FixtureRuntime):
    def generate(self, data):
        if self.calls:
            Path(marker).touch()
            threading.Event().wait()
        return super().generate(data)
runtime = InterruptedProvider([json.loads(first)])
service = UniversalMissionService(runtime, root)
opened = service.submit(json.loads(spec), ident)
assert service.step(ident)["status"] == "ready"
service.step(ident)
"""
        proc = subprocess.Popen([sys.executable, "-c", initial, str(ROOT), str(self.workspace), str(marker),
                                 ident, json.dumps(specification()), json.dumps(propose(construct(), compute()))],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        end = time.monotonic() + 6
        try:
            while not marker.exists() and proc.poll() is None and time.monotonic() < end:
                time.sleep(0.02)
            self.assertTrue(marker.exists(), "Child did not persist the second dispatch reservation")
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.communicate(timeout=3)
        service, runtime = self.service([propose(compute(), {"tool": "write_document", "name": "done.md",
                                                               "content": "The retained ex ante result was 3."}, done=True)])
        interrupted = service.get(ident)
        self.assertEqual(interrupted["status"], "interrupted")
        self.assertEqual(interrupted["actions"], 2)
        self.assertEqual(interrupted["model_calls"], 2)
        self.assertEqual(runtime.calls, [])
        with self.assertRaises(BridgeError):
            service.step(ident)
        service.resume(ident, background=False)
        result = service.step(ident)
        history = [event["kind"] for event in result["events"]]
        self.assertIn("interruption_recovered", history)
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["actions"], 4)
        self.assertEqual(result["model_calls"], 3)
        computations = [e["detail"]["outcome"] for e in result["events"]
                        if e["kind"] == "tool_completed" and e["detail"]["tool"] == "run_instrument"]
        self.assertTrue(computations[0]["operation_executed"])
        self.assertFalse(computations[1]["operation_executed"])


if __name__ == "__main__":
    unittest.main()
