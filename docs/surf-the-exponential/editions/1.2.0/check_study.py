#!/usr/bin/env python3
"""Check one-fixed-target publication arithmetic by explicit branch enumeration.

F is the truth of one prespecified material-defect proposition; D alleges that
same proposition and A accepts it. Unrelated or mixed true/false allegations are
outside this model. The accepted/accept-all comparison fixes G,H within truth
classes instead of inferring heterogeneous revision quality from acceptance.

This checker does not import study.py, call its utility formula, or accept its
verdicts. Independence here means a separate calculation, not an independent
empirical dataset, model family, author, or external scientific replication.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def read_rational(value: object) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (str, int, Fraction)):
        raise ValueError("An exact rational is required")
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("Malformed rational") from exc


def enumerate_branches(parameters: dict) -> tuple[dict[str, str], list[dict]]:
    required = {"pi", "d", "a", "f", "b", "G", "H", "K"}
    if set(parameters) != required:
        raise ValueError("Unexpected parameter set")
    p = {key: read_rational(value) for key, value in parameters.items()}
    for name in ("pi", "d", "f", "a", "b"):
        if p[name] < 0 or p[name] > 1:
            raise ValueError("Probability is out of range")
    if p["H"] < 0 or p["K"] < 0:
        raise ValueError("Negative harm or review cost")
    totals = {name: Fraction(0) for name in (
        "mass", "true_accept_probability", "false_accept_probability",
        "unaddressed_flaw_probability", "benefit_contribution",
        "harm_contribution", "review_cost", "delta",
    )}
    branches = []
    for flaw, proposed, accepted in itertools.product((False, True), repeat=3):
        flaw_weight = p["pi"] if flaw else 1 - p["pi"]
        proposal_rate = p["d"] if flaw else p["f"]
        proposal_weight = proposal_rate if proposed else 1 - proposal_rate
        if proposed:
            acceptance_rate = p["a"] if flaw else p["b"]
            acceptance_weight = acceptance_rate if accepted else 1 - acceptance_rate
        else:
            acceptance_weight = Fraction(0) if accepted else Fraction(1)
        probability = flaw_weight * proposal_weight * acceptance_weight
        payoff = p["G"] if accepted and flaw else -p["H"] if accepted else Fraction(0)
        totals["mass"] += probability
        totals["review_cost"] += probability * p["K"]
        totals["delta"] += probability * (payoff - p["K"])
        if flaw and accepted:
            totals["true_accept_probability"] += probability
            totals["benefit_contribution"] += probability * payoff
        elif not flaw and accepted:
            totals["false_accept_probability"] += probability
            totals["harm_contribution"] -= probability * payoff
        if flaw and not accepted:
            totals["unaddressed_flaw_probability"] += probability
        branches.append({
            "F": flaw, "D": proposed, "A": accepted,
            "probability": str(probability), "utility_after_review_cost": str(payoff - p["K"]),
        })
    if totals.pop("mass") != 1:
        raise ValueError("Branch probabilities do not sum to one")
    if any(read_rational(row["probability"]) < 0 for row in branches):
        raise ValueError("Negative branch probability")
    totals["value_with_stop"] = max(Fraction(0), totals["delta"])
    return {key: str(value) for key, value in totals.items()}, branches


def pair_enumeration(marginal: str, correlation: str) -> dict[str, str]:
    q, rho = read_rational(marginal), read_rational(correlation)
    if q <= 0 or q >= 1:
        raise ValueError("Degenerate Bernoulli correlation")
    # Correlation specifies the joint distribution; coverage is then enumerated.
    p11 = rho * q * (1 - q) + q ** 2
    distribution = {
        (True, True): p11,
        (True, False): q - p11,
        (False, True): q - p11,
        (False, False): 1 - 2 * q + p11,
    }
    if any(value < 0 for value in distribution.values()) or sum(distribution.values()) != 1:
        raise ValueError("Invalid joint detection distribution")
    union = sum(value for (first, second), value in distribution.items() if first or second)
    lower, upper = q, min(Fraction(1), q + q)
    if not lower <= union <= upper:
        raise ValueError("Union bound violation")
    return {
        "marginal_detection": str(q), "rho": str(rho), "both_detect": str(p11),
        "at_least_one_detects": str(union), "neither_detects": str(distribution[(False, False)]),
        "union_lower_bound": str(lower), "union_upper_bound": str(upper),
    }


def check_cash_prefixes(flows: list) -> dict:
    """Recalculate each supplied path prefix; no native financial state is held."""
    values = [read_rational(value) for value in flows]
    if not values:
        raise ValueError("An explicit successful path is required")
    prefixes = [sum(values[:end], Fraction(0)) for end in range(1, len(values) + 1)]
    minimum = max([Fraction(0)] + [-prefix for prefix in prefixes])
    if any(minimum + prefix < 0 for prefix in prefixes):
        raise ValueError("Calculated starting cash is insufficient")
    if minimum > 0 and not any(minimum + prefix == 0 for prefix in prefixes):
        raise ValueError("Claimed positive minimum is not tight")
    return {
        "cumulative_flows": [str(prefix) for prefix in prefixes],
        "total_inflows": str(sum((value for value in values if value > 0), Fraction(0))),
        "total_outflows": str(sum((-value for value in values if value < 0), Fraction(0))),
        "net_contribution": str(sum(values, Fraction(0))),
        "minimum_starting_cash": str(minimum),
    }


def formatted(value: str) -> str:
    q = read_rational(value)
    with localcontext() as context:
        context.prec = 50
        return format(Decimal(q.numerator) / Decimal(q.denominator), ".4f")


def ensure(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def check_publication(root: Path = ROOT, evidence: Path | None = None) -> dict:
    evidence = evidence if evidence is not None else root / "evidence"
    protocol = json.loads((root / "protocol.json").read_text(encoding="utf-8"))
    observed = json.loads((evidence / "results.json").read_text(encoding="utf-8"))
    for field in ("schema", "evidence_status", "units"):
        ensure(observed[field] == protocol[field], f"Mismatched {field}")
    ensure(observed["event_scope"] == protocol["events"], "Fixed-target event scope differs")
    source_names = {"protocol.json", "study.py", "check_study.py", "test_study.py"}
    ensure(set(observed["source_sha256"]) == source_names, "Incomplete source binding")
    for name, digest in observed["source_sha256"].items():
        ensure(hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, f"Changed source: {name}")
    specified = protocol["scenarios"] + protocol["controls"]
    ensure(len(protocol["scenarios"]) == 6 and len(protocol["controls"]) == 5, "Unexpected scenario/control count")
    ensure(len(specified) == observed["profile_count"] == len(observed["profiles"]) == 11, "Missing or extra profiles")
    ensure(len({row["id"] for row in specified}) == len(specified), "Duplicate profile identifier")
    verified = []
    for source, row in zip(specified, observed["profiles"]):
        for key in ("id", "label", "kind", "parameters"):
            ensure(row[key] == source[key], f"Changed profile {key}: {source['id']}")
        metrics, _ = enumerate_branches(source["parameters"])
        ensure(row["metrics"] == metrics, f"Branch calculation disagrees: {source['id']}")
        ensure(read_rational(metrics["delta"]) == read_rational(source["expected_delta"]), f"Declared delta differs: {source['id']}")
        delta = read_rational(metrics["delta"])
        verdict = "bound_only" if source["kind"] == "unavailable_bound" else "review" if delta > 0 else "incumbent" if delta < 0 else "tie"
        ensure(row["decision_vs_incumbent"] == verdict, f"Incorrect decision: {source['id']}")
        verified.append(row)

    grid = protocol["grid"]
    axis_order = grid["axis_order"]
    ensure(len(axis_order) == len(set(axis_order)) and set(axis_order) == set(grid["axes"]), "Invalid grid definition")
    ensure(not set(axis_order) & set(grid["fixed"]), "Overlapping grid/fixed parameters")
    digest = hashlib.sha256()
    signs = {"positive": 0, "zero": 0, "negative": 0}
    exact_values = []
    for index, point in enumerate(itertools.product(*(grid["axes"][name] for name in axis_order))):
        parameters = dict(grid["fixed"])
        parameters.update(zip(axis_order, point))
        metrics, _ = enumerate_branches(parameters)
        record = {"index": index, "parameters": parameters, "metrics": metrics}
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        digest.update(encoded + b"\n")
        value = read_rational(metrics["delta"])
        exact_values.append(value)
        signs["positive" if value > 0 else "negative" if value < 0 else "zero"] += 1
    ensure(len(exact_values) == grid["expected_count"] == 2304, "Incomplete grid")
    expected_grid = {
        "count": len(exact_values), "sign_counts": signs,
        "minimum_delta": str(min(exact_values)), "maximum_delta": str(max(exact_values)),
        "canonical_rows_sha256": digest.hexdigest(), "interpretation": grid["interpretation"],
    }
    ensure(observed["grid"] == expected_grid, "Grid arithmetic or digest differs")

    pair_spec = protocol["critic_pair"]
    ensure(len(observed["critic_pair"]) == len(pair_spec["correlations"]) == 3, "Missing critic-pair cases")
    for source, row in zip(pair_spec["correlations"], observed["critic_pair"]):
        expected = {"id": source["id"], **pair_enumeration(pair_spec["marginal_detection_given_flaw"], source["rho"])}
        ensure(row == expected, "Critic-pair enumeration differs")

    cash_spec = protocol["cash_illustrations"]
    cash_output = observed["cash_illustrations"]
    ensure(cash_output["scope"] == cash_spec["scope"], "Cash-illustration scope differs")
    ensure(len(cash_output["cases"]) == len(cash_spec["cases"]) == 2, "Missing success-path illustration")
    for source, row in zip(cash_spec["cases"], cash_output["cases"]):
        for key in ("id", "label", "flows"):
            ensure(row[key] == source[key], f"Changed cash illustration {key}")
        metrics = check_cash_prefixes(source["flows"])
        ensure(row["metrics"] == metrics, "Cash prefix calculation differs")
        ensure(read_rational(metrics["minimum_starting_cash"]) == read_rational(source["expected_minimum_starting_cash"]),
               "Declared minimum starting cash differs")
        ensure(read_rational(metrics["net_contribution"]) == read_rational(source["expected_net_contribution"]),
               "Declared success-path contribution differs")

    by_id = {row["id"]: read_rational(row["metrics"]["delta"]) for row in verified}
    ensure(by_id["grounded_challenge"] == by_id["matched_conventional"], "Identical conventional control does not tie")
    ensure(by_id["cheaper_conventional"] - by_id["grounded_challenge"] == 1, "Cheaper conventional control does not win by one")
    ensure(all(read_rational(row["metrics"]["delta"]) < 0 for row in verified[1:6]), "An adverse scenario disappeared")

    with (evidence / "results.csv").open(newline="", encoding="utf-8") as handle:
        csv_rows = list(csv.DictReader(handle))
    ensure(len(csv_rows) == len(verified), "CSV profile count differs")
    for exported, row in zip(csv_rows, verified):
        metric = row["metrics"]
        expected = {
            "id": row["id"], "label": row["label"], "kind": row["kind"], **row["parameters"],
            "delta_exact": metric["delta"], "delta_display": formatted(metric["delta"]),
            "unaddressed_flaw_exact": metric["unaddressed_flaw_probability"],
            "unaddressed_flaw_display": formatted(metric["unaddressed_flaw_probability"]),
            "decision_vs_incumbent": row["decision_vs_incumbent"],
        }
        ensure(exported == expected, f"CSV row differs: {row['id']}")
    tex = (evidence / "results_table.tex").read_text(encoding="utf-8")
    tex_rows = [line for line in tex.splitlines() if " & " in line and not line.startswith("Scenario or comparator")]
    ensure(len(tex_rows) == len(verified), "LaTeX profile count differs")
    visible = {"review": "Review", "incumbent": "Retain", "tie": "Tie", "bound_only": "Bound"}
    for line, row in zip(tex_rows, verified):
        columns = [part.strip().rstrip("\\").strip() for part in line.split("&")]
        expected = [row["label"], formatted(row["metrics"]["delta"]),
                    formatted(row["metrics"]["unaddressed_flaw_probability"]), visible[row["decision_vs_incumbent"]]]
        ensure(columns == expected, f"LaTeX row differs: {row['id']}")
    return {
        "status": "PASS", "named_profiles_checked": len(verified),
        "grid_points_checked": len(exact_values), "logical_branches_per_point": 8,
        "critic_pair_cases_checked": 3, "source_files_bound": len(source_names),
        "successful_cash_paths_checked": 2,
        "publication_formats_checked": ["JSON", "CSV", "LaTeX"],
        "scope": "Separate exact arithmetic implementation; no empirical model validation or external replication.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, help="Evidence directory; default is the sibling evidence directory")
    args = parser.parse_args()
    print(json.dumps(check_publication(evidence=args.evidence), indent=2))


if __name__ == "__main__":
    main()
