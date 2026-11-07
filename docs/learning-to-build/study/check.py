#!/usr/bin/env python3
"""Recompute the entire registered report without importing the producer.

This separate implementation is an engineering cross-check, not an independent
institutional review, measurement of AI learning, or validation outside the model.
The exact frozen protocol is pinned: this is not a configurable simulator.
"""
import argparse
import csv
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys

REGISTERED_PROTOCOL_SHA256 = "38a4ef8101139270a903525bc75f6ce13890828eeac645e586472b7c6503e820"
STATES = ("fresh", "artifact", "constructor")
ROUTE_COSTS = {"fresh": [18, 10, 6, 8, 12], "artifact": [18, 0, 6, 8, 12], "constructor": [7, 0, 6, 8, 12]}
ROUTE_TIMES = {"fresh": [3, 2, 1, 1, 1], "artifact": [3, 0, 1, 1, 1], "constructor": [1, 0, 1, 1, 1]}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    # JSON comparison also distinguishes true from 1 and integer counts from floats.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def parse_json(text):
    return json.loads(text, object_pairs_hook=unique_object)


def specification_hash(spec):
    return hashlib.sha256(canonical(spec).encode()).hexdigest()


def expected_answer(spec, row):
    value = sum(weight * (scale * row[field] + offset)
                for field, scale, offset, weight
                in zip(spec["fields"], spec["scales"], spec["offsets"], spec["weights"]))
    return {"weighted_measurement": value, "accepted": value >= spec["threshold"],
            "spec_sha256": specification_hash(spec)}


def ordinary_interpreter(spec, row):
    # Separately reproduce the conventional control, using calibrated intermediates.
    calibrated = [spec["scales"][j] * row[field] + spec["offsets"][j]
                  for j, field in enumerate(spec["fields"])]
    value = sum(spec["weights"][j] * x for j, x in enumerate(calibrated))
    return {"weighted_measurement": value, "accepted": value >= spec["threshold"],
            "spec_sha256": specification_hash(spec)}


def matches(spec, row, answer):
    return canonical(answer) == canonical(expected_answer(spec, row))


def execute(path, rows):
    return subprocess.run([sys.executable, str(path)],
                          input="".join(json.dumps(row) + "\n" for row in rows),
                          text=True, capture_output=True)


def parse_answers(proc):
    require(proc.returncode == 0, "instrument failed")
    return [parse_json(line) for line in proc.stdout.splitlines()]


def event_route(state, cash, deadline, consent, maintenance, qualified=True):
    """Recompute admissibility through individual cost events, not producer totals."""
    due = maintenance if state == "constructor" else 0
    if cash < due:
        return "obligation_shortfall"
    outcomes = []
    routes = [("external", [58], [4], True),
              ("internal", ROUTE_COSTS[state], ROUTE_TIMES[state], consent and qualified)]
    for name, events, times, rights in routes:
        balances = [cash-due]
        for outflow in events:
            balances.append(balances[-1]-outflow)
        if min(balances) >= 0 and sum(times) <= deadline and rights:
            balances.append(balances[-1]+80)
            cost = sum(events)+due
            require(balances[-1]-cash == 80-cost, "cash conservation")
            outcomes.append((cost, sum(times), name))
    return min(outcomes)[2] if outcomes else "nonentry"


def analytical_control(state, cash, deadline, consent, maintenance):
    due = maintenance if state == "constructor" else 0
    if cash < due:
        return "obligation_shortfall"
    if consent and cash >= due+sum(ROUTE_COSTS[state]) and deadline >= sum(ROUTE_TIMES[state]):
        return "internal"
    if cash >= due+58 and deadline >= 4:
        return "external"
    return "nonentry"


