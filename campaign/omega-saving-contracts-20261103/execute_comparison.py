#!/usr/bin/env python3
"""Execute and independently replay every registered account without resetting it.

Each subprocess imports its own frozen runtime and owns one authenticated account.
Logs and per-attempt receipts survive interruption. A later invocation resumes the
same account, or audits a completed one. No timeout or favorable-result filter is
used. Parallelism changes only wall-clock execution, never information or money.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    temp = path.with_name(path.name + ".new")
    temp.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")
    os.replace(temp, path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--cases", help="Optional comma-separated registered IDs; never changes the registration")
    args = p.parse_args()
    if args.workers < 1:
        raise ValueError("POSITIVE_EXECUTION_CONCURRENCY_REQUIRED")
    output = args.output.resolve()
    matrix = read(output / "MATRIX.json")
    selected = set(args.cases.split(",")) if args.cases else None
    jobs = []
    for row in matrix["variants"]:
        directory = output / row["directory"]
        if directory.resolve().parent != output:
            raise ValueError("LOCAL_REGISTERED_VARIANT_REQUIRED")
        reg, source = read(directory / "REGISTRATION.json"), read(directory / "SOURCE.json")
        if source["sha256"] != row["source_sha256"] or source["registration_sha256"] != row["registration_sha256"]:
            raise ValueError("MATRIX_SOURCE_OR_REGISTRATION_CHANGED")
        jobs.extend((directory, case["id"]) for case in reg["cases"])
    ids = [case_id for _, case_id in jobs]
    if len(set(ids)) != len(ids) or len(jobs) != matrix["registered_financial_accounts"]:
        raise ValueError("EXACT_UNIQUE_REGISTERED_ACCOUNT_DENOMINATOR_REQUIRED")
    if selected is not None and not selected.issubset(ids):
        raise ValueError("UNREGISTERED_CASE_SELECTION")

    logs = output / "execution"
    logs.mkdir(exist_ok=True)
    receipt_path = logs / "EXECUTION.json"
    receipt = read(receipt_path) if receipt_path.exists() else {
        "schema": "omega-savings/execution/v1", "created_utc": now(), "attempts": [],
        "matrix_sha256": hashlib.sha256((output / "MATRIX.json").read_bytes()).hexdigest()}
    if receipt["matrix_sha256"] != hashlib.sha256((output / "MATRIX.json").read_bytes()).hexdigest():
        raise ValueError("EXECUTION_MATRIX_CHANGED")
    lock = threading.Lock()
    run = {"started_utc": now(), "workers": args.workers, "selected": sorted(selected) if selected else "all",
           "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "cases": {}}
    receipt["attempts"].append(run)
    save(receipt_path, receipt)
    attempt = len(receipt["attempts"])
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", PYTHONUNBUFFERED="1")

    def record(case_id, **changes):
        with lock:
            run["cases"].setdefault(case_id, {}).update(changes)
            save(receipt_path, receipt)
        print(json.dumps({"case_id": case_id, **changes}, sort_keys=True), flush=True)

    def execute(job):
        directory, case_id = job
        record(case_id, status="running", started_utc=now())
        start = time.monotonic()
        try:
            # A persistent file is harmless; the OS lock, not its existence,
            # prevents concurrent drivers from opening this same account.
            with (logs / (case_id + ".lock")).open("a") as handle:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                folder = directory / "cases" / case_id
                actions = ["audit"] if (folder / "RESULT.json").exists() else ["operate", "audit"]
                for action in actions:
                    log = logs / f"{case_id}.{attempt}.{action}.log"
                    command = [sys.executable, "-m", "omega_savings.runner", action,
                               "--output", str(directory), "--case", case_id]
                    with log.open("wb") as stream:
                        process = subprocess.run(command, cwd=directory / "source", env=env,
                                                 stdout=stream, stderr=subprocess.STDOUT)
                    if process.returncode:
                        record(case_id, status="failed", action=action, returncode=process.returncode,
                               log=str(log.relative_to(output)), elapsed_seconds=time.monotonic() - start,
                               completed_utc=now())
                        return False
                    if action == "audit":
                        audited = json.loads(log.read_text())
                        if not audited.get("accepted"):
                            raise ValueError("INDEPENDENT_AUDIT_NOT_ACCEPTED")
                        save(folder / "INDEPENDENT_AUDIT.json", audited)
                result = read(folder / "RESULT.json")
                if result.get("complete") is not True:
                    raise ValueError("COMPLETE_REGISTERED_HORIZON_REQUIRED")
                record(case_id, status="accepted", elapsed_seconds=time.monotonic() - start,
                       completed_utc=now(), source_sha256=result["source_sha256"],
                       native_actions_sha256=result["account_actions_sha256"])
                return True
        except Exception as exc:
            record(case_id, status="failed", exception=type(exc).__name__, message=str(exc),
                   elapsed_seconds=time.monotonic() - start, completed_utc=now())
            return False

    chosen = [job for job in jobs if selected is None or job[1] in selected]
    # Start the primary immediately and make inexpensive controls available
    # without queuing them behind every long positive-demand account. This is
    # execution scheduling only: no policy observes labels or another account.
    def execution_order(job):
        case_id = job[1]
        if job[0].name == "primary" and case_id == "positive-adaptive-701":
            rank = 0
        elif "-no_entry-" in case_id:
            rank = 1
        elif "-capability_only-" in case_id:
            rank = 2
        elif not case_id.startswith("positive-"):
            rank = 3
        else:
            rank = 4
        return rank, ids.index(case_id)
    chosen.sort(key=execution_order)
    okay = True
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(execute, job) for job in chosen]
        for future in as_completed(futures):
            okay = future.result() and okay
    summaries = []
    for row in matrix["variants"]:
        directory = output / row["directory"]
        log = logs / f"{row['variant']}.{attempt}.summary.log"
        with log.open("wb") as stream:
            process = subprocess.run([sys.executable, "-m", "omega_savings.runner", "summary", "--output", str(directory)],
                                     cwd=directory / "source", env=env, stdout=stream, stderr=subprocess.STDOUT)
        if process.returncode:
            okay = False
            summaries.append({"variant": row["variant"], "summary_failed": process.returncode})
        else:
            summaries.append({"variant": row["variant"], **read(directory / "COMPARISON.json")})
    run["finished_utc"] = now()
    run["all_selected_accepted"] = okay
    save(receipt_path, receipt)
    audited_ids = {case_id for directory, case_id in jobs
                   if (directory / "cases" / case_id / "INDEPENDENT_AUDIT.json").exists()
                   and read(directory / "cases" / case_id / "INDEPENDENT_AUDIT.json").get("accepted")}
    complete = okay and len(audited_ids) == len(jobs) and all(row.get("complete") for row in summaries)
    save(output / "ALL_COMPARISONS.json", {"schema": "omega-savings/all-comparisons/v1",
         "complete": complete, "registered_accounts": len(jobs), "independently_audited_accounts": len(audited_ids),
         "uncompleted_or_unaudited": sorted(set(ids) - audited_ids), "variants": summaries,
         "accounts_independent_never_pooled": True})
    print(json.dumps({"all_selected_accepted": okay, "complete_registered_comparison": complete,
                      "independently_audited_accounts": len(audited_ids), "registered_accounts": len(jobs)}), flush=True)
    return 0 if okay else 1


if __name__ == "__main__":
    raise SystemExit(main())
