"""Schedule the frozen Portfolio 071 account experiments without changing them.

The registered controller, manifest, account operations and full native audits
remain unchanged. Only independent account scheduling is concurrent. Existing
complete accounts are read and independently audited; they are never reopened.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import time

from commercial.ledger import canonical, digest, strict_json
from connected_enterprise.finance import source_paths_for_manifest
from portfolio071.economics import (
    CAPITALS_USD, HORIZON_DAYS, World, compact, conditional_market_frontier,
    execute_trajectory, project_game, registered_worlds,
)
from portfolio071.reproduce import stage_native_source
from portfolio071.service import load_contracts, safe_path
from portfolio071.verify_economics import audit_arm


REPO = Path(__file__).resolve().parents[1]
FROZEN_FINANCIAL_COMMIT = "9d4b2a2efb0289d6493d24e2e6c9493720596971"
FROZEN_FINANCIAL_DOCUMENT_SHA256 = "3cfe1304592430bdea1329c42d4c4e5122dd7c90107302ada5fcff89ffbfd389"
AMENDMENT = REPO / "experiments/portfolio_20261102/ORCHESTRATION_AMENDMENT.md"
ECONOMIC_FREEZE = REPO / "experiments/portfolio_20261102/ECONOMICS_FREEZE.json"
ORCHESTRATION_FREEZE = REPO / "experiments/portfolio_20261102/ORCHESTRATION_FREEZE.json"
WORKFLOW = ".github/workflows/portfolio071.yml"
ORCHESTRATION_SOURCES = {"scripts/replay_portfolio071_parallel.py", "tests/test_portfolio071_parallel.py",
                         "experiments/portfolio_20261102/ORCHESTRATION_AMENDMENT.md", WORKFLOW}
REQUIRED_PUBLIC_FILES = ("manifest.json", "trajectory.json", "native-at-horizon.json", "native-after-drain.json")


def load(path):
    return strict_json(Path(path).read_bytes())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with Path(path).open("xb") as stream:
        stream.write(canonical(value) + b"\n")


def registered_jobs():
    """The exact ordered recipes in the frozen run_campaign function."""
    recipes = [(World(), capital, "working_capital_aware", False) for capital in CAPITALS_USD]
    recipes += [(world, 100000, "working_capital_aware", False) for world in registered_worlds()[1:]]
    recipes += [(World(), 100000, "working_capital_aware", True),
                (World(), 100000, "stylized_prepaid_reach_capacity", False)]
    rows = [{"index": index, "directory": f"arm-{index:02d}", "world": asdict(world),
             "capital_usd": capital, "policy": policy, "earned_only_k2": earned,
             "horizon_days": HORIZON_DAYS}
            for index, (world, capital, policy, earned) in enumerate(recipes)]
    identities = [(row["world"]["name"], row["capital_usd"], row["policy"], row["earned_only_k2"]) for row in rows]
    if len(rows) != 24 or len(set(identities)) != 24:
        raise ValueError("EXACT_REGISTERED_24_UNIQUE_RECIPES_REQUIRED")
    return rows


def validate_freezes(source, manifest, *, repo=REPO, economic_freeze=ECONOMIC_FREEZE,
                     orchestration_freeze=ORCHESTRATION_FREEZE):
    """Enforce the old financial freeze and the one explicit workflow amendment."""
    if sha(economic_freeze) != FROZEN_FINANCIAL_DOCUMENT_SHA256:
        raise ValueError("ORIGINAL_ECONOMIC_FREEZE_DOCUMENT_CHANGED")
    frozen, amendment = load(economic_freeze), load(orchestration_freeze)
    original = frozen["source_hashes"]
    if frozen.get("registered_arms") != 24 or frozen.get("horizon_hours") != 43800 or len(original) != 72:
        raise ValueError("ORIGINAL_ECONOMIC_DENOMINATOR_OR_HORIZON_CHANGED")
    amended = amendment.get("source_hashes", {})
    if not ORCHESTRATION_SOURCES.issubset(amended):
        raise ValueError("COMPLETE_ORCHESTRATION_SOURCE_FREEZE_REQUIRED")
    overrides = amendment.get("source_overrides", {})
    if set(overrides) != {WORKFLOW} or set(overrides[WORKFLOW]) != {"previous_sha256", "amended_sha256"}:
        raise ValueError("ONLY_EXPLICIT_WORKFLOW_SCHEDULING_OVERRIDE_ALLOWED")
    workflow = overrides[WORKFLOW]
    if workflow["previous_sha256"] != original[WORKFLOW] or workflow["amended_sha256"] != amended[WORKFLOW]:
        raise ValueError("WORKFLOW_OLD_TO_NEW_HASH_BINDING_REQUIRED")
    for name, expected in original.items():
        required = workflow["amended_sha256"] if name == WORKFLOW else expected
        if sha(safe_path(repo, name)) != required:
            raise ValueError("FROZEN_EXECUTING_SOURCE_CHANGED:" + name)
    for name, expected in amended.items():
        if sha(safe_path(repo, name)) != expected:
            raise ValueError("FROZEN_ORCHESTRATION_SOURCE_CHANGED:" + name)
    runtime = {}
    for name in source_paths_for_manifest(manifest):
        if name not in original or sha(safe_path(source, name)) != original[name]:
            raise ValueError("ORIGINAL_STAGED_RUNTIME_SOURCE_CHANGED:" + name)
        runtime[name] = original[name]
    return {"economic_freeze_sha256": sha(economic_freeze),
            "orchestration_freeze_sha256": sha(orchestration_freeze),
            "original_source_count": len(original), "runtime_source_hashes": runtime,
            "workflow_scheduling_amendment": workflow}


def resource_limits():
    """Measure this host; the worker cap is operational, never market evidence."""
    affinity = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 1)
    quota_cores = None
    cgroup = Path("/sys/fs/cgroup")
    try:
        quota, period = (cgroup / "cpu.max").read_text().split()
        if quota != "max":
            quota_cores = max(1, int(quota) // int(period))
    except (OSError, ValueError, ZeroDivisionError):
        pass
    memory_limit = memory_current = None
    try:
        text = (cgroup / "memory.max").read_text().strip()
        if text != "max":
            memory_limit = int(text)
            memory_current = int((cgroup / "memory.current").read_text())
    except (OSError, ValueError):
        pass
    available_cpu = min(affinity, quota_cores) if quota_cores is not None else affinity
    memory_cap = 4
    if memory_limit is not None and memory_current is not None:
        # At least 512 MiB per additional worker plus a 512 MiB shared margin.
        # This is deliberately more than the observed approximately 200 MiB
        # peak of the existing canonical process. It is not an OOM guarantee.
        headroom = max(0, memory_limit - memory_current - 512 * 1024**2)
        memory_cap = max(0, headroom // (512 * 1024**2))
    maximum = min(4, available_cpu, memory_cap)
    return {"affinity_cpus": affinity, "quota_cpus_floor": quota_cores,
            "memory_limit_bytes": memory_limit, "memory_current_bytes": memory_current,
            "conservative_worker_maximum": maximum,
            "scope": "Local execution resource limit, not a company or market scale ceiling."}


def select_workers(requested=None):
    observed = resource_limits()
    allowed = observed["conservative_worker_maximum"]
    if allowed < 1:
        raise ValueError("INSUFFICIENT_MEMORY_HEADROOM_FOR_ONE_REGISTERED_WORKER")
    if requested is not None and (type(requested) is not int or not 1 <= requested <= allowed):
        raise ValueError(f"WORKERS_MUST_BE_BETWEEN_1_AND_RESOURCE_BOUND_{allowed}")
    return requested or allowed, observed


def _execute_job(source, manifest, output, job):
    """A spawn worker receives only public data, never a live account/key."""
    result = execute_trajectory(source, manifest, Path(output) / job["directory"],
        capital_usd=job["capital_usd"], world=World(**job["world"]), policy=job["policy"],
        earned_only_k2=job["earned_only_k2"], horizon_days=job["horizon_days"])
    return compact(result)


def validate_completed(source, manifest, directory, job):
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("REAL_ACCOUNT_DIRECTORY_REQUIRED")
    if any(not (directory / name).is_file() or (directory / name).is_symlink()
           for name in REQUIRED_PUBLIC_FILES):
        raise ValueError("INCOMPLETE_EXISTING_ACCOUNT_REFUSED:" + directory.name)
    trajectory = load(directory / "trajectory.json")
    expected = {key: job[key] for key in ("world", "capital_usd", "policy", "earned_only_k2")}
    if any(trajectory.get(key) != value for key, value in expected.items()):
        raise ValueError("COMPLETED_ACCOUNT_RECIPE_MISMATCH:" + directory.name)
    identity = f'{job["world"]["name"]}-{job["capital_usd"]}-{job["policy"]}-{int(job["earned_only_k2"])}'
    if trajectory.get("id") != identity or trajectory.get("infer_idle_days") is not True:
        raise ValueError("COMPLETED_ACCOUNT_IDENTITY_MISMATCH:" + directory.name)
    if load(directory / "manifest.json") != manifest:
        raise ValueError("COMPLETED_ACCOUNT_MANIFEST_MISMATCH:" + directory.name)
    if len(trajectory.get("daily", [])) != job["horizon_days"]:
        raise ValueError("COMPLETED_ACCOUNT_HORIZON_MISMATCH:" + directory.name)
    contract = "portfolio071-" + digest(identity)[:24]
    opening = job["capital_usd"] * 1_000_000
    for filename in ("native-at-horizon.json", "native-after-drain.json"):
        record = load(directory / filename)
        for config in (record["ledger"]["config"], record["connected_journal"]):
            if (config.get("contract") != contract or config.get("opening") != opening
                    or config.get("working") != 0 or config.get("manifest_sha256") != digest(manifest)):
                raise ValueError("COMPLETED_NATIVE_CONTRACT_OR_OPENING_MISMATCH:" + directory.name)
    # This independently replays both public exports and checks signed profit,
    # every-action cash identities, complete days, pending tax and settlements.
    audited = audit_arm(source, directory, expected_hours=job["horizon_days"] * 24)
    if not audited["accepted"]:
        raise ValueError("COMPLETED_ACCOUNT_INDEPENDENT_AUDIT_REFUSED:" + directory.name)
    fingerprints = {name: sha(directory / name) for name in REQUIRED_PUBLIC_FILES}
    return compact(trajectory), {"index": job["index"], "directory": directory.name,
        "status": "RETAINED_COMPLETE_ACCOUNT_READ_ONLY", "public_file_sha256": fingerprints,
        "registered_native_contract": contract,
        "independent_audit": audited}


def _preflight(source, manifest, output, jobs, resume_completed):
    output = Path(output)
    if output.is_symlink():
        raise ValueError("SYMLINK_OUTPUT_REFUSED")
    if output.exists() and not resume_completed:
        raise ValueError("FRESH_OUTPUT_REQUIRED_OR_EXPLICIT_RESUME_COMPLETED")
    if not output.exists() and resume_completed:
        raise ValueError("RESUME_REQUIRES_EXISTING_CAMPAIGN_DIRECTORY")
    if not output.exists():
        output.mkdir(parents=True, exist_ok=False)
    if not output.is_dir():
        raise ValueError("CAMPAIGN_DIRECTORY_REQUIRED")
    for name in ("campaign.json", "ORCHESTRATION_START.json", "ORCHESTRATION_RESULT.json"):
        if (output / name).exists():
            raise ValueError("EXISTING_CAMPAIGN_OR_ORCHESTRATION_RECEIPT_REFUSED:" + name)
    expected = {job["directory"]: job for job in jobs}
    existing = {path.name: path for path in output.iterdir() if path.name.startswith("arm-")}
    if set(existing) - set(expected):
        raise ValueError("UNREGISTERED_ACCOUNT_DIRECTORY_REFUSED")
    # Check every directory for completion before expensive replay or submission.
    # An empty root-created stop gate is incomplete and is deliberately refused.
    for path in existing.values():
        if path.is_symlink() or not path.is_dir() or any(
                not (path / name).is_file() or (path / name).is_symlink() for name in REQUIRED_PUBLIC_FILES):
            raise ValueError("INCOMPLETE_EXISTING_ACCOUNT_REFUSED:" + path.name)
    retained, receipts = {}, []
    for name in sorted(existing):
        value, receipt = validate_completed(source, manifest, existing[name], expected[name])
        retained[expected[name]["index"]] = value
        receipts.append(receipt)
    return retained, receipts


def _campaign(records, manifest):
    # The same public aggregation fields as frozen economics.run_campaign.
    # All monetary values come from unchanged, fully audited native accounts.
    return {"schema": "portfolio071/economic-campaign/v1", "registered_arms": 24,
        "completed_arms": len(records), "arms": records, "factorial_game": project_game(),
        "unique_scientific_artifacts": len(manifest["jobs"]),
        "artifact_reuse_scope": "The same accepted catalog is licensed across counterfactual accounts; per-arm catalog counts must not be summed as new scientific artifacts.",
        "conditional_market_frontier": conditional_market_frontier(),
        "actual_external_revenue_usd": 0,
        "milestone_1b_count": sum(row["milestone_1b"] for row in records),
        "milestone_3b_count": sum(row["milestone_3b"] for row in records),
        "claims": {"code_execution": "SUPPORTED_IF_REPLAY_PASSES",
                   "finite_game_optimality": "CONDITIONAL_FINITE_MENU_ONLY",
                   "novel_discovery_superiority": "NOT_ESTABLISHED_CONVENTIONAL_TIE",
                   "actual_market_demand": "UNRESOLVED_AUTHORED_BUYERS",
                   "physical_installation": "NOT_RUN", "industrial_rights": "UNRESOLVED",
                   "model_cost_calibration": "UNRESOLVED", "actual_commerce": "NOT_RUN"}}


def _schedule(source, manifest, output, jobs, workers):
    """Attempt each registered submission once and account for every index."""
    records, statuses, futures = {}, {}, {}
    infrastructure_failure = None

    def collect(future, job):
        try:
            records[job["index"]] = future.result()
            status = {"index": job["index"], "directory": job["directory"], "status": "COMPLETED_NATIVE_ACCOUNT"}
        except Exception as error:
            status = {"index": job["index"], "directory": job["directory"],
                      "status": "FAILED_NO_RETRY", "error_type": type(error).__name__, "reason": str(error)}
        statuses[job["index"]] = status
        print(json.dumps(status, sort_keys=True), flush=True)

    try:
        # spawn inherits no live SQLite connection, signer or writer lease.
        with ProcessPoolExecutor(max_workers=workers,
                                 mp_context=multiprocessing.get_context("spawn")) as pool:
            for job in jobs:
                try:
                    future = pool.submit(_execute_job, str(source), manifest, str(output), job)
                    futures[future] = job
                except Exception as error:
                    infrastructure_failure = {"status": "POOL_SUBMISSION_FAILURE",
                        "error_type": type(error).__name__, "reason": str(error)}
                    break
            for future in as_completed(futures):
                collect(future, futures[future])
    except Exception as error:
        infrastructure_failure = {"status": "POOL_INFRASTRUCTURE_FAILURE",
            "error_type": type(error).__name__, "reason": str(error)}
    # A context/iterator/shutdown failure must not erase submitted or unsubmitted
    # indices. No task is resubmitted, including an interrupted or broken worker.
    for future, job in futures.items():
        if job["index"] not in statuses:
            if future.done():
                collect(future, job)
            else:
                statuses[job["index"]] = {"index": job["index"], "directory": job["directory"],
                    "status": "SUBMITTED_INFRASTRUCTURE_FAILURE_NO_RETRY"}
    for job in jobs:
        if job["index"] not in statuses:
            statuses[job["index"]] = {"index": job["index"], "directory": job["directory"],
                "status": "NOT_STARTED_INFRASTRUCTURE_FAILURE"}
    ordered = [statuses[job["index"]] for job in jobs]
    failures = [row for row in ordered if row["status"] != "COMPLETED_NATIVE_ACCOUNT"]
    if infrastructure_failure is not None:
        failures.append(infrastructure_failure)
    return records, ordered, failures


def run(reproduction_output, *, resume_completed=False, workers=None):
    reproduction_output = Path(reproduction_output).absolute()
    if reproduction_output.is_symlink() or not reproduction_output.is_dir():
        raise ValueError("EXISTING_SCIENTIFIC_REPRODUCTION_DIRECTORY_REQUIRED")
    if (reproduction_output / "ORCHESTRATION.json").exists():
        raise ValueError("EXISTING_OVERALL_ORCHESTRATION_RECEIPT_REFUSED")
    source = reproduction_output / "native-source"
    manifest_file = reproduction_output / "native-manifest.json"
    if source.exists() != manifest_file.exists():
        raise ValueError("PARTIAL_NATIVE_STAGING_REFUSED")
    if not source.exists():
        if resume_completed:
            raise ValueError("RESUME_REQUIRES_ORIGINAL_NATIVE_STAGE")
        source, manifest = stage_native_source(reproduction_output, reproduction_output / "r3")
    else:
        if source.is_symlink() or manifest_file.is_symlink():
            raise ValueError("SYMLINK_NATIVE_STAGE_REFUSED")
        manifest = load(manifest_file)
    load_contracts(source, manifest)
    freeze_identity = validate_freezes(source, manifest)
    jobs = registered_jobs()
    worker_count, resources = select_workers(workers)
    output = reproduction_output / "economics"
    retained, retention_receipts = _preflight(source, manifest, output, jobs, resume_completed)
    remaining = [job for job in jobs if job["index"] not in retained]
    provenance = {"schema": "portfolio071/parallel-orchestration/v1",
        "frozen_financial_commit": FROZEN_FINANCIAL_COMMIT,
        "runner_sha256": sha(__file__), "amendment_sha256": sha(AMENDMENT),
        "retention_verifier_sha256": sha(REPO / "portfolio071/verify_economics.py"),
        "manifest_canonical_sha256": hashlib.sha256(canonical(manifest)).hexdigest(),
        **freeze_identity,
        "source_hashes": manifest["source_hashes"], "registered_jobs": jobs,
        "registered_jobs_sha256": hashlib.sha256(canonical(jobs)).hexdigest(),
        "worker_count": worker_count, "resources_at_start": resources,
        "multiprocessing_start_method": "spawn", "automatic_retries": 0,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "retained_complete_accounts": retention_receipts,
        "new_account_indices": [job["index"] for job in remaining],
        "scope": "Scheduling only. Frozen financial source and every native audit remain unchanged; no account or cash is reopened, reset, copied or pooled."}
    write_new(output / "ORCHESTRATION_START.json", provenance)
    start = time.monotonic()
    new_records, execution_statuses, failures = _schedule(source, manifest, output, remaining, worker_count)
    records = {**retained, **new_records}
    for receipt in retention_receipts:
        directory = output / receipt["directory"]
        try:
            unchanged = all(sha(directory / name) == value for name, value in receipt["public_file_sha256"].items())
        except OSError:
            unchanged = False
        if not unchanged:
            failures.append({"directory": receipt["directory"], "status": "RETAINED_PUBLIC_ACCOUNT_CHANGED"})
    try:
        validate_freezes(source, manifest)
    except Exception as error:
        failures.append({"status": "FROZEN_SOURCE_CHANGED_AFTER_SCHEDULING",
                         "error_type": type(error).__name__, "reason": str(error)})
    accepted = not failures and len(records) == len(jobs)
    result = {**provenance, "completed_arms": len(records), "registered_arms": len(jobs),
        "accepted": accepted, "failures": failures, "execution_statuses": execution_statuses,
        "wall_seconds": time.monotonic() - start,
        "record_order": [job["directory"] for job in jobs],
        "original_scientific_summary_preserved": (reproduction_output / "SUMMARY.json").is_file(),
        "audit_scope": "Each new trajectory retains full native audits; complete retained trajectories were independently audited before scheduling. A separate all-arm independent audit remains required."}
    if accepted:
        campaign = _campaign([records[index] for index in range(len(jobs))], manifest)
        write_new(output / "campaign.json", campaign)
        result["campaign_sha256"] = sha(output / "campaign.json")
    write_new(output / "ORCHESTRATION_RESULT.json", result)
    write_new(reproduction_output / "ORCHESTRATION.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reproduction-output", type=Path, required=True)
    parser.add_argument("--resume-completed", action="store_true")
    parser.add_argument("--workers", type=int)
    args = parser.parse_args()
    result = run(args.reproduction_output, resume_completed=args.resume_completed, workers=args.workers)
    print(json.dumps({key: result[key] for key in ("accepted", "registered_arms", "completed_arms", "worker_count")}, sort_keys=True))
    if not result["accepted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
