#!/usr/bin/env python3
"""Build the manuscript locally, preserving the supplied inspected PDF."""
from __future__ import annotations
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = 'ALPHA_GENESIS_FLYWHEEL_OMEGA'

def main() -> int:
    engine = shutil.which('pdflatex')
    if not engine:
        print('pdflatex is not installed. Install a TeX Live distribution with the packages listed in README.md.', file=sys.stderr)
        return 2
    output = ROOT / 'build'
    output.mkdir(exist_ok=True)
    for attempt in range(1, 4):
        process = subprocess.run(
            [engine, '-no-shell-escape', '-interaction=nonstopmode', '-halt-on-error', '-output-directory=build', f'{NAME}.tex'],
            cwd=ROOT, capture_output=True, text=True, errors='replace', check=False,
        )
        (output / f'pass-{attempt}.txt').write_text(process.stdout + process.stderr, encoding='utf-8')
        if process.returncode:
            print(process.stdout[-6000:], file=sys.stderr)
            print(f'Build failed; full output: {output / f"pass-{attempt}.txt"}', file=sys.stderr)
            return process.returncode
    log = (output / f'{NAME}.log').read_text(encoding='utf-8', errors='replace')
    failures = re.findall(r'^.*(?:Overfull|Missing character|Warning:|undefined references|undefined citations).*$' , log, flags=re.MULTILINE)
    if failures:
        print('The PDF was generated, but publication checks require review:', file=sys.stderr)
        print('\n'.join(failures), file=sys.stderr)
        return 1
    print(f'Built: {output / f"{NAME}.pdf"}')
    print('Three compilation passes completed without detected publication warnings.')
    print('The root-level inspected PDF has not been replaced. Visually inspect any revised edition.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
