#!/usr/bin/env python3
"""Verify and package the canonical CONTINUITY OMEGA publication.

Usage:
    python3 package.py --output /tmp/continuity-publication-NEW

The output must be a new absolute directory outside this paper's source
directory. The command runs verify.py before producing either deliverable.
It then snapshots the exact manifest-listed bytes, checks their identities
again, and emits both complete language PDFs and CONTINUITY_OMEGA_SOURCE.zip.
Le paquet contient les deux articles intégraux et toutes les sources bilingues.

The ZIP contains the complete PUBLICATION.json inventory plus the manifest
under CONTINUITY_OMEGA/. It includes the canonical PDF. File ordering,
timestamps, permissions, and compression settings are normalized; build
outputs, bytecode caches, and unlisted files are never included. No source
file or existing output is modified. Packaging is not scientific validation
beyond the checks explicitly performed by verify.py.

Python 3.10+; this script uses only the standard library. The existing verifier
also needs pdfinfo/pdftotext as described in the paper's build instructions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parent
MANIFEST_NAME = "PUBLICATION.json"
PDF_NAME = "CONTINUITY_OMEGA.pdf"
PDF_NAMES = (PDF_NAME, "CONTINUITY_OMEGA_FR.pdf")
ZIP_NAME = "CONTINUITY_OMEGA_SOURCE.zip"
ZIP_PREFIX = "CONTINUITY_OMEGA/"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked_path(relative: str) -> Path:
    """Permit regular, canonical manifest paths without following symlinks."""
    require(isinstance(relative, str) and bool(relative), "Invalid empty manifest path")
    path = PurePosixPath(relative)
    require(not path.is_absolute() and path.as_posix() == relative
            and ".." not in path.parts and "\\" not in relative and "\0" not in relative,
            f"Invalid package-relative path: {relative!r}")
    require("build" not in path.parts and "__pycache__" not in path.parts
            and not relative.endswith((".pyc", ".pyo")),
            f"Excluded artifact in publication inventory: {relative}")
    current = ROOT
    for component in path.parts:
        current = current / component
        require(not current.is_symlink(), f"Symlinks are not packaged: {relative}")
    require(current.resolve().is_relative_to(ROOT), f"Path leaves the paper directory: {relative}")
    require(current.is_file(), f"Publication file is missing or not regular: {relative}")
    require(stat.S_ISREG(current.stat().st_mode), f"Publication file is not regular: {relative}")
    return current


def verify_publication() -> bytes:
    """Bind verification to an unchanged manifest before any output is created."""
    manifest_path = checked_path(MANIFEST_NAME)
    checked_path("verify.py")
    before = manifest_path.read_bytes()
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    env.pop("PYTHONPATH", None)
    try:
        result = subprocess.run(
            [sys.executable, "-B", str(ROOT / "verify.py")], cwd=ROOT,
            capture_output=True, encoding="utf-8", errors="replace", env=env, timeout=120,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError("verify.py did not complete within 120 seconds; no package was created") from error
    require(result.returncode == 0,
            "verify.py failed; no package was created:\n" + (result.stderr or result.stdout).strip())
    after = checked_path(MANIFEST_NAME).read_bytes()
    require(before == after, "PUBLICATION.json changed during verification; freeze the publication and retry")
    return after


def snapshot(manifest_bytes: bytes) -> tuple[dict, dict[str, bytes]]:
    manifest = json.loads(manifest_bytes)
    require(isinstance(manifest, dict), "PUBLICATION.json must contain an object")
    files = manifest.get("files")
    require(isinstance(files, dict) and bool(files), "Missing manifest file inventory")
    require(MANIFEST_NAME not in files, "PUBLICATION.json must not hash itself")
    require(set(PDF_NAMES) <= files.keys(), "Manifest omits a canonical language PDF / PDF linguistique manquant")
    require(manifest.get("pdf_sha256") == files[PDF_NAME], "Canonical PDF identity is inconsistent")
    contents = {}
    for relative in sorted(files):
        expected = files[relative]
        require(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected) is not None,
                f"Invalid SHA-256 identity: {relative}")
        data = checked_path(relative).read_bytes()
        require(digest(data) == expected, f"Source changed or hash mismatch: {relative}")
        contents[relative] = data
    require(checked_path(MANIFEST_NAME).read_bytes() == manifest_bytes,
            "PUBLICATION.json changed while source files were being read")
    contents[MANIFEST_NAME] = manifest_bytes
    return manifest, contents


def write_archive(path: Path, contents: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, mode="x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in sorted(contents):
            info = zipfile.ZipInfo(ZIP_PREFIX + relative, date_time=ZIP_TIMESTAMP)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, contents[relative], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(path) as archive:
        expected = [ZIP_PREFIX + relative for relative in sorted(contents)]
        require(archive.namelist() == expected, "Archive inventory differs from the verified snapshot")
        require(archive.testzip() is None, "Archive integrity check failed")
        require(archive.read(ZIP_PREFIX + MANIFEST_NAME) == contents[MANIFEST_NAME],
                "Archived manifest differs from the verified snapshot")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, required=True,
                        help="New absolute output directory outside the paper's source directory")
    args = parser.parse_args()
    if not args.output.is_absolute():
        parser.error("--output must be an absolute path")
    if args.output.exists() or args.output.is_symlink():
        parser.error("--output already exists; choose a new directory to preserve prior deliverables")
    output = args.output.resolve()
    if output == ROOT or output.is_relative_to(ROOT):
        parser.error("--output must be outside the paper directory so packaging does not change its verified inventory")

    manifest_bytes = verify_publication()
    manifest, contents = snapshot(manifest_bytes)
    output.mkdir(parents=True)
    zip_partial = output / (ZIP_NAME + ".partial")
    pdf_paths = []
    for name in PDF_NAMES:
        partial = output / (name + ".partial")
        partial.write_bytes(contents[name])
        require(digest(partial.read_bytes()) == manifest["files"][name],
                f"Output PDF differs from canonical identity / identité PDF différente: {name}")
        pdf_paths.append((partial, output / name))
    write_archive(zip_partial, contents)
    zip_path = output / ZIP_NAME
    for partial, final in pdf_paths:
        partial.rename(final)
    zip_partial.rename(zip_path)
    result = {
        "status": "PACKAGED_VERIFIED_PUBLICATION",
        "edition": manifest["edition"],
        "pages": manifest["pages"],
        "languages": manifest["languages"],
        "verification": "verify.py passed; manifest and file hashes checked again before packaging",
        "manifest_sha256": digest(manifest_bytes),
        "zip_entries": len(contents),
        "artifacts": [
            {"path": str(path), "bytes": path.stat().st_size, "sha256": digest(path.read_bytes())}
            for path in (*(final for _, final in pdf_paths), zip_path)
        ],
    }
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        print(json.dumps({"status": "PACKAGING_FAILED", "error": str(error)}, indent=2), file=sys.stderr)
        sys.exit(1)
