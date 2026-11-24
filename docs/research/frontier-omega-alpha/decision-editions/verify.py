"""Verify or recover an exact public edition using its separately pinned catalogue."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
import tarfile

FILES = {'atlas-release.json', 'atlas-ledger.json', 'member-value.json'}
SCHEMA = 'frontier/historical-public-editions-v1'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def matches(data, seal):
    return len(data) == seal['bytes'] and sha256(data).hexdigest() == seal['sha256']


def read_catalog(parent):
    index = parent / 'index.json'
    require(index.stat().st_size <= 64_000, 'Oversized catalogue')
    catalogue = json.loads(index.read_bytes())
    require(set(catalogue) == {'schema', 'editions'} and catalogue['schema'] == SCHEMA, 'Unexpected catalogue')
    entries = catalogue['editions']
    require(all(isinstance(entry['run'], str) and re.fullmatch('[1-9][0-9]{0,18}', entry['run'])
                for entry in entries), 'Invalid publication run')
    editions = {entry['run']: entry for entry in entries}
    require(editions and len(editions) == len(entries), 'Missing or ambiguous publication run')
    return editions


def verify(archive, entry):
    require(set(entry['files']) == FILES, 'Unexpected evidence file set')
    require(0 < entry['archive_bytes'] <= 20_000_000
            and archive.stat().st_size == entry['archive_bytes'], 'Unexpected archive length')
    with archive.open('rb') as package:
        digest = sha256(package.read()).hexdigest()
        require(digest == entry['archive_sha256'], 'Archive differs from the pinned digest')
        package.seek(0)
        byte_limit = sum(seal['bytes'] for seal in entry['files'].values()) + 32_768
        require(0 < byte_limit <= 61_000_000, 'Oversized evidence')
        with subprocess.Popen(('zstd', '-q', '-d', '-c', '-M128MB'), stdin=package, stdout=subprocess.PIPE) as decoder:
            decoded = decoder.stdout.read(byte_limit + 1)
            if len(decoded) > byte_limit:
                decoder.kill()
                raise ValueError('Oversized decompressed archive')
            require(decoder.wait() == 0, 'Invalid compressed archive')

    files = {}
    with tarfile.open(fileobj=BytesIO(decoded), mode='r:') as tar:
        for item in tar:
            require(item.name in FILES and item.name not in files and item.isfile(), 'Unexpected archive member')
            seal = entry['files'][item.name]
            require(item.size == seal['bytes'], 'File length differs from the pinned size')
            raw = tar.extractfile(item).read()
            require(matches(raw, seal), 'File differs from the pinned digest')
            files[item.name] = raw
    require(set(files) == FILES, 'Missing required evidence')
    release = json.loads(files['atlas-release.json'])
    ledger = json.loads(files['atlas-ledger.json'])
    member = json.loads(files['member-value.json'])
    require(release['workflow_run'] == entry['run'] and release['source_commit'] == entry['source'],
            'Receipt refers to a different release')
    require(release['ledger_sha256'] == entry['files']['atlas-ledger.json']['sha256'] == member['atlas_sha256']
            and release['member_value_sha256'] == entry['files']['member-value.json']['sha256'], 'Inconsistent receipt')
    require(entry['records'] == release['records'] == len(ledger['records']) == len(member['briefs'])
            and member['publication'] == 'public-file' and member['protected_member_first'] is None,
            'Unexpected evidence or publication scope')
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', help='Exact Pages run number, or all')
    parser.add_argument('--directory', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--output', type=Path, help='New folder for the three verified JSON files')
    args = parser.parse_args()
    if args.run == 'all' and args.output:
        parser.error('Choose one run when extracting an edition')
    try:
        editions = read_catalog(args.directory)
        runs = editions if args.run == 'all' else [args.run]
        for run in runs:
            entry = editions[run]
            files = verify(args.directory / f'{run}.tar.zst', entry)
            if args.output:
                args.output.mkdir()
                for name, raw in files.items():
                    (args.output / name).write_bytes(raw)
            print(json.dumps({'run': run, 'source': entry['source'], 'records': entry['records'],
                              'archive_sha256': entry['archive_sha256'], 'status': 'MATCHED_PINNED_EDITION'}))
    except (ValueError, KeyError, OSError, tarfile.TarError, TypeError) as error:
        parser.exit(2, f'ABSTAIN: {error}\n')


if __name__ == '__main__':
    main()
