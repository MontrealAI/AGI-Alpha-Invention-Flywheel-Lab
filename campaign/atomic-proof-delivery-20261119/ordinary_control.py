"""Strong conventional exact software for the identical three-coloring output.
No model calls, account, economic demand, paid operation or external data.
"""
from __future__ import annotations
import itertools
import json
import argparse
import time

def check(rows: list[int], colors: list[int]) -> bool:
    n = len(rows)
    if not 3 <= n <= 32 or len(colors) != n:
        return False
    mask = (1 << n) - 1
    for i, row in enumerate(rows):
        if not isinstance(row, int) or row < 0 or row > mask or (row >> i) & 1:
            return False
        if not isinstance(colors[i], int) or not 0 <= colors[i] < 3:
            return False
        for j in range(i + 1, n):
            e = (row >> j) & 1
            if e != (rows[j] >> i) & 1:
                return False
            if e and colors[i] == colors[j]:
                return False
    return True

def solve(rows: list[int]) -> list[int] | None:
    """Brute-force fully competent exact comparator on this finite tiny test domain."""
    n = len(rows)
    if n > 8 or n < 3 or any(not isinstance(x, int) for x in rows):
        raise ValueError("reference exhaustive solver is restricted to 3..8 vertices")
    for colors in itertools.product(range(3), repeat=n):
        if check(rows, list(colors)):
            return list(colors)
    return None

CASES = {
    "K3": [6, 5, 3],
    "C4": [10, 5, 10, 5],
    "K4": [14, 13, 11, 7],
}
OPTIONS = [
    {"name": "ordinary_offchain_self_service", "outcome_correctness": "same"},
    {"name": "buyer_verifier_escrow", "conditional_issue": "unilateral_buyer_refusal"},
    {"name": "independent_verifier_escrow", "conditional_issue": "trusted_verifier_cost_and_refusal"},
    {"name": "onchain_proof_carrying_result", "conditional_issue": "gas_and_public_mempool"},
    {"name": "no_deploy", "outcome": "retains_cash_and_no_obligations"},
]

def report() -> dict:
    start = time.process_time()
    results = {}
    for name, rows in CASES.items():
        colors = solve(rows)
        results[name] = {
            "rows": rows,
            "colors": colors,
            "solution_found": colors is not None,
            "independently_valid": colors is not None and check(rows, colors),
        }
    assert results["K3"]["independently_valid"]
    assert results["C4"]["independently_valid"]
    assert not results["K4"]["solution_found"]
    return {
        "scope": "authored_tiny_graphs_competent_ordinary_exact_solver",
        "results": results,
        "alternatives": OPTIONS,
        "direct_ordinary_comparator": "ties_on_tested_accepted_solutions",
        "observed_real_buyer": False,
        "collected_commercial_revenue": None,
        "native_account_operation": None,
        "chain_gas_usd": None,
        "whole_campaign_billing_usd": None,
        "decision": "HOLD_NO_DEPLOY_NO_BID",
        "observed_cpu_seconds_lower_bound": time.process_time() - start,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report(), f, sort_keys=True, indent=2)
    print("APD001 ordinary-control K3/C4 accepted; K4 not 3-colorable; no commerce")
