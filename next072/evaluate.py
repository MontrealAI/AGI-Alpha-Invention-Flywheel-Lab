"""Evaluator-owned reveal oracle and finite discovery metrics."""
from __future__ import annotations

import math

import numpy as np

from .data import canonical_json_hash
from .policy import PublicContext, allocate, hash_order
from .protocol import MIN_TARGET_RECALL, POLICIES, PRIMARY_POLICY, REFERENCE_FRACTION, REVEAL_FRACTION, SPLIT_SALT, TARGET_FRACTION


class RevealOracle:
    def __init__(self, outcomes: dict[str, float], references: set[str], budget: int):
        if not np.isfinite(list(outcomes.values())).all():
            raise ValueError("Nonfinite hidden outcomes")
        self.__outcomes = dict(outcomes)
        self.__reference_names = set(references)
        self.__budget = budget
        self.receipt = []

    def reveal(self, pair: str) -> float:
        if pair in self.__reference_names:
            raise ValueError("Calibration pair cannot count as a new query")
        if pair not in self.__outcomes:
            raise ValueError("Unknown pair")
        if any(row["pair"] == pair for row in self.receipt):
            raise ValueError("Duplicate reveal request")
        if len(self.receipt) >= self.__budget:
            raise ValueError("Reveal budget exhausted")
        value = self.__outcomes[pair]
        self.receipt.append({"pair": pair, "D": value, "query": len(self.receipt) + 1})
        return value


def run(prepared: dict) -> dict:
    names = prepared["pair_names"]
    features = prepared["features"]
    outcomes = dict(zip(names, prepared["outcomes"]))
    if len(outcomes) != len(names) or not np.isfinite(prepared["outcomes"]).all():
        raise ValueError("Invalid outcome vector")
    n_reference = math.ceil(REFERENCE_FRACTION * len(names))
    reference_names = hash_order(names, SPLIT_SALT)[:n_reference]
    candidates = sorted(set(names) - set(reference_names))
    budget = math.floor(REVEAL_FRACTION * len(candidates))
    target_count = math.ceil(TARGET_FRACTION * len(candidates))
    if not candidates or not target_count:
        raise ValueError("Insufficient complete confirmation pairs")
    # Evaluation labels are never added to PublicContext or passed to policies.
    targets = sorted(candidates, key=lambda name: (-outcomes[name], name))[:target_count]
    target_set = set(targets)
    context = PublicContext(
        tuple(names), tuple(map(tuple, features)), tuple(reference_names),
        tuple(outcomes[name] for name in reference_names), budget,
    )
    policy_results = {}
    all_receipts = {}
    for policy in POLICIES:
        oracle = RevealOracle(outcomes, set(reference_names), budget)
        receipt = allocate(context, oracle.reveal, policy)
        if [row["pair"] for row in receipt] != [row["pair"] for row in oracle.receipt]:
            raise AssertionError("Policy/oracle receipt mismatch")
        # Selection is sealed before target labels enter these receipt rows.
        sealed_hash = canonical_json_hash(receipt)
        discoveries = 0
        for item in receipt:
            item["is_target_after_seal"] = item["pair"] in target_set
            discoveries += int(item["is_target_after_seal"])
            item["cumulative_discoveries_after_seal"] = discoveries
        policy_results[policy] = {
            "queries": len(receipt), "discoveries": discoveries,
            "missed_targets": target_count - discoveries,
            "non_target_queries": len(receipt) - discoveries,
            "target_count": target_count,
            "precision": discoveries / len(receipt) if receipt else None,
            "recall": discoveries / target_count,
            "boundary_met": discoveries / target_count >= MIN_TARGET_RECALL,
            "sealed_selection_sha256": sealed_hash,
        }
        all_receipts[policy] = receipt
    random_mean = float(np.mean([policy_results[f"hash_{i:02d}"]["discoveries"] for i in range(32)]))
    primary = policy_results[PRIMARY_POLICY]
    for result in policy_results.values():
        result["lift_vs_hash_mean"] = result["discoveries"] / random_mean if random_mean else None
    equivalent = all_receipts[PRIMARY_POLICY] == all_receipts["ordinary_equal_content"]
    return {
        "status": "source_bound_replay_completed",
        "primary_policy": PRIMARY_POLICY,
        "input_denominator": {"pairs": len(names), "readout_genes": len(prepared["readout_genes"]), "pair_readout_rows": prepared["rows"]},
        "references": reference_names,
        "confirmation_candidates": candidates,
        "confirmation_target_pairs_after_seal": targets,
        "reference_pairs": n_reference, "confirmation_pairs": len(candidates),
        "query_budget": budget, "target_count": target_count,
        "full_profile_cost_counts": {
            "unique_single_profiles": len(prepared["single_interventions"]), "control_profiles": 1,
            "calibration_double_profiles": n_reference, "selected_double_profiles": budget,
            "total_profiles_used_per_policy": len(prepared["single_interventions"]) + 1 + n_reference + budget,
            "total_profiles_for_all_pairs": len(prepared["single_interventions"]) + 1 + len(names),
            "count_is_not_money_or_equal_assay_cost": True,
        },
        "policy_results": policy_results,
        "hash_control_mean_discoveries": random_mean,
        "equal_content_ordinary_reuse_exact_tie": equivalent,
        "proposed_discovery_boundary_met": primary["boundary_met"],
        "independent_acceptance": "PENDING",
        "physical_or_biological_delivery_admission": "NOT_ESTABLISHED",
        "commercial_or_native_financial_admission": "NOT_ESTABLISHED",
        "receipts": all_receipts,
    }
