#!/usr/bin/env python3
"""Small independently authored, standard-library minimum-cover proof checker.

It never imports the producer's solver and never trusts claimed residual states.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from decimal import Decimal
from pathlib import Path


class Rejected(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise Rejected(reason)


def integer(x):
    return type(x) is int


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def verify(problem, certificate):
    t0 = time.perf_counter_ns()
    require(isinstance(problem, dict) and set(problem) == {"schema", "option_ids", "requirements"}, "PROBLEM_SCHEMA")
    require(problem["schema"] == "frontier-cover-instance/v1", "PROBLEM_VERSION")
    labels, rows = problem["option_ids"], problem["requirements"]
    require(isinstance(labels, list) and all(type(x) is str and x for x in labels), "OPTION_IDENTITIES")
    require(len(set(labels)) == len(labels), "DUPLICATE_OPTION_IDENTITY")
    require(isinstance(rows, list), "REQUIREMENTS_TYPE")
    n = len(labels)
    for row in rows:
        require(isinstance(row, list), "ROW_TYPE")
        require(all(integer(j) and 0 <= j < n for j in row), "ROW_OPTION_INDEX")
        require(len(set(row)) == len(row), "DUPLICATE_ROW_OPTION")
    require(isinstance(certificate, dict), "CERTIFICATE_TYPE")
    require(set(certificate) == {"schema", "problem_sha256", "optimum", "selected", "root", "nodes"}, "CERTIFICATE_SCHEMA")
    require(certificate["schema"] == "frontier-min-cover-proof/v1", "CERTIFICATE_VERSION")
    require(certificate["problem_sha256"] == canonical_hash(problem), "PROBLEM_BINDING")
    selected, k = certificate["selected"], certificate["optimum"]
    require(integer(k) and k >= 0, "OPTIMUM_TYPE")
    require(isinstance(selected, list) and len(selected) == k, "SELECTED_CARDINALITY")
    require(all(integer(j) and 0 <= j < n for j in selected), "SELECTED_INDEX")
    require(len(set(selected)) == k, "SELECTED_DUPLICATE")
    chosen = set(selected)
    require(all(any(j in chosen for j in row) for row in rows), "INFEASIBLE_SELECTED")
    nodes, root = certificate["nodes"], certificate["root"]
    require(isinstance(nodes, list), "NODES_TYPE")
    if not rows:
        require(k == 0 and root is None and nodes == [], "EMPTY_UNIVERSE_NONMINIMAL")
        return {"accepted": True, "optimum": 0, "proof_nodes": 0, "checked_states": 0,
                "wall_seconds": (time.perf_counter_ns() - t0) / 1e9}
    require(k > 0 and integer(root) and 0 <= root < len(nodes), "ROOT_INDEX")
    row_sets = [frozenset(row) for row in rows]
    option_hits = [frozenset(r for r, row in enumerate(rows) if j in row) for j in range(n)]
    checked = set()

    def check(node_index, uncovered, budget):
        require(integer(node_index) and 0 <= node_index < len(nodes), "NODE_INDEX")
        require(uncovered and budget >= 0, "PROOF_AT_FEASIBLE_STATE")
        state = (node_index, uncovered, budget)
        if state in checked:
            return
        node = nodes[node_index]
        require(isinstance(node, dict) and type(node.get("type")) is str, "NODE_TYPE")
        kind = node["type"]
        if kind == "packing":
            require(set(node) == {"type", "rows"}, "PACKING_SCHEMA")
            pack = node["rows"]
            require(isinstance(pack, list) and all(integer(r) and r in uncovered for r in pack), "PACKING_ROWS")
            require(len(set(pack)) == len(pack) and len(pack) > budget, "PACKING_COUNT")
            used = set()
            for r in pack:
                require(not (used & row_sets[r]), "PACKING_OVERLAP")
                used.update(row_sets[r])
        elif kind == "capacity":
            require(set(node) == {"type"}, "CAPACITY_SCHEMA")
            largest = max((len(uncovered & hits) for hits in option_hits), default=0)
            require(largest == 0 or (len(uncovered) + largest - 1) // largest > budget, "CAPACITY_NOT_PROVEN")
        elif kind == "empty":
            require(set(node) == {"type", "row"}, "EMPTY_SCHEMA")
            r = node["row"]
            require(integer(r) and r in uncovered and not row_sets[r], "EMPTY_ROW_NOT_EMPTY")
        elif kind == "branch":
            require(set(node) == {"type", "row", "children", "dominated"}, "BRANCH_SCHEMA")
            r, children, omitted = node["row"], node["children"], node["dominated"]
            require(integer(r) and r in uncovered and row_sets[r], "BRANCH_ROW")
            require(budget > 0, "BRANCH_NEGATIVE_BUDGET")
            require(isinstance(children, list) and children and isinstance(omitted, list), "BRANCH_LISTS")
            explicit = {}
            for child in children:
                require(isinstance(child, list) and len(child) == 2, "CHILD_PAIR")
                option, child_index = child
                require(integer(option) and option in row_sets[r] and option not in explicit, "CHILD_OPTION")
                require(integer(child_index) and 0 <= child_index < node_index, "CHILD_ORDER")
                explicit[option] = child_index
            seen = set(explicit)
            for pair in omitted:
                require(isinstance(pair, list) and len(pair) == 2, "DOMINANCE_PAIR")
                option, representative = pair
                require(integer(option) and integer(representative), "DOMINANCE_INTEGER")
                require(option in row_sets[r] and option not in seen and representative in explicit, "DOMINANCE_OPTIONS")
                require((uncovered & option_hits[option]) <= (uncovered & option_hits[representative]), "FALSE_DOMINANCE")
                seen.add(option)
            require(seen == row_sets[r], "INCOMPLETE_BRANCH")
            for option, child_index in explicit.items():
                check(child_index, uncovered - option_hits[option], budget - 1)
        else:
            raise Rejected("UNSUPPORTED_PROOF_NODE")
        checked.add(state)

    check(root, frozenset(range(len(rows))), k - 1)
    return {"accepted": True, "optimum": k, "proof_nodes": len(nodes), "checked_states": len(checked),
            "wall_seconds": (time.perf_counter_ns() - t0) / 1e9}


def _decimal(x):
    require(type(x) is str, "DECIMAL_STRING_REQUIRED")
    value = Decimal(x)
    require(value.is_finite(), "NONFINITE_CLAIMED_VALUE")
    return value


def source_bound_first_record(record, source_path):
    from baselines import amidation
    begin = time.perf_counter_ns()
    require(record.get("source_sha256") == hashlib.sha256(Path(source_path).read_bytes()).hexdigest(), "SOURCE_BINDING")
    expected_url = "https://raw.githubusercontent.com/doyle-lab-ucla/bandit-optimization/ae3e910dcea27cfd1631a28b793b6c63607baedd/datasets/amidation.csv"
    require(record.get("source_url") == expected_url, "SOURCE_URL")
    require([c.get("fraction_percent") for c in record["cases"]] == [50, 70, 80, 90, 95], "CASE_DENOMINATOR")
    require(record.get("primary_fraction_percent") == 90, "PRIMARY_FRACTION")
    with Path(source_path).open(newline="") as f:
        original_rows = list(csv.DictReader(f))
    original = {(r["nucleophile_id"], (r["base_name"], r["solvent_name"], r["activator_name"])): (line, r)
                for line, r in enumerate(original_rows, start=2)}
    results = []
    for case in record["cases"]:
        p = amidation(source_path, case["fraction_percent"])
        require(record.get("source_rows") == len(original_rows), "SOURCE_ROW_COUNT")
        require(record.get("condition_count") == len(p.options), "CONDITION_COUNT")
        require(record.get("substrate_count") == len(p.required), "SUBSTRATE_COUNT")
        recorded_range = record.get("recorded_yield_range_percent")
        require(isinstance(recorded_range, list) and len(recorded_range) == 2, "YIELD_RANGE")
        require([_decimal(x) for x in recorded_range] == [Decimal(p.details["minimum_recorded_yield"]),
                Decimal(p.details["maximum_recorded_yield"])], "YIELD_RANGE_CHANGED")
        expected_labels = [json.dumps({"base_name": o[0], "solvent_name": o[1], "activator_name": o[2]}, sort_keys=True)
                           for o in p.options]
        expected = {"schema": "frontier-cover-instance/v1", "option_ids": expected_labels, "requirements": p.rows}
        require(case["problem"] == expected, "SOURCE_DERIVATION_MISMATCH")
        outcome = case["result"]
        require(outcome.get("selected") == outcome["certificate"]["selected"], "RESULT_SELECTION_MISMATCH")
        require(outcome.get("cardinality") == outcome["certificate"]["optimum"], "RESULT_CARDINALITY_MISMATCH")
        result = verify(expected, outcome["certificate"])
        selected = outcome["selected"]
        recipes = case.get("recipes")
        expected_recipes = [{"index": j, "base_name": p.options[j][0], "solvent_name": p.options[j][1],
                             "activator_name": p.options[j][2]} for j in selected]
        require(recipes == expected_recipes, "DISPLAYED_RECIPE_MISMATCH")
        assignments = case.get("assignments")
        require(isinstance(assignments, list) and len(assignments) == len(p.required), "ASSIGNMENT_COUNT")
        require([a.get("substrate_id") for a in assignments] == p.required, "ASSIGNMENT_SUBSTRATE_DENOMINATOR")
        slacks = []
        for a, s in zip(assignments, p.required):
            j = a.get("condition_index")
            require(integer(j) and j in selected, "ASSIGNED_CONDITION_NOT_SELECTED")
            line, raw = original[s, tuple(p.options[j])]
            require(a.get("substrate_name") == raw["nucleophile_name"], "ASSIGNED_SUBSTRATE_NAME")
            require(integer(a.get("csv_line")) and a["csv_line"] == line, "ASSIGNMENT_SOURCE_LINE")
            measured = Decimal(raw["yield"])
            maximum = Decimal(p.details["maxima"][s])
            threshold = maximum * case["fraction_percent"] / 100
            require(_decimal(a.get("recorded_yield_percent")) == measured, "ASSIGNMENT_YIELD")
            require(_decimal(a.get("recorded_maximum_percent")) == maximum, "ASSIGNMENT_MAXIMUM")
            require(_decimal(a.get("required_yield_percent")) == threshold, "ASSIGNMENT_THRESHOLD")
            require(measured >= threshold, "ASSIGNMENT_NOT_ACCEPTABLE")
            slacks.append(measured - threshold)
        require(case.get("covered_substrates") == len(p.required), "COVERED_SUBSTRATE_COUNT")
        counts = [sum(j in row for row in p.rows) for j in range(len(p.options))]
        best_index = case.get("best_single_condition_index")
        require(integer(best_index) and 0 <= best_index < len(counts), "BEST_SINGLE_INDEX")
        require(case.get("best_single_condition_coverage") == max(counts) == counts[best_index], "BEST_SINGLE_COVERAGE")
        result["fraction_percent"] = case["fraction_percent"]
        result["semantic_output_verified"] = True
        result["minimum_recorded_acceptance_slack_percentage_points"] = str(min(slacks))
        results.append(result)
    return {"schema": "frontier-independent-full-source-verdict/v2", "accepted": True, "cases": results,
            "complete_source_and_output_verification_wall_seconds": (time.perf_counter_ns() - begin) / 1e9,
            "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "independence": "Rebuilt original source; verified every displayed recipe, assignment, yield, maximum, threshold, source line, coverage and mathematical certificate without production imports."}


def source_bound_first(path, source_path):
    result = source_bound_first_record(json.loads(Path(path).read_text()), source_path)
    result.update({
            "producer_result_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
    })
    return result


def source_bound_successor_record(record, source_root):
    from baselines import diagnostic, EXPECTED
    begin = time.perf_counter_ns()
    expected_ids = [f"{name}:{gap}" for name in ("nib-etoh.csv", "nib-meoh.csv") for gap in (10, 15, 20, 25, 30)]
    require(record.get("registered_denominator") == 10 and record.get("completed_case_count") == 10,
            "SUCCESSOR_DENOMINATOR")
    require(record.get("failures") == [], "SUCCESSOR_REPORTED_FAILURE")
    cases = record.get("results")
    require(isinstance(cases, list) and [c.get("case_id") for c in cases] == expected_ids, "SUCCESSOR_CASE_ORDER")
    result_rows = []
    for case in cases:
        source = case["source"]
        name = source.get("filename")
        require(name in ("nib-etoh.csv", "nib-meoh.csv"), "SUCCESSOR_SOURCE_NAME")
        source_path = Path(source_root) / name
        raw_bytes = source_path.read_bytes()
        require(source.get("sha256") == EXPECTED[name] == hashlib.sha256(raw_bytes).hexdigest(), "SUCCESSOR_SOURCE_BINDING")
        require(source.get("bytes") == len(raw_bytes), "SUCCESSOR_SOURCE_BYTES")
        require(source.get("git_blob_sha1") == hashlib.sha1(b"blob " + str(len(raw_bytes)).encode() + b"\x00" + raw_bytes).hexdigest(),
                "SUCCESSOR_GIT_BLOB")
        require(source.get("repository") == "doyle-lab-ucla/bandit-optimization" and
                source.get("commit") == "ae3e910dcea27cfd1631a28b793b6c63607baedd" and
                source.get("path") == f"datasets/{name}", "SUCCESSOR_PROVENANCE")
        require(source.get("url") == f"https://raw.githubusercontent.com/doyle-lab-ucla/bandit-optimization/ae3e910dcea27cfd1631a28b793b6c63607baedd/datasets/{name}", "SUCCESSOR_SOURCE_URL")
        require(source.get("solvent") == {"nib-etoh.csv": "ethanol", "nib-meoh.csv": "methanol"}[name], "SUCCESSOR_SOLVENT")
        gap = _decimal(case.get("gap_percentage_points"))
        require(gap in map(Decimal, (10, 15, 20, 25, 30)), "SUCCESSOR_GAP")
        p = diagnostic(source_path, int(gap))
        expected = {"schema": "frontier-cover-instance/v1", "option_ids": p.options, "requirements": p.rows}
        require(case.get("problem") == expected, "SUCCESSOR_SOURCE_DERIVATION")
        require(case.get("requirement_ligand_pairs") == p.required, "SUCCESSOR_PAIR_LABELS")
        require(case.get("substrate_count") == len(p.options) and case.get("ligand_count") == p.details["condition_count"], "SUCCESSOR_MATRIX_COUNTS")
        require(case.get("full_pair_denominator") == p.details["all_condition_pair_count"], "SUCCESSOR_PAIR_DENOMINATOR")
        require(case.get("distinguishable_pair_count") == len(p.required), "SUCCESSOR_DISTINGUISHABLE_COUNT")
        indistinguishable = case.get("indistinguishable_pairs")
        require(isinstance(indistinguishable, list) and
                case.get("indistinguishable_pair_count") == len(p.details["indistinguishable_pairs"]) and
                [x.get("ligands") for x in indistinguishable] == p.details["indistinguishable_pairs"], "SUCCESSOR_OMITTED_PAIRS")
        require(case.get("primary") is (name == "nib-etoh.csv" and gap == 20), "SUCCESSOR_PRIMARY_LABEL")
        outcome = case["answer"]
        require(outcome.get("selected") == outcome["certificate"]["selected"] and
                outcome.get("cardinality") == outcome["certificate"]["optimum"], "SUCCESSOR_ANSWER_CERTIFICATE")
        checked = verify(expected, outcome["certificate"])
        selected_labels = [p.options[j] for j in outcome["selected"]]
        require(case.get("selected_substrates") == selected_labels, "SUCCESSOR_DISPLAYED_SELECTION")
        with source_path.open(newline="") as f:
            rows = list(csv.DictReader(f))
        source_rows = {(r["electrophile_id"], r["ligand_name"]): (line, r) for line, r in enumerate(rows, start=2)}
        for omitted in indistinguishable:
            a, b = omitted["ligands"]
            differences = {s: abs(Decimal(source_rows[s, a][1]["yield"]) - Decimal(source_rows[s, b][1]["yield"]))
                           for s in p.options}
            maximum_gap = max(differences.values())
            substrate = omitted.get("max_gap_substrate")
            require(substrate in p.options and differences[substrate] == maximum_gap < gap, "SUCCESSOR_OMITTED_MAXIMUM")
            require(_decimal(omitted.get("maximum_recorded_gap")) == maximum_gap, "SUCCESSOR_OMITTED_GAP")
            expected_rows = []
            for condition in (a, b):
                line, raw = source_rows[substrate, condition]
                expected_rows.append({"csv_line": line, "source_index": raw[""], "electrophile_id": substrate,
                                      "ligand_name": condition, "yield": raw["yield"]})
            require(omitted.get("source_rows_at_maximum") == expected_rows, "SUCCESSOR_OMITTED_SOURCE_ROWS")
        witnesses = case.get("source_linked_pair_witnesses")
        require(isinstance(witnesses, list) and len(witnesses) == len(p.required), "SUCCESSOR_WITNESS_COUNT")
        require([w.get("ligands") for w in witnesses] == p.required, "SUCCESSOR_WITNESS_PAIR_DENOMINATOR")
        slacks = []
        for witness, pair in zip(witnesses, p.required):
            substrate = witness.get("substrate")
            require(substrate in selected_labels, "SUCCESSOR_WITNESS_SUBSTRATE")
            expected_rows = []
            yields = []
            for condition in pair:
                line, raw = source_rows[substrate, condition]
                expected_rows.append({"csv_line": line, "source_index": raw[""], "electrophile_id": substrate,
                                      "ligand_name": condition, "yield": raw["yield"]})
                yields.append(Decimal(raw["yield"]))
            require(witness.get("source_rows") == expected_rows, "SUCCESSOR_WITNESS_SOURCE_ROWS")
            actual_gap = abs(yields[0] - yields[1])
            require(_decimal(witness.get("absolute_gap_percentage_points")) == actual_gap >= gap, "SUCCESSOR_WITNESS_GAP")
            slacks.append(actual_gap - gap)
        checked.update({"case_id": case["case_id"], "semantic_output_verified": True,
                        "minimum_recorded_gap_slack_percentage_points": str(min(slacks)) if slacks else None,
                        "indistinguishable_pairs": len(p.details["indistinguishable_pairs"])})
        result_rows.append(checked)
    return {"schema": "frontier-independent-full-successor-verdict/v1", "accepted": True, "cases": result_rows,
            "complete_source_and_output_verification_wall_seconds": (time.perf_counter_ns() - begin) / 1e9,
            "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "independence": "Original source reconstruction, complete displayed witnesses and exact certificates; no production imports."}


def source_bound_successor(path, source_root):
    result = source_bound_successor_record(json.loads(Path(path).read_text()), source_root)
    result["producer_result_sha256"] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--first-result", type=Path)
    group.add_argument("--successor-result", type=Path)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = source_bound_first(args.first_result, args.source) if args.first_result else source_bound_successor(args.successor_result, args.source)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
