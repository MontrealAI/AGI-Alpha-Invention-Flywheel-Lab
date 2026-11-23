#!/usr/bin/env python3
"""Guard an evaluator-only, offline job under external standing approval."""
from argparse import ArgumentParser
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import pwd
import shutil
import socket
import stat
import subprocess
import sys
import tempfile

from common import atomic, checked, clock, encode, read, require, sha
from cycle import exclusive_state, signature, verify

METRICS = {"accepted", "abstained", "cases", "rejected"}
SCHEMA = "frontier-omega-alpha/evaluator-standing-authority-v1"
BATCH_SCHEMA = "frontier-omega-alpha/evaluator-input-version-v1"


def timestamp(text):
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, "TIMEZONE_REQUIRED")
    return parsed


def protected(path, *, directory=False, owner=0, private=False):
    status = path.lstat()
    require(status.st_uid == owner and (stat.S_ISDIR(status.st_mode) if directory else stat.S_ISREG(status.st_mode)),
            "INVALID_OWNER_OR_FILE_TYPE")
    require(status.st_mode & (0o077 if private else 0o022) == 0, "WRITABLE_OR_PUBLIC_AUTHORITY_PATH")
    return path


def file_set(directory, identities, *, private_group=None, max_bytes=None):
    protected(directory, directory=True)
    require(isinstance(identities, dict) and identities and {p.name for p in directory.iterdir()} == identities.keys(),
            "APPROVED_FILE_SET_CHANGED")
    require(not os.access(directory, os.W_OK), "APPROVED_DIRECTORY_WRITABLE")
    if private_group is not None:
        status = directory.stat()
        require(status.st_gid == private_group and not status.st_mode & 0o007, "RECORD_DIRECTORY_VISIBLE_TO_OTHERS")
    total = 0
    for name, digest in identities.items():
        require(name == Path(name).name and name not in {".", ".."}, "UNSAFE_APPROVED_FILENAME")
        path = protected(directory / name)
        total += path.stat().st_size
        require(max_bytes is None or total <= max_bytes, "APPROVED_INPUT_BYTE_BUDGET_EXCEEDED")
        if private_group is not None:
            status = path.stat()
            require(status.st_gid == private_group and not status.st_mode & 0o007, "RECORD_VISIBLE_TO_OTHERS")
        require(sha(path.read_bytes()) == digest and not os.access(path, os.W_OK), "APPROVED_INPUT_CHANGED")


def active_approval(envelope, now):
    require(envelope["schema"] == SCHEMA and envelope["purpose"] == "non-production-only", "UNKNOWN_AUTHORITY_SCOPE")
    require(envelope["state"] == "ACTIVE" and envelope["evaluator_key_sha256"] not in envelope["revoked_key_sha256"],
            "EVALUATOR_REVOKED")
    require(timestamp(envelope["valid_from"]) <= now < timestamp(envelope["valid_until"]), "APPROVAL_EXPIRED_OR_NOT_YET_VALID")
    require(envelope["new_spend_authorized"] is False and envelope["publish"] == "signed-aggregate-only",
            "UNSUPPORTED_AUTHORITY_EFFECT")
    required = envelope["operating_requirements_file"]
    require(envelope["score_entry"] in envelope["code_sha256"], "MISSING_APPROVED_ENTRY_OR_REQUIREMENTS")
    if "record_publisher" in envelope:
        publisher = envelope["record_publisher"]
        require(set(publisher) == {"key_sha256", "scope_id", "requirements_sha256"} and
                all(isinstance(value, str) and value for value in publisher.values()) and
                required != "input-version.json", "INVALID_RECORD_PUBLISHER_GRANT")
    else:
        require(required in envelope["records_sha256"], "MISSING_APPROVED_ENTRY_OR_REQUIREMENTS")
    require(type(envelope.get("record_queue", False)) is bool and
            (not envelope.get("record_queue") or "record_publisher" in envelope), "UNAPPROVED_RECORD_QUEUE")
    require(type(envelope["run_wall_seconds"]) is int and envelope["run_wall_seconds"] > 0, "MISSING_APPROVED_WALL_LIMIT")
    require(type(envelope["max_input_bytes"]) is int and envelope["max_input_bytes"] > 0, "MISSING_APPROVED_BYTE_BUDGET")
    require(type(envelope["retention_days"]) is int and envelope["retention_days"] > 0, "MISSING_APPROVED_RETENTION")
    return envelope


