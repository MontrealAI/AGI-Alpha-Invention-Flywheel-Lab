"""Precommitted six-case adverse native business-design experiment.

This script operates ONLY fresh, independent simulated canonical native accounts
through connected_enterprise.design_flywheel. It never opens a predecessor account,
moves cash between arms, modifies the ledger, or authorizes an external action.
"""
from __future__ import annotations

import argparse
import json
import os
import resource
import shutil
import sys
import time
from pathlib import Path

# Script mode (python scripts/...) must import the exact working repository, not site packages.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from commercial.ledger import canonical, digest
from connected_enterprise.design_flywheel import SCHEMA as DESIGN_SCHEMA
from connected_enterprise.design_flywheel import example_spec, execute, validate, verify
from connected_enterprise.runner import identity as native_source_identity, source_paths as native_source_paths

REPORT_SCHEMA = "agi-alpha/native-design-adverse151/v1"
M = 1_000_000
ARMS = (
    ("incumbent", "baseline"),
    ("earned_distribution", "growth"),
    ("competitive_distribution", "competitive_growth"),
)
CAPITALS = (("low", 2500 * M), ("medium", 25000 * M))
# Exactly these three authored worlds; current market data is not calibrated.
REGIMES = (
    ("potential-demand", 151101, 151102, 151103,
     {"arrival_bps": 8000, "retention_bps": 8500, "nonpayment_bps": 200},
     {"price_microUSD": 2 * M}),
    ("competing-low-value", 151201, 151202, 151203,
     {"arrival_bps": 5000, "retention_bps": 3000,
      "nonpayment_bps": 3000, "price_pressure_bps": 7000,
      "value_bps": 7000, "buyer_budget_multiplier_bps": 7000,
      "production_cost": 2500_000},
     {}),
    ("supplier-refusal-cost", 151301, 151302, 151303,
     {"arrival_bps": 6500, "retention_bps": 6000,
      "nonpayment_bps": 1500, "production_cost": 4 * M,
      "capacity_price": 15 * M},
     {"price_microUSD": 15 * M, "activation_reliability_bps": 2000,
      "realization_bps": 3500, "overlap_bps": 5000}),
)


def specifications():
    """All six mutually independent account experiments, fixed before execution."""
    rows = []
    for name, development, confirmation, cohort, changes, pilot in REGIMES:
        for capital_name, opening in CAPITALS:
            spec = example_spec()
            spec["evidence_role"] = "finite_authored_comparison"
            spec["development_seed"] = development
            spec["confirmation_seed"] = confirmation
            spec["service_cohort_seed"] = cohort
            spec["config"].update({
                "horizon_days": 21,
                "customer_pool": 10,
                "setup_cost": 25 * M,
                "opening": opening,
                "maintenance_daily": 100_000,
            })
            spec["config"].update(changes)
            spec["config"]["channels"]["pilot"].update(pilot)
            spec["designs"] = [
                {"id": ident, "arm": arm, "policies": {}}
                for ident, arm in ARMS
            ]
            spec["incumbent"] = "incumbent"
            spec = validate(spec)
            rows.append((name + "-" + capital_name, spec))
    if len(rows) != 6 or len(set(name for name, _ in rows)) != 6:
        raise ValueError("EXACT_SIX_CASES_REQUIRED")
    return rows


def interpret(registered, public):
    """No reviewer-generated account or cash; read the native audited public receipt."""
    if public.get("schema") != DESIGN_SCHEMA or public.get("status") != "CONDITIONAL_SIMULATED_EXECUTION":
        raise ValueError("ACTUAL_SOURCE_BOUND_NATIVE_DESIGN_REPORT_REQUIRED")
    if public.get("spec_sha256") != digest(registered):
        raise ValueError("REGISTERED_CASE_SOURCE_CHANGED")
    recommendation = public["heldout_recommendation"]
    if recommendation.get("native_financial_action_authority") != []:
        raise ValueError("NO_EXTERNAL_ACTION_AUTHORITY_ALLOWED")
    selected = recommendation.get("recommended_policy")
    confirmation = public["confirmation"]
    incumbent = confirmation.get("incumbent")
    selected_receipt = confirmation.get(selected) if selected is not None else None
    profit = selected_receipt["profit_microUSD"] if selected_receipt else None
    protected = bool(selected_receipt and selected_receipt["obligations_covered"])
    if selected == "incumbent" and not incumbent:
        raise ValueError("INCUMBENT_RECEIPT_MISSING")
    if selected is not None and (selected not in {a for a, _ in ARMS} or not protected or profit <= 0):
        raise ValueError("UNSUPPORTED_NATIVE_POLICY_RECOMMENDATION")
    delta = public["matched_confirmation_profit_delta_microUSD"]
    challenger_accepted = bool(recommendation["challenger_accepted"])
    support = (selected not in (None, "incumbent") and challenger_accepted and
               delta is not None and delta > 0 and protected and profit > 0)
    if challenger_accepted != (selected not in (None, "incumbent")):
        raise ValueError("CHALLENGER_RECOMMENDATION_CONFLICT")
    return {
        "native_case_source_sha256": public["source_sha256"],
        "native_registration_sha256": public["spec_sha256"],
        "native_challenger": selected if support else None,
        "native_recommendation": selected or "NO_DEPLOY",
        "native_no_deploy_modeled_profit_microUSD": 0,
        "selected_modeled_profit_microUSD": profit,
        "incumbent_modeled_profit_microUSD": (incumbent or {}).get("profit_microUSD"),
        "selected_unrestricted_earned_microUSD": (
            selected_receipt["unrestricted_earned_microUSD"] if selected_receipt else None),
        "selected_obligations_covered": protected,
        "matched_native_profit_delta_microUSD": delta,
        "challenger_accepted_on_heldout": challenger_accepted,
        "robust_challenger_support_in_this_case": support,
        "original_connected_funded_successor_witness": public.get("connected_earned_successor_witness"),
        "native_financial_action_authority": [],
        "actual_external_collections_microUSD": 0,
        "real_buyer_count": 0,
    }


