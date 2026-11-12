# SPDX-License-Identifier: Apache-2.0
import http.client
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile

from bridge.adapters import BridgeError
from bridge.instruments import compile_formula, evaluate
from bridge.server import HarnessServer
from bridge.workflows import WorkflowService
from bridge import workshop, workshop_protocol


def candidate(expression, **unexpected):
    return json.dumps({"summary": "A direct formula or ordinary spreadsheet could implement this.",
                       "inputs": ["x"], "bindings": {}, "outputs": {"result": expression}, **unexpected})


class AuthoredTransport:
    """Deterministic model responses exercise transport-independent guards only."""
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.prompts = []

    def status(self):
        return {"providers": [{"id": "fixture", "ready": True, "models": ["author"], "local": True}]}

    def generate(self, request):
        self.prompts.append(request["prompt"])
        return {"text": next(self.responses), "model": "author", "qualification": "AUTHORED_FIXTURE"}

    def redact(self, value):
        return value

    def cancel(self, _):
        pass


def authored_request(marker="1", values=(1, 2, 90317)):
    return {"request_id": marker * 32, "family": "custom", "objective": "Prepare a shipping calculator",
            "provider": "fixture", "model": "author", "consent": "local",
            "context": "Input x is a package count. Output result is twice x.",
            "cases": [{"input": {"x": x}, "expected": {"result": x * 2}} for x in values]}


