"""Fresh independent F03 probes; no existing account/private authority is copied."""
from pathlib import Path, PurePosixPath
import argparse
import stat
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', required=True, type=Path,
                    help='Exact trusted source root to snapshot and execute')
parser.add_argument('--output', required=True, type=Path,
                    help='New output directory; contains private synthetic account authority')
args = parser.parse_args()
INPUT_SOURCE = args.source.absolute()
OUTPUT = args.output.absolute()
for candidate in (INPUT_SOURCE, OUTPUT):
    if any(p.is_symlink() for p in (candidate, *candidate.parents)):
        raise ValueError('UNSYMLINKED_CHALLENGE_PATH_REQUIRED')
if not INPUT_SOURCE.is_dir():
    raise ValueError('TRUSTED_SOURCE_DIRECTORY_REQUIRED')
if OUTPUT.exists():
    raise ValueError('NEW_CHALLENGE_OUTPUT_REQUIRED')
query = "from connected_enterprise.finance import source_paths_for_manifest; import json; print(json.dumps(source_paths_for_manifest({'schema':'genesis-commitment001/native-services/v1'})))"
closure = subprocess.run([sys.executable, '-c', query], cwd=INPUT_SOURCE,
                         check=True, text=True, capture_output=True,
                         env={**os.environ, 'PYTHONPATH': str(INPUT_SOURCE),
                              'PYTHONDONTWRITEBYTECODE': '1'})
names = sorted(set(json.loads(closure.stdout)))
SOURCE = OUTPUT/'source'
OUTPUT.mkdir(exist_ok=False)
source_hashes = {}
for name in names:
    relative = PurePosixPath(name)
    if (relative.is_absolute() or '..' in relative.parts
            or str(relative) != name or '\\' in name):
        raise ValueError('SAFE_RUNTIME_SOURCE_PATH_REQUIRED')
    original = INPUT_SOURCE/name
    if not original.is_file() or any(p.is_symlink() for p in (original, *original.parents)):
        raise ValueError('REGULAR_RUNTIME_SOURCE_FILE_REQUIRED')
    raw = original.read_bytes()
    target = SOURCE/name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    source_hashes[name] = hashlib.sha256(raw).hexdigest()
(OUTPUT/'SOURCE.json').write_text(json.dumps(source_hashes, indent=2)+'\n')
sys.path.insert(0, str(SOURCE))
from campaign.genesis_commitment001 import service
from commercial.ledger import canonical


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value)+b'\n')


def call(*arguments):
    return subprocess.run([sys.executable, '-m', 'campaign.genesis_commitment001.runner',
                           *map(str, arguments)], cwd=SOURCE, text=True,
                          capture_output=True, env={**os.environ,
                          'PYTHONPATH': str(SOURCE), 'PYTHONDONTWRITEBYTECODE': '1'})


def public_copy(original, destination):
    destination.mkdir()
    for path in original.iterdir():
        if path.name == 'private':
            continue
        if path.is_dir():
            shutil.copytree(path, destination/path.name,
                            ignore=shutil.ignore_patterns('__pycache__'))
        else:
            shutil.copyfile(path, destination/path.name)


def finances(output):
    return {name: hashlib.sha256((output/name).read_bytes()).hexdigest()
            for name in ('NATIVE_EXPORT.json', 'REPORT.json', 'EXECUTION.json',
                         'REGISTRATION.json', 'MANIFEST.json')}


def expect(output, rejected, name):
    before = finances(output)
    audit = call('audit', '--output', output)
    archive = OUTPUT/(name+'.zip')
    package = call('package', '--output', output, '--archive', archive)
    row = {'case': name, 'expect_rejection': rejected,
           'audit_exit': audit.returncode, 'package_exit': package.returncode,
           'financial_records_unchanged': finances(output) == before}
    row['passed'] = (bool(audit.returncode) == rejected
                     and bool(package.returncode) == rejected
                     and row['financial_records_unchanged'])
    if rejected:
        row['no_archive_created'] = not archive.exists()
        row['passed'] &= row['no_archive_created']
        row['audit_error'] = audit.stderr.splitlines()[-1] if audit.stderr else None
    else:
        extracted = OUTPUT/(name+'-extracted')
        with zipfile.ZipFile(archive) as z:
            members = z.infolist()
            names = [item.filename for item in members]
            if len(names) != len(set(names)) or sum(item.file_size for item in members) > 256_000_000:
                raise ValueError('UNIQUE_BOUNDED_CHALLENGE_ARCHIVE_REQUIRED')
            for item in members:
                path = PurePosixPath(item.filename)
                if (not item.filename or path.is_absolute() or '..' in path.parts
                        or str(path) != item.filename or '\\' in item.filename
                        or stat.S_ISLNK(item.external_attr >> 16)):
                    raise ValueError('UNSAFE_CHALLENGE_ARCHIVE_MEMBER')
            if z.testzip() is not None:
                raise ValueError('CHALLENGE_ARCHIVE_CRC_FAILURE')
            if any('private' in Path(p).parts or p.endswith('.adaptive-simulation-key')
                   for p in z.namelist()):
                raise AssertionError('Private archive member')
            z.extractall(extracted)
        result = subprocess.run([sys.executable, '-m', 'campaign.genesis_commitment001.runner',
                                 'audit', '--output', str(extracted)], cwd=extracted/'source',
                                text=True, capture_output=True, env={**os.environ,
                                'PYTHONPATH': str(extracted/'source'),
                                'PYTHONDONTWRITEBYTECODE': '1'})
        row['extracted_audit_exit'] = result.returncode
        row['passed'] &= result.returncode == 0
    return row


