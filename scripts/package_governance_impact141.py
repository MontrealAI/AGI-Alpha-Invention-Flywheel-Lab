"""Deterministic, key-free transport for the offline Governance Impact140 research prototype.

Not a signed compliance deliverable, commercial release or native-account migration.
Uses a fixed allowlist; independent expected digests must come from outside the ZIP.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

SCHEMA = "agi-alpha/governance-portable141/v1"
FILES = (
    "campaign/governance-portable141/PROTOCOL.md",
    "campaign/public-demand140/EVIDENCE_RECONCILIATION_20261112.md",
    "campaign/public-demand140/PROTOCOL.md",
    "products/governance_impact140/README.md",
    "products/governance_impact140/__init__.py",
    "products/governance_impact140/engine.py",
    "tests/test_governance_impact140.py",
)
MANIFEST_NAME = "MANIFEST.json"
MAX_FILE_BYTES = 4_000_000
MAX_TOTAL_BYTES = 20_000_000


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(data: object) -> bytes:
    return (json.dumps(data, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _hash(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise ValueError("VALID_SHA256_REQUIRED")
    return value


def _commit(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch("[0-9a-f]{40}", value) is None:
        raise ValueError("VALID_COMMIT_REQUIRED")
    return value


def _files(root: Path) -> dict[str, bytes]:
    base = root.resolve(strict=True)
    output = {}
    for name in FILES:
        path = base / name
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(base) or not resolved.is_file():
            raise ValueError("SOURCE_OUTSIDE_ROOT_OR_NOT_FILE")
        contents = resolved.read_bytes()
        if len(contents) > MAX_FILE_BYTES:
            raise ValueError("SOURCE_FILE_TOO_LARGE")
        output[name] = contents
    return output


def build(root: Path, archive: Path, receipt: Path, commit: str) -> dict:
    commit = _commit(commit)
    files = _files(root)
    manifest = {
        "schema": SCHEMA,
        "scope": "OFFLINE_SYNTHETIC_RESEARCH_ONLY_NO_COMPLIANCE_APPROVAL",
        "source_commit": commit,
        "files": {name: digest(value) for name, value in sorted(files.items())},
    }
    files[MANIFEST_NAME] = canonical(manifest)
    if sum(len(value) for value in files.values()) > MAX_TOTAL_BYTES:
        raise ValueError("PACKAGE_TOO_LARGE")
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9, allowZip64=False) as z:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            z.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED,
                       compresslevel=9)
    data = bio.getvalue()
    report = {
        "schema": SCHEMA,
        "scope": manifest["scope"],
        "source_commit": commit,
        "archive_sha256": digest(data),
        "manifest_sha256": digest(files[MANIFEST_NAME]),
        "file_count": len(files),
        "claim": "PORTABLE_ENGINEERING_ONLY_NO_BUYER_OR_NATIVE_FINANCE",
    }
    archive.parent.mkdir(parents=True, exist_ok=True)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    with archive.open("xb") as f:
        f.write(data)
    with receipt.open("x", encoding="utf-8") as f:
        f.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def verify(archive: Path, *, expected_sha256: str, expected_commit: str,
           expected_manifest_sha256: str, extract: Path | None = None) -> dict:
    expected_sha256 = _hash(expected_sha256)
    expected_manifest_sha256 = _hash(expected_manifest_sha256)
    expected_commit = _commit(expected_commit)
    data = archive.read_bytes()
    if digest(data) != expected_sha256:
        raise ValueError("EXTERNAL_ARCHIVE_DIGEST_MISMATCH")
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = set()
        contents = {}
        for info in z.infolist():
            name = info.filename
            path = PurePosixPath(name)
            if (not name or "\\" in name or path.is_absolute()
                    or ".." in path.parts or name.endswith("/")
                    or name != path.as_posix()):
                raise ValueError("UNSAFE_ARCHIVE_PATH")
            if name in names:
                raise ValueError("DUPLICATE_ARCHIVE_MEMBER")
            if stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK:
                raise ValueError("ARCHIVE_SYMLINK_FORBIDDEN")
            names.add(name)
            if name not in set(FILES) | {MANIFEST_NAME}:
                raise ValueError("UNREGISTERED_ARCHIVE_MEMBER")
            if info.file_size > MAX_FILE_BYTES:
                raise ValueError("ARCHIVE_FILE_TOO_LARGE")
            contents[name] = z.read(info)
        if names != set(FILES) | {MANIFEST_NAME}:
            raise ValueError("INCOMPLETE_ARCHIVE")
        if sum(len(value) for value in contents.values()) > MAX_TOTAL_BYTES:
            raise ValueError("ARCHIVE_TOO_LARGE")
    if digest(contents[MANIFEST_NAME]) != expected_manifest_sha256:
        raise ValueError("EXTERNAL_MANIFEST_DIGEST_MISMATCH")
    manifest = json.loads(contents[MANIFEST_NAME], object_pairs_hook=_unique)
    if (set(manifest) != {"schema", "scope", "source_commit", "files"}
            or manifest["schema"] != SCHEMA
            or manifest["scope"] != "OFFLINE_SYNTHETIC_RESEARCH_ONLY_NO_COMPLIANCE_APPROVAL"
            or manifest["source_commit"] != expected_commit
            or not isinstance(manifest["files"], dict)
            or set(manifest["files"]) != set(FILES)):
        raise ValueError("INVALID_PACKAGE_MANIFEST")
    if canonical(manifest) != contents[MANIFEST_NAME]:
        raise ValueError("NONCANONICAL_MANIFEST")
    for name in FILES:
        if digest(contents[name]) != _hash(manifest["files"][name]):
            raise ValueError("ARCHIVE_SOURCE_HASH_MISMATCH")
    if extract is not None:
        extract.mkdir(parents=True, exist_ok=False)
        for name, value in contents.items():
            destination = extract / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as f:
                f.write(value)
    return {"accepted": True, "source_commit": expected_commit,
            "file_count": len(contents), "archive_sha256": expected_sha256,
            "manifest_sha256": expected_manifest_sha256,
            "scope": manifest["scope"]}


def _unique(pairs):
    row = {}
    for k, v in pairs:
        if k in row:
            raise ValueError("DUPLICATE_JSON_FIELD")
        row[k] = v
    return row


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    make = subs.add_parser("build")
    make.add_argument("--root", type=Path, required=True)
    make.add_argument("--archive", type=Path, required=True)
    make.add_argument("--receipt", type=Path, required=True)
    make.add_argument("--source-commit", required=True)
    check = subs.add_parser("verify")
    check.add_argument("--archive", type=Path, required=True)
    check.add_argument("--expected-sha256", required=True)
    check.add_argument("--expected-manifest-sha256", required=True)
    check.add_argument("--expected-commit", required=True)
    check.add_argument("--extract", type=Path)
    args = parser.parse_args(argv)
    if args.command == "build":
        result = build(args.root, args.archive, args.receipt, args.source_commit)
    else:
        result = verify(args.archive, expected_sha256=args.expected_sha256,
                        expected_manifest_sha256=args.expected_manifest_sha256,
                        expected_commit=args.expected_commit, extract=args.extract)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
