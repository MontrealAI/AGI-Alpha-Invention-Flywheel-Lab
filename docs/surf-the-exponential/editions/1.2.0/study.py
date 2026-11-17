#!/usr/bin/env python3
"""Exact authored arithmetic for one prespecified material-defect proposition.

F means that exact target is true, D alleges it, and A accepts that same claim.
Mixed true/false batches and adaptive target choice are outside the model.
Payoffs are held fixed within truth classes for the adjudicated/accept-all
comparison. This is no empirical model or market experiment.

Run from any directory: python3 study.py [--output /absolute/output/directory]
The separate check_study.py does not import this module or use its formula.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import itertools
import json
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parent
KEYS = frozenset({"pi", "d", "a", "f", "b", "G", "H", "K"})
PROBABILITIES = ("pi", "d", "a", "f", "b")
SOURCE_FILES = ("protocol.json", "study.py", "check_study.py", "test_study.py")
CSV_FIELDS = (
    "id", "label", "kind", "pi", "d", "a", "f", "b", "G", "H", "K",
    "delta_exact", "delta_display", "unaddressed_flaw_exact",
    "unaddressed_flaw_display", "decision_vs_incumbent",
)


def rational(value: object) -> Fraction:
    """Reject floating point and booleans instead of silently rounding inputs."""
    if isinstance(value, bool) or not isinstance(value, (str, int, Fraction)):
        raise ValueError("Use a rational string or integer, not a float or boolean")
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("Invalid finite rational") from exc


def validate(parameters: dict) -> dict[str, Fraction]:
    if set(parameters) != KEYS:
        raise ValueError("Parameter names must be exactly pi,d,a,f,b,G,H,K")
    p = {key: rational(value) for key, value in parameters.items()}
    if any(not 0 <= p[key] <= 1 for key in PROBABILITIES):
        raise ValueError("Every probability must lie in [0,1]")
    if p["H"] < 0 or p["K"] < 0:
        raise ValueError("H and K must be nonnegative")
    return p


def evaluate(parameters: dict) -> dict[str, str]:
    p = validate(parameters)
    true_accept = p["pi"] * p["d"] * p["a"]
    false_accept = (1 - p["pi"]) * p["f"] * p["b"]
    benefit = true_accept * p["G"]
    harm = false_accept * p["H"]
    delta = benefit - harm - p["K"]
    return {
        "true_accept_probability": str(true_accept),
        "false_accept_probability": str(false_accept),
        "unaddressed_flaw_probability": str(p["pi"] * (1 - p["d"] * p["a"])),
        "benefit_contribution": str(benefit),
        "harm_contribution": str(harm),
        "review_cost": str(p["K"]),
        "delta": str(delta),
        "value_with_stop": str(max(Fraction(0), delta)),
    }


def decimal4(value: str) -> str:
    q = rational(value)
    with localcontext() as context:
        context.prec = 50
        return format(Decimal(q.numerator) / Decimal(q.denominator), ".4f")


def decision(delta: str, kind: str) -> str:
    if kind == "unavailable_bound":
        return "bound_only"
    value = rational(delta)
    return "review" if value > 0 else "incumbent" if value < 0 else "tie"


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def grid_parameters(grid: dict):
    names = grid["axis_order"]
    if len(names) != len(set(names)) or set(names) != set(grid["axes"]):
        raise ValueError("Invalid grid axes")
    if set(names) & set(grid["fixed"]):
        raise ValueError("Grid axes and fixed parameters overlap")
    for values in itertools.product(*(grid["axes"][name] for name in names)):
        yield {**grid["fixed"], **dict(zip(names, values))}


def summarize_grid(grid: dict) -> dict:
    digest = hashlib.sha256()
    signs = {"positive": 0, "zero": 0, "negative": 0}
    values = []
    for index, parameters in enumerate(grid_parameters(grid)):
        metrics = evaluate(parameters)
        record = {"index": index, "parameters": parameters, "metrics": metrics}
        digest.update(canonical(record) + b"\n")
        delta = rational(metrics["delta"])
        values.append(delta)
        signs["positive" if delta > 0 else "negative" if delta < 0 else "zero"] += 1
    if len(values) != grid["expected_count"]:
        raise ValueError("Grid does not match declared count")
    return {
        "count": len(values), "sign_counts": signs,
        "minimum_delta": str(min(values)), "maximum_delta": str(max(values)),
        "canonical_rows_sha256": digest.hexdigest(),
        "interpretation": grid["interpretation"],
    }


def critic_pair(marginal: str, rho: str) -> dict[str, str]:
    q, r = rational(marginal), rational(rho)
    if not 0 < q < 1:
        raise ValueError("Correlation requires a nondegenerate marginal in (0,1)")
    joint = q * q + r * q * (1 - q)
    if not max(Fraction(0), 2 * q - 1) <= joint <= q:
        raise ValueError("Correlation does not define a feasible Bernoulli pair")
    return {
        "marginal_detection": str(q), "rho": str(r),
        "both_detect": str(joint), "at_least_one_detects": str(2 * q - joint),
        "neither_detects": str(1 - 2 * q + joint),
        "union_lower_bound": str(q), "union_upper_bound": str(min(Fraction(1), 2 * q)),
    }


def successful_cash_path(flows: list) -> dict:
    """Arithmetic of a supplied successful path, not an account or risk model."""
    values = [rational(value) for value in flows]
    if not values:
        raise ValueError("A cash illustration requires an explicit nonempty path")
    cumulative = []
    total = Fraction(0)
    lowest = Fraction(0)
    for value in values:
        total += value
        lowest = min(lowest, total)
        cumulative.append(str(total))
    return {
        "cumulative_flows": cumulative,
        "total_inflows": str(sum((value for value in values if value > 0), Fraction(0))),
        "total_outflows": str(-sum((value for value in values if value < 0), Fraction(0))),
        "net_contribution": str(total),
        "minimum_starting_cash": str(-lowest),
    }


def csv_text(profiles: list[dict]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in profiles:
        metrics = row["metrics"]
        writer.writerow({
            "id": row["id"], "label": row["label"], "kind": row["kind"],
            **row["parameters"], "delta_exact": metrics["delta"],
            "delta_display": decimal4(metrics["delta"]),
            "unaddressed_flaw_exact": metrics["unaddressed_flaw_probability"],
            "unaddressed_flaw_display": decimal4(metrics["unaddressed_flaw_probability"]),
            "decision_vs_incumbent": row["decision_vs_incumbent"],
        })
    return stream.getvalue()


def latex_text(profiles: list[dict]) -> str:
    lines = [
        "% Generated by study.py; authored utility scenarios, not measured performance.",
        "% F is one prespecified material-defect proposition; D alleges that same target.",
        "% P(F and not A) is a true target without accepted challenge, not post-repair error.",
        r"\begin{tabular}{@{}p{0.49\linewidth}rrl@{}}",
        r"\toprule",
        r"Scenario or comparator & $\Delta U$ & $P(F\cap\neg A)$ & Decision \\",
        r"\midrule",
    ]
    labels = {"review": "Review", "incumbent": "Retain", "tie": "Tie", "bound_only": "Bound"}
    for index, row in enumerate(profiles):
        if index == 6:
            lines.append(r"\midrule")
        metric = row["metrics"]
        lines.append(
            f'{row["label"]} & {decimal4(metric["delta"])} & '
            f'{decimal4(metric["unaddressed_flaw_probability"])} & '
            f'{labels[row["decision_vs_incumbent"]]} \\\\'
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    return "\n".join(lines)


def generate(root: Path = ROOT, output: Path | None = None) -> dict:
    protocol_bytes = (root / "protocol.json").read_bytes()
    protocol = json.loads(protocol_bytes)
    profiles = []
    identifiers = set()
    for supplied in protocol["scenarios"] + protocol["controls"]:
        if supplied["id"] in identifiers:
            raise ValueError("Duplicate profile identifier")
        identifiers.add(supplied["id"])
        metrics = evaluate(supplied["parameters"])
        if rational(metrics["delta"]) != rational(supplied["expected_delta"]):
            raise ValueError(f'Declared arithmetic does not match: {supplied["id"]}')
        profiles.append({
            key: supplied[key] for key in ("id", "label", "kind", "parameters")
        } | {"metrics": metrics, "decision_vs_incumbent": decision(metrics["delta"], supplied["kind"])})
    pair = protocol["critic_pair"]
    cash_spec = protocol["cash_illustrations"]
    cash_cases = []
    for item in cash_spec["cases"]:
        metrics = successful_cash_path(item["flows"])
        if (metrics["minimum_starting_cash"] != str(rational(item["expected_minimum_starting_cash"]))
                or metrics["net_contribution"] != str(rational(item["expected_net_contribution"]))):
            raise ValueError(f'Declared cash illustration does not match: {item["id"]}')
        cash_cases.append({key: item[key] for key in ("id", "label", "flows")} | {"metrics": metrics})
    results = {
        "schema": protocol["schema"], "evidence_status": protocol["evidence_status"],
        "units": protocol["units"],
        "event_scope": protocol["events"],
        "source_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in SOURCE_FILES},
        "profile_count": len(profiles), "profiles": profiles,
        "grid": summarize_grid(protocol["grid"]),
        "critic_pair": [{"id": item["id"], **critic_pair(pair["marginal_detection_given_flaw"], item["rho"])}
                        for item in pair["correlations"]],
        "cash_illustrations": {"scope": cash_spec["scope"], "cases": cash_cases},
        "claims_supported": [
            "The supplied utility identity has the reported exact values.",
            "The authored examples include five adverse scenarios, a conventional tie and a cheaper conventional winner.",
            "Critic dependence can change coverage under specified joint distributions.",
            "Two supplied successful cash paths require starting cash 90 and 50 while retaining net contribution 30.",
        ],
        "claims_not_supported": [
            "Measured model accuracy or superiority", "Whole-artifact or mixed-batch criticism coverage",
            "Empirical discovery or market invention", "Cash adequacy under failure or unobserved consent",
            "Real demand, revenue or profit", "General self-improvement or exponential growth",
        ],
    }
    if (root / "protocol.json").read_bytes() != protocol_bytes:
        raise RuntimeError("Protocol changed during generation")
    destination = output if output is not None else root / "evidence"
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    (destination / "results.csv").write_text(csv_text(profiles), encoding="utf-8")
    (destination / "results_table.tex").write_text(latex_text(profiles), encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Output directory; default is the sibling evidence directory")
    args = parser.parse_args()
    result = generate(output=args.output)
    print(json.dumps({"profiles": result["profile_count"], "grid": result["grid"],
                      "critic_pair_cases": len(result["critic_pair"]),
                      "successful_cash_paths": len(result["cash_illustrations"]["cases"])}, indent=2))


if __name__ == "__main__":
    main()
