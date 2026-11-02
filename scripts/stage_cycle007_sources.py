"""Stage an unchanged historical experiment without newer package initializers."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil

FREEZE = 'campaign/cycle-007/REPAIRED_REPRODUCTION_FREEZE.json'

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
        'scope': 'Historical source reproduction only; no current portfolio qualification or rewritten evidence.'}
    (output / 'ISOLATED_STAGE.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.root, args.output)))