def admit_batch(manifest, authority, now):
    publisher = authority["record_publisher"]
    require(manifest["schema"] == BATCH_SCHEMA and manifest["scope_id"] == publisher["scope_id"],
            "INPUT_VERSION_OUTSIDE_APPROVED_SCOPE")
    require(timestamp(manifest["valid_from"]) <= now < timestamp(manifest["valid_until"]), "INPUT_VERSION_EXPIRED")
    files = manifest["records_sha256"]
    required = authority["operating_requirements_file"]
    require(isinstance(files, dict) and required in files and files[required] == publisher["requirements_sha256"] and
            "input-version.json" not in files and len(files) >= 2, "INPUT_VERSION_CHANGED_APPROVED_REQUIREMENTS")
    return files, timestamp(manifest["valid_until"])


def signed_host_binding(root, trust_sha256, state):
    require(os.geteuid() != 0 and root.is_absolute() and root.resolve() == root, "INVALID_EVALUATOR_IDENTITY_OR_PATH")
    for ancestor in reversed((root, *root.parents)):
        protected(ancestor, directory=True)
    manifest = protected(root / "authority.json")
    authority = verify(manifest, trust_sha256)["receipt"]
    require(authority["schema"] == SCHEMA and authority["purpose"] == "non-production-only", "UNKNOWN_AUTHORITY_SCOPE")
    require(authority["evaluator_key_sha256"] != trust_sha256, "OWNER_AND_EVALUATOR_KEYS_MUST_DIFFER")
    uid = os.geteuid()
    require((uid, pwd.getpwuid(uid).pw_name) == (authority["evaluator_uid"], authority["evaluator_user"]) and
            uid != authority["constructor_uid"], "EVALUATOR_CONSTRUCTOR_IDENTITY_NOT_SEPARATE")
    binding = protected(root / "host-binding.json")
    require(sha(binding.read_bytes()) == authority["host_binding_sha256"] and
            read(binding)["hostname"] == socket.gethostname(), "UNAPPROVED_HOST_BINDING")
    require(state == Path(authority["private_state"]) and state.resolve() == state and not state.is_relative_to(root),
            "UNAPPROVED_PRIVATE_CASE_STORE")
    protected(state, directory=True, owner=uid, private=True)
    return authority, manifest


def digest_name(name):
    return isinstance(name, str) and len(name) == 64 and all(c in "0123456789abcdef" for c in name)


def record_directory(root, authority, slot):
    records = root / "cleared-records"
    if authority.get("record_queue"):
        require(digest_name(slot), "INPUT_VERSION_DIRECTORY_REQUIRED")
        protected(records, directory=True)
        return records / slot
    require(slot is None, "INPUT_VERSION_DIRECTORY_UNAPPROVED")
    return records


