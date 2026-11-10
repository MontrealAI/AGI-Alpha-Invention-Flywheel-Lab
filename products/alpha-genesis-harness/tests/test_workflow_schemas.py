# SPDX-License-Identifier: Apache-2.0
"""Syntax constraints guide generation; frozen semantic acceptance stays decisive."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.instruments import evaluate
from bridge.output_schema import prepare_schema, validate_output, SchemaError
from bridge.workflow_demo import FixtureRuntime, proposal, specification
from bridge.workflow_schemas import response_schema, INSTRUMENT_GRAMMAR
from bridge.workflows import WorkflowService


def construct(expression, inputs=()):
    return {"summary": "Construct a bounded instrument", "actions": [{"tool": "construct_instrument",
            "name": "calculator.json", "spec": {"inputs": list(inputs), "outputs": {"result": expression}}}], "done": True}


class WorkflowSchemaTests(unittest.TestCase):
    def setUp(self):
        self.schema = prepare_schema(response_schema("builder", ["construct_instrument"]))

    def test_full_supported_nesting_boundary_without_recursive_references(self):
        expression = True
        for _ in range(32):
            expression = {"op": "not", "args": [expression]}
        value = construct(expression)
        validate_output(value, self.schema)
        self.assertEqual(evaluate(value["actions"][0]["spec"], {})["output"], {"result": True})
        deeper = construct({"op": "not", "args": [expression]})
        with self.assertRaises(SchemaError):
            validate_output(deeper, self.schema)
        with self.assertRaisesRegex(ValueError, "nesting bound"):
            evaluate(deeper["actions"][0]["spec"], {})

    def test_observed_shape_failures_are_rejected_without_repairing_content(self):
        valid = construct({"op": "mul", "args": [{"field": "x"}, 2]}, ["x"])
        malformed = []
        value = copy.deepcopy(valid)
        value["actions"][0]["spec"]["outputs"]["result"]["args"][1] = {"literal": 2}
        malformed.append(value)
        value = copy.deepcopy(valid)
        value["actions"][0]["spec"]["misplaced_result"] = True
        malformed.append(value)
        value = copy.deepcopy(valid)
        value["actions"].append('done”:true}{')
        malformed.append(value)
        value = copy.deepcopy(valid)
        action = value["actions"][0]
        value["actions"][0] = {"tool": action["tool"], "arguments": {k: v for k, v in action.items() if k != "tool"}}
        malformed.append(value)
        for value in malformed:
            before = copy.deepcopy(value)
            with self.subTest(value=value), self.assertRaises(SchemaError):
                validate_output(value, self.schema)
            self.assertEqual(value, before)
        validate_output(valid, self.schema)

    def test_syntax_acceptance_does_not_claim_semantic_correctness(self):
        value = construct({"op": "mul", "args": [{"field": "x"}, {"field": "x"}]}, ["x"])
        validate_output(value, self.schema)
        self.assertEqual(evaluate(value["actions"][0]["spec"], {"x": 3})["output"], {"result": 9})
        runtime = FixtureRuntime([value])
        runtime.provider = lambda _: SimpleNamespace(remote=False, kind="openai", models={"fixture": SimpleNamespace(json_schema=True)})
        spec = specification()
        spec.update(roles={"builder": {"provider": "fixture", "model": "fixture"}}, strategy="single-model", max_iterations=1)
        spec["acceptance"] = [{"kind": "instrument", "artifact": "calculator.json", "input": {"x": 3}, "expected": {"result": 6}}]
        with tempfile.TemporaryDirectory() as folder:
            service = WorkflowService(runtime, folder)
            try:
                state = service.create(spec)
                while state["status"] == "ready":
                    state = service.step(state["id"])
                self.assertEqual(state["status"], "exhausted")
                self.assertFalse(state["verification"]["passed"])
                self.assertEqual(state["verification"]["checks"][0]["actual"], {"result": 9})
                self.assertEqual(state["model_calls"], 1)
                self.assertIsNone(state["capability_id"])
            finally:
                service.close()

    def test_tool_permissions_and_remaining_allocation_constrain_only_actions(self):
        read = {"summary": "Read", "actions": [{"tool": "read_artifact", "name": "report.md"}], "done": False}
        with self.assertRaises(SchemaError):
            validate_output(read, self.schema)
        readable = prepare_schema(response_schema("builder", ["read_artifact"], 1))
        validate_output(read, readable)
        read["actions"] *= 2
        with self.assertRaises(SchemaError):
            validate_output(read, readable)
        for permissions, remaining in (([], 8), (["read_artifact"], 0)):
            bounded = prepare_schema(response_schema("builder", permissions, remaining))
            with self.assertRaises(SchemaError):
                validate_output(read, bounded)
            validate_output({"summary": "No action authorized", "actions": [], "done": True}, bounded)

    def test_all_tools_have_exact_arguments_and_generic_data(self):
        tools = ["write_document", "write_dataset", "construct_instrument", "run_instrument", "read_artifact", "retrieve_source"]
        schema = prepare_schema(response_schema("builder", tools))
        actions = [
            {"tool": "write_document", "name": "report.md", "content": "Report"},
            {"tool": "write_dataset", "name": "data.csv", "columns": ["n"], "rows": [[1], [None]]},
            construct([1, True, None, "text"])["actions"][0],
            {"tool": "run_instrument", "name": "calculator.json", "input": {"nested": {"array": [1, None]}}},
            {"tool": "read_artifact", "name": "report.md"},
            {"tool": "retrieve_source", "name": "source.json", "url": "https://example.test/source"},
        ]
        validate_output({"summary": "Permitted syntax", "actions": actions, "done": True}, schema)
        for action in actions:
            changed = dict(action, shell="forbidden")
            with self.subTest(tool=action["tool"]), self.assertRaises(SchemaError):
                validate_output({"summary": "Invalid", "actions": [changed], "done": True}, schema)

    def test_critic_schema_requires_exact_review_and_bounded_feedback(self):
        schema = prepare_schema(response_schema("critic"))
        validate_output({"verdict": "revise", "feedback": "Recorded evidence fails."}, schema)
        for value in ({"verdict": "approve", "feedback": "ok"},
                      {"verdict": "accept", "feedback": "ok", "actions": []},
                      {"verdict": "accept", "feedback": "x" * 12001}):
            with self.subTest(value=str(value)[:80]), self.assertRaises(SchemaError):
                validate_output(value, schema)

    def test_schema_is_fresh_and_contains_no_task_specific_answers(self):
        first = response_schema("builder", ["construct_instrument"])
        second = response_schema("builder", ["construct_instrument"])
        first["$defs"]["expr0"]["anyOf"].clear()
        self.assertNotEqual(first, second)
        self.assertNotIn("expected", json.dumps(second))
        self.assertNotIn("quote.json", json.dumps(second))
        self.assertNotIn("within_capacity", json.dumps(second))


class WorkflowSchemaIntegrationTests(unittest.TestCase):
    def run_fixture(self, capability, kind="openai", remote=False, analysis=False):
        outputs = (["supplied-context research"] if analysis else []) + [proposal(True), {"verdict": "accept", "feedback": "Cases pass."}]
        runtime = FixtureRuntime(outputs)
        runtime.provider = lambda _: SimpleNamespace(remote=remote, kind=kind, models={"fixture": SimpleNamespace(json_schema=capability, json_mode=True)})
        spec = specification()
        spec["local_only"] = not remote
        if analysis:
            spec["roles"]["researcher"] = {"provider": "fixture", "model": "fixture"}
        spec["roles"] = {role: {"provider": "fixture", "model": "fixture"} for role in spec["roles"]}
        spec["tool_permissions"] = ["construct_instrument"]
        with tempfile.TemporaryDirectory() as folder:
            service = WorkflowService(runtime, folder)
            try:
                state = service.create(spec)
                while state["status"] == "ready":
                    state = service.step(state["id"])
                self.assertEqual(state["status"], "complete")
            finally:
                service.close()
        return runtime.calls

    def test_explicit_local_capability_gets_role_schema_and_shared_grammar(self):
        calls = self.run_fixture(True, analysis=True)
        self.assertNotIn("json_schema", calls[0])
        for call in calls[1:]:
            prepare_schema(call["json_schema"])
            self.assertIn(INSTRUMENT_GRAMMAR, call["prompt"])
            self.assertNotIn("json_mode", call)
        tools = calls[1]["json_schema"]["properties"]["actions"]["items"]["anyOf"]
        self.assertEqual([tool["properties"]["tool"]["const"] for tool in tools], ["construct_instrument"])
        self.assertEqual(calls[2]["json_schema"], response_schema("critic"))

    def test_no_implicit_schema_support_for_plain_remote_or_subscription_routes(self):
        for capability, kind, remote in ((False, "openai", False), (True, "openai", True),
                                        (True, "anthropic", True), (True, "chatgpt", True), (True, "codex", True)):
            with self.subTest(capability=capability, kind=kind, remote=remote):
                self.assertTrue(all("json_schema" not in call for call in self.run_fixture(capability, kind, remote)))


if __name__ == "__main__":
    unittest.main()
