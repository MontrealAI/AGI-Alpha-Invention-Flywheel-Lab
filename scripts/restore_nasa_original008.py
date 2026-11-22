"""Restore all 47 exact original NASA input artifacts before repair replay.

Primary data are size/hash checked. Only deterministic ct/profile arrays are
regenerated with the unchanged public intake; historical receipts are copied as
frozen inputs, while the new intake's stdout/stderr remain separately labeled.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

EXPECTED = '60a275fcf18a4a01e44fed5ac12c6260052125bdc214eaa64f4818ee549b9033'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def restore(source, archive, ct, profile, output):
    source, archive, output = Path(source).resolve(), Path(archive).resolve(), Path(output).absolute()
    if output.exists() or any(x.is_symlink() for x in (output, *output.parents)):
        raise ValueError('FRESH_OUTPUT_REQUIRED')
    if sha(source / 'MANIFEST.json') != EXPECTED:
        raise ValueError('FROZEN_ORIGINAL_MANIFEST_REQUIRED')
    manifest = json.loads((source / 'MANIFEST.json').read_text())
    files = {x['path']: x for x in manifest['files']}
    inputs = {'TTT_AM_315400_low_res.tif': Path(ct), 'TTT_AM_315400_profilometry.zip': Path(profile)}
    for name, path in inputs.items():
        if not path.is_file() or path.is_symlink() or path.stat().st_size != files[name]['bytes'] or sha(path) != files[name]['sha256']:
            raise ValueError('PRIMARY_DATA_IDENTITY')
    if sha(source / 'intake.py') != files['intake.py']['sha256']:
        raise ValueError('INTAKE_SOURCE_IDENTITY')
    support = json.loads((archive / 'NASA_ORIGINAL_SUPPORT.json').read_text())
    locations = {x['original_name']: archive / x['path'] for x in support['files']}
    fields = json.loads((archive / 'NASA_ARRAY_PUBLICATION.json').read_text())
    locations.update({Path(x['path']).name: archive / x['path'] for x in fields['files'] if not any(p['original_path'] == x['path'] for p in fields['parts'])})
    output.mkdir(parents=True, exist_ok=False)
    old = output / 'original47'
    old.mkdir()
    for name, path in inputs.items():
        shutil.copyfile(path, old / name)
    shutil.copyfile(source / 'intake.py', old / 'intake.py')
    with (output / 'new-intake.stdout.log').open('xb') as stdout, (output / 'new-intake.stderr.log').open('xb') as stderr:
        subprocess.run([sys.executable, str(old / 'intake.py')], cwd=old, stdout=stdout, stderr=stderr, check=True, timeout=180)
    # Copy historical source/reports only after new decode; never relabel them new.
    for name, item in files.items():
        if name in ('ct.npy', 'profile.npy'):
            path = old / name
        else:
            origin = source / name if (source / name).is_file() else locations.get(name, inputs.get(name))
            if origin is None or not origin.is_file() or sha(origin) != item['sha256']:
                raise ValueError('MISSING_OR_CHANGED_ORIGINAL ' + name)
            path = old / name
            shutil.copyfile(origin, path)
        if path.stat().st_size != item['bytes'] or sha(path) != item['sha256']:
            raise ValueError('RESTORED_ORIGINAL_MISMATCH ' + name)
    shutil.copyfile(source / 'MANIFEST.json', old / 'MANIFEST.json')
    report = {'original_manifest_sha256': EXPECTED, 'restored_original_files': len(files), 'all_original_hashes_match': True,
              'historical_receipts_are_inputs_not_new_execution_receipts': True,
              'new_decode_logs': ['new-intake.stdout.log', 'new-intake.stderr.log'],
              'scope': 'Exact prerequisite restoration only; actual repair and separate verification remain required.'}
    (output / 'REPORT.json').write_text(json.dumps(report, indent=2) + '\n')
    return old


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True)
    p.add_argument('--archive', required=True)
    p.add_argument('--ct', required=True)
    p.add_argument('--profile', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    print(restore(a.source, a.archive, a.ct, a.profile, a.output))
