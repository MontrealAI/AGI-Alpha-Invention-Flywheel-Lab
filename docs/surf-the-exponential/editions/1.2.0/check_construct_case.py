#!/usr/bin/env python3
"""Independently check the authored construction and refundable-cash case.

This file never imports the producer. It checks task answers directly from the
source states, enumerates set partitions as blocks rather than restricted-growth
strings, validates distinguishing witnesses, and simulates complete cash paths.
Independence means a separate implementation, not external scientific replication.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_NAMES = ("construct_protocol.json", "construct_case.py", "test_construct_case.py", "check_construct_case.py")


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def same(actual: object, expected: object, message: str) -> None:
    # JSON comparison also distinguishes booleans from integer labels and counts.
    ensure(canonical(actual) == canonical(expected), message)


def task_answers(protocol: dict, states: list[list[int]], task: str) -> list[list[bool]]:
    if task == "primary":
        return [
            [not any(reading > limit for reading in state) for limit in protocol[task]["thresholds"]]
            for state in states
        ]
    return [
        [not any(reading < low or reading > high for reading in state)
         for low, high in protocol[task]["intervals"]]
        for state in states
    ]


def canonical_classes(keys: list) -> tuple[list[int], list[int]]:
    """Assign a state to the first earlier equivalent representative."""
    representatives: list[int] = []
    labels = []
    for state_index, key in enumerate(keys):
        matching = [label for label, representative in enumerate(representatives)
                    if key == keys[representative]]
        if matching:
            labels.append(matching[0])
        else:
            labels.append(len(representatives))
            representatives.append(state_index)
    return labels, representatives


def set_partitions(size: int):
    """Enumerate every partition once by insertion into disjoint state blocks."""
    def insert(index: int, blocks: list[list[int]]):
        if index == size:
            yield blocks
            return
        for slot in range(len(blocks)):
            updated = [block[:] for block in blocks]
            updated[slot].append(index)
            yield from insert(index + 1, updated)
        yield from insert(index + 1, blocks + [[index]])

    yield from insert(0, [])


def inspect_partitions(answers: dict[str, list[list[bool]]]) -> dict:
    """A block is legal only if it merges no task-distinguishable state pair."""
    size = len(answers["primary"])
    forbidden = {
        task: {(left, right) for left, right in itertools.combinations(range(size), 2)
               if rows[left] != rows[right]}
        for task, rows in answers.items()
    }
    counts = {task: 0 for task in answers}
    minima = {task: size + 1 for task in answers}
    partition_count = 0
    for blocks in set_partitions(size):
        partition_count += 1
        merged_pairs = {pair for block in blocks for pair in itertools.combinations(block, 2)}
        for task in answers:
            if not (merged_pairs & forbidden[task]):
                counts[task] += 1
                minima[task] = min(minima[task], len(blocks))
    return {
        "partition_count": partition_count,
        **{task: {"exact_partition_count": counts[task], "minimum_labels": minima[task]}
           for task in answers},
    }


def validate_collision(witness: object, labels: list[int], rows: list[list[bool]], context: str) -> None:
    conflicting = [(left, right) for left, right in itertools.combinations(range(len(labels)), 2)
                   if labels[left] == labels[right] and rows[left] != rows[right]]
    if not conflicting:
        same(witness, None, f"{context}: collision claimed for a sufficient representation")
        return
    ensure(isinstance(witness, dict), f"{context}: a real collision witness is missing")
    same(sorted(witness), sorted(("left_state_index", "right_state_index", "query_index",
                                 "left_answer", "right_answer")), f"{context}: malformed witness")
    left, right, query = (witness[name] for name in ("left_state_index", "right_state_index", "query_index"))
    ensure(all(type(index) is int for index in (left, right, query)), f"{context}: witness indices must be integers")
    ensure(0 <= left < len(labels) and 0 <= right < len(labels) and left != right,
           f"{context}: state index out of scope")
    ensure(0 <= query < len(rows[0]), f"{context}: query index out of scope")
    ensure(labels[left] == labels[right], f"{context}: states have different observations")
    ensure(rows[left][query] != rows[right][query], f"{context}: witness does not distinguish outcomes")
    same(witness["left_answer"], rows[left][query], f"{context}: incorrect left outcome")
    same(witness["right_answer"], rows[right][query], f"{context}: incorrect right outcome")


def check_task(observed: dict, protocol: dict, rows: list[list[bool]], task: str) -> list[int]:
    parameters = protocol[task]["thresholds" if task == "primary" else "intervals"]
    same(sorted(observed), sorted(("query_parameters", "state_query_checks", "artifact")),
         f"{task}: unexpected result fields")
    same(observed["query_parameters"], parameters, f"{task}: query family changed")
    same(observed["state_query_checks"], len(rows) * len(parameters), f"{task}: check count differs")
    artifact = observed["artifact"]
    same(sorted(artifact), sorted(("state_labels", "decoder", "class_count", "representative_state_indices",
                                 "separating_queries")), f"{task}: malformed artifact")
    labels, representatives = canonical_classes(rows)
    same(artifact["state_labels"], labels, f"{task}: encoder does not match task equivalence")
    same(artifact["class_count"], len(representatives), f"{task}: class count differs")
    same(artifact["representative_state_indices"], representatives, f"{task}: representative states differ")
    same(artifact["decoder"], [rows[index] for index in representatives], f"{task}: decoder differs")
    # Exercise the emitted encoder/decoder for every source state and query.
    for state_index, expected_answers in enumerate(rows):
        decoded = artifact["decoder"][artifact["state_labels"][state_index]]
        same(decoded, expected_answers, f"{task}: emitted instrument fails at state {state_index}")
    pairs = set(itertools.combinations(range(len(representatives)), 2))
    witnesses = artifact["separating_queries"]
    ensure(isinstance(witnesses, list), f"{task}: separating witnesses must be a list")
    ensure(len(witnesses) == len(pairs), f"{task}: missing pairwise minimality witnesses")
    for witness in witnesses:
        same(sorted(witness), sorted(("left_label", "right_label", "query_index", "left_answer", "right_answer")),
             f"{task}: malformed separating query")
        left, right, query = (witness[name] for name in ("left_label", "right_label", "query_index"))
        ensure(all(type(index) is int for index in (left, right, query)), f"{task}: noninteger witness index")
        ensure((left, right) in pairs, f"{task}: duplicate or invalid witness pair")
        pairs.remove((left, right))
        ensure(0 <= query < len(parameters), f"{task}: separating query out of range")
        left_answer, right_answer = rows[representatives[left]][query], rows[representatives[right]][query]
        ensure(left_answer != right_answer, f"{task}: witnesses fail to establish a necessary distinction")
        same(witness["left_answer"], left_answer, f"{task}: left witness outcome differs")
        same(witness["right_answer"], right_answer, f"{task}: right witness outcome differs")
    ensure(not pairs, f"{task}: incomplete lower-bound certificate")
    return labels


def cash_trace(events: list[int], openings: list[int]) -> dict:
    cumulative = []
    running = 0
    for event in events:
        running += event
        cumulative.append(running)

    def feasible(opening: int) -> bool:
        balance = opening
        for event in events:
            balance += event
            if balance < 0:
                return False
        return True

    # Search integer capital and directly execute the path; all case amounts are
    # integral. A prefix attaining the requirement also proves real-valued minimality.
    upper_bound = sum(-event for event in events if event < 0)
    required = next(capital for capital in range(upper_bound + 1) if feasible(capital))
    return {
        "events": events, "cumulative_flows": cumulative,
        "minimum_opening_cash": required, "net_contribution": running,
        "feasible_at_opening_cash": {str(opening): feasible(opening) for opening in openings},
    }


def finance_expectations(spec: dict) -> dict:
    construction = spec["construction_cost"]
    buyers = spec["buyers"]
    per_buyer = spec["delivery_cost_per_buyer"]
    delivery = sum(per_buyer for _ in buyers)
    total = construction + delivery
    prices = [buyer["price_on_acceptance"] for buyer in buyers]
    values = [buyer["value_relative_to_outside_option"] for buyer in buyers]
    receipts = sum(prices)
    advance = spec["refundable_advance_total"]
    openings = spec["opening_cash_values"]
    surpluses = [value - price for value, price in zip(values, prices)]
    standalone_costs = [construction + per_buyer for _ in buyers]
    standalone_surpluses = [value - cost for value, cost in zip(values, standalone_costs)]
    paths = {
        "success_without_advance": cash_trace([-construction, -delivery, receipts], openings),
        "success_with_advance": cash_trace([advance, -construction, -delivery, receipts - advance], openings),
        "failure_with_full_refund": cash_trace([advance, -construction, -delivery, -advance], openings),
    }
    adverse_ids = ["success_with_advance", "failure_with_full_refund"]
    robust_requirement = max(paths[key]["minimum_opening_cash"] for key in adverse_ids)
    success_gain = paths["success_with_advance"]["net_contribution"]
    failure_gain = paths["failure_with_full_refund"]["net_contribution"]
    points = []
    for value in spec["success_probability_points"]:
        p = Fraction(value)
        ensure(0 <= p <= 1, "Success probability point is out of range")
        expected = p * success_gain + (1 - p) * failure_gain
        points.append({"p": value, "operator_expected_contribution": str(expected),
                       "buyer_expected_surpluses": [str(p * surplus) for surplus in surpluses],
                       "operator_participates": expected >= 0})
    sweep = spec["construction_cost_sweep"]
    digest = hashlib.sha256()
    rows = []
    for fixed_cost in range(sweep["minimum"], sweep["maximum"] + 1, sweep["step"]):
        success = cash_trace([advance, -fixed_cost, -delivery, receipts - advance], [])
        failure = cash_trace([advance, -fixed_cost, -delivery, -advance], [])
        minimum = max(success["minimum_opening_cash"], failure["minimum_opening_cash"])
        row = {"construction_cost": fixed_cost, "successful_contribution": success["net_contribution"],
               "minimum_opening_cash": minimum, "cash_feasible": minimum <= spec["sweep_opening_cash"],
               "positive_success_contribution": success["net_contribution"] > 0}
        rows.append(row)
        digest.update(canonical(row) + b"\n")

    def summary(selected: list[int]) -> dict:
        return {"minimum": min(selected), "maximum": max(selected), "count": len(selected)}

    feasible_costs = [row["construction_cost"] for row in rows if row["cash_feasible"]]
    positive_costs = [row["construction_cost"] for row in rows if row["positive_success_contribution"]]
    positive_unfunded = [row["construction_cost"] for row in rows
                        if row["positive_success_contribution"] and not row["cash_feasible"]]
    return {
        "assumptions": spec,
        "shared": {"construction_cost": construction, "delivery_cost_total": delivery, "total_cost": total,
                   "receipts_on_success": receipts, "successful_contribution": receipts - total,
                   "buyer_surpluses_on_success": surpluses, "buyer_surpluses_on_failure": [0 for _ in buyers],
                   "all_buyers_nonnegative_surplus": all(value >= 0 for value in surpluses)},
        "standalone": {"total_cost": sum(standalone_costs), "cost_per_buyer": standalone_costs,
                       "buyer_value_caps": values, "value_minus_cost_per_buyer": standalone_surpluses,
                       "total_value_minus_cost": sum(standalone_surpluses),
                       "all_standalone_self_funding_at_value_cap": all(value >= 0 for value in standalone_surpluses)},
        "ordinary_shared": {"total_cost": total, "successful_contribution": receipts - total, "matches_shared": True},
        "cash_paths": paths,
        "all_declared_advance_paths": {
            "path_ids": adverse_ids, "minimum_opening_cash": robust_requirement,
            "feasible_at_opening_cash": {
                str(opening): all(paths[key]["feasible_at_opening_cash"][str(opening)] for key in adverse_ids)
                for opening in openings},
            "advance_reduces_success_path_requirement_by":
                paths["success_without_advance"]["minimum_opening_cash"] - paths["success_with_advance"]["minimum_opening_cash"],
            "advance_reduces_full_obligation_requirement_by":
                paths["success_without_advance"]["minimum_opening_cash"] - robust_requirement,
        },
        "probability_analysis": {
            "symbol": "p", "operator_expected_contribution": {"constant": failure_gain, "coefficient": success_gain - failure_gain},
            "operator_nonnegative_at_or_above": str(Fraction(-failure_gain, success_gain - failure_gain)),
            "buyer_expected_surplus_coefficients": surpluses, "points": points,
        },
        "sweep": {
            "opening_cash": spec["sweep_opening_cash"], "point_count": len(rows), "canonical_rows_sha256": digest.hexdigest(),
            "successful_contribution_formula": {"constant": receipts - delivery, "construction_cost_coefficient": -1},
            "full_obligation_cash_formula": {"constant": delivery, "construction_cost_coefficient": 1},
            "cash_feasible_construction_costs": summary(feasible_costs),
            "positive_success_contribution_costs": summary(positive_costs),
            "positive_success_but_insufficient_cash": summary(positive_unfunded),
            "zero_success_contribution_costs": [row["construction_cost"] for row in rows if row["successful_contribution"] == 0],
            "separate_construction_value_feasible_up_to": min(values) - per_buyer,
            "shared_positive_contribution_below": receipts - delivery,
            "full_refund_cash_feasible_up_to": max(feasible_costs),
        },
    }


def check_publication(evidence: Path | None = None, protocol_path: Path | None = None) -> dict:
    evidence = Path(evidence) if evidence is not None else ROOT / "evidence"
    protocol_path = Path(protocol_path) if protocol_path is not None else ROOT / "construct_protocol.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    observed = json.loads((evidence / "construct_results.json").read_text(encoding="utf-8"))
    same(protocol["schema_version"], "1.0.0", "Unsupported protocol schema")
    same(protocol["case_id"], "task-relative-construction-and-refundable-cash", "Unexpected case")
    same(protocol["status"], "authored_finite_demonstration", "Case status changed")
    same(protocol["domain"], {"reading_values": [60, 80, 100], "readings_per_state": 2,
                              "state_order": "lexicographic_ordered_pairs"}, "Finite source domain changed")
    same(protocol["primary"], {"predicate": "every_reading_at_most_threshold", "thresholds": [60, 80, 90, 100]},
         "Primary task contract changed")
    same(protocol["successor"], {"predicate": "every_reading_in_closed_interval",
                                 "intervals": [[60, 60], [60, 80], [60, 100], [80, 80], [80, 100], [100, 100]]},
         "Successor task contract changed")
    same(sorted(observed), sorted(("schema_version", "case_id", "source_sha256", "scope", "states", "primary",
                                  "successor", "representations", "partition_enumeration", "finance")),
         "Unexpected top-level result fields")
    same(observed["schema_version"], protocol["schema_version"], "Output schema changed")
    same(observed["case_id"], protocol["case_id"], "Output case identifier changed")
    same(observed["scope"], protocol["scope"], "Published scope differs from the protocol")
    expected_hashes = {name: hashlib.sha256((protocol_path if name == "construct_protocol.json" else ROOT / name).read_bytes()).hexdigest()
                       for name in SOURCE_NAMES}
    same(observed["source_sha256"], expected_hashes, "Source identity differs; regenerate from the named sources")
    states = [[first, second] for first in protocol["domain"]["reading_values"]
              for second in protocol["domain"]["reading_values"]]
    same(observed["states"], states, "Source state ordering or coverage differs")
    answers = {task: task_answers(protocol, states, task) for task in ("primary", "successor")}
    constructed = {task: check_task(observed[task], protocol, answers[task], task) for task in answers}
    keys = {
        "mean_only": [Fraction(sum(state), len(state)) for state in states],
        "constructed_primary": constructed["primary"],
        "conventional_maximum": [sorted(state)[-1] for state in states],
        "mean_plus_flag": [(Fraction(sum(state), len(state)), not any(x > protocol["patch_threshold"] for x in state))
                           for state in states],
        "constructed_successor": constructed["successor"],
        "conventional_minimum_maximum": [(sorted(state)[0], sorted(state)[-1]) for state in states],
        "raw_ordered_pair": [tuple(state) for state in states],
    }
    same(protocol["representations"], list(keys), "Missing or reordered representation controls")
    same(sorted(observed["representations"]), sorted(keys), "Representation result set differs")
    for identifier, representation_keys in keys.items():
        row = observed["representations"][identifier]
        same(sorted(row), sorted(("label_count", "state_labels", "primary_exact", "successor_exact",
                                  "primary_collision", "successor_collision")), f"{identifier}: result fields differ")
        labels, representatives = canonical_classes(representation_keys)
        same(row["state_labels"], labels, f"{identifier}: source-to-label mapping differs")
        same(row["label_count"], len(representatives), f"{identifier}: label count differs")
        for task, rows in answers.items():
            exact = all(labels[left] != labels[right] or rows[left] == rows[right]
                        for left, right in itertools.combinations(range(len(states)), 2))
            same(row[f"{task}_exact"], exact, f"{identifier}: {task} verdict differs")
            validate_collision(row[f"{task}_collision"], labels, rows, f"{identifier}/{task}")
    partitions = inspect_partitions(answers)
    same(partitions, {"partition_count": 21147, "primary": {"exact_partition_count": 260, "minimum_labels": 3},
                      "successor": {"exact_partition_count": 8, "minimum_labels": 6}}, "Exhaustive partition totals changed")
    same(observed["partition_enumeration"], partitions, "Partition enumeration or optimality result differs")
    expected_finance = finance_expectations(protocol["finance"])
    same(observed["finance"], expected_finance, "Participation, cash, probability or sensitivity result differs")
    same(expected_finance["all_declared_advance_paths"]["minimum_opening_cash"], 90, "Full-refund requirement must remain 90")
    same(expected_finance["probability_analysis"]["operator_nonnegative_at_or_above"], "3/4", "Conditional participation boundary changed")
    return {
        "status": "PASS", "source_states_checked": len(states),
        "primary_state_query_checks": sum(len(row) for row in answers["primary"]),
        "successor_state_query_checks": sum(len(row) for row in answers["successor"]),
        "pairwise_minimality_witnesses_checked": sum(len(observed[task]["artifact"]["separating_queries"]) for task in answers),
        "partitions_enumerated": partitions["partition_count"],
        "representations_checked": len(keys), "cash_paths_checked": len(expected_finance["cash_paths"]),
        "complete_advance_outcome_paths_checked": len(expected_finance["all_declared_advance_paths"]["path_ids"]),
        "construction_costs_checked": expected_finance["sweep"]["point_count"], "source_files_bound": len(SOURCE_NAMES),
        "scope": "Separate exhaustive finite implementation; no measured model, market, consent, or discovery advantage.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, help="Evidence directory containing construct_results.json")
    parser.add_argument("--protocol", type=Path, help="Frozen protocol path; defaults to the sibling protocol")
    args = parser.parse_args()
    print(json.dumps(check_publication(evidence=args.evidence, protocol_path=args.protocol), indent=2))


if __name__ == "__main__":
    main()
