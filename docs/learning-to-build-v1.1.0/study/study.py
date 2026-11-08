#!/usr/bin/env python3
"""Finite, author-specified construction study. No AI, physical sensor or commerce.

Builds standalone measurement programs, exhaustively checks them on a declared
finite domain, and evaluates complete-means routes in a separate synthetic model.
The cost units below are illustrative assumptions, not measured economic costs.
This is reproduction of one registered model, not a configurable simulator:
the exact frozen protocol bytes are required before any output is written.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import itertools
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REGISTERED_PROTOCOL_SHA256 = "38a4ef8101139270a903525bc75f6ce13890828eeac645e586472b7c6503e820"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_spec(spec):
    required = {"id", "fields", "scales", "offsets", "weights", "threshold"}
    if set(spec) != required:
        raise ValueError("exact specification fields required")
    n = len(spec["fields"])
    if n < 1 or n > 8 or len(set(spec["fields"])) != n:
        raise ValueError("invalid field count or duplicate field")
    if any(not isinstance(x, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", x) for x in spec["fields"]):
        raise ValueError("invalid field name")
    if not all(len(spec[k]) == n for k in ("scales", "offsets", "weights")):
        raise ValueError("coefficient length mismatch")
    for x in [spec["threshold"]] + spec["scales"] + spec["offsets"] + spec["weights"]:
        if type(x) is not int:
            raise ValueError("integer specification required")


def spec_hash(spec):
    return hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def compile_instrument(spec):
    """Construct fresh executable source by algebraic combination of affine maps.

    This conventional compiler is author supplied. Its output is a new instrument;
    neither the compiler nor its generation process is claimed to have been learned.
    """
    validate_spec(spec)
    terms = [f"({a*w} * row[{field!r}])" for field, a, w in zip(spec["fields"], spec["scales"], spec["weights"])]
    intercept = sum(b*w for b, w in zip(spec["offsets"], spec["weights"]))
    expression = " + ".join(terms + [repr(intercept)])
    return f'''#!/usr/bin/env python3
# Generated from an authored finite measurement specification.
import json
import sys
SPEC_HASH = {spec_hash(spec)!r}
FIELDS = {spec['fields']!r}

def measure(row):
    if set(row) != set(FIELDS) or any(type(row[k]) is not int for k in FIELDS):
        raise ValueError("exact integer schema required")
    value = {expression}
    return {{"weighted_measurement": value, "accepted": value >= {spec['threshold']}, "spec_sha256": SPEC_HASH}}

if __name__ == "__main__":
    for line in sys.stdin:
        print(json.dumps(measure(json.loads(line)), sort_keys=True))
'''


def ordinary_interpret(spec, row):
    """Strong equal-content control: direct interpretation, no compilation needed."""
    if set(row) != set(spec["fields"]) or any(type(row[k]) is not int for k in spec["fields"]):
        raise ValueError("exact integer schema required")
    calibrated = [a * row[f] + b for f, a, b in zip(spec["fields"], spec["scales"], spec["offsets"])]
    value = sum(w * x for w, x in zip(spec["weights"], calibrated))
    return {"weighted_measurement": value, "accepted": value >= spec["threshold"], "spec_sha256": spec_hash(spec)}


def run_program(path, rows):
    payload = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    proc = subprocess.run([sys.executable, str(path)], input=payload, capture_output=True, text=True)
    if proc.returncode:
        raise ValueError("generated program rejected input or failed")
    answers = [json.loads(line) for line in proc.stdout.splitlines()]
    if len(answers) != len(rows):
        raise ValueError("output count mismatch")
    return answers


def independent_expected(spec, row):
    """Separate symbolic polynomial expansion, kept explicit for review."""
    total = 0
    for j in range(len(spec["fields"])):
        total += row[spec["fields"][j]] * spec["scales"][j] * spec["weights"][j]
        total += spec["offsets"][j] * spec["weights"][j]
    return total, total >= spec["threshold"]


def qualify(spec, rows, answers):
    if len(rows) != len(answers):
        return False
    for row, answer in zip(rows, answers):
        total, accepted = independent_expected(spec, row)
        if answer != {"weighted_measurement": total, "accepted": accepted, "spec_sha256": spec_hash(spec)}:
            return False
    return True


def best_route(state, cash, deadline, internal_consent, maintenance, qualified=True):
    """Exact enumeration of the complete supplied routes, with prefix cash.

    No revenue is available before delivery. Maintenance is a binding retained-state
    obligation, paid even when choosing the external route or nonentry. All routes
    require a current instrument certificate in addition to input-schema correctness.
    """
    obligation = maintenance if state == "constructor" else 0
    if cash < obligation:
        return {"choice": "obligation_shortfall", "cost": obligation, "profit": -obligation, "min_cash": cash-obligation}
    routes = [("external", 58, 4, True)]
    inner = {"fresh": (54, 8), "artifact": (44, 6), "constructor": (33, 4)}[state]
    routes.append(("internal", inner[0], inner[1], internal_consent and qualified))
    feasible = []
    for name, cost, duration, allowed in routes:
        all_cost = cost + obligation
        if allowed and duration <= deadline and cash >= all_cost:
            # Prefix 1: mandatory maintenance; 2: all delivery costs; 3: receipt.
            balances = [cash, cash-obligation, cash-all_cost, cash-all_cost+80]
            feasible.append((all_cost, duration, name, balances))
    if not feasible:
        return {"choice": "nonentry", "cost": obligation, "profit": -obligation, "min_cash": cash-obligation}
    cost, duration, name, balances = min(feasible)
    return {"choice": name, "cost": cost, "duration": duration, "profit": 80-cost, "min_cash": min(balances), "cash_path": balances}


def closed_form_route(state, cash, deadline, consent, maintenance, qualified=True):
    """Independent analytical oracle. Internal always costs less in this catalogue."""
    m = maintenance if state == "constructor" else 0
    if cash < m:
        return "obligation_shortfall"
    required_cash, required_time = {"fresh": (54, 8), "artifact": (44, 6), "constructor": (33, 4)}[state]
    if consent and qualified and cash >= m+required_cash and deadline >= required_time:
        return "internal"
    if cash >= m+58 and deadline >= 4:
        return "external"
    return "nonentry"


def run(output):
    require(sha256(ROOT/"PROTOCOL.json") == REGISTERED_PROTOCOL_SHA256,
            "unsupported protocol: exact registered protocol hash required")
    protocol = json.loads((ROOT/"PROTOCOL.json").read_text())
    output.mkdir(parents=True, exist_ok=True)
    program_dir = output / "instruments"
    program_dir.mkdir(exist_ok=True)
    specs = protocol["domain"]["specs"]
    checks = []
    source_program = None
    for spec in specs:
        path = program_dir / (spec["id"] + ".py")
        path.write_text(compile_instrument(spec))
        rows = [dict(zip(spec["fields"], values)) for values in itertools.product(protocol["domain"]["raw_values"], repeat=len(spec["fields"]))]
        answers = run_program(path, rows)
        ordinary = [ordinary_interpret(spec, row) for row in rows]
        if not qualify(spec, rows, answers) or not qualify(spec, rows, ordinary):
            raise AssertionError("independent acceptance failed")
        if spec["id"] == "source":
            source_program = path
            source_reuse = "same task"
        else:
            try:
                source_answers = run_program(source_program, rows)
                source_reuse = "accepted" if qualify(spec, rows, source_answers) else "rejected by qualification"
            except ValueError:
                source_reuse = "rejected by schema"
        checks.append({"task": spec["id"], "fields": len(spec["fields"]), "input_cases": len(rows), "compiled_matches": len(rows), "ordinary_matches": len(rows), "source_artifact_reuse": source_reuse, "program_sha256": sha256(path), "spec_sha256": spec_hash(spec)})
    f = protocol["financial_model"]
    cells = []
    summary = {state: {"internal": 0, "external": 0, "nonentry": 0, "obligation_shortfall": 0} for state in ("fresh", "artifact", "constructor")}
    for cash, deadline, consent, maintenance in itertools.product(f["cash"], f["deadline"], f["current_rights"], f["maintenance"]):
        cell = {"cash": cash, "deadline": deadline, "internal_consent": consent, "maintenance": maintenance}
        for state in summary:
            result = best_route(state, cash, deadline, consent, maintenance)
            require(result["choice"] == closed_form_route(state, cash, deadline, consent, maintenance), "route oracle mismatch")
            if result["choice"] in ("internal", "external"):
                require(result["min_cash"] >= 0, "negative accepted-route cash")
                require(result["profit"] == 80-result["cost"], "profit identity mismatch")
            cell[state] = result["choice"]
            summary[state][result["choice"]] += 1
        # The equal-content exact planner is the same feasible-set oracle, not a
        # baseline deprived of the constructor recipe or acquisition permission.
        cell["equal_content_control"] = closed_form_route("constructor", cash, deadline, consent, maintenance)
        require(cell["constructor"] == cell["equal_content_control"], "equal-content decision mismatch")
        cells.append(cell)
    require(len(cells) == protocol["summary_denominator"], "grid denominator mismatch")
    no_qual = best_route("constructor", 33, 4, True, 0, qualified=False)
    require(no_qual["choice"] == "nonentry", "missing qualification accepted")
    # A tampered low threshold must be rejected by an independent output checker.
    sample = {name: 0 for name in specs[1]["fields"]}
    bad_spec = dict(specs[1], threshold=-999)
    bad_answer = ordinary_interpret(bad_spec, sample)
    require(not qualify(specs[1], [sample], [bad_answer]), "tampered contract accepted")
    # Complete technical artifacts without current voluntary access cannot deliver.
    require(best_route("constructor", 33, 4, False, 0)["choice"] == "nonentry", "missing rights accepted")
    # Retained obligations can reduce reachability; this violates state dominance.
    require(best_route("artifact", 58, 4, False, 0)["choice"] == "external", "external counterexample failed")
    require(best_route("constructor", 58, 4, False, 12)["choice"] == "nonentry", "maintenance counterexample failed")
    retention = [{"successors": n, "maintenance_per_successor": m, "net_saving_after_acquisition": n*(11-m)-9} for n in (1,2,3,10) for m in f["maintenance"]]
    results = {
      "status": "finite authored illustration reproduced",
      "protocol_sha256": sha256(ROOT/"PROTOCOL.json"),
      "implementation_sha256": sha256(Path(__file__)),
      "technical": checks,
      "total_input_cases": sum(x["input_cases"] for x in checks),
      "fresh_successor_tasks": 3,
      "route_grid_cells": len(cells),
      "route_decisions": len(cells)*3,
      "equal_content_decision_ties": len(cells),
      "route_summary": summary,
      "retention": retention,
      "adversarial_checks": {"wrong_schema_rejected": True,"tampered_contract_rejected":True,"missing_current_qualification_rejected":True,"absent_current_rights_rejected":True,"maintenance_can_shrink_frontier":True},
      "break_even": "n*(11-m) > 9, conditional on same acceptance, fixture availability, rights, deadlines and prefix liquidity",
      "limitations": protocol["claim_limits"],
      "actual_customer_receipts": 0,
      "actual_external_resource_bills": "not measured"
    }
    (output/"RESULTS.json").write_text(json.dumps(results, indent=2, sort_keys=True)+"\n")
    with (output/"frontier.csv").open("w", newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(cells[0])); writer.writeheader();writer.writerows(cells)
    print(json.dumps({k:results[k] for k in ("protocol_sha256","total_input_cases","fresh_successor_tasks","route_grid_cells","route_decisions","equal_content_decision_ties","route_summary")},indent=2))
    return results


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT/"evidence")
    args=parser.parse_args()
    run(args.output.resolve())
