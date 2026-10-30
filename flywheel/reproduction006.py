"""Materialize frozen cycle-006 inputs without changing their reference identities."""
import argparse
import hashlib
import json
from pathlib import Path

FREEZE = 'campaign/cycle-006/REPRODUCTION_FREEZE.json'
FREEZE_SHA256 = 'd64396e8d8e058aaddf1ecacf3e89f618d77b1e9ea88c87682ac3e8917534fdc'
SNAPSHOTS = {
    '.github/workflows/campaign.yml': 'historical/cycle-006/campaign-workflow.yml.txt',
    'flywheel/legacy.py': 'historical/cycle-006/legacy.py.txt',
    **{name: 'historical/cycle-001/' + name + '.txt'
       for name in ('AGENTS.md', 'CHARTER.md', 'FIRST_CAMPAIGN.md', 'README.md')},
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def regular(root, name):
    relative = Path(name)
    if (type(name) is not str or relative.is_absolute() or '..' in relative.parts
            or not relative.parts or relative.as_posix() != name or '\\' in name):
        raise ValueError('FROZEN006_PATH_SCOPE')
    path = root / relative
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError('FROZEN006_SYMLINK_REFUSED ' + name)
    if not path.is_file():
        raise ValueError('FROZEN006_INPUT_MISSING ' + name)
    return path.read_bytes()


def materialize(root, destination):
    root, destination = Path(root).resolve(), Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    if any(parent.is_symlink() for parent in destination.parents):
        raise ValueError('FROZEN006_DESTINATION_SYMLINK')
    if any((parent/'.git').exists() for parent in [destination, *destination.parents]):
        raise ValueError('FROZEN006_DESTINATION_GIT_ANCESTRY')
    freeze_raw = regular(root, FREEZE)
    if digest(freeze_raw) != FREEZE_SHA256:
        raise ValueError('FROZEN006_FREEZE_IDENTITY_MISMATCH')
    frozen = json.loads(freeze_raw)
    pins = frozen['sources']
    if frozen['schema'] != 'agi-alpha/cycle006-reproduction-freeze/v1' or len(pins) != 6363:
        raise ValueError('FROZEN006_SOURCE_SET_MISMATCH')
    payloads, origins = {FREEZE: freeze_raw}, {}
    for name, expected in sorted(pins.items()):
        raw, origin = regular(root, name), 'current-tree'
        if digest(raw) != expected and name in SNAPSHOTS:
            raw, origin = regular(root, SNAPSHOTS[name]), SNAPSHOTS[name]
        if digest(raw) != expected:
            raise ValueError('FROZEN006_SOURCE_IDENTITY_MISMATCH ' + name)
        payloads[name], origins[name] = raw, origin
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in payloads.items():
        path = destination/name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream: stream.write(raw)
    receipt = {'schema': 'alpha/frozen-cycle006-materialization/v1',
        'freeze_sha256': FREEZE_SHA256, 'sources_checked': len(pins),
        'scientific_public_commit': frozen['scientific_public_commit'],
        'substituted_original_inputs': {name: {'origin': origin, 'sha256': pins[name]}
            for name, origin in origins.items() if origin != 'current-tree'},
        'git_history_required': False, 'destination_git_ancestry_absent': True,
        'scope': 'Exact historical reproduction inputs, not execution of current code as historical code; exposed engineering replay only.'}
    with (destination/'FROZEN006_SNAPSHOT.json').open('x') as stream:
        json.dump(receipt, stream, indent=2); stream.write('\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(args.root, args.output)))


if __name__ == '__main__':
    main()
