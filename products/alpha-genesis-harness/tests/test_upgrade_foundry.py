# SPDX-License-Identifier: Apache-2.0
"""Foundry contract tests; synthetic Codex and sandbox responses, no model calls.

No generated candidate Python is imported or executed in this host process.
The evaluator fixture executes only the existing trusted instrument evaluator.
"""
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError, Runtime
from bridge.chatgpt import ChatGPTPlanService
from bridge.codex import CodexService
from bridge.instruments import evaluate
from bridge.upgrade_foundry import UpgradeFoundryService, NativeEvaluator, EDITABLE, _CHILD
from bridge.workflows import WorkflowService
from bridge.services import AccessRuntime
from test_chatgpt import FakeTransport, seed
from test_codex import ProcessFixture


class EvaluatorFixture:
    """Trusted baseline computation supplies protocol responses, not candidate proof."""
    def __init__(self): self.calls = []; self.fail = False; self.bad = False
    def run(self, directory, cases, *, cancel=None):
        self.calls.append((Path(directory), copy.deepcopy(cases)))
        if self.fail: raise BridgeError("CODEX_SANDBOX_UNAVAILABLE", "Synthetic unavailable host")
        if self.bad: return [{"id": c["id"], "output": {"result": -999999}} for c in cases]
        rows = []
        for case in cases:
            try: rows.append({"id": case["id"], "output": evaluate(case["instrument"], case["inputs"], case["max_operations"])["output"]})
            except Exception: rows.append({"id": case["id"], "error": True})
        return rows


class FoundryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.runtime = AccessRuntime(Runtime({}), private_root=self.root / "runtime")
        self.workflows = WorkflowService(self.runtime, self.root / "workflows")
        self.transport = FakeTransport()
        self.plan = ChatGPTPlanService({"allow_plan_usage": True, "distribution": "open-source-local"}, self.root / "auth", self.transport)
        seed(self.plan)
        self.process_calls = []; self.other_edit = False; self.no_edit = False; self.extra_file = False
        self.messages = [{"id": 0, "result": {}}, {"id": 1, "result": {"thread": {"id": "thread-one"}, "activePermissionProfile": {"id": "harness_isolated"}}},
                         {"id": 2, "result": {"turn": {"id": "turn-one"}}},
                         {"method": "item/started", "params": {"threadId": "thread-one", "turnId": "turn-one", "item": {"id": "foundry-answer", "type": "agentMessage", "text": "", "phase": "final_answer"}}},
                         {"method": "item/agentMessage/delta", "params": {"threadId": "thread-one", "turnId": "turn-one", "itemId": "foundry-answer", "delta": "Authored fixture source alteration, not a model result"}},
                         {"method": "item/completed", "params": {"threadId": "thread-one", "turnId": "turn-one", "item": {"id": "foundry-answer", "type": "agentMessage", "text": "Authored fixture source alteration, not a model result", "phase": "final_answer"}}},
                         {"method": "turn/completed", "params": {"threadId": "thread-one", "turn": {"id": "turn-one", "status": "completed"}}}]
        def factory(command, **kwargs):
            self.process_calls.append((command, kwargs))
            directory = Path(kwargs["cwd"])
            if not self.no_edit:
                target = directory / EDITABLE
                target.write_text(target.read_text() + "\n# Contract fixture source alteration; no model inference.\n")
            if self.other_edit: (directory / "bridge" / "workflows.py").write_text("not authorized")
            if self.extra_file: (directory / "extra.py").write_text("raise RuntimeError('never execute')")
            return ProcessFixture(self.messages)
        self.codex = CodexService({"allow_execution": True, "allow_workspace_write": True, "executable": sys.executable},
                                 self.plan, self.root / "codex", factory, sandbox_validator=lambda _: None, runtime_probe=lambda *args: None)
        self.runtime._services.update(codex=self.codex, chatgpt=self.plan)
        self.evaluator = EvaluatorFixture()
        self.service = UpgradeFoundryService(self.workflows, self.codex, evaluator=self.evaluator)

    def tearDown(self):
        self.service.close(); self.codex.close(); self.plan.close(); self.workflows.close(); self.temp.cleanup()

    def register(self):
        return self.service.register({"objective": "Reduce repeated interpreter work while preserving acceptance", "model": "account-model"})["experiment"]

    def construct(self):
        exp = self.register()
        return self.service.construct({"experiment_id": exp["id"], "authorize": True})["experiment"]

    def qualify(self):
        exp = self.construct()
        return self.service.qualify({"experiment_id": exp["id"], "authorize": True})["experiment"]

    def test_register_freezes_source_and_external_protocol_before_construction(self):
        exp = self.register()
        self.assertEqual(exp["status"], "registered")
        self.assertEqual(exp["editable_paths"], [EDITABLE])
        self.assertNotIn("protocol", exp)
        base = self.service.root / exp["id"]
        self.assertTrue((base / "baseline" / EDITABLE).is_file())
        self.assertTrue((base / "PROTOCOL.json").is_file())
        self.assertFalse(self.process_calls)
        with self.assertRaises(BridgeError): self.service.export({"experiment_id": exp["id"]})

    def test_construction_explicit_permission_and_native_probe_first(self):
        exp = self.register()
        with self.assertRaises(BridgeError): self.service.construct({"experiment_id": exp["id"]})
        self.codex.config["allow_workspace_write"] = False
        with self.assertRaises(BridgeError): self.service.construct({"experiment_id": exp["id"], "authorize": True})
        self.assertFalse(self.process_calls)

    def test_direct_service_local_only_refuses_before_codex_dispatch(self):
        for source in ("facade", "base"):
            with self.subTest(source=source):
                exp = self.register()
                previous = self.runtime.base.local_only
                if source == "facade":
                    self.runtime.config["local_only"] = True
                else:
                    self.runtime.base.local_only = True
                try:
                    with self.assertRaises(BridgeError) as error:
                        self.service.construct({"experiment_id": exp["id"], "authorize": True})
                    self.assertEqual(error.exception.code, "LOCAL_ONLY")
                    self.assertFalse(self.process_calls)
                finally:
                    self.runtime.config.pop("local_only", None)
                    self.runtime.base.local_only = previous

    def test_direct_service_without_shared_admission_fails_closed(self):
        exp = self.register()
        self.workflows.runtime = Runtime({})
        try:
            with self.assertRaises(BridgeError) as error:
                self.service.construct({"experiment_id": exp["id"], "authorize": True})
            self.assertEqual(error.exception.code, "FOUNDRY_EXECUTION_ADMISSION")
            self.assertFalse(self.process_calls)
        finally:
            self.workflows.runtime = self.runtime

    def _queue_construction(self, exp):
        results, errors = [], []
        def run():
            try:
                results.append(self.service.construct({"experiment_id": exp["id"], "authorize": True}))
            except Exception as error:
                errors.append(error)
        worker = threading.Thread(target=run)
        worker.start()
        gate = self.plan._harness_execution_gate
        deadline = time.monotonic() + 3
        while worker.is_alive() and time.monotonic() < deadline:
            with gate.condition:
                if gate.waiters:
                    return worker, results, errors
            time.sleep(.01)
        worker.join(1)
        self.fail("Foundry did not wait behind the existing account execution slot: " + repr(errors))

    def test_foundry_shares_plan_queue_and_cancelled_waiter_never_dispatches(self):
        exp = self.register()
        with self.runtime.execution_slot({"provider": "codex", "model": "account-model"}):
            worker, results, errors = self._queue_construction(exp)
            try:
                self.assertFalse(self.process_calls)
                self.assertTrue(self.service.cancel({"experiment_id": exp["id"]})["cancelled"])
                worker.join(3)
                self.assertFalse(worker.is_alive())
            finally:
                self.service.cancel({"experiment_id": exp["id"]})
                worker.join(3)
        self.assertFalse(results)
        self.assertTrue(errors and isinstance(errors[0], BridgeError))
        self.assertIn(errors[0].code, {"CANCELLED", "FOUNDRY_CANCELLED"})
        self.assertFalse(self.process_calls)
        row = next(row for row in self.service.status()["experiments"] if row["id"] == exp["id"])
        self.assertFalse(row["events"][-1]["dispatch_started"])

    def test_foundry_queue_reconnect_refuses_stale_identity_before_dispatch(self):
        exp = self.register()
        with self.runtime.execution_slot({"provider": "codex", "model": "account-model"}):
            worker, results, errors = self._queue_construction(exp)
            try:
                with self.plan.store.locked():
                    state = self.plan.store.read()
                    state["authorization_epoch"] = state.get("authorization_epoch", 0) + 1
                    self.plan.store.write(state)
                worker.join(3)
                self.assertFalse(worker.is_alive())
            finally:
                self.service.cancel({"experiment_id": exp["id"]})
                worker.join(3)
        self.assertFalse(results)
        self.assertTrue(errors and isinstance(errors[0], BridgeError))
        self.assertEqual(errors[0].code, "EXECUTION_IDENTITY_CHANGED")
        self.assertFalse(self.process_calls)

    def test_seeded_constructor_rechecks_admitted_identity_after_native_probe(self):
        exp = self.register()
        def reconnect_during_probe(*args):
            with self.plan.store.locked():
                state = self.plan.store.read()
                state["authorization_epoch"] = state.get("authorization_epoch", 0) + 1
                self.plan.store.write(state)
        self.codex.runtime_probe = reconnect_during_probe
        with self.assertRaises(BridgeError) as error:
            self.service.construct({"experiment_id": exp["id"], "authorize": True})
        self.assertEqual(error.exception.code, "CHATGPT_ACCOUNT_CHANGED")
        self.assertFalse(self.process_calls)

    def test_constructed_code_cannot_edit_independent_evaluator_or_other_source(self):
        for edit in ("other_edit", "extra_file"):
            with self.subTest(edit=edit):
                setattr(self, edit, True); exp = self.register()
                with self.assertRaises(BridgeError) as error:
                    self.service.construct({"experiment_id": exp["id"], "authorize": True})
                self.assertEqual(error.exception.code, "FOUNDRY_SCOPE")
                setattr(self, edit, False)
        self.assertIsNone(self.service.status()["active_candidate"])

    def test_unchanged_model_result_is_not_a_constructed_upgrade(self):
        self.no_edit = True; exp = self.register()
        with self.assertRaises(BridgeError) as error: self.service.construct({"experiment_id": exp["id"], "authorize": True})
        self.assertEqual(error.exception.code, "FOUNDRY_NO_CHANGE")

    def test_end_to_end_contract_qualification_retention_and_rollback(self):
        exp = self.qualify()
        self.assertEqual(exp["qualification"]["correctness"], "PASS")
        self.assertEqual(exp["qualification"]["arms"]["candidate"]["cases"], 52)
        self.assertEqual(exp["qualification"]["arms"]["ordinary_direct_arithmetic"]["cases"], 48)
        self.assertEqual(exp["qualification"]["general_improvement"], "NOT_ESTABLISHED")
        with self.assertRaises(BridgeError): self.service.activate({"experiment_id": exp["id"], "authorize": True, "expected_candidate_sha256": "wrong"})
        self.service.activate({"experiment_id": exp["id"], "authorize": True, "expected_candidate_sha256": exp["candidate_sha256"]})
        case = self.evaluator.calls[-1][1][0]
        result = self.service.evaluate_retained({k: case[k] for k in ("instrument", "inputs", "expected", "max_operations")})
        self.assertTrue(result["execution"]["accepted"])
        self.assertEqual(len(self.evaluator.calls), 3)
        self.assertTrue(self.evaluator.calls[2][0].is_relative_to(self.service.root))
        exported = self.service.export({"experiment_id": exp["id"]})
        self.assertIn("candidate_source", exported["experiment"])
        self.assertIn("protocol", exported["experiment"])
        self.assertNotIn("source_files", exported["experiment"])
        self.service.rollback({"authorize": True})
        self.assertIsNone(self.service.status()["active_candidate"])
        with self.assertRaises(BridgeError): self.service.evaluate_retained({"instrument": {}, "inputs": {}})

    def test_wrong_candidate_outputs_fail_parent_decision(self):
        exp = self.construct(); self.evaluator.bad = True
        result = self.service.qualify({"experiment_id": exp["id"], "authorize": True})["experiment"]
        self.assertEqual(result["qualification"]["correctness"], "FAIL")
        with self.assertRaises(BridgeError): self.service.activate({"experiment_id": exp["id"], "authorize": True, "expected_candidate_sha256": exp["candidate_sha256"]})

    def test_native_sandbox_blocker_is_preserved_without_fallback(self):
        exp = self.construct(); self.evaluator.fail = True
        with self.assertRaises(BridgeError): self.service.qualify({"experiment_id": exp["id"], "authorize": True})
        state = self.service.status(); failed = next(e for e in state["experiments"] if e["id"] == exp["id"])
        self.assertEqual(failed["status"], "qualification_blocked")
        self.assertEqual(failed["qualification"]["correctness"], "BLOCKED")
        self.assertIsNone(state["active_candidate"])

    def test_protocol_or_source_tamper_prevents_qualification(self):
        exp = self.construct()
        path = self.service.root / exp["id"] / "PROTOCOL.json"
        path.write_text("{}")
        with self.assertRaises(BridgeError): self.service.qualify({"experiment_id": exp["id"], "authorize": True})
        self.assertFalse(self.evaluator.calls)

    def test_candidate_change_after_qualification_refuses_retained_execution(self):
        exp = self.qualify()
        self.service.activate({"experiment_id": exp["id"], "authorize": True, "expected_candidate_sha256": exp["candidate_sha256"]})
        candidate = self.service.root / exp["candidate_relative"] / EDITABLE
        candidate.write_text(candidate.read_text() + "\n# changed after qualification")
        with self.assertRaises(BridgeError): self.service.evaluate_retained({"instrument": {}, "inputs": {}})
        self.assertEqual(len(self.evaluator.calls), 2)

    def test_candidate_verdict_and_extra_fields_are_not_acceptance_authority(self):
        cases = [{"id": "one", "expected": {"result": 3}}]
        for rows in ([{"id": "one", "passed": True}], [{"id": "other", "output": {"result": 3}}], []):
            with self.assertRaises(BridgeError): self.service._judge(cases, rows)

    def test_cancel_prevents_late_output_from_becoming_qualified(self):
        exp = self.construct()
        original = self.evaluator.run
        def cancel_then_return(directory, cases, *, cancel=None):
            cancel.set(); return original(directory, cases)
        self.evaluator.run = cancel_then_return
        with self.assertRaises(BridgeError) as error: self.service.qualify({"experiment_id": exp["id"], "authorize": True})
        self.assertEqual(error.exception.code, "FOUNDRY_CANCELLED")
        self.assertIsNone(self.service.status()["active_candidate"])