def verify_authority(root, trust_sha256, state, slot=None):
    authority, manifest = signed_host_binding(root, trust_sha256, state)
    now = datetime.now(timezone.utc)
    active_approval(authority, now)
    if sys.platform == "darwin":
        from mac_activation import require_canary
        require_canary(root, authority, sha(manifest.read_bytes()))
    uid = os.geteuid()
    private_key = protected(state / "evaluator.key", owner=uid, private=True)
    public = checked(["openssl", "pkey", "-in", str(private_key), "-pubout"])
    require(sha(public) == authority["evaluator_key_sha256"], "EVALUATOR_KEY_NOT_APPROVED")
    require(sha(Path(sys.executable).read_bytes()) == authority["python_sha256"], "UNAPPROVED_EVALUATOR_RUNTIME")
    file_set(root / "approved-code", authority["code_sha256"])
    gid = authority["evaluator_gid"]
    require(gid in {os.getegid(), *os.getgroups()}, "EVALUATOR_GROUP_UNAVAILABLE")
    directory = record_directory(root, authority, slot)
    approval_sha = sha(manifest.read_bytes())
    inputs, version, expiry = authority.get("records_sha256"), approval_sha, timestamp(authority["valid_until"])
    if "record_publisher" in authority:
        protected(directory, directory=True)
        published = protected(directory / "input-version.json")
        stamp = sha(published.read_bytes())
        require(slot is None or slot == stamp, "SOURCE_VERSION_DIRECTORY_CONTENT_CHANGED")
        batch = verify(published, authority["record_publisher"]["key_sha256"])["receipt"]
        files, batch_expiry = admit_batch(batch, authority, now)
        inputs = files | {"input-version.json": stamp}
        version = sha(encode([approval_sha, stamp]))
        expiry = min(expiry, batch_expiry)
    file_set(directory, inputs, private_group=gid, max_bytes=authority["max_input_bytes"])
    if sys.platform == "darwin":
        from mac_activation import require_posix_only
        for path in (directory, *(directory / name for name in inputs)):
            require_posix_only(path)
    return authority, approval_sha, version, expiry, inputs


def validate_metrics(result):
    require(isinstance(result, dict) and set(result) == METRICS and
            all(type(value) is int and value >= 0 for value in result.values()), "UNAPPROVED_PUBLIC_RESULT_FIELDS")
    require(result["accepted"] + result["abstained"] + result["rejected"] == result["cases"], "SCORING_DENOMINATOR_MISMATCH")
    return result


def verify_aggregate(path, approval_path, owner_key, expected_version=None):
    authority = active_approval(verify(approval_path, owner_key)["receipt"], datetime.now(timezone.utc))
    require(authority["evaluator_key_sha256"] != owner_key, "OWNER_AND_EVALUATOR_KEYS_MUST_DIFFER")
    result = verify(path, authority["evaluator_key_sha256"])["receipt"]
    require(result["schema"] == "frontier-omega-alpha/independent-evaluator-aggregate-v1" and
            result["scope"] == "non-production-only" and result["authority_envelope_sha256"] ==
            sha(approval_path.read_bytes()), "RECEIPT_NOT_BOUND_TO_ACTIVE_APPROVAL")
    source = result["input_version_binding_sha256"]
    require(digest_name(source) and
            (expected_version is None or source == expected_version), "RECEIPT_INPUT_VERSION_MISMATCH")
    return validate_metrics(result["metrics"])


def cleanup_managed_runs(state):
    past = state / "managed-runs"
    if not past.exists():
        return
    protected(past, directory=True, owner=os.geteuid(), private=True)
    now = datetime.now(timezone.utc)
    for run_state in past.iterdir():
        if run_state.name.startswith("case-") and run_state.is_dir() and not run_state.is_symlink():
            lease = protected(run_state / "retention.json", owner=os.geteuid(), private=True)
            if timestamp(read(lease)["delete_after"]) <= now:
                shutil.rmtree(run_state)


