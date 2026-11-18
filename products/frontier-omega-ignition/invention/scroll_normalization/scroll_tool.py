"""Offline CPU recipient for one-channel flat-ink robust normalization."""
import argparse
from array import array
import ctypes
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
ARMS = ('base', 'incumbent', 'candidate')
LIMIT = 50_000_000
UPSTREAM_SHA256 = '39f38f15544263ce8b26cdd6ab19321600c9da32efc10120eea502e5a4dc7713'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def compiled(arm, cache):
    """Compile an upstream or candidate operator into a trusted local cache."""
    if arm not in ARMS:
        raise ValueError('unknown operator')
    source = (ROOT / 'upstream.zip').read_bytes()
    if digest(source) != UPSTREAM_SHA256:
        raise ValueError('the pinned upstream source bundle has changed')
    compiler = shutil.which('c++')
    if not compiler:
        raise ValueError('a C++20 compiler is required')
    patch = (ROOT / 'candidate.patch').read_bytes()
    identity = digest(b'\0'.join([arm.encode(), source, patch, (ROOT/'operator.cpp').read_bytes(),
                                   subprocess.check_output([compiler, '--version']), platform.machine().encode()]))
    cache.mkdir(parents=True, exist_ok=True)
    receipt = cache / f'{arm}-{identity}.sha256'
    try:
        checksum = receipt.read_text().strip()
        if len(checksum) == 64 and all(c in '0123456789abcdef' for c in checksum):
            output = cache / f'{arm}-{identity}-{checksum}.so'
            if digest(output.read_bytes()) == checksum:
                return ctypes.CDLL(str(output))
    except (OSError, UnicodeError):
        pass
    # A missing, damaged or mismatched local binary is rebuilt from pinned source.
    with tempfile.TemporaryDirectory(dir=cache) as temp:
        build = Path(temp)
        prefix = ('incumbent' if arm == 'candidate' else arm) + '/'
        with zipfile.ZipFile(ROOT / 'upstream.zip') as archive:
            for item in archive.namelist():
                if item.startswith(prefix):
                    target = build / item.removeprefix(prefix)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(item))
        if arm == 'candidate':
            subprocess.run(['patch', '--batch', '-p1', '--input', str(ROOT/'candidate.patch')],
                           cwd=build, check=True, stdout=subprocess.DEVNULL)
        so = build / 'operator.so'
        subprocess.run([compiler, '-std=c++20', '-O2', '-ffp-contract=off', '-fPIC', '-shared',
                        '-I', str(build), str(ROOT/'operator.cpp'), '-o', str(so)], check=True)
        checksum = digest(so.read_bytes())
        output = cache / f'{arm}-{identity}-{checksum}.so'
        os.replace(so, output)
        pending = build / 'checksum'
        pending.write_text(checksum + '\n')
        os.replace(pending, receipt)
    return ctypes.CDLL(str(output))


def call(library, values, mask=None):
    scalar = ctypes.c_float if values.typecode == 'f' else ctypes.c_double
    op = library.normalize_float if values.typecode == 'f' else library.normalize_double
    op.argtypes = [ctypes.POINTER(scalar), ctypes.c_size_t, ctypes.POINTER(ctypes.c_uint8)]
    op.restype = ctypes.c_int
    flags = None
    if mask is not None:
        if len(mask) != len(values) or not any(mask):
            raise ValueError('expected a nonempty validity selection matching the input')
        flags = (ctypes.c_uint8 * len(mask)).from_buffer_copy(mask)
    view = (scalar * len(values)).from_buffer(values)
    if op(view, len(values), flags):
        raise ValueError('operator rejected the input')
    return values


def little_bytes(values):
    if sys.byteorder != 'little':
        values = array(values.typecode, values)
        values.byteswap()
    return values.tobytes()


def self_check(libraries):
    examples = [
        [0], [17] * 32, [0] * 65 + [1, 7, 254, 255] * 6,
        [64] * 42 + [0, 5, 64, 129, 255] * 4,
        list(range(256)) * 2, [-2.5, 3.5, 4., 6., 11.],
        [-0., 0., 1., 9., 16.], [255, 0] * 127 + [13],
    ]
    cases = 0
    for items, kind, masked in itertools.product(examples, ('f', 'd'), (False, True)):
        mask = bytes(int(i % 3 != 1) for i in range(len(items))) if masked else None
        answers = [little_bytes(call(lib, array(kind, items), mask)) for lib in libraries]
        if len(set(answers)) != 1:
            raise ValueError(f'byte disagreement in self-check case {cases + 1}')
        if min(items) == max(items) and any(answers[0]):
            raise ValueError('constant crops must produce zero')
        cases += 1
    return {'passed': True, 'cases': cases, 'comparators': list(ARMS)}


def run(args, cache):
    if args.command == 'prepare':
        for arm in ARMS:
            compiled(arm, cache)
        return {'prepared': list(ARMS)}
    if args.command == 'self-check':
        return self_check([compiled(arm, cache) for arm in ARMS])
    with args.input.open('rb') as stream:
        data = stream.read(LIMIT + 1)
    if not 0 < len(data) <= LIMIT:
        raise ValueError(f'input must contain between 1 and {LIMIT} unsigned bytes')
    values = array('f', memoryview(data))
    if args.command == 'normalize':
        result = little_bytes(call(compiled('candidate', cache), values))
        if args.output.exists() and args.output.samefile(args.input):
            raise ValueError('output must be separate from input')
        with tempfile.NamedTemporaryFile(dir=args.output.parent, delete=False) as stream:
            temp = Path(stream.name)
        try:
            temp.write_bytes(result)
            os.replace(temp, args.output)
        finally:
            temp.unlink(missing_ok=True)
        return {'voxels': len(data), 'output_sha256': digest(result)}
    hashes = {arm: digest(little_bytes(call(compiled(arm, cache), array('f', values)))) for arm in ARMS}
    if len(set(hashes.values())) != 1:
        raise ValueError('candidate and upstream outputs disagree')
    return {'passed': True, 'voxels': len(data), 'sha256': hashes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('prepare', 'self-check', 'normalize', 'verify'):
        command = commands.add_parser(name)
        command.add_argument('--cache', type=Path, required=name == 'prepare', help='trusted compiled-library cache')
        if name in ('normalize', 'verify'):
            command.add_argument('--input', type=Path, required=True, help='one-channel raw unsigned bytes')
        if name == 'normalize':
            command.add_argument('--output', type=Path, required=True, help='little-endian float32 output')
    args = parser.parse_args()
    try:
        if args.cache:
            result = run(args, args.cache.resolve())
        else:
            with tempfile.TemporaryDirectory() as cache:
                result = run(args, Path(cache))
        print(json.dumps(result, sort_keys=True))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