class FormulaTests(unittest.TestCase):
    def test_nested_comparison_operands_share_one_compilation(self):
        formula = "True"
        for _ in range(22):
            formula = f"True == ({formula}) == True"
        compiled = compile_formula(formula, {})
        for _ in range(22):
            left, right = compiled["args"]
            shared = left["args"][1]
            self.assertIs(shared, right["args"][0])
            compiled = shared
        self.assertIs(compiled, True)
        with self.assertRaisesRegex(ValueError, "operation or nesting bound"):
            evaluate({"inputs": [], "outputs": {"result": {"formula": formula}}}, {}, max_operations=30)

    def test_formula_bindings_and_lazy_branch(self):
        spec = {"inputs": ["x"], "bindings": {"twice": {"formula": "2 * x"}},
                "outputs": {"result": {"formula": "twice if 0 <= x <= 10 else None"}}}
        self.assertEqual(evaluate(spec, {"x": 8})["output"], {"result": 16})
        self.assertEqual(evaluate(spec, {"x": -1})["output"], {"result": None})
        spec["outputs"]["result"] = {"formula": "0 if x == 0 else 1 / x"}
        self.assertEqual(evaluate(spec, {"x": 0})["output"], {"result": 0})
        spec["outputs"]["result"] = {"formula": "choose(x >= 0 && x <= 10 || x == 15, 'a&&b', 'c||d')"}
        self.assertEqual(evaluate(spec, {"x": 15})["output"], {"result": "a&&b"})
        self.assertEqual(evaluate(spec, {"x": 20})["output"], {"result": "c||d"})

    def test_active_python_and_cycles_refused(self):
        for text in ('__import__("os")', 'x.__class__', 'x[0]', '[z for z in x]', 'lambda: x',
                     'min(x=1)', '1e400', 'x ** 4', '().__class__.__mro__'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                evaluate({"inputs": ["x"], "outputs": {"result": {"formula": text}}}, {"x": 1})
        with self.assertRaisesRegex(ValueError, "cycle"):
            evaluate({"inputs": [], "bindings": {"a": {"formula": "a + 1"}},
                      "outputs": {"result": {"ref": "a"}}}, {})
        with self.assertRaisesRegex(ValueError, "bound"):
            evaluate({"inputs": ["x"], "outputs": {"result": {"formula": "x + x"}}}, {"x": 1}, 2)


class WorkshopTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def service(self, runtime, directory="a"):
        value = WorkflowService(runtime, Path(self.folder.name) / directory)
        self.addCleanup(value.close)
        return value

    def test_final_cases_withheld_and_failure_stops_admission(self):
        runtime = AuthoredTransport(candidate("2 * x if x < 100 else 0"))
        service = self.service(runtime)
        created = workshop.register(service, authored_request())
        result = service.step(created["id"])
        self.assertEqual(result["status"], "needs_review")
        self.assertNotIn("90317", runtime.prompts[0])
        self.assertNotIn("180634", runtime.prompts[0])
        self.assertEqual([e["detail"]["stage"] for e in result["events"] if e["kind"] == "verification"],
                         ["development", "final"])
        self.assertEqual(workshop.view(service, result)["docket"]["status"], "rejected")
        self.assertEqual(service.capabilities(), {"capabilities": []})

    def test_duplicate_revision_revoke_and_fresh_inheritance(self):
        runtime = AuthoredTransport(candidate("2 * x"), json.dumps({"inputs": [], "bindings": {}, "outputs": {}, "summary": "Keep the prior instrument."}))
        service = self.service(runtime)
        request = authored_request()
        first = workshop.register(service, request)
        self.assertEqual(workshop.register(service, request)["id"], first["id"])
        with self.assertRaises(BridgeError) as caught:
            workshop.register(service, dict(request, objective="Different"))
        self.assertEqual(caught.exception.code, "WORKSHOP_CONFLICT")
        service.step(first["id"])
        first = workshop.operate(service, "get", {"run_id": first["id"]})
        self.assertEqual(first["docket"]["status"], "admitted")
        with self.assertRaises(BridgeError):
            workshop.register(service, dict(authored_request("2"), inherit=first["id"], loop="successor"))
        with self.assertRaisesRegex(BridgeError, "fresh independent"):
            workshop.register(service, dict(authored_request("5", (1.0, 2.0, 90317.0)), inherit=first["id"], loop="successor"))
        new_interface = authored_request("6", (14, 16, 19))
        for case in new_interface["cases"]:
            case["expected"] = {"different": case["expected"]["result"]}
        with self.assertRaisesRegex(BridgeError, "does not cover this scope"):
            workshop.register(service, dict(new_interface, inherit=first["id"], loop="successor"))
        second = workshop.register(service, dict(authored_request("3", (14, 16, 19)), inherit=first["id"], loop="successor"))
        self.assertEqual(second["docket"]["status"], "open")
        self.assertEqual(service.step(second["id"])["status"], "complete")
        with self.assertRaises(BridgeError):
            workshop.operate(service, "revoke", {"run_id": first["id"], "revision": "a" * 64})
        revoked = workshop.operate(service, "revoke", {"run_id": first["id"], "revision": first["revision"]})
        self.assertEqual(revoked["docket"]["status"], "revoked")
        with self.assertRaises(BridgeError):
            service.reuse(first["id"], {"x": 3})
        with self.assertRaises(BridgeError):
            workshop.register(service, dict(authored_request("4", (42, 43, 44)), inherit=first["id"], loop="successor"))
        self.assertEqual(len(workshop.list_missions(service)["missions"]), 2)
        self.assertEqual(len(workshop.list_missions(self.service(runtime, "separate"))["missions"]), 0)

    def test_repair_reuses_contract_and_preserves_failed_response(self):
        runtime = AuthoredTransport(candidate("x/0"), candidate("2*x"))
        service = self.service(runtime)
        state = workshop.register(service, authored_request())
        self.assertEqual(service.step(state["id"])["status"], "ready")
        self.assertEqual(service.step(state["id"])["status"], "complete")
        self.assertIn("Division by zero", runtime.prompts[1])
        self.assertNotIn("90317", runtime.prompts[1])
        state = workshop.operate(service, "get", {"run_id": state["id"]})
        bundle = workshop.bundle(service, {"run_id": state["id"], "revision": state["revision"]})
        with zipfile.ZipFile(io.BytesIO(bundle)) as exported:
            self.assertIn("RUN_WORKSHOP.py", exported.namelist())
            history = json.loads(exported.read("WORKFLOW-EXPORT.json"))["state"]["events"]
            self.assertEqual([json.loads(e["detail"]["response"]) for e in history if e["kind"] == "model_completed"],
                             [json.loads(candidate("x/0")), json.loads(candidate("2*x"))])
            proof = json.loads(exported.read("PROOF.json"))
            self.assertEqual([case["stage"] for case in proof["observations"]], ["development", "development", "final"])

    def test_permission_boundary_and_source_change(self):
        runtime = AuthoredTransport(candidate("2*x", name="../secret", tool="shell"), candidate("2*x"))
        service = self.service(runtime)
        state = workshop.register(service, authored_request())
        failed = service.step(state["id"])
        self.assertTrue(any(e["kind"] == "response_refused" for e in failed["events"]))
        self.assertFalse(failed["artifacts"])
        service.step(state["id"])
        with patch("bridge.workshop.source_hashes", return_value={}):
            stale = workshop.operate(service, "get", {"run_id": state["id"]})
            self.assertEqual(stale["docket"]["status"], "stale")
            self.assertFalse(stale["docket"]["passed"])
            self.assertEqual(stale["docket"]["accepted"], 3)
            with self.assertRaises(BridgeError):
                service.reuse(state["id"], {"x": 3})

    def test_late_model_result_cannot_apply_after_cancellation(self):
        entered, release = threading.Event(), threading.Event()
        class Delayed(AuthoredTransport):
            def generate(self, request):
                entered.set()
                if not release.wait(4):
                    raise RuntimeError("test timed out")
                return super().generate(request)
        service = self.service(Delayed(candidate("2*x")))
        state = workshop.register(service, authored_request())
        service.start(state["id"])
        self.assertTrue(entered.wait(3))
        live = workshop.operate(service, "get", {"run_id": state["id"]})
        workshop.operate(service, "cancel", {"run_id": live["id"], "revision": live["revision"]})
        release.set()
        for _ in range(100):
            current = service.get(state["id"])
            if not current["worker_active"]:
                break
            time.sleep(.025)
        self.assertEqual(current["status"], "cancelled")
        self.assertFalse(current["artifacts"])
        self.assertTrue(any(e["kind"] == "late_result_discarded" for e in current["events"]))

    def test_http_origin_session_and_workspace_boundary(self):
        server = HarnessServer(("127.0.0.1", 0), workspace=Path(self.folder.name) / "http")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def call(origin, token):
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
                headers = {"Origin": origin, "X-Harness-Token": token, "Content-Type": "application/json"}
                connection.request("POST", "/api/workshop/list", "{}", headers=headers)
                reply = connection.getresponse()
                result = reply.status, json.loads(reply.read())
                connection.close()
                return result
            self.assertEqual(call("https://example.com", server.token)[1]["error"]["code"], "ORIGIN")
            self.assertEqual(call(server.origin, "different-session")[1]["error"]["code"], "TOKEN")
            self.assertEqual(call(server.origin, server.token), (200, {"missions": []}))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


class ControlTests(unittest.TestCase):
    def test_strong_controls_tie_and_raw_sample_aliases_two_outcomes(self):
        rows = workshop_protocol.observations("foundry")
        controls = workshop_protocol.compare("foundry", rows)
        self.assertEqual(len(rows), 18)
        for arm in ("stdlib_fit", "exact_interpolation"):
            self.assertEqual([row["output"] for row in controls[arm]], [row["expected"] for row in rows])
        a, b = rows[:2]
        self.assertEqual(a["input"]["reading"], b["input"]["reading"])
        self.assertNotEqual(a["expected"]["defect"], b["expected"]["defect"])
        self.assertNotEqual(controls["sample_only"][1]["defect"], b["expected"]["defect"])
        self.assertEqual({row["profile"] for row in rows}, {"optics", "pressure", "cold"})

    def test_adapters_reject_malformed_and_ambiguous_inputs(self):
        for profile, bad in (
            ("pressure", '{"references_kpa":[1,2,3],"sample_kpa":1,"sample_kpa":2,"traceable":true,"affine":true}'),
            ("optics", "ref0_um,ref5_um,ref10_um,sample_um,traceable,affine\n1,2,3,4,1,1,extra"),
            ("cold", "sample=3\nsample=4"),
        ):
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                workshop_protocol.normalize(profile, bad)


if __name__ == "__main__":
    unittest.main()
