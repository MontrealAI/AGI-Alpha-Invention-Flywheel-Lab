"""Fail-closed HARNESS prerelease asset inventory.

Only zero-byte optional stderr probe logs can be omitted from the GitHub Release
upload. They remain in the original hosted artifacts, and their names are
recorded in the public inventory. No input data or account state is modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat


SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z", re.ASCII)
MANIFEST = "HARNESS-PUBLICATION-ASSET-INVENTORY.json"


def prepare(directory: Path, source: str, paths0: Path) -> dict:
    directory = Path(directory)
    paths0 = Path(paths0)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("RELEASE_DIRECTORY_MUST_BE_OWNED_DIRECTORY")
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise ValueError("EXACT_COMMIT_SHA_REQUIRED")
    manifest = directory / MANIFEST
    if manifest.exists() or manifest.is_symlink():
        raise ValueError("PREEXISTING_RELEASE_INVENTORY")
    if paths0.resolve().is_relative_to(directory.resolve()):
        raise ValueError("PATHS0_MUST_BE_OUTSIDE_ASSET_DIRECTORY")
    if paths0.exists() or paths0.is_symlink():
        raise ValueError("PREEXISTING_ASSET_PATH_LIST")

    kept, omitted = [], []
    for path in sorted(directory.iterdir(), key=lambda entry: entry.name):
        if not SAFE_NAME.fullmatch(path.name) or path.name in (".", ".."):
            raise ValueError("UNSAFE_RELEASE_ASSET_NAME")
        meta = path.lstat()
        if not stat.S_ISREG(meta.st_mode):
            raise ValueError("NOT_A_DIRECT_REGULAR_ASSET:" + path.name)
        size = meta.st_size
        if not size:
            if not path.name.endswith(".stderr.txt"):
                raise ValueError("EMPTY_REQUIRED_RELEASE_ASSET:" + path.name)
            omitted.append({"name": path.name, "size": 0, "reason": "EMPTY_OPTIONAL_STDERR"})
            continue
        payload = path.read_bytes()
        if len(payload) != size or path.lstat().st_mtime_ns != meta.st_mtime_ns:
            raise ValueError("ASSET_CHANGED_DURING_PREFLIGHT:" + path.name)
        kept.append({"name": path.name, "size": size, "sha256": hashlib.sha256(payload).hexdigest()})
    if not kept or not any(row["name"].endswith(".zip") for row in kept):
        raise ValueError("NONEMPTY_SOURCE_ARCHIVE_REQUIRED")

    inventory = {
        "schema": "agi-alpha/harness124-publication-inventory/v1",
        "source_commit": source,
        "status": "PREPARED_NOT_PUBLISHED",
        "included": kept,
        "omitted_only_empty_stderr": omitted,
        "historical_failures_unchanged": True,
    }
    encoded = json.dumps(inventory, indent=2, sort_keys=True, allow_nan=False).encode() + b"\n"
    manifest.write_bytes(encoded)
    files = [directory / row["name"] for row in kept] + [manifest]
    paths0.parent.mkdir(parents=True, exist_ok=True)
    paths0.write_bytes(b"\0".join(os.fsencode(str(path)) for path in files) + b"\0")
    return inventory


def main() -> None:
    parser = argparse.ArgumentParser(description="Preflight release assets before GitHub Release transport")
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--source", required=True)
    parser.add_argument("--paths0", required=True, type=Path)
    args = parser.parse_args()
    result = prepare(args.directory, args.source, args.paths0)
    print(json.dumps({
        "status": result["status"], "source_commit": result["source_commit"],
        "included_count": len(result["included"]) + 1,
        "omitted_empty_stderr_count": len(result["omitted_only_empty_stderr"]),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
