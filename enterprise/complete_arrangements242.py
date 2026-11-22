"""Research-only complete arrangement selection on frozen mixed buyer choices.

No financial authority, actual buyers, partner agreements, renewal receipts or
published runtime decision. An offered component is voluntarily complemented by
a buyer's independently available outside sources: not a complete provider claim.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from enterprise.pricing import probabilities, utilities
from enterprise.mixed_bundle240 import (
    PRICE_FACTORS, VALUE_FACTORS, _inputs, frozen_case, optimize_mixed_bundle,
)

SCHEMA = "agi-alpha/complete-arrangements242/v1"
STANDALONE_FACTORS = (.70, .95, 1.10)
STRESS_CASES = ("BASE", "PRICE_WAR", "NO_ARRIVAL", "NONPAYMENT")


def registered_cases():
    base = frozen_case()
    war = copy.deepcopy(base)
    war["quotes"][1]["rival"]["price"] = 10
    absent = copy.deepcopy(base)
    absent["regime"]["arrival_probability"] = 0
    failed = copy.deepcopy(base)
    failed["regime"].update(collection_probability=.30, refund_probability=.10)
    repeating = copy.deepcopy(base)
    repeating["publics"][1]["repeat_probability"] = .80
    return {
        "BASE": base, "PRICE_WAR": war, "NO_ARRIVAL": absent,
        "NONPAYMENT": failed, "REPEAT": repeating,
    }


def policy_names():
    names = ["NO_BID"]
    names += ["BUNDLE@" + str(f) for f in PRICE_FACTORS]
    for component in ("A", "B"):
        for factor in STANDALONE_FACTORS:
            names += ["STANDALONE_" + component + "@" + str(factor)]
            names += ["RECURRING_" + component + "@" + str(factor)]
    return names


def _one_component(public, quote, regime, model, factor, *, recurring):
    price = quote["price"] * factor
    # Same seven public-independent valuation factors across all registered arms.
    tau = public["anchor_usd"] * regime["temperature_ratio"]
    choice = sum(probabilities(utilities(
        public["anchor_usd"] * value, price, quote["rival"]["price"], public, regime
    ), model, tau)[0] for value in VALUE_FACTORS) / len(VALUE_FACTORS)
    exposure = (regime["arrival_probability"] *
                regime["qualification_probability"] *
                (1. - regime["supplier_outage_probability"]))
    first_win = choice * exposure
    collected = regime["collection_probability"] * (1. - regime["refund_probability"])
    net_collected = (collected * price - price * public["payment_fraction"] -
                     public["payment_fixed_usd"])
    # Even a failed/no-arrival paid attempt consumes its preregistered resources.
    cost_per_attempt = public["autonomous_cost_usd"] + regime["quote_cost_usd"]
    contribution = first_win * (net_collected - public["onboarding_cost_usd"]) - cost_per_attempt
    renewal_scores = []
    if recurring:
        # A renewal is never booked automatically. Reach requires a prior sale
        # and an independently authored repeat propensity. A new decision
        # can select the rival/self-service/decline instead. No opening cash
        # or forecasted revenue is permitted to finance another commitment.
        reach = first_win
        renewal_choice = choice * (1. - regime["supplier_outage_probability"])
        for cycle in (2, 3):
            reach *= public["repeat_probability"]
            increment = reach * (renewal_choice * net_collected - cost_per_attempt)
            renewal_scores.append({"cycle": cycle,
                                   "conditional_reach_probability": reach,
                                   "expected_increment": increment})
            contribution += increment
            reach *= renewal_choice
    return {"contribution": contribution, "price": price,
            "initial_choice_probability": choice,
            "initial_win_probability": first_win,
            "initial_attempt_cost": cost_per_attempt,
            "conditional_collected_net_receipt": net_collected,
            "renewal_scores": renewal_scores}


def evaluate(policy, case):
    pp, qq, rr, coordination = _inputs(
        case["publics"], case["quotes"], case["regime"],
        case["model"], case["coordination_cost_usd"])
    if policy == "NO_BID":
        return {"contribution": 0., "price": None, "action": "NO_BID",
                "native_financial_authority": []}
    try:
        kind, factor_str = policy.split("@")
        factor = float(factor_str)
    except (ValueError, AttributeError):
        raise ValueError("REGISTERED_POLICY_REQUIRED") from None
    if kind == "BUNDLE":
        if factor not in PRICE_FACTORS:
            raise ValueError("REGISTERED_BUNDLE_FACTOR_REQUIRED")
        # Parent's mixed outside-choice *attempt*, NOT its no-bid optimizer.
        result = optimize_mixed_bundle(pp, qq, rr, case["model"],
                                       coordination_cost_usd=coordination)
        row = next(row for row in result["candidate_curve"] if row["factor"] == factor)
        return {"contribution": row["expected_immediate_contribution_per_opportunity"],
                "price": row["total_price"], "action": kind,
                "native_financial_authority": []}
    if kind not in ("STANDALONE_A", "STANDALONE_B",
                    "RECURRING_A", "RECURRING_B") or factor not in STANDALONE_FACTORS:
        raise ValueError("REGISTERED_COMPONENT_POLICY_REQUIRED")
    which = 0 if kind.endswith("_A") else 1
    value = _one_component(pp[which], qq[which], rr, case["model"],
                           factor, recurring=kind.startswith("RECURRING"))
    return {**value, "action": kind, "native_financial_authority": []}


def compare():
    cases = registered_cases()
    # Both policy and offered price are frozen across the four adverse worlds.
    arms = []
    for policy in policy_names():
        rows = {name: evaluate(policy, case) for name, case in cases.items()}
        worst = min(rows[name]["contribution"] for name in STRESS_CASES)
        arms.append({"policy": policy, "worst_case_contribution": worst,
                     "case_scores": {name: rows[name]["contribution"] for name in cases},
                     "case_details": rows})
    # Tie goes to NO_BID; never optimize the price separately AFTER each shock.
    selected = max(arms, key=lambda arm: (
        arm["worst_case_contribution"], arm["policy"] == "NO_BID",
        -len(arm["policy"]), arm["policy"]))
    base_best = max(arms, key=lambda arm: (
        arm["case_scores"]["BASE"], arm["policy"] == "NO_BID",
        -len(arm["policy"]), arm["policy"]))
    original = frozen_case()
    src = Path(__file__)
    parent = src.with_name("mixed_bundle240.py")
    return {
        "schema": SCHEMA,
        "source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
        "parent_model_sha256": hashlib.sha256(parent.read_bytes()).hexdigest(),
        "frozen_parent_case_sha256": hashlib.sha256(json.dumps(
            original, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "registered_cases": list(cases),
        "registered_case_data": cases,
        "price_selected_before_adverse_case": True,
        "policy_comparisons": arms,
        "conditional_base_best": base_best["policy"],
        "robust_development_policy": selected["policy"],
        "robust_development_worst_case": selected["worst_case_contribution"],
        "native_financial_authority": [],
        "actual_paid_orders": 0,
        "actual_collected_revenue_usd": 0,
        "native_trailing_365_profit_usd": None,
        "actual_host_model_billing_usd": None,
        "observed_buyer_demand": None,
        "observed_partner_agreement": None,
        "claim": "EXPOSED_AUTHORED_GAME_ONLY_NOT_NEW_COMMERCIAL_CONFIRMATION",
        "decision": "HOLD_NO_NATIVE_ACTION",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.out.exists() or args.out.is_symlink():
        raise FileExistsError("CREATE_ONLY_RESEARCH_REPORT_REQUIRED")
    report = compare()
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"base": report["conditional_base_best"],
                      "robust": report["robust_development_policy"],
                      "decision": report["decision"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