def main(root, evidence):
    require(digest(root/"PROTOCOL.json") == REGISTERED_PROTOCOL_SHA256,
            "unsupported protocol: exact registered protocol hash required")
    protocol = parse_json((root/"PROTOCOL.json").read_text())
    report = parse_json((evidence/"RESULTS.json").read_text())
    specs = protocol["domain"]["specs"]
    technical = []
    source_path = evidence/"instruments"/"source.py"
    for spec in specs:
        path = evidence/"instruments"/(spec["id"]+".py")
        rows = [dict(zip(spec["fields"], values)) for values in itertools.product(
            protocol["domain"]["raw_values"], repeat=len(spec["fields"]))]
        answers = parse_answers(execute(path, rows))
        require(len(answers) == len(rows), "incomplete instrument answers")
        compiled_matches = sum(matches(spec, row, answer) for row, answer in zip(rows, answers))
        ordinary_matches = sum(matches(spec, row, ordinary_interpreter(spec, row)) for row in rows)
        require(compiled_matches == ordinary_matches == len(rows), "incorrect instrument or control")
        if spec["id"] == "source":
            reuse = "same task"
        else:
            donor = execute(source_path, rows)
            if donor.returncode:
                require("exact integer schema required" in donor.stderr,
                        "donor failed for an unclassified reason")
                reuse = "rejected by schema"
            else:
                donor_answers = parse_answers(donor)
                donor_matches = (len(donor_answers) == len(rows) and all(
                    matches(spec, row, answer) for row, answer in zip(rows, donor_answers)))
                reuse = "accepted" if donor_matches else "rejected by qualification"
        technical.append({"task": spec["id"], "fields": len(spec["fields"]),
                          "input_cases": len(rows), "compiled_matches": compiled_matches,
                          "ordinary_matches": ordinary_matches, "source_artifact_reuse": reuse,
                          "program_sha256": digest(path), "spec_sha256": specification_hash(spec)})

    f = protocol["financial_model"]
    grid = list(itertools.product(f["cash"], f["deadline"], f["current_rights"], f["maintenance"]))
    require(len(grid) == protocol["summary_denominator"], "registered grid denominator mismatch")
    summary = {s: {x: 0 for x in ("internal", "external", "nonentry", "obligation_shortfall")}
               for s in STATES}
    expected_rows = []
    ties = 0
    for cash, deadline, consent, maintenance in grid:
        row = {"cash": str(cash), "deadline": str(deadline),
               "internal_consent": str(consent), "maintenance": str(maintenance)}
        for state in STATES:
            choice = event_route(state, cash, deadline, consent, maintenance)
            row[state] = choice
            summary[state][choice] += 1
        row["equal_content_control"] = analytical_control("constructor", cash, deadline, consent, maintenance)
        ties += row["constructor"] == row["equal_content_control"]
        expected_rows.append(row)
    with (evidence/"frontier.csv").open(newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == list(expected_rows[0]), "frontier CSV columns mismatch")
        actual_rows = list(reader)
    require(actual_rows == expected_rows, "frontier CSV disagrees with complete event replay")
    require(ties == len(grid), "equal-content control did not reproduce all decisions")

    retention = []
    for n, maintenance in itertools.product((1, 2, 3, 10), f["maintenance"]):
        baseline_cost = sum(ROUTE_COSTS["fresh"])+n*sum(ROUTE_COSTS["artifact"])
        retained_cost = sum(ROUTE_COSTS["fresh"])+9+n*(sum(ROUTE_COSTS["constructor"])+maintenance)
        retention.append({"successors": n, "maintenance_per_successor": maintenance,
                          "net_saving_after_acquisition": baseline_cost-retained_cost})
    sample = {name: 0 for name in specs[1]["fields"]}
    bad_spec = dict(specs[1], threshold=-999)
    adverse = {
        "wrong_schema_rejected": all(t["source_artifact_reuse"] == "rejected by schema"
                                     for t in technical if t["task"] != "source"),
        "tampered_contract_rejected": not matches(specs[1], sample, ordinary_interpreter(bad_spec, sample)),
        "missing_current_qualification_rejected": event_route("constructor", 33, 4, True, 0, qualified=False) == "nonentry",
        "absent_current_rights_rejected": event_route("constructor", 33, 4, False, 0) == "nonentry",
        "maintenance_can_shrink_frontier": (event_route("artifact", 58, 4, False, 0) == "external"
                                           and event_route("constructor", 58, 4, False, 12) == "nonentry")}
    require(all(adverse.values()), "registered adverse check failed")
    total = sum(t["input_cases"] for t in technical)
    expected_report = {
        "status": "finite authored illustration reproduced",
        "protocol_sha256": REGISTERED_PROTOCOL_SHA256,
        "implementation_sha256": digest(root/"study.py"),
        "technical": technical,
        "total_input_cases": total,
        "fresh_successor_tasks": sum(t["task"] != "source" for t in technical),
        "route_grid_cells": len(grid),
        "route_decisions": len(grid)*len(STATES),
        "equal_content_decision_ties": ties,
        "route_summary": summary,
        "retention": retention,
        "adversarial_checks": adverse,
        "break_even": "n*(11-m) > 9, conditional on same acceptance, fixture availability, rights, deadlines and prefix liquidity",
        "limitations": protocol["claim_limits"],
        "actual_customer_receipts": 0,
        "actual_external_resource_bills": "not measured"}
    # Exact whole-report equality rejects omitted/extra rows, flags, hashes and
    # claims as well as false counts; no reported denominator controls this check.
    require(canonical(report) == canonical(expected_report),
            "reported RESULTS.json does not match independently recomputed evidence")
    print(json.dumps({"accepted": True, "checked_program_inputs": total,
                      "checked_complete_route_decisions": len(grid)*len(STATES),
                      "equal_content_ties": ties,
                      "scope": "separate-source engineering check of the declared finite model"}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=Path(__file__).resolve().parent/"evidence")
    args = parser.parse_args()
    main(Path(__file__).resolve().parent, args.evidence.resolve())
