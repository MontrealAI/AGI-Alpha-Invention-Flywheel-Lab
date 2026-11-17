"""Preregister a matched private backlog, select deliveries blind, then score only those deliveries."""
import argparse
import json
import re
from pathlib import Path

import pilot
from pairing_lab import ROOT, analyze, digest

ARMS = ("historical_single", "historical_pair", "current_agent", "direct_tool", "human_conventional")
COSTS = ("production", "selection", "verification", "infrastructure", "human_labor", "delivery_and_obligations")
AUTHORITIES = ("rights_and_distribution", "gate_procedure", "gate_qualification",
               "acceptance_procedure", "acceptance_qualification", "accounting_and_deadline")
LIMIT = 2_000_000


def read_json(raw):
    def unique(pairs):
        result = dict(pairs)
        if len(pairs) != len(result):
            raise ValueError("repeated JSON keys make a pilot record ambiguous")
        return result
    return json.loads(raw, object_pairs_hook=unique)


def fields(obj, names):
    if not isinstance(obj, dict) or set(obj) != set(names):
        raise ValueError(f"expected exactly these fields: {', '.join(names)}")
    return obj


def count(value):
    if type(value) is not int or value < 0:
        raise ValueError("expected a nonnegative integer")
    return value


def checked(raw, expected):
    if not isinstance(expected, str) or not pilot.HEX.fullmatch(expected) or digest(raw) != expected:
        raise ValueError("content differs from its separately retained SHA-256")
    return raw


def evidence(directory, ref):
    if not isinstance(ref, str) or not pilot.HEX.fullmatch(ref):
        raise ValueError("evidence must use a lowercase SHA-256 identifier")
    raw = checked((directory / ref).read_bytes(), ref)
    if not raw:
        raise ValueError("empty evidence cannot qualify a pilot observation")
    return raw


def bound_receipt(directory, ref, expected):
    receipt = read_json(evidence(directory, ref))
    if not isinstance(receipt, dict) or any(k not in receipt or pilot.canonical(receipt[k]) != pilot.canonical(v)
                                           for k, v in expected.items()):
        raise ValueError("evidence receipt does not bind the required observations")
    evidence(directory, receipt["source_sha256"])


def register(spec, directory, data):
    fields(spec, ("tasks", "authority", "configurations", "currency"))
    tasks = spec["tasks"]
    if not isinstance(tasks, dict):
        raise ValueError("tasks must map each fresh issue ID to its frozen outcome contract")
    if len(set(tasks.values())) != len(tasks):
        raise ValueError("each fresh issue needs its own independently identifiable outcome contract")
    rights = fields(spec["authority"], AUTHORITIES)
    if rights["gate_procedure"] == rights["acceptance_procedure"]:
        raise ValueError("require a separate outcome evaluator from the selection gate")
    if not isinstance(spec["currency"], str) or not re.fullmatch(r"[A-Z]{3}", spec["currency"]):
        raise ValueError("expected the currency code for all reported micro-units")
    policy = pilot.register(data, list(tasks), rights["gate_procedure"],
                            budget=LIMIT, width=2, min_percent=45)
    single = analyze(data, budget=LIMIT, width=1, witnesses=False)["selected"]
    pair = sorted(policy["required_stacks"], key=lambda stack: (stack not in single, stack))
    routes = {"historical_single": single, "historical_pair": pair,
              **{arm: [arm] for arm in ARMS[2:]}}
    required = sorted({slot for slots in routes.values() for slot in slots})
    configs = fields(spec["configurations"], required)
    for ref in (*tasks.values(), *rights.values(), *configs.values()):
        evidence(directory, ref)
    for stage in ("gate", "acceptance"):
        procedure = rights[stage + "_procedure"]
        calibration = read_json(evidence(directory, rights[stage + "_qualification"]))
        fields(calibration, ("procedure", "controls"))
        if calibration["procedure"] != procedure:
            raise ValueError(f"{stage} control observations use another procedure")
        observed = {}
        for control in calibration["controls"]:
            fields(control, ("artifact", "expected", "observed", "source_sha256"))
            evidence(directory, control["artifact"])
            evidence(directory, control["source_sha256"])
            if (type(control["expected"]) is not bool or control["observed"] is not control["expected"]
                    or control["artifact"] in observed):
                raise ValueError(f"{stage} failed or repeated a registered control")
            observed[control["artifact"]] = control["observed"]
        if set(observed.values()) != {True, False}:
            raise ValueError(f"{stage} requires observed positive and negative controls")
    return {"schema": "pairing-operational-pilot/1", "spec": spec, "routes": routes,
            "historical_plan": policy, "program_sha256": digest(Path(__file__).read_bytes())}


