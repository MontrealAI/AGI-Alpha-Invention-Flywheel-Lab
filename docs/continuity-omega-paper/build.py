#!/usr/bin/env python3
"""Build the manuscript without shell escape; reject substantive TeX warnings."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true", help="Update the two canonical PDF copies after a clean build")
    args = parser.parse_args()
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    for iteration in range(3):
        result = subprocess.run([
            "pdflatex", "-interaction=nonstopmode", "-halt-on-error",
            "-no-shell-escape", "-output-directory=build", "CONTINUITY_OMEGA.tex",
        ], cwd=ROOT, capture_output=True, text=True)
        (build / f"pass-{iteration + 1}.txt").write_text(result.stdout + result.stderr)
        if result.returncode:
            raise SystemExit(result.stdout[-6000:] + result.stderr[-2000:])
    log = (build / "CONTINUITY_OMEGA.log").read_text()
    bad = re.findall(r"^.*(?:Overfull|undefined references|undefined citations|Citation .+ undefined|Reference .+ undefined|LaTeX Error|Missing character).*$", log, re.M)
    if bad:
        raise SystemExit("Unresolved manuscript defects:\n" + "\n".join(bad))
    if args.publish:
        shutil.copyfile(build / "CONTINUITY_OMEGA.pdf", ROOT / "CONTINUITY_OMEGA.pdf")
        research = ROOT.parent / "research"
        if research.is_dir():
            shutil.copyfile(build / "CONTINUITY_OMEGA.pdf", research / "continuity-omega.pdf")
    print("Clean manuscript build:", build / "CONTINUITY_OMEGA.pdf")


if __name__ == "__main__":
    main()
