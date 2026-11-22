"""Research-only complete-bundle choice with independent mixed outside options.

Strong buyer counterfactual: buy an unbundled component from us, a rival or a
competent human, self-serve, or refuse EACH component. The all-ours *bundle*
is a separate alternative with one conservative shared approval friction.
No calibrated buyers, native finance, or live account authority are involved.
"""
from __future__ import annotations

import argparse
from itertools import product
import hashlib
import json
import math
from pathlib import Path

from enterprise.pricing import optimize_bundle, public_observation, utilities

MODEL = "agi-alpha/mixed-independent-bundle240/v1"
VALUE_FACTORS = (1.3, 1.7, 2.1, 2.5, 2.9, 3.3, 3.7)
PRICE_FACTORS = (.70, .80, .90, .95, 1., 1.05, 1.10)
REGIME_FIELDS = frozenset((
    "our_hours", "rival_hours", "self_complete_cost_ratio", "temperature_ratio",
    "arrival_probability", "qualification_probability",
    "supplier_outage_probability", "collection_probability",
    "refund_probability", "quote_cost_usd"
))


def _finite(value, *, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (positive and value <= 0):
        raise ValueError("FINITE_NONNEGATIVE_AUTHORED_INPUT_REQUIRED")
    return float(value)


def _inputs(publics, quotes, regime, model, coordination_cost_usd):
    if not isinstance(publics, (list, tuple)) or not isinstance(quotes, (list, tuple)) or len(publics) < 2 or len(publics) != len(quotes):
        raise ValueError("TWO_OR_MORE_MATCHED_COMPONENTS_REQUIRED")
    pp = [public_observation(p) for p in publics]
    qq = []
    for q in quotes:
        if not isinstance(q, dict) or set(q) != {"price", "rival"} or not isinstance(q["rival"], dict) or "price" not in q["rival"]:
            raise ValueError("EXPLICIT_COMPONENT_QUOTE_AND_RIVAL_REQUIRED")
        price = None if q["price"] is None else _finite(q["price"], positive=True)
        rival = _finite(q["rival"]["price"], positive=True)
        qq.append({"price": price, "rival": {"price": rival}})
    if not isinstance(regime, dict) or set(regime) != REGIME_FIELDS:
        raise ValueError("COMPLETE_DECLARED_BUYER_AND_COST_REGIME_REQUIRED")
    rr = {k: _finite(v, positive=(k == "temperature_ratio" and model == "logit")) for k, v in regime.items()}
    for k in ("arrival_probability", "qualification_probability", "supplier_outage_probability",
              "collection_probability", "refund_probability"):
        if rr[k] > 1:
            raise ValueError("BOUNDED_AUTHORED_PROBABILITY_REQUIRED")
    if model not in ("utility", "logit"):
        raise ValueError("SUPPORTED_BUYER_MODEL_REQUIRED")
    cc = _finite(coordination_cost_usd)
    return pp, qq, rr, cc


def mixed_choice_probability(rows, bundle_utility, model, temperature):
    """Buyer chooses the bundle or one of 5**n complete outside combinations.

    For logit, factorize the exact partition function. Nothing is enumerated in
    production, and the no-purchase option is present separately per component.
    """
    if not isinstance(rows, (list, tuple)) or len(rows) < 2 or any(
        not isinstance(r, (list, tuple)) or len(r) != 5 for r in rows
    ):
        raise ValueError("EXACT_FIVE_COMPONENT_OUTSIDE_CHOICES_REQUIRED")
    for row in rows:
        for x in row:
            if type(x) not in (int, float) or not math.isfinite(x):
                raise ValueError("FINITE_COMPONENT_UTILITIES_REQUIRED")
    if type(bundle_utility) not in (int, float) or not math.isfinite(bundle_utility):
        raise ValueError("FINITE_BUNDLE_UTILITY_REQUIRED")
    if model == "utility":
        # Favor the bundle on a true tie, matching the legacy five-choice tie.
        return float(bundle_utility >= sum(max(r) for r in rows))
    if model != "logit":
        raise ValueError("SUPPORTED_BUYER_MODEL_REQUIRED")
    tau = _finite(temperature, positive=True)
    outside_log_weight = 0.
    for row in rows:
        peak = max(row)
        outside_log_weight += peak / tau + math.log(sum(math.exp((x - peak) / tau) for x in row))
    difference = outside_log_weight - bundle_utility / tau
    if difference >= 0:
        v = math.exp(-difference)
        return v / (1. + v)
    return 1. / (1. + math.exp(difference))


def optimize_mixed_bundle(publics, quotes, regime, model, *,
                          strategic=True, coordination_cost_usd=3.):
    """Finite complete-outcome pricing *hypothesis*, not an executable native bid.

    All costs are authored scenario inputs. A zero-cost no-bid is evaluated
    before any hypothetical quote/production attempt; no model makes purchases.
    """
    pp, qq, rr, coordination = _inputs(publics, quotes, regime, model, coordination_cost_usd)
    if type(strategic) is not bool:
        raise ValueError("EXPLICIT_BOOLEAN_SEARCH_MODE_REQUIRED")
    if any(q["price"] is None for q in qq):
        return {"schema": MODEL, "decision": "NO_BID_UNAVAILABLE_COMPONENT",
                "price_factors": [], "total_price": None, "win_probability": 0.,
                "expected_immediate_contribution_per_opportunity": 0.,
                "candidate_curve": [], "native_financial_authority": []}
    factors = PRICE_FACTORS if strategic else (.95,)
    curve = []
    for discount in factors:
        component_prices = [q["price"] * discount for q in qq]
        total = sum(component_prices)
        conditional_purchase_probability = 0.
        for value_factor in VALUE_FACTORS:
            rows = [utilities(p["anchor_usd"] * value_factor, price,
                              q["rival"]["price"], p, rr)
                    for p, q, price in zip(pp, qq, component_prices)]
            # One approval: conservatively keep the largest component friction.
            bundle_utility = sum(row[0] for row in rows) + sum(p["friction_usd"] for p in pp) - max(p["friction_usd"] for p in pp)
            temperature = sum(p["anchor_usd"] for p in pp) * rr["temperature_ratio"]
            conditional_purchase_probability += mixed_choice_probability(
                rows, bundle_utility, model, temperature) / len(VALUE_FACTORS)
        exposure = rr["arrival_probability"] * rr["qualification_probability"] * (1. - rr["supplier_outage_probability"])
        win = conditional_purchase_probability * exposure
        collected_fraction = rr["collection_probability"] * (1. - rr["refund_probability"])
        # Component-specific percentage charges are not silently taken from
        # just the first component. Each declared fixed payment fee is charged.
        conditional_net_receipt = sum(
            collected_fraction * price - price * p["payment_fraction"] - p["payment_fixed_usd"]
            for p, price in zip(pp, component_prices)) - max(p["onboarding_cost_usd"] for p in pp)
        unconditional_attempt_cost = (sum(p["autonomous_cost_usd"] for p in pp) +
                                      coordination + len(pp) * rr["quote_cost_usd"])
        contribution = win * conditional_net_receipt - unconditional_attempt_cost
        curve.append({"factor": discount, "total_price": total,
                      "conditional_choice_probability_on_exposure": conditional_purchase_probability,
                      "win_probability": win, "public_exposure_probability": exposure,
                      "unconditional_attempt_acquisition_coordination_cost": unconditional_attempt_cost,
                      "conditional_net_receipt_if_sold": conditional_net_receipt,
                      "expected_immediate_contribution_per_opportunity": contribution})
    best = max(curve, key=lambda x: (x["expected_immediate_contribution_per_opportunity"], -x["total_price"]))
    if best["expected_immediate_contribution_per_opportunity"] <= 0:
        return {"schema": MODEL, "decision": "NO_BID_NONPOSITIVE_COMPLETE_CONTRIBUTION",
                "price_factors": [], "total_price": None, "win_probability": 0.,
                "expected_immediate_contribution_per_opportunity": 0.,
                "best_rejected_attempt": best, "candidate_curve": curve,
                "native_financial_authority": [],
                "scope": "Uncalibrated independent-component outside menu; zero-cost no-bid before commitment."}
    return {"schema": MODEL, "decision": "CONDITIONAL_AUTHORED_GAME_QUOTE_ONLY",
            **best, "price_factors": [best["factor"]] * len(pp),
            "candidate_curve": curve, "native_financial_authority": [],
            "scope": "Finite uncalibrated game; independent mixed outside providers and no-purchase, not real commerce."}


def frozen_case():
    p = {"anchor_usd": 100, "autonomous_cost_usd": 20,
         "onboarding_cost_usd": 1, "friction_usd": 5, "trust": 1,
         "rival_trust": .98, "urgency_value_hour": 0,
         "repeat_probability": 0, "payment_fraction": 0,
         "payment_fixed_usd": 0}
    return {
        "publics": [dict(p), dict(p)],
        "quotes": [{"price": 50, "rival": {"price": 5}},
                   {"price": 50, "rival": {"price": 500}}],
        "regime": {"our_hours": 0, "rival_hours": 0,
                   "self_complete_cost_ratio": .5, "temperature_ratio": .1,
                   "arrival_probability": 1, "qualification_probability": 1,
                   "supplier_outage_probability": 0, "collection_probability": 1,
                   "refund_probability": 0, "quote_cost_usd": 1},
        "model": "utility",
        "coordination_cost_usd": 3,
        "claim": "ILLUSTRATIVE_BUYER_MIXING_COUNTEREXAMPLE_NO_OBSERVED_DEMAND",
    }


def run_frozen():
    case = frozen_case()
    a = case["publics"]; q = case["quotes"]; r = case["regime"]
    old = optimize_bundle(a, q, r, case["model"],
                          coordination_cost_usd=case["coordination_cost_usd"])
    improved = optimize_mixed_bundle(a, q, r, case["model"],
                                    coordination_cost_usd=case["coordination_cost_usd"])
    old_win = old["expected_immediate_contribution_per_opportunity"] > 0
    new_abstain = improved["decision"] == "NO_BID_NONPOSITIVE_COMPLETE_CONTRIBUTION"
    return {
        "schema": MODEL, "frozen_input": case,
        "frozen_case_sha256": hashlib.sha256(json.dumps(case, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "legacy_homogeneous_quote": old["total_price"],
        "legacy_homogeneous_win_probability": old["win_probability"],
        "legacy_homogeneous_modeled_contribution": old["expected_immediate_contribution_per_opportunity"],
        "mixed_best_rejected_attempt": improved["best_rejected_attempt"],
        "mixed_decision": improved["decision"],
        "buyer_choice_set_falsification": bool(old_win and new_abstain),
        "observed_external_customers": 0, "observed_paid_revenue_usd": 0,
        "native_profit_usd": None, "actual_complete_model_host_cost_usd": None,
        "native_financial_authority": [],
        "verdict": "MODEL_CONDITIONAL_ONLY_NO_DEPLOY",
        "scope": "Exposed fixed hypothetical values, not a demand estimate, paid outcome, new physical capability or profit"
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.out.exists() or args.out.is_symlink():
        raise FileExistsError("CREATE_ONLY_PUBLIC_RESEARCH_RECEIPT_REQUIRED")
    report = run_frozen()
    if not report["buyer_choice_set_falsification"]:
        raise ValueError("PREREGISTERED_FALSIFICATION_NOT_OBSERVED")
    args.out.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"falsification": report["buyer_choice_set_falsification"],
                      "legacy_quote": report["legacy_homogeneous_quote"],
                      "mixed_decision": report["mixed_decision"],
                      "observed_paid_revenue_usd": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
