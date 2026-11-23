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


def file_set(directory, identities, *, private_group=None):
    protected(directory, directory=True)
    require(isinstance(identities, dict) and identities and {p.name for p in directory.iterdir()} == identities.keys(),
            "APPROVED_FILE_SET_CHANGED")
    require(not os.access(directory, os.W_OK), "APPROVED_DIRECTORY_WRITABLE")
    if private_group is not None:
        status = directory.stat()
        require(status.st_gid == private_group and not status.st_mode & 0o007, "RECORD_DIRECTORY_VISIBLE_TO_OTHERS")
    for name, digest in identities.items():
        require(name == Path(name).name and name not in {".", ".."}, "UNSAFE_APPROVED_FILENAME")
        path = protected(directory / name)
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
    require(envelope["score_entry"] in envelope["code_sha256"] and envelope["operating_requirements_file"] in envelope["records_sha256"],
            "MISSING_APPROVED_ENTRY_OR_REQUIREMENTS")
    require(type(envelope["run_wall_seconds"]) is int and envelope["run_wall_seconds"] > 0, "MISSING_APPROVED_WALL_LIMIT")
    require(type(envelope["retention_days"]) is int and envelope["retention_days"] > 0, "MISSING_APPROVED_RETENTION")
    return envelope


def signed_host_binding(root, trust_sha256, state):
    require(os.geteuid() != 0 and root.is_absolute() and root.resolve() == root, "INVALID_EVALUATOR_IDENTITY_OR_PATH")
    for ancestor in reversed((root, *root.parents)):
        protected(ancestor, directory=True)
    manifest = protected(root / "authority.json")
    authority = verify(manifest, trust_sha256)["receipt"]
    require(authority["schema"] == SCHEMA and authority["purpose"] == "non-production-only", "UNKNOWN_AUTHORITY_SCOPE")
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


def verify_authority(root, trust_sha256, state):
    authority, manifest = signed_host_binding(root, trust_sha256, state)
    active_approval(authority, datetime.now(timezone.utc))
    uid = os.geteuid()
    private_key = protected(state / "evaluator.key", owner=uid, private=True)
    public = checked(["openssl", "pkey", "-in", str(private_key), "-pubout"])
    require(sha(public) == authority["evaluator_key_sha256"], "EVALUATOR_KEY_NOT_APPROVED")
    require(sha(Path(sys.executable).read_bytes()) == authority["python_sha256"], "UNAPPROVED_EVALUATOR_RUNTIME")
    file_set(root / "approved-code", authority["code_sha256"])
    gid = authority["evaluator_gid"]
    require(gid in {os.getegid(), *os.getgroups()}, "EVALUATOR_GROUP_UNAVAILABLE")
    file_set(root / "cleared-records", authority["records_sha256"], private_group=gid)
    return authority, sha(manifest.read_bytes())


def validate_metrics(result):
    require(isinstance(result, dict) and set(result) == METRICS and
            all(type(value) is int and value >= 0 for value in result.values()), "UNAPPROVED_PUBLIC_RESULT_FIELDS")
    require(result["accepted"] + result["abstained"] + result["rejected"] == result["cases"], "SCORING_DENOMINATOR_MISMATCH")
    return result


def verify_aggregate(path, approval_path, owner_key):
    authority = active_approval(verify(approval_path, owner_key)["receipt"], datetime.now(timezone.utc))
    result = verify(path, authority["evaluator_key_sha256"])["receipt"]
    require(result["schema"] == "frontier-omega-alpha/independent-evaluator-aggregate-v1" and
            result["scope"] == "non-production-only" and result["authority_envelope_sha256"] ==
            sha(approval_path.read_bytes()), "RECEIPT_NOT_BOUND_TO_ACTIVE_APPROVAL")
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


def run(root, trust, state, output):
    # Only the signed, administrator-pinned scorer executes on held cases.
    protected(state, directory=True, owner=os.geteuid(), private=True)
    with exclusive_state(state):
        cleanup_managed_runs(state)
        authority, manifest = verify_authority(root, trust, state)
        require(output.parent == Path(authority["aggregate_directory"]) and output.parent.resolve() == output.parent and
                output.name == manifest + ".json" and output.parent.is_dir() and
                not output.resolve().is_relative_to(state), "UNAPPROVED_EXPORT")
        if output.exists():
            verify_aggregate(output, root / "authority.json", trust)
            return
        managed = state / "managed-runs"
        managed.mkdir(mode=0o700, exist_ok=True)
        protected(managed, directory=True, owner=os.geteuid(), private=True)
        case_state = Path(tempfile.mkdtemp(prefix="case-", dir=managed))
        cutoff = min(timestamp(authority["valid_until"]), datetime.now(timezone.utc) + timedelta(days=authority["retention_days"]))
        atomic(case_state / "retention.json", {"delete_after": cutoff.isoformat()})
        # Approved code lives in an immutable directory. Explicit path insertion lets it
        # import only its administrator-pinned sibling modules in isolated Python.
        script = root / "approved-code" / authority["score_entry"]
        loader = "import runpy,sys; sys.path.insert(0,sys.argv[1]); sys.argv=sys.argv[2:]; runpy.run_path(sys.argv[0],run_name='__main__')"
        command = [sys.executable, "-I", "-B", "-c", loader, str(script.parent), str(script),
                   str(root / "cleared-records"), str(case_state)]
        try:
            observation = subprocess.run(command, capture_output=True, check=True, cwd=case_state,
                                         env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C"},
                                         timeout=authority["run_wall_seconds"])
        except (subprocess.SubprocessError, OSError):
            raise ValueError("APPROVED_SCORER_FAILED_PRIVATE_EVIDENCE_RETAINED") from None
        metrics = validate_metrics(json.loads(observation.stdout))
        current, current_manifest = verify_authority(root, trust, state)
        require(manifest == current_manifest and authority == current, "AUTHORITY_CHANGED_DURING_SCORING")
        receipt = {"schema": "frontier-omega-alpha/independent-evaluator-aggregate-v1", "completed_utc": clock(),
                   "authority_envelope_sha256": manifest, "metrics": metrics, "scope": "non-production-only"}
        atomic(output, signature(state, receipt))


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
            authority, manifest = verify_authority(args.authority_root, args.owner_trust_sha256, args.private_state)
            run(args.authority_root, args.owner_trust_sha256, args.private_state, args.output / (manifest + ".json"))
        else:
            authority, _ = verify_authority(args.authority_root, args.owner_trust_sha256, args.private_state)
            print(encode({"state": "READY", "scope": authority["purpose"]}).decode(), end="")
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        # Never report discovered record names, data, paths, credentials or stderr.
        reason = str(error) if type(error) is ValueError and str(error).replace("_", "").isupper() else type(error).__name__
        print(encode({"state": "ABSTAIN", "reason": reason}).decode(), end="")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
