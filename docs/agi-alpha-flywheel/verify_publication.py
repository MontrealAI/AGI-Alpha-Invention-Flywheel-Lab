import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata

ROOT = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pdf_facts(path):
    if not path.read_bytes().startswith(b'%PDF-'):
        raise ValueError(f'Not a PDF: {path.name}')
    info = subprocess.check_output(['pdfinfo', str(path)], text=True)
    text = subprocess.check_output(['pdftotext', str(path), '-'], text=True)
    pages = int(re.search(r'^Pages:\s+(\d+)', info, re.M).group(1))
    required = ('FLYWHEEL', 'Vincent Boucher', 'Build the next starting point', 'References')
    for phrase in required:
        if phrase not in text:
            raise ValueError(f'Missing PDF text: {phrase}')
    if '[?]' in text or 'PAPER_SHA256_PLACEHOLDER' in text or 'PAPER_PAGECOUNT_PLACEHOLDER' in text:
        raise ValueError('Unresolved PDF content')
    if pages < 12:
        raise ValueError('Unexpectedly incomplete manuscript')
    return pages


def check_sources():
    tex = (ROOT / 'paper.tex').read_text()
    bib = (ROOT / 'references.bib').read_text()
    cited = {key.strip() for group in re.findall(r'\\cite\w*\{([^}]+)\}', tex) for key in group.split(',')}
    defined = set(re.findall(r'@\w+\s*\{\s*([^,\s]+)', bib))
    if cited != defined:
        raise ValueError(f'Citation mismatch: undefined={sorted(cited-defined)}, unused={sorted(defined-cited)}')
    subprocess.run([sys.executable, str(ROOT / 'examples/succession.py'), '--check'], check=True)
    actual = subprocess.check_output([sys.executable, str(ROOT / 'examples/succession.py')], text=True)
    if json.loads(actual) != json.loads((ROOT / 'examples/example-results.json').read_text()):
        raise ValueError('Stored example differs from current executable source')
    return len(cited)


def normalized_pdf_text(path):
    text = unicodedata.normalize('NFKC', subprocess.check_output(['pdftotext', str(path), '-'], text=True))
    text = text.replace('\u00ad', '')
    text = re.sub(r'(?<=[A-Za-z])-\s*\n\s*(?=[a-z])', '', text)
    text = ''.join(text.split())
    return re.sub(r'(?<=[A-Za-z])-(?=[A-Za-z])', '', text)


def verify(build_only=False):
    citations = check_sources()
    if build_only:
        pdf = ROOT / 'build/paper.pdf'
        pages = pdf_facts(pdf)
        log = (ROOT / 'build/paper.log').read_text(errors='replace')
        bad = re.findall(r'^.*(?:Overfull \\[hv]box|undefined references|Citation .* undefined|LaTeX Error|Package .* Error).*$', log, re.M)
        if bad:
            raise ValueError('Compilation defects: ' + '; '.join(bad))
        return {'status': 'PASS', 'scope': 'local build and exact example', 'pages': pages, 'citations': citations}
    manifest = json.loads((ROOT / 'PUBLICATION.json').read_text())
    for name, expected in manifest['source_sha256'].items():
        path = ROOT / name
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError(f'Invalid source path: {name}')
        if sha256(path) != expected:
            raise ValueError(f'Source identity changed: {name}')
    standalone = ROOT / 'AGI_ALPHA_FLYWHEEL.pdf'
    pdf = standalone if standalone.exists() else ROOT.parent / 'research/agi-alpha-flywheel-20261102.pdf'
    if sha256(pdf) != manifest['pdf']['sha256'] or pdf.stat().st_size != manifest['pdf']['bytes']:
        raise ValueError('Published PDF identity changed')
    pages = pdf_facts(pdf)
    if pages != manifest['pdf']['pages']:
        raise ValueError('Published page count differs')
    rebuilt = ROOT / 'build/paper.pdf'
    if rebuilt.exists():
        if pdf_facts(rebuilt) != pages or normalized_pdf_text(rebuilt) != normalized_pdf_text(pdf):
            raise ValueError('Rebuilt manuscript differs from the inspected publication')
    return {'status': 'PASS', 'scope': 'inspected publication and bound source', 'pages': pages, 'citations': citations, 'pdf_sha256': sha256(pdf), 'rebuilt_text_matches': rebuilt.exists()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(verify(args.build_only), sort_keys=True))
