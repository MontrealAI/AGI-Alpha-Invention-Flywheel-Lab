"""Create and verify a compact no-Git commercial campaign distribution."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

PREFIXES = ['commercial', 'benchmarks', 'campaign/commercial-010', 'docs/commercial010', 'evidence/commercial010', 'vendor']
FILES = ['README.md', 'AGENTS.md', 'CHARTER.md', 'FIRST_CAMPAIGN.md', 'COMMERCIAL_COMPARISON.md',
         'run_commercial010.py', 'requirements-commercial010.txt', 'scripts/run_service010.py', 'scripts/run_onboarding010.py', 'scripts/package_commercial010.py', 'scripts/check_commercial010_paper.py',
         'experiments/__init__.py', 'experiments/commerce006.py', 'experiments/resource006_v3.py',
         'verification/__init__.py', 'verification/commercial010_audit.py']


def build(root, output, source):
    root, output = Path(root).resolve(), Path(output)
    if not re.fullmatch('[0-9a-f]{40}', source):
        raise ValueError('IMMUTABLE_SOURCE_COMMIT_REQUIRED')
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    candidates = {root / name for name in FILES}
    for prefix in PREFIXES:
        candidates.update((root / prefix).rglob('*'))
    candidates.update((root / 'tests').glob('*010*.py'))
    entries = {}
    for path in sorted(candidates):
        if path.is_symlink():
            raise ValueError('PACKAGE_SYMLINK_REFUSED')
        if not path.is_file() or '__pycache__' in path.parts or path.suffix in {'.pyc', '.lock'}:
            continue
        raw = path.read_bytes()
        entries[path.relative_to(root).as_posix()] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    required = set(FILES) | {'campaign/commercial-010/SOURCE_FREEZE.json', 'campaign/commercial-010/POLICY.json', 'docs/commercial010/paper.pdf'}
    if not required <= set(entries):
        raise ValueError('INCOMPLETE_COMMERCIAL_DISTRIBUTION ' + str(sorted(required - set(entries))))
    manifest = {'schema': 'agi-alpha/commercial010-distribution/v1', 'source_commit': source,
                'scope': 'SIMULATED', 'entries': entries,
                'dependencies': 'Python3.12; pinned cryptography/cffi/pycparser in requirements-commercial010.txt; native exchange source included; PDF recompilation needs pdflatex separately.',
                'replay': 'Run commands in campaign/commercial-010/REPRODUCE.md. No Git history or network required for runtime.'}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in [*entries, 'PACKAGE_MANIFEST.json']:
            raw = (root / name).read_bytes() if name in entries else (json.dumps(manifest, indent=2) + '\n').encode()
            if name in entries and hashlib.sha256(raw).hexdigest() != entries[name]['sha256']:
                raise ValueError('SOURCE_CHANGED_DURING_PACKAGE')
            info = zipfile.ZipInfo(name, (2026, 10, 30, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, raw, compresslevel=9)
    verify(output)
    return {'archive': output.name, 'bytes': output.stat().st_size, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'files': len(entries), 'source_commit': source}


def verify(archive):
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or any(Path(n).is_absolute() or '..' in Path(n).parts for n in names):
            raise ValueError('UNSAFE_ARCHIVE_PATH')
        m = json.loads(z.read('PACKAGE_MANIFEST.json'))
        if set(names) != set(m['entries']) | {'PACKAGE_MANIFEST.json'} or m['scope'] != 'SIMULATED':
            raise ValueError('ARCHIVE_MEMBERS_OR_SCOPE_CHANGED')
        for name, meta in m['entries'].items():
            raw = z.read(name)
            if len(raw) != meta['bytes'] or hashlib.sha256(raw).hexdigest() != meta['sha256']:
                raise ValueError('ARCHIVE_SOURCE_CHANGED ' + name)
    return m


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=Path('.'))
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--source', required=True)
    a = p.parse_args()
    print(json.dumps(build(a.root, a.output, a.source)))
