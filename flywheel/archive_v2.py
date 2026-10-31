"""Content-verified source archives and unchanged historical replay.

New builds omit only the exact root enterprise011/adaptive012 multipart transport
directories and their generated combined ZIPs, avoiding recursive embedding of a
newer package inside this older bounded source archive. Current code, financial records and other artifacts remain included. A narrow
hash-pinned list of completed historical engineering logs is omitted from new
source packages only; exact originals remain in Git and linked by the omission
manifest. Old archives retain their original complete manifest verification. The extractor still verifies every
declared payload of older archives, including transport files already present.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import stat
import zipfile

OLD_FREEZE = "fa2a87c8bc6a41c4444fea28b10d8d09e25971e06d1e61d0cbb84ba399e2a55c"
OLD_COMMIT = "90791dbf8cc8d9d53e5d58b997887882fa2e5f00"
PREFIX = "AGI_ALPHA_Mechanism_Completion/"
MANIFEST = "ARCHIVE_MANIFEST.json"
SKIP = {".git", ".venv", "__pycache__", ".pytest_cache"}
MAX_BYTES, MAX_FILES = 512 * 1024**2, 10000
OMISSIONS = "docs/packaging/SOURCE_ONLY_OMISSIONS.json"
TRANSACTION_PREFIXES = (".commercial010-package-", ".publication-")


def _excluded(path):
    return bool(set(path.parts) & SKIP) or any(part.startswith(TRANSACTION_PREFIXES) for part in path.parts)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _name(value):
    path = Path(value)
    if not isinstance(value, str) or path.is_absolute() or ".." in path.parts or not path.parts or "\\" in value or path.as_posix() != value:
        raise ValueError("ARCHIVE_PATH_SCOPE")
    return path


def _regular(root, name):
    path = Path(root) / _name(name)
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError("ARCHIVE_SYMLINK_REFUSED")
    if not path.is_file():
        raise ValueError("HISTORICAL_INPUT_MISSING " + str(name))
    return path.read_bytes()


def materialize_cycle004(root, destination):
    root, destination = Path(root).resolve(), Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    freeze_raw = _regular(root, "historical/cycle-004/FREEZE.json.txt")
    if _sha(freeze_raw) != OLD_FREEZE:
        raise ValueError("HISTORICAL_FREEZE_IDENTITY_MISMATCH")
    frozen = json.loads(freeze_raw)
    if len(frozen["sources"]) != 22:
        raise ValueError("HISTORICAL_SOURCE_SET_MISMATCH")
    payloads = {"campaign/cycle-004/FREEZE.json": freeze_raw}
    for name, expected in frozen["sources"].items():
        _name(name)
        raw = _regular(root, "historical/cycle-004/files/" + name + ".txt")
        if _sha(raw) != expected:
            raise ValueError("HISTORICAL_SOURCE_IDENTITY_MISMATCH " + name)
        payloads[name] = raw
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in payloads.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
    receipt = {"schema": "lab/cycle004-unchanged-source-snapshot/v1", "commit": OLD_COMMIT,
               "freeze_sha256": OLD_FREEZE, "paths": {name: _sha(raw) for name, raw in payloads.items()},
               "scope": "Historical source unchanged, exposed pilot only; no new qualification inferred"}
    with (destination / "CYCLE004_SNAPSHOT.json").open("x") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    return receipt


def _manifest(raw, payloads):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("ARCHIVE_MANIFEST_DUPLICATE_KEY")
            result[key] = value
        return result
    try:
        manifest = json.loads(raw, object_pairs_hook=unique)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("ARCHIVE_MANIFEST_INVALID_JSON") from error
    if type(manifest) is not dict or manifest.get("schema") != "lab/self-contained-source-archive/v2" or type(manifest.get("files")) is not dict:
        raise ValueError("ARCHIVE_MANIFEST_SET_MISMATCH")
    for name, expected in manifest["files"].items():
        path = _name(name)
        if name == MANIFEST or _excluded(path) or type(expected) is not str or len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
            raise ValueError("ARCHIVE_MANIFEST_ENTRY_SCOPE")
    if set(payloads) != set(manifest["files"]):
        raise ValueError("ARCHIVE_MANIFEST_SET_MISMATCH")
    if any(_sha(raw) != manifest["files"][name] for name, raw in payloads.items()):
        raise ValueError("ARCHIVE_CONTENT_IDENTITY_MISMATCH")
    return manifest


def _engineering_log_scope(relative):
    # Only completed engineering transcript areas; never financial/output records.
    if relative.parts[:2] == ("evidence", "completion015"):
        return relative.suffix in {".log", ".stdout", ".stderr"}
    if relative.suffix != ".log":
        return False
    if relative.parent.as_posix() in {"evidence/connected014/engineering", "evidence/enterprise011", "evidence/commercial010/qualification"}:
        return True
    return relative.parent.as_posix() == "evidence/adaptive012" and relative.name in {
        "imported-allocation-ownership-tests.log", "initial-137-tests.log",
        "CI-adaptive-current.log", "CI-public-package.log", "CI-historical-general.log"}


def _source_log_omissions(root):
    path = Path(root) / OMISSIONS
    if not path.exists():
        return {}
    raw = _regular(root, OMISSIONS)
    record = json.loads(raw)
    files = record.get("files")
    if record.get("schema") != "lab/source-package-omissions/v1" or not isinstance(files, dict) or len(files) > 128:
        raise ValueError("BOUNDED_SOURCE_LOG_OMISSIONS_REQUIRED")
    for name, entry in files.items():
        relative = _name(name)
        if (not _engineering_log_scope(relative)
                or not isinstance(entry, dict) or set(entry) != {"sha256", "bytes"}
                or type(entry["bytes"]) is not int or entry["bytes"] < 0
                or not isinstance(entry["sha256"], str) or len(entry["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in entry["sha256"])):
            raise ValueError("SOURCE_LOG_OMISSION_SCOPE")
    return files


def build(root, archive_path):
    root, archive_path = Path(root).resolve(), Path(archive_path).absolute()
    if archive_path.exists() or archive_path.is_symlink():
        raise FileExistsError(archive_path)
    payloads, packaging_manifest = {}, None
    omitted_logs = _source_log_omissions(root)
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if _excluded(relative) or path == archive_path:
            continue
        if relative.parts[:2] in {("artifacts", "enterprise011-parts"), ("artifacts", "adaptive012-parts")} or relative.as_posix() in {"artifacts/AGI_ALPHA_Enterprise_011_source_evidence.zip", "artifacts/AGI_ALPHA_Adaptive_012_source_evidence.zip"}:
            continue
        if path.is_symlink():
            raise ValueError("ARCHIVE_SYMLINK_REFUSED " + str(relative))
        if path.is_file():
            name = relative.as_posix()
            if name == MANIFEST:
                if path.stat().st_size > MAX_BYTES:
                    raise ValueError("ARCHIVE_RESOURCE_BOUND")
                packaging_manifest = path.read_bytes()
                continue
            raw = path.read_bytes()
            if name in omitted_logs:
                expected = omitted_logs[name]
                if len(raw) != expected["bytes"] or _sha(raw) != expected["sha256"]:
                    raise ValueError("SOURCE_LOG_OMISSION_IDENTITY_CHANGED " + name)
                continue
            payloads[name] = raw
    if len(payloads) > MAX_FILES or sum(map(len, payloads.values())) > MAX_BYTES:
        raise ValueError("ARCHIVE_RESOURCE_BOUND")
    if packaging_manifest is not None:
        _manifest(packaging_manifest, payloads)
    manifest = {"schema": "lab/self-contained-source-archive/v2", "files": {name: _sha(raw) for name, raw in payloads.items()},
                "source_history_required": False, "network_required_for_extraction": False,
                "omitted_historical_engineering_logs": omitted_logs,
                "omission_provenance": OMISSIONS if omitted_logs else None,
                "scope": "Executable source and retained evidence; omitted engineering logs remain at pinned Git URLs, not in this package.",
                "limits": {"files": MAX_FILES, "uncompressed_bytes": MAX_BYTES}}
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in payloads.items():
            archive.writestr(PREFIX + name, raw)
        archive.writestr(PREFIX + MANIFEST, json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return {"archive_sha256": _sha(archive_path.read_bytes()), "archive_bytes": archive_path.stat().st_size,
            "files": len(payloads), "manifest": manifest}


def extract(archive_path, destination):
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    if any(parent.is_symlink() for parent in destination.parents):
        raise ValueError("ARCHIVE_SYMLINK_REFUSED")
    payloads = {}
    with zipfile.ZipFile(archive_path) as archive:
        records = archive.infolist()
        if len(records) > MAX_FILES + 1 or sum(item.file_size for item in records) > MAX_BYTES:
            raise ValueError("ARCHIVE_RESOURCE_BOUND")
        for item in records:
            if not item.filename.startswith(PREFIX) or item.is_dir() or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError("ARCHIVE_ENTRY_SCOPE")
            name = item.filename[len(PREFIX):]
            _name(name)
            if name in payloads:
                raise ValueError("ARCHIVE_DUPLICATE_ENTRY")
            payloads[name] = archive.read(item)
    if MANIFEST not in payloads:
        raise ValueError("ARCHIVE_MANIFEST_MISSING")
    manifest = _manifest(payloads.pop(MANIFEST), payloads)
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in payloads.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "extract", "cycle004"])
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    result = {"build": build, "extract": extract, "cycle004": materialize_cycle004}[args.action](args.source, args.destination)
    print(json.dumps({"action": args.action, "destination": str(args.destination),
                      "files": len(result.get("files", result.get("paths", {}))) if isinstance(result.get("files", {}), dict) else result.get("files")}))


if __name__ == "__main__":
    main()
