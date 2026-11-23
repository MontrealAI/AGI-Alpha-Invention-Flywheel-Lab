#!/usr/bin/env python3
"""Run a scoped source adapter, sign its versions, and stage approved immutable inputs."""
from argparse import ArgumentParser
import base64
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import plistlib
import pwd
import resource
import shutil
import stat
import subprocess
import sys
import tempfile

from common import atomic, checked, encode, read, require, sha
from cycle import exclusive_state, signature, verify
from standing_authority import BATCH_SCHEMA, active_approval, admit_batch, digest_name, protected, timestamp

RELEASE_SCHEMA = "frontier-omega-alpha/source-output-v1"
MANIFEST = "input-version.json"


def safe_name(name):
    return (isinstance(name, str) and name == Path(name).name and name not in {"", ".", ".."} and
            not any(ord(char) < 32 for char in name))


def admitted_release(release, authority, now):
    fields = authority["record_publisher"]
    require(release["schema"] == RELEASE_SCHEMA and release["scope_id"] == fields["scope_id"] and
            digest_name(release["source_revision_sha256"]), "UNAPPROVED_SOURCE_OUTPUT")
    source_deadline(release, authority)
    payload, size = {}, 0
    for name, data in release["records"].items():
        require(safe_name(name) and name != MANIFEST, "UNSAFE_SOURCE_RECORD_NAME")
        item = base64.b64decode(data, validate=True)
        size += len(item)
        require(size <= authority["max_input_bytes"], "SOURCE_RECORDS_EXCEED_BYTE_BUDGET")
        payload[name] = item
    version = {"schema": BATCH_SCHEMA, "scope_id": release["scope_id"],
               "source_revision_sha256": release["source_revision_sha256"],
               "valid_from": release["valid_from"], "valid_until": release["valid_until"],
               "records_sha256": {name: sha(data) for name, data in payload.items()}}
    admit_batch(version, authority, now)
    return version, payload


def source_deadline(record, authority):
    end = timestamp(record["valid_until"])
    require(end <= timestamp(authority["valid_until"]) and
            end <= timestamp(record["valid_from"]) + timedelta(days=authority["retention_days"]),
            "SOURCE_EXPIRY_EXCEEDS_APPROVAL")
    return end


