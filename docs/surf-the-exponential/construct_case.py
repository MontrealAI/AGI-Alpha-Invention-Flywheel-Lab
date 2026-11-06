#!/usr/bin/env python3
"""Construct and audit one authored finite example using only the standard library.

The generic constructor partitions raw states by complete answer signatures. It
is ordinary task-relative quotient construction, not a new invention algorithm
or an experiment on a language model. Label counts are not total costs. Finance
amounts and outcome paths are stipulated separately, not revenue earned by code.

Run: python3 construct_case.py [--output /absolute/output/directory]
check_construct_case.py independently verifies the resulting artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_FILES = ("construct_protocol.json", "construct_case.py", "check_construct_case.py", "test_construct_case.py")


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def integer(value: object, name: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def probability(value: object) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (str, int, Fraction)):
        raise ValueError("A probability must be an exact rational string or integer")
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("Invalid rational probability") from exc
    if not 0 <= result <= 1:
        raise ValueError("A probability must lie in [0,1]")
    return result


def validate_protocol(p: dict) -> None:
    if p["schema_version"] != "1.1.0":
        raise ValueError("Unsupported protocol schema")
    if (p["domain"]["state_order"] != "lexicographic_ordered_pairs"
            or p["primary"]["predicate"] != "every_reading_at_most_threshold"
            or p["successor"]["predicate"] != "every_reading_in_closed_interval"):
        raise ValueError("Unsupported state order or query semantics")
    values = p["domain"]["reading_values"]
    if not values or values != sorted(set(values)):
        raise ValueError("Reading values must be nonempty, increasing, and unique")
    for value in values:
        integer(value, "reading value")
    if p["domain"]["readings_per_state"] != 2:
        raise ValueError("This finite case requires exactly two readings per state")
    thresholds = p["primary"]["thresholds"]
    if not thresholds or thresholds != sorted(set(thresholds)):
        raise ValueError("Thresholds must be nonempty, increasing, and unique")
    for threshold in thresholds:
        integer(threshold, "threshold")
    intervals = p["successor"]["intervals"]
    if not intervals or len({tuple(interval) for interval in intervals}) != len(intervals):
        raise ValueError("Intervals must be nonempty and distinct")
    for interval in intervals:
        if len(interval) != 2:
            raise ValueError("An interval requires two endpoints")
        lo, hi = interval
        integer(lo, "interval lower bound")
        integer(hi, "interval upper bound")
        if lo > hi:
            raise ValueError("Interval endpoints are reversed")
    integer(p["patch_threshold"], "patch threshold")
    f = p["finance"]
    for key in ("construction_cost", "delivery_cost_per_buyer", "refundable_advance_total", "sweep_opening_cash"):
        integer(f[key], key, 0)
    if not f["buyers"]:
        raise ValueError("At least one buyer is required")
    for buyer in f["buyers"]:
        integer(buyer["value_relative_to_outside_option"], "buyer value", 0)
        integer(buyer["price_on_acceptance"], "buyer price", 0)
    receipts = sum(buyer["price_on_acceptance"] for buyer in f["buyers"])
    if receipts <= 0 or f["refundable_advance_total"] > receipts:
        raise ValueError("Positive receipts must cover the advance")
    for cash in f["opening_cash_values"]:
        integer(cash, "opening cash", 0)
    for point in f["success_probability_points"]:
        probability(point)
    sweep = f["construction_cost_sweep"]
    integer(sweep["minimum"], "minimum construction cost", 0)
    integer(sweep["maximum"], "maximum construction cost", sweep["minimum"])
    integer(sweep["step"], "construction cost step", 1)


def canonical_labels(observations) -> list[int]:
    labels: dict[object, int] = {}
    return [labels.setdefault(value, len(labels)) for value in observations]


def construct(signatures: list[list[bool]]) -> dict:
    """Build a representation for the entire declared family, before query choice."""
    if not signatures or not signatures[0]:
        raise ValueError("Source states and query family must both be nonempty")
    width = len(signatures[0])
    if any(len(row) != width or any(type(answer) is not bool for answer in row) for row in signatures):
        raise ValueError("Answer signatures must form a rectangular Boolean table")
    state_labels = canonical_labels(tuple(row) for row in signatures)
    count = len(set(state_labels))
    representatives = [state_labels.index(label) for label in range(count)]
    decoder = [list(signatures[index]) for index in representatives]
    witnesses = []
    for left, right in itertools.combinations(range(count), 2):
        query = next(i for i in range(width) if decoder[left][i] != decoder[right][i])
        witnesses.append({
            "left_label": left, "right_label": right, "query_index": query,
            "left_answer": decoder[left][query], "right_answer": decoder[right][query],
        })
    return {
        "state_labels": state_labels, "decoder": decoder, "class_count": count,
        "representative_state_indices": representatives, "separating_queries": witnesses,
    }


def collision(labels: list[int], signatures: list[list[bool]]) -> dict | None:
    for left, right in itertools.combinations(range(len(labels)), 2):
        if labels[left] != labels[right]:
            continue
        for query, (left_answer, right_answer) in enumerate(zip(signatures[left], signatures[right])):
            if left_answer != right_answer:
                return {
                    "left_state_index": left, "right_state_index": right,
                    "query_index": query, "left_answer": left_answer, "right_answer": right_answer,
                }
    return None


def restricted_growth_partitions(size: int):
    """Enumerate each unlabeled partition once as a restricted-growth string."""
    integer(size, "partition size", 1)

    def extend(prefix: tuple[int, ...], maximum: int):
        if len(prefix) == size:
            yield prefix
            return
        for label in range(maximum + 2):
            yield from extend(prefix + (label,), max(maximum, label))

    yield from extend((0,), 0)


def supports(labels, signatures: list[list[bool]]) -> bool:
    observed = {}
    for label, row in zip(labels, signatures):
        signature = tuple(row)
        if label in observed and observed[label] != signature:
            return False
        observed[label] = signature
    return True


def enumerate_partitions(primary: list[list[bool]], successor: list[list[bool]]) -> dict:
    result = {
        "partition_count": 0,
        "primary": {"exact_partition_count": 0, "minimum_labels": len(primary)},
        "successor": {"exact_partition_count": 0, "minimum_labels": len(successor)},
    }
    for labels in restricted_growth_partitions(len(primary)):
        result["partition_count"] += 1
        for name, table in (("primary", primary), ("successor", successor)):
            if supports(labels, table):
                entry = result[name]
                entry["exact_partition_count"] += 1
                entry["minimum_labels"] = min(entry["minimum_labels"], max(labels) + 1)
    return result


def cash_path(events: list[int], opening_cash_values: list[int]) -> dict:
    cumulative = list(itertools.accumulate(events))
    requirement = -min([0, *cumulative])
    return {
        "events": events, "cumulative_flows": cumulative,
        "minimum_opening_cash": requirement, "net_contribution": sum(events),
        "feasible_at_opening_cash": {str(cash): cash >= requirement for cash in opening_cash_values},
    }


def finite_range(values: list[int]) -> dict:
    return {"minimum": min(values) if values else None, "maximum": max(values) if values else None, "count": len(values)}


def finance_case(f: dict) -> dict:
    fixed = f["construction_cost"]
    per_buyer = f["delivery_cost_per_buyer"]
    buyers = f["buyers"]
    delivery = len(buyers) * per_buyer
    cost = fixed + delivery
    receipts = sum(buyer["price_on_acceptance"] for buyer in buyers)
    values = [buyer["value_relative_to_outside_option"] for buyer in buyers]
    surplus = [buyer["value_relative_to_outside_option"] - buyer["price_on_acceptance"] for buyer in buyers]
    advance = f["refundable_advance_total"]
    cash_values = f["opening_cash_values"]
    paths = {
        "success_without_advance": cash_path([-fixed, -delivery, receipts], cash_values),
        "success_with_advance": cash_path([advance, -fixed, -delivery, receipts - advance], cash_values),
        "failure_with_full_refund": cash_path([advance, -fixed, -delivery, -advance], cash_values),
    }
    complete_requirement = max(paths[name]["minimum_opening_cash"] for name in ("success_with_advance", "failure_with_full_refund"))
    points = []
    for point in f["success_probability_points"]:
        p = probability(point)
        expected = p * (receipts - cost) + (1 - p) * (-cost)
        points.append({
            "p": str(p), "operator_expected_contribution": str(expected),
            "buyer_expected_surpluses": [str(p * value) for value in surplus],
            "operator_participates": expected >= 0,
        })
    sweep = f["construction_cost_sweep"]
    cash = f["sweep_opening_cash"]
    rows = [{
        "construction_cost": candidate,
        "successful_contribution": receipts - candidate - delivery,
        "minimum_opening_cash": candidate + delivery,
        "cash_feasible": candidate + delivery <= cash,
        "positive_success_contribution": receipts - candidate - delivery > 0,
    } for candidate in range(sweep["minimum"], sweep["maximum"] + 1, sweep["step"])]
    digest = hashlib.sha256(b"".join(canonical(row) + b"\n" for row in rows)).hexdigest()
    return {
        "assumptions": f,
        "shared": {
            "construction_cost": fixed, "delivery_cost_total": delivery, "total_cost": cost,
            "receipts_on_success": receipts, "successful_contribution": receipts - cost,
            "buyer_surpluses_on_success": surplus, "buyer_surpluses_on_failure": [0] * len(buyers),
            "all_buyers_nonnegative_surplus": all(value >= 0 for value in surplus),
        },
        "standalone": {
            "total_cost": len(buyers) * (fixed + per_buyer),
            "cost_per_buyer": [fixed + per_buyer] * len(buyers), "buyer_value_caps": values,
            "value_minus_cost_per_buyer": [value - fixed - per_buyer for value in values],
            "total_value_minus_cost": sum(values) - len(buyers) * (fixed + per_buyer),
            "all_standalone_self_funding_at_value_cap": all(value >= fixed + per_buyer for value in values),
        },
        "ordinary_shared": {"total_cost": cost, "successful_contribution": receipts - cost, "matches_shared": True},
        "cash_paths": paths,
        "all_declared_advance_paths": {
            "path_ids": ["success_with_advance", "failure_with_full_refund"],
            "minimum_opening_cash": complete_requirement,
            "feasible_at_opening_cash": {str(value): value >= complete_requirement for value in cash_values},
            "advance_reduces_success_path_requirement_by": paths["success_without_advance"]["minimum_opening_cash"] - paths["success_with_advance"]["minimum_opening_cash"],
            "advance_reduces_full_obligation_requirement_by": paths["success_without_advance"]["minimum_opening_cash"] - complete_requirement,
        },
        "probability_analysis": {
            "symbol": "p", "operator_expected_contribution": {"constant": -cost, "coefficient": receipts},
            "operator_nonnegative_at_or_above": str(Fraction(cost, receipts)),
            "buyer_expected_surplus_coefficients": surplus, "points": points,
        },
        "sweep": {
            "opening_cash": cash, "point_count": len(rows), "canonical_rows_sha256": digest,
            "successful_contribution_formula": {"constant": receipts - delivery, "construction_cost_coefficient": -1},
            "full_obligation_cash_formula": {"constant": delivery, "construction_cost_coefficient": 1},
            "cash_feasible_construction_costs": finite_range([row["construction_cost"] for row in rows if row["cash_feasible"]]),
            "positive_success_contribution_costs": finite_range([row["construction_cost"] for row in rows if row["positive_success_contribution"]]),
            "positive_success_but_insufficient_cash": finite_range([row["construction_cost"] for row in rows if row["positive_success_contribution"] and not row["cash_feasible"]]),
            "zero_success_contribution_costs": [row["construction_cost"] for row in rows if row["successful_contribution"] == 0],
            "separate_construction_value_feasible_up_to": min(values) - per_buyer,
            "shared_positive_contribution_below": receipts - delivery,
            "full_refund_cash_feasible_up_to": cash - delivery,
        },
    }


def nonnegative_rational(value: object, name: str) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (str, int, Fraction)):
        raise ValueError(f"{name} must be an exact rational string or integer")
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"Invalid rational {name}") from exc
    if result < 0:
        raise ValueError(f"{name} must be nonnegative")
    return result


def retention_decision(parameters: dict, deferred_access_available: bool) -> dict:
    """Value a fixed pre-expiry policy menu; conditional exercise may be declined.

    p concerns an opportunity needing a missing distinction, not arbitrary future
    queries. Values are incremental decision values, never advance cash. Gross
    bounds must be funded separately even when an expected value is favorable.
    """
    names = ("p", "q", "v", "c", "a", "r", "resource_allowance")
    if set(parameters) != set(names) or type(deferred_access_available) is not bool:
        raise ValueError("Declare exactly p,q,v,c,a,r,resource_allowance and a Boolean timing control")
    x = {name: probability(parameters[name]) if name in ("p", "q")
         else nonnegative_rational(parameters[name], name) for name in names}
    p, q, v, c, a, r = (x[name] for name in names[:-1])
    exercise = max(v - r, Fraction(0))
    values = {
        "ordinary_access": p * q * exercise,
        "retain_sufficient": p * v - c,
        "secure_access": p * exercise - a,
    }
    bounds = {"ordinary_access": r, "retain_sufficient": c, "secure_access": a + r}
    if deferred_access_available:
        # A capable late route uses ordinary access before buying anything.
        values["deferred_access"] = p * (q * exercise + (1 - q) * max(v - r - a, Fraction(0)))
        bounds["deferred_access"] = a + r
    required = max(bounds.values())
    if x["resource_allowance"] < required:
        raise ValueError("Current resource allowance must cover complete route costs before any benefit")
    best = max(values.values())
    return {
        "parameters": {name: str(x[name]) for name in names},
        "deferred_access_available": deferred_access_available,
        "policy_values": {name: str(value) for name, value in values.items()},
        "best_policies": [name for name, value in values.items() if value == best],
        "best_value": str(best),
        "policy_cost_bounds": {name: str(value) for name, value in bounds.items()},
        "required_resource_allowance": str(required), "all_policy_costs_funded": True,
    }


def retention_case(option: dict) -> dict:
    witness = option["gap_witness"]
    left, right = witness["left_source"], witness["right_source"]
    lo, hi = witness["future_interval"]
    left_answer = all(lo <= value <= hi for value in left)
    right_answer = all(lo <= value <= hi for value in right)
    if (witness["compact_representation"] != "maximum" or max(left) != max(right)
            or left_answer == right_answer):
        raise ValueError("The retention opportunity must require a genuinely missing distinction")

    def scenario(item: dict) -> dict:
        parameters = {**option["common_parameters"], "p": item["p"], "r": item["r"]}
        return {"id": item["id"], **retention_decision(parameters, item["deferred_access_available"])}

    return {
        "assumptions": option,
        "gap_witness": {
            "left_source": left, "right_source": right, "future_interval": [lo, hi],
            "compact_label_left": max(left), "compact_label_right": max(right),
            "left_answer": left_answer, "right_answer": right_answer,
        },
        "primary_scenarios": [scenario(item) for item in option["primary_scenarios"]],
        "switch_witness": scenario(option["switch_witness"]),
        "deferred_control": scenario(option["deferred_control"]),
    }


def build_results(protocol: dict) -> dict:
    validate_protocol(protocol)
    states = list(itertools.product(protocol["domain"]["reading_values"], repeat=2))
    primary = [[all(value <= threshold for value in state) for threshold in protocol["primary"]["thresholds"]] for state in states]
    successor = [[all(lo <= value <= hi for value in state) for lo, hi in protocol["successor"]["intervals"]] for state in states]
    first = construct(primary)
    second = construct(successor)
    representations = {
        "mean_only": canonical_labels(Fraction(sum(state), len(state)) for state in states),
        "constructed_primary": first["state_labels"],
        "conventional_maximum": canonical_labels(max(state) for state in states),
        "mean_plus_flag": canonical_labels((Fraction(sum(state), len(state)), all(value <= protocol["patch_threshold"] for value in state)) for state in states),
        "constructed_successor": second["state_labels"],
        "conventional_minimum_maximum": canonical_labels((min(state), max(state)) for state in states),
        "raw_ordered_pair": canonical_labels(states),
    }
    if list(representations) != protocol["representations"]:
        raise ValueError("Representation declarations do not match this implementation")
    controls = {}
    for name, labels in representations.items():
        primary_collision, successor_collision = collision(labels, primary), collision(labels, successor)
        controls[name] = {
            "label_count": len(set(labels)), "state_labels": labels,
            "primary_exact": primary_collision is None, "successor_exact": successor_collision is None,
            "primary_collision": primary_collision, "successor_collision": successor_collision,
        }
    return {
        "schema_version": protocol["schema_version"], "case_id": protocol["case_id"],
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCE_FILES},
        "scope": protocol["scope"], "states": [list(state) for state in states],
        "primary": {"query_parameters": protocol["primary"]["thresholds"], "state_query_checks": len(states) * len(primary[0]), "artifact": first},
        "successor": {"query_parameters": protocol["successor"]["intervals"], "state_query_checks": len(states) * len(successor[0]), "artifact": second},
        "representations": controls, "partition_enumeration": enumerate_partitions(primary, successor),
        "finance": finance_case(protocol["finance"]),
        "retention_option": retention_case(protocol["retention_option"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "evidence", help="Output directory for construct_results.json")
    args = parser.parse_args()
    protocol = json.loads((ROOT / "construct_protocol.json").read_text(encoding="utf-8"))
    results = build_results(protocol)
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / "construct_results.json"
    destination.write_text(json.dumps(results, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Wrote {destination}")
    print("Authored finite construction: " + "; ".join(
        f"{results[name]['state_query_checks']} {name} checks / {results[name]['artifact']['class_count']} labels"
        for name in ("primary", "successor")) + ".")
    finance = results["finance"]
    print(f"Refund-protected cash: {finance['all_declared_advance_paths']['minimum_opening_cash']}; "
          f"successful advance path alone: {finance['cash_paths']['success_with_advance']['minimum_opening_cash']}.")
    option = results["retention_option"]
    print("Retention policy winners: " + ", ".join("/".join(row["best_policies"]) for row in option["primary_scenarios"]) + ".")
    print(f"Deferred-access control: {option['deferred_control']['best_value']} incremental decision value.")


if __name__ == "__main__":
    main()
