import argparse
import collections
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile


def scan(parts):
    index = json.loads((parts / 'INDEX.json').read_text())
    for part in index['parts']:
        data = (parts / part['path']).read_bytes()
        if len(data) != part['bytes'] or hashlib.sha256(data).hexdigest() != part['sha256']:
            raise ValueError('ORIGINAL_ARCHIVE_PART_IDENTITY_MISMATCH')
    data = b''.join((parts / part['path']).read_bytes() for part in index['parts'])
    if len(data) != index['archive_bytes'] or hashlib.sha256(data).hexdigest() != index['archive_sha256']:
        raise ValueError('ORIGINAL_ARCHIVE_IDENTITY_MISMATCH')
    counts, rows = collections.Counter(), []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in archive.namelist():
            if not (name.startswith('worlds/') or name.startswith('prior-incomplete-confirmation001/worlds/')) or not name.endswith('.json.gz'):
                continue
            raw = archive.read(name)
            world = json.loads(gzip.decompress(raw))
            actions = world['ledger']['actions']
            cancellation_count = sum(event.get('op') == 'cancel_investment' for event in actions)
            kind = 'confirmation002' if name.startswith('worlds/') else 'incomplete_confirmation001'
            counts[kind + '_completed_worlds'] += 1
            counts[kind + '_actions'] += len(actions)
            counts[kind + '_cancellations'] += cancellation_count
            rows.append({'path': name, 'sha256': hashlib.sha256(raw).hexdigest(),
                         'actions_sha256': world['ledger']['actions_sha256'],
                         'native_actions': len(actions), 'cancel_investment_count': cancellation_count})
    return {'schema': 'agi-alpha/cancellation-retirement-historical-scan/v1',
            'scope': 'Original published native action inspection; not a new financial or operating replay',
            'archive_sha256': index['archive_sha256'], 'parts_sha256_verified': len(index['parts']),
            'counts': dict(counts), 'worlds': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--parts', type=Path, default=Path('artifacts/adaptive012-parts'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = scan(args.parts)
    rendered = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end='')
