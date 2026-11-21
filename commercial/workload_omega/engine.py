"""WORKLOAD Ω: conservative offline shadow evaluator; never places live calls or claims cash."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path


SCHEMA = "workload-omega/v1"
COST_UNIT = "microUSD"


def _integer(value, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name}: expected integer >= {minimum}")
    return value


def _name(value, field: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 128 or value != value.strip():
        raise ValueError(f"{field}: expected a nonempty trimmed string up to 128 characters")
    return value


def _stats(rows: dict, arm: str, reference: str) -> dict:
    values = [row[arm] for _, row in sorted(rows.items())]
    return {
        "pairs": len(values),
        "total_cost_microusd": sum(v["cost_microusd"] for v in values),
        "max_latency_ms": max(v["latency_ms"] for v in values),
        "accepted": sum(v["accepted"] for v in values),
        "regressions": sum(
            row[reference]["accepted"] and not row[arm]["accepted"]
            for row in rows.values()
        ),
    }


def _commercial(contract: dict, holdout_savings: int, pairs: int) -> dict:
    terms = contract.get("economics")
    if terms is None:
        return {
            "status": "NOT_MODELED",
            "unknown": [
                "monthly_volume", "savings_share", "recurring_operating_cost",
                "onboarding_amortization", "monitoring_cost", "other_costs"
            ],
        }
    if not isinstance(terms, dict):
        raise ValueError("economics: expected object or null")
    required = {
        "expected_monthly_requests": 1,
        "savings_share_bps": 0,
        "monthly_operating_cost_microusd": 0,
        "monthly_onboarding_amortization_microusd": 0,
        "monitoring_cost_per_request_microusd": 0,
        "other_monthly_cost_microusd": 0,
    }
    if set(terms) != set(required):
        raise ValueError("economics: all six declared cost, volume, and fee fields required")
    for field, minimum in required.items():
        _integer(terms[field], "economics." + field, minimum)
    if terms["savings_share_bps"] > 10000:
        raise ValueError("economics.savings_share_bps: must not exceed 10000")
    volume = terms["expected_monthly_requests"]
    # Floor sub-microUSD fractions to avoid overclaiming customer benefit.
    gross = (holdout_savings * volume) // pairs
    fee = (max(0, gross) * terms["savings_share_bps"]) // 10000
    provider_cost = (
        terms["monthly_operating_cost_microusd"]
        + terms["monthly_onboarding_amortization_microusd"]
        + volume * terms["monitoring_cost_per_request_microusd"]
        + terms["other_monthly_cost_microusd"]
    )
    contribution = fee - provider_cost
    return {
        "status": "MODEL_ONLY_POSITIVE" if gross > 0 and contribution > 0
        else "MODEL_ONLY_NONPOSITIVE",
        "currency": "USD",
        "amount_unit": COST_UNIT,
        "modeled_monthly_gross_buyer_savings_microusd": gross,
        "modeled_monthly_buyer_fee_microusd": fee,
        "modeled_monthly_provider_cost_microusd": provider_cost,
        "modeled_monthly_provider_contribution_microusd": contribution,
        "verified_bill": False,
        "actual_settled_receipts_microusd": 0,
        "note": "Scenario, not forecast, authenticated invoice, complete audited cost, or earned revenue.",
    }


def evaluate(contract: dict) -> dict:
    """Train-only deterministic choice, frozen holdout check, explicit economic limits."""
    if not isinstance(contract, dict) or contract.get("schema") != SCHEMA:
        raise ValueError("schema: unsupported workload contract")
    workload = _name(contract.get("workload_id"), "workload_id")
    evidence = contract.get("evidence_type")
    if evidence not in ("synthetic", "measured_unverified"):
        raise ValueError("evidence_type: only synthetic or measured_unverified")
    reference = _name(contract.get("reference_arm"), "reference_arm")
    candidates = contract.get("candidate_arms")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("candidate_arms: nonempty array required")
    arms = [reference] + [_name(x, "candidate_arm") for x in candidates]
    if len(set(arms)) != len(arms):
        raise ValueError("reference/candidate arm names must be unique")
    max_latency = _integer(contract.get("max_latency_ms"), "max_latency_ms", 1)
    min_quality = _integer(contract.get("min_acceptance_bps"), "min_acceptance_bps")
    if min_quality > 10000:
        raise ValueError("min_acceptance_bps: must not exceed 10000")
    min_train = _integer(contract.get("min_train_pairs"), "min_train_pairs", 2)
    min_holdout = _integer(contract.get("min_holdout_pairs"), "min_holdout_pairs", 2)
    observations = contract.get("observations")
    if not isinstance(observations, list):
        raise ValueError("observations: array required")
    cohorts = {"train": defaultdict(dict), "holdout": defaultdict(dict)}
    seen_case_splits = {}
    for i, obs in enumerate(observations):
        if not isinstance(obs, dict) or set(obs) != {
            "split", "case_id", "arm", "accepted", "latency_ms", "cost_microusd"
        }:
            raise ValueError(f"observations[{i}]: exact observation fields required")
        split = obs["split"]
        if split not in cohorts:
            raise ValueError(f"observations[{i}]: unknown split")
        case = _name(obs["case_id"], "case_id")
        arm = _name(obs["arm"], "arm")
        if arm not in arms:
            raise ValueError(f"observations[{i}]: unknown arm")
        if type(obs["accepted"]) is not bool:
            raise ValueError(f"observations[{i}]: accepted must be boolean")
        _integer(obs["latency_ms"], "latency_ms")
        _integer(obs["cost_microusd"], "cost_microusd")
        if case in seen_case_splits and seen_case_splits[case] != split:
            raise ValueError(f"case_id {case}: train/holdout leakage")
        seen_case_splits[case] = split
        if arm in cohorts[split][case]:
            raise ValueError(f"case_id {case}: duplicate arm in split {split}")
        cohorts[split][case][arm] = obs
    for split, minimum in (("train", min_train), ("holdout", min_holdout)):
        rows = cohorts[split]
        if len(rows) < minimum:
            raise ValueError(f"{split}: insufficient case pairs")
        for case, paired in rows.items():
            if set(paired) != set(arms):
                raise ValueError(f"{split}/{case}: missing candidate or reference arm")
    train = cohorts["train"]
    base_train = _stats(train, reference, reference)
    ranking = []
    train_summary = {}
    for arm in sorted(candidates):
        s = _stats(train, arm, reference)
        saving = base_train["total_cost_microusd"] - s["total_cost_microusd"]
        eligible = (
            s["regressions"] == 0
            and s["accepted"] * 10000 >= min_quality * s["pairs"]
            and s["max_latency_ms"] <= max_latency
            and saving > 0
        )
        train_summary[arm] = {**s, "saving_microusd": saving, "eligible": eligible}
        if eligible:
            ranking.append((-saving, arm))
    source_sha = hashlib.sha256(
        json.dumps(contract, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    common = {
        "schema": SCHEMA,
        "workload_id": workload,
        "input_sha256": source_sha,
        "evidence_type": evidence,
        "reference_arm": reference,
        "amount_unit": COST_UNIT,
        "train_pairs": len(train),
        "holdout_pairs": len(cohorts["holdout"]),
        "train_candidate_results": train_summary,
        "actual_settled_revenue_microusd": 0,
        "first_dollar_proven": False,
        "second_distinct_asset_proven": False,
        "live_deployment_authorized": False,
        "limitations": [
            "External acceptance labels and input costs are not independently authenticated.",
            "Finite paired cases do not establish out-of-sample population guarantees.",
            "Monthly volumes and contract costs are assumptions, not a complete-cost audit.",
        ],
    }
    # Validate economics even if no candidate is selected; do not conceal malformed terms.
    if not ranking:
        finance = _commercial(contract, 0, len(cohorts["holdout"]))
        return {**common, "selected_arm": reference, "decision": "HOLD_TRAINING",
                "holdout_result": None, "economics": finance}
    ranking.sort()
    selected = ranking[0][1]
    holdout = cohorts["holdout"]
    b = _stats(holdout, reference, reference)
    s = _stats(holdout, selected, reference)
    saving = b["total_cost_microusd"] - s["total_cost_microusd"]
    qualified = (
        s["regressions"] == 0
        and s["accepted"] * 10000 >= min_quality * s["pairs"]
        and s["max_latency_ms"] <= max_latency
        and saving > 0
    )
    finance = _commercial(contract, saving, len(holdout))
    if not qualified:
        decision = "HOLD_HOLDOUT"
    elif finance["status"] == "MODEL_ONLY_NONPOSITIVE":
        decision = "HOLD_ECONOMICS"
    elif evidence == "synthetic":
        decision = "ENGINEERING_ONLY"
    else:
        decision = "SHADOW_CANDIDATE"
    return {
        **common,
        "selected_arm": selected,
        "decision": decision,
        "holdout_result": {
            "reference": b, "candidate": s, "gross_savings_microusd": saving,
            "qualified": qualified,
            "selection_used_holdout": False,
        },
        "economics": finance,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path, help="Local JSON; do not submit secrets")
    parser.add_argument("--output", type=Path, help="Local machine-readable result path")
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    result = evaluate(contract)
    payload = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
