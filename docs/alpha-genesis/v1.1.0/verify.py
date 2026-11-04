#!/usr/bin/env python3
"""Verify the research release locally; optional complete PDF rebuild. No network."""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from release_tools import verify_manifest,check_html_links

ROOT=Path(__file__).resolve().parent
NAME='ALPHA_GENESIS_FLYWHEEL_OMEGA'


def load_companion():
    spec=importlib.util.spec_from_file_location('genesis_companion',ROOT/'study'/'companion.py')
    if spec is None or spec.loader is None:raise ValueError('Companion module is missing.')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def run_checks(full:bool=False) -> dict:
    hashes=verify_manifest(ROOT)
    print(f'Package identities and inventory: {hashes} files match.',flush=True)
    links=check_html_links(ROOT)
    print(f'Local document links: {links} checked.',flush=True)
    module=load_companion()
    with tempfile.TemporaryDirectory(prefix='genesis-reproduce-') as temp:
        output=Path(temp)/'new';module.emit_results(output)
        reference=ROOT/'study'/'results'
        if {p.name for p in output.iterdir()}!={p.name for p in reference.iterdir() if p.is_file()}:
            raise ValueError('Generated artifact inventory differs from retained inventory.')
        for path in output.iterdir():
            if path.read_bytes()!=(reference/path.name).read_bytes():
                raise ValueError(f'Reproduced artifact differs: {path.name}')
    print('All four emitted study artifacts: byte-for-byte reproduction.',flush=True)
    for optimized in (False,True):
        command=[sys.executable]+(['-O'] if optimized else [])+['-m','unittest','discover','-s','study','-p','test_*.py','-v']
        subprocess.run(command,cwd=ROOT,check=True)
    pdf_rebuild='NOT_REQUESTED'
    if full:
        if not shutil.which('pdftotext'):raise ValueError('Full check needs Poppler pdftotext.')
        subprocess.run([sys.executable,'build_paper.py'],cwd=ROOT,check=True)
        texts=[]
        for pdf in (ROOT/f'{NAME}.pdf',ROOT/'build'/f'{NAME}.pdf'):
            texts.append(subprocess.run(['pdftotext','-layout',str(pdf),'-'],capture_output=True,check=True).stdout)
        if b' '.join(texts[0].split())!=b' '.join(texts[1].split()):
            raise ValueError('Rebuilt text differs from the inspected PDF.')
        pdf_rebuild='NORMALIZED_TEXT_MATCH'
        print('Rebuilt PDF: warning-free, normalized text matches inspected PDF.',flush=True)
    status=json.loads((ROOT/'RELEASE_STATUS.json').read_text(encoding='utf-8'))
    if status['edition']!=module.EDITION:raise ValueError('Release edition mismatch.')
    if status['product_runtime_included'] is not False:raise ValueError('Research package misclassified as a product runtime.')
    return {'edition':module.EDITION,'package_files':hashes,'local_links':links,
            'study_artifacts':'BYTE_IDENTICAL','normal_and_optimized_tests':'PASSED',
            'paper_rebuild':pdf_rebuild,'scope':'Research publication and supplied models only'}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full',action='store_true',help='Also rebuild the PDF and compare extracted text.')
    parser.add_argument('--report',type=Path,help='Write a NEW report outside the source package.')
    args=parser.parse_args()
    try:
        if args.report:
            if args.report.exists() or args.report.is_symlink():raise ValueError('Report already exists; choose a new path.')
            if args.report.resolve().is_relative_to(ROOT):raise ValueError('Write reports outside the immutable package.')
        result=run_checks(args.full)
        if args.report:
            with args.report.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
        print(json.dumps(result,indent=2))
        print('Publication checks are not proof of autonomous discovery, live security, demand or profit.')
        return 0
    except (OSError,ValueError,ImportError,subprocess.SubprocessError) as exc:
        print(f'Verification failed: {exc}',file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
