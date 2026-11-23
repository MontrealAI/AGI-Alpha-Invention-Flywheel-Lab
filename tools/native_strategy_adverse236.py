"""Preregistered adverse policy search over canonical, independently audited native businesses.

Research-only: each scenario and arm owns a distinct *simulated* account. Nothing here
opens, migrates, signs, funds, or replaces the protected native-capital owner's account.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import resource
import shutil
import time
from pathlib import Path

from commercial.ledger import canonical, strict_json
from connected_enterprise.design_flywheel import (
    SCHEMA, example_spec, validate, execute, verify,
)

PROTOCOL_SCHEMA = "agi-alpha/native-strategy-adverse236/preregistered-v1"
REPORT_SCHEMA = "agi-alpha/native-strategy-adverse236/public-result/v1"
REGISTERED_SOURCE = "f0987aa48d5c9136b28540f54eabf5367e63bbe6"
CASES = ("reference-positive", "weak-arrivals", "rival-price-war",
         "collection-default", "delivery-cost-shock")
ALLOWED_OVERRIDES = frozenset((
    "arrival_bps", "retention_bps", "price_pressure_bps", "nonpayment_bps",
    "production_cost", "support_cost", "supplier_unit_cost",
))
EXPECTED_ARMS = (("incumbent", "baseline"),
                 ("earned_distribution", "growth"),
                 ("competitive_distribution", "competitive_growth"))


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_protocol(path: Path) -> dict:
    raw = path.read_bytes()
    contract = strict_json(raw)
    if not isinstance(contract, dict) or contract.get("schema") != PROTOCOL_SCHEMA:
        raise ValueError("EXACT_PREREGISTRATION_REQUIRED")
    if contract.get("frozen_underlying_source") != REGISTERED_SOURCE:
        raise ValueError("SOURCE_PARENT_CHANGED")
    if contract.get("role") != "finite_authored_comparison":
        raise ValueError("AUTHORED_FINITE_ROLE_REQUIRED")
    if contract.get("no_deploy_option") is not True:
        raise ValueError("NO_DEPLOY_REQUIRED")
    if contract.get("common_service_cohort_seed") != 2360000:
        raise ValueError("FROZEN_SERVICE_COHORT_REQUIRED")
    registered = contract.get("exact_registered_designs")
    if (not isinstance(registered, list) or
            tuple((x.get("id"), x.get("arm")) for x in registered) != EXPECTED_ARMS or
            any(x.get("policies") != {} or set(x) != {"id", "arm", "policies"}
                for x in registered)):
        raise ValueError("EXACT_INCUMBENT_AND_INTERVENTIONS_REQUIRED")
    cohorts = contract.get("cohorts")
    if (not isinstance(cohorts, list) or
            tuple(x.get("id") for x in cohorts) != CASES):
        raise ValueError("EXACT_REGISTERED_SCENARIO_DENOMINATOR_REQUIRED")
    seeds = []
    for case in cohorts:
        if set(case) != {"id", "development_seed", "confirmation_seed", "config_overrides"}:
            raise ValueError("EXACT_SCENARIO_FIELDS_REQUIRED")
        overrides = case["config_overrides"]
        if not isinstance(overrides, dict) or not set(overrides) <= ALLOWED_OVERRIDES:
            raise ValueError("UNREGISTERED_MARKET_INTERVENTION")
        if any(type(n) is not int or n < 0 for n in overrides.values()):
            raise ValueError("NONINTEGER_OR_NEGATIVE_INTERVENTION")
        for field in ("development_seed", "confirmation_seed"):
            seed = case[field]
            if type(seed) is not int or seed < 0:
                raise ValueError("NONNEGATIVE_INTEGER_SEED_REQUIRED")
            seeds.append(seed)
    if len(set(seeds)) != len(seeds):
        raise ValueError("PRECOMMITTED_COMMON_RANDOM_NUMBER_SEEDS_REQUIRED")
    if contract.get("decision_rule", {}).get("no_deploy") != (
            "Default absent externally verified buyers and complete full actual resource/billing costs."):
        raise ValueError("CONSERVATIVE_COMMERCIAL_BOUNDARY_REQUIRED")
    return contract


def registered_spec(contract: dict, case: dict) -> dict:
    spec = example_spec()
    spec["schema"] = SCHEMA
    spec["evidence_role"] = contract["role"]
    spec["development_seed"] = case["development_seed"]
    spec["confirmation_seed"] = case["confirmation_seed"]
    spec["service_cohort_seed"] = contract["common_service_cohort_seed"]
    spec["designs"] = copy.deepcopy(contract["exact_registered_designs"])
    spec["incumbent"] = "incumbent"
    spec["config"].update(copy.deepcopy(case["config_overrides"]))
    return validate(spec)


def public_case(case: dict, proof: dict, wall: float, cpu: float) -> dict:
    recommendation = proof["heldout_recommendation"]
    delta = proof["matched_confirmation_profit_delta_microUSD"]
    passes = (recommendation["challenger_accepted"] is True and
              proof["confirmed_positive_funded_successor_opportunity"] is True and
              proof["comparative_advantage_on_one_fresh_seed"] is True and
              type(delta) is int and delta > 0)
    confirmations = {}
    for name, record in proof["confirmation"].items():
        confirmations[name] = {
            "native_modeled_profit_microUSD": record["profit_microUSD"],
            "native_obligations_covered": record["obligations_covered"],
            "native_settled_orders": record["settled_orders"],
        }
    return {
        "case": case["id"],
        "development_seed": case["development_seed"],
        "confirmation_seed": case["confirmation_seed"],
        "overrides": case["config_overrides"],
        "source_sha256": proof["source_sha256"],
        "spec_sha256": proof["spec_sha256"],
        "native_audit_and_independent_replay": "PASSED",
        "selected_development": proof["selection"]["selected"],
        "recommended_native_policy": recommendation["recommended_policy"],
        "positive_funded_successor": proof["confirmed_positive_funded_successor_opportunity"],
        "matched_profit_delta_microUSD": delta,
        "native_confirmation": confirmations,
        "strict_adverse_challenger_gate": bool(passes),
        "measured_local_wall_seconds": round(wall, 6),
        "measured_process_user_plus_system_cpu_seconds": round(cpu, 6),
        "unmeasured_host_or_model_dollars": None,
        "actual_external_collections_usd": 0,
        "external_policy_adoption": "NO_DEPLOY",
    }


def independent_frozen_runtime(source: Path, destination: Path) -> Path:
    """Copy exact release-closure source into a new isolated simulated world root.

    The canonical prepare_services generator insists on a create-only
    service-inputs/ directory. Each preregistered scenario must own an immutable
    working-source root; sharing one repo working tree would violate both the
    generator's no-overwrite rule and independently audited source identity.
    """
    from connected_enterprise.runner import identity

    before = identity(source)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("CREATE_ONLY_NATIVE_SOURCE_ROOT_REQUIRED")
    destination.mkdir(parents=True)
    for name in before["files"]:
        original = source / name
        copy = destination / name
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, copy)
    if identity(destination) != before:
        raise ValueError("ISOLATED_CANONICAL_RUNTIME_SOURCE_CHANGED")
    return destination


def run(contract_path: Path, output: Path) -> dict:
    contract = load_protocol(contract_path)
    output = output.absolute()
    if output.exists() or any(p.is_symlink() for p in (output, *output.parents)):
        raise FileExistsError("FRESH_NON_SYMLINK_RESEARCH_OUTPUT_REQUIRED")
    output.mkdir(parents=True)
    src = Path(__file__).resolve().parents[1]
    result = {
        "schema": REPORT_SCHEMA,
        "preregistration_sha256": sha256(contract_path.read_bytes()),
        "parent_source_commit": REGISTERED_SOURCE,
        "status": "PARTIAL_NOT_ALL_REGISTERED_COHORTS_EXECUTED",
        "registered_scenarios": list(CASES),
        "observations": [],
        "strict_robust_challenger_qualified": False,
        "external_qualified_buyer_demand": False,
        "actual_paid_contracts": 0,
        "actual_external_collections_usd": 0,
        "native_t365_complete_cost_profit_usd": None,
        "whole_campaign_host_model_dollars": None,
        "strong_unrestricted_human_and_AI_comparator": "NOT_EXECUTED",
        "claim": "FINITE_AUTHORED_SIMULATION_NOT_CAUSAL_INVENTION_OR_REAL_COMMERCE",
        "decision": "NO_DEPLOY",
    }
    public_dir = output / "publish"
    public_dir.mkdir()
    (public_dir / "REGISTERED_PROTOCOL.json").write_bytes(canonical(contract) + b"\n")

    for case in contract["cohorts"]:
        start = time.perf_counter()
        before = resource.getrusage(resource.RUSAGE_SELF)
        try:
            spec = registered_spec(contract, case)
            case_output = output / ("native-" + case["id"])
            frozen_root = independent_frozen_runtime(src, output / ("source-" + case["id"]))
            constructed = execute(spec, frozen_root, case_output)
            independently_recomputed = verify(frozen_root, case_output)
            if constructed != independently_recomputed:
                raise ValueError("INDEPENDENT_REDERIVATION_MISMATCH")
            after = resource.getrusage(resource.RUSAGE_SELF)
            cpu = ((after.ru_utime + after.ru_stime) -
                   (before.ru_utime + before.ru_stime))
            receipt = public_case(case, independently_recomputed,
                                  time.perf_counter() - start, cpu)
            result["observations"].append(receipt)
            (public_dir / (case["id"] + ".json")).write_bytes(
                canonical(independently_recomputed) + b"\n")
            (public_dir / "SUMMARY.partial.json").write_bytes(canonical(result) + b"\n")
        except Exception as exc:
            result["failed_scenario"] = case["id"]
            result["failed_exception_type"] = type(exc).__name__
            # Do not export error text: operating paths and account locations are private.
            (public_dir / "SUMMARY.partial.json").write_bytes(canonical(result) + b"\n")
            raise
    result["status"] = "ALL_REGISTERED_AUTHORED_SCENARIOS_EXECUTED_AND_NATIVE_AUDITED"
    result["strict_robust_challenger_qualified"] = (
        len(result["observations"]) == len(CASES) and
        all(x["strict_adverse_challenger_gate"] for x in result["observations"])
    )
    (public_dir / "SUMMARY.json").write_bytes(canonical(result) + b"\n")
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--protocol", type=Path, default=Path(
        "campaign/native-strategy-adverse236/PROTOCOL.json"))
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    result = run(args.protocol, args.output)
    print(json.dumps({
        "status": result["status"],
        "cases": len(result["observations"]),
        "strict_robust_challenger_qualified": result["strict_robust_challenger_qualified"],
        "actual_external_collections_usd": result["actual_external_collections_usd"],
        "decision": result["decision"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
