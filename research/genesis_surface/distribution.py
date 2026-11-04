"""Build and verify a small, explicitly allowlisted public research distribution.

No native account directories, credentials, repository history, unrelated files,
or private source documents are read or exported. A package is not a deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

from .build import build, audit, save
from .calibration import diagnose
from .model import read
from .mesh import export_mesh

ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN = 'campaign/genesis-surface/'
CAMPAIGN_FILES = ('REQUEST.json', 'SUCCESSOR_REQUEST.json', 'README.md', 'requirements.txt', 'CAPABILITY.json')


def source_files(root=ROOT):
    files = [p.relative_to(root).as_posix() for p in (root/'research/genesis_surface').glob('*.py')]
    files += [p.relative_to(root).as_posix() for p in (root/'tests').glob('test_genesis_surface*.py')]
    files += [CAMPAIGN+n for n in CAMPAIGN_FILES]
    for name in files:
        p = root/name
        if not p.is_file() or any(q.is_symlink() for q in (p, *p.parents)):
            raise ValueError('regular allowlisted source required: '+name)
    return sorted(set(files))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def start_page(diagnosis):
    threshold = 100*diagnosis['fixed_design_requirement']['maximum_uniform_relative_shear_error']
    nominal_contacts = diagnosis['nominal_check']['contacts']
    conditional_contacts = diagnosis['hypothetical_calibration_comparison']['check']['contacts']
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ALPHA GENESIS — Start here</title>
<style>*{{box-sizing:border-box}}body{{margin:0;background:#111019;color:#f2eee5;font:17px/1.65 system-ui,sans-serif}}main{{max-width:1000px;margin:auto;padding:44px 24px}}h1{{font-size:clamp(36px,6vw,65px);line-height:1.06;letter-spacing:-2px}}h2{{line-height:1.25}}a{{color:#f6d18a}}.kicker{{color:#f6d18a;font-size:12px;letter-spacing:3px}}.card{{background:#211b2c;padding:24px;border:1px solid #574559;border-radius:15px;margin:24px 0}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:20px}}.button{{display:inline-block;background:#f6d18a;color:#201322;font-weight:700;padding:12px 20px;border-radius:8px;text-decoration:none;margin:5px 0}}code,pre{{font-size:13px;white-space:pre-wrap;overflow-wrap:anywhere}}.muted{{color:#c9bfd0}}footer{{border-top:1px solid #574559;margin-top:40px;padding-top:20px;font-size:14px}}</style></head><body><main>
<p class="kicker">MONTREAL.AI · QUEBEC.AI</p><h1>ALPHA GENESIS<br>A capability you can inspect.</h1>
<p>From a declared physical-function requirement to editable geometry, independent numerical checking and a precise statement of what evidence is still missing.</p>
<a class="button" href="demo/OPEN_ME.html">Open the constructed design</a>
<div class="grid"><section class="card"><h2>Inspect</h2><p><a href="demo/surface.scad" download>Editable CAD</a><br><a href="mesh/surface-preview.stl" download>3D preview mesh</a><br><a href="demo/layout.json">Contact-family map</a></p></section><section class="card"><h2>Understand</h2><p><a href="CALIBRATION.json">Calibration diagnosis</a><br><a href="reverse/OPEN_ME.html">Second development target</a><br><a href="demo/PHYSICAL_TEST_PLAN.md">Physical acceptance plan</a></p></section></div>
<section class="card"><h2>The finding—not a sales claim</h2><p>The nominal {nominal_contacts}-contact design meets the specified numerical target. The existing uncertainty boxes cannot guarantee that result. For the fixed design, the most restrictive modeled shear-accuracy requirement is approximately <strong>{threshold:.4f}%</strong>, with geometry, modulus and model discrepancy held fixed.</p><p>A conditional redesign for a <em>hypothetical</em>0.25% calibration bound uses {conditional_contacts} contacts and passes its independent numerical check. That calibration has <strong>not</strong> been measured. The system preserves the failed original uncertainty test.</p><p><strong>Physical and commercial status: not qualified.</strong> The current evidence does not justify fabricating for use or claiming a sellable breakthrough. A single-material print does not reproduce the different contact families.</p></section>
<section class="card"><h2>Use the software</h2><p>No installation is needed to inspect this package. To calculate another design, use Python 3.12 and the declared numerical dependencies. From the extracted folder:</p><pre>python -m pip install -r campaign/genesis-surface/requirements.txt
python -m research.genesis_surface build --out /absolute/new/my-design
python -m research.genesis_surface audit --out /absolute/new/my-design
python -m research.genesis_surface.calibration --design /absolute/new/my-design --out /absolute/new/calibration.json</pre><p>These commands do not use paid model APIs, access an account or operate hardware. Change a copy of the request and supply <code>--request your-request.json</code> to build a different declared target.</p><p><a href="README.md">Build instructions and scope</a> · <a href="PACKAGE.json">Exact source and file identities</a></p></section>
<footer>This is a working research construction tool, not the complete autonomous enterprise. No actual customer revenue, new physical measurements, improved inventor, or production deployment is established.</footer></main></body></html>'''


def verify(root):
    root = Path(root).absolute()
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError('regular package root required')
    manifest = read(root/'PACKAGE.json')
    if manifest.get('schema') != 'genesis/surface-distribution/v1':
        raise ValueError('package schema')
    if manifest.get('scope') != 'RESEARCH_ONLY_NOT_PHYSICAL_OR_COMMERCIAL_QUALIFICATION':
        raise ValueError('package scope')
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.relative_to(root).as_posix() != 'PACKAGE.json'}
    if any(p.is_symlink() for p in root.rglob('*')):
        raise ValueError('package symlink')
    if actual != set(manifest['files']):
        raise ValueError('package file inventory changed')
    for name, expected in manifest['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts or sha(root/name) != expected:
            raise ValueError('package file identity changed: '+name)
    for folder in ('demo','reverse'):
        audit(root/folder)
    result = diagnose(root/'demo', .0025)
    if read(root/'CALIBRATION.json') != result:
        raise ValueError('calibration result does not reproduce')
    return {'accepted': True, 'files': len(actual), 'scope': manifest['scope'], 'commit': manifest['commit']}


def package(output, commit='LOCAL_CANDIDATE_NOT_PUBLISHED'):
    output = Path(output).absolute()
    if any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError('regular new output required')
    output.mkdir(parents=True, exist_ok=False)
    stage = output/'ALPHA_GENESIS_SURFACE'
    stage.mkdir()
    names = source_files()
    for name in names:
        dst = stage/name; dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, dst)
    # Namespace package initialization is explicit in the standalone distribution.
    (stage/'research/__init__.py').write_text('"""GENESIS public research distribution."""\n')
    build(ROOT/(CAMPAIGN+'REQUEST.json'), stage/'demo')
    build(ROOT/(CAMPAIGN+'SUCCESSOR_REQUEST.json'), stage/'reverse')
    diagnosis = diagnose(stage/'demo', .0025)
    save(stage/'CALIBRATION.json', diagnosis)
    export_mesh(stage/'demo', stage/'mesh', .2)
    (stage/'START_HERE.html').write_text(start_page(diagnosis), encoding='utf-8')
    (stage/'README.md').write_text('# ALPHA GENESIS — executable surface research\n\nExtract the complete ZIP and open START_HERE.html.\n\n'
        'This distribution contains public source, two exposed development designs, CAD, a sampled mesh and independently checked numerical evidence. It contains no accounts or credentials.\n\n'
        'Run tests: `python -B -m unittest discover -s tests -p "test_genesis_surface*.py" -v`.\n\n'
        'Verify package: `python -B -m research.genesis_surface.distribution verify --out .`.\n\n'
        'Physical behavior, customer value and a self-sustaining enterprise remain unestablished. Source is supplied under the originating project\'s existing terms; no new license is granted by packaging.\n', encoding='utf-8')
    identities = {p.relative_to(stage).as_posix(): sha(p) for p in sorted(stage.rglob('*')) if p.is_file()}
    save(stage/'PACKAGE.json', {'schema':'genesis/surface-distribution/v1', 'commit':commit,
        'scope':'RESEARCH_ONLY_NOT_PHYSICAL_OR_COMMERCIAL_QUALIFICATION', 'files':identities,
        'source_files':names, 'digest_meaning':'Byte identity, not independent scientific certification.'})
    verify(stage)
    archive = output/'ALPHA_GENESIS_SURFACE.zip'
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(stage.rglob('*')):
            if path.is_file():
                info = zipfile.ZipInfo('ALPHA_GENESIS_SURFACE/'+path.relative_to(stage).as_posix(), (2026,11,4,0,0,0))
                info.external_attr = 0o100644 << 16
                z.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    with tempfile.TemporaryDirectory() as temp:
        with zipfile.ZipFile(archive) as z:
            for member in z.infolist():
                if Path(member.filename).is_absolute() or '..' in Path(member.filename).parts:
                    raise ValueError('unsafe generated member')
            z.extractall(temp)
        extracted = Path(temp)/'ALPHA_GENESIS_SURFACE'
        env = {k:v for k,v in os.environ.items() if k in ('PATH','SYSTEMROOT','TMPDIR','LANG','LC_ALL')}
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        command = [sys.executable, '-B', '-m', 'research.genesis_surface.distribution', 'verify', '--out', '.']
        p = subprocess.run(command, cwd=extracted, env=env, text=True, capture_output=True, check=True)
        verification = json.loads(p.stdout)
    receipt = {'archive_sha256':sha(archive), 'archive_bytes':archive.stat().st_size,
               'clean_extracted_verification': verification, 'actual_release_download':False,
               'scope':'Generated candidate package verified after ZIP extraction. Not a merged or published release.'}
    save(output/'DISTRIBUTION_RECEIPT.json', receipt)
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['build','verify'])
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--commit', default='LOCAL_CANDIDATE_NOT_PUBLISHED')
    args = p.parse_args()
    result = package(args.out, args.commit) if args.command == 'build' else verify(args.out)
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__': main()
