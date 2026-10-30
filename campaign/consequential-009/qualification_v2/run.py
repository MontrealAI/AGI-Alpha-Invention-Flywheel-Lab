"""Qualify frozen 009 execution with an explicit current journal-race adapter."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
FREEZE = 'campaign/consequential-009/SOURCE_FREEZE.json'
FREEZE_SHA256 = '089796613d29e7a8a68618bf68ebe4e70df0bbe3832668626e773070d1d7527e'
WORKFLOW = '.github/workflows/consequential009.yml'
SNAPSHOT = 'campaign/consequential-009/qualification_v2/consequential009-workflow.yml.txt'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def regular(root, name):
    relative = Path(name)
    if not relative.parts or relative.is_absolute() or '..' in relative.parts or relative.as_posix() != name or '\\' in name:
        raise ValueError('QUALIFICATION009_PATH')
    path = root / relative
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents) or not path.is_file():
        raise ValueError('QUALIFICATION009_REGULAR_INPUT_REQUIRED ' + name)
    return path.read_bytes()


def materialize(root, destination):
    root, destination = Path(root).resolve(), Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    if any(p.is_symlink() or (p / '.git').exists() for p in [destination, *destination.parents]):
        raise ValueError('QUALIFICATION009_FRESH_NOGIT_DESTINATION')
    raw = regular(root, FREEZE)
    if sha(raw) != FREEZE_SHA256:
        raise ValueError('QUALIFICATION009_FREEZE_IDENTITY')
    freeze = json.loads(raw)
    if freeze['schema'] != 'agi-alpha/consequential009-source-freeze/v1' or len(freeze['files']) != 31:
        raise ValueError('QUALIFICATION009_FROZEN_CLOSURE')
    payloads, substitutions = {FREEZE: raw}, {}
    for name, expected in freeze['files'].items():
        data = regular(root, name)
        if sha(data) != expected and name == WORKFLOW:
            data = regular(root, SNAPSHOT)
            substitutions[name] = {'origin': SNAPSHOT, 'sha256': sha(data)}
        if sha(data) != expected:
            raise ValueError('QUALIFICATION009_FROZEN_IDENTITY ' + name)
        payloads[name] = data
    destination.mkdir(parents=True, exist_ok=False)
    for name, data in payloads.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
    return {'source_freeze_sha256': FREEZE_SHA256, 'frozen_files_verified': 31,
            'historical_workflow_sha256': freeze['files'][WORKFLOW],
            'current_workflow_sha256': sha(regular(root, WORKFLOW)),
            'substituted_original_inputs': substitutions, 'git_history_required': False,
            'materialized_root': str(destination)}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(output):
    output = Path(output).absolute()
    frozen_root = output.with_name(output.name + '-frozen-inputs')
    boundary = materialize(ROOT, frozen_root)
    boundary.update({'schema': 'agi-alpha/consequential009-runtime-boundary/v2',
        'runner_adapter_sha256': sha(Path(__file__).read_bytes()),
        'resource_adapter_sha256': sha(regular(ROOT, 'campaign/consequential-009/qualification_v2/resource_guard.py')),
        'scope': 'Exposed engineering replay of original financial/technical source with an explicit current resource-monitor adapter; not a new campaign, original-monitor replay, or fresh confirmation.'})
    sys.path.insert(0, str(frozen_root))
    runner = load('_qualification009_frozen_runner', frozen_root / 'run_consequential009.py')
    adapter = load('_qualification009_resource_adapter', ROOT / 'campaign/consequential-009/qualification_v2/resource_guard.py')
    runner.bounded_run = adapter.run
    try:
        result = runner.run(output)
        boundary['completed'] = True
        return result
    finally:
        if output.is_dir():
            with (output / 'RUNTIME_BOUNDARY.json').open('x') as stream:
                json.dump(boundary, stream, indent=2, sort_keys=True, allow_nan=False)
                stream.write('\n')
        sys.path.pop(0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps({'completed': result['completed'], 'independent_acceptance': result['independent_acceptance'],
                      'mission_success': result['mission_success'], 'wall_seconds': result['wall_seconds']}))
