"""Execute only the twelve never-started recipes after a preserved interruption.

This is a scheduling amendment, not recovery of an incomplete account. The
original controller and native account implementation are imported unchanged.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time

from commercial.ledger import canonical
from scripts.replay_portfolio071_parallel import (
    REPO, _schedule, load, registered_jobs, select_workers, sha,
    validate_freezes, write_new,
)

REGISTRATION = REPO / "experiments/portfolio_20261102/UNOPENED_SCHEDULING_PREREGISTRATION.json"
INDICES = list(range(12, 24))


def protected_identities(campaign):
    """Read public records only; never open an owned Account or a signing key."""
    result = {}
    for index in range(8):
        arm = campaign / f"arm-{index:02d}"
        result[arm.name] = {}
        for name in ("manifest.json", "trajectory.json", "native-at-horizon.json", "native-after-drain.json"):
            path = arm / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("EIGHT_COMPLETED_ACCOUNT_PUBLIC_FILES_REQUIRED")
            result[arm.name][name] = sha(path)
    for index in range(8, 12):
        arm = campaign / f"arm-{index:02d}"
        path = arm / "account.sqlite.connected-journal.json"
        if arm.is_symlink() or path.is_symlink() or not path.is_file() or (arm / "trajectory.json").exists():
            raise ValueError("FOUR_PRESERVED_INCOMPLETE_ACCOUNTS_REQUIRED")
        body = load(path)["body"]
        result[arm.name] = {"public_journal_body_sha256": hashlib.sha256(canonical(body)).hexdigest(),
                            "manifest_sha256": sha(arm / "manifest.json")}
    return result


def run(reproduction_output, registration_commit, *, workers=None):
    if not re.fullmatch(r"[0-9a-f]{40}", registration_commit):
        raise ValueError("PUBLIC_REGISTRATION_COMMIT_REQUIRED")
    base = Path(reproduction_output).absolute()
    if base.is_symlink() or not base.is_dir():
        raise ValueError("ORIGINAL_REPRODUCTION_DIRECTORY_REQUIRED")
    campaign = base / "economics"
    source = base / "native-source"
    manifest = load(base / "native-manifest.json")
    registration = load(REGISTRATION)
    if registration.get("indices") != INDICES or registration.get("source_sha256") != sha(__file__):
        raise ValueError("EXACT_PUBLIC_UNOPENED_REGISTRATION_REQUIRED")
    if any((campaign / name).exists() for name in
           ("campaign.json", "UNOPENED_START.json", "UNOPENED_RESULT.json")):
        raise ValueError("PRIOR_STAGE_OR_COMPLETED_CAMPAIGN_REFUSED")
    if {p.name for p in campaign.glob("arm-*")} != {f"arm-{i:02d}" for i in range(12)}:
        raise ValueError("EXACT_EIGHT_CLOSED_FOUR_PARTIAL_TWELVE_ABSENT_BOUNDARY_REQUIRED")
    for index in INDICES:
        if (campaign / f"arm-{index:02d}").exists() or (campaign / f"arm-{index:02d}").is_symlink():
            raise ValueError("NEVER_STARTED_EXCLUSIVE_ACCOUNT_PATH_REQUIRED")
    binding = validate_freezes(source, manifest)
    if (binding["economic_freeze_sha256"] != registration["economic_freeze_sha256"]
            or binding["orchestration_freeze_sha256"] != registration["orchestration_freeze_sha256"]):
        raise ValueError("REGISTERED_ORIGINAL_SOURCE_CLOSURE_REQUIRED")
    protected = protected_identities(campaign)
    if protected != registration.get("protected_public_identities"):
        raise ValueError("EXACT_REGISTERED_INTERRUPTION_PREFIX_REQUIRED")
    jobs = [job for job in registered_jobs() if job["index"] in INDICES]
    count, limits = select_workers(workers)
    provenance = {"schema": "portfolio071/unopened-scheduling/v1", "registration_commit": registration_commit,
        "registration_sha256": sha(REGISTRATION), "runner_sha256": sha(__file__),
        "original_interruption_preserved": True, "indices": INDICES,
        "previously_closed_indices": list(range(8)), "incomplete_indices_not_reopened": list(range(8, 12)),
        "protected_public_identities": protected, "frozen_source_binding": binding,
        "automatic_retries": 0, "worker_count": count, "resources_at_start": limits,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "First execution of twelve originally registered unopened accounts; no recovery, reset, top-up or pooled balance."}
    write_new(campaign / "UNOPENED_START.json", provenance)
    start = time.monotonic()
    records, statuses, failures = _schedule(source, manifest, campaign, jobs, count)
    try:
        if protected_identities(campaign) != protected:
            failures.append({"status": "PROTECTED_OLD_ACCOUNT_PUBLIC_IDENTITY_CHANGED"})
        if validate_freezes(source, manifest) != binding:
            failures.append({"status": "SOURCE_CLOSURE_CHANGED"})
    except Exception as error:
        failures.append({"status": "FINAL_IDENTITY_CHECK_FAILED", "error": type(error).__name__ + ": " + str(error)})
    result = {**provenance, "accepted": not failures and set(records) == set(INDICES),
        "completed_indices": sorted(records), "execution_statuses": statuses, "failures": failures,
        "compact_completed_records": [records[index] for index in sorted(records)],
        "wall_seconds": time.monotonic() - start,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "full_campaign_accepted": False,
        "remaining_gate": "Four original interrupted accounts require separately qualified same-account recovery and all24 independent reconciliation."}
    write_new(campaign / "UNOPENED_RESULT.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reproduction-output", type=Path, required=True)
    parser.add_argument("--registration-commit", required=True)
    parser.add_argument("--workers", type=int)
    args = parser.parse_args()
    result = run(args.reproduction_output, args.registration_commit, workers=args.workers)
    print(json.dumps({key: result[key] for key in ("accepted", "completed_indices", "full_campaign_accepted")}, sort_keys=True))
    if not result["accepted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
