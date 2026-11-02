"""Finite symbolic participation/cash screen; no invented prices or collection.

None denotes an unobserved economic input. Fully specified authored examples
remain conditional scenarios, never native operations or evidence of demand.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

OPTIONS = ("non_entry", "public_complete_outcome_self_service", "full_measurement", "internal_human_specialist_same_algorithm",
           "source_bound_analysis_offer", "separately_qualified_prospective_study")
CAPITAL_CASES = (0, 100_000, 1_000_000_000)
COMPRESSION_MONTHS = (3, 6, 12, 18, 24)
PRIMARY_ALLOCATION_METHOD = "probability_of_hit"
PRIOR_ART = (
    {"name": "Rubbi et al. 2026, Many Needles in a Haystack",
     "url": "https://proceedings.mlr.press/v306/rubbi26a.html",
     "scope": "Threshold-oriented probability-of-hit allocation; credited primary acquisition, with a declared reference-quantile adaptation."},
    {"name": "Qin et al. 2025, NAIAD",
     "url": "https://proceedings.mlr.press/v267/qin25g.html",
     "scope": "Existing single-effect-informed combinatorial perturbation prediction and adaptive recommendation; full framework is not reproduced here."},
    {"name": "Tosh et al. 2025, BATCHIE",
     "url": "https://www.nature.com/articles/s41467-024-55287-7",
     "scope": "Existing complete adaptive experimental arrangement demonstrated with prospective drug-combination measurements; different endpoint from this replay."},
)
PROVIDER_COSTS = ("research_and_failed_attempt_cost", "setup_cost", "compute_and_inference_cost",
    "review_and_qualification_cost", "support_and_remedy_cost", "acquisition_cost", "channel_cost",
    "license_cost", "depreciation_cost", "financing_fee_and_interest_cost", "expected_default_loss", "tax_expense")
CASH_INPUTS = ("setup_cash", "initial_financing_fee_cash", "committed_refund_reserve",
    "customer_deposit_received", "supplier_deposit_cash", "fulfillment_cash", "acquisition_cash",
    "collateral_reserve", "warranty_reserve", "accepted_balance_collection", "maintenance_and_remedy_cash",
    "tax_cash", "principal_repayment_cash", "interest_repayment_cash")
ECONOMIC_INPUTS = set(PROVIDER_COSTS) | set(CASH_INPUTS) | {
    "analysis_price", "minimum_operator_profit", "buyer_analysis_value", "buyer_analysis_loss",
    "buyer_analysis_attention_and_switching_cost", "buyer_best_outside_utility",
    "human_same_algorithm_full_cost", "supplier_payment", "supplier_complete_incremental_cost",
    "supplier_outside_surplus", "investor_discounted_distribution", "investor_required_return",
    "full_measurement_value", "full_measurement_total_cost", "full_measurement_residual_loss",
    "public_outcome_value", "public_retrieval_cost", "public_interpretation_cost", "public_verification_cost",
    "internal_analysis_value", "internal_analysis_residual_loss",
    "study_value", "study_total_cost", "study_residual_loss", "equity_fraction_given_to_investor",
} | {f"rival_complete_offer_price_at_{month}_months" for month in COMPRESSION_MONTHS}


def scalar(value):
    if value is None:
        return None
    if type(value) not in {int, float} or not math.isfinite(value):
        raise ValueError("FINITE_SCENARIO_AMOUNT_OR_UNKNOWN_REQUIRED")
    return value


def total(values):
    return None if any(value is None for value in values) else math.fsum(values)


def difference(left, right):
    return None if left is None or right is None else left - right


def inequality(name, expression, left, right):
    state = "HOLD" if left is None or right is None else ("PASS" if left >= right else "REFUSE")
    return {"name": name, "expression": expression, "left": left, "relation": ">=", "right": right, "status": state}


def gate(name, value):
    if value not in (True, False, None) or type(value) not in {bool, type(None)}:
        raise ValueError("BOOLEAN_OR_UNKNOWN_GATE_REQUIRED")
    return {"name": name, "status": "HOLD" if value is None else "PASS" if value else "REFUSE", "observed_or_assumed": value}


def conjunction(constraints):
    states = [row["status"] for row in constraints]
    return "REFUSE" if "REFUSE" in states else "HOLD" if "HOLD" in states else "CONDITIONAL_SCENARIO_ONLY"


def cash_schedule(parameters, capital, deposit_terms):
    """Four finite events. Future balance collections cannot fund event0/1."""
    get = lambda name: parameters.get(name)
    setup = total([get("setup_cash"), get("initial_financing_fee_cash")])
    customer_deposit = get("customer_deposit_received") if deposit_terms else 0.0
    costs_before_acceptance = total([get("supplier_deposit_cash"), get("fulfillment_cash"), get("acquisition_cash")])
    existing_protected = total([get("committed_refund_reserve"), get("collateral_reserve"), get("warranty_reserve")])
    protected = total([existing_protected, customer_deposit])
    after_setup = difference(capital, setup)
    before_acceptance = difference(total([after_setup, customer_deposit]), costs_before_acceptance)
    after_acceptance = total([before_acceptance, get("accepted_balance_collection")])
    drain_cost = total([get("maintenance_and_remedy_cash"), get("tax_cash"),
                       get("principal_repayment_cash"), get("interest_repayment_cash")])
    after_obligations = difference(after_acceptance, drain_cost)
    rows = [
        {"event": "t0_setup_after_conditional_funding_receipt", "cash": after_setup,
         "protected": existing_protected},
        {"event": "t1_committed_work_before_acceptance", "cash": before_acceptance, "protected": protected},
        {"event": "t2_accepted_report_balance_collection", "cash": after_acceptance,
         "protected": existing_protected},
        {"event": "t3_settle_maintenance_tax_and_financing", "cash": after_obligations,
         "protected": existing_protected},
    ]
    checks = [inequality(row["event"], "actual cash at this event >= still-protected obligations",
                         row["cash"], row["protected"]) for row in rows]
    checks.append(inequality("collections_bounded_by_accepted_contract",
        "analysis contract price >= received deposit + accepted balance collection",
        get("analysis_price"), total([customer_deposit, get("accepted_balance_collection")])))
    margins = [difference(row["cash"], row["protected"]) for row in rows]
    shortfall = None if any(x is None for x in margins) else max(0.0, -min(margins))
    return {"capital_if_actually_received": capital, "capital_is_secured_or_received": False,
        "terms": "refundable_deposit_then_acceptance" if deposit_terms else "payment_after_acceptance",
        "events": rows, "constraints": checks, "maximum_cash_shortfall": shortfall,
        "funding_dates_requiring_evidence": [row["event"] for row, check in zip(rows, checks[:4]) if check["status"] != "PASS"],
        "reserve_release_rule": "Existing refund, collateral and warranty protection stays through all events; no release milestone is evidenced. Customer-deposit liability releases only at the explicitly conditional accepted-report event.",
        "status": conjunction(checks), "native_account_or_transition_executed": False}


def evaluate(parameters=None, *, research_artifact_accepted=None, allocation_boundary_met=None,
             prospective_study_qualified=False, supplier_terms_accepted=None, financing_terms_accepted=None):
    supplied = {} if parameters is None else dict(parameters)
    if set(supplied) - ECONOMIC_INPUTS:
        raise ValueError("UNREGISTERED_ECONOMIC_SCENARIO_INPUT")
    parameters = {name: scalar(supplied.get(name)) for name in sorted(ECONOMIC_INPUTS)}
    for name, value in parameters.items():
        if value is not None and name != "buyer_best_outside_utility" and value < 0:
            raise ValueError("NEGATIVE_COST_PRICE_OR_VALUE_OUTSIDE_DECLARED_SCENARIO:" + name)
    dilution = parameters["equity_fraction_given_to_investor"]
    if dilution is not None and dilution > 1:
        raise ValueError("EQUITY_FRACTION_OUTSIDE_ZERO_ONE")
    get = parameters.get
    complete_provider_cost = total([get(name) for name in PROVIDER_COSTS])
    operator_minimum_price = total([complete_provider_cost, get("minimum_operator_profit")])
    buyer_maximum_price = difference(get("buyer_analysis_value"), total([
        get("buyer_analysis_loss"), get("buyer_analysis_attention_and_switching_cost"), get("buyer_best_outside_utility")]))
    utility = {
        "non_entry": 0.0,
        "public_complete_outcome_self_service": difference(get("public_outcome_value"), total([
            get("public_retrieval_cost"), get("public_interpretation_cost"), get("public_verification_cost")])),
        "full_measurement": difference(get("full_measurement_value"), total([get("full_measurement_total_cost"), get("full_measurement_residual_loss")])),
        "internal_human_specialist_same_algorithm": difference(get("internal_analysis_value"), total([get("human_same_algorithm_full_cost"), get("internal_analysis_residual_loss")])),
        "source_bound_analysis_offer": difference(get("buyer_analysis_value"), total([get("analysis_price"), get("buyer_analysis_loss"), get("buyer_analysis_attention_and_switching_cost")])),
        "separately_qualified_prospective_study": difference(get("study_value"), total([get("study_total_cost"), get("study_residual_loss")])),
    }
    lab_choices = {}
    for option in OPTIONS:
        if option == "non_entry":
            lab_choices[option] = {"status": "AVAILABLE_NO_NEW_COMMITMENT", "incremental_utility_reference": 0,
                                   "sunk_research_cost_is_not_erased": True}
            continue
        quality = research_artifact_accepted if option in {"source_bound_analysis_offer", "public_complete_outcome_self_service"} else (
            prospective_study_qualified if option == "separately_qualified_prospective_study" else None)
        checks = [gate("scope_matched_acceptance", quality)]
        for rival in OPTIONS:
            if rival == option or (rival == "separately_qualified_prospective_study" and prospective_study_qualified is False):
                continue
            checks.append(inequality("lab_choice_over_" + rival, "laboratory net utility of chosen option >= eligible outside option utility",
                                     utility[option], utility[rival]))
        lab_choices[option] = {"net_utility": utility[option], "constraints": checks, "status": conjunction(checks)}
    joint = [gate("accepted_source_bound_research_artifact", research_artifact_accepted),
        inequality("operator_complete_cost_profit", "analysis price >= complete costs + explicit taxes + requested operator surplus",
                   get("analysis_price"), operator_minimum_price),
        inequality("buyer_voluntary_price_ceiling", "buyer value - miss loss - switching/attention - best outside utility >= analysis price",
                   buyer_maximum_price, get("analysis_price")),
        inequality("equal_quality_specialist_outside_option", "competent human complete same-algorithm cost >= offer price + buyer switching/attention",
                   get("human_same_algorithm_full_cost"), total([get("analysis_price"), get("buyer_analysis_attention_and_switching_cost")])),
        inequality("supplier_voluntary_participation", "supplier payment >= complete incremental supplier cost + supplier outside surplus",
                   get("supplier_payment"), total([get("supplier_complete_incremental_cost"), get("supplier_outside_surplus")])),
        gate("declared_supplier_terms_and_obligations", supplier_terms_accepted)]
    # The named outside options constrain entry directly. A supplied aggregate
    # outside-utility assumption cannot override a better explicit public option.
    joint.extend(lab_choices["source_bound_analysis_offer"]["constraints"])
    capitals = []
    for capital in CAPITAL_CASES:
        finance = [gate("voluntary_funding_dilution_control_and_downside_terms", financing_terms_accepted),
            inequality("investor_participation", "discounted investor distributions >= supplied principal + required investor return",
                       get("investor_discounted_distribution"), total([capital, get("investor_required_return")]))]
        for deposits in (False, True):
            schedule = cash_schedule(parameters, capital, deposits)
            capitals.append({"capital_hypothesis_usd": capital, "financing_constraints": finance,
                "cash": schedule, "joint_entry_status": conjunction(joint + finance + schedule["constraints"])})
    compression = [inequality(f"same_quality_rival_price_at_{month}_months",
        "rival complete equivalent-offer price >= focal offer price + customer switching cost",
        get(f"rival_complete_offer_price_at_{month}_months"), total([get("analysis_price"), get("buyer_analysis_attention_and_switching_cost")]))
        | {"months": month, "evidence_role": "unmeasured timing sensitivity; 6–18 months is a user hypothesis"}
        for month in COMPRESSION_MONTHS]
    return {"schema": "next072/finite-symbolic-economic-screen/v1", "participants": {
        "research_lab": "Chooses measured scientific decision value net complete outlay, attention and missed-target loss.",
        "human_specialist": "100% human attention plus genuine conventional software; same data, algorithm and retained means allowed.",
        "assay_supplier": "Accepts only funded, scope-defined work covering its complete incremental costs and outside surplus.",
        "analysis_operator": "Seeks complete-cost after-tax profit while preserving current and future obligations.",
        "investor_lender": "Seeks acceptable discounted distributions, downside and dilution/control terms.",
        "same_algorithm_rival": "May adopt the identical tool; no durable method exclusivity is assumed."},
        "information": "Published inputs and source-bound replay results are common information; monetary values, attention, assay-specific costs and private preferences are unobserved.",
        "solution_concept": "Finite outside-option best-response inequalities and joint voluntary/cash feasibility; unknown inputs yield HOLD. No calibrated equilibrium or optimum is claimed.",
        "laboratory_choice_menu": lab_choices, "complete_provider_cost_after_explicit_tax": complete_provider_cost,
        "break_even_offer_price": operator_minimum_price, "buyer_maximum_offer_price": buyer_maximum_price,
        "joint_participation_constraints": joint, "capital_and_terms_comparisons": capitals,
        "rival_cost_gap_compression_sensitivity": compression,
        "allocation_boundary_gate": gate("experimental_allocation_boundary", allocation_boundary_met),
        "report_and_allocation_service_are_separate": {
            "negative_analysis_report_technical_gate": gate("truthful_source_bound_report", research_artifact_accepted),
            "experimental_allocation_service_status": conjunction([
                gate("research_artifact", research_artifact_accepted), gate("budget_crossing", allocation_boundary_met),
                gate("fresh_prospective_study_qualification", prospective_study_qualified)]),
            "negative_boundary_result_cannot_qualify_budget_crossing_service": True,
            "analysis_report_has_observed_willing_buyer": False},
        "economic_evidence_status": conjunction(joint), "scope_matched_financial_admission": "NOT_ESTABLISHED",
        "capital_received": 0, "orders_executed": 0, "native_collections": 0,
        "actual_research_and_inference_cost_usd": None,
        "unknown_inputs": sorted(name for name, value in parameters.items() if value is None),
        "input_values_are": "Unmeasured unless separately sourced; supplied numbers are conditional scenario inputs, never observed demand.",
        "retained_obligations": "Principal and restricted reserves are not expenses; future collections are unavailable before acceptance. Existing obligations and sunk research are retained.",
        "full_profile_counts_are_not_assay_money_costs": True,
        "all_retrospective_outcomes_are_already_public": True,
        "actual_new_assays_avoided_by_this_replay": 0,
        "registered_primary_allocation_method": PRIMARY_ALLOCATION_METHOD,
        "generic_adaptive_platform_missing_means_claim": "SOURCE_REJECTED",
        "generic_platform_rejection_is_independent_of_allocation_outcome": True,
        "current_primary_prior_art": list(PRIOR_ART),
        "source_bound_question": "Does this fixed six-feature single-profile representation identify large measured residuals under the credited primary method and complete reference budget?",
        "full_naiad_or_batchie_framework_superiority": "NOT_TESTED",
        "next_investment_scope": "A failed boundary rejects this allocation contract. A passed boundary alone does not establish feature value: inspect the fixed no-feature, static, simpler and hash controls. Any resulting fresh-study proposal still needs independent domain-specific truth, complete cost, buyer acceptance and funding evidence.",
        "profit_milestone": {"completed_trailing_365_day_profit_usd": None, "usd_3_billion_established": False}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path)
    parser.add_argument("--verification", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    parameters = json.loads(args.scenario.read_text()) if args.scenario else None
    accepted = boundary = None
    verification_identity = None
    if args.verification:
        verification = json.loads(args.verification.read_text())
        if verification.get("schema") != "next072/independent-verification/v1":
            raise ValueError("INDEPENDENT_RESEARCH_VERDICT_REQUIRED")
        accepted = verification.get("accepted") is True
        audit = verification.get("result_audit", {})
        if accepted and (audit.get("primary_policy") != PRIMARY_ALLOCATION_METHOD or audit.get("policies_verified") != 42):
            raise ValueError("EXACT_PRIMARY_AND_COMPLETE_REGISTERED_CONTROLS_REQUIRED")
        boundary = verification.get("result_audit", {}).get("proposed_boundary_met") if accepted else None
        verification_identity = {"sha256": hashlib.sha256(args.verification.read_bytes()).hexdigest(),
            "accepted": accepted, "primary_policy": audit.get("primary_policy"), "policies_verified": audit.get("policies_verified")}
    report = evaluate(parameters, research_artifact_accepted=accepted, allocation_boundary_met=boundary)
    report["independent_verification_binding"] = verification_identity
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"economic_evidence_status": report["economic_evidence_status"], "financial_admission": "NOT_ESTABLISHED",
                      "unknown_inputs": len(report["unknown_inputs"]), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
