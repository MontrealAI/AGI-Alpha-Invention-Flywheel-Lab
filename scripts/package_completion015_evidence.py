"""Verify/extract the lossless completion015 historical evidence transport.

Never changes source, accounts, verdicts, guards or existing destinations.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

MAX_FILES = 10000
MAX_BYTES = 512 * 1024**2
PREFIXES = ('evidence/completion015/', 'evidence/connected014/')
SCHEMA = 'agi-alpha/completion015-evidence-transport/v1'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def strict(raw):
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('DUPLICATE_FIELD')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def safe(name):
    p = PurePosixPath(name)
    if (not name.startswith(PREFIXES) or p.is_absolute() or '..' in p.parts
            or str(p) != name or '\\' in name or '\0' in name
            or name.endswith('/') or len(p.parts) < 4):
        raise ValueError('MEMBER_SCOPE')
    return p


def payloads(index_raw, zip_raw):
    index = strict(index_raw)
    if index.get('schema') != SCHEMA or type(index.get('files')) is not dict:
        raise ValueError('INDEX_SCHEMA')
    files = index['files']
    if not 0 < len(files) <= MAX_FILES or len(files) != index['file_count']:
        raise ValueError('FILE_BOUND')
    if len(zip_raw) > MAX_BYTES or len(zip_raw) != index['bundle']['bytes'] or sha(zip_raw) != index['bundle']['sha256']:
        raise ValueError('TRANSPORT_IDENTITY')
    result = {}
    with zipfile.ZipFile(io.BytesIO(zip_raw)) as archive:
        entries = archive.infolist()
        if [e.filename for e in entries] != sorted(files):
            raise ValueError('MEMBER_SET')
        total = sum(e.file_size for e in entries)
        if total > MAX_BYTES or total != index['uncompressed_bytes']:
            raise ValueError('BYTE_BOUND')
        for e in entries:
            safe(e.filename)
            f = files[e.filename]
            if stat.S_IFMT(e.external_attr >> 16) != stat.S_IFREG or f['git_mode'] != '100644':
                raise ValueError('REGULAR_MEMBER_REQUIRED')
            raw = archive.read(e)
            if len(raw) != f['bytes'] or sha(raw) != f['sha256'] or blob(raw) != f['git_blob_sha1']:
                raise ValueError('ORIGINAL_BYTE_IDENTITY')
            result[e.filename] = raw
    return result


def verify(index_path):
    index_path = Path(index_path)
    if index_path.is_symlink() or any(p.is_symlink() for p in index_path.parents):
        raise ValueError('SYMLINK_REFUSED')
    if index_path.stat().st_size > MAX_BYTES:
        raise ValueError('INDEX_BOUND')
    raw = index_path.read_bytes()
    index = strict(raw)
    if index['bundle']['filename'] != 'HISTORICAL_EVIDENCE.zip':
        raise ValueError('TRANSPORT_PATH')
    archive = index_path.parent / index['bundle']['filename']
    if archive.is_symlink() or archive.stat().st_size > MAX_BYTES:
        raise ValueError('TRANSPORT_BOUND_OR_SYMLINK')
    return payloads(raw, archive.read_bytes())


def extract(index_path, destination):
    # Verify every member before making output; restore only into a new tree.
    content = verify(index_path)
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    if any(p.is_symlink() for p in destination.parents):
        raise ValueError('SYMLINK_REFUSED')
    destination.mkdir(parents=True)
    for name, raw in content.items():
        path = destination.joinpath(*safe(name).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    return len(content)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('index', type=Path)
    parser.add_argument('--extract', type=Path)
    args = parser.parse_args()
    count = extract(args.index, args.extract) if args.extract else len(verify(args.index))
    print(json.dumps({'verified_original_files': count, 'scope': 'LOSSLESS_HISTORICAL_TRANSPORT_NOT_NEW_QUALIFICATION'}))
