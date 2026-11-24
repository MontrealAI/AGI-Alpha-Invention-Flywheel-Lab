"""Exact JSON decision edition transport, with optional record-level reuse."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryFile

NAMES = ('atlas-release.json', 'atlas-ledger.json', 'member-value.json')
ROWS = {'atlas-ledger.json': 'records', 'member-value.json': 'briefs'}
LIMIT = 20_000_000
SCHEMA = 'frontier/decision-edition-delta-v1'


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode()


def exact_json(raw):
    value = json.loads(raw)
    if not isinstance(value, dict) or canonical(value) != raw:
        raise ValueError('Expected exact canonical object')
    return value


def digest(raw):
    return sha256(raw).hexdigest()


def anchor(files):
    return {name: digest(files[name]) for name in NAMES}


def documents(directory):
    if {p.name for p in directory.iterdir()} != set(NAMES):
        raise ValueError('Edition must contain exactly the three public evidence files')
    result = {}
    for name in NAMES:
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > LIMIT:
            raise ValueError('Invalid edition file')
        result[name] = path.read_bytes()
    return result


def by_id(rows):
    result = {row['id']: row for row in rows}
    if len(result) != len(rows) or not all(isinstance(key, str) and key for key in result):
        raise ValueError('Ambiguous record identity')
    return result


def pack(files, prior=None):
    if set(files) != set(NAMES):
        raise ValueError('Unexpected file set')
    changes = {}
    for name, raw in files.items():
        current = exact_json(raw)
        previous = exact_json(prior[name]) if prior is not None else {}
        slot = ROWS.get(name)
        rows = None
        if slot:
            now = by_id(current.pop(slot))
            before = by_id(previous.pop(slot, []))
            rows = [list(now), {key: row for key, row in now.items() if row != before.get(key)}]
        changes[name] = {
            'remove': sorted(previous.keys() - current.keys()),
            'set': {key: value for key, value in current.items() if key not in previous or previous[key] != value},
            'rows': rows,
        }
    return canonical({'schema': SCHEMA, 'prior': anchor(prior) if prior is not None else None,
                      'files': changes})


def restore(payload, expected, prior=None):
    frame = exact_json(payload)
    if (set(frame) != {'schema', 'prior', 'files'} or frame['schema'] != SCHEMA
            or set(frame['files']) != set(NAMES) or set(expected) != set(NAMES)
            or frame['prior'] != (anchor(prior) if prior is not None else None)):
        raise ValueError('Wrong format, file set or predecessor')
    output = {}
    for name, patch in frame['files'].items():
        previous = exact_json(prior[name]) if prior is not None else {}
        slot = ROWS.get(name)
        if set(patch) != {'remove', 'set', 'rows'} or not isinstance(patch['set'], dict):
            raise ValueError('Unexpected edit')
        for key in patch['remove']:
            if key in patch['set'] or key == slot:
                raise ValueError('Conflicting edit')
            del previous[key]
        if slot:
            if slot in patch['set']:
                raise ValueError('Conflicting record edit')
            order, updated = patch['rows']
            if len(order) != len(set(order)) or not set(updated).issubset(order):
                raise ValueError('Ambiguous record edit')
            rows = by_id(previous.pop(slot, [])) | by_id(updated.values())
            if any(key != row['id'] for key, row in updated.items()):
                raise ValueError('Mismatched record ID')
            previous[slot] = [rows[key] for key in order]
        elif patch['rows'] is not None:
            raise ValueError('Unexpected record edit')
        output[name] = canonical(previous | patch['set'])
    if anchor(output) != expected:
        raise ValueError('Reconstructed evidence does not match the independent digest anchor')
    return output


def zstd(raw, *arguments, limit=3 * LIMIT):
    """Bound decoded output before it can reach either comparator."""
    with TemporaryFile() as encoded:
        encoded.write(raw)
        encoded.seek(0)
        with subprocess.Popen(('zstd', '-q', '-c', *arguments), stdin=encoded,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
            output = process.stdout.read(limit + 1)
            if len(output) > limit:
                process.kill()
                raise ValueError('Decoded output exceeds evidence limit')
            if process.wait() != 0:
                raise ValueError('Zstandard rejected the payload')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    write = commands.add_parser('pack')
    write.add_argument('edition', type=Path)
    write.add_argument('output', type=Path)
    read = commands.add_parser('restore')
    read.add_argument('package', type=Path)
    read.add_argument('trusted_digests', type=Path)
    read.add_argument('output', type=Path)
    for subcommand in (write, read):
        subcommand.add_argument('--prior', type=Path)
    args = parser.parse_args()
    try:
        prior = documents(args.prior) if args.prior else None
        if args.command == 'pack':
            packed = zstd(pack(documents(args.edition), prior), '-5')
            with args.output.open('xb') as file:
                file.write(packed)
        else:
            if args.package.stat().st_size > 3 * LIMIT:
                raise ValueError('Oversized edition package')
            raw = zstd(args.package.read_bytes(), '-d')
            files = restore(raw, json.loads(args.trusted_digests.read_bytes()), prior)
            args.output.mkdir()
            for name, content in files.items():
                (args.output / name).write_bytes(content)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        parser.exit(2, f'{error}\n')


if __name__ == '__main__':
    main()