def install_snapshot(target, slot, files, group=None):
    require(digest_name(slot) and slot == sha(files[MANIFEST]), "UNBOUND_INTAKE_VERSION")
    require(all(safe_name(name) for name in files), "UNSAFE_SOURCE_RECORD_NAME")
    destination = target / slot
    if destination.exists():
        require(destination.is_dir() and not destination.is_symlink() and
                {p.name for p in destination.iterdir()} == files.keys(), "STAGED_VERSION_CONFLICT")
        require(all((destination / name).is_file() and not (destination / name).is_symlink() and
                    sha((destination / name).read_bytes()) == sha(data) for name, data in files.items()),
                "STAGED_VERSION_CONFLICT")
        return "already_present"
    with tempfile.TemporaryDirectory(prefix=".pending-", dir=target) as scratch:
        temp = Path(scratch) / "version"
        temp.mkdir(mode=0o700)
        for name, data in files.items():
            fd = os.open(temp / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as output:
                output.write(data)
                if group is not None:
                    os.fchown(output.fileno(), 0, group)
                    os.fchmod(output.fileno(), 0o640)
                output.flush()
                os.fsync(output.fileno())
        if group is not None:
            os.chown(temp, 0, group)
            temp.chmod(0o750)
        temp.rename(destination)
        directory = os.open(target, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    return "published"


def seal_release(release, authority, state, outbox):
    body, inputs = admitted_release(release, authority, datetime.now(timezone.utc))
    key = protected(state / "evaluator.key", owner=os.geteuid(), private=True)
    public = checked(["openssl", "pkey", "-in", str(key), "-pubout"])
    require(sha(public) == authority["record_publisher"]["key_sha256"] and
            sha(public) != authority["evaluator_key_sha256"], "INPUT_PUBLISHER_KEY_UNAPPROVED")
    envelope = encode(signature(state, body))
    require(len(envelope) + sum(map(len, inputs.values())) <= authority["max_input_bytes"],
            "SOURCE_VERSION_AND_SIGNATURE_EXCEED_BYTE_BUDGET")
    return install_snapshot(outbox, sha(envelope), inputs | {MANIFEST: envelope})


def read_slot(outbox, slot, owner, limit):
    """Take a bounded snapshot of one source-owned directory without following redirects."""
    require(digest_name(slot), "INPUT_VERSION_DIRECTORY_REQUIRED")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parent_fd = os.open(outbox, flags)
    try:
        require(os.fstat(parent_fd).st_uid == owner, "INPUT_OUTBOX_OWNER_CHANGED")
        version_fd = os.open(slot, flags, dir_fd=parent_fd)
        try:
            require(os.fstat(version_fd).st_uid == owner, "INPUT_VERSION_OWNER_CHANGED")
            result = {}
            remaining = limit
            for name in os.listdir(version_fd):
                require(safe_name(name), "UNSAFE_SOURCE_RECORD_NAME")
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=version_fd)
                with os.fdopen(fd, "rb") as source:
                    info = os.fstat(source.fileno())
                    require(stat.S_ISREG(info.st_mode) and info.st_uid == owner and
                            info.st_size <= remaining, "UNAPPROVED_INPUT_FILE")
                    data = source.read(remaining + 1)
                    require(len(data) <= remaining, "INPUT_SNAPSHOT_EXCEEDS_BYTE_BUDGET")
                    remaining -= len(data)
                    result[name] = data
            require(sha(result[MANIFEST]) == slot, "INPUT_VERSION_SNAPSHOT_CHANGED")
            return result
        finally:
            os.close(version_fd)
    finally:
        os.close(parent_fd)


def admit_snapshot(snapshot, authority, now, scratch):
    placed = scratch / MANIFEST
    placed.write_bytes(snapshot[MANIFEST])
    manifest = verify(placed, authority["record_publisher"]["key_sha256"])["receipt"]
    approved, _ = admit_batch(manifest, authority, now)
    source_deadline(manifest, authority)
    require({name: sha(data) for name, data in snapshot.items() if name != MANIFEST} == approved,
            "SOURCE_VERSIONS_DO_NOT_MATCH_SIGNED_HASHES")
    return manifest


def retire_expired(directory, owner, authority, now):
    retired = 0
    for slot in sorted(p.name for p in directory.iterdir() if digest_name(p.name)):
        try:
            files = read_slot(directory, slot, owner, authority["max_input_bytes"])
            with tempfile.TemporaryDirectory(prefix="frontier-expiry-") as scratch:
                staged = Path(scratch) / MANIFEST
                staged.write_bytes(files[MANIFEST])
                manifest = verify(staged, authority["record_publisher"]["key_sha256"])["receipt"]
                expiry = source_deadline(manifest, authority)
                if expiry > now:
                    continue
                admit_snapshot(files, authority, expiry - timedelta(microseconds=1), Path(scratch))
            shutil.rmtree(directory / slot)
            retired += 1
        except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
            # An unknown or unsigned directory is outside the automatic deletion scope.
            continue
    return retired


def validate_scope(authority, root):
    scope = authority["source_intake"]
    require(authority.get("record_queue") is True and
            type(scope["publisher_uid"]) is int and scope["publisher_uid"] > 0 and
            scope["publisher_uid"] not in {authority["evaluator_uid"], authority["constructor_uid"],
                                           authority["mac_activation"]["administrator_uid"]}, "INPUT_ROLES_NOT_SEPARATE")
    require(type(scope["max_versions_per_run"]) is int and scope["max_versions_per_run"] > 0 and
            type(scope["adapter_wall_seconds"]) is int and scope["adapter_wall_seconds"] > 0, "INPUT_ADAPTER_BOUNDS_MISSING")
    state = Path(scope["publisher_state"])
    require(state.is_absolute() and state.resolve() == state and not state.is_relative_to(root) and
            not state.is_relative_to(Path(authority["private_state"])), "INPUT_PUBLISHER_STATE_UNAPPROVED")
    protected(state, directory=True, owner=scope["publisher_uid"], private=True)
    outbox = protected(state / "outbox", directory=True, owner=scope["publisher_uid"], private=True)
    return scope, state, outbox


def produce(authority, scope, root, state, outbox):
    require(os.geteuid() == scope["publisher_uid"], "ACTUAL_PUBLISHER_IDENTITY_REQUIRED")
    adapter = protected(root / "approved-source-adapter.py")
    require(sha(adapter.read_bytes()) == scope["adapter_sha256"], "INPUT_ADAPTER_CHANGED")
    limit = (2 * authority["max_input_bytes"] + 65536) * scope["max_versions_per_run"]
    def limit_output():
        resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))
    with exclusive_state(state), tempfile.TemporaryFile(dir=state) as output:
        command = [sys.executable, "-I", "-B", str(adapter)]
        subprocess.run(command, stdout=output, stderr=subprocess.DEVNULL, check=True, preexec_fn=limit_output,
                       cwd=state, env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C"},
                       timeout=scope["adapter_wall_seconds"])
        output.seek(0)
        data = output.read(limit + 1)
        require(len(data) <= limit, "INPUT_ADAPTER_OUTPUT_EXCEEDS_BUDGET")
        outputs = json.loads(data)
        require(isinstance(outputs, list) and len(outputs) <= scope["max_versions_per_run"], "ADAPTER_CASE_COUNT_EXCEEDED")
        counts = {"published": 0, "already_present": 0, "source_rejected": 0,
                  "retired": retire_expired(outbox, scope["publisher_uid"], authority, datetime.now(timezone.utc))}
        for release in outputs:
            try:
                counts[seal_release(release, authority, state, outbox)] += 1
            except (ValueError, TypeError, KeyError):
                counts["source_rejected"] += 1
    return counts


