"""Independently audit and assemble the fixed interrupted 24-account campaign.

Reads public durable records only. Native replay is confined to the frozen
auditor's disposable state; this module cannot reopen an operating account.
The original failed orchestration is never rewritten as a completed process.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import time

from commercial.ledger import canonical, digest, strict_json
from portfolio071.economics import CAPITALS_USD, World, compact, registered_worlds
from portfolio071.verify_economics import audit_arm
from scripts.replay_portfolio071_parallel import _campaign
from scripts.verify_portfolio071_recovery_prefix import (
    FINANCIAL_FREEZE_SHA256, PREFIX_PATH, PREFIX_SHA256, PUBLIC_FILES,
    RECOVERED_INDICES, SECOND_PREFIX_PATH, SECOND_PREFIX_SHA256,
    check as check_prefixes, public_input_hashes, read, same, sha,
)

CLOSED = [0, 1, 2, 3, 4, 5, 6, 7, 12, 13, 14, 15, 18, 19, 20, 21]
FRESH = [23]
SOURCES = ("portfolio071/recovery.py", "portfolio071/recovery_controller.py")
RUNNER = "scripts/recover_portfolio071_campaign.py"
THIS_SOURCE = "scripts/assemble_portfolio071_recovered.py"
ORCHESTRATION_FREEZE_SHA256 = "3fb7b3dd6b624031805e00ff855a2bb739c6bc26be405391e77be9cd74066817"
ORCHESTRATION_V1_SHA256 = "95c0913b6f1e931d83e8cfde705ea844bd4626157890442fb42d77be017f2c4d"
ORCHESTRATION_V1_PATH = "experiments/portfolio_20261102/historical/ORCHESTRATION_FREEZE_v1.json"
WORKFLOW_V1_PATH = "experiments/portfolio_20261102/historical/portfolio071_workflow_v1.yml"
WORKFLOW = ".github/workflows/portfolio071.yml"


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def write_new(path, value):
    with Path(path).open("xb") as stream:
        stream.write(canonical(value) + b"\n")


def recipes():
    rows = [(World(), capital, "working_capital_aware", False) for capital in CAPITALS_USD]
    rows += [(world, 100000, "working_capital_aware", False) for world in registered_worlds()[1:]]
    rows += [(World(), 100000, "working_capital_aware", True),
             (World(), 100000, "stylized_prepaid_reach_capacity", False)]
    return [{"index": index, "directory": f"arm-{index:02d}", "world": asdict(world),
             "capital_usd": capital, "policy": policy, "earned_only_k2": earned,
             "horizon_days": 1825, "infer_idle_days": True}
            for index, (world, capital, policy, earned) in enumerate(rows)]


def recipe_for_recovery(job):
    return {key: value for key, value in job.items() if key not in {"index", "directory"}}


def expected_id(job):
    return f'{job["world"]["name"]}-{job["capital_usd"]}-{job["policy"]}-{int(job["earned_only_k2"])}'


def path_map():
    return [{"index": i, "directory": f"arm-{i:02d}",
             "public_source": f'{"recovery" if i in RECOVERED_INDICES else "economics"}/arm-{i:02d}',
             "original_account_directory": f"economics/arm-{i:02d}",
             "disposition": "RECOVERED_SAME_ORIGINAL_ACCOUNT" if i in RECOVERED_INDICES
                else "PRESERVED_ORIGINAL_COMPLETE" if i in CLOSED else "FIRST_ORIGINAL_EXECUTION"}
            for i in range(24)]


def check_sources(root, freeze_path, registration_commit):
    require(re.fullmatch(r"[0-9a-f]{40}", registration_commit or ""), "PUBLIC_REGISTRATION_COMMIT_REQUIRED")
    financial_path = root / "experiments/portfolio_20261102/ECONOMICS_FREEZE.json"
    require(sha(financial_path) == FINANCIAL_FREEZE_SHA256, "ORIGINAL_FINANCIAL_FREEZE_CHANGED")
    require(sha(root / PREFIX_PATH) == PREFIX_SHA256 and sha(root / SECOND_PREFIX_PATH) == SECOND_PREFIX_SHA256,
            "INDEPENDENT_INTERRUPTION_IDENTITIES_CHANGED")
    financial, registration = read(financial_path), read(freeze_path)
    require(registration.get("recovered_indices") == RECOVERED_INDICES
            and registration.get("unopened_indices") == FRESH
            and registration.get("preserved_complete_indices") == CLOSED
            and type(registration.get("registered_total_accounts")) is int
            and registration["registered_total_accounts"] == 24
            and registration.get("financial_freeze_sha256") == FINANCIAL_FREEZE_SHA256,
            "EXACT_24_ACCOUNT_RECOVERY_REGISTRATION_REQUIRED")
    orchestration_path = root / "experiments/portfolio_20261102/ORCHESTRATION_FREEZE.json"
    require(sha(orchestration_path) == ORCHESTRATION_FREEZE_SHA256
            and registration.get("orchestration_freeze_sha256") == ORCHESTRATION_FREEZE_SHA256,
            "PROSPECTIVE_ORCHESTRATION_V2_FREEZE_CHANGED")
    require(sha(root / ORCHESTRATION_V1_PATH) == ORCHESTRATION_V1_SHA256,
            "HISTORICAL_ORCHESTRATION_V1_BYTES_CHANGED")
    orchestration, previous = read(orchestration_path), read(root / ORCHESTRATION_V1_PATH)
    expected_history = {"document_path": ORCHESTRATION_V1_PATH, "document_sha256": ORCHESTRATION_V1_SHA256,
                        "workflow_path": WORKFLOW_V1_PATH, "workflow_sha256": previous["source_hashes"][WORKFLOW],
                        "public_head": "418440e4587165488ccbf5a9d6bc04ba375a4675"}
    require(orchestration.get("schema") == "portfolio071/orchestration-freeze/v2"
            and orchestration.get("financial_freeze_sha256") == FINANCIAL_FREEZE_SHA256
            and same(orchestration.get("supersedes"), expected_history)
            and sha(root / WORKFLOW_V1_PATH) == expected_history["workflow_sha256"],
            "EXACT_WORKFLOW_V2_AND_RETAINED_V1_HISTORY_REQUIRED")
    require(set(orchestration["source_hashes"]) == set(previous["source_hashes"])
            and all(value == previous["source_hashes"][name] for name, value in orchestration["source_hashes"].items()
                    if name != WORKFLOW), "ORCHESTRATION_V2_MAY_CHANGE_ONLY_WORKFLOW_SOURCE")
    require(same(orchestration.get("source_overrides"), {WORKFLOW: {
                "previous_sha256": financial["source_hashes"][WORKFLOW],
                "amended_sha256": orchestration["source_hashes"][WORKFLOW]}}),
            "EXACT_ORIGINAL_FINANCIAL_TO_WORKFLOW_V2_OVERRIDE_REQUIRED")
    for name, value in orchestration["source_hashes"].items():
        require(sha(root / name) == value, "EXACT_WORKFLOW_V2_OR_UNCHANGED_ORCHESTRATION_HELPER_REQUIRED:" + name)
    required = {*SOURCES, RUNNER, THIS_SOURCE, PREFIX_PATH, SECOND_PREFIX_PATH, ORCHESTRATION_V1_PATH, WORKFLOW_V1_PATH,
                "scripts/verify_portfolio071_recovery_prefix.py"}
    registered_sources = registration.get("source_hashes", {})
    require(required.issubset(registered_sources), "COMPLETE_PRODUCER_AND_INDEPENDENT_SOURCE_FREEZE_REQUIRED")
    for name, value in registered_sources.items():
        require(type(name) is str and not Path(name).is_absolute() and ".." not in Path(name).parts,
                "RELATIVE_FROZEN_SOURCE_REQUIRED")
        path = root / name
        require(not path.is_symlink() and path.is_file() and sha(path) == value,
                "RECOVERY_REGISTERED_SOURCE_CHANGED:" + name)
    financial_sources = {name: value for name, value in financial["source_hashes"].items()
                         if not name.startswith(".github/workflows/")}
    for name, value in financial_sources.items():
        path = root / name
        require(not path.is_symlink() and path.is_file() and sha(path) == value,
                "FROZEN_FINANCIAL_SOURCE_CHANGED:" + name)
    require(len(financial_sources) == 71, "ORIGINAL_71_NONWORKFLOW_SOURCE_CLOSURE_REQUIRED")
    return financial, registration, {name: registered_sources[name] for name in SOURCES}


def audit_current(source, folder):
    """Do not accept a historical audit merely because the account ID matches."""
    before = public_input_hashes(folder)
    started = time.process_time()
    row = audit_arm(source, folder)
    elapsed = time.process_time() - started
    require(public_input_hashes(folder) == before, "INPUT_CHANGED_DURING_FRESH_NATIVE_AUDIT")
    require(row.get("accepted") is True, "CURRENT_NATIVE_REPLAY_NOT_ACCEPTED")
    return row, before, elapsed


def verify_actual_public_tail(original_folder, exported):
    tape_path = original_folder / "account.sqlite.actions.jsonl"
    require(not tape_path.is_symlink() and tape_path.is_file()
            and tape_path.stat().st_size <= 64_000_000, "REGULAR_PUBLIC_DURABLE_TAPE_REQUIRED")
    raw = tape_path.read_bytes()
    lines = raw.splitlines()
    require(bool(lines), "NONEMPTY_PUBLIC_DURABLE_TAPE_REQUIRED")
    header = strict_json(lines[0])
    require(same(header["config"], exported["ledger"]["config"]), "DURABLE_NATIVE_CONFIG_CHANGED")
    expected = canonical(header) + b"\n" + b"".join(canonical(row) + b"\n" for row in exported["ledger"]["actions"])
    require(raw == expected, "FINAL_EXPORT_DIFFERS_FROM_ACTUAL_ORIGINAL_PUBLIC_TAPE")
    body = read(original_folder / "account.sqlite.connected-journal.json")["body"]
    require(same(body, exported["connected_journal"]), "FINAL_EXPORT_DIFFERS_FROM_ACTUAL_ORIGINAL_PUBLIC_JOURNAL")
    return {"native_tape_sha256": hashlib.sha256(raw).hexdigest(),
            "journal_body_sha256": digest(body), "native_action_count": len(exported["ledger"]["actions"])}


def preserved_attempts(folder, prefix):
    dirs = sorted(folder.glob(prefix + "*"))
    require(bool(dirs) and [path.name for path in dirs] == [f"{prefix}{i:04d}" for i in range(1, len(dirs) + 1)],
            "CONTIGUOUS_PRESERVED_ATTEMPTS_REQUIRED")
    require(all(path.is_dir() and not path.is_symlink() for path in dirs), "REGULAR_ATTEMPT_DIRECTORIES_REQUIRED")
    return dirs


def check_preopen_public(before):
    raw = canonical(before["native_header"]) + b"\n"
    raw += b"".join(canonical(row) + b"\n" for row in before["native_actions"])
    require(type(before["native_action_count"]) is int
            and before["native_action_count"] == len(before["native_actions"])
            and before["native_actions_sha256"] == digest(before["native_actions"])
            and before["native_tape_bytes"] == len(raw)
            and before["native_tape_sha256"] == hashlib.sha256(raw).hexdigest()
            and before["journal_body_sha256"] == digest(before["connected_journal"])
            and type(before["journal_entry_count"]) is int
            and before["journal_entry_count"] == len(before["connected_journal"]["entries"]),
            "PREOPEN_PUBLIC_CONTENT_AND_IDENTITIES_DISAGREE")


def check_producer(folder, job, identity, source_hashes, registration_commit, registration_sha256, public_hashes):
    result = read(folder / "RECOVERY_RESULT.json")
    recipe = recipe_for_recovery(job)
    require(result.get("schema") == "portfolio071/recovery-result/v1" and result.get("accepted") is True,
            "ACCEPTED_RECOVERY_PRODUCER_RECEIPT_REQUIRED")
    require(result.get("id") == expected_id(job) and same(result.get("recipe"), recipe)
            and same(result.get("sources"), source_hashes)
            and result.get("registration_commit") == registration_commit
            and result.get("registration_sha256") == registration_sha256,
            "RECOVERY_PRODUCER_RECIPE_OR_SOURCE_IDENTITY_CHANGED")
    require(result.get("original_directory") == job["directory"]
            and result.get("recovery_directory") == job["directory"]
            and type(result.get("new_equity_or_financing")) is int and result["new_equity_or_financing"] == 0
            and type(result.get("automatic_retries")) is int and result["automatic_retries"] == 0,
            "EXACT_ORIGINAL_ACCOUNT_NO_NEW_CAPITAL_OR_AUTOMATIC_RETRY_REQUIRED")
    require(same(result.get("public_output_sha256"), public_hashes), "PRODUCER_RECEIPT_HAS_STALE_PUBLIC_INPUTS")
    attempts = preserved_attempts(folder, "recovery-attempt-")
    require(result.get("attempt_directory") == attempts[-1].name, "LAST_PRESERVED_ATTEMPT_MUST_COMPLETE_CONTROLLER")
    evidence = []
    for position, attempt in enumerate(attempts):
        start = read(attempt / "ATTEMPT_START.json")
        before = read(attempt / "PREOPEN_PUBLIC.json")
        check_preopen_public(before)
        require(start.get("schema") == "portfolio071/recovery-attempt/v1"
                and start.get("development") is False and start.get("original_account_existed") is True
                and type(start.get("attempt")) is int and start["attempt"] == position + 1
                and same(start.get("recipe"), recipe) and same(start.get("sources"), source_hashes)
                and start.get("registration_commit") == registration_commit
                and start.get("registration_sha256") == registration_sha256
                and start.get("original_directory") == job["directory"]
                and start.get("opening") == job["capital_usd"] * 1_000_000 and start.get("working") == 0
                and start.get("contract") == "portfolio071-" + digest(expected_id(job))[:24]
                and start.get("manifest_sha256") == identity["manifest_canonical_sha256"]
                and start.get("preopen_public_sha256") == digest(before),
                "EXACT_CANONICAL_PREOPEN_ATTEMPT_BINDING_REQUIRED")
        if position == 0:
            require(before["native_tape_sha256"] == identity["durable_actions_file_sha256"]
                    and before["native_tape_bytes"] == identity["durable_actions_file_bytes"]
                    and before["journal_body_sha256"] == identity["journal_body_sha256"]
                    and before["native_action_count"] == identity["native_actions"]
                    and before["journal_entry_count"] == identity["journal_entries"],
                    "FIRST_PREOPEN_DIFFERS_FROM_INDEPENDENT_FROZEN_INTERRUPTION")
        names = ("ATTEMPT_START.json", "PREOPEN_PUBLIC.json", "NATIVE_REOPEN.json", "EXACT_CUTOVER.json", "ATTEMPT_RESULT.json")
        hashes = {name: sha(attempt / name) for name in names if (attempt / name).is_file()}
        ended = read(attempt / "ATTEMPT_RESULT.json") if "ATTEMPT_RESULT.json" in hashes else None
        evidence.append({"directory": attempt.name, "public_file_sha256": hashes,
                         "disposition": ended.get("status") if ended else "INTERRUPTED_WITHOUT_TERMINAL_RECEIPT_RETAINED"})
    last = attempts[-1]
    ended, cutover, reopened = [read(last / name) for name in ("ATTEMPT_RESULT.json", "EXACT_CUTOVER.json", "NATIVE_REOPEN.json")]
    before = read(last / "PREOPEN_PUBLIC.json")
    require(ended.get("accepted") is True and ended.get("status") == "CONTROLLER_CONTEXT_COMPLETE"
            and same(cutover, result.get("cutover")) and same(cutover, ended.get("cutover"))
            and same(reopened, result.get("native_reopen")), "PRODUCER_FINAL_ATTEMPT_NOT_EXACT_COMPLETE_CUTOVER")
    require(reopened.get("accepted") is True and reopened.get("original_public_prefix_sha256") == digest(before)
            and cutover.get("accepted") is True
            and cutover.get("matched_original_native_actions") == reopened.get("reopened_native_actions")
            and cutover.get("matched_original_journal_entries") == reopened.get("original_journal_entries")
            and cutover.get("reconstructed_public_export_sha256") == cutover.get("authenticated_live_export_sha256")
            == reopened.get("reopened_public_export_sha256")
            and cutover.get("checkpoint_state_and_result_reconstructed") is True
            and type(cutover.get("new_operation_count_at_cutover")) is int and cutover["new_operation_count_at_cutover"] == 0,
            "EXACT_COMPLETE_HISTORICAL_RECONSTRUCTION_REQUIRED")
    require(result["final_public_export_sha256"] == digest(read(folder / "native-after-drain.json")),
            "FINAL_PRODUCER_EXPORT_BINDING_CHANGED")
    trajectory = read(folder / "trajectory.json")
    provenance = trajectory.get("recovery_provenance", {})
    require(provenance.get("same_original_account") is True
            and same(provenance.get("cutover"), cutover) and same(provenance.get("native_reopen"), reopened)
            and provenance.get("registration_commit") == registration_commit
            and provenance.get("registration_sha256") == registration_sha256
            and same(provenance.get("sources"), source_hashes), "TRAJECTORY_RECOVERY_PROVENANCE_CHANGED")
    return {"recovery_result_sha256": sha(folder / "RECOVERY_RESULT.json"), "attempts": evidence,
            "cutover": cutover, "reopen": reopened}


def check_schedule(base, registration_commit, registration_sha256, sources, registered_hashes, closed_hashes):
    folder = base / "recovery"
    value = read(folder / "RECOVERY_SCHEDULING_RESULT.json")
    require(value.get("schema") == "portfolio071/recovery-scheduling/v1" and value.get("accepted") is True
            and value.get("failures") == [] and value.get("full24_independent_acceptance") is False,
            "COMPLETED_RECOVERY_SCHEDULE_WITHOUT_INDEPENDENT_PROMOTION_REQUIRED")
    require(value.get("registration_commit") == registration_commit
            and value.get("registration_sha256") == registration_sha256
            and value.get("runner_sha256") == registered_hashes[RUNNER]
            and same(value.get("sources"), sources), "RECOVERY_SCHEDULER_SOURCE_BINDING_CHANGED")
    binding = value["financial_and_orchestration_binding"]
    require(binding.get("economic_freeze_sha256") == FINANCIAL_FREEZE_SHA256
            and binding.get("orchestration_freeze_sha256") == ORCHESTRATION_FREEZE_SHA256
            and binding.get("original_source_count") == 72
            and len(binding.get("runtime_source_hashes", {})) == 56,
            "SCHEDULER_FROZEN_FINANCIAL_RUNTIME_BINDING_CHANGED")
    require(type(value.get("worker_count")) is int
            and type(value.get("resource_limits", {}).get("conservative_worker_maximum")) is int
            and 1 <= value["worker_count"] <= value["resource_limits"]["conservative_worker_maximum"] <= 4,
            "REGISTERED_MEASURED_WORKER_BOUND_REQUIRED")
    require(value.get("recovered_indices") == RECOVERED_INDICES and value.get("unopened_indices") == FRESH
            and value.get("preserved_complete_indices") == CLOSED
            and value.get("completed_indices") == RECOVERED_INDICES + FRESH
            and same(value.get("closed_public_identities"), closed_hashes)
            and type(value.get("automatic_retries")) is int and value["automatic_retries"] == 0,
            "EXACT_RECOVERY_PARTITION_AND_NO_RETRY_REQUIRED")
    scheduled, retained = value["scheduled_indices"], value["retained_indices"]
    require(all(type(i) is int for i in scheduled + retained)
            and len(scheduled + retained) == len(set(scheduled + retained)) == 8
            and set(scheduled + retained) == set(RECOVERED_INDICES + FRESH), "EXACT_SCHEDULED_RETAINED_PARTITION_REQUIRED")
    statuses = value["execution_statuses"]
    require(len(statuses) == len(scheduled) and {row["index"] for row in statuses} == set(scheduled)
            and all(row["status"] == ("COMPLETED_FIRST_ORIGINAL_EXECUTION" if row["index"] == 23
                                      else "COMPLETED_SAME_ACCOUNT_RECOVERY") for row in statuses),
            "EVERY_SCHEDULED_ACCOUNT_MUST_HAVE_EXACT_COMPLETION_DISPOSITION")
    attempts = preserved_attempts(folder, "stage-attempt-")
    require(same(read(attempts[-1] / "RESULT.json"), value), "LAST_SCHEDULER_RECEIPT_MISMATCH")
    receipts = []
    for attempt in attempts:
        start = read(attempt / "START.json")
        require(start.get("registration_commit") == registration_commit and start.get("registration_sha256") == registration_sha256
                and same(start.get("sources"), sources), "PRESERVED_SCHEDULER_ATTEMPT_SOURCE_MISMATCH")
        receipts.append({"directory": attempt.name, "start_sha256": sha(attempt / "START.json"),
                         "result_sha256": sha(attempt / "RESULT.json") if (attempt / "RESULT.json").is_file() else None})
    # The original schedulers really did stop; a recovery report cannot turn
    # their absent terminal success into an uninterrupted successful process.
    require(not (base / "ORCHESTRATION.json").exists()
            and not (base / "economics/ORCHESTRATION_RESULT.json").exists(),
            "ORIGINAL_INTERRUPTED_ORCHESTRATION_MUST_REMAIN_UNCOMPLETED")
    return value, {"receipt_sha256": sha(folder / "RECOVERY_SCHEDULING_RESULT.json"), "attempts": receipts}


def copy_public_view(output, base, evidence, campaign):
    view = output / "public-campaign-view"
    view.mkdir(exist_ok=False)
    write_new(view / "campaign.json", campaign)
    for row in evidence:
        require(set(row["input_sha256"]) == set(PUBLIC_FILES), "ONLY_FOUR_PUBLIC_FILES_ALLOWED_IN_VIEW")
        source, destination = base / row["public_source"], view / row["directory"]
        destination.mkdir(exist_ok=False)
        for name in PUBLIC_FILES:
            raw = (source / name).read_bytes()
            require(hashlib.sha256(raw).hexdigest() == row["input_sha256"][name], "PUBLIC_VIEW_SOURCE_CHANGED")
            with (destination / name).open("xb") as stream:
                stream.write(raw)
    return view


def assemble(root, reproduction, output, recovery_freeze, registration_commit):
    root, base, output, recovery_freeze = map(lambda p: Path(p).absolute(), (root, reproduction, output, recovery_freeze))
    require(not base.is_symlink() and base.is_dir() and not output.exists(), "ORIGINAL_ROOT_AND_FRESH_ASSEMBLY_DIRECTORY_REQUIRED")
    financial, registration, sources = check_sources(root, recovery_freeze, registration_commit)
    first, second = read(root / PREFIX_PATH), read(root / SECOND_PREFIX_PATH)
    identities = {row["index"]: row for row in first["prefixes"] + second["prefixes"]}
    require(second["completed_before_recovery"] == CLOSED and second["never_started_indices"] == FRESH,
            "EXACT_SECOND_INTERRUPTION_PARTITION_REQUIRED")
    freeze_sha = sha(recovery_freeze)
    schedule, scheduling_evidence = check_schedule(base, registration_commit, freeze_sha, sources,
                                                  registration["source_hashes"], second["completed_public_file_sha256"])
    output.mkdir(parents=True, exist_ok=False)
    started = time.process_time()
    jobs, mapping, audits, records, evidence, failures = recipes(), path_map(), [], [], [], []
    frozen_auditor = financial["source_hashes"]["portfolio071/verify_economics.py"]
    for job, mapped in zip(jobs, mapping):
        folder = base / mapped["public_source"]
        try:
            require(folder.is_dir() and not folder.is_symlink(), "REGULAR_EXACT_MAPPED_PUBLIC_DIRECTORY_REQUIRED")
            checked, hashes, elapsed = audit_current(base / "native-source", folder)
            manifest, trajectory, native, drained = [read(folder / name) for name in PUBLIC_FILES]
            require(trajectory["id"] == expected_id(job)
                    and all(same(trajectory[key], job[key]) for key in ("world", "capital_usd", "policy", "earned_only_k2", "infer_idle_days"))
                    and trajectory["investor_test"]["horizon_days"] == 1825,
                    "EXACT_FROZEN_ORDERED_RECIPE_REQUIRED")
            contract = "portfolio071-" + digest(expected_id(job))[:24]
            for exported in (native, drained):
                for config in (exported["ledger"]["config"], exported["connected_journal"]):
                    require(config["contract"] == contract and type(config["opening"]) is int
                            and config["opening"] == job["capital_usd"] * 1_000_000 and config["working"] == 0
                            and config["manifest_sha256"] == digest(manifest), "EXACT_ORIGINAL_NATIVE_CONTRACT_AND_EQUITY_REQUIRED")
                closure = exported["connected_journal"]["source"]["files"]
                require(all(financial["source_hashes"].get(name) == value
                            and sha(base / "native-source" / name) == value for name, value in closure.items()),
                        "ORIGINAL_STAGED_NATIVE_SOURCE_CHANGED")
            require(all(financial["source_hashes"].get(name) == value for name, value in manifest["source_hashes"].items())
                    and len(manifest["jobs"]) == trajectory["actual_scientific_artifacts"] == 2
                    and manifest["account_namespace"] == "adaptive012", "FROZEN_TWO_ARTIFACT_CATALOG_REQUIRED")
            row_evidence = {**mapped, "id": trajectory["id"], "input_sha256": hashes,
                            "contract": contract, "manifest_sha256": digest(manifest),
                            "source_closure_sha256": digest(closure), "catalog_sha256": digest(manifest["jobs"]),
                            "actual_original_public_tail": verify_actual_public_tail(base / mapped["original_account_directory"], drained)}
            if job["index"] in CLOSED:
                require(hashes == second["completed_public_file_sha256"][job["directory"]],
                        "PREVIOUSLY_CLOSED_PUBLIC_FILES_CHANGED")
            elif job["index"] in RECOVERED_INDICES:
                row_evidence["recovery"] = check_producer(folder, job, identities[job["index"]], sources,
                                                           registration_commit, freeze_sha, hashes)
            else:
                require("recovery_provenance" not in trajectory, "ARM23_MUST_BE_FIRST_ORIGINAL_EXECUTION")
            require(public_input_hashes(folder) == hashes, "PUBLIC_INPUT_CHANGED_DURING_ASSEMBLY")
            audits.append({**checked, "audit_cpu_seconds": elapsed, "auditor_source_sha256": frozen_auditor})
            records.append(compact(trajectory))
            evidence.append(row_evidence)
            print(json.dumps({"index": job["index"], "accepted": True, "source": mapped["public_source"]}), flush=True)
        except Exception as error:
            failure = {"arm": job["directory"], "accepted": False, "failure": type(error).__name__ + ": " + str(error)}
            audits.append(failure); failures.append(failure)
            print(json.dumps(failure), flush=True)
    native_report = {"schema": "portfolio071/independent-economic-audit/v1", "accepted": not failures and len(audits) == 24,
                     "registered_arms": 24, "arms": audits, "verifier_sha256": frozen_auditor,
                     "identity_bindings": evidence, "process_cpu_seconds": time.process_time() - started,
                     "scope": "Fresh frozen native audit of every current mapped output; original accounts never reopened by verifier."}
    native_path = output / "INDEPENDENT_NATIVE_RECONCILIATION.json"
    write_new(native_path, native_report)
    if native_report["accepted"]:
        try:
            prefix = check_prefixes(root, base, native_path)
        except Exception as error:
            prefix = {"accepted": False, "failure": type(error).__name__ + ": " + str(error)}
    else:
        prefix = {"accepted": False, "not_run": "Full 24-account current native admission failed."}
    prefix_path = output / "INDEPENDENT_RECOVERED_PREFIX_AUDIT.json"
    write_new(prefix_path, prefix)
    checks = {
        "all24_current_native_audits": native_report["accepted"],
        "all7_original_prefixes_and16_closed_outputs": prefix["accepted"],
        "exact24_ordered_identities": len(records) == 24 and [r["id"] for r in records] == [expected_id(j) for j in jobs],
        "unique24_contracts": len(evidence) == 24 and len({r["contract"] for r in evidence}) == 24,
        "same_frozen_manifest_catalog_and_runtime": len(evidence) == 24 and all(len({r[k] for r in evidence}) == 1
            for k in ("manifest_sha256", "catalog_sha256", "source_closure_sha256")),
        "source_files_unchanged_at_end": False,
        "all_current_input_hashes_unchanged_at_end": all(public_input_hashes(base / r["public_source"]) == r["input_sha256"] for r in evidence),
        "scheduler_compact_rows_match_current_outputs": same(schedule["compact_completed_records"],
            [records[i] for i in RECOVERED_INDICES + FRESH]) if len(records) == 24 else False,
    }
    try:
        check_sources(root, recovery_freeze, registration_commit)
        checks["source_files_unchanged_at_end"] = sha(recovery_freeze) == freeze_sha
    except Exception as error:
        failures.append({"failure": type(error).__name__ + ": " + str(error)})
    accepted = all(checks.values())
    report = {**native_report, "accepted": accepted, "assembly_checks": checks,
              "assembly_checker_sha256": sha(root / THIS_SOURCE), "registration_commit": registration_commit,
              "registration_sha256": freeze_sha, "scheduling_evidence": scheduling_evidence,
              "prefix_report_sha256": sha(prefix_path), "native_report_sha256": sha(native_path),
              "process_cpu_seconds": time.process_time() - started,
              "pre_interruption_cpu_and_wall_seconds": None,
              "resource_scope": "This independent fresh24 audit, seven additional prefix reaudits and assembly only; lost interrupted-process telemetry is unknown.",
              "failures": failures,
              "scope": "24 separate conditional accounts, exact same-account continuations and fixed original recipes; no pooled profit, unbroken original scheduler, observed demand or external commerce claim."}
    view = None
    if accepted:
        try:
            campaign = _campaign(records, read(base / "native-manifest.json"))
            for threshold, key in ((1_000_000_000, "milestone_1b_count"), (3_000_000_000, "milestone_3b_count")):
                require(campaign[key] == sum(row["independent_trailing_profit_microUSD"] >= threshold * 1_000_000 for row in audits),
                        "INDEPENDENT_MILESTONE_COUNT_MISMATCH")
            write_new(output / "campaign.json", campaign)
            view = copy_public_view(output, base, evidence, campaign)
            require(all(public_input_hashes(base / row["public_source"]) == row["input_sha256"] for row in evidence),
                    "SOURCE_CHANGED_DURING_PUBLIC_VIEW_CREATION")
        except Exception as error:
            report["accepted"] = False
            report["failures"].append({"failure": type(error).__name__ + ": " + str(error)})
    write_new(output / "INDEPENDENT_ECONOMIC_AUDIT.json", report)
    write_new(output / "RECOVERY_PATH_MAP.json", {"schema": "portfolio071/recovery-path-map/v1", "accepted": report["accepted"],
               "registered_arms": 24, "paths": mapping, "current_identity_bindings": evidence})
    if report["accepted"]:
        write_new(view / "PUBLIC_VIEW.json", {"schema": "portfolio071/public-campaign-view/v1", "accepted": True,
                   "original_path_map_sha256": sha(output / "RECOVERY_PATH_MAP.json"),
                   "independent_audit_sha256": sha(output / "INDEPENDENT_ECONOMIC_AUDIT.json"),
                   "files_per_arm": list(PUBLIC_FILES), "private_operating_files_included": False,
                   "scope": "Exact public copies for read-only plotting and packaging; no native DB, private key or signed controller checkpoint is included."})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--reproduction-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--registration-commit", required=True)
    parser.add_argument("--recovery-freeze", type=Path, required=True)
    args = parser.parse_args()
    report = assemble(args.root, args.reproduction_output, args.output, args.recovery_freeze, args.registration_commit)
    print(json.dumps({"accepted": report["accepted"], "registered_arms": 24, "failures": report["failures"]}), flush=True)
    if not report["accepted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
