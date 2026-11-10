#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reviewer-owned fresh-instance successor qualification; no model/network use.

Freeze this generator/protocol, then freeze candidate source, then generate
fresh nonce-bound instances. Each receipt preserves all arms and unknown costs.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import secrets
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PATHS = {
    "candidate": ROOT / "bridge/genesis_next.py",
    "evaluator": Path(__file__).resolve(),
    "protocol": ROOT / "evidence/OMEGA-FRESH-SUCCESSOR-PROTOCOL.md",
    "original_protocol": ROOT / "evidence/OMEGA-PROTOCOL.md",
    "interpreter": ROOT / "bridge/instruments.py",
    "workflow_helpers": ROOT / "bridge/workflows.py",
    "workflow_strategies": ROOT / "bridge/workflow_strategies.py",
    "workflow_schemas": ROOT / "bridge/workflow_schemas.py",
    "output_schema": ROOT / "bridge/output_schema.py",
    "execution_services": ROOT / "bridge/services.py",
    "provider_contracts": ROOT / "bridge/adapters.py",
}
BUDGET = 20


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def source_identities():
    return {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in PATHS.items()}


def exclusive_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def freeze(path):
    identities = source_identities()
    result = {"schema": "omega-successor-source-freeze/v1", "source_sha256": identities,
              "scope": "Source snapshot before random instances; independently bind this receipt to the reviewed Git revision."}
    exclusive_json(path, result)
    return result


def instrument():
    return {"name": "Bounded addition instrument", "inputs": ["x", "offset"],
            "outputs": {"result": {"op": "add", "args": [{"field": "x"}, {"field": "offset"}]}},
            "conditions": "Exact supplied finite integer arithmetic.", "limitations": "No empirical semantics."}


def generate(seed, interpreter_hash):
    random_source = random.Random(int(seed, 16))
    def make_record(label, wrong=False):
        x = random_source.randint(-10000, 10000)
        offset = random_source.randint(-1000, 1000)
        return {"id": label, "spec": {"instrument": instrument(), "input": {"x": x, "offset": offset},
                "expected": {"result": x + offset + (1 if wrong else 0)}},
                "dependencies": {"bridge/instruments.py": interpreter_hash, "source": digest([seed, label])}}
    initial = [make_record(f"initial-{i:02}") for i in range(24)]
    selected = list(range(24))
    random_source.shuffle(selected)
    successor = [copy.deepcopy(initial[i]) for i in selected[:12]]
    for number, index in enumerate(selected[12:20]):
        successor.append(make_record(f"initial-{index:02}-source-changed", wrong=number < 4))
    successor += [make_record(f"new-{i:02}", wrong=i < 4) for i in range(12)]
    random_source.shuffle(successor)
    return initial, successor


def oracle(record):
    supplied = record["spec"]
    actual = supplied["input"]["x"] + supplied["input"]["offset"]
    return {"passed": supplied["expected"] == {"result": actual}, "output": {"result": actual}}


class AllowanceExhausted(Exception):
    pass


class OrdinaryMemoization:
    """Strong equal-information conventional control, separate implementation."""
    def __init__(self, checker_id):
        self.checker_id = checker_id
        self.cache = {}
    def check(self, spec, dependencies, verifier):
        key = digest({"checker": self.checker_id, "payload": spec, "dependencies": dependencies})
        if key in self.cache:
            return {"accepted": self.cache[key]["passed"], "result": copy.deepcopy(self.cache[key]), "reused": True}
        value = verifier()
        if value["passed"]:
            self.cache[key] = copy.deepcopy(value)
        return {"accepted": value["passed"], "result": value, "reused": False}


class Uncached:
    def check(self, spec, dependencies, verifier):
        value = verifier()
        return {"accepted": value["passed"], "result": value, "reused": False}


def run_arm(name, index, initial, successor, withdraw_inheritance=False):
    from bridge.instruments import evaluate
    start_wall, start_cpu = time.perf_counter(), time.process_time()
    construction_calls = [0]
    successor_calls = [0]
    def check_record(record, counter, bounded=False):
        def observe():
            if bounded and counter[0] >= BUDGET:
                raise AllowanceExhausted()
            counter[0] += 1
            spec = record["spec"]
            actual = evaluate(spec["instrument"], spec["input"])["output"]
            return {"passed": actual == spec["expected"], "output": actual}
        return index.check(record["spec"], record["dependencies"], observe)
    for record in initial:
        result = check_record(record, construction_calls)
        if not result["accepted"] or result["result"] != oracle(record):
            raise AssertionError("Initial observation failed independent arithmetic acceptance.")
    if withdraw_inheritance:
        # Removing the retained asset does not erase its acquisition cost.
        index.invalidate(sorted({key for record in initial for key in record["dependencies"]}))
    decisions = []
    for record in successor:
        try:
            outcome = check_record(record, successor_calls, True)
            correct = (outcome["accepted"] is oracle(record)["passed"] and outcome["result"] == oracle(record))
            decisions.append({"id": record["id"], "status": "ADJUDICATED", "accepted": outcome["accepted"],
                              "reused": outcome["reused"], "correct": correct})
        except AllowanceExhausted:
            decisions.append({"id": record["id"], "status": "UNKNOWN_BUDGET_EXHAUSTED", "correct": None})
    adjudicated = [d for d in decisions if d["status"] == "ADJUDICATED"]
    return {"arm": name, "initial_verification_calls": construction_calls[0],
            "successor_verification_calls": successor_calls[0], "total_verification_calls": construction_calls[0] + successor_calls[0],
            "adjudicated": len(adjudicated), "correct_decisions": sum(d["correct"] is True for d in adjudicated),
            "errors": sum(d["correct"] is not True for d in adjudicated),
            "reused": sum(d.get("reused", False) for d in decisions), "decisions": decisions,
            "wall_seconds": time.perf_counter() - start_wall, "cpu_seconds": time.process_time() - start_cpu}


