#!/usr/bin/env python3
"""Verify source/PDF identity and optionally compare a fresh manuscript build."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess

from package import PDF, ROOT, verify_manifest


def extracted_text(path: Path) -> str:
    process = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=True)
    return re.sub(r"\s+", " ", process.stdout).strip()


def verify(rebuilt: Path | None = None) -> dict:
    publication = verify_manifest()
    canonical_text = extracted_text(ROOT / PDF)
    for marker in ("LEARNING TO BUILD", "Vincent Boucher", "2026", "References"):
        if marker not in canonical_text:
            raise ValueError(f"Required manuscript content is missing: {marker}")
    if "[?]" in canonical_text or "??" in canonical_text:
        raise ValueError("Unresolved reference marker in canonical PDF text")
    if rebuilt is not None and extracted_text(rebuilt.resolve()) != canonical_text:
        raise ValueError("Rebuilt PDF text differs from the reviewed canonical manuscript")
    research = ROOT.parent / "research"
    website_pdf = research / "learning-to-build-v1.1.0.pdf"
    if website_pdf.is_file():
        if website_pdf.read_bytes() != (ROOT / PDF).read_bytes():
            raise ValueError("Website PDF is not byte-identical to the canonical PDF")
        website_figure = research / "learning-to-build-v1.1.0-example.png"
        if not website_figure.is_file() or website_figure.read_bytes() != (ROOT / "construction/figures/protocol-first-fields.png").read_bytes():
            raise ValueError("Website example figure differs from the bound scientific figure")
        reader = (research / "learning-to-build-v1.1.0.html").read_text(encoding="utf-8")
        for marker in (
            '<span data-pdf-pages>' + str(publication["pdf"]["pages"]) + ' pages</span>',
            '<span data-pdf-bytes>' + str(publication["pdf"]["bytes"]) + ' bytes</span>',
            '<code data-pdf-sha>' + publication["pdf"]["sha256"] + '</code>',
        ):
            if marker not in reader:
                raise ValueError("Browser reader does not carry the canonical PDF identity")
    return {
        "status": "VERIFIED", "edition": publication["edition"],
        "pdf_sha256": publication["pdf"]["sha256"],
        "source_files": len(publication["source_files"]),
        "canonical_text_checked": True,
        "rebuilt_text_equivalent": True if rebuilt is not None else None,
        "website_copy_checked": website_pdf.is_file(),
        "scope": "Source identity and publication consistency; not independent scientific or commercial certification.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-build", type=Path, help="Compare text from this fresh PDF with the canonical manuscript")
    arguments = parser.parse_args()
    print(json.dumps(verify(arguments.check_build), indent=2))
