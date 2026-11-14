"""Deterministic portable research build: unchanged offline governance 140+152+153.

Only public fixed allowlisted source; no customer data, credentials or native finance.
Digest anchors must be obtained from the separate build receipt, never from ZIP alone.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

SCHEMA = 'agi-alpha/governance-linked-portable158/v1'
SCOPE = 'OFFLINE_SYNTHETIC_RESEARCH_NO_AUTHORIZED_REVIEW_NO_BID'
FILES = (
    'campaign/public-demand140/PROTOCOL.md',
    'campaign/governance-native-reassessment153/PROTOCOL.md',
    'products/governance_impact140/README.md',
    'products/governance_impact140/__init__.py',
    'products/governance_impact140/engine.py',
    'products/governance_impact140/native_risk152.py',
    'products/governance_impact140/native_reassessment153.py',
    'tests/test_governance_impact140.py',
    'tests/test_governance_native_risk152.py',
    'tests/test_governance_native_reassessment153.py',
)
MANIFEST = 'MANIFEST.json'
MAX_FILE = 4_000_000
MAX_TOTAL = 20_000_000


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(data: object) -> bytes:
    return (json.dumps(data, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')


def require_hash(value):
    if type(value) is not str or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise ValueError('EXTERNAL_SHA256_ANCHOR_REQUIRED')
    return value


def require_commit(value):
    if type(value) is not str or not re.fullmatch(r'[0-9a-f]{40}', value):
        raise ValueError('SOURCE_COMMIT_REQUIRED')
    return value


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('DUPLICATE_JSON_FIELD')
        result[key] = value
    return result


def collect(root: Path):
    root = root.resolve(strict=True)
    data = {}
    for name in FILES:
        source = root / name
        resolved = source.resolve(strict=True)
        if not resolved.is_relative_to(root) or not source.is_file() or source.is_symlink():
            raise ValueError('SOURCE_OUTSIDE_ROOT_OR_SYMLINK')
        raw = source.read_bytes()
        if len(raw) > MAX_FILE:
            raise ValueError('SOURCE_FILE_TOO_LARGE')
        data[name] = raw
    return data


def build(root: Path, archive: Path, receipt: Path, source_commit: str):
    source_commit = require_commit(source_commit)
    data = collect(root)
    manifest = {'schema': SCHEMA, 'scope': SCOPE, 'source_commit': source_commit,
                'files': {name: sha(raw) for name, raw in sorted(data.items())}}
    data[MANIFEST] = canonical(manifest)
    if sum(map(len, data.values())) > MAX_TOTAL:
        raise ValueError('PACKAGE_TOO_LARGE')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9, allowZip64=False) as z:
        for name, raw in sorted(data.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            z.writestr(info, raw, compress_type=zipfile.ZIP_DEFLATED,
                       compresslevel=9)
    packed = buf.getvalue()
    if len(packed) > MAX_TOTAL:
        raise ValueError('ARCHIVE_TOO_LARGE')
    record = {'schema': SCHEMA, 'source_commit': source_commit,
              'archive_sha256': sha(packed), 'manifest_sha256': sha(data[MANIFEST]),
              'file_count': len(data), 'scope': SCOPE,
              'verdict': 'PUBLIC_SYNTHETIC_ENGINEERING_ONLY_NO_COMMERCIAL_OR_TRL_CLAIM'}
    archive.parent.mkdir(parents=True, exist_ok=True)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    # Fail closed for output name collisions; no modification of prior receipts.
    with archive.open('xb') as f:
        f.write(packed)
    with receipt.open('x', encoding='utf-8') as f:
        f.write(json.dumps(record, sort_keys=True, indent=2) + '\n')
    return record


def verify(archive: Path, *, expected_archive: str, expected_manifest: str,
           expected_commit: str, extract: Path | None = None):
    expected_archive = require_hash(expected_archive)
    expected_manifest = require_hash(expected_manifest)
    expected_commit = require_commit(expected_commit)
    packed = archive.read_bytes()
    if len(packed) > MAX_TOTAL or sha(packed) != expected_archive:
        raise ValueError('EXTERNAL_ARCHIVE_MISMATCH')
    entries = {}
    with zipfile.ZipFile(io.BytesIO(packed), 'r') as z:
        for info in z.infolist():
            name = info.filename
            path = PurePosixPath(name)
            if (not name or '\\' in name or path.is_absolute()
                    or '..' in path.parts or name.endswith('/')
                    or name != path.as_posix()):
                raise ValueError('UNSAFE_ARCHIVE_PATH')
            if name in entries:
                raise ValueError('DUPLICATE_ARCHIVE_MEMBER')
            if stat.S_IFMT(info.external_attr >> 16) != stat.S_IFREG:
                raise ValueError('NONREGULAR_ARCHIVE_MEMBER')
            if name not in set(FILES) | {MANIFEST}:
                raise ValueError('UNREGISTERED_ARCHIVE_MEMBER')
            if info.file_size > MAX_FILE:
                raise ValueError('ARCHIVE_FILE_TOO_LARGE')
            entries[name] = z.read(info)
    if set(entries) != set(FILES) | {MANIFEST}:
        raise ValueError('INCOMPLETE_ARCHIVE')
    if sum(map(len, entries.values())) > MAX_TOTAL:
        raise ValueError('ARCHIVE_TOO_LARGE')
    if sha(entries[MANIFEST]) != expected_manifest:
        raise ValueError('EXTERNAL_MANIFEST_MISMATCH')
    m = json.loads(entries[MANIFEST], object_pairs_hook=unique_json,
                   parse_constant=lambda x: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))
    if (type(m) is not dict or set(m) != {'schema','scope','source_commit','files'}
            or m['schema'] != SCHEMA or m['scope'] != SCOPE
            or m['source_commit'] != expected_commit
            or type(m['files']) is not dict or set(m['files']) != set(FILES)
            or canonical(m) != entries[MANIFEST]):
        raise ValueError('INVALID_SOURCE_MANIFEST')
    for name in FILES:
        if sha(entries[name]) != require_hash(m['files'][name]):
            raise ValueError('SOURCE_FILE_HASH_MISMATCH')
    if extract is not None:
        extract.mkdir(parents=True, exist_ok=False)
        for name, raw in entries.items():
            path = extract / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as f:
                f.write(raw)
    return {'accepted': True, 'source_commit': expected_commit,
            'archive_sha256': expected_archive, 'manifest_sha256': expected_manifest,
            'files': len(entries), 'scope': SCOPE}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    b = sub.add_parser('build')
    b.add_argument('--root', type=Path, required=True)
    b.add_argument('--archive', type=Path, required=True)
    b.add_argument('--receipt', type=Path, required=True)
    b.add_argument('--source-commit', required=True)
    v = sub.add_parser('verify')
    v.add_argument('--archive', type=Path, required=True)
    v.add_argument('--expected-archive', required=True)
    v.add_argument('--expected-manifest', required=True)
    v.add_argument('--expected-commit', required=True)
    v.add_argument('--extract', type=Path)
    args = parser.parse_args(argv)
    if args.action == 'build':
        result = build(args.root, args.archive, args.receipt, args.source_commit)
    else:
        result = verify(args.archive, expected_archive=args.expected_archive,
                        expected_manifest=args.expected_manifest,
                        expected_commit=args.expected_commit, extract=args.extract)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
