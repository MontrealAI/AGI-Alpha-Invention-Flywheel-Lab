"""Restore exact frozen numerical evidence, refusing missing/corrupted pieces.

This is data integrity, not a physical or runtime qualification of an instrument.
Run from the separate public NASA array archive or pass its root explicitly.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()


def regular(root, name):
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts or relative.parts[0] != 'evidence':
        raise ValueError('DATA_PATH_SCOPE')
    path = root / relative
    if not path.is_file() or any(x.is_symlink() for x in (path, *path.parents)):
        raise ValueError('REGULAR_DATA_REQUIRED')
    return path


def assemble(root, output):
    root, output = Path(root).resolve(), Path(output).absolute()
    if output.exists() or any(x.is_symlink() for x in (output, *output.parents)):
        raise ValueError('FRESH_OUTPUT_REQUIRED')
    manifest = json.loads((root / 'NASA_ARRAY_PUBLICATION.json').read_text())
    output.mkdir(parents=True, exist_ok=False)
    (output / 'PENDING.json').write_text(json.dumps({'state': 'incomplete_until_REPORT'}) + '\n')
    results = []
    for item in manifest['files']:
        target = output / Path(item['path']).name
        pieces = sorted((x for x in manifest['parts'] if x['original_path'] == item['path']), key=lambda x: x['path'])
        if pieces:
            with target.open('xb') as stream:
                for part in pieces:
                    source = regular(root, part['path'])
                    if source.stat().st_size != part['bytes'] or digest(source) != part['sha256']:
                        raise ValueError('PART_IDENTITY_MISMATCH')
                    with source.open('rb') as fragment:
                        shutil.copyfileobj(fragment, stream, length=1024**2)
        else:
            source = regular(root, item['path'])
            if source.stat().st_size != item['bytes'] or digest(source) != item['sha256']:
                raise ValueError('WHOLE_FIELD_IDENTITY_MISMATCH')
            with target.open('xb') as stream, source.open('rb') as fragment:
                shutil.copyfileobj(fragment, stream, length=1024**2)
        if target.stat().st_size != item['bytes'] or digest(target) != item['sha256']:
            raise ValueError('RECONSTRUCTED_FIELD_IDENTITY_MISMATCH')
        results.append({'name': target.name, 'bytes': item['bytes'], 'sha256': item['sha256']})
    report = {'state': 'complete', 'files': results,
              'scope': 'Original frozen bytes only. No new measurement, physical uncertainty, technical advantage, profitable delivery or mission success.'}
    (output / 'REPORT.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = assemble(args.root, args.output)
    print(json.dumps({'state': result['state'], 'files': len(result['files'])}))
