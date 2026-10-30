import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def regular(name):
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts or any((ROOT / Path(*relative.parts[:i])).is_symlink() for i in range(1, len(relative.parts) + 1)):
        raise ValueError('UNSAFE_PAPER_INPUT')
    path = ROOT / relative
    if not path.is_file():
        raise ValueError('MISSING_PAPER_INPUT: ' + name)
    return path


def check():
    paths = {name: regular('docs/research/' + name) for name in ('cycle-007.md', 'cycle-007.inputs.json', 'cycle-007.build.json', 'PDF_QA_007.json')}
    inputs, build, qa = (json.loads(paths[name].read_text()) for name in ('cycle-007.inputs.json', 'cycle-007.build.json', 'PDF_QA_007.json'))
    if inputs.get('schema') != 'agi-alpha-evidence-paper/v1' or build.get('schema') != 'agi-alpha-evidence-paper-build/v1' or qa.get('schema') != 'agi-alpha-paper007-visual-qa/v1':
        raise ValueError('PAPER_RECEIPT_SCHEMA')
    if not re.fullmatch('[0-9a-f]{40}', inputs.get('source_ref', '')) or build.get('source_ref') != inputs['source_ref']:
        raise ValueError('PAPER_PUBLIC_SOURCE_IDENTITY')
    if sha(paths['cycle-007.inputs.json']) != build.get('manifest_sha256') or sha(paths['cycle-007.md']) != inputs.get('markdown_sha256') or inputs['markdown_sha256'] != build.get('markdown_sha256'):
        raise ValueError('PAPER_SOURCE_BINDING')
    evidence = inputs.get('evidence')
    if not isinstance(evidence, dict) or not 1 <= len(evidence) <= 256 or evidence != build.get('evidence'):
        raise ValueError('PAPER_EVIDENCE_BINDING')
    for name, expected in evidence.items():
        if not re.fullmatch('[0-9a-f]{64}', expected) or sha(regular(name)) != expected:
            raise ValueError('PAPER_EVIDENCE_CHANGED: ' + name)
    expected_paths = {'docs/research/cycle-007.' + extension for extension in ('tex', 'pdf', 'html')}
    if set(build.get('outputs', {})) != expected_paths:
        raise ValueError('PAPER_OUTPUT_SET')
    for name, expected in build['outputs'].items():
        if sha(regular(name)) != expected:
            raise ValueError('PAPER_OUTPUT_CHANGED: ' + name)
    pdf = regular('docs/research/cycle-007.pdf')
    if not pdf.read_bytes().startswith(b'%PDF-') or sha(pdf) != qa.get('pdf_sha256'):
        raise ValueError('PAPER_PDF_BINDING')
    if type(build.get('pages')) is not int or build['pages'] < 1 or qa.get('pages') != build['pages'] or qa.get('inspected_pages') != list(range(1, build['pages'] + 1)) or qa.get('passed') is not True:
        raise ValueError('PAPER_VISUAL_QA_COVERAGE')
    info = None
    if shutil.which('pdfinfo'):
        info = subprocess.check_output(['pdfinfo', str(pdf)], text=True, timeout=10)
        pages = re.search(r'^Pages:\s+(\d+)$', info, re.MULTILINE)
        if not pages or int(pages.group(1)) != build['pages']:
            raise ValueError('PAPER_ACTUAL_PAGE_COUNT')
    return {'schema': 'agi-alpha-paper007-mechanical-binding-check/v1', 'passed': True, 'source_ref': inputs['source_ref'],
            'evidence_files_checked': len(evidence), 'outputs': build['outputs'], 'pages': build['pages'],
            'qa_sha256': sha(paths['PDF_QA_007.json']), 'actual_pdfinfo_checked': info is not None,
            'scope': 'Identity and declared manual-QA coverage only; does not independently certify visual quality or scientific/commercial truth.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = check()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as stream:
            json.dump(report, stream, indent=2); stream.write('\n')
    print(json.dumps(report, indent=2))
