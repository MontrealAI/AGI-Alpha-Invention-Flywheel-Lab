#!/usr/bin/env python3
"""Reproduce the new exact study and compile the manuscript without shell escape.

Requires Python 3.10+, pdflatex and the standard packages listed in README.md.
This checks the supplied model; it invokes no LLM, customer, payment or network.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
NAME = 'SURF_THE_EXPONENTIAL'


def run(command: list[str], cwd: Path, output: Path) -> None:
    with output.open('w', encoding='utf-8') as log:
        completed = subprocess.run(command, cwd=cwd, stdout=log,
            stderr=subprocess.STDOUT, check=False, env={**os.environ,
            'SOURCE_DATE_EPOCH': '1793912400', 'FORCE_SOURCE_DATE':'1'})
    if completed.returncode:
        details=output.read_text(errors="replace")
        print(details[-24000:], file=sys.stderr)
        (ROOT/"evidence/failed-build-command.txt").write_text(details)
        raise RuntimeError(f'Command failed ({completed.returncode}): {command!r}; log: {output}')


def build(tests_only: bool = False) -> dict:
    records = ROOT / 'evidence'
    records.mkdir(exist_ok=True)
    run([sys.executable, '-B', '-m', 'unittest', '-v'], ROOT/'analysis', records/'tests-normal.txt')
    run([sys.executable, '-O', '-B', '-m', 'unittest', '-v'], ROOT/'analysis', records/'tests-optimized.txt')
    with tempfile.TemporaryDirectory(prefix='surf-evidence-') as tmp:
        result = Path(tmp)/'result.json'
        run([sys.executable, '-B', 'run_study.py', '--out', str(result)], ROOT/'analysis', Path(tmp)/'run.log')
        if result.read_bytes() != (records/'exact-results.json').read_bytes():
            raise RuntimeError('Deterministic exact evidence differs from the retained result')
    status={'tests':38,'parameter_cases':192,'model_admissions':63,'model_refusals':129,
        'actual_customer_receipts':0,'separate_llm_reviewer':False,
        'result_sha256':hashlib.sha256((records/'exact-results.json').read_bytes()).hexdigest()}
    if tests_only:
        return status
    if not shutil.which('pdflatex'):
        raise RuntimeError('pdflatex is required. See README.md for standard TeX Live packages.')
    with tempfile.TemporaryDirectory(prefix='surf-latex-') as tmp:
        work=Path(tmp)
        shutil.copyfile(ROOT/f'{NAME}.tex',work/f'{NAME}.tex')
        for i in range(3):
            run(['pdflatex','-no-shell-escape','-interaction=nonstopmode','-halt-on-error',f'{NAME}.tex'],work,work/f'pass-{i+1}.txt')
        log=(work/f'{NAME}.log').read_text(errors='replace')
        forbidden = ('Overfull \\hbox','Overfull \\vbox','There were undefined references',
            'Citation ', 'Reference ')
        issues=[line for line in log.splitlines() if 'undefined' in line.lower() or line.startswith('Overfull ')]
        if issues:
            raise RuntimeError('LaTeX qualification failed: '+ '\n'.join(issues))
        pdf=(work/f'{NAME}.pdf').read_bytes()
        if not pdf.startswith(b'%PDF-'):
            raise RuntimeError('Invalid PDF output')
        (ROOT/f'{NAME}.pdf').write_bytes(pdf)
        status.update(pdf_sha256=hashlib.sha256(pdf).hexdigest(),pdf_bytes=len(pdf),
            tex_sha256=hashlib.sha256((ROOT/f'{NAME}.tex').read_bytes()).hexdigest(),
            latex_overfull_boxes=0,undefined_citations_and_references=0)
        (records/'build-check.json').write_text(json.dumps(status,indent=2,sort_keys=True)+'\n')
        (records/'latex-qualification.txt').write_text('Three pdflatex passes; shell escape disabled.\nNo overfull boxes or undefined references/citations.\n'+subprocess.check_output(['pdflatex','--version'],text=True).splitlines()[0]+'\n')
    return status


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tests-only',action='store_true')
    args=parser.parse_args()
    print(json.dumps(build(args.tests_only),sort_keys=True))
