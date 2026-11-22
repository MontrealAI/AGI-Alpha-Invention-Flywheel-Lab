"""Key-free, independent aggregation of the fixed 3-arm reach ablation.

Only a new, fully source-matched and independently audited native account is
eligible. Never publish raw accounts, orders, tickets, recovery files, or keys.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from commercial.ledger import strict_json
from mechanism_harness.reach_verify import verify_reach

ARMS = ("organic", "trial_once", "pilot")
SCENARIOS = ("central", "weak", "copycat", "no_demand", "failed_activation")
PAIRS = (("trial_once", "organic"), ("pilot", "trial_once"), ("pilot", "organic"))


def _read(path: Path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("REGULAR_PRIVATE_REACH_EVIDENCE_REQUIRED")
    return strict_json(path.read_bytes())


def summarize(root: Path, scenario: str, source_commit: str):
    if scenario not in SCENARIOS or len(source_commit) != 40 or any(c not in "0123456789abcdef" for c in source_commit):
        raise ValueError("REGISTERED_SCENARIO_AND_SOURCE_REQUIRED")
    reports = {}
    plans = {}
    orders = {}
    audit_receipts = {}
    for arm in ARMS:
        folder = root / arm
        checked = verify_reach(folder)
        if checked.get("accepted") is not True:
            raise ValueError("INDEPENDENT_NATIVE_AUDIT_REFUSED")
        audit_receipts[arm] = checked
        reports[arm] = _read(folder / "REPORT.json")
        plans[arm] = _read(folder / "PLAN.json")["decisions"]
        orders[arm] = _read(folder / "ORDERS.json")
        if (reports[arm]["arm"], reports[arm]["scenario"]) != (arm, scenario):
            raise ValueError("SOURCE_MATCHED_REGISTERED_ARM_MISMATCH")
        if len(plans[arm]) != 2 or reports[arm]["native_export_sha256"] != checked["native_export_sha256"]:
            raise ValueError("REGISTERED_NATIVE_TWO_DECISION_PROOF_MISSING")
    first_once, first_pilot = plans["trial_once"][0], plans["pilot"][0]
    if (first_once["policy"]["action"] != first_pilot["policy"]["action"]
            or first_once["policy"]["observed"] != first_pilot["policy"]["observed"]
            or first_once["policy"]["expected_net_microUSD"] != first_pilot["policy"]["expected_net_microUSD"]):
        raise ValueError("MATCHED_FIRST_PLAN_DIFFERED")
    if ([row for row in orders["trial_once"] if row["day"] < 118]
            != [row for row in orders["pilot"] if row["day"] < 118]):
        raise ValueError("PAIRED_NATIVE_FIRST_PERIOD_CHANGED")
    if (plans["trial_once"][1]["policy"]["action"] != "SKIP"
            or plans["trial_once"][1]["policy"]["reason"] != "REGISTERED_ONE_TRANCHE"
            or any(p["policy"]["action"] != "SKIP" for p in plans["organic"])):
        raise ValueError("UNAUTHORIZED_CONTROL_CHANNEL_PURCHASE")
    keys = {
        "profit": "modeled_aftertax_profit_microUSD",
        "revenue": "revenue_microUSD", "collections": "collections_microUSD",
        "expenses": "expenses_microUSD", "cash": "cash_microUSD",
        "available": "available_microUSD", "unrestrictedEarned": "earned_available_microUSD",
        "tailReserve": "tail_reserve_microUSD", "payables": "payables_microUSD",
    }
    results = {}
    for arm in ARMS:
        s = reports[arm]["native_summary"]
        results[arm] = {name: s[field] for field, name in keys.items()}
        results[arm].update({
            "native_export_sha256": audit_receipts[arm]["native_export_sha256"],
            "report_sha256": audit_receipts[arm]["report_sha256"],
            "settled_baskets": reports[arm]["settled"],
            "paid_invoices_microUSD": reports[arm]["invoice_microUSD"],
            "contacts": reports[arm]["contacts"],
            "first_action": plans[arm][0]["policy"]["action"],
            "renewal_action": plans[arm][1]["policy"]["action"],
        })
    pairs = {}
    for arm, control in PAIRS:
        a, b = results[arm], results[control]
        pairs[arm + "_minus_" + control] = {
            "profit_microUSD": a["modeled_aftertax_profit_microUSD"] - b["modeled_aftertax_profit_microUSD"],
            "settled_baskets": a["settled_baskets"] - b["settled_baskets"],
            "available_microUSD": a["available_microUSD"] - b["available_microUSD"],
        }
    return {
        "schema": "agi-alpha/omega-trial-once-keyfree-matched-ablation/v1",
        "source_commit": source_commit, "scenario": scenario,
        "seed_scope": "EXPOSED_ENGINEERING_REPRODUCTION_NOT_NEW_DEMAND",
        "native_accounts_executed": 3, "independent_audits_accepted": 3,
        "matched_first_period": True, "three_arms": results,
        "paired_differences": pairs, "status": "EXECUTED_AUDITED",
        "real_paid_customers": 0, "US3B_target_established": False,
        "model_host_billing_USD": None,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-root", type=Path, required=True)
    p.add_argument("--scenario", choices=SCENARIOS, required=True)
    p.add_argument("--source-commit", required=True)
    p.add_argument("--public-output", type=Path, required=True)
    args = p.parse_args(argv)
    if args.public_output.exists() or args.public_output.is_symlink():
        raise ValueError("FRESH_PUBLIC_EVIDENCE_REQUIRED")
    result = summarize(args.private_root, args.scenario, args.source_commit)
    args.public_output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"scenario": result["scenario"], "paired_differences": result["paired_differences"],
                      "no_real_commerce": True}, sort_keys=True))


if __name__ == "__main__":
    main()
