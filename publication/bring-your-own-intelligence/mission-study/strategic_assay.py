# SPDX-License-Identifier: Apache-2.0
"""Check frozen assisted strategic graphs against separate prose review and exact oracles."""

from argparse import ArgumentParser
from fractions import Fraction
from hashlib import sha256
import json
from math import gcd
from pathlib import Path
import sys
from time import perf_counter


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PRIOR = REPO / "publication/outcome-driven/strategic"
ORDER = PRIOR / "order-diagnostic"
ASSISTED_SHA256 = "439cfa0c52abbe27ce49d3ab26cefdbc835b4fe9f0f0e8eeb2f6cb536842dcec"
sys.path[:0] = [str(ORDER), str(PRIOR)]
from formalize import COMPATIBLE, FIELDS, Game, compile_reviewed, numeric_missing, ordinary_interpretation
from grade import check_certificate, exact
from reference import reference as enumerate_order_reference
from witness import assess as graph_proof


def digest(data):
    return sha256(data).hexdigest()


def exact_json(path, expected_hash):
    data = path.read_bytes()
    if digest(data) != expected_hash:
        raise ValueError("Frozen bytes changed: " + path.name)
    return json.loads(data)


def roster(items):
    indexed = {record["id"]: record for record in items}
    if len(items) != len(indexed):
        raise ValueError("Duplicate case identity.")
    return indexed


