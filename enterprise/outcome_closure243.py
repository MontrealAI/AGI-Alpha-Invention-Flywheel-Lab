"""Source-bound partial-offer completion gate; does not authorize native commerce.

This is an intentionally conservative research model: even an affirmative
authored rights record remains *hypothetical*, never verified commerce.
"""
from __future__ import annotations

import argparse
import copy
from hashlib import sha256
import json
import math
from pathlib import Path

from enterprise.complete_arrangements242 import evaluate, registered_cases

SCHEMA = "agi-alpha/outcome-closure243/research-v1"
PARENT_HEAD = "f92a5e02d1974884f2d663f35051bb11b8b3c028"
PERMISSION_FIELDS = frozenset((
    "evidence_tier", "rights_asserted", "compatibility_asserted",
    "acceptance_asserted", "completion_probability",
    "verification_cost_usd", "coordination_cost_usd",
    "correction_cost_usd",
))
POLICIES = ("STANDALONE_B@0.95", "NO_BID")


def _num(value, *, probability=False):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("EXPLICIT_FINITE_NONNEGATIVE_COMPLEMENT_COST_REQUIRED")
    if probability and value > 1:
        raise ValueError("BOUNDED_COMPLEMENT_PROBABILITY_REQUIRED")
    return float(value)


def validate_permission(record):
    if not isinstance(record, dict) or frozenset(record) != PERMISSION_FIELDS:
        raise ValueError("COMPLETE_EXPLICIT_COMPLEMENT_RECORD_REQUIRED")
    tier = record["evidence_tier"]
    if tier not in ("unverified", "authored_only"):
        raise ValueError("NO_EXTERNAL_EVIDENCE_AUTHORITY_IN_THIS_RESEARCH_MODULE")
    flags = [record[k] for k in (
        "rights_asserted", "compatibility_asserted", "acceptance_asserted")]
    if any(type(v) is not bool for v in flags):
        raise ValueError("EXPLICIT_BOOLEAN_SUPPLIER_AND_ACCEPTANCE_GATES_REQUIRED")
    cost_fields = (
        "completion_probability", "verification_cost_usd",
        "coordination_cost_usd", "correction_cost_usd")
    if tier == "unverified":
        if any(flags) or any(record[k] is not None for k in cost_fields):
            raise ValueError("UNVERIFIED_COMPLEMENT_MUST_NOT_CLAIM_READY_COSTS")
        return "UNVERIFIED"
    if not all(flags):
        raise ValueError("MODEL_OFFER_WITHOUT_COMPLEMENT_RIGHTS_OR_ACCEPTANCE")
    for k in cost_fields:
        _num(record[k], probability=(k == "completion_probability"))
    return "AUTHORED_ONLY"


def _record(tier, *, p=1., v=3., c=2., f=0.):
    is_model = tier == "authored_only"
    return {
        "evidence_tier": tier,
        "rights_asserted": is_model,
        "compatibility_asserted": is_model,
        "acceptance_asserted": is_model,
        "completion_probability": p if is_model else None,
        "verification_cost_usd": v if is_model else None,
        "coordination_cost_usd": c if is_model else None,
        "correction_cost_usd": f if is_model else None,
    }


def registered_witnesses():
    cases = registered_cases()
    return {
        "NO_RIGHTS": (copy.deepcopy(cases["BASE"]), _record("unverified")),
        "MODEL_AUTHORIZED": (copy.deepcopy(cases["BASE"]), _record("authored_only")),
        "MODEL_FAILURE": (copy.deepcopy(cases["BASE"]), _record(
            "authored_only", p=.5, f=4.)),
        "WAR": (copy.deepcopy(cases["PRICE_WAR"]), _record("authored_only")),
        "ABSENT": (copy.deepcopy(cases["NO_ARRIVAL"]), _record("authored_only")),
    }


