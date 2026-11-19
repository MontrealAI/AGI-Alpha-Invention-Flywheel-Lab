"""Ω ALPHA — bounded economic-mechanism discovery and construction.

No model, market, buyer or chain access. Enumerates genuine *different* possible
contract arrangements inside a disclosed, narrow grammar; does not claim open-
ended invention. Uses exact rational arithmetic in AUTHORED synthetic worlds.

The only emitted Solidity target is the tested ordinary proof escrow. No token
movement, payment quote, wallet signing or production deployment occurs here.
"""
from __future__ import annotations

from fractions import Fraction
import argparse
import hashlib
import json
from pathlib import Path
import re

SCHEMA = "montreal.ai/mechanism-foundry/v1"
MODES = ("direct", "buyer_escrow", "independent_escrow")
FEES = (0, 25, 100, 200)
DAYS = (1, 3, 7)
MAX_CASES = 200
REQUIRED_CASE = {
    "id", "price", "value_if_accepted", "seller_cost", "success_ppm",
    "network_cost", "independent_check_cost", "operator_cost",
    "buyer_outside", "seller_outside", "time_limit_days",
}
ALLOWED_TOP = {
    "schema", "mission_id", "outcome", "evidence_cutoff", "enabler",
    "rights_confirmed", "currency", "development", "holdout",
    "comparison_options", "fixed_construction_cost",
}
CANONICAL_TOKEN = "0xA61a3B3a130a9c20768EEBF97E21515A6046a1fA"