def compatible_units(case):
    """Preserve exact choices and bounds through a positive integral change of units."""
    def check_input(record):
        Game.from_document({key: record[key] for key in ("id", "payoffs", "accuracy", "fee")})

    try:
        check_input(case)
        return case, 1
    except ValueError:
        common_unit = gcd(case["fee"], *(value for row in case["payoffs"] for value in row))
        if common_unit <= 1:
            raise
        scaled = {**case, "payoffs": [[value // common_unit for value in row] for row in case["payoffs"]],
                  "fee": case["fee"] // common_unit}
        check_input(scaled)
        return scaled, common_unit


def structural_disposition(semantic, approved):
    mismatches = [key for key in FIELDS if semantic[key] != approved[key]]
    if mismatches:
        return {"disposition": "interpretation_disagrees", "fields": mismatches}
    return {"disposition": "withhold", "issues": {key: val for key, val in semantic.items() if val != COMPATIBLE[key]}}


def check_case(case, approved, authored):
    intended = {key: approved[key] for key in FIELDS}
    citations = authored["evidence"]
    matched_citations = bool(citations) and all(phrase in case["brief"] for phrase in citations.values())
    graph = authored["witness"]
    timing = graph_proof(graph)
    reference = enumerate_order_reference(graph)
    reviewed = {"timing": timing["timing"], "units": authored["units"], "missing": numeric_missing(case)}
    numerical = None
    ordinary_case = case
    if intended == COMPATIBLE:
        ordinary_case, unit = compatible_units(case)
        independent_original = exact(case)
        independent_scaled = exact(ordinary_case)
        direct_outcome = compile_reviewed(ordinary_case, intended, intended)
        check_certificate(direct_outcome, independent_scaled, ordinary_case)
        result = compile_reviewed(ordinary_case, reviewed, intended)
        if reviewed == intended:
            check_certificate(result, independent_scaled, ordinary_case)
            source_bounds = {key: str(Fraction(value) * unit) for key, value in result["exact_bounds"].items()}
            original_buy = Fraction(independent_original["purchase_before_fee"]) - case["fee"]
            if (Fraction(source_bounds["BUY"]) != original_buy or source_bounds["SKIP"] != independent_original["skip"]
                    or result["decision"] != independent_original["choice"]):
                raise ArithmeticError("The exact re-expression changed an original-unit value or decision.")
            numerical = {"mathematical_reference_original_units": independent_original, "decision": result["decision"],
                         "exact_bounds_original_units": source_bounds, "exact_certificate_unit_multiplier": unit,
                         "certificate_solver_inputs": result["solver_input"], "certificates": result["certificates"]}
    else:
        result = structural_disposition(reviewed, intended)
        direct_outcome = structural_disposition(intended, intended)
    try:
        ordinary = ordinary_interpretation(ordinary_case)
        plain_outcome = (compile_reviewed(ordinary_case, ordinary, intended) if intended == COMPATIBLE
                         else structural_disposition(ordinary, intended))
    except ValueError as error:
        ordinary = None
        plain_outcome = {"disposition": "technical_refusal", "reason": str(error)}
    required_issues = {key: intended[key] for key in intended if intended[key] != COMPATIBLE[key]}
    accepted_scope = (bool(numerical) and numerical["decision"] == approved.get("decision") if intended == COMPATIBLE else (
        result["disposition"] == "withhold" and result["issues"] == required_issues
        and "solver_input" not in result and "exact_bounds" not in result
    ))
    return {
        "id": case["id"], "language": case["lang"], "source_citations_present": matched_citations,
        "complete_proof_agreement": timing == reference, "graph_proof": timing, "inferred": reviewed,
        "direct_independent_semantics": intended, "direct_assessor_purchase_advice": approved.get("decision"),
        "ordinary_rules_semantics": ordinary,
        "disposition": result["disposition"], "direct_disposition": direct_outcome["disposition"],
        "ordinary_rules_disposition": plain_outcome["disposition"],
        "ordinary_rules_refusal": plain_outcome.get("reason"), "withheld_issues": result.get("issues", {}),
        "false_solver_proposed": reviewed == COMPATIBLE and intended != COMPATIBLE,
        "numerical": numerical,
        "accepted": timing == reference and matched_citations and reviewed == intended and accepted_scope,
    }


def run_assessment():
    registration_path = HERE / "STRATEGIC-REGISTRATION.json"
    registration = json.loads(registration_path.read_bytes())
    adaptation_path = HERE / "STRATEGIC-ADAPTATION.json"
    adaptation = json.loads(adaptation_path.read_bytes())
    cases = exact_json(HERE / "STRATEGIC-INPUTS.json", registration["inputs_sha256"])
    labels = roster(exact_json(HERE / "STRATEGIC-REFERENCE.json", registration["independent_semantics_sha256"]))
    proposals = roster(exact_json(HERE / "STRATEGIC-PROPOSALS.json", ASSISTED_SHA256))
    if set(labels) != set(proposals) or set(proposals) != set(roster(cases)):
        raise ValueError("Strategic input, reference and proposal rosters differ.")
    started = perf_counter()
    results = [check_case(case, labels[case["id"]], proposals[case["id"]]) for case in cases]
    seconds = perf_counter() - started
    return {
        "schema": "frontier/assisted-strategic-witness-assessment-v1",
        "owner_ambition": registration["owner_ambition"],
        "original_owner_ambition": registration["original_owner_ambition"],
        "scope": "Independent author supplied previously withheld bilingual synthetic briefs and dispositions under shared administration. Included Codex authored the graph before labels were opened. The native retained graph proof and two exact arithmetic paths executed locally. No newly trained model or live member inference.",
        "verdict": "GO_SCOPED_ASSISTED_WITNESS" if all(item["accepted"] for item in results) else "NO_GO",
        "first_attempt": adaptation["initial_attempt"], "followup": adaptation["followup"],
        "assisted_graph_completed": sum(item["accepted"] for item in results),
        "direct_included_assessor_completed": sum(item["direct_disposition"] in {"certified_scoped", "withhold"} for item in results),
        "ordinary_rules_completed": sum(item["ordinary_rules_disposition"] in {"certified_scoped", "withhold"} for item in results),
        "denominator": len(results), "false_solver_proposals": sum(item["false_solver_proposed"] for item in results),
        "exact_certificates": sum(item["numerical"] is not None for item in results), "results": results,
        "binding": {
            "registration_sha256": digest(registration_path.read_bytes()),
            "adaptation_sha256": digest(adaptation_path.read_bytes()), "inputs_sha256": registration["inputs_sha256"],
            "reference_sha256": registration["independent_semantics_sha256"], "assisted_proposals_sha256": ASSISTED_SHA256,
            "assessor_sha256": digest(Path(__file__).read_bytes()),
            "order_checker_sha256": digest((ORDER / "witness.py").read_bytes()),
            "separate_order_reference_sha256": digest((ORDER / "reference.py").read_bytes()),
            "strategic_compiler_sha256": digest((PRIOR / "formalize.py").read_bytes()),
            "exact_solver_sha256": digest((REPO / "publication/evidence-bound/strategic/game.py").read_bytes()),
            "exact_reference_sha256": digest((REPO / "publication/evidence-bound/evaluation/strategic_reference.py").read_bytes()),
        },
        "costs": {"graph_authoring_wall_seconds_approx": 54,
                  "independent_case_author_and_direct_review_wall_seconds_approx": 41,
                  "verification_wall_seconds": seconds,
                  "provider_requests_during_evaluation": 0, "paid_requests": 0,
                  "hosted_assisted_token_cost_and_human_attention": None},
        "specialist_deployment": "NO_GO. No fresh learned parameters or general strategic-intelligence advantage.",
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_assessment()
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(result["verdict"], result["assisted_graph_completed"], result["denominator"])
    if result["verdict"] == "NO_GO":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