def evaluate_complete(case, permission, policy):
    if policy not in POLICIES:
        raise ValueError("FROZEN_POLICY_REQUIRED")
    tier = validate_permission(permission)
    # Validate all original buyer/price/cost inputs even on a no-bid path.
    parent = evaluate(policy, case)
    if policy == "NO_BID":
        return {
            "policy": policy, "parent_partial_contribution_usd": 0.,
            "modeled_complete_contribution_usd": 0.,
            "selected_if_known_case": True, "completion_probability": None,
            "model_evidence_tier": tier, "operational_authority": [],
            "qualified_paid_outcome": None,
        }
    partial = parent["contribution"]
    if tier == "UNVERIFIED":
        return {
            "policy": policy, "parent_partial_contribution_usd": partial,
            "modeled_complete_contribution_usd": None,
            "selected_if_known_case": False, "completion_probability": None,
            "model_evidence_tier": "UNVERIFIED_COMPLETE_OUTCOME",
            "operational_authority": [], "qualified_paid_outcome": None,
        }
    q = parent["initial_win_probability"]
    p = _num(permission["completion_probability"], probability=True)
    net = parent["conditional_collected_net_receipt"]
    # Parent's registered B onboarding is charged for any accepted B sale,
    # not just a verified completion; no negative receipt can be spent.
    onboarding = case["publics"][1]["onboarding_cost_usd"]
    v = _num(permission["verification_cost_usd"])
    c = _num(permission["coordination_cost_usd"])
    f = _num(permission["correction_cost_usd"])
    a = parent["initial_attempt_cost"]
    amount = q * (p * net - onboarding - v - c - (1. - p) * f) - a
    return {
        "policy": policy, "parent_partial_contribution_usd": partial,
        "modeled_complete_contribution_usd": amount,
        "selected_if_known_case": amount > 0,
        "completion_probability": p,
        "complete_acceptance_probability": q * p,
        "initial_sale_probability": q,
        "first_attempt_and_quote_cost_usd": a,
        "model_evidence_tier": "AUTHOR_ASSUMPTIONS_ONLY",
        "operational_authority": [], "qualified_paid_outcome": None,
    }


def report():
    witnesses = registered_witnesses()
    rows = {}
    for key, (case, permission) in witnesses.items():
        candidate = evaluate_complete(case, permission, POLICIES[0])
        control = evaluate_complete(case, permission, POLICIES[1])
        rows[key] = {
            "scenario_sha256": sha256(json.dumps(
                {"case": case, "permission": permission},
                sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "partial_offer": candidate,
            "no_bid": control,
            "decision": ("HOLD_UNVERIFIED" if candidate[
                "modeled_complete_contribution_usd"] is None else
                ("CONDITIONAL_MODEL_OFFER" if candidate[
                    "modeled_complete_contribution_usd"] > 0 else
                    "CONDITIONAL_MODEL_NO_BID")),
        }
    src = Path(__file__)
    parent = src.with_name("complete_arrangements242.py")
    return {
        "schema": SCHEMA, "parent_git_head": PARENT_HEAD,
        "source_sha256": sha256(src.read_bytes()).hexdigest(),
        "parent_source_sha256": sha256(parent.read_bytes()).hexdigest(),
        "all_cases": rows, "scenario_count": len(rows),
        "real_supplier_rights_verified": None,
        "real_buyer_acceptance_verified": None,
        "real_customer_collections_usd": None,
        "native_trailing365_complete_cost_profit_usd": None,
        "native_financial_authority": [],
        "commercial_verdict": "UNQUALIFIED_HOLD_NO_NATIVE_ACTION",
        "research_claim": "EXPOSED_AUTHOR_ASSUMPTIONS_ONLY_NOT_PAID_COMMERCE",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.out.exists() or args.out.is_symlink():
        raise FileExistsError("CREATE_ONLY_RESEARCH_RESULT_REQUIRED")
    result = report()
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({
        "commercial_verdict": result["commercial_verdict"],
        "scenario_count": result["scenario_count"],
        "evidence_tier": result["research_claim"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
