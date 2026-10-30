"""Materialize the exact released cycle-005 baseline without rewriting its freeze."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tempfile
import zipfile

from .archive_v2 import extract, PREFIX

ARCHIVE_SHA256 = '9e80e3708f430b0a5ac18c8580eb2320febb213cbda63cc7eaa00be81b78e95d'
ARCHIVE_BYTES = 5858230
FREEZE_SHA256 = '6606628dcd020dc735219186ba678ec0f4bb3d906ff689f5b896966406af4b40'
OLD_COMMIT = 'bef0b697206699330a158f1430fe3b3ca58c6d97'
ARCHIVE_PATH = 'historical/cycle-005/mechanism-completion-release.zip'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def materialize(root, destination):
    root, destination = Path(root).resolve(), Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    if any(parent.is_symlink() for parent in destination.parents):
        raise ValueError('BASELINE005_DESTINATION_SYMLINK')
    if any((parent/'.git').exists() for parent in [destination, *destination.parents]):
        raise ValueError('BASELINE005_GIT_ANCESTRY_REFUSED')
    source = root / ARCHIVE_PATH
    if source.is_symlink() or any(parent.is_symlink() for parent in source.parents) or not source.is_file():
        raise ValueError('BASELINE005_ARCHIVE_MISSING_OR_SYMLINK')
    if source.stat().st_size != ARCHIVE_BYTES:
        raise ValueError('BASELINE005_ARCHIVE_IDENTITY_MISMATCH')
    raw = source.read_bytes()
    if sha(raw) != ARCHIVE_SHA256:
        raise ValueError('BASELINE005_ARCHIVE_IDENTITY_MISMATCH')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        freeze_raw = archive.read(PREFIX+'campaign/cycle-005/FREEZE.json')
        if sha(freeze_raw) != FREEZE_SHA256:
            raise ValueError('BASELINE005_FREEZE_IDENTITY_MISMATCH')
        frozen = json.loads(freeze_raw)
        if type(frozen.get('sources')) is not dict or len(frozen['sources']) != 50:
            raise ValueError('BASELINE005_SOURCE_SET_MISMATCH')
        for name, expected in frozen['sources'].items():
            if sha(archive.read(PREFIX+name)) != expected:
                raise ValueError('BASELINE005_SOURCE_IDENTITY_MISMATCH '+name)
    with tempfile.TemporaryDirectory(prefix='alpha005-pinned-input-') as temporary:
        pinned = Path(temporary)/'released.zip'
        with pinned.open('xb') as stream:
            stream.write(raw)
        manifest = extract(pinned, destination)
    receipt = {'schema': 'agi-alpha/cycle005-unchanged-release-snapshot/v1', 'old_commit': OLD_COMMIT,
        'archive_sha256': ARCHIVE_SHA256, 'archive_bytes': ARCHIVE_BYTES,
        'freeze_sha256': FREEZE_SHA256, 'sources': frozen['sources'], 'payload_files': len(manifest['files']),
        'git_history_required': False, 'git_ancestry_absent': True, 'packaging_manifest_consumed': True,
        'scope': 'Exact historical source identity, not retrospective recertification; old commands execute unchanged.'}
    with (destination/'CYCLE005_SNAPSHOT.json').open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    receipt = materialize(args.root, args.output)
    print(json.dumps({'output': str(args.output), 'archive_sha256': receipt['archive_sha256'], 'sources': len(receipt['sources'])}))


if __name__ == '__main__':
    main()