def read_plan(raw, commitment, directory, data):
    plan = read_json(checked(raw, commitment))
    if pilot.canonical(register(plan["spec"], directory, data)) != raw:
        raise ValueError("plan does not reproduce from the frozen specification")
    return plan


def cell(task, arm):
    return task + ":" + arm


def expected_cells(plan):
    return {cell(task, arm): arm for task in plan["spec"]["tasks"] for arm in ARMS}


def select(plan, logs, directory):
    """This operation has no access to final outcome labels. All scheduled attempts incur costs."""
    cells = expected_cells(plan)
    fields(logs, cells)
    chosen, ids = {}, set()
    for key, arm in cells.items():
        task, _ = key.split(":")
        slots = plan["routes"][arm]
        attempts = fields(logs[key], slots)
        candidates = []
        tokens = 0
        for slot in slots:
            rows = attempts[slot]
            if not isinstance(rows, list) or not rows:
                raise ValueError(f"missing attempted configuration for {key} / {slot}")
            for row in rows:
                fields(row, ("run_id", "tokens", "artifact", "gate_pass", "receipt"))
                run_id = row["run_id"]
                if not isinstance(run_id, str) or not pilot.LABEL.fullmatch(run_id) or run_id in ids:
                    raise ValueError("each independently run attempt needs its own run ID")
                ids.add(run_id)
                tokens += count(row["tokens"])
                bound_receipt(directory, row["receipt"], {
                    "type": "selection", "task_contract": plan["spec"]["tasks"][task], "arm": arm,
                    "configuration": plan["spec"]["configurations"][slot],
                    "grader": plan["spec"]["authority"]["gate_procedure"],
                    **{k: v for k, v in row.items() if k != "receipt"}})
                if type(row["gate_pass"]) is not bool:
                    raise ValueError("selection gate must report true or false")
                if row["artifact"] is not None:
                    evidence(directory, row["artifact"])
                if row["gate_pass"]:
                    if row["artifact"] is None:
                        raise ValueError("an accepted gate requires an identifiable artifact")
                    candidates.append(row["artifact"])
        chosen[key] = {"selected": next(iter(candidates), None), "attempts": sum(map(len, attempts.values())),
                       "tokens": tokens}
    return {"schema": "pairing-blind-deliveries/1", "plan_sha256": digest(pilot.canonical(plan)),
            "attempt_log_sha256": digest(pilot.canonical(logs)), "cells": chosen}