class Refused(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Refused(message)


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_JSON_FIELD")
            result[key] = value
        return result

    def nonfinite(_):
        raise Refused("NONFINITE_JSON")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def integer(value, low=0, high=10**18):
    return type(value) is int and low <= value <= high


def validate_brief(brief):
    require(type(brief) is dict and set(brief) == ALLOWED_TOP, "EXACT_BRIEF_FIELDS")
    require(brief["schema"] == SCHEMA, "INVALID_SCHEMA")
    require(type(brief["mission_id"]) is str
            and re.fullmatch(r"[a-z][a-z0-9_-]{2,60}", brief["mission_id"]),
            "INVALID_MISSION_ID")
    require(type(brief["outcome"]) is str and len(brief["outcome"].strip()) >= 12
            and len(brief["outcome"]) <= 1000, "MISSING_MEANINGFUL_OUTCOME")
    require(type(brief["evidence_cutoff"]) is str
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", brief["evidence_cutoff"]),
            "INVALID_EVIDENCE_CUTOFF")
    require(type(brief["enabler"]) is dict and
            set(brief["enabler"]) == {"source", "claimed_change", "verified"},
            "INVALID_ENABLER")
    require(type(brief["enabler"]["source"]) is str
            and brief["enabler"]["source"].startswith("https://")
            and type(brief["enabler"]["claimed_change"]) is str
            and type(brief["enabler"]["verified"]) is bool,
            "INVALID_ENABLER_SOURCE")
    require(type(brief["rights_confirmed"]) is bool, "INVALID_RIGHTS")
    require(brief["currency"] == "SYNTHETIC_UNITS_NOT_MONEY", "NO_REAL_MONEY_INPUT")
    require(integer(brief["fixed_construction_cost"]), "INVALID_CONSTRUCTION_COST")
    require(type(brief["comparison_options"]) is list
            and {"no_entry", "direct", "free_existing_escrow"}.issubset(
                set(brief["comparison_options"]))
            and len(set(brief["comparison_options"])) == len(brief["comparison_options"])
            and set(brief["comparison_options"]) <=
            {"no_entry", "direct", "free_existing_escrow"},
            "STRONG_COMPARISONS_REQUIRED")
    for stage in ("development", "holdout"):
        cases = brief[stage]
        require(type(cases) is list and 1 <= len(cases) <= MAX_CASES,
                "EMPTY_OR_UNBOUNDED_" + stage.upper())
        ids = set()
        for case in cases:
            require(type(case) is dict and set(case) == REQUIRED_CASE,
                    "INVALID_CASE_FIELDS")
            label = case["id"]
            require(type(label) is str and re.fullmatch(r"[a-z0-9_-]{1,60}", label)
                    and label not in ids, "DUPLICATE_OR_INVALID_CASE_ID")
            ids.add(label)
            for key in REQUIRED_CASE - {"id"}:
                require(integer(case[key]), "INVALID_CASE_NUMBER_" + key)
            require(0 <= case["success_ppm"] <= 1_000_000,
                    "SUCCESS_OUT_OF_RANGE")
            require(1 <= case["time_limit_days"] <= 365,
                    "TIME_LIMIT_OUT_OF_RANGE")
            require(case["price"] > 0, "PRICE_REQUIRED")
            require(case["value_if_accepted"] >= case["price"],
                    "BUYER_VALUE_BELOW_PRICE")
    ids = {case["id"] for case in brief["development"]}
    require(not ids.intersection({case["id"] for case in brief["holdout"]}),
            "HOLDOUT_NOT_SEPARATE")
    require(len(canonical(brief)) <= 250_000, "BRIEF_TOO_LARGE")
    return brief


def candidates():
    # Grammar includes three materially different payment arrangements, with
    # conditional verification and post-expiry refund for escrow options.
    offer = [{"kind": "direct", "verifier": "none", "fee_bps": 0,
              "expiry_days": 0, "deployable": False}]
    for verifier in ("buyer", "independent"):
        for bps in FEES:
            for days in DAYS:
                offer.append({
                    "kind": verifier + "_escrow",
                    "verifier": verifier,
                    "fee_bps": bps, "expiry_days": days, "deployable": True,
                })
    return offer


def value(case, mechanism, fixed_cost_per_case=Fraction(0)):
    """A modeled buyer/seller game, with no synthetic buyer called 'real'.

    Rational participation takes outside options as given and is conservative:
    both buyer and seller must prefer the candidate.
    """
    p = Fraction(case["success_ppm"], 1_000_000)
    amount = Fraction(case["price"])
    val = Fraction(case["value_if_accepted"])
    cost = Fraction(case["seller_cost"])
    net = Fraction(case["network_cost"])
    operator = Fraction(case["operator_cost"])
    fee = Fraction(mechanism["fee_bps"], 10_000) * amount
    kind = mechanism["kind"]
    conditional = kind != "direct"
    check = Fraction(case["independent_check_cost"]) if kind == "independent_escrow" else 0
    # In this simple model all mechanisms use the same externally specified
    # acceptance probability; new quality is never silently assumed.
    # With conditional settlement the buyer pays only upon accepted work.
    if conditional:
        buyer = p * (val - amount) - net - check
        seller = p * (amount - fee) - cost
        owner = p * fee - operator - fixed_cost_per_case
    else:
        buyer = p * val - amount - net
        seller = amount - cost
        owner = -operator - fixed_cost_per_case

    delivery_possible = (
        not conditional or
        (mechanism["expiry_days"] <= case["time_limit_days"])
    )
    participates = delivery_possible and buyer >= case["buyer_outside"] \
        and seller >= case["seller_outside"] and buyer >= 0 and seller >= 0
    # Declined transaction: no revenue. Development costs already incurred,
    # but transaction-specific operator charges are not.
    if not participates:
        return {"accepted": False, "buyer": Fraction(0), "seller": Fraction(0),
                "owner": -fixed_cost_per_case, "reason": "DECLINED_OR_INFEASIBLE"}
    return {"accepted": True, "buyer": buyer, "seller": seller,
            "owner": owner, "reason": "MODELED_PARTICIPATION"}


def aggregate(cases, mechanism, construction_cost):
    fixed = Fraction(construction_cost, len(cases))
    results = [value(case, mechanism, fixed) for case in cases]
    return {
        "candidate": mechanism,
        "cases": len(results),
        "transactions": sum(int(v["accepted"]) for v in results),
        "owner_profit_exact": str(sum((v["owner"] for v in results), Fraction(0))),
        "buyer_utility_exact": str(sum((v["buyer"] for v in results), Fraction(0))),
        "seller_utility_exact": str(sum((v["seller"] for v in results), Fraction(0))),
        "all_cases_accept": all(v["accepted"] for v in results),
        "per_case": [{"id": c["id"], "accepted": v["accepted"],
                      "reason": v["reason"]} for c, v in zip(cases, results)],
        "source": "AUTHORED_SYNTHETIC_MODEL",
    }


def _fraction(value):
    return Fraction(value)


def ranking_key(record):
    return (_fraction(record["owner_profit_exact"]), record["transactions"],
            -record["candidate"]["fee_bps"], record["candidate"]["kind"])


def compile_plan(candidate):
    """Construct an executable **deployment parameter proposal**, never deploy.

    No unimplemented family can be sent to a production contract. The buyer
    chooses an independent verifier; 'buyer escrow' sets verifier to buyer.
    """
    if not candidate["deployable"]:
        return {"status": "NO_CONTRACT", "reason": "DIRECT_EXISTING_ALTERNATIVE"}
    require(candidate["fee_bps"] <= 250, "FEE_CONTRACT_CAP")
    return {
        "target_source": "contracts/FrontierProofExchange.sol",
        "constructor": {
            "paymentToken": CANONICAL_TOKEN,
            "feeRecipient": "OPERATOR_VERIFIED_TREASURY_REQUIRED",
            "platformFeeBps": candidate["fee_bps"],
        },
        "job": {
            "verifier": "BUYER_ADDRESS" if candidate["verifier"] == "buyer"
                         else "BUYER_SELECTED_INDEPENDENT_VERIFIER_REQUIRED",
            "expiry_days": candidate["expiry_days"],
            "principal": "SET_BY_BUYER_FOR_EACH_JOB",
            "specification": "FROZEN_EVIDENCE_HASH_REQUIRED",
        },
        "deployment_status": "NOT_DEPLOYED",
        "security_review": "UNQUALIFIED",
        "contract_adoption": "NOT_OBSERVED",
        "royalty_rights": "ONLY_TRANSACTIONS_USING_THIS_DEPLOYED_CONTRACT",
    }


def run(brief):
    validate_brief(brief)
    options = candidates()
    training = [aggregate(brief["development"], c, brief["fixed_construction_cost"])
                for c in options]
    # This is a constrained model optimization, not a universal economic optimum.
    best = max(training, key=ranking_key)
    baseline = [r for r in training if r["candidate"]["kind"] == "direct"
                or (r["candidate"]["kind"] == "buyer_escrow"
                    and r["candidate"]["fee_bps"] == 0)]
    # Frozen holdout evaluated AFTER selection, no opportunistic reranking.
    held = aggregate(brief["holdout"], best["candidate"],
                     brief["fixed_construction_cost"])
    best_control = max(baseline, key=ranking_key)
    controls_held = [
        aggregate(brief["holdout"], r["candidate"],
                  brief["fixed_construction_cost"]) for r in baseline
    ]
    strongest_holdout_control = max(controls_held, key=ranking_key)
    has_superiority = (
        _fraction(held["owner_profit_exact"]) >
        _fraction(strongest_holdout_control["owner_profit_exact"])
        and held["transactions"] > 0
    )
    return {
        "schema": SCHEMA,
        "mission_id": brief["mission_id"],
        "input_sha256": digest(brief),
        "grammar": {"modes": list(MODES), "fee_bps": list(FEES),
                    "expiry_days": list(DAYS), "candidate_count": len(options)},
        "objective": "maximize modeled owner return subject to bilateral participation",
        "development_selected": best,
        "development_strongest_baseline": best_control,
        "holdout_selected": held,
        "holdout_strongest_baseline": strongest_holdout_control,
        "holdout_superiority_within_authored_model": has_superiority,
        "build": compile_plan(best["candidate"]),
        "evidence": {
            "enabler_source": brief["enabler"]["source"],
            "enabler_claimed_change": brief["enabler"]["claimed_change"],
            "author_supplied_verification_flag": brief["enabler"]["verified"],
            "independent_frontier_verification": "NOT_PERFORMED",
            "new_mechanism_novelty": "NOT_ESTABLISHED",
            "actual_buyer_demand": "NOT_OBSERVED",
            "real_collected_revenue": "NOT_OBSERVED",
            "complete_real_world_cost": "NOT_MEASURED",
            "actual_successor_advantage": "NOT_ESTABLISHED",
            "economic_units": "SYNTHETIC_UNITS_NOT_MONEY",
        },
        "decision": "HOLD_NO_DEPLOY_NO_REVENUE",
        "reason": "Synthetic utility assumptions cannot establish real demand or a new productive frontier",
    }


def compare_successor(first, second):
    """No inheritance advantage can be awarded when both arms see same tools."""
    require(first["schema"] == second["schema"] == SCHEMA, "SCHEMA_MISMATCH")
    require(first["mission_id"] != second["mission_id"], "SUCCESSOR_MUST_BE_DISTINCT")
    reused = first["development_selected"]["candidate"]
    # Caller must supply second brief independently; compare retained policy
    # against an equally endowed fresh exhaustive search, not a crippled reset.
    validate_brief(second)
    full = run(second)
    reuse = aggregate(second["holdout"], reused, second["fixed_construction_cost"])
    return {
        "first_mission": first["mission_id"], "successor_mission": second["mission_id"],
        "retained_candidate": reused, "retained_on_fresh_cases": reuse,
        "ordinary_complete_research_on_fresh_cases": full["holdout_selected"],
        "claimed_causal_compounding": "NOT_ESTABLISHED",
        "reason": "Equal-content controls have the same constructor; construction and retention costs unmeasured",
        "actual_economic_value": "NOT_OBSERVED",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--brief", required=True)
    p.add_argument("--successor")
    p.add_argument("--out")
    args = p.parse_args()
    first = strict_json(Path(args.brief).read_text(encoding="utf-8"))
    result = run(first)
    if args.successor:
        nxt = strict_json(Path(args.successor).read_text(encoding="utf-8"))
        result["successor_comparison"] = compare_successor(result, nxt)
    data = json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Refuse rewriting a prior experiment, including its failures.
        with target.open("x", encoding="utf-8") as handle:
            handle.write(data)
    else:
        print(data, end="")


if __name__ == "__main__":
    main()