def robust_verdict(cases):
    if set(cases) != {name + "-" + tier for name, *_ in REGIMES for tier, _ in CAPITALS}:
        raise ValueError("REGISTERED_SIX_CASE_DENOMINATOR_REQUIRED")
    winners = [row["native_challenger"] for row in cases.values()]
    all_supported = bool(winners[0] and all(w == winners[0] for w in winners))
    return {
        "support": "ROBUST_SIMULATED_CHALLENGER_SUPPORTED" if all_supported
                   else "REJECT_ROBUST_SIMULATED_CHALLENGER",
        "common_challenger": winners[0] if all_supported else None,
        "cases_attempted": 6,
        "cases_completed": len(cases),
        "criterion": "Identical non-incumbent wins confirmed against baseline and no-deploy with protected positive native complete-cost profit in all six authored cases",
        "claims": {
            "empirical_buyer_demand": False, "paid_external_commerce": False,
            "source_migration_of_original_account": False,
            "physical_product": False, "causal_discovery_advantage": False,
            "annual_3b_profit_qualified": False,
        },
    }



def separate_exact_native_source(checkout, destination):
    """Create one exact, private source closure per independently seeded cohort.

    design_flywheel.execute creates service-inputs/ exclusively under its supplied
    root. Sharing a checkout between different cohort seeds is invalid; never
    overwrite source inputs or make a new signing authority for an OLD account.
    This copies only canonical public source identities (no credentials/.git),
    then proves the full native closure is identical *before* native operation.
    """
    checkout, destination = Path(checkout).resolve(), Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("FRESH_CANONICAL_CASE_SOURCE_REQUIRED")
    original = tuple(native_source_paths(checkout))
    if not original or len(original) != len(set(original)):
        raise ValueError("COMPLETE_UNIQUE_CANONICAL_SOURCE_REQUIRED")
    for name in original:
        p = Path(name)
        old = checkout / p
        if p.is_absolute() or ".." in p.parts or not old.is_file() or old.is_symlink():
            raise ValueError("CANONICAL_SOURCE_PATH_UNSAFE")
        new = destination / p
        new.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(old, new)
    if tuple(native_source_paths(destination)) != original:
        raise ValueError("CASE_SOURCE_INVENTORY_CHANGED")
    if native_source_identity(destination) != native_source_identity(checkout):
        raise ValueError("CASE_CANONICAL_EXECUTING_BYTES_CHANGED")
    return destination


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", required=True,
                    help="Fresh absolute private directory outside repository for the full run")
    args = ap.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    out = Path(args.output)
    if not out.is_absolute() or out.exists() or any(x.is_symlink() for x in (out, *out.parents)):
        raise ValueError("FRESH_ABSOLUTE_NON_SYMLINK_OUTPUT_REQUIRED")
    os.umask(0o077)
    out.mkdir(parents=True)
    registered = specifications()
    # Entire registration catalog is written BEFORE the first financial simulation.
    catalog = [{"name": name, "spec_sha256": digest(spec), "spec": spec}
               for name, spec in registered]
    (out / "REGISTRATION.json").write_bytes(canonical({
        "schema": REPORT_SCHEMA, "base_main": "de4e9c2425c3879ad1b2e52bbe44cff79dcf973d",
        "cases": catalog, "complete_case_count": 6,
        "no_deploy": {"modeled_profit_microUSD": 0, "native_account_operated": False}
    }) + b"\n")
    rows = {}
    started = time.monotonic()
    for name, spec in registered:
        # Each design-flywheel executes and independently audits native accounts.
        case_source = separate_exact_native_source(root, out / ("source-" + name))
        raw = execute(spec, case_source, out / name)
        checked = verify(case_source, out / name)
        if raw != checked:
            raise ValueError("REPLAYED_NATIVE_DESIGN_REPORT_CHANGED")
        rows[name] = interpret(spec, checked)
        print("CASE_FINISHED", name, rows[name]["native_recommendation"],
              rows[name]["selected_modeled_profit_microUSD"], flush=True)
    u = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt = {
        "schema": REPORT_SCHEMA,
        "registered_catalog_sha256": digest(catalog),
        "source_execution_scope": "ACTUAL_CURRENT_REPOSITORY_CANONICAL_NATIVE_SIMULATION",
        "cases": rows,
        "decision": robust_verdict(rows),
        "resources": {
            "observed_wall_seconds": time.monotonic() - started,
            "observed_process_tree_cpu_seconds": u.ru_utime + u.ru_stime + children.ru_utime + children.ru_stime,
            "whole_campaign_host_billing_usd": None, "frontier_model_billing_usd": None
        },
        "actual_paid_commerce_profit_microUSD": None,
        "modeled_native_trailing365_profit_microUSD": None,
        "external_demand_calibrated": False,
        "next": "NO_REAL_BID; retain strongest native incumbent or no-deploy, construct a newly attainable accepted outcome with independently evidenced buyer demand before any real capital decision."
    }
    (out / "PUBLIC.json").write_bytes(canonical(receipt) + b"\n")
    print("REGISTERED_ADVERSE_NATIVE_DESIGN151", receipt["decision"]["support"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