def stage(authority, scope, root, outbox, approval_sha):
    require(os.geteuid() == 0, "INDEPENDENT_STAGER_IDENTITY_REQUIRED")
    target = protected(root / "cleared-records", directory=True)
    require(target.stat().st_gid == authority["evaluator_gid"] and not target.stat().st_mode & 0o007,
            "PUBLISHER_STAGING_GROUP_UNAPPROVED")
    counts = {"published": 0, "already_present": 0, "source_rejected": 0,
              "retired": retire_expired(target, 0, authority, datetime.now(timezone.utc))}
    for slot in sorted(p.name for p in outbox.iterdir() if digest_name(p.name)):
        try:
            snapshot = read_slot(outbox, slot, scope["publisher_uid"], authority["max_input_bytes"])
            with tempfile.TemporaryDirectory(prefix="frontier-intake-") as directory:
                admit_snapshot(snapshot, authority, datetime.now(timezone.utc), Path(directory))
            require(sha((root / "authority.json").read_bytes()) == approval_sha, "INTAKE_APPROVAL_CHANGED")
            counts[install_snapshot(target, slot, snapshot, authority["evaluator_gid"])] += 1
        except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
            counts["source_rejected"] += 1
    return counts


def launcher(root, owner_pin, role, scope):
    require(role in {"produce", "stage"}, "INPUT_JOB_SCOPE_UNAPPROVED")
    interval = scope["interval_seconds"]
    require(type(interval) is int and interval > 0, "INPUT_WAKE_INTERVAL_UNAPPROVED")
    return {"Label": f"ai.montreal.frontier-source-{role}",
            "UserName": pwd.getpwuid(scope["publisher_uid"]).pw_name if role == "produce" else "root",
            "StartInterval": interval, "ProcessType": "Background",
            "ProgramArguments": [str(Path(sys.executable).resolve()), "-B", str(Path(__file__).resolve()), role,
                                 "--authority-root", str(root), "--owner-pin", owner_pin]}


def run(root, owner_pin, role):
    from mac_activation import require_mac, crypto_path, approved_mac, validate_roles, require_canary
    require_mac()
    require(root.is_absolute() and root.resolve() == root, "INTAKE_ROOT_UNAPPROVED")
    for folder in reversed((root, *root.parents)):
        protected(folder, directory=True)
    crypto_path(root)
    manifest = protected(root / "authority.json")
    approval_sha = sha(manifest.read_bytes())
    authority = verify(manifest, owner_pin)["receipt"]
    now = datetime.now(timezone.utc)
    inactive = False
    try:
        active_approval(authority, now)
    except ValueError as error:
        require(str(error) in {"APPROVAL_EXPIRED_OR_NOT_YET_VALID", "EVALUATOR_REVOKED"} and
                timestamp(authority["valid_from"]) <= now, str(error))
        inactive = True
    approved = approved_mac(authority)
    receipt = read(protected(root / "mac-canary.json"))
    require(receipt["approval_sha256"] == approval_sha, "MAC_INTAKE_CANARY_UNAVAILABLE")
    validate_roles(receipt, authority, approved)
    require(sha(manifest.read_bytes()) == approval_sha, "INTAKE_APPROVAL_CHANGED")
    scope, state, outbox = validate_scope(authority, root)
    if inactive:
        require(role in {"produce", "stage"}, "INPUT_LAUNCH_REQUIRES_ACTIVE_APPROVAL")
        uid = scope["publisher_uid"] if role == "produce" else 0
        require(os.geteuid() == uid, "INPUT_RETIREMENT_IDENTITY_MISMATCH")
        location = outbox if role == "produce" else protected(root / "cleared-records", directory=True)
        return {"state": "RETIRE_ONLY", "retired": retire_expired(location, uid, authority, now)}
    if role.startswith("plist-"):
        return plistlib.dumps(launcher(root, owner_pin, role.removeprefix("plist-"), scope))
    if role == "produce":
        return produce(authority, scope, root, state, outbox)
    require_canary(root, authority, approval_sha)
    return stage(authority, scope, root, outbox, approval_sha)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=("produce", "stage", "plist-produce", "plist-stage"))
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--owner-pin", required=True)
    args = parser.parse_args()
    try:
        result = run(args.authority_root, args.owner_pin, args.role)
        if isinstance(result, bytes):
            sys.stdout.buffer.write(result)
        else:
            print(encode(result).decode(), end="")
        return 0
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        print(encode({"state": "ABSTAIN", "reason": type(error).__name__}).decode(), end="")
        return 1


if __name__ == "__main__":
    sys.exit(main())
