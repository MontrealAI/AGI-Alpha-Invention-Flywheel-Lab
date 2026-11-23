#!/usr/bin/env python3
"""On-device, nonconfidential Mac Studio permission qualification for issue #565."""
from argparse import ArgumentParser
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import plistlib
import pwd
import shutil
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory

from common import HERE, atomic, checked, clock, encode, read, require, sha
from cycle import verify
from standing_authority import active_approval, protected

LABEL = "ai.montreal.frontier-evaluator"
SCOPE = "frontier-omega-alpha/mac-studio-canary-v1"
DIAGNOSTIC = b"Public nonconfidential custody permission canary for issue #565.\n"
RUNTIME_FILES = ("mac_activation.py", "standing_authority.py", "common.py", "cycle.py", "evaluation.py")
PROBE = """import json, os, sys
operations = json.loads(sys.argv[1])
result = {}
for label, path, write in operations:
    try:
        fd = os.open(path, (os.O_WRONLY if write else os.O_RDONLY) | os.O_NOFOLLOW)
    except PermissionError:
        result[label] = False
    else:
        os.close(fd)
        result[label] = True
print(json.dumps({'uid': os.geteuid(), 'gid': os.getegid(), 'operations': result}))
"""
EVAL_RIGHTS = {"case_read": True, "case_write": True, "key_read": True, "record_read": True,
               "record_write": False, "approval_write": False, "code_write": False}
CONSTRUCTOR_RIGHTS = {name: False for name in EVAL_RIGHTS}


def require_mac():
    require(platform.system() == "Darwin", "ACTUAL_MAC_STUDIO_REQUIRED")


def inventory():
    require_mac()
    model = checked(["/usr/sbin/sysctl", "-n", "hw.model"]).decode().strip()
    devices = plistlib.loads(checked(["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice", "-a"]))
    require(len(devices) == 1 and devices[0].get("IOPlatformUUID"), "MAC_DEVICE_ID_UNAVAILABLE")
    openssl = Path(shutil.which("openssl") or "").resolve()
    require(openssl.is_file(), "MAC_SIGNING_RUNTIME_UNAVAILABLE")
    return {"model": model, "private_machine_binding_sha256": sha(encode([model, devices[0]["IOPlatformUUID"]])),
            "host_binding": {"hostname": socket.gethostname()}, "python_sha256": sha(Path(sys.executable).read_bytes()),
            "openssl_sha256": sha(openssl.read_bytes()),
            "runtime_files": {name: sha((HERE / name).read_bytes()) for name in RUNTIME_FILES}}


def approved_mac(authority):
    details = authority["mac_activation"]
    local = inventory()
    require(details["model"] == local["model"] and details["machine_binding_sha256"] ==
            local["private_machine_binding_sha256"], "APPROVAL_IS_FOR_A_DIFFERENT_MAC")
    require(details["runtime_files"] == local["runtime_files"] and authority["python_sha256"] == local["python_sha256"] and
            details["openssl_sha256"] == local["openssl_sha256"],
            "MAC_RUNTIME_NOT_EXACTLY_APPROVED")
    require(type(details["interval_seconds"]) is int and details["interval_seconds"] > 0, "MAC_INTERVAL_UNAPPROVED")
    require("record_publisher" not in authority or authority.get("record_queue") is True,
            "MAC_ROUTINE_PUBLISHER_REQUIRES_RETAINED_VERSIONS")
    admin, evaluator, constructor = details["administrator_uid"], authority["evaluator_uid"], authority["constructor_uid"]
    require(all(type(n) is int and n > 0 for n in (admin, evaluator, constructor)) and
            len({admin, evaluator, constructor}) == 3, "THREE_ACTUAL_SEPARATE_HOST_IDENTITIES_REQUIRED")
    return details


def validate_roles(receipt, authority, approved):
    require(receipt["schema"] == SCOPE and receipt["machine_binding_sha256"] == approved["machine_binding_sha256"] and
            receipt["runtime_files"] == approved["runtime_files"] and receipt["signing_canary_verified"] is True,
            "MAC_CANARY_IDENTITY_MISMATCH")
    require(receipt["administrator_uid"] == approved["administrator_uid"] and
            receipt["evaluator"] == {"uid": authority["evaluator_uid"], "gid": authority["evaluator_gid"],
                                    "operations": EVAL_RIGHTS} and
            receipt["constructor"]["uid"] == authority["constructor_uid"] and
            receipt["constructor"]["gid"] != authority["evaluator_gid"] and
            receipt["constructor"]["operations"] == CONSTRUCTOR_RIGHTS,
            "ACTUAL_MAC_PERMISSION_MATRIX_NOT_SATISFIED")


