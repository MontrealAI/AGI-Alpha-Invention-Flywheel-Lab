#!/usr/bin/env python3
"""Build the paper without shell escape or network access; preserve a build log."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
STEM = 'ALPHA_GENESIS_FLYWHEEL_OMEGA_v2'

def main() -> None:
    latex = shutil.which('pdflatex')
    bib = shutil.which('bibtex') or shutil.which('bibtex.original')
    if latex is None or bib is None:
        raise SystemExit('Install a TeX distribution with pdflatex and BibTeX. See README.md.')
    commands = [[latex, '-interaction=nonstopmode', '-halt-on-error', '-no-shell-escape', STEM + '.tex'],
                [bib, STEM]]
    commands.extend([commands[0]] * 2)
    with (ROOT / 'BUILD.log').open('w', encoding='utf-8') as log:
        for command in commands:
            log.write('$ ' + ' '.join(command) + '\n'); log.flush()
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            if result.returncode:
                raise SystemExit(f'Build failed ({result.returncode}); inspect BUILD.log.')
    print(str(ROOT / (STEM + '.pdf')))

if __name__ == '__main__':
    main()
