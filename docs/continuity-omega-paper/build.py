#!/usr/bin/env python3
"""Build the complete English/French manuscripts without shell escape.

Construire les articles intégraux en anglais et en français sans shell escape.
"""
import argparse
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
LANGUAGES = {
    "en": ("CONTINUITY_OMEGA", "continuity-omega.pdf"),
    "fr": ("CONTINUITY_OMEGA_FR", "continuity-omega-fr.pdf"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", choices=("en", "fr", "all"), default="all",
                        help="Manuscript language / langue de l'article (default / défaut: all)")
    parser.add_argument("--publish", action="store_true", help="Update canonical PDF copies / mettre à jour les PDF canoniques")
    args = parser.parse_args()
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    selected = LANGUAGES if args.language == "all" else {args.language: LANGUAGES[args.language]}
    for language, (stem, public_name) in selected.items():
        for iteration in range(3):
            result = subprocess.run([
                "pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                "-no-shell-escape", "-output-directory=build", stem + ".tex",
            ], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
            (build / f"{language}-pass-{iteration + 1}.txt").write_text(result.stdout + result.stderr)
            if result.returncode:
                raise SystemExit(result.stdout[-6000:] + result.stderr[-2000:])
        log = (build / (stem + ".log")).read_text(encoding="utf-8", errors="replace")
        bad = re.findall(r"^.*(?:Overfull|undefined references|undefined citations|Citation .+ undefined|Reference .+ undefined|LaTeX Error|Missing character).*$", log, re.M)
        if bad:
            raise SystemExit(f"{language}: unresolved defects / défauts non résolus:\n" + "\n".join(bad))
        print("Clean build / compilation sans défaut:", build / (stem + ".pdf"))
    # Publish only after every selected language has passed the same checks.
    if args.publish:
        for stem, public_name in selected.values():
            shutil.copyfile(build / (stem + ".pdf"), ROOT / (stem + ".pdf"))
            research = ROOT.parent / "research"
            if research.is_dir():
                shutil.copyfile(build / (stem + ".pdf"), research / public_name)


if __name__ == "__main__":
    main()
