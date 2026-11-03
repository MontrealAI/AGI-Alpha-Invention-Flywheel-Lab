#!/usr/bin/env python3
"""Assemble the inspected PDF and a deterministic, self-contained source ZIP.

Existing output directories are refused. Only source_files explicitly bound in
PUBLICATION.json, that manifest, and the inspected PDF enter the source archive.
Build directories, private source documents, and historical accounts are excluded.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

from verify import ROOT, RELEASE_PDF_NAME, check, require, source_path

ARCHIVE_NAME = "FLYWHEEL_OMEGA_SOURCE.zip"


def archive_name(name: str) -> str:
    relative = PurePosixPath(name)
    require(bool(name) and not relative.is_absolute() and relative.as_posix() == name
            and all(part not in ("", ".", "..") and not part.startswith(".") for part in relative.parts),
            "Unsafe archive entry: " + name)
    return name


def deterministic_zip(destination: Path, entries: dict[str, bytes], edition_date: str) -> None:
    """Stored entries avoid compression-library variability; metadata is fixed."""
    stamp = date.fromisoformat(edition_date)
    require(1980 <= stamp.year <= 2107, "ZIP edition date is out of range")
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted(entries.items()):
            archive_name(name)
            info = zipfile.ZipInfo(name, date_time=(stamp.year, stamp.month, stamp.day, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    with zipfile.ZipFile(destination) as archive:
        require(archive.testzip() is None, "Source ZIP failed its integrity check")
        require(set(archive.namelist()) == set(entries), "Unexpected source ZIP entry")


def package(output: Path) -> dict:
    require(not output.exists() and not output.is_symlink(), "Choose a new output directory; existing output is never replaced")
    verified = check()
    manifest_bytes = (ROOT / "PUBLICATION.json").read_bytes()
    require(hashlib.sha256(manifest_bytes).hexdigest() == verified["manifest_sha256"],
            "Publication manifest changed after verification")
    manifest = json.loads(manifest_bytes)
    entries = {"PUBLICATION.json": manifest_bytes}
    for name, expected_hash in manifest["source_files"].items():
        data = source_path(name).read_bytes()
        require(hashlib.sha256(data).hexdigest() == expected_hash, "Source changed during packaging: " + name)
        entries[name] = data
    inspected_pdf = Path(verified["published_pdf"]).read_bytes()
    require(hashlib.sha256(inspected_pdf).hexdigest() == manifest["pdf"]["sha256"]
            and len(inspected_pdf) == manifest["pdf"]["bytes"], "PDF changed during packaging")
    entries[RELEASE_PDF_NAME] = inspected_pdf
    output.mkdir(parents=True, exist_ok=False)
    pdf_path = output / RELEASE_PDF_NAME
    with pdf_path.open("xb") as stream:
        stream.write(inspected_pdf)
    archive_path = output / ARCHIVE_NAME
    deterministic_zip(archive_path, entries, manifest["date"])
    assets = (pdf_path, archive_path)
    checksums = "".join(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name + "\n" for path in assets)
    with (output / "SHA256SUMS").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(checksums)
    return {
        "status": "PASS", "version": manifest["version"], "output": str(output),
        "assets": [RELEASE_PDF_NAME, ARCHIVE_NAME, "SHA256SUMS"],
        "source_files": len(manifest["source_files"]), "archive_entries": len(entries),
        "manifest_sha256": verified["manifest_sha256"],
        "scope": "Inspected research edition and reproducible source; no native operating accounts.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new publication output directory")
    args = parser.parse_args()
    print(json.dumps(package(args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