def run(root, trust, state, output, slot=None):
    # Only the signed, administrator-pinned scorer executes on held cases.
    protected(state, directory=True, owner=os.geteuid(), private=True)
    with exclusive_state(state):
        cleanup_managed_runs(state)
        authority, manifest, version, expires, inputs = verify_authority(root, trust, state, slot)
        require(output == Path(authority["aggregate_directory"]) and output.resolve() == output and output.is_dir() and
                not output.is_relative_to(state), "UNAPPROVED_EXPORT")
        destination = output / (version + ".json")
        if destination.exists():
            verify_aggregate(destination, root / "authority.json", trust, version)
            return "already_scored"
        managed = state / "managed-runs"
        managed.mkdir(mode=0o700, exist_ok=True)
        protected(managed, directory=True, owner=os.geteuid(), private=True)
        case_state = Path(tempfile.mkdtemp(prefix="case-", dir=managed))
        cutoff = min(expires, datetime.now(timezone.utc) + timedelta(days=authority["retention_days"]))
        atomic(case_state / "retention.json", {"delete_after": cutoff.isoformat()})
        snapshot = case_state / "input-snapshot"
        snapshot.mkdir(mode=0o700)
        for name, identity in inputs.items():
            raw = (record_directory(root, authority, slot) / name).read_bytes()
            require(sha(raw) == identity, "APPROVED_INPUT_CHANGED_DURING_FREEZE")
            path = snapshot / name
            path.write_bytes(raw)
            path.chmod(0o400)
        # Approved code lives in an immutable directory. Explicit path insertion lets it
        # import only its administrator-pinned sibling modules in isolated Python.
        script = root / "approved-code" / authority["score_entry"]
        loader = "import runpy,sys; sys.path.insert(0,sys.argv[1]); sys.argv=sys.argv[2:]; runpy.run_path(sys.argv[0],run_name='__main__')"
        command = [sys.executable, "-I", "-B", "-c", loader, str(script.parent), str(script),
                   str(snapshot), str(case_state)]
        try:
            observation = subprocess.run(command, capture_output=True, check=True, cwd=case_state,
                                         env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C"},
                                         timeout=authority["run_wall_seconds"])
        except (subprocess.SubprocessError, OSError):
            raise ValueError("APPROVED_SCORER_FAILED_PRIVATE_EVIDENCE_RETAINED") from None
        metrics = validate_metrics(json.loads(observation.stdout))
        current, current_manifest, current_version, _, _ = verify_authority(root, trust, state, slot)
        require(manifest == current_manifest and authority == current and version == current_version,
                "AUTHORITY_CHANGED_DURING_SCORING")
        receipt = {"schema": "frontier-omega-alpha/independent-evaluator-aggregate-v1", "completed_utc": clock(),
                   "authority_envelope_sha256": manifest, "input_version_binding_sha256": version,
                   "metrics": metrics, "scope": "non-production-only"}
        atomic(destination, signature(state, receipt))
        return "scored"


def run_available(root, trust, state):
    authority, manifest = signed_host_binding(root, trust, state)
    with exclusive_state(state):
        cleanup_managed_runs(state)
    active_approval(authority, datetime.now(timezone.utc))
    if sys.platform == "darwin":
        from mac_activation import require_canary
        require_canary(root, authority, sha(manifest.read_bytes()))
    output = Path(authority["aggregate_directory"])
    if not authority.get("record_queue"):
        return {run(root, trust, state, output): 1}
    records = protected(root / "cleared-records", directory=True)
    stats = {"scored": 0, "already_scored": 0, "ineligible_or_unavailable": 0}
    for slot in sorted(p.name for p in records.iterdir() if digest_name(p.name)):
        try:
            stats[run(root, trust, state, output, slot)] += 1
        except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
            # Score independent, valid versions even when a neighboring version is expired or corrupt.
            stats["ineligible_or_unavailable"] += 1
    return stats


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--authority-root", type=Path)
    parser.add_argument("--owner-trust-sha256", required=True)
    parser.add_argument("--private-state", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-receipt", type=Path)
    parser.add_argument("--active-approval", type=Path)
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    try:
        if args.verify_receipt:
            require(args.active_approval is not None, "ACTIVE_APPROVAL_REQUIRED")
            validate = verify_aggregate(args.verify_receipt, args.active_approval, args.owner_trust_sha256)
            print(encode({"state": "VERIFIED", "metrics": validate}).decode(), end="")
            return 0
        require(args.authority_root is not None and args.private_state is not None, "EVALUATOR_PATHS_REQUIRED")
        if args.cleanup:
            signed_host_binding(args.authority_root, args.owner_trust_sha256, args.private_state)
            with exclusive_state(args.private_state):
                cleanup_managed_runs(args.private_state)
        elif args.output:
            run(args.authority_root, args.owner_trust_sha256, args.private_state, args.output)
        else:
            authority, _, _, _, _ = verify_authority(args.authority_root, args.owner_trust_sha256, args.private_state)
            print(encode({"state": "READY", "scope": authority["purpose"]}).decode(), end="")
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        # Never report discovered record names, data, paths, credentials or stderr.
        reason = str(error) if type(error) is ValueError and str(error).replace("_", "").isupper() else type(error).__name__
        print(encode({"state": "ABSTAIN", "reason": reason}).decode(), end="")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