def require_canary(root, authority, manifest_sha):
    require_mac()
    approved = approved_mac(authority)
    receipt = read(protected(root / "mac-canary.json"))
    require(receipt["approval_sha256"] == manifest_sha, "MAC_CANARY_BELONGS_TO_DIFFERENT_APPROVAL")
    validate_roles(receipt, authority, approved)
    evaluator, constructor = (pwd.getpwuid(authority[role + "_uid"]).pw_name for role in ("evaluator", "constructor"))
    require(all(not (name_groups(name) & {"admin", "wheel", "sudo"}) for name in (evaluator, constructor)),
            "MAC_GROUP_AUTHORITY_CHANGED")
    constructor_groups = set(checked(["/usr/bin/id", "-G", constructor]).decode().split())
    require(str(authority["evaluator_gid"]) not in constructor_groups, "MAC_CONSTRUCTOR_JOINED_EVALUATOR_GROUP")
    state = Path(authority["private_state"])
    records = root / "cleared-records"
    for path in (root, root / "authority.json", root / "approved-code", records, state, state / "evaluator.key",
                 *(root / "approved-code").iterdir(), *records.iterdir()):
        require_posix_only(path)
    return receipt


def name_groups(name):
    return set(checked(["/usr/bin/id", "-Gn", name]).decode().split())


def require_posix_only(path):
    listing = checked(["/bin/ls", "-ldeb", str(path)]).decode().splitlines()
    require(len(listing) == 1 and not listing[0].split()[0].endswith("+"), "UNAPPROVED_MAC_ACCESS_LIST")


