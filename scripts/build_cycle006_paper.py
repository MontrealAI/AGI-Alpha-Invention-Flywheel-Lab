import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
AUTHOR = 'Vincent Boucher, President of MONTREAL.AI'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_file(name):
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts or any((ROOT / Path(*relative.parts[:i])).is_symlink() for i in range(1, len(relative.parts) + 1)):
        raise ValueError('UNSAFE_INPUT_PATH: ' + name)
    path = ROOT / relative
    if not path.is_file():
        raise ValueError('MISSING_INPUT: ' + name)
    return path


def build(markdown, manifest, destination):
    started, cpu = time.monotonic(), time.process_time()
    prior = resource.getrusage(resource.RUSAGE_CHILDREN)
    source, binding = checked_file(markdown), checked_file(manifest)
    declared = json.loads(binding.read_text())
    if declared.get('schema') != 'agi-alpha-evidence-paper/v1' or not re.fullmatch('[0-9a-f]{40}', declared.get('source_ref', '')):
        raise ValueError('PAPER_SCHEMA_OR_PUBLIC_SOURCE_REF')
    if sha(source) != declared.get('markdown_sha256') or not declared.get('evidence'):
        raise ValueError('UNBOUND_PAPER_SOURCE_OR_EMPTY_EVIDENCE')
    for name, expected in declared['evidence'].items():
        if not re.fullmatch('[0-9a-f]{64}', expected) or sha(checked_file(name)) != expected:
            raise ValueError('EVIDENCE_IDENTITY_MISMATCH: ' + name)
    if not declared.get('title') or declared.get('author') != AUTHOR:
        raise ValueError('PAPER_TITLE_OR_AUTHOR')
    destination = Path(destination).resolve()
    if any(destination.with_suffix('.' + extension).is_symlink() for extension in ('tex', 'html', 'pdf', 'build.json')):
        raise ValueError('UNSAFE_OUTPUT_PATH')
    destination.parent.mkdir(parents=True, exist_ok=True)
    for binary in ('pandoc', 'pdflatex', 'pdfinfo'):
        if not shutil.which(binary):
            raise RuntimeError('MISSING_TOOL: ' + binary)
    env = dict(os.environ, SOURCE_DATE_EPOCH=str(declared.get('source_date_epoch', 1793318400)), FORCE_SOURCE_DATE='1', TZ='UTC')
    with tempfile.TemporaryDirectory(prefix='paper006-', dir=destination.parent) as temporary:
        work = Path(temporary)
        stem = destination.name
        common = ['pandoc', str(source), '--standalone', '--metadata', 'title=' + declared['title'], '--metadata', 'author=' + AUTHOR,
                  '--metadata', 'date=' + declared.get('date', '29 October 2026'), '--variable', 'geometry:margin=1in', '--variable', 'fontsize:10pt',
                  '--variable', 'colorlinks=true', '--variable', 'linkcolor=Maroon', '--variable', 'urlcolor=Blue', '--variable', 'documentclass=article']
        subprocess.run(common + ['--to=latex', '--output', str(work / (stem + '.tex'))], check=True, timeout=30, env=env, cwd=ROOT)
        header = work / 'style.html'
        header.write_text('<style>body{max-width:78ch;margin:3rem auto;padding:0 1.2rem;font:17px/1.65 system-ui,sans-serif;color:#172033}h1,h2,h3{line-height:1.2;color:#162b4a}table{border-collapse:collapse;width:100%;font-size:.9em}td,th{padding:.5rem;border-bottom:1px solid #ccd3dc;text-align:left;vertical-align:top}code{overflow-wrap:anywhere}pre{overflow:auto;background:#f2f4f7;padding:1rem}a{color:#174b88}img{max-width:100%}@media print{body{max-width:none;margin:0}}</style>')
        subprocess.run(common + ['--to=html5', '--mathml', '--include-in-header', str(header), '--output', str(work / (stem + '.html'))], check=True, timeout=30, env=env, cwd=ROOT)
        with (work / 'compile.log').open('wb') as log:
            for _ in range(2):
                subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', '-file-line-error', stem + '.tex'], check=True,
                               stdout=log, stderr=subprocess.STDOUT, timeout=60, env=env, cwd=work)
        log = (work / (stem + '.log')).read_text(errors='replace')
        bad = [line for line in log.splitlines() if 'Overfull ' in line or 'undefined references' in line]
        if bad:
            raise ValueError('PAPER_LAYOUT_OR_REFERENCE_FAILURE: ' + '\n'.join(bad))
        info = subprocess.check_output(['pdfinfo', str(work / (stem + '.pdf'))], text=True, timeout=10)
        pages = int(re.search(r'^Pages:\s+(\d+)$', info, re.MULTILINE).group(1))
        for extension in ('tex', 'html', 'pdf'):
            shutil.copyfile(work / (stem + '.' + extension), destination.with_suffix('.' + extension))
        versions = {binary: subprocess.check_output([binary, '--version'], text=True).splitlines()[0] for binary in ('pandoc', 'pdflatex')}
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        receipt = {'schema': 'agi-alpha-evidence-paper-build/v1', 'source_ref': declared['source_ref'], 'manifest_sha256': sha(binding),
                   'markdown_sha256': sha(source), 'evidence': declared['evidence'], 'outputs': {(destination.with_suffix('.' + extension).relative_to(ROOT).as_posix() if destination.is_relative_to(ROOT) else str(destination.with_suffix('.' + extension))): sha(destination.with_suffix('.' + extension)) for extension in ('tex', 'html', 'pdf')},
                   'pages': pages, 'visual_inspection': 'PENDING_SEPARATE_RENDERED_PAGE_INSPECTION',
                   'pandoc': versions['pandoc'], 'pdflatex': versions['pdflatex'],
                   'resources': {'wall_seconds': time.monotonic() - started, 'process_cpu_seconds': time.process_time() - cpu,
                                 'child_cpu_seconds': usage.ru_utime + usage.ru_stime - prior.ru_utime - prior.ru_stime,
                                 'external_model_calls': 0, 'complete_monetary_cost': None},
                   'scope': 'Hash binding and clean compilation do not establish the truth of scientific or commercial claims.'}
        destination.with_suffix('.build.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--markdown', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', default=str(ROOT / 'docs/research/cycle-006'))
    args = parser.parse_args()
    print(json.dumps(build(args.markdown, args.manifest, args.output), indent=2))


if __name__ == '__main__':
    main()
