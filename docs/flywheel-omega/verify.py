#!/usr/bin/env python3
"""Verify the compiled manuscript, exact companion, and inspected edition.

``--build-only`` works before PUBLICATION.json is finalized. Full verification
also binds every archived source file and the inspected public PDF. It does not
certify an operating enterprise or replace visual inspection of the paper.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import unicodedata

from companion import evaluate

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
PUBLIC_NAME = "flywheel-omega.pdf"
RELEASE_PDF_NAME = "FLYWHEEL_OMEGA.pdf"
VERSION_PATTERN = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
SHA_PATTERN = re.compile(r"[0-9a-f]{64}")
REQUIRED_SOURCES = {
    "paper.tex", "references.bib", "VERSION", "Makefile", "companion.py",
    "test_companion.py", "PROTOCOL.md", "results.json", "verify.py", "package.py",
    "README.md", "CITATION.cff", "RELEASE_NOTES.md", "sources.json",
    "replay_public_case.py", "public_replay.json",
}
ALLOWED_SUFFIXES = {".tex", ".bib", ".py", ".md", ".json", ".pdf", ".csv", ".cff", ".svg", ".png"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_text(text: str) -> str:
    # NFKC normalizes extracted ligatures without changing minus signs or numbers.
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def public_pdf() -> Path:
    repository_pdf = ROOT.parent / "research" / PUBLIC_NAME
    return repository_pdf if repository_pdf.is_file() else ROOT / RELEASE_PDF_NAME


def source_path(name: str) -> Path:
    require(isinstance(name, str) and bool(name), "Source filename must be a nonempty string")
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and relative.as_posix() == name
            and all(part not in ("", ".", "..") and not part.startswith(".")
                    for part in relative.parts), "Unsafe source path: " + name)
    require(relative.parts[0] not in {"build", "__pycache__", "output", "tmp"},
            "Build or temporary content is not a publication source: " + name)
    require(name not in {"PUBLICATION.json", RELEASE_PDF_NAME, PUBLIC_NAME},
            "Manifest/public PDF must not recursively appear in source_files: " + name)
    require(name in {"Makefile", "VERSION"} or relative.suffix in ALLOWED_SUFFIXES,
            "Unapproved source file type: " + name)
    path = ROOT.joinpath(*relative.parts)
    require(path.is_file(), "Missing publication source: " + name)
    current = path
    while current != ROOT:
        require(not current.is_symlink(), "Symlinks are not publication sources: " + name)
        current = current.parent
    require(path.resolve().is_relative_to(ROOT), "Source escapes publication directory: " + name)
    return path


def load_manifest() -> dict:
    manifest_path = ROOT / "PUBLICATION.json"
    require(manifest_path.is_file() and not manifest_path.is_symlink(),
            "Finalize PUBLICATION.json before full publication verification")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest.get("schema_version") == 1, "Unsupported publication manifest schema")
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    require(bool(VERSION_PATTERN.fullmatch(version)) and manifest.get("version") == version,
            "Manifest version does not match VERSION")
    require(isinstance(manifest.get("title"), str) and bool(manifest["title"].strip()),
            "Publication title required")
    require(isinstance(manifest.get("date"), str), "ISO publication date required")
    date.fromisoformat(manifest["date"])
    require(manifest.get("private_source_documents_published") is False,
            "Private source documents must not be published")
    require(isinstance(manifest.get("evidence_scope"), str) and bool(manifest["evidence_scope"].strip()),
            "Explicit evidence scope required")
    require(bool(re.fullmatch(r"[0-9a-f]{40}", manifest.get("source_repository_snapshot", ""))),
            "Exact public source_repository_snapshot commit required")
    files = manifest.get("source_files")
    require(isinstance(files, dict) and REQUIRED_SOURCES <= set(files),
            "Manifest omits required self-contained publication sources")
    for name, digest in files.items():
        require(isinstance(digest, str) and bool(SHA_PATTERN.fullmatch(digest)),
                "Invalid source hash: " + name)
        require(sha(source_path(name)) == digest, "Source identity mismatch: " + name)
    pdf = manifest.get("pdf", {})
    require(pdf.get("file") == PUBLIC_NAME, "Unexpected public PDF filename in manifest")
    require(type(pdf.get("bytes")) is int and pdf["bytes"] > 0, "Positive PDF byte count required")
    require(type(pdf.get("pages")) is int and 20 <= pdf["pages"] <= 40,
            "Manifest page count must be in the declared 20–40 page range")
    require(isinstance(pdf.get("sha256"), str) and bool(SHA_PATTERN.fullmatch(pdf["sha256"])),
            "Exact inspected PDF hash required")
    return manifest


def pdf_text(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), "Missing regular PDF: " + str(path))
    require(path.read_bytes().startswith(b"%PDF-"), "File does not have a PDF header: " + str(path))
    return subprocess.check_output(["pdftotext", str(path), "-"], text=True, encoding="utf-8")


def pdf_pages(path: Path) -> int:
    info = subprocess.check_output(["pdfinfo", str(path)], text=True, encoding="utf-8")
    match = re.search(r"^Pages:\s+(\d+)\s*$", info, flags=re.MULTILINE)
    require(match is not None, "Cannot read PDF page count")
    return int(match.group(1))


def local_tex_inputs() -> set[str]:
    """Require the recorder's local source inputs to be included in the archive."""
    recorder = BUILD / "paper.fls"
    require(recorder.is_file(), "Compile with latexmk so build/paper.fls records dependencies")
    result = set()
    for line in recorder.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("INPUT "):
            continue
        item = Path(line[6:])
        path = item if item.is_absolute() else ROOT / item
        resolved = path.resolve()
        if resolved.is_relative_to(BUILD):
            continue  # TeX's generated aux/bbl/out files are rebuilt, not distributed.
        if resolved.is_relative_to(ROOT):
            result.add(resolved.relative_to(ROOT).as_posix())
        elif not item.is_absolute():
            raise ValueError("Relative TeX input escapes the self-contained source: " + str(item))
    return result


