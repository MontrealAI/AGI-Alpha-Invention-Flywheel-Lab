"""Source-pinned finite incentive counterexample; SYNTHETIC, NOT real commerce.

The contract only commits to an artifact hash. This witness assumes the buyer
can inspect/benefit from the useful artifact before choosing to attest, and
that cheating has no external penalty. Alternative reveal schemes may change
the game and are not covered here.
"""
from __future__ import annotations

from fractions import Fraction
import json

from invent import value


def exact(number: Fraction | int) -> str:
    return str(Fraction(number))


def evaluate() -> dict:
    price = 100
    buyer_value = 150
    seller_cost = 40
    fee = 1
    check_cost = 3

    case = {
        "id": "observable-accepted-artifact",
        "price": price,
        "value_if_accepted": buyer_value,
        "seller_cost": seller_cost,
        "success_ppm": 1_000_000,
        "network_cost": 0,
        "independent_check_cost": check_cost,
        "operator_cost": 0,
        "buyer_outside": 0,
        "seller_outside": 0,
        "time_limit_days": 3,
    }
    buyer_escrow = {
        "kind": "buyer_escrow", "verifier": "buyer",
        "fee_bps": 100, "expiry_days": 1, "deployable": True,
    }
    original = value(case, buyer_escrow)
    if not original["accepted"]:
        raise ValueError("ORIGINAL_MODEL_NOT_IN_DECLARED_POSITIVE_REGION")
    source_model = {
        "accepted": original["accepted"],
        "buyer_surplus": exact(original["buyer"]),
        "seller_surplus": exact(original["seller"]),
        "protocol_surplus": exact(original["owner"]),
        "source": "ORIGINAL_AUTHORED_SYNTHETIC_VALUE_FUNCTION",
    }

    # Conditioned on seller delivering an accessible valuable artifact.
    accept_buyer = Fraction(buyer_value - price)
    refund_after_observation = Fraction(buyer_value)
    if not refund_after_observation > accept_buyer:
        raise ValueError("WITHHOLDING_NOT_STRICTLY_PROFITABLE")
    # If the buyer is expected to exploit that choice, cost is a sunk loss
    # for an already-delivering seller and strictly negative before entry.
    seller_if_delivered_and_refunded = Fraction(-seller_cost)
    if not seller_if_delivered_and_refunded < 0:
        raise ValueError("SELLER_HAS_NO_ENTRY_INCENTIVE")
    scenarios = {
        "buyer_verifier_paid_if_honest": {
            "buyer_surplus": exact(accept_buyer),
            "seller_surplus": exact(price - fee - seller_cost),
            "protocol_surplus": exact(fee),
            "conditional": "buyer voluntarily attests and transfers succeed",
        },
        "buyer_verifier_after_accessible_delivery_and_strategic_refund": {
            "buyer_surplus": exact(refund_after_observation),
            "seller_surplus": exact(seller_if_delivered_and_refunded),
            "protocol_surplus": "0",
            "conditional": "buyer withholds, can keep useful artifact, then refunds",
        },
        "buyer_verifier_rational_preentry": {
            "buyer_surplus": "0", "seller_surplus": "0", "protocol_surplus": "0",
            "conditional": "rational seller refuses a predictably loss-making job",
        },
        "honest_independent_verifier_fee_bearing": {
            "buyer_surplus": exact(buyer_value - price - check_cost),
            "seller_surplus": exact(price - fee - seller_cost),
            "protocol_surplus": exact(fee),
            "verification_cost": exact(check_cost),
            "conditional": "independent verifier acts honestly; verifier cost paid",
        },
        "honest_independent_verifier_fee_free_incumbent": {
            "buyer_surplus": exact(buyer_value - price - check_cost),
            "seller_surplus": exact(price - seller_cost),
            "protocol_surplus": "0",
            "verification_cost": exact(check_cost),
            "conditional": "competent fee-free escrow and honest independent verifier",
        },
        "direct_prepaid_competent_seller": {
            "buyer_surplus": exact(buyer_value - price),
            "seller_surplus": exact(price - seller_cost),
            "protocol_surplus": "0",
            "conditional": "buyer prepays and competent seller delivers; fraud risk excluded",
        },
        "no_deploy": {
            "buyer_surplus": "0", "seller_surplus": "0", "protocol_surplus": "0",
            "conditional": "no trade, no investment, no obligations",
        },
    }
    return {
        "schema": "montreal.ai/omega-verifier-incentive-counterexample/v1",
        "economic_domain": "AUTHORED_FINITE_RATIONAL_SYNTHETIC_GAME_NOT_MARKET",
        "assumptions": {
            "buyer_value": buyer_value, "price": price,
            "seller_production_cost": seller_cost,
            "fee": fee, "verifier_cost": check_cost,
            "artifact_accessible_before_acceptance": True,
            "external_penalty_for_false_refusal": 0,
            "token_behavior": "COMPLIANT_SIMULATED_ERC20",
            "actual_buyers": 0, "actual_payments": 0,
        },
        "original_buyer_escrow_value": source_model,
        "buyer_after_delivery": {
            "accept_surplus": exact(accept_buyer),
            "refund_surplus": exact(refund_after_observation),
            "strict_best_response": "WITHHOLD_AND_REFUND",
        },
        "seller_best_response_before_entry": "NO_ENTRY",
        "scenarios": scenarios,
        "decision": "BUYER_CONTROLLED_ESCROW_NOT_INCENTIVE_COMPATIBLE_UNDER_DECLARED_INFORMATION_PATTERN",
        "engineering_evidence_only": True,
        "actual_revenue": "NONE_OBSERVED",
        "actual_model_host_billing": "UNKNOWN",
        "new_invention_or_universal_equilibrium": "NOT_ESTABLISHED",
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), sort_keys=True, indent=2))
