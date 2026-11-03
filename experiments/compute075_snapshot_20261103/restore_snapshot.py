"""Restore the reviewed public snapshot into a new directory; never run it."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import sys
import zipfile

ARCHIVE_SHA256 = '3e7344247b2c421d87ec55209030eb411935a8e1d0312742cb7e7db000f43d18'
MAX_FILES = 10000
MAX_BYTES = 512 * 1024**2


def restore(destination):
    root = Path(__file__).resolve().parent
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('New destination required')
    if any(parent.is_symlink() for parent in destination.parents):
        raise ValueError('Unsymlinked destination parents required')
    record = json.loads((root / 'TRANSPORT.json').read_text())
    raw = (root / 'SNAPSHOT.zip').read_bytes()
    if hashlib.sha256(raw).hexdigest() != ARCHIVE_SHA256 or record['archive_sha256'] != ARCHIVE_SHA256:
        raise ValueError('Archive identity mismatch')
    payloads = {}
    with zipfile.ZipFile(root / 'SNAPSHOT.zip') as archive:
        members = archive.infolist()
        if len(members) != len({m.filename for m in members}) or len(members) > MAX_FILES:
            raise ValueError('Duplicate or excessive members')
        if sum(m.file_size for m in members) > MAX_BYTES:
            raise ValueError('Uncompressed size limit')
        if set(record['files']) != {m.filename for m in members}:
            raise ValueError('Manifest member mismatch')
        for item in members:
            name = PurePosixPath(item.filename)
            if name.is_absolute() or '..' in name.parts or '\\' in item.filename or str(name) != item.filename:
                raise ValueError('Unsafe member path')
            if item.is_dir() or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('Regular files required')
            data = archive.read(item)
            expected = record['files'][item.filename]
            if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
                raise ValueError('Member identity mismatch')
            payloads[item.filename] = data
    if len(payloads) != record['file_count'] or sum(map(len, payloads.values())) != record['uncompressed_bytes']:
        raise ValueError('Transport totals mismatch')
    if hashlib.sha256(payloads['MANIFEST.json']).hexdigest() != record['inner_manifest_sha256']:
        raise ValueError('Inner manifest mismatch')
    destination.mkdir(parents=True, exist_ok=False)
    for name, data in payloads.items():
        path = destination.joinpath(*PurePosixPath(name).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
    return {'restored_files': len(payloads), 'bytes': sum(map(len, payloads.values())),
            'scope': 'Reviewed public derivative restored; no experiment executed.'}


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python3 restore_snapshot.py /absolute/new/destination')
    print(json.dumps(restore(sys.argv[1]), sort_keys=True))
