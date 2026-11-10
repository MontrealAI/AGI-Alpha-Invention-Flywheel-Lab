"""Compile only pinned public staged stdlib using the exact trusted native build."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import py_compile
import re
import sys

MAGIC = bytes.fromhex('520e0d0a')
CACHE_TAG = 'cpython-315'
EXCLUDED_DIRECTORIES = {'test', 'tests', 'idle_test', '__pycache__'}
UPSTREAM_EXCLUSION = re.compile(r'bad_coding|badsyntax|site-packages')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def selected(relative):
    path = Path(relative)
    return (path.suffix == '.py' and not any(part in EXCLUDED_DIRECTORIES for part in path.parts)
            and not UPSTREAM_EXCLUSION.search(path.as_posix()))


def check_header(data, source):
    if (data[:4] != MAGIC or len(data) < 16 or int.from_bytes(data[4:8], 'little') != 3
            or data[8:16] != importlib.util.source_hash(source)):
        raise ValueError('Invalid matching checked-hash bytecode header')


def source_files(original, staged):
    original, staged = Path(original).resolve(), Path(staged).resolve()
    if any(path.is_symlink() for path in staged.rglob('*')):
        raise ValueError('Symlink in dedicated staged stdlib')
    records = []
    for path in sorted(staged.rglob('*.py')):
        if path.is_symlink() or not path.is_file():
            raise ValueError('Nonregular staged stdlib source')
        relative = path.relative_to(staged)
        source = original / relative
        if (source.is_symlink() or not source.is_file()
                or source.resolve().relative_to(original) != relative
                or path.read_bytes() != source.read_bytes()):
            raise ValueError('Staged stdlib source differs from pinned public source')
        records.append((path, relative))
    if {relative for _, relative in records} != {path.relative_to(original) for path in original.rglob('*.py')}:
        raise ValueError('Staged stdlib source inventory differs')
    if not records:
        raise ValueError('Empty public stdlib')
    return records


def main(args):
    if (tuple(sys.version_info[:3]) != (3, 15, 2) or sys.implementation.cache_tag != CACHE_TAG
            or importlib.util.MAGIC_NUMBER != MAGIC or sys.flags.optimize != 0
            or not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode):
        raise ValueError('Exact isolated nonoptimized CPython3.15.2 build required')
    original, staged = args.source_lib.resolve(), args.staged_lib.resolve()
    if (original.name != 'Lib' or staged.parts[-3:] != ('python', 'lib', 'python3.15')
            or original == staged or original in staged.parents or staged in original.parents):
        raise ValueError('Dedicated public staging layout required')
    records = source_files(original, staged)
    if any(staged.rglob('*.pyc')):
        raise ValueError('Fresh staged stdlib already contains caches')
    manifest = {'schema': 'harness-wasi-checked-stdlib-cache/v1',
                'compiler': {'version': sys.version, 'executable_sha256': sha(sys.executable),
                             'cache_tag': CACHE_TAG, 'magic_hex': MAGIC.hex(), 'optimize': 0,
                             'invalidation_mode': 'CHECKED_HASH', 'header_flags': 3},
                'excluded_directory_names': sorted(EXCLUDED_DIRECTORIES),
                'upstream_exclusion_regex': UPSTREAM_EXCLUSION.pattern,
                'compiled': [], 'excluded': [], 'source_unchanged': False}
    before = {relative.as_posix(): sha(path) for path, relative in records}
    try:
        for path, relative in records:
            if not selected(relative):
                manifest['excluded'].append({'source': relative.as_posix(), 'source_sha256': sha(path)})
                continue
            target = Path(importlib.util.cache_from_source(str(path), optimization=''))
            if (target.parent != path.parent / '__pycache__' or target.suffix != '.pyc'
                    or not target.resolve().is_relative_to(staged)):
                raise ValueError('Cache output escaped selected stdlib directory')
            py_compile.compile(str(path), cfile=str(target),
                               dfile='/sandbox/python/lib/python3.15/' + relative.as_posix(),
                               doraise=True, optimize=0,
                               invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH)
            check_header(target.read_bytes(), path.read_bytes())
            manifest['compiled'].append({'source': relative.as_posix(), 'source_sha256': sha(path),
                                         'pyc': target.relative_to(staged).as_posix(),
                                         'pyc_sha256': sha(target), 'pyc_bytes': target.stat().st_size})
        manifest['source_unchanged'] = all(sha(staged / name) == digest for name, digest in before.items())
        if not manifest['source_unchanged']:
            raise ValueError('Public stdlib source changed during cache construction')
    finally:
        args.manifest.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'compiled': len(manifest['compiled']), 'excluded': len(manifest['excluded']),
                      'pyc_bytes': sum(row['pyc_bytes'] for row in manifest['compiled']),
                      'source_unchanged': manifest['source_unchanged']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-lib', type=Path, required=True)
    parser.add_argument('--staged-lib', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    main(parser.parse_args())