def qualify(freeze_path, output_path):
    bound = json.loads(Path(freeze_path).read_text(encoding="utf-8"))
    current = source_identities()
    if bound.get("schema") != "omega-successor-source-freeze/v1" or bound.get("source_sha256") != current:
        raise ValueError("Candidate, protocol, interpreter or evaluator changed after the source freeze.")
    # This sample occurs only after the frozen byte identities were verified.
    seed = secrets.token_hex(32)
    initial, successor = generate(seed, current["interpreter"])
    from bridge.genesis_next import EvidenceIndex
    checker_id = digest({"reviewer": current["evaluator"], "interpreter": current["interpreter"]})
    arms = []
    for name, index, withdrawn in (
        ("uncached_baseline", Uncached(), False),
        ("inherited_candidate", EvidenceIndex(checker_id), False),
        ("strong_ordinary_memoization", OrdinaryMemoization(checker_id), False),
        ("inheritance_withdrawn", EvidenceIndex(checker_id), True),
    ):
        try:
            arms.append(run_arm(name, index, initial, successor, withdraw_inheritance=withdrawn))
        except Exception as error:
            # Keep the other registered arms and the failed attempt visible.
            # An exception is never a reason to silently replace the sampled seed.
            arms.append({"arm": name, "status": "ERROR", "error_type": type(error).__name__,
                         "error": str(error)[:500], "adjudicated": 0, "errors": 1,
                         "successor_verification_calls": None, "total_verification_calls": None,
                         "reused": 0, "unknown_costs": ["work completed before exception"]})
    candidate, ordinary = arms[1], arms[2]
    failures = [f"{arm['arm']}: incorrect decisions" for arm in arms if arm["errors"]]
    failures += [f"{arm['arm']}: unknown or exceeded successor allowance" for arm in arms
                 if arm["successor_verification_calls"] is None or arm["successor_verification_calls"] > BUDGET]
    for arm in (candidate, ordinary):
        if arm["adjudicated"] != 32 or arm["successor_verification_calls"] != 20 or arm["reused"] != 12:
            failures.append(f"{arm['arm']}: failed complete successor qualification")
    if source_identities() != current:
        failures.append("source changed during qualification")
    result = {"schema": "omega-fresh-successor-qualification/v1", "status": "PASS" if not failures else "FAIL",
              "failures": failures, "source_sha256": current, "freeze_sha256": hashlib.sha256(Path(freeze_path).read_bytes()).hexdigest(),
              "seed_generated_after_source_freeze": seed, "initial_instances": initial, "successor_instances": successor,
              "instances_sha256": digest({"initial": initial, "successor": successor}),
              "successor_evaluator_allowance": BUDGET, "arms": arms,
              "direct_successor_without_construction_calls": len(successor),
              "complete_costs_known": False,
              "unknown_costs": ["engineering", "search", "independent qualification", "integration", "maintenance", "host/electricity", "economic opportunity cost"],
              "strong_control_advantage": "NOT_ESTABLISHED" if candidate["adjudicated"] <= ordinary["adjudicated"] else "REQUIRES_COMPLETE_COSTS",
              "verdict": "Fresh post-freeze instances exercised a distinct internal selection task. Conventional exact-content reuse is the strong control; a tie does not establish general compounding superiority.",
              "scope": "Finite generated instances, no new external task family, no live model inference, no actual commerce, no general self-improving intelligence claim."}
    exclusive_json(output_path, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    freezer = sub.add_parser("freeze")
    freezer.add_argument("--output", required=True, type=Path)
    runner = sub.add_parser("run")
    runner.add_argument("--freeze", required=True, type=Path)
    runner.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = freeze(args.output) if args.action == "freeze" else qualify(args.freeze, args.output)
    print(json.dumps({"status": result.get("status", "FROZEN"), "output": str(args.output), "source_sha256": result["source_sha256"]}))
    return 0 if result.get("status", "PASS") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