def score(plan, deliveries, finals, directory):
    cells = expected_cells(plan)
    fields(finals, cells)
    reports = {arm: {"tasks": 0, "accepted": 0, "attempts": 0, "tokens": 0, "human_ms": 0,
                     "sum_delivery_ms": 0, "cost_micros": {c: 0 for c in COSTS}, "unknown_costs": []}
               for arm in ARMS}
    delivery_sha = digest(pilot.canonical(deliveries))
    for key, arm in cells.items():
        obs = fields(finals[key], ("delivered", "accepted", "decision_receipt", "meter_receipt",
                                   "human_ms", "delivery_ms", "cost_micros"))
        selected = deliveries["cells"][key]
        if obs["delivered"] != selected["selected"] or type(obs["accepted"]) is not bool:
            raise ValueError("outcome must grade exactly the artifact chosen before final acceptance")
        if obs["accepted"] and obs["delivered"] is None:
            raise ValueError("cannot accept a missing delivery")
        task, _ = key.split(":")
        identity = {"task_contract": plan["spec"]["tasks"][task], "arm": arm,
                    "delivery_sha256": delivery_sha}
        bound_receipt(directory, obs["decision_receipt"], {**identity, "type": "acceptance",
                      "grader": plan["spec"]["authority"]["acceptance_procedure"],
                      "delivered": obs["delivered"], "accepted": obs["accepted"]})
        bound_receipt(directory, obs["meter_receipt"], {**identity, "type": "costs",
                      "currency": plan["spec"]["currency"], "human_ms": obs["human_ms"],
                      "delivery_ms": obs["delivery_ms"], "cost_micros": obs["cost_micros"]})
        r = reports[arm]
        r["tasks"] += 1
        r["accepted"] += int(obs["accepted"])
        r["attempts"] += selected["attempts"]
        r["tokens"] += selected["tokens"]
        r["human_ms"] += count(obs["human_ms"])
        r["sum_delivery_ms"] += count(obs["delivery_ms"])
        costs = fields(obs["cost_micros"], COSTS)
        for category, amount in costs.items():
            if amount is None:
                r["unknown_costs"].append([key, category])
            else:
                r["cost_micros"][category] += count(amount)
    for r in reports.values():
        r["total_cost_micros"] = None if r["unknown_costs"] else sum(r["cost_micros"].values())
    pair = reports["historical_pair"]
    comparisons = {}
    for arm in ARMS:
        if arm == "historical_pair":
            continue
        other = reports[arm]
        delta_cost = None
        if pair["total_cost_micros"] is not None and other["total_cost_micros"] is not None:
            delta_cost = pair["total_cost_micros"] - other["total_cost_micros"]
        comparisons[arm] = {"additional_accepted": pair["accepted"] - other["accepted"],
                            "additional_cost_micros": delta_cost,
                            "additional_sum_delivery_ms": pair["sum_delivery_ms"] - other["sum_delivery_ms"]}
    return {"schema": "pairing-operational-outcome/1", "plan_sha256": digest(pilot.canonical(plan)),
            "delivery_sha256": digest(pilot.canonical(deliveries)), "finals_sha256": digest(pilot.canonical(finals)),
            "currency": plan["spec"]["currency"], "arms": reports, "pair_minus_alternative": comparisons,
            "scope": "Operator-supplied grades, meters and rights records. Verify their contents independently."}


def write_new(path, result):
    raw = pilot.canonical(result)
    with path.open("xb") as f:
        f.write(raw)
    print(digest(raw))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("register", "select", "score"):
        p = sub.add_parser(action)
        p.add_argument("--evidence", type=Path, required=True, help="private directory of records named by SHA-256")
        p.add_argument("--data", type=Path, default=ROOT / "runs.csv")
        p.add_argument("--out", type=Path, required=True)
        if action == "register":
            p.add_argument("--spec", type=Path, required=True)
        else:
            p.add_argument("--plan", type=Path, required=True)
            p.add_argument("--plan-sha", required=True)
            p.add_argument("--attempts", type=Path, required=True)
        if action == "score":
            p.add_argument("--deliveries", type=Path, required=True)
            p.add_argument("--delivery-sha", required=True)
            p.add_argument("--finals", type=Path, required=True)
    a = parser.parse_args()
    try:
        data = a.data.read_bytes()
        if a.action == "register":
            result = register(read_json(a.spec.read_bytes()), a.evidence, data)
        else:
            plan = read_plan(a.plan.read_bytes(), a.plan_sha, a.evidence, data)
            result = select(plan, read_json(a.attempts.read_bytes()), a.evidence)
            if a.action == "score":
                sealed = checked(a.deliveries.read_bytes(), a.delivery_sha)
                if sealed != pilot.canonical(result):
                    raise ValueError("current attempt logs do not reproduce the earlier blind deliveries")
                result = score(plan, result, read_json(a.finals.read_bytes()), a.evidence)
        write_new(a.out, result)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"Operational pilot error: {exc}\n")


if __name__ == "__main__":
    main()
