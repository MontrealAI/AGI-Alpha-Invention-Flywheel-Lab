"""Stage an unchanged historical experiment without newer package initializers."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil

FREEZE = 'campaign/cycle-007/REPAIRED_REPRODUCTION_FREEZE.json'
COMPATIBILITY_MAIN = 'a842861dcf532ee8b769f39248c4c1faabfb628a'
COMPATIBILITY_DEPENDENCIES = {
    'experiments/commerce006.py': '2fc529131885c75752dab8dbd77d85b5a36d4c0b43cb5e7e53286c997cc0a52f',
    'campaign/cycle-007/ECONOMICS_SOURCES.json': '9bb9410fa5b6fb0d5b185342796cb5f900ad8eb2709657315a249bc5f219050c'}

def regular(root, name):
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts or str(relative) != name:
        raise ValueError('HISTORICAL_RELATIVE_SOURCE_REQUIRED')
    path = root / relative
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('HISTORICAL_REGULAR_SOURCE_REQUIRED:' + name)
    return path

def stage(root, output):
    root, output = Path(root).resolve(), Path(output).absolute()
    if output.exists() or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError('NEW_UNSYMLINKED_HISTORICAL_STAGE_REQUIRED')
    raw = regular(root, FREEZE).read_bytes()
    freeze = json.loads(raw)
    files = dict(freeze['files'])
    for name, expected in files.items():
        if hashlib.sha256(regular(root, name).read_bytes()).hexdigest() != expected:
            raise ValueError('FROZEN_SOURCE_MISMATCH:' + name)
    if any(name in files for name in freeze.get('expected_absent_paths', [])):
        raise ValueError('INCONSISTENT_FROZEN_ABSENCE_CONTRACT')
    extras = {name: hashlib.sha256(regular(root, name).read_bytes()).hexdigest()
              for name in (FREEZE, 'run_cycle007_repaired.py') if name not in files}
    for name, expected in COMPATIBILITY_DEPENDENCIES.items():
        if hashlib.sha256(regular(root, name).read_bytes()).hexdigest() != expected:
            raise ValueError('PINNED_COMPATIBILITY_HELPER_CHANGED:' + name)
        if name not in files:
            extras[name] = expected
    output.mkdir(parents=True)
    for name in sorted(set(files) | set(extras)):
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(regular(root, name), target)
        if hashlib.sha256(target.read_bytes()).hexdigest() != (files | extras)[name]:
            raise ValueError('HISTORICAL_COPY_CHANGED:' + name)
    if any((output / name).exists() for name in freeze.get('expected_absent_paths', [])):
        raise ValueError('HISTORICAL_ABSENCE_CONTRACT_CHANGED')
    receipt = {'schema': 'agi-alpha/cycle007-isolated-source-stage/v1',
        'freeze_sha256': hashlib.sha256(raw).hexdigest(), 'frozen_files': len(files),
        'unchanged_orchestration_files': extras, 'expected_absent_paths': freeze.get('expected_absent_paths', []),
        'additional_compatibility_main': COMPATIBILITY_MAIN,
        'additional_compatibility_dependencies': COMPATIBILITY_DEPENDENCIES,
        'historical_limit': 'The original95-file freeze omitted commerce006. This explicit helper pin qualifies current exposed compatibility, not the original freeze or a new scientific result.',
        'scope': 'Historical source reproduction only; no current portfolio qualification or rewritten evidence.'}
    (output / 'ISOLATED_STAGE.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt

def verify_stage(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    raw = regular(root, FREEZE).read_bytes()
    if regular(output, FREEZE).read_bytes() != raw:
        raise ValueError('STAGED_FREEZE_CHANGED')
    freeze = json.loads(raw)
    expected = dict(freeze['files']) | COMPATIBILITY_DEPENDENCIES
    expected['run_cycle007_repaired.py'] = hashlib.sha256(regular(root, 'run_cycle007_repaired.py').read_bytes()).hexdigest()
    for name, checksum in expected.items():
        if hashlib.sha256(regular(output, name).read_bytes()).hexdigest() != checksum:
            raise ValueError('STAGED_EXECUTING_DEPENDENCY_CHANGED:' + name)
    if any((output / name).exists() or (output / name).is_symlink()
           for name in freeze.get('expected_absent_paths', [])):
        raise ValueError('STAGED_ABSENCE_CONTRACT_CHANGED')
    return {'accepted': True, 'frozen_files': len(freeze['files']), 'additional_pinned_dependencies': COMPATIBILITY_DEPENDENCIES}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--output', required=True)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    print(json.dumps(verify_stage(args.root, args.output) if args.verify else stage(args.root, args.output)))
