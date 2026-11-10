#!/usr/bin/env python3
"""Create or verify a deterministic, source-bound HARNESS distribution.

Copyright 2026 Vincent Boucher. SPDX-License-Identifier: Apache-2.0
No dependency downloads, credentials, model calls or repository mutations.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

PRODUCT = Path(__file__).resolve().parents[1]
REPOSITORY = PRODUCT.parents[1]
PREFIX = "products/alpha-genesis-harness/"
VERSION = "0.3.0"
MAX_ARCHIVE = 300_000_000
ALLOWED_DIRS = {"app", "bridge", "docs", "scripts", "tests", "evidence", "commercial", "examples"}
ALLOWED_ROOT = {"LICENSE", "NOTICE", "README.md", "SECURITY.md", "CONTRIBUTING.md", "START-HERE.html", "GUIDE.html", "VERSION.json", "THIRD-PARTY.json", "launch.py", "Launch-HARNESS.command", "Launch-HARNESS.sh", "Launch-HARNESS.cmd", "requirements-chatgpt.txt"}
EXECUTABLE_FILES = {"Launch-HARNESS.command", "Launch-HARNESS.sh"}
SUFFIXES = {".py", ".js", ".cjs", ".mjs", ".html", ".css", ".md", ".txt", ".json", ".csv", ".svg", ".png", ".jpg", ".yml", ".yaml", ".sh", ".cmd", ".command"}
REQUIRED = {"LICENSE", "NOTICE", "README.md", "START-HERE.html", "VERSION.json", "THIRD-PARTY.json", "app/index.html", "app/app.js", "app/engine.js", "app/styles.css"}
BLOCKED_PARTS = {"__pycache__", "node_modules", ".git", ".venv", "venv", "private", "credentials", "dist"}
MANIFEST_NAME = "RELEASE-MANIFEST.json"


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(REPOSITORY), *args], stderr=subprocess.PIPE)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_file(name: str) -> bool:
    path = PurePosixPath(name)
    if not name or path.as_posix() != name or path.is_absolute() or "\\" in name or any(p in {"", ".", ".."} for p in path.parts):
        return False
    if any(part.startswith(".") or part in BLOCKED_PARTS for part in path.parts):
        return False
    if len(path.parts) == 1:
        return name in ALLOWED_ROOT
    return path.parts[0] in ALLOWED_DIRS and path.suffix.lower() in SUFFIXES


def check_bytes(name: str, data: bytes) -> None:
    if len(data) > 30_000_000:
        raise ValueError(f"Oversized file requires explicit packaging review: {name}")
    if re.search(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", data):
        raise ValueError(f"Private key material detected: {name}")
    if re.search(rb"(?:sk-proj-|sk-ant-api\d{2}-)[A-Za-z0-9_-]{24,}", data):
        raise ValueError(f"Possible provider credential detected: {name}")


def collect(revision: str, candidate: bool) -> tuple[dict[str, bytes], str, str | None]:
    resolved = git("rev-parse", "--verify", revision + "^{commit}").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", resolved):
        raise ValueError("Expected a complete Git commit identifier")
    content: dict[str, bytes] = {}
    if candidate:
        for path in sorted(PRODUCT.rglob("*")):
            relative = path.relative_to(PRODUCT).as_posix()
            if safe_file(relative):
                if path.is_symlink():
                    raise ValueError(f"Symlinks cannot be packaged: {relative}")
                if path.is_file():
                    content[relative] = path.read_bytes()
        tree = None
    else:
        lines = git("ls-tree", "-r", "-z", resolved, "--", PREFIX).split(b"\0")
        for line in lines:
            if not line:
                continue
            meta, raw_path = line.split(b"\t", 1)
            mode, kind, blob = meta.decode().split()
            path = raw_path.decode("utf-8")
            relative = path[len(PREFIX):]
            if not safe_file(relative):
                continue
            if kind != "blob" or mode not in {"100644", "100755"}:
                raise ValueError(f"Only ordinary source files may be distributed: {relative}")
            content[relative] = git("cat-file", "blob", blob)
        tree = git("rev-parse", resolved + ":" + PREFIX.rstrip("/")).decode().strip()
    missing = REQUIRED.difference(content)
    if missing:
        raise ValueError("Required product files are absent: " + ", ".join(sorted(missing)))
    for name, data in content.items():
        check_bytes(name, data)
    version = json.loads(content["VERSION.json"])
    if version.get("version") != VERSION:
        raise ValueError("Packager version and VERSION.json disagree")
    return content, resolved, tree


def build(output: Path, revision: str, candidate: bool = False) -> dict:
    files, source_revision, tree = collect(revision, candidate)
    mode = "candidate" if candidate else "source-bound"
    root = f"ALPHA_GENESIS_HARNESS_{VERSION}"
    manifest = {
        "schema": "alpha-genesis-harness-release/v1",
        "product": "ALPHA GENESIS FLYWHEEL Ω HARNESS",
        "version": VERSION,
        "release_status": "release-candidate",
        "build_mode": mode,
        "source_repository": "https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab",
        "source_revision": source_revision,
        "source_product_tree": tree,
        "source_matches_commit": not candidate,
        "source_scope": PREFIX.rstrip("/"),
        "licence_scope": "Newly authored product code only; see LICENSE, NOTICE and THIRD-PARTY.json",
        "qualification": "Build integrity is not customer, provider, commerce or research qualification; see evidence/.",
        "files": [{"path": name, "bytes": len(data), "sha256": digest(data)} for name, data in sorted(files.items())],
    }
    files[MANIFEST_NAME] = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"{root}_{mode}_{source_revision[:12]}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(root + "/" + name, date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name in EXECUTABLE_FILES else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    if archive.stat().st_size >= MAX_ARCHIVE:
        archive.unlink()
        raise ValueError("Archive exceeds the verified Squarespace Download-product ceiling")
    receipt = verify(archive, expected_source_revision=source_revision, compare_source_revision=None if candidate else source_revision)
    receipt.update({"archive": str(archive.resolve())})
    archive.with_suffix(".zip.sha256").write_text(receipt["archive_sha256"] + "  " + archive.name + "\n", encoding="utf-8")
    archive.with_suffix(".receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return receipt


def verify(archive: Path, expected_sha256: str | None = None, expected_source_revision: str | None = None, compare_source_revision: str | None = None) -> dict:
    # Hash and ZIP interpretation share one bounded immutable snapshot. A path
    # replacement between a separate hash read and ZipFile open must not rebind it.
    with archive.open("rb") as source:
        snapshot = source.read(MAX_ARCHIVE)
        if len(snapshot) >= MAX_ARCHIVE or source.read(1):
            raise ValueError("Archive is too large")
    return verify_snapshot(snapshot, expected_sha256, expected_source_revision, compare_source_revision)


def verify_snapshot(snapshot: bytes, expected_sha256: str | None = None, expected_source_revision: str | None = None, compare_source_revision: str | None = None) -> dict:
    """Verify the same immutable bytes a caller will subsequently extract/use."""
    if not isinstance(snapshot, bytes):
        raise ValueError("Archive snapshot must be immutable bytes")
    if len(snapshot) >= MAX_ARCHIVE:
        raise ValueError("Archive is too large")
    archive_sha256 = digest(snapshot)
    if expected_sha256 is not None:
        if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256) or archive_sha256 != expected_sha256:
            raise ValueError("Archive does not match the externally expected SHA-256")
    if expected_source_revision is not None and not re.fullmatch(r"[0-9a-f]{40}", expected_source_revision):
        raise ValueError("Expected source revision must be a complete Git commit identifier")
    with zipfile.ZipFile(io.BytesIO(snapshot)) as bundle:
        names = bundle.namelist()
        if not names or len(names) != len(set(names)):
            raise ValueError("Empty archive or duplicate member names")
        roots = {name.split("/", 1)[0] for name in names}
        if roots != {f"ALPHA_GENESIS_HARNESS_{VERSION}"}:
            raise ValueError("Unexpected archive root")
        root = next(iter(roots)) + "/"
        relative = [name[len(root):] for name in names]
        if any(not safe_file(name) and name != MANIFEST_NAME for name in relative):
            raise ValueError("Unsafe or unapproved archive path")
        if any(info.file_size > 30_000_000 or ((info.external_attr >> 16) & 0o170000) == 0o120000 for info in bundle.infolist()):
            raise ValueError("Oversized or symlink archive member")
        if sum(info.file_size for info in bundle.infolist()) > MAX_ARCHIVE:
            raise ValueError("Expanded archive is too large")
        manifest = json.loads(bundle.read(root + MANIFEST_NAME))
        if manifest.get("schema") != "alpha-genesis-harness-release/v1" or manifest.get("version") != VERSION:
            raise ValueError("Unsupported release manifest")
        if manifest.get("build_mode") not in {"candidate", "source-bound"}:
            raise ValueError("Unsupported build mode")
        if manifest.get("source_matches_commit") is not (manifest["build_mode"] == "source-bound"):
            raise ValueError("Build mode and source qualification disagree")
        if manifest["build_mode"] == "source-bound" and not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("source_product_tree", ""))):
            raise ValueError("Source-bound archive needs a product tree identifier")
        if manifest["build_mode"] == "candidate" and manifest.get("source_product_tree") is not None:
            raise ValueError("Working-tree candidate cannot assert a committed source tree")
        if not isinstance(manifest.get("source_revision"), str) or not re.fullmatch(r"[0-9a-f]{40}", manifest["source_revision"]):
            raise ValueError("Invalid source revision")
        if expected_source_revision is not None and manifest["source_revision"] != expected_source_revision:
            raise ValueError("Manifest does not name the externally expected source revision")
        records = manifest.get("files")
        if not isinstance(records, list) or any(not isinstance(r, dict) or not isinstance(r.get("path"), str) for r in records):
            raise ValueError("Invalid manifest inventory")
        expected = [record["path"] for record in records]
        if len(expected) != len(set(expected)) or set(relative) != set(expected) | {MANIFEST_NAME} or not REQUIRED.issubset(expected):
            raise ValueError("Manifest inventory does not match archive")
        for record in records:
            data = bundle.read(root + record["path"])
            if len(data) != record.get("bytes") or digest(data) != record.get("sha256"):
                raise ValueError("Hash or size mismatch: " + record["path"])
            check_bytes(record["path"], data)
        source_compared = False
        if compare_source_revision is not None:
            source_files, resolved, tree = collect(compare_source_revision, False)
            if manifest["build_mode"] != "source-bound" or manifest["source_revision"] != resolved or manifest["source_product_tree"] != tree:
                raise ValueError("Manifest source identity differs from the independently selected Git source")
            if set(source_files) != set(expected):
                raise ValueError("Archive inventory differs from selected Git source")
            for name, data in source_files.items():
                if bundle.read(root + name) != data:
                    raise ValueError("Archive bytes differ from selected Git source: " + name)
            source_compared = True
        return {"schema": "alpha-genesis-harness-integrity/v1", "integrity": "PASSED IN SCOPE", "version": VERSION,
                "archive_sha256": archive_sha256, "archive_bytes": len(snapshot),
                "source_revision": manifest["source_revision"], "source_claim_matches_commit": manifest.get("source_matches_commit") is True,
                "source_matches_commit": source_compared,
                "build_mode": manifest.get("build_mode"), "file_count": len(records),
                "external_archive_hash_matched": expected_sha256 is not None,
                "expected_source_revision_matched": expected_source_revision is not None,
                "meaning": "All listed file bytes match this archive's manifest. Authenticate the archive hash against the public release independently."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("build", help="Build from exact Git source; candidate mode includes current approved working files")
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--source-revision", required=True)
    create.add_argument("--candidate", action="store_true")
    check = commands.add_parser("verify", help="Verify archive inventory, safe paths and SHA-256 hashes")
    check.add_argument("archive", type=Path)
    check.add_argument("--expected-sha256", help="SHA-256 independently obtained from the trusted public release")
    check.add_argument("--expected-source-revision", help="Expected full source commit from the trusted public release")
    check.add_argument("--compare-source-revision", help="Compare all archive bytes with this independently selected source commit; requires repository checkout")
    args = parser.parse_args()
    try:
        result = build(args.output, args.source_revision, args.candidate) if args.command == "build" else verify(args.archive, args.expected_sha256, args.expected_source_revision, args.compare_source_revision)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        print(json.dumps({"integrity": "INVALID", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
