# SPDX-License-Identifier: Apache-2.0
"""Deterministic offline qualification, explicitly not live model integration."""
import json
from pathlib import Path
from types import SimpleNamespace

from .workflows import WorkflowService, encoded


class FixtureRuntime:
    """Authored responses exercise orchestration; they do not impersonate a model."""
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def provider(self, ident):
        return SimpleNamespace(remote=False)

    def status(self):
        return {"providers": [{"id": "fixture", "local": True}]}

    def generate(self, data):
        self.calls.append(data)
        response = next(self.responses)
        return {"provider": "fixture", "model": data["model"], "text": json.dumps(response), "usage": {"input_tokens": None, "output_tokens": None},
                "cost": {"amount": None, "basis": "AUTHORED_FIXTURE_NO_INFERENCE", "complete_cost_known": False}, "qualification": "AUTHORED_FIXTURE_NOT_LIVE_MODEL"}

    def cancel(self, ident):
        return {"run_id": ident, "cancelled": False}


def instrument(correct=True):
    multiplication = {"op": "mul", "args": [{"field": "x"}, {"field": "gain"}]}
    return {"name": "Affine measurement / production instrument", "inputs": ["x", "gain", "offset"],
            "outputs": {"result": {"op": "add", "args": [multiplication, {"field": "offset"}]} if correct else multiplication},
            "conditions": "An affine input-output relationship is independently justified; units must match.",
            "limitations": "The arithmetic does not establish a causal model, real measurements or profitable demand."}


def proposal(correct=True):
    return {"summary": "Construct a bounded affine calculator.", "actions": [{"tool": "construct_instrument", "name": "affine.json", "spec": instrument(correct)}], "done": True}


def specification(objective="Calibrate a sensor under a supplied affine calibration", successor=False):
    cases = [({"x": 2, "gain": 3, "offset": 4}, {"result": 10}), ({"x": 0, "gain": 3, "offset": 7}, {"result": 7})]
    if successor:
        cases = [({"x": 17, "gain": 41, "offset": 101}, {"result": 798}), ({"x": 3, "gain": 127, "offset": 29}, {"result": 410})]
    return {"objective": objective, "context": "Synthetic cases with operator-supplied expected values; no factual market or physical claims.",
            "roles": {"builder": {"provider": "fixture", "model": "authored-builder"}, "critic": {"provider": "fixture", "model": "authored-critic"}},
            "acceptance": [{"kind": "instrument", "artifact": "affine.json", "input": inputs, "expected": expected} for inputs, expected in cases],
            "max_iterations": 3, "max_actions": 10, "local_only": True}


def demonstrate(workspace, output=None):
    runtime = FixtureRuntime([proposal(False), {"verdict": "revise", "feedback": "The instrument omits offset; both frozen cases fail."}, proposal(True), {"verdict": "accept", "feedback": "Both explicit cases now pass. General applicability remains unverified."}])
    service = WorkflowService(runtime, workspace)
    first = service.create(specification())
    state = first
    while state["status"] not in {"complete", "failed", "exhausted", "needs_review", "paused"}:
        state = service.step(first["id"])
    if state["status"] != "complete":
        raise ValueError("Fixture construction failed.")
    # Reopen from the persisted checkpoint through a separately constructed service.
    reopened = WorkflowService(runtime, workspace)
    inherited = specification("Estimate a production order: quantity × unit cost + setup", successor=True)
    inherited["inherited_capability"] = state["id"]
    successor = reopened.create(inherited)
    new_input = inherited["acceptance"][0]["input"]
    reuse = reopened.reuse(state["id"], new_input)
    ordinary = new_input["x"] * new_input["gain"] + new_input["offset"]
    assert reuse["outputs"]["affine.json"]["output"]["result"] == ordinary == 798
    # A capable fresh-construction control has the same information and grammar.
    control_runtime = FixtureRuntime([proposal(True), {"verdict": "accept", "feedback": "Both operator cases pass."}])
    control_service = WorkflowService(control_runtime, Path(workspace) / "control")
    control = control_service.create(specification("Estimate a production order: quantity × unit cost + setup", successor=True))
    while control["status"] not in {"complete", "failed", "exhausted", "needs_review", "paused"}:
        control = control_service.step(control["id"])
    result = {"schema": "alpha-genesis-workflow-demo/v1", "scope": "Authored offline protocol qualification. No live inference, empirical novelty, commercial demand or general discovery advantage.",
              "construction_run": state["id"], "construction_status": state["status"], "construction_model_calls": len(runtime.calls),
              "failed_checks_preserved": sum(1 for e in state["events"] if e["kind"] == "verification" and not e["detail"]["passed"]),
              "reopened_integrity": reopened.get(state["id"])["verification"]["passed"], "successor_run": successor["id"], "successor_revalidation": successor["verification"],
              "inherited_output": reuse["outputs"]["affine.json"]["output"], "strong_ordinary_output": {"result": ordinary},
              "fresh_control_status": control["status"], "fresh_control_model_calls": len(control_runtime.calls),
              "inherited_additional_model_calls": 0, "ordinary_equal_content_reuse_model_calls": 0,
              "total_inherited_construction_model_calls": len(runtime.calls), "unknown_costs": ["human authored fixtures", "compute", "development", "maintenance", "validation"],
              "successor_advantage": "NOT_ESTABLISHED: equal-content ordinary reuse ties; full inherited construction used more authored calls than the fresh control. A narrow reduction versus fresh reconstruction excludes sunk construction cost and is not compounding proof.",
              "export": reopened.export(state["id"])}
    if output:
        Path(output).write_bytes(json.dumps(result, indent=2, ensure_ascii=False).encode() + b"\n")
    return result