class NativeEvaluatorTests(unittest.TestCase):
    def test_probe_failure_prevents_candidate_process(self):
        called = []
        def fail(*args): raise BridgeError("CODEX_SANDBOX_UNAVAILABLE", "Synthetic denied host")
        def factory(*args, **kwargs): called.append((args, kwargs)); raise AssertionError("Must not execute")
        evaluator = NativeEvaluator(sys.executable, process_factory=factory, profile_validator=lambda _: None, runtime_probe=fail)
        with tempfile.TemporaryDirectory() as temp, self.assertRaises(BridgeError): evaluator.run(temp, [])
        self.assertFalse(called)

    def test_native_command_excludes_credentials_and_expected_answers(self):
        captured = []
        rows = [{"id": "case", "output": {"result": 3}}]
        def factory(command, **kwargs):
            captured.append((command, kwargs))
            self.process = ProcessFixture([{ "id": 0, "result": {}}, {"id": 1, "result": {"data": [{"id": "harness_isolated", "allowed": True}]}},
                       {"id": 2, "result": {"exitCode": 0, "stdout": json.dumps({"results": rows}), "stderr": ""}}])
            return self.process
        evaluator = NativeEvaluator(sys.executable, process_factory=factory, profile_validator=lambda _: None, runtime_probe=lambda *args: None)
        with tempfile.TemporaryDirectory() as temp, patch.dict("os.environ", {"OPENAI_API_KEY": "never-export", "ACCESS_TOKEN": "never-export"}):
            result = evaluator.run(temp, [{"id": "case", "instrument": {}, "inputs": {}, "max_operations": 100, "expected": {"result": 3}}])
        self.assertEqual(result, rows)
        command, options = captured[0]
        self.assertNotIn("OPENAI_API_KEY", options["env"])
        self.assertNotIn("ACCESS_TOKEN", options["env"])
        sent = [json.loads(line) for line in self.process.stdin.saved.splitlines()]
        execute = next(row for row in sent if row.get("method") == "command/exec")
        self.assertEqual(execute["params"]["permissionProfile"], "harness_isolated")
        inputs = json.loads(execute["params"]["command"][-1])
        self.assertNotIn("expected", inputs[0])
        self.assertIn('":root"="deny"', " ".join(command))
        self.assertIn('.network.enabled=false', " ".join(command))
        self.assertNotIn('="write"', " ".join(command))


if __name__ == "__main__": unittest.main()