def no_sudo_policy(user):
    verdict = subprocess.run(["/usr/bin/sudo", "-n", "-l", "-U", user], capture_output=True, timeout=15,
                             env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LC_ALL": "C"})
    detail = (verdict.stdout + verdict.stderr).lower()
    return verdict.returncode == 1 and (b"not allowed to run sudo" in detail or b"may not run sudo" in detail)


def crypto_path(root):
    candidate = root / "bin" / "openssl"
    protected(candidate.parent, directory=True)
    protected(candidate)
    location = f"{candidate.parent}:/usr/bin:/bin:/usr/sbin:/sbin"
    os.environ["PATH"] = location
    return location


def prove_signing(root, evaluator, key, challenge, public):
    openssl = str(root / "bin" / "openssl")
    signed = checked(["/usr/bin/sudo", "-n", "-u", evaluator, "--", openssl, "pkeyutl", "-sign", "-rawin",
                      "-inkey", str(key), "-in", str(challenge)])
    with TemporaryDirectory() as directory:
        public_path, signature_path = Path(directory) / "public.pem", Path(directory) / "canary.sig"
        public_path.write_bytes(public)
        signature_path.write_bytes(signed)
        checked([openssl, "pkeyutl", "-verify", "-rawin", "-pubin", "-inkey", str(public_path), "-in",
                 str(challenge), "-sigfile", str(signature_path)])


def canary(root, state, owner_pin):
    require_mac()
    require(os.geteuid() == 0 and root.is_absolute() and root.resolve() == root, "SEPARATE_MAC_ADMINISTRATOR_REQUIRED")
    protected(root, directory=True)
    for directory in reversed((HERE, *HERE.parents)):
        protected(directory, directory=True)
    for name in RUNTIME_FILES:
        protected(HERE / name)
    manifest = protected(root / "authority.json")
    approval_sha = sha(manifest.read_bytes())
    policy = active_approval(verify(manifest, owner_pin)["receipt"], datetime.now(timezone.utc))
    approved = approved_mac(policy)
    binding = protected(root / "host-binding.json")
    require(sha(binding.read_bytes()) == policy["host_binding_sha256"] and
            read(binding) == {"hostname": socket.gethostname()}, "MAC_HOST_BINDING_UNAPPROVED")
    require(int(os.environ.get("SUDO_UID", "-1")) == approved["administrator_uid"], "WRONG_MAC_ADMINISTRATOR")
    admin, evaluator, constructor = (pwd.getpwuid(n) for n in
        (approved["administrator_uid"], policy["evaluator_uid"], policy["constructor_uid"]))
    require("admin" in name_groups(admin.pw_name) and all(not (name_groups(p.pw_name) & {"admin", "wheel", "sudo"})
            for p in (evaluator, constructor)) and evaluator.pw_name == policy["evaluator_user"] and
            evaluator.pw_gid == policy["evaluator_gid"], "MAC_GROUP_SEPARATION_UNPROVEN")
    require(all(no_sudo_policy(account.pw_name) for account in (evaluator, constructor)), "MAC_PRIVILEGE_SEPARATION_UNPROVEN")
    require(state == Path(policy["private_state"]) and state.resolve() == state, "MAC_CASE_STORE_UNAPPROVED")
    protected(state, directory=True, owner=evaluator.pw_uid, private=True)
    private_key = protected(state / "evaluator.key", owner=evaluator.pw_uid, private=True)
    public = checked(["openssl", "pkey", "-in", str(private_key), "-pubout"])
    require(sha(public) == policy["evaluator_key_sha256"] and sha(public) != owner_pin, "MAC_SIGNING_KEY_SCOPE_UNPROVEN")
    records = protected(root / "cleared-records", directory=True)
    require(records.stat().st_gid == evaluator.pw_gid and not records.stat().st_mode & 0o007 and
            not list(records.iterdir()), "CANARY_REQUIRES_EMPTY_PRIVATE_INTAKE")
    score = protected(root / "approved-code" / policy["score_entry"])
    require(sha(score.read_bytes()) == policy["code_sha256"][score.name], "APPROVED_MAC_SCORE_CHANGED")
    for path in (root, manifest, state, private_key, records, root / "approved-code", score):
        require_posix_only(path)
    staged = []
    try:
        for path, uid, gid, mode in ((state / ".nonconfidential-canary", evaluator.pw_uid, evaluator.pw_gid, 0o600),
                                      (records / ".nonconfidential-canary", 0, evaluator.pw_gid, 0o640)):
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
            staged.append(path)
            with os.fdopen(fd, "wb") as output:
                os.fchown(output.fileno(), uid, gid)
                output.write(DIAGNOSTIC)
        state_probe, record_probe = staged
        probes = [[label, str(path), write] for label, path, write in (
            ("case_read", state_probe, False), ("case_write", state_probe, True), ("key_read", private_key, False),
            ("record_read", record_probe, False), ("record_write", record_probe, True),
            ("approval_write", manifest, True), ("code_write", score, True))]
        measures = {}
        for role, person in (("evaluator", evaluator), ("constructor", constructor)):
            data = checked(["/usr/bin/sudo", "-n", "-u", person.pw_name, "--", sys.executable, "-I", "-B", "-c",
                            PROBE, json.dumps(probes)])
            measures[role] = json.loads(data)
        prove_signing(root, evaluator.pw_name, private_key, state_probe, public)
        receipt = {"schema": SCOPE, "recorded_utc": clock(), "approval_sha256": approval_sha,
                   "machine_binding_sha256": approved["machine_binding_sha256"], "runtime_files": approved["runtime_files"],
                   "administrator_uid": admin.pw_uid, "signing_canary_verified": True, **measures}
        validate_roles(receipt, policy, approved)
        require(sha(manifest.read_bytes()) == approval_sha, "MAC_APPROVAL_CHANGED_DURING_CANARY")
        receipt_path = root / "mac-canary.json"
        atomic(receipt_path, receipt)
        receipt_path.chmod(0o644)
        return {"state": "MAC_ROLE_CANARY_ACCEPTED", "redacted_receipt_sha256": sha(receipt_path.read_bytes())}
    finally:
        for path in staged:
            path.unlink(missing_ok=True)


def plist_document(root, state, owner_pin, authority, interval):
    return {"Label": LABEL, "ProgramArguments": [str(Path(sys.executable).resolve()), "-B", str(HERE / "mac_activation.py"),
            "run", "--authority-root", str(root), "--private-state", str(state), "--owner-pin", owner_pin],
            "UserName": authority["evaluator_user"], "StartInterval": interval, "ProcessType": "Background",
            "WorkingDirectory": str(state), "EnvironmentVariables": {"PATH": f"{root}/bin:/usr/bin:/bin:/usr/sbin:/sbin"}}


def runtime(root, state, owner_pin):
    require_mac()
    from standing_authority import run_available
    return run_available(root, owner_pin, state)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("describe", "inventory", "canary", "plist", "run"))
    parser.add_argument("--authority-root", type=Path)
    parser.add_argument("--private-state", type=Path)
    parser.add_argument("--owner-pin")
    args = parser.parse_args()
    try:
        if args.operation == "describe":
            result = {"state": "ON_DEVICE_APPROVAL_REQUIRED", "runtime_files": {name: sha((HERE / name).read_bytes())
                      for name in RUNTIME_FILES}, "platform_required": "Darwin", "launch_label": LABEL}
        elif args.operation == "inventory":
            require_mac()
            if args.authority_root is not None:
                crypto_path(args.authority_root)
            result = inventory()
        else:
            root, state, pin = args.authority_root, args.private_state, args.owner_pin
            require(root is not None and state is not None and pin is not None, "AUTHORITY_STATE_AND_PIN_REQUIRED")
            require_mac()
            crypto_path(root)
            if args.operation == "canary":
                result = canary(root, state, pin)
            elif args.operation == "plist":
                manifest = protected(root / "authority.json")
                authority = active_approval(verify(manifest, pin)["receipt"], datetime.now(timezone.utc))
                require_canary(root, authority, sha(manifest.read_bytes()))
                sys.stdout.buffer.write(plistlib.dumps(plist_document(root, state, pin, authority,
                    authority["mac_activation"]["interval_seconds"])))
                return 0
            else:
                result = runtime(root, state, pin)
        print(encode(result).decode(), end="")
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        term = str(error)
        reason = term if type(error) is ValueError and term.replace("_", "").isupper() else type(error).__name__
        print(encode({"state": "ABSTAIN", "reason": reason}).decode(), end="")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
