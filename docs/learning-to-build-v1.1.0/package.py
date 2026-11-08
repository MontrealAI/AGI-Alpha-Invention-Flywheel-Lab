#!/usr/bin/env python3
"""Bind, verify or package a reviewed Learning to Build research edition."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent
PDF = "LEARNING_TO_BUILD.pdf"
MANIFEST = "PUBLICATION.json"
SOURCE_ZIP = "LEARNING_TO_BUILD_SOURCE.zip"
EDITION = "1.1.0"
TAG = "learning-to-build-v1.1.0"
TITLE = "Learning to Build: How Intelligence Learns to Create What Makes New Possibilities Real"
SITE = "https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/"
EXCLUDED_DIRECTORIES = {"__pycache__", ".git", ".build", "build", "dist", "tmp", "output"}
SOURCE_EXTENSIONS = {".py", ".md", ".tex", ".bib", ".json", ".csv", ".cff", ".pdf", ".png", ".svg", ".txt", ".gz", ".html"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate publication-manifest key: {key}")
        result[key] = value
    return result


def source_paths() -> list[Path]:
    result = []
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_DIRECTORIES or part.startswith(".") for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError(f"Publication source cannot be a symlink: {relative}")
        if not path.is_file() or path.name in {PDF, MANIFEST} or path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        result.append(path)
    return sorted(result)


def pdf_metadata(path: Path) -> dict:
    data = path.read_bytes()
    if not data.startswith(b"%PDF-"):
        raise ValueError("Canonical manuscript is not a PDF")
    process = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True, check=True)
    match = re.search(r"^Pages:\s+(\d+)\s*$", process.stdout, re.MULTILINE)
    if match is None:
        raise ValueError("Could not read the canonical PDF page count")
    return {"file": PDF, "pages": int(match.group(1)), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def make_manifest() -> dict:
    required = (
        "LEARNING_TO_BUILD.tex", "references.bib", "README.md", "CITATION.cff",
        "RELEASE_NOTES.md", "SOURCE_MAP.md", "REVIEW.md", "build.py", "package.py",
        "verify.py", "study/PROTOCOL.json", "study/study.py", "study/check.py",
        "study/test_integrity.py", "study/evidence/RESULTS.json",
        "construction/README.md", "construction/check.py", "construction/test_integrity.py",
        "construction/RESULTS.json", "construction/RESULTS.md", "construction/CLAIMS.json",
        "construction/evidence/EVIDENCE_MANIFEST.json", "construction/evidence/REPRODUCTION.tar.gz",
        "construction/figures.py", "construction/requirements-figures.txt",
        "construction/figures/protocol-first-fields.png", "construction/figures/protocol-first-fields.json",
        "construction/summarize.py",
        "EVIDENCE_INDEX.md", "COST_LEDGER.md", "COST_LEDGER.json",
        "construction/setup_incumbent.py", "construction/test_setup.py",
        "construction/projection.py", "construction/test_projection.py",
        "construction/diagnostics/PREREGISTRATION.json", "construction/diagnostics/FREEZE.json",
        "construction/diagnostics/run.py", "construction/diagnostics/RESULTS.json",
        "construction/diagnostics/OBSERVED_RUN.tar.gz", "construction/diagnostics/EVIDENCE.json",
        "construction/repair/PREREGISTRATION.json", "construction/repair/FREEZE.json",
        "construction/repair/composition.py", "construction/repair/evaluate.py",
        "construction/repair/RESULTS.json", "construction/repair/OBSERVED_RUN.tar.gz",
        "construction/repair/EVIDENCE.json", "qualification/setup-boundary-evidence.tar.gz",
        "qualification/publication-review.tar.gz", "qualification/PDF_VISUAL_REVIEW.json",
        "qualification/evidence-review.tar.gz",
        "qualification/ROOT_PROJECTION_REVIEW.json", "qualification/COST_LEDGER_REVIEW.json",
    )
    missing = [name for name in required if not (ROOT / name).is_file()]
    if missing:
        raise ValueError("Incomplete publication inputs: " + ", ".join(missing))
    return {
        "schema": "learning-to-build/publication/v1",
        "title": TITLE, "author": "Vincent Boucher",
        "affiliations": ["MONTREAL.AI", "QUEBEC.AI"],
        "edition": EDITION, "date": "2026-11-07", "language": "en",
        "release_tag": TAG, "reader": SITE + "learning-to-build-v1.1.0.html",
        "pdf": pdf_metadata(ROOT / PDF),
        "source_files": [
            {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}
            for path in source_paths()
        ],
        "scope": (
            "Versioned research synthesis and a reproduced, preregistered public-microscopy "
            "construction comparison with a fixed pretrained alternative. Preserves the original "
            "authored finite study. Qualification, constructor learning, successor acceptance and "
            "economics are separate verdicts. No real customer acceptance, receipts or physical "
            "deployment is established. Historical exposed comparisons are reproductions, not fresh confirmations."
        ),
        "reproducibility": (
            "The manifest binds the reviewed canonical PDF and all packaged sources. "
            "Rebuilds use fixed source dates and no shell escape. Byte equality is checked within "
            "one toolchain; different TeX distributions may produce different PDF bytes."
        ),
    }


def verify_manifest() -> dict:
    recorded = json.loads((ROOT / MANIFEST).read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    actual = make_manifest()
    # Exact JSON types matter: a Boolean is not an integer count.
    if json.dumps(recorded, sort_keys=True, allow_nan=False) != json.dumps(actual, sort_keys=True, allow_nan=False):
        if recorded.get("pdf") != actual["pdf"]:
            raise ValueError("Canonical PDF does not match PUBLICATION.json")
        old = {item["path"]: item for item in recorded.get("source_files", [])}
        new = {item["path"]: item for item in actual["source_files"]}
        changed = sorted(name for name in old.keys() | new.keys() if old.get(name) != new.get(name))
        raise ValueError("Publication binding differs: " + (", ".join(changed) or "edition metadata"))
    return recorded


def refresh() -> dict:
    """Explicit authoring operation; never called by qualification or release jobs."""
    publication = make_manifest()
    (ROOT / MANIFEST).write_text(json.dumps(publication, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    research = ROOT.parent / "research"
    reader = research / "learning-to-build-v1.1.0.html"
    website_manifest = research / "publication-manifest.json"
    if reader.is_file() and website_manifest.is_file():
        shutil.copyfile(ROOT / PDF, research / "learning-to-build-v1.1.0.pdf")
        shutil.copyfile(ROOT / "construction/figures/protocol-first-fields.png",
                        research / "learning-to-build-v1.1.0-example.png")
        page = reader.read_text(encoding="utf-8")
        values = {
            "data-pdf-pages": str(publication["pdf"]["pages"]) + " pages",
            "data-pdf-bytes": str(publication["pdf"]["bytes"]) + " bytes",
            "data-pdf-sha": publication["pdf"]["sha256"],
        }
        for attribute, value in values.items():
            pattern = rf'(<(?:span|code) {attribute}>)[^<]*(</(?:span|code)>)'
            page, count = re.subn(pattern, lambda match: match[1] + value + match[2], page)
            if count != 1:
                raise ValueError(f"Expected exactly one reader metadata field: {attribute}")
        reader.write_text(page, encoding="utf-8")
        site_manifest = json.loads(website_manifest.read_text(encoding="utf-8"))
        entry = {
            "file": "learning-to-build-v1.1.0.pdf", "title": TITLE,
            "author": "Vincent Boucher", "date": "2026-11-07",
            "pages": publication["pdf"]["pages"], "bytes": publication["pdf"]["bytes"],
            "sha256": publication["pdf"]["sha256"],
            "source": "https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/main/docs/learning-to-build-v1.1.0",
            "scope": publication["scope"],
        }
        previous = [item for item in site_manifest["papers"] if item["file"] != entry["file"]]
        site_manifest["papers"] = previous + [entry]
        website_manifest.write_text(json.dumps(site_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return verify_manifest()


def package(output: Path) -> dict:
    publication = verify_manifest()
    output = output.expanduser().resolve()
    if output.exists() or output.is_symlink():
        raise ValueError("Package output must be a new directory; existing files are never replaced")
    if output.is_relative_to(ROOT):
        raise ValueError("Package output must be outside the canonical publication source directory")
    output.mkdir(parents=True)
    for name in (PDF, MANIFEST):
        shutil.copyfile(ROOT / name, output / name)
    files = sorted([PDF, MANIFEST] + [item["path"] for item in publication["source_files"]])
    with zipfile.ZipFile(output / SOURCE_ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in files:
            relative = PurePosixPath(name)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"Unsafe archive path: {name}")
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 7, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (ROOT / name).read_bytes(), compresslevel=9)
    assets = (PDF, SOURCE_ZIP, MANIFEST)
    sums = "".join(f"{digest(output / name)}  {name}\n" for name in assets)
    (output / "SHA256SUMS").write_text(sums, encoding="ascii")
    return {
        "status": "PACKAGED", "edition": EDITION, "directory": str(output),
        "source_archive_files": len(files),
        "assets": {name: digest(output / name) for name in (*assets, "SHA256SUMS")},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--verify", action="store_true", help="Verify the immutable source and canonical-PDF bindings")
    action.add_argument("--refresh", action="store_true", help="After editorial review, bind current source/PDF and update website PDF identities")
    action.add_argument("--output", type=Path, help="Build the reviewed source ZIP and PDF assets in a new directory")
    arguments = parser.parse_args()
    if arguments.refresh:
        result = refresh()
        print(json.dumps({"status": "BOUND", "pdf": result["pdf"], "source_files": len(result["source_files"])}, indent=2))
    elif arguments.verify:
        result = verify_manifest()
        print(json.dumps({"status": "VERIFIED", "edition": result["edition"], "pdf": result["pdf"], "source_files": len(result["source_files"])}, indent=2))
    else:
        print(json.dumps(package(arguments.output), indent=2))
