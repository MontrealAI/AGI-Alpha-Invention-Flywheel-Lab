#!/usr/bin/env python3
"""Compile the editable manuscript in a clean directory, without shell escape."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
MAIN = "LEARNING_TO_BUILD.tex"
EPOCH = "1794009600"  # 7 November 2026, 00:00:00 UTC.


def input_files() -> list[Path]:
    files = set(ROOT.glob("*.tex")) | set(ROOT.glob("*.bib"))
    for directory in ("sections", "figures", "evidence", "construction/figures"):
        for path in (ROOT / directory).rglob("*"):
            if path.is_file() and path.suffix.lower() in {
                ".tex", ".bib", ".pdf", ".png", ".jpg", ".jpeg"
            }:
                files.add(path)
    for path in files:
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise ValueError(f"Unsafe manuscript input: {path}")
    if ROOT / MAIN not in files:
        raise ValueError(f"Missing manuscript: {MAIN}")
    return sorted(files)


def build(output: Path) -> dict:
    for binary in ("pdflatex", "bibtex"):
        if shutil.which(binary) is None:
            raise SystemExit(f"Missing {binary}; see README.md for the standard TeX dependencies.")
    inputs = input_files()
    output = output.expanduser().resolve()
    environment = dict(
        os.environ, SOURCE_DATE_EPOCH=EPOCH, FORCE_SOURCE_DATE="1",
        TZ="UTC", LC_ALL="C.UTF-8", openout_any="p", shell_escape="f",
    )
    with tempfile.TemporaryDirectory(prefix="learning-to-build-") as temporary:
        work = Path(temporary)
        for source in inputs:
            destination = work / source.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        command = [
            "pdflatex", "-no-shell-escape", "-interaction=nonstopmode",
            "-halt-on-error", "-file-line-error", MAIN,
        ]
        stem = Path(MAIN).stem
        for step in (command, ["bibtex", stem], command, command, command):
            process = subprocess.run(
                step, cwd=work, env=environment, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
            if process.returncode:
                print(process.stdout[-18000:])
                raise SystemExit(process.returncode)
        log = (work / f"{stem}.log").read_text(errors="replace")
        problems = [line for line in log.splitlines() if (
            "Missing character:" in line or "Overfull " in line or
            "undefined" in line.lower() or
            re.search(r"(?:LaTeX|Package \S+|Class \S+) Warning:", line)
        )]
        output.parent.mkdir(parents=True, exist_ok=True)
        log_path = output.with_suffix(".build.log")
        log_path.write_text(log, encoding="utf-8")
        if problems:
            print("Final-pass manuscript warnings must be resolved:\n" + "\n".join(problems))
            print(f"Full build log: {log_path}")
            raise SystemExit(1)
        shutil.copyfile(work / f"{stem}.pdf", output)
    data = output.read_bytes()
    result = {
        "status": "BUILT", "output": str(output), "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(), "source_epoch": EPOCH,
        "shell_escape": False, "final_pass_warnings": [],
        "input_files": [str(path.relative_to(ROOT)) for path in inputs],
    }
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "LEARNING_TO_BUILD.pdf")
    arguments = parser.parse_args()
    build(arguments.output)
