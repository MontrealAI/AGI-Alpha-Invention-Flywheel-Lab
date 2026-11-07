#!/usr/bin/env python3
"""Build the manuscript without shell escape in a clean temporary directory."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
EPOCH = "1793836800"  # Fixed source epoch: 5 November 2026, 00:00:00 UTC.

def build(output: Path) -> dict:
    bibtex = shutil.which("bibtex") or shutil.which("bibtex.original")
    if not shutil.which("pdflatex") or not bibtex:
        raise SystemExit("Missing pdfLaTeX or BibTeX; see README.md for TeX dependencies.")
    inputs = sorted(set(ROOT.glob("*.tex")) | set(ROOT.glob("*.bib")) |
                    set((ROOT / "figures").rglob("*.tex")) |
                    {ROOT / "evidence/results_table.tex"})
    env = dict(os.environ, SOURCE_DATE_EPOCH=EPOCH, FORCE_SOURCE_DATE="1",
               TZ="UTC", LC_ALL="C.UTF-8")
    with tempfile.TemporaryDirectory(prefix="surf-paper-") as name:
        work = Path(name)
        for source in inputs:
            target = work / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        command = ["pdflatex", "-no-shell-escape", "-interaction=nonstopmode",
                   "-halt-on-error", "-file-line-error", "paper.tex"]
        for cmd in (command, [bibtex, "paper"], command, command):
            proc = subprocess.run(cmd, cwd=work, env=env, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if proc.returncode:
                print(proc.stdout[-14000:])
                raise SystemExit(proc.returncode)
        log = (work / "paper.log").read_text(errors="replace")
        bad = [line for line in log.splitlines()
               if "undefined" in line.lower() or "Missing character:" in line]
        if bad:
            raise SystemExit("\n".join(bad))
        output = output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(work / "paper.pdf", output)
        (output.parent / (output.stem + ".build.log")).write_text(log)
        data = output.read_bytes()
        report = {"output": str(output), "bytes": len(data),
                  "sha256": hashlib.sha256(data).hexdigest(),
                  "source_epoch": EPOCH,
                  "overfull_boxes": [line for line in log.splitlines() if "Overfull " in line],
                  "input_files": [str(p.relative_to(ROOT)) for p in inputs]}
        print(json.dumps(report, indent=2))
        return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "SURF_THE_EXPONENTIAL.pdf")
    args = parser.parse_args()
    build(args.output)