def check(build_only: bool = False) -> dict:
    expected = json.loads((ROOT / "results.json").read_text(encoding="utf-8"))
    require(evaluate() == expected, "Exact analytical results differ from results.json")
    built = BUILD / "paper.pdf"
    require(built.is_file(), "Compile paper.tex first with make or latexmk")
    text = pdf_text(built)
    normalized = normalize_text(text)
    folded = normalized.casefold()
    for marker in ("flywheel", "the economy as an output", "vincent boucher", "references"):
        require(marker in folded, "Missing manuscript content: " + marker)
    require("??" not in text and "[?]" not in text, "Unresolved PDF citation or cross-reference")
    log_path = BUILD / "paper.log"
    require(log_path.is_file(), "Missing build/paper.log")
    log = log_path.read_text(encoding="utf-8", errors="replace")
    for pattern, label in (
        (r"Overfull \\[hv]box", "overfull box"),
        (r"(?i)(?:reference|citation)[^\n]*undefined", "undefined reference/citation"),
        (r"(?i)there were undefined", "undefined references"),
        (r"(?i)Missing character:", "missing glyph"),
        (r"(?i)multiply defined", "multiply defined label"),
        (r"(?i)destination with the same identifier", "duplicate PDF destination"),
    ):
        require(re.search(pattern, log) is None, "LaTeX issue: " + label)
    pages = pdf_pages(built)
    require(20 <= pages <= 40, "Compiled page count is outside the declared 20–40 range")
    dependencies = local_tex_inputs()
    report = {
        "status": "PASS", "pages": pages, "analytical_snapshot": "MATCH",
        "build_only": build_only, "local_tex_inputs": len(dependencies),
        "normalized_pdf_text_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "scope": "Exact analytical companion and source-bound research publication; no operating enterprise qualification.",
    }
    if not build_only:
        manifest = load_manifest()
        require(dependencies <= set(manifest["source_files"]),
                "Manifest omits TeX inputs: " + ", ".join(sorted(dependencies - set(manifest["source_files"]))))
        published = public_pdf()
        inspected_text = normalize_text(pdf_text(published))
        require(sha(published) == manifest["pdf"]["sha256"]
                and published.stat().st_size == manifest["pdf"]["bytes"],
                "Inspected public PDF byte identity mismatch")
        require(pages == manifest["pdf"]["pages"] == pdf_pages(published),
                "Compiled, inspected, and manifest page counts differ")
        require(normalized == inspected_text, "Rebuilt text differs from the inspected public PDF")
        report.update(version=manifest["version"], source_files=len(manifest["source_files"]),
                      public_pdf_sha256=manifest["pdf"]["sha256"], published_pdf=str(published),
                      manifest_sha256=sha(ROOT / "PUBLICATION.json"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-only", action="store_true",
                        help="check compilation and exact results before the publication manifest exists")
    args = parser.parse_args()
    print(json.dumps(check(args.build_only), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
