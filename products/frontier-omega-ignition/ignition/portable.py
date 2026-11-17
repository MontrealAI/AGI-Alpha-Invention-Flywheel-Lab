"""Entrypoint copied to a delivered package as run.py. Python 3.10+."""
from contextlib import ExitStack, contextmanager
import hashlib
import json
import os
import stat
import sys
from pathlib import Path


MEMBERS = (
    "README.txt", "artifact.json", "context.json", "contract.json", "example-input.json",
    "ignition/__init__.py", "ignition/construction.py", "ignition/evaluation.py", "receipt.json", "run.py",
)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _strict(raw):
    def refuse_constant(_):
        raise ValueError("nonfinite numeric literal")
    return json.loads(raw, object_pairs_hook=_unique, parse_constant=refuse_constant)


def semantic_receipt(receipt):
    # Wall-clock timing is an observation of one run, not a reproducible identity.
    return {k: v for k, v in receipt.items() if k not in ("telemetry_ns", "receipt_sha256")}


@contextmanager
def _directory(parent, name):
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    try:
        yield fd
    finally:
        os.close(fd)


def _stable(s):
    # Directory enumeration or regular-file reads can change atime.
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _hash_at(parent, name, snapshot):
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_NOCTTY", 0)
    fd = os.open(name, flags, dir_fd=parent)
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or _stable(opened) != _stable(snapshot):
            raise ValueError("file type or identity changed during audit")
        remaining = opened.st_size
        digest = hashlib.sha256()
        while remaining:
            chunk = os.read(fd, min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError("file ended during audit")
            digest.update(chunk)
            remaining -= len(chunk)
        if _stable(opened) != _stable(os.fstat(fd)):
            raise ValueError("file changed during audit")
        return digest.hexdigest()
    finally:
        os.close(fd)


def _audit_directory(artifact, selected):
    from ignition.construction import MAX_FILES, _logical_path, classify_manifest, execute
    if artifact.get("kind") != "manifest_audit":
        raise ValueError("audit-directory requires a manifest_audit package")
    execute(artifact, {"files": {}})  # Validate the compiled package and manifest before any target access.
    if (not all(hasattr(os, name) for name in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK"))
            or os.open not in os.supports_dir_fd or os.scandir not in os.supports_fd
            or os.stat not in os.supports_dir_fd or os.stat not in os.supports_follow_symlinks):
        raise ValueError("audit-directory requires POSIX descriptor-relative no-follow operations")
    chosen = Path(selected)
    if not selected or ".." in chosen.parts:
        raise ValueError("select a directory directly without parent traversal")
    trusted = artifact["program"]["manifest"]
    actual = {}
    visited = set()

    def scan(fd, prefix, root_device):
        before = os.fstat(fd)
        identity = (before.st_dev, before.st_ino)
        if before.st_dev != root_device or identity in visited:
            raise ValueError("refusing a cross-device or repeated directory")
        visited.add(identity)
        if len(visited) > MAX_FILES * 2:
            raise ValueError("directory inventory exceeded 512 directories")
        with os.scandir(fd) as entries:
            for entry in entries:
                name = entry.name
                relative = prefix + name
                _logical_path(relative)
                observed = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if observed.st_dev != root_device:
                    raise ValueError("refusing an entry on another device")
                if stat.S_ISDIR(observed.st_mode):
                    with _directory(fd, name) as child:
                        if _stable(os.fstat(child)) != _stable(observed):
                            raise ValueError("directory changed during audit")
                        scan(child, relative + "/", root_device)
                elif stat.S_ISREG(observed.st_mode) and observed.st_nlink == 1:
                    if len(actual) >= MAX_FILES:
                        raise ValueError("directory inventory exceeded 256 files")
                    # Unexpected names have no trusted digest. Never open their contents.
                    actual[relative] = _hash_at(fd, name, observed) if relative in trusted else None
                else:
                    raise ValueError("refusing symlink, multiply linked file or non-regular entry: " + relative)
                if _stable(os.stat(name, dir_fd=fd, follow_symlinks=False)) != _stable(observed):
                    raise ValueError("directory entry changed during audit")
        if _stable(os.fstat(fd)) != _stable(before):
            raise ValueError("directory changed during audit")

    # Open the operator-selected root component by component. O_NOFOLLOW on
    # the final component alone would still follow symlinks in its ancestors.
    with ExitStack() as stack:
        start = stack.enter_context(_directory(None, "/" if chosen.is_absolute() else "."))
        anchors = []
        components = chosen.parts[1:] if chosen.is_absolute() else chosen.parts
        for component in components:
            child = stack.enter_context(_directory(start, component))
            snapshot = os.fstat(child)
            anchors.append((start, component, (snapshot.st_dev, snapshot.st_ino)))
            start = child
        scan(start, "", os.fstat(start).st_dev)
        for parent, name, identity in anchors:
            now = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if (now.st_dev, now.st_ino) != identity:
                raise ValueError("operator-selected directory moved during audit")
    return classify_manifest(trusted, actual)


def _migrate_jsonl(artifact):
    from ignition.construction import MAX_BYTES, canonical, execute
    if artifact.get("kind") != "record_migration":
        raise ValueError("migrate-jsonl requires a record_migration package")
    execute(artifact, {"rows": []})
    emitted = 0
    while True:
        raw = sys.stdin.buffer.readline(MAX_BYTES + 1)
        if not raw:
            return 0
        try:
            if len(raw) > MAX_BYTES:
                raise ValueError("line exceeds 2 MiB")
            row = _strict(raw.decode("utf-8"))
            if not isinstance(row, dict):
                raise ValueError("one JSON object is required per line")
            out = execute(artifact, {"rows": [row]})["rows"][0]
            sys.stdout.buffer.write(canonical(out) + b"\n")
            sys.stdout.buffer.flush()
            emitted += 1
        except (ValueError, RecursionError) as error:
            print(json.dumps({"line": emitted + 1, "emitted": emitted,
                              "error": getattr(error, "code", "invalid_input"), "message": str(error)}), file=sys.stderr)
            return 2


def main():
    args = sys.argv[1:]
    if args not in (["verify"], ["run"], ["migrate-jsonl"]) and not (len(args) == 2 and args[0] == "audit-directory"):
        raise ValueError("Usage: python3 -I run.py verify | run < input.json | audit-directory DIR | migrate-jsonl < rows.jsonl")
    base = Path(__file__).resolve().parent
    hashes = _strict((base / "SHA256SUMS.json").read_bytes())
    if set(hashes) != set(MEMBERS):
        raise ValueError("unexpected bundle member list")
    for name in MEMBERS:
        path = base / name
        if path.is_symlink() or path.parent.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != hashes[name]:
            raise ValueError(f"bundle content differs: {name}")
    sys.path.insert(0, str(base))
    from ignition.construction import ConstructionError, MAX_BYTES, canonical, execute
    from ignition.evaluation import check_receipt_integrity, evaluate
    artifact = _strict((base / "artifact.json").read_bytes())
    if args[0] == "audit-directory":
        result = _audit_directory(artifact, args[1])
        print(canonical(result).decode())
        return 0 if result["ok"] else 1
    if args[0] == "migrate-jsonl":
        return _migrate_jsonl(artifact)
    if args[0] == "verify":
        contract = _strict((base / "contract.json").read_bytes())
        archived = _strict((base / "receipt.json").read_bytes())
        check_receipt_integrity(archived)
        new = evaluate(contract, artifact)
        if new["status"] != "pass" or canonical(semantic_receipt(archived)) != canonical(semantic_receipt(new)):
            raise ValueError("reproduction failed or accepted scope changed")
        print(json.dumps({"status": "pass", "contract_sha256": contract["sha256"], "artifact_sha256": artifact["sha256"],
                          "cases": len(new["cases"]), "comparison": new["comparison"]["outcome"]}))
    else:
        data = sys.stdin.buffer.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("input exceeds 2 MiB")
        try:
            result = execute(artifact, _strict(data))
        except ConstructionError as error:
            print(json.dumps({"error": error.code, "message": str(error)}), file=sys.stderr)
            return 2
        print(canonical(result).decode())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RecursionError) as failure:
        print(str(failure), file=sys.stderr)
        raise SystemExit(2)
