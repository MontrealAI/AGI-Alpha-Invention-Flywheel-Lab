#!/usr/bin/env python3
"""Opt-in, key-free source-archive evidence compaction. Never deletes original paths."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import zipfile

MAX_FILES = 10000
MAX_BYTES = 512 * 1024 ** 2
SKIP = {'.git', '.venv', '__pycache__', '.pytest_cache'}
TRANSACTION_PREFIXES = ('.commercial010-package-', '.publication-')
SCHEMA = 'agi-alpha/source-archive-lossless-compaction/v1'


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def checked_path(value, prefix='evidence/'):
    if not isinstance(value, str) or not value.startswith(prefix) or '\\' in value or '\0' in value:
        raise ValueError('ONLY_EXPLICIT_EVIDENCE_PATHS_ALLOWED')
    p = Path(value)
    if p.is_absolute() or '..' in p.parts or p.as_posix() != value or len(p.parts) < 2:
        raise ValueError('NONCANONICAL_EVIDENCE_PATH')
    return value


def excluded(name):
    parts = Path(name).parts
    return (any(p in SKIP or p.startswith(TRANSACTION_PREFIXES) for p in parts)
            or parts[:2] in [('artifacts', 'enterprise011-parts'), ('artifacts', 'adaptive012-parts')]
            or name in {'artifacts/AGI_ALPHA_Enterprise_011_source_evidence.zip',
                        'artifacts/AGI_ALPHA_Adaptive_012_source_evidence.zip', 'ARCHIVE_MANIFEST.json'})


def tree(root, ref):
    commit = git(root, 'rev-parse', '--verify', ref + '^{commit}').decode().strip()
    data = git(root, 'ls-tree', '-rlz', commit)
    entries = {}
    for item in data.split(b'\0'):
        if not item:
            continue
        header, name = item.split(b'\t', 1)
        mode, typ, oid, size = header.decode().split()
        path = name.decode('utf-8', 'strict')
        if path in entries or typ != 'blob' or mode not in {'100644', '100755', '120000'}:
            raise ValueError('UNSUPPORTED_OR_DUPLICATE_GIT_TREE_ENTRY')
        entries[path] = {'mode': mode, 'git_blob_sha1': oid, 'bytes': int(size)}
    return commit, entries


def candidate(root, paths, ref, zip_path, index_path):
    commit, entries = tree(root, ref)
    if git(root, 'rev-parse', 'HEAD').decode().strip() != commit:
        raise ValueError('SOURCE_REFERENCE_MUST_MATCH_CURRENT_HEAD')
    if git(root, 'status', '--porcelain', '-z', '--untracked-files=all'):
        raise ValueError('CLEAN_COMMITTED_CHECKOUT_REQUIRED')
    proposed = {}
    for name in paths:
        checked_path(name)
        if name in proposed or name not in entries or excluded(name) or entries[name]['mode'] != '100644':
            raise ValueError('NONUNIQUE_UNTRACKED_OR_NONREGULAR_EVIDENCE')
        file = root / name
        if not file.is_file() or file.is_symlink() or any(p.is_symlink() for p in file.parents):
            raise ValueError('LOCAL_EVIDENCE_FILE_OR_PARENT_NOT_REGULAR')
        raw = file.read_bytes()
        if blob(raw) != entries[name]['git_blob_sha1'] or len(raw) != entries[name]['bytes']:
            raise ValueError('EVIDENCE_DIFFERS_FROM_IMMUTABLE_GIT_BLOB')
        proposed[name] = {'sha256': sha(raw), **entries[name]}
    if not proposed:
        raise ValueError('EXPLICIT_NONEMPTY_EVIDENCE_SELECTION_REQUIRED')
    for path in [zip_path, index_path]:
        checked_path(path)
        if any(parent.is_symlink() for parent in (root / path).parents):
            raise ValueError('BUNDLE_OUTPUT_SYMLINK_PARENT_REFUSED')
        if path in entries or path in proposed or (root / path).exists():
            raise ValueError('NEW_BUNDLE_PATH_MUST_BE_ABSENT')
    eligible = [r for p, r in entries.items() if not excluded(p)]
    count = len(eligible) - len(proposed) + 2
    # The ZIP and its index must be measured after construction, not estimated as free.
    if count > MAX_FILES:
        raise ValueError('INSUFFICIENT_ELIGIBLE_FILES_SELECTED_FOR_UNCHANGED_GUARD')
    return {'schema': SCHEMA, 'source_commit': commit, 'bundle': zip_path,
            'removal_performed': False, 'consumer_compatibility_qualified': False,
            'packed': dict(sorted(proposed.items())), 'index_path': index_path,
            'baseline_archive_files': len(eligible), 'archive_files_after_removal': count,
            'baseline_archive_bytes': sum(r['bytes'] for r in eligible)}


def build(root, proposal):
    archive = root / proposal['bundle']
    index_path = root / proposal['index_path']
    archive.parent.mkdir(parents=True, exist_ok=True)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as out:
            for name in proposal['packed']:
                raw = (root / name).read_bytes()
                item = proposal['packed'][name]
                if sha(raw) != item['sha256'] or blob(raw) != item['git_blob_sha1']:
                    raise ValueError('EVIDENCE_CHANGED_DURING_PACKAGING')
                zi = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                zi.compress_type = zipfile.ZIP_DEFLATED
                zi.external_attr = (stat.S_IFREG | 0o644) << 16
                out.writestr(zi, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        proposal['zip_sha256'] = sha(archive.read_bytes())
        proposal['zip_bytes'] = archive.stat().st_size
        data = (json.dumps(proposal, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
        with index_path.open('xb') as stream:
            stream.write(data)
        new_bytes = (proposal['baseline_archive_bytes'] - sum(v['bytes'] for v in proposal['packed'].values())
                     + proposal['zip_bytes'] + len(data))
        if new_bytes > MAX_BYTES:
            raise ValueError('UNCOMPRESSED_ARCHIVE_LIMIT_STILL_EXCEEDED')
        verify(root, index_path)
        proposal['archive_bytes_after_removal'] = new_bytes
        return proposal
    except BaseException:
        index_path.unlink(missing_ok=True)
        archive.unlink(missing_ok=True)
        raise


def unique_object(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError('DUPLICATE_BUNDLE_MANIFEST_FIELD')
        result[k] = v
    return result


def verify(root, index_path):
    raw = index_path.read_bytes()
    manifest = json.loads(raw, object_pairs_hook=unique_object)
    if manifest.get('schema') != SCHEMA or not isinstance(manifest.get('packed'), dict):
        raise ValueError('WRONG_LOSSLESS_BUNDLE_SCHEMA')
    checked_path(manifest['bundle'])
    if (root / manifest['index_path']).resolve() != index_path.resolve():
        raise ValueError('BUNDLE_INDEX_LOCATION_CHANGED')
    if index_path.is_symlink() or any(parent.is_symlink() for parent in index_path.parents):
        raise ValueError('BUNDLE_INDEX_SYMLINK_REFUSED')
    archive = root / manifest['bundle']
    if archive.is_symlink() or any(p.is_symlink() for p in archive.parents):
        raise ValueError('BUNDLE_SYMLINK_REFUSED')
    if archive.stat().st_size != manifest['zip_bytes'] or sha(archive.read_bytes()) != manifest['zip_sha256']:
        raise ValueError('LOSSLESS_BUNDLE_ARCHIVE_CHANGED')
    if (len(manifest['packed']) > MAX_FILES or sum(v['bytes'] for v in manifest['packed'].values()) > MAX_BYTES
            or manifest['archive_files_after_removal'] > MAX_FILES):
        raise ValueError('LOSSLESS_BUNDLE_RESOURCE_BOUND')
    with zipfile.ZipFile(archive) as bundle:
        info = bundle.infolist()
        if [item.filename for item in info] != sorted(manifest['packed']):
            raise ValueError('LOSSLESS_BUNDLE_MEMBER_SET_OR_ORDER_CHANGED')
        for item in info:
            checked_path(item.filename)
            record = manifest['packed'][item.filename]
            if item.is_dir() or not stat.S_ISREG(item.external_attr >> 16):
                raise ValueError('NONREGULAR_BUNDLE_MEMBER')
            contents = bundle.read(item)
            if (len(contents) != record['bytes'] or sha(contents) != record['sha256']
                    or blob(contents) != record['git_blob_sha1'] or record['mode'] != '100644'):
                raise ValueError('LOSSLESS_BUNDLE_MEMBER_CHANGED')
    commit, original = tree(root, manifest['source_commit'])
    if commit != manifest['source_commit']:
        raise ValueError('SOURCE_COMMIT_CHANGED')
    for name, rec in manifest['packed'].items():
        if name not in original or original[name] != {k: rec[k] for k in ['mode', 'git_blob_sha1', 'bytes']}:
            raise ValueError('ORIGINAL_GIT_BLOB_NOT_ADDRESSABLE')
    return {'verified': True, 'packed': len(manifest['packed']), 'source_commit': commit,
            'archive_files_after_removal': manifest['archive_files_after_removal'],
            'zip_sha256': manifest['zip_sha256']}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('plan', 'build', 'verify'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--paths-file', type=Path)
    parser.add_argument('--bundle', default='evidence/P0_ARCHIVE_EVIDENCE_BUNDLE.zip')
    parser.add_argument('--index', default='evidence/P0_ARCHIVE_EVIDENCE_BUNDLE.json')
    parser.add_argument('--ref', default='HEAD')
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.mode == 'verify':
        result = verify(root, root / checked_path(args.index))
    else:
        if not args.paths_file or not args.paths_file.is_file():
            parser.error('paths-file is mandatory for plan/build')
        paths = [p for p in args.paths_file.read_text().splitlines() if p]
        result = candidate(root, paths, args.ref, args.bundle, args.index)
        if args.mode == 'build':
            result = build(root, result)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
