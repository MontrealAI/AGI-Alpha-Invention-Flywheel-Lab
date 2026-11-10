# SPDX-License-Identifier: Apache-2.0
"""Independent strategy and shared-budget regressions with authored model replies."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError, Runtime
from bridge.workflows import WorkflowService, portable_digest


class SequenceRuntime:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
    def status(self):
        return {"local_only": True, "providers": [{"id": "local", "local": True}]}
    def provider(self, ident):
        return SimpleNamespace(remote=False)
    def generate(self, data):
        self.calls.append(data)
        return {"text": json.dumps(self.responses.pop(0)), "provider": "local", "model": "fixture", "usage": {}, "cost": {"amount": None}}
    def cancel(self, ident):
        return {"cancelled": True}


class IndependentActionBudgetTests(unittest.TestCase):
    def service(self, responses):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        runtime = SequenceRuntime(responses)
        service = WorkflowService(runtime, Path(temporary.name) / "work")
        self.addCleanup(service.close)
        return service, runtime

    @staticmethod
    def spec(max_actions):
        return {"objective": "Retain valid within-budget work and recompute its acceptance", "max_actions": max_actions,
                "roles": {"builder": {"provider": "local", "model": "fixture"}, "critic": {"provider": "local", "model": "fixture"}},
                "acceptance": [{"artifact": "answer.txt", "kind": "document", "contains": ["accepted text"]}]}

    def test_extra_action_cannot_skip_checks_or_required_critic(self):
        service, runtime = self.service([
            {"actions": [{"tool": "write_document", "name": "answer.txt", "content": "accepted text"},
                         {"tool": "read_artifact", "name": "answer.txt"}]},
            {"verdict": "accept", "feedback": "The frozen structural condition passed."}])
        ident = service.create(self.spec(1))["id"]
        built = service.step(ident)
        self.assertEqual(built["actions"], 1)
        self.assertTrue(built["verification"]["passed"])
        self.assertEqual(built["phase"], "critic")
        completed = service.step(ident)
        self.assertEqual(completed["status"], "complete")
        self.assertEqual(completed["actions"], 1)
        self.assertEqual(len(runtime.calls), 2)

    def test_budget_exhausted_repair_cannot_retain_previous_pass(self):
        service, runtime = self.service([
            {"actions": [{"tool": "write_document", "name": "answer.txt", "content": "accepted text"}]},
            {"verdict": "revise", "feedback": "Exercise a separate repair iteration."},
            {"actions": [{"tool": "write_document", "name": "answer.txt", "content": "incorrect replacement"},
                         {"tool": "read_artifact", "name": "answer.txt"}]},
            {"verdict": "accept", "feedback": "A model claim cannot override the frozen failing case."}])
        ident = service.create(self.spec(2))["id"]
        self.assertTrue(service.step(ident)["verification"]["passed"])
        service.step(ident)
        repaired = service.step(ident)
        self.assertEqual(repaired["actions"], 2)
        self.assertFalse(repaired["verification"]["passed"])
        reviewed = service.step(ident)
        self.assertNotEqual(reviewed["status"], "complete")
        final = service.step(ident)
        self.assertEqual(final["status"], "exhausted")
        self.assertEqual(final["actions"], 2)
        self.assertEqual(len(runtime.calls), 4)


class StrategyRuntime:
    max_concurrent = 2
    def __init__(self, respond):
        self.respond = respond
        self.calls = []
        self.lock = threading.Lock()
    def status(self):
        return {"local_only": True, "providers": [{"id": "local", "local": True}]}
    def provider(self, ident):
        return SimpleNamespace(remote=False)
    def generate(self, data):
        with self.lock:
            self.calls.append(data)
        payload = json.loads(data["prompt"].split("UNTRUSTED_WORKSPACE_DATA\n", 1)[1])
        response = self.respond(data, payload)
        return {"text": json.dumps(response), "provider": "local", "model": "fixture", "usage": {"input_tokens": 1, "output_tokens": 1},
                "cost": {"amount": 0.01, "basis": "synthetic_reported_usage", "complete_cost_known": True}}
    def cancel(self, ident):
        return {"cancelled": True}


class IndependentStrategyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "work"
        self.services = []

    def tearDown(self):
        for service in self.services:
            service.close()
        self.temporary.cleanup()

    def service(self, respond):
        runtime = StrategyRuntime(respond)
        service = WorkflowService(runtime, self.root)
        self.services.append(service)
        return service, runtime

    @staticmethod
    def spec(strategy="parallel-exploration", **changes):
        return {"objective": "Construct an independently accepted branch result", "strategy": strategy,
                "approaches": ["ALPHA exact arithmetic", "BETA independent representation"],
                "roles": {"builder": {"provider": "local", "model": "fixture"}}, "max_iterations": 2, "max_actions": 2,
                "acceptance": [{"artifact": "answer.txt", "kind": "document", "contains": ["accepted text"]}], **changes}

    @staticmethod
    def write(text="accepted text"):
        return {"actions": [{"tool": "write_document", "name": "answer.txt", "content": text}]}

    def finish(self, service, ident):
        for _ in range(30):
            state = service.get(ident)
            if state["status"] not in {"ready", "running", "interrupted"}:
                return state
            state = service.step(ident)
        self.fail("Bounded strategy did not settle within its registered allocations")

    def test_partitions_include_review_overhead_and_internal_branches_cannot_dispatch(self):
        service, runtime = self.service(lambda *_: self.fail("Creation must not dispatch"))
        roles = {name: {"provider": "local", "model": "fixture"} for name in ["builder", "critic", "adversary", "economist", "researcher"]}
        parent = service.create(self.spec(roles=roles, max_iterations=5, max_actions=7))
        self.assertEqual(sum(b["max_iterations"] for b in parent["branch_runs"]), 5)
        self.assertEqual(sum(b["max_actions"] for b in parent["branch_runs"]), 7)
        self.assertEqual(parent["model_call_limit"], 5 * 4 + 2)
        for ref in parent["branch_runs"]:
            child = service.get(ref["run_id"])
            self.assertEqual(child["spec"]["acceptance"], parent["spec"]["acceptance"])
            self.assertEqual(child["spec"]["roles"], roles)
            for operation in [service.step, service.start, lambda ident: service.resume(ident, background=False)]:
                with self.assertRaises(BridgeError):
                    operation(ref["run_id"])
        self.assertEqual(runtime.calls, [])

    def test_parallel_artifacts_and_acceptance_are_isolated_before_selection(self):
        service, runtime = self.service(lambda _, p: self.write("accepted text ALPHA" if "ALPHA exact" in p["context"] else "BETA failed draft"))
        parent = service.create(self.spec())
        result = self.finish(service, parent["id"])
        self.assertEqual(result["status"], "complete")
        first, second = result["branch_runs"]
        self.assertEqual(result["selected_branch"], first["run_id"])
        self.assertEqual(service.export(first["run_id"])["files"]["answer.txt"], "accepted text ALPHA")
        self.assertEqual(service.export(second["run_id"])["files"]["answer.txt"], "BETA failed draft")
        self.assertEqual(service.export(parent["id"])["files"]["answer.txt"], "accepted text ALPHA")
        self.assertEqual((result["actions"], result["iteration"], result["model_calls"]), (2, 2, 2))
        self.assertEqual(len(runtime.calls), 2)

    def test_accepted_parent_reports_all_branch_costs(self):
        service, _ = self.service(lambda *_: self.write())
        result = self.finish(service, service.create(self.spec())["id"])
        capability = next(c for c in service.capabilities()["capabilities"] if c["id"] == result["id"])
        self.assertEqual(len(capability["costs"]), 2)
        self.assertAlmostEqual(sum(cost["amount"] for cost in capability["costs"]), 0.02)

    def test_repeated_failed_branches_cannot_expand_shared_call_or_iteration_caps(self):
        service, runtime = self.service(lambda *_: {"actions": []})
        result = self.finish(service, service.create(self.spec(max_iterations=5, max_actions=7))["id"])
        self.assertEqual(result["status"], "exhausted")
        self.assertEqual((result["iteration"], result["model_calls"], result["model_call_limit"]), (5, 5, 5))
        self.assertEqual(result["actions"], 0)
        self.assertEqual(len(runtime.calls), 5)

    def test_parallel_branches_share_one_atomic_monetary_reservation(self):
        entered, second_reservation, release = threading.Event(), threading.Event(), threading.Event()
        dispatches, reservation_attempts, failures = [], [], []
        def sender(*args, **kwargs):
            dispatches.append(1)
            entered.set()
            if not release.wait(5): raise RuntimeError("Independent provider fixture was not released")
            return {"choices": [{"message": {"content": json.dumps(self.write())}}], "usage": {"prompt_tokens": 0, "completion_tokens": 1}}
        runtime = Runtime({"local_only": True, "session_budget_usd": 1.5, "max_attempts": 1,
            "providers": {"local": {"kind": "openai", "base_url": "http://127.0.0.1:2", "models": {
                "fixture": {"input_per_million": 0, "output_per_million": 1000000, "input_token_overhead": 0, "max_output_tokens": 1}}}}}, sender=sender)
        original_reserve = runtime.budget.reserve
        def observed_reserve(amount):
            reservation_attempts.append(amount)
            if len(reservation_attempts) == 2: second_reservation.set()
            return original_reserve(amount)
        runtime.budget.reserve = observed_reserve
        service = WorkflowService(runtime, self.root)
        self.services.append(service)
        parent = service.create(self.spec(max_output_tokens=1))
        def run():
            try: service.step(parent["id"])
            except BaseException as error: failures.append(error)
        worker = threading.Thread(target=run)
        worker.start()
        try:
            self.assertTrue(entered.wait(5))
            self.assertTrue(second_reservation.wait(5))
            self.assertEqual(runtime.budget.view()["reserved"], 1)
            self.assertEqual(len(dispatches), 1)
        finally:
            release.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(len(dispatches), 1)
        self.assertEqual(runtime.budget.view()["committed"], 1)
        self.assertEqual(runtime.budget.view()["reserved"], 0)
        self.assertEqual(service.get(parent["id"])["status"], "paused")

    def test_adaptive_success_does_not_activate_unneeded_alternatives(self):
        service, runtime = self.service(lambda *_: self.write())
        result = self.finish(service, service.create(self.spec("adaptive", max_iterations=3, max_actions=3))["id"])
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["strategy_phase"], "primary")
        self.assertEqual([b["model_calls"] for b in result["branches"]], [1, 0, 0])
        self.assertFalse(any(e["kind"] == "strategy_switched" for e in result["events"]))
        self.assertEqual(len(runtime.calls), 1)

    def test_adaptive_switch_keeps_original_failure_and_frozen_permissions(self):
        service, runtime = self.service(lambda _, p: self.write("accepted text" if "ALPHA exact" in p["context"] else "failed draft"))
        original = self.spec("adaptive", max_iterations=3, max_actions=3)
        result = self.finish(service, service.create(original)["id"])
        self.assertEqual(result["status"], "complete")
        switch = next(e["detail"] for e in result["events"] if e["kind"] == "strategy_switched")
        self.assertFalse(switch["providers_changed"])
        self.assertFalse(switch["permissions_changed"])
        self.assertFalse(switch["acceptance_changed"])
        self.assertTrue(switch["evidence"])
        self.assertEqual(result["branches"][0]["status"], "exhausted")
        self.assertFalse(result["branches"][0]["verification"]["passed"])
        self.assertEqual((result["model_calls"], result["iteration"], result["actions"]), (3, 3, 3))
        self.assertEqual(len(runtime.calls), 3)

    def blocked_wave(self, service, parent, entered, release):
        failures = []
        def run():
            try: service.step(parent["id"])
            except BaseException as error: failures.append(error)
        worker = threading.Thread(target=run)
        worker.start()
        self.addCleanup(release.set)
        self.addCleanup(lambda: worker.join(5))
        self.assertTrue(entered.wait(5), "Both isolated branches should enter the authored provider")
        return worker, failures

    def blocking_runtime(self):
        entered, release = threading.Event(), threading.Event()
        counter, lock = [], threading.Lock()
        def respond(*_):
            with lock:
                counter.append(1)
                if len(counter) == 2: entered.set()
            if not release.wait(5): raise RuntimeError("Independent fixture was not released")
            return self.write()
        return respond, entered, release

    def test_parent_cancellation_discards_all_late_branch_writes(self):
        respond, entered, release = self.blocking_runtime()
        service, runtime = self.service(respond)
        parent = service.create(self.spec())
        worker, failures = self.blocked_wave(service, parent, entered, release)
        service.cancel(parent["id"])
        release.set(); worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        result = service.get(parent["id"])
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(result["model_calls"], 2)
        for branch in result["branches"]:
            self.assertEqual(branch["status"], "cancelled")
            self.assertEqual(branch["artifacts"], {})
        self.assertEqual(result["artifacts"], {})
        with self.assertRaises(BridgeError): service.resume(parent["id"], background=False)

    def test_pause_reopen_resume_retains_branch_ids_and_consumed_attempts(self):
        respond, entered, release = self.blocking_runtime()
        service, _ = self.service(respond)
        parent = service.create(self.spec(max_iterations=4, max_actions=4))
        ids = [b["run_id"] for b in parent["branch_runs"]]
        worker, failures = self.blocked_wave(service, parent, entered, release)
        service.pause(parent["id"])
        release.set(); worker.join(5)
        self.assertEqual(failures, [])
        service.close()
        reopened, runtime = self.service(lambda *_: self.write())
        reopened.resume(parent["id"], background=False)
        result = self.finish(reopened, parent["id"])
        self.assertEqual(result["status"], "complete")
        self.assertEqual([b["run_id"] for b in result["branch_runs"]], ids)
        self.assertEqual((result["model_calls"], result["iteration"], result["actions"]), (4, 4, 2))
        self.assertEqual(len(runtime.calls), 2)

    def test_rehashed_child_cannot_expand_parent_frozen_contract_on_import(self):
        service, _ = self.service(lambda *_: self.write())
        parent = service.create(self.spec())
        exported = service.export(parent["id"])
        child = exported["branch_exports"][0]
        child["state"]["spec"]["max_iterations"] += 10
        child["sha256"] = portable_digest({k: v for k, v in child.items() if k != "sha256"})
        exported["sha256"] = portable_digest({k: v for k, v in exported.items() if k != "sha256"})
        before = set(self.root.iterdir())
        with self.assertRaises(BridgeError): service.import_archive(exported)
        self.assertEqual(set(self.root.iterdir()), before)

    def test_imported_parent_and_branches_require_current_acceptance(self):
        service, runtime = self.service(lambda *_: self.write())
        parent = self.finish(service, service.create(self.spec())["id"])
        count = len(runtime.calls)
        imported = service.import_archive(service.export(parent["id"]))
        self.assertEqual(imported["status"], "paused")
        self.assertFalse(imported["verification"]["passed"])
        self.assertIsNone(imported["selected_branch"])
        self.assertEqual(len(runtime.calls), count)
        original_ids = {b["run_id"] for b in parent["branches"]}
        for branch in imported["branches"]:
            self.assertNotIn(branch["run_id"], original_ids)
            self.assertEqual(branch["status"], "paused")
            self.assertFalse(branch["verification"]["passed"])

    def test_interrupted_branch_initialization_retains_owned_identity_on_recovery(self):
        service, runtime = self.service(lambda *_: self.write())
        original_save = service._save
        saved = {}
        class AbruptStop(BaseException):
            pass
        def interrupt_child_commit(state):
            original_save(state)
            if state["spec"]["strategy"] == "parallel-exploration":
                saved["parent"] = state["id"]
            elif "child" not in saved:
                saved["child"] = state["id"]
                raise AbruptStop()
        service._save = interrupt_child_commit
        try:
            with self.assertRaises(AbruptStop): service.create(self.spec())
        finally:
            service._save = original_save
        child = service.get(saved["child"])
        self.assertEqual(child.get("parent_run"), saved["parent"], "A crash exposed a branch as an unrestricted standalone workflow")
        with self.assertRaises(BridgeError): service.step(saved["child"])
        service.resume(saved["parent"], background=False)
        result = self.finish(service, saved["parent"])
        self.assertEqual(result["status"], "complete")
        self.assertIn(saved["child"], [row["run_id"] for row in result["branches"]])
        self.assertEqual(len(list(self.root.glob("wf_*"))), 3)
        self.assertEqual(len(runtime.calls), 2)

    def test_tampered_inherited_capability_never_seeds_exploration(self):
        service, runtime = self.service(lambda *_: self.write())
        base_spec = self.spec()
        base_spec.pop("approaches")
        base_spec["strategy"] = "single-model"
        original = self.finish(service, service.create(base_spec)["id"])
        blob = self.root / original["id"] / ".objects" / original["artifacts"]["answer.txt"]["sha256"]
        blob.write_text("tampered inherited source")
        calls = len(runtime.calls)
        with self.assertRaises(BridgeError): service.create(self.spec(inherited_capability=original["id"]))
        self.assertEqual(len(runtime.calls), calls)


class IndependentAdversaryTests(unittest.TestCase):
    def service(self, responses):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        runtime = SequenceRuntime(responses)
        service = WorkflowService(runtime, Path(temporary.name) / "work")
        self.addCleanup(service.close)
        return service, runtime

    @staticmethod
    def instrument(expression):
        return {"name": "Double", "inputs": ["x"], "outputs": {"value": expression}}

    def spec(self, oracle=True):
        result = {"objective": "Challenge the artifact beyond the original case", "strategy": "adversarial-review",
                  "roles": {role: {"provider": "local", "model": "fixture"} for role in ["builder", "adversary"]},
                  "acceptance": [{"artifact": "double.json", "kind": "instrument", "input": {"x": 1}, "expected": {"value": 2}}]}
        if oracle:
            result["adversarial_oracles"] = {"double.json": self.instrument({"op": "mul", "args": [{"field": "x"}, 2]})}
        return result

    def response(self, expression):
        return {"actions": [{"tool": "construct_instrument", "name": "double.json", "spec": self.instrument(expression)}]}

    @staticmethod
    def proposal(expected):
        return {"counterexamples": [{"artifact": "double.json", "input": {"x": 2}, "expected": {"value": expected}, "reason": "Probe a different input"}], "feedback": "An authored adversarial fixture"}

    def test_model_expected_value_cannot_override_operator_reference(self):
        service, _ = self.service([self.response({"op": "mul", "args": [{"field": "x"}, 2]}), self.proposal(999)])
        ident = service.create(self.spec())["id"]
        service.step(ident)
        result = service.step(ident)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["adversarial_cases"][0]["expected"], {"value": 4})
        finding = next(e["detail"]["findings"][0] for e in result["events"] if e["kind"] == "adversarial_review")
        self.assertEqual(finding["verdict"], "COUNTEREXAMPLE_REJECTED")
        self.assertEqual(finding["claimed_expected"], {"value": 999})

    def test_confirmed_counterexample_invalidates_initial_pass(self):
        service, _ = self.service([self.response(2), self.proposal(2)])
        ident = service.create(self.spec())["id"]
        self.assertTrue(service.step(ident)["verification"]["passed"])
        result = service.step(ident)
        self.assertFalse(result["verification"]["passed"])
        self.assertNotEqual(result["status"], "complete")
        self.assertEqual(result["adversarial_cases"][0]["expected"], {"value": 4})
        self.assertEqual(result["spec"]["acceptance"][0]["expected"], {"value": 2})

    def test_unadjudicated_model_expectation_never_registers_a_capability(self):
        service, _ = self.service([self.response(2), self.proposal(999)])
        ident = service.create(self.spec(oracle=False))["id"]
        service.step(ident)
        result = service.step(ident)
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["adversarial_cases"], [])
        self.assertEqual(result["unadjudicated_counterexamples"][0]["verdict"], "UNADJUDICATED")
        self.assertEqual(service.capabilities()["capabilities"], [])


class IndependentPairedRetrievalTests(unittest.TestCase):
    def test_paired_arms_keep_equal_contracts_and_do_not_share_retrieved_source(self):
        from bridge.strategy_demo import demonstrate
        with tempfile.TemporaryDirectory() as directory:
            record = demonstrate(directory)
            root = Path(directory)
            control = json.loads((root / "no-retrieval-project.json").read_text())
            treatment = json.loads((root / "retrieval-project.json").read_text())
        control_spec = control["state"]["spec"]
        treatment_spec = treatment["state"]["spec"]
        self.assertEqual(set(treatment_spec["tool_permissions"]) - set(control_spec["tool_permissions"]), {"retrieve_source"})
        treatment_spec["tool_permissions"].remove("retrieve_source")
        self.assertEqual(control_spec, treatment_spec)
        self.assertNotIn("inherited_capability", control_spec)
        self.assertNotIn("source.json", control["files"])
        self.assertIn("source.json", treatment["files"])
        self.assertEqual(control["files"]["task-context.txt"], treatment["files"]["task-context.txt"])
        arms = {arm["arm"]: arm for arm in record["arms"]}
        for arm in arms.values():
            self.assertEqual((arm["model_calls"], arm["actions"]), (2, 2))
            self.assertEqual(arm["status"], "complete")
        self.assertTrue(arms["no-retrieval"]["honest_abstention"])
        self.assertEqual(arms["no-retrieval"]["fixture_source_fetches"], 0)
        self.assertEqual(arms["retrieval"]["fixture_source_fetches"], 1)
        self.assertTrue(arms["retrieval"]["matches_withheld_source"])
        self.assertEqual(record["competent_conventional_control"]["model_calls"], 0)
        self.assertFalse(record["complete_economic_cost"]["known"])

    def test_paired_fact_result_changes_with_source_bytes_not_a_fixed_answer(self):
        from bridge.strategy_demo import demonstrate
        with tempfile.TemporaryDirectory() as directory, patch("bridge.strategy_demo.SOURCE_TEXT", "Synthetic approved gain coefficient is 17. Date unknown."):
            record = demonstrate(directory)
        arms = {arm["arm"]: arm for arm in record["arms"]}
        self.assertEqual(arms["retrieval"]["resolved_coefficient"], 17)
        self.assertIsNone(arms["no-retrieval"]["resolved_coefficient"])
        self.assertEqual(record["competent_conventional_control"]["coefficient"], 17)

    def test_missing_ground_truth_cannot_produce_a_successful_comparison(self):
        from bridge.strategy_demo import demonstrate
        with tempfile.TemporaryDirectory() as directory, patch("bridge.strategy_demo.SOURCE_TEXT", "No coefficient is supplied in this synthetic record."):
            with self.assertRaises((ValueError, BridgeError)):
                demonstrate(directory)


if __name__ == "__main__":
    unittest.main()
