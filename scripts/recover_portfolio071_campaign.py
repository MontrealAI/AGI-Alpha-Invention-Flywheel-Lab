"""Resume seven original accounts and execute the sole never-opened recipe.

The original sixteen completed accounts remain read-only. A manual repeat after
an interruption retains completed outputs and reconstructs only unfinished
original histories under the same published recovery source. No automatic retry
or account replacement is implemented.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing
from pathlib import Path
import re
import time

from commercial.ledger import canonical, digest
from portfolio071.economics import World, compact, execute_trajectory
from portfolio071.recovery import (
    SOURCE_NAMES, public_before_open, read, recover_trajectory, same, sha, write_new,
)
from scripts.replay_portfolio071_parallel import (
    REPO, registered_jobs, select_workers, validate_completed, validate_freezes,
)

RECOVERED = [8, 9, 10, 11, 16, 17, 22]
FRESH = [23]
CLOSED = [0, 1, 2, 3, 4, 5, 6, 7, 12, 13, 14, 15, 18, 19, 20, 21]
REGISTRATION = REPO / "experiments/portfolio_20261102/RECOVERY_FREEZE.json"
PREFIX_RECORDS = (
    "experiments/portfolio_20261102/RECOVERY_PREFIX_IDENTITIES.json",
    "experiments/portfolio_20261102/RECOVERY_SECOND_PREFIX_IDENTITIES.json",
)


def check_registration(registration):
    if (registration.get("recovered_indices") != RECOVERED
            or registration.get("unopened_indices") != FRESH
            or registration.get("preserved_complete_indices") != CLOSED
            or registration.get("registered_total_accounts") != 24):
        raise ValueError("EXACT_SIXTEEN_CLOSED_SEVEN_PARTIAL_ONE_UNOPENED_REGISTRATION_REQUIRED")
    sources = registration.get("source_hashes", {})
    required = set(SOURCE_NAMES) | {"scripts/recover_portfolio071_campaign.py", *PREFIX_RECORDS}
    if not required.issubset(sources):
        raise ValueError("COMPLETE_RECOVERY_SOURCE_AND_PREFIX_FREEZE_REQUIRED")
    for name, expected in sources.items():
        path = REPO / name
        if not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("BOUNDED_RELATIVE_RECOVERY_SOURCE_REQUIRED")
        if path.is_symlink() or sha(path) != expected:
            raise ValueError("REGISTERED_RECOVERY_SOURCE_CHANGED:" + name)
    return {name: sources[name] for name in SOURCE_NAMES}


def original_prefix_identities():
    first, second = [read(REPO / name) for name in PREFIX_RECORDS]
    if (first["interrupted_indices"] != [8, 9, 10, 11]
            or second["additional_interrupted_indices"] != [16, 17, 22]
            or second["all_recovery_indices"] != RECOVERED
            or second["never_started_indices"] != FRESH):
        raise ValueError("EXACT_INDEPENDENT_SEVEN_PREFIX_RECORDS_REQUIRED")
    rows = {row["index"]: row for row in first["prefixes"] + second["prefixes"]}
    if sorted(rows) != RECOVERED:
        raise ValueError("EXACT_INDEPENDENT_SEVEN_PREFIX_IDENTITIES_REQUIRED")
    return rows, second["completed_public_file_sha256"]


def check_original_prefix(folder, identity, *, allow_appended):
    before = public_before_open(folder / "account.sqlite")
    count = identity["native_actions"]
    entries = before["connected_journal"]["entries"]
    complete_count = identity.get("completed_journal_entries", identity["journal_entries"])
    complete_digest = identity.get("completed_journal_entries_sha256", identity["journal_entries_sha256"])
    if (not same(before["native_header"], identity["durable_header"])
            or len(before["native_actions"]) < count
            or digest(before["native_actions"][:count]) != identity["native_actions_prefix_sha256"]
            or len(entries) < identity["journal_entries"]
            or digest(entries[:complete_count]) != complete_digest):
        raise ValueError("ORIGINAL_REGISTERED_NATIVE_OR_COMPLETE_JOURNAL_PREFIX_CHANGED")
    if (sha(folder / "manifest.json") != identity["manifest_file_sha256"]
            or digest(read(folder / "manifest.json")) != identity["manifest_canonical_sha256"]):
        raise ValueError("ORIGINAL_MANIFEST_CHANGED")
    if not allow_appended:
        if (before["native_tape_sha256"] != identity["durable_actions_file_sha256"]
                or before["native_tape_bytes"] != identity["durable_actions_file_bytes"]
                or before["journal_body_sha256"] != identity["journal_body_sha256"]):
            raise ValueError("FIRST_RECOVERY_REQUIRES_EXACT_REGISTERED_INTERRUPTION_STATE")
    elif identity.get("pending_entry") is not None:
        old = identity["pending_entry"]
        current = entries[identity["pending_entry_index"]]
        immutable = {"key", "request", "plan", "funding", "attempt", "obligation_receipt"}
        if any(not same(old.get(key), current.get(key)) for key in immutable):
            raise ValueError("ORIGINAL_PENDING_INTENT_WAS_CHANGED")
        if current["status"] not in {"PENDING", "COMPLETE"}:
            raise ValueError("REGISTERED_PENDING_TERMS_INTENT_NOT_SUCCESSFULLY_RECOVERABLE")
    return {"original_native_actions": count, "current_native_actions": before["native_action_count"],
            "current_journal_entries": before["journal_entry_count"],
            "current_public_prefix_sha256": digest(before)}


def check_closed(campaign, expected):
    hashes = {}
    for index in CLOSED:
        name = f"arm-{index:02d}"
        folder = campaign / name
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("ALL_SIXTEEN_ORIGINAL_CLOSED_DIRECTORIES_REQUIRED")
        hashes[name] = {}
        for filename in ("manifest.json", "trajectory.json", "native-at-horizon.json", "native-after-drain.json"):
            path = folder / filename
            if path.is_symlink() or not path.is_file():
                raise ValueError("ALL_SIXTEEN_CLOSED_PUBLIC_HISTORIES_REQUIRED")
            hashes[name][filename] = sha(path)
    if not same(hashes, expected):
        raise ValueError("ORIGINAL_SIXTEEN_COMPLETED_ACCOUNT_BYTES_CHANGED")
    return hashes


def _job(base, job, registration_commit, registration_sha256, sources):
    base = Path(base)
    root, manifest = base / "native-source", read(base / "native-manifest.json")
    index = job["index"]
    kwargs = {"capital_usd": job["capital_usd"], "world": World(**job["world"]),
              "policy": job["policy"], "earned_only_k2": job["earned_only_k2"],
              "horizon_days": job["horizon_days"]}
    if index in RECOVERED:
        record = recover_trajectory(root, manifest,
            base / "economics" / job["directory"] / "account.sqlite",
            base / "recovery" / job["directory"],
            registration_commit=registration_commit, registration_sha256=registration_sha256,
            expected_source_hashes=sources, **kwargs)
    elif index == 23:
        record = execute_trajectory(root, manifest, base / "economics" / job["directory"], **kwargs)
    else:
        raise ValueError("UNREGISTERED_RECOVERY_JOB_REFUSED")
    return compact(record)


def run(reproduction_output, registration_commit, *, workers=None, resume_interrupted=False,
        recovery_freeze=REGISTRATION):
    if not re.fullmatch(r"[0-9a-f]{40}", registration_commit):
        raise ValueError("PUBLIC_RECOVERY_REGISTRATION_COMMIT_REQUIRED")
    base = Path(reproduction_output).absolute()
    if base.is_symlink() or not base.is_dir():
        raise ValueError("ORIGINAL_REPRODUCTION_ROOT_REQUIRED")
    recovery_freeze = Path(recovery_freeze)
    registration = read(recovery_freeze)
    sources = check_registration(registration)
    prefix_rows, closed_expected = original_prefix_identities()
    campaign, recovered = base / "economics", base / "recovery"
    manifest = read(base / "native-manifest.json")
    binding = validate_freezes(base / "native-source", manifest)
    if (binding["economic_freeze_sha256"] != registration["financial_freeze_sha256"]
            or binding["orchestration_freeze_sha256"] != registration["orchestration_freeze_sha256"]):
        raise ValueError("REGISTERED_FINANCIAL_AND_ORCHESTRATION_IDENTITIES_REQUIRED")
    closed_hashes = check_closed(campaign, closed_expected)
    if (recovered / "RECOVERY_SCHEDULING_RESULT.json").exists():
        raise ValueError("COMPLETED_RECOVERY_SCHEDULE_MUST_NOT_BE_REEXECUTED")
    if recovered.exists() and not resume_interrupted:
        raise ValueError("EXPLICIT_MANUAL_RESUME_REQUIRED_FOR_EXISTING_RECOVERY_STAGE")
    recovered.mkdir(exist_ok=True)
    jobs = {job["index"]: job for job in registered_jobs()}
    retained, scheduled, prefix_checks = {}, [], {}
    for index in RECOVERED:
        source_folder, output = campaign / f"arm-{index:02d}", recovered / f"arm-{index:02d}"
        if (source_folder / "trajectory.json").exists():
            raise ValueError("ORIGINAL_INTERRUPTED_OUTPUT_MUST_NOT_BE_RELABELLED_UNINTERRUPTED")
        prefix_checks[index] = check_original_prefix(source_folder, prefix_rows[index], allow_appended=resume_interrupted)
        if (output / "trajectory.json").exists() or (output / "RECOVERY_RESULT.json").exists():
            if not resume_interrupted or not (output / "trajectory.json").is_file() or not (output / "RECOVERY_RESULT.json").is_file():
                raise ValueError("EXACT_COMPLETED_RECOVERY_PAIR_REQUIRED")
            row, audit = validate_completed(base / "native-source", manifest, output, jobs[index])
            receipt = read(output / "RECOVERY_RESULT.json")
            if (receipt["accepted"] is not True or receipt["registration_commit"] != registration_commit
                    or receipt["registration_sha256"] != sha(recovery_freeze)
                    or not same(receipt["sources"], sources)
                    or any(sha(output / name) != value for name, value in receipt["public_output_sha256"].items())):
                raise ValueError("RETAINED_RECOVERY_SOURCE_OR_RESULT_CHANGED")
            retained[index] = {"record": row, "audit": audit, "recovery_result_sha256": sha(output / "RECOVERY_RESULT.json")}
        else:
            scheduled.append(jobs[index])
    fresh = campaign / "arm-23"
    if fresh.exists():
        if not resume_interrupted:
            raise ValueError("FIRST_EXECUTION_ARM23_MUST_HAVE_ABSENT_PATH")
        # This original controller has no policy checkpoint. An incomplete fresh
        # arm requires a further explicit recovery registration, never a reset.
        if not (fresh / "trajectory.json").is_file():
            raise ValueError("INTERRUPTED_ARM23_REQUIRES_NEW_EXPLICIT_RECOVERY_REGISTRATION")
        row, audit = validate_completed(base / "native-source", manifest, fresh, jobs[23])
        retained[23] = {"record": row, "audit": audit}
    else:
        scheduled.append(jobs[23])
    count, limits = select_workers(workers)
    previous = sorted(recovered.glob("stage-attempt-*"))
    number = len(previous) + 1
    if [path.name for path in previous] != [f"stage-attempt-{i:04d}" for i in range(1, number)]:
        raise ValueError("CONTIGUOUS_PRESERVED_STAGE_ATTEMPTS_REQUIRED")
    attempt = recovered / f"stage-attempt-{number:04d}"
    attempt.mkdir(exist_ok=False)
    start = {"schema": "portfolio071/recovery-scheduling/v1", "registration_commit": registration_commit,
        "registration_sha256": sha(recovery_freeze), "runner_sha256": sha(__file__), "sources": sources,
        "financial_and_orchestration_binding": binding, "recovered_indices": RECOVERED,
        "unopened_indices": FRESH, "preserved_complete_indices": CLOSED,
        "scheduled_indices": [job["index"] for job in scheduled], "retained_indices": sorted(retained),
        "closed_public_identities": closed_hashes, "current_original_prefix_checks": prefix_checks,
        "manual_resume": resume_interrupted, "automatic_retries": 0,
        "worker_count": count, "resource_limits": limits,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Seven exact original account continuations and one original fresh recipe; sixteen completed accounts untouched."}
    write_new(attempt / "START.json", start)
    records, statuses, failures, futures = {i: v["record"] for i, v in retained.items()}, {}, [], {}
    started = time.monotonic()
    try:
        with ProcessPoolExecutor(max_workers=count, mp_context=multiprocessing.get_context("spawn")) as pool:
            for job in scheduled:
                future = pool.submit(_job, str(base), job, registration_commit, sha(recovery_freeze), sources)
                futures[future] = job
            for future in as_completed(futures):
                job = futures[future]
                try:
                    records[job["index"]] = future.result()
                    status = {"index": job["index"], "status": "COMPLETED_SAME_ACCOUNT_RECOVERY" if job["index"] in RECOVERED else "COMPLETED_FIRST_ORIGINAL_EXECUTION"}
                except BaseException as error:
                    status = {"index": job["index"], "status": "FAILED_NO_AUTOMATIC_RETRY", "error_type": type(error).__name__, "error": str(error)}
                    failures.append(status)
                statuses[job["index"]] = status
                print(json.dumps(status, sort_keys=True), flush=True)
    except BaseException as error:
        failures.append({"status": "SCHEDULING_INFRASTRUCTURE_INTERRUPTION", "error_type": type(error).__name__, "error": str(error)})
    for job in scheduled:
        if job["index"] not in statuses:
            statuses[job["index"]] = {"index": job["index"], "status": "UNRESOLVED_SUBMISSION_OR_EXECUTION_NO_RETRY"}
            failures.append(statuses[job["index"]])
    try:
        check_registration(registration)
        if check_closed(campaign, closed_expected) != closed_hashes or validate_freezes(base / "native-source", manifest) != binding:
            raise ValueError("PROTECTED_SOURCE_OR_CLOSED_HISTORY_CHANGED")
    except BaseException as error:
        failures.append({"status": "FINAL_SOURCE_OR_RETENTION_FAILURE", "error_type": type(error).__name__, "error": str(error)})
    result = {**start, "accepted": not failures and set(records) == set(RECOVERED + FRESH),
        "completed_indices": sorted(records), "execution_statuses": [statuses[i] for i in sorted(statuses)],
        "retained_completed": retained, "compact_completed_records": [records[i] for i in sorted(records)],
        "failures": failures, "wall_seconds": time.monotonic() - started,
        "full24_independent_acceptance": False,
        "remaining_gate": "Independent full24 native audits, original-prefix proofs and explicit recovered-output assembly."}
    write_new(attempt / "RESULT.json", result)
    if result["accepted"]:
        write_new(recovered / "RECOVERY_SCHEDULING_RESULT.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reproduction-output", type=Path, required=True)
    parser.add_argument("--registration-commit", required=True)
    parser.add_argument("--workers", type=int)
    parser.add_argument("--recovery-freeze", type=Path, default=REGISTRATION)
    parser.add_argument("--resume-interrupted", action="store_true")
    args = parser.parse_args()
    result = run(args.reproduction_output, args.registration_commit, workers=args.workers,
                 resume_interrupted=args.resume_interrupted, recovery_freeze=args.recovery_freeze)
    print(json.dumps({"accepted": result["accepted"], "completed_indices": result["completed_indices"]}, sort_keys=True))
    if not result["accepted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