started = time.monotonic()
fixtures = {}
fixture_cases = [('favorable_envelope', arm) for arm in ('retained', 'direct')]
fixture_cases += [(s, 'retained') for s in ('central', 'bad_output', 'shared_shock', 'cost_stress')]
for scenario, arm in fixture_cases:
    out = OUTPUT/('original-'+scenario+'-'+arm)
    result = call('run', '--output', out, '--scenario', scenario, '--arm', arm)
    if result.returncode:
        raise RuntimeError(result.stderr)
    fixtures[(scenario, arm)] = out

rows = []
for (scenario, arm), original in fixtures.items():
    name = 'honest-'+scenario+'-'+arm
    output = OUTPUT/name
    public_copy(original, output)
    rows.append(expect(output, False, name))


def probe(name, scenario, mutate, arm='retained'):
    out = OUTPUT/name
    public_copy(fixtures[(scenario, arm)], out)
    mutate(out)
    rows.append(expect(out, True, name))


def change_json(out, name, key, value):
    data = read(out/name)
    data[key] = value
    save(out/name, data)


for arm in ('retained', 'direct'):
    for stage in ('FIRST', 'SUCCESSOR'):
        probe('bool-alias-'+arm+'-'+stage, 'favorable_envelope',
              lambda out, stage=stage: change_json(out, stage+'_ACCEPTANCE.json', 'accepted', 1), arm)
        probe('wrong-method-'+arm+'-'+stage, 'favorable_envelope',
              lambda out, stage=stage, arm=arm: change_json(out, stage+'_ARTIFACT.json', 'method',
                                                         'direct' if arm == 'retained' else 'retained'), arm)
probe('negative-bool-alias', 'bad_output',
      lambda out: change_json(out, 'FIRST_ACCEPTANCE.json', 'accepted', 0))
probe('shared-shock-wrong-method', 'shared_shock',
      lambda out: change_json(out, 'FIRST_ARTIFACT.json', 'method', 'direct'))
probe('bad-output-wrong-method', 'bad_output',
      lambda out: change_json(out, 'FIRST_ARTIFACT.json', 'method', 'direct'))


def coherent_negative(out, alteration):
    artifact = read(out/'FIRST_ARTIFACT.json')
    if alteration == 'cause':
        artifact['request_id'] = 'FRESH-F03-DIFFERENT-REJECTION'
    elif alteration == 'database':
        raw = b'FRESH-F03-NOT-A-SQLITE-DATABASE'*25
        artifact['output_database_b64'] = base64.b64encode(raw).decode('ascii')
        artifact['output_sha256'] = hashlib.sha256(raw).hexdigest()
    else:
        raise AssertionError(alteration)
    manifest = read(out/'MANIFEST.json')
    save(out/'FIRST_ARTIFACT.json', artifact)
    save(out/'source'/service.DELIVERIES/'restore-first.json', artifact)
    save(out/'FIRST_ACCEPTANCE.json', service.verify_delivery(out/'source', manifest,
                                                             'restore-first', artifact))


probe('negative-cause-coherently-replaced', 'bad_output',
      lambda out: coherent_negative(out, 'cause'))
probe('negative-database-coherently-corrupted', 'bad_output',
      lambda out: coherent_negative(out, 'database'))
probe('shared-shock-undelivered-corrupted-production', 'shared_shock',
      lambda out: change_json(out, 'FIRST_ARTIFACT.json', 'output_sha256', '0'*64))


def inject(out, stage, kind):
    original = fixtures[('favorable_envelope', 'retained')]
    if kind in ('ARTIFACT', 'ACCEPTANCE'):
        shutil.copyfile(original/(stage+'_'+kind+'.json'), out/(stage+'_'+kind+'.json'))
    else:
        job = 'restore-first' if stage == 'FIRST' else 'migration-next'
        dest = out/'source'/service.DELIVERIES/(job+'.json')
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original/'source'/service.DELIVERIES/(job+'.json'), dest)


for scenario, stages in [('central', ('FIRST', 'SUCCESSOR')),
                         ('cost_stress', ('SUCCESSOR',)),
                         ('bad_output', ('SUCCESSOR',))]:
    for stage in stages:
        for kind in ('ARTIFACT', 'ACCEPTANCE', 'SOURCE'):
            probe('unexpected-'+scenario+'-'+stage+'-'+kind, scenario,
                  lambda out, stage=stage, kind=kind: inject(out, stage, kind))
for kind in ('ACCEPTANCE', 'SOURCE'):
    probe('undelivered-shared-shock-'+kind, 'shared_shock',
          lambda out, kind=kind: inject(out, 'FIRST', kind))

result = {'id': 'F03-FRESH-CHALLENGE', 'scope': 'Independent fresh disposable synthetic fixtures; no native ledger forgery or private-authority copying.',
          'source_hashes': read(OUTPUT/'SOURCE.json'),
          'challenge_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'runtime_source_count': len(source_hashes), 'fresh_accounts': len(fixtures),
          'honest_cases': sum(not row['expect_rejection'] for row in rows),
          'prospective_mutations': sum(row['expect_rejection'] for row in rows),
          'total': len(rows), 'passed': sum(row['passed'] for row in rows),
          'wall_seconds': round(time.monotonic()-started, 3), 'rows': rows}
save(OUTPUT/'FRESH_CHALLENGE.json', result)
print(json.dumps({'total': result['total'], 'passed': result['passed'],
                  'honest_cases': result['honest_cases'],
                  'prospective_mutations': result['prospective_mutations'],
                  'failures': [row for row in rows if not row['passed']]}, indent=2))
raise SystemExit(0 if result['passed'] == result['total'] else 1)
