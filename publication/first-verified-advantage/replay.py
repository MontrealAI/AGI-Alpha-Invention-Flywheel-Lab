"""Independently audit and compare exact historical Pages decision editions."""

import argparse
from hashlib import file_digest, sha256
from io import BytesIO
import json
from pathlib import Path
from resource import RUSAGE_CHILDREN, RUSAGE_SELF, getrusage
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
from time import perf_counter_ns
from zipfile import ZipFile

REGISTRATION = Path(__file__).with_name('INPUTS.json')
sys.path.insert(0, str(REGISTRATION.parents[2] / 'products/frontier-member-tools'))
import edition_delta as delta

FILES = ('atlas-ledger.json', 'atlas-release.json', 'member-value.json')
PREFIX = 'frontier-omega-alpha/'
MAX_FILE = 20_000_000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def independent_sha(data):
    return sha256(data).hexdigest()


def timed(fn, *values):
    start = perf_counter_ns()
    before = [getrusage(kind) for kind in (RUSAGE_SELF, RUSAGE_CHILDREN)]
    result = fn(*values)
    after = [getrusage(kind) for kind in (RUSAGE_SELF, RUSAGE_CHILDREN)]
    return result, {
        'wall_ns': perf_counter_ns() - start,
        'cpu_ns': round(sum(end.ru_utime - begin.ru_utime + end.ru_stime - begin.ru_stime
                            for begin, end in zip(before, after, strict=True)) * 1e9),
    }


def extract(tar, *, root=''):
    names = {root + name: name for name in FILES}
    accepted = {}
    for item in tar:
        path = item.name.removeprefix('./')
        if path not in names and root:
            continue
        require(path in names and path not in accepted and item.isfile()
                and 0 < item.size <= MAX_FILE, 'Unexpected or duplicated evidence file')
        data = tar.extractfile(item).read(MAX_FILE + 1)
        require(len(data) == item.size, 'Partial file')
        accepted[path] = data
    require(set(accepted) == set(names), 'Evidence is missing')
    return {names[path]: value for path, value in accepted.items()}


def reference(archive, contract):
    require(archive.stat().st_size == contract['archive_bytes'], 'Actions archive length mismatch')
    with archive.open('rb') as stream:
        require(file_digest(stream, 'sha256').hexdigest() == contract['archive_sha256'],
                'Actions archive hash mismatch')
    with ZipFile(archive) as zipped:
        require(zipped.namelist() == ['artifact.tar'], 'Unexpected official archive contents')
        with zipped.open('artifact.tar') as payload, tarfile.open(fileobj=payload, mode='r|*') as tar:
            result = extract(tar, root=PREFIX)
    validate(result, contract)
    return result


def validate(files, contract):
    require(set(files) == set(FILES), 'Wrong deliverable set')
    release = json.loads(files['atlas-release.json'])
    member = json.loads(files['member-value.json'])
    ledger = json.loads(files['atlas-ledger.json'])
    require(release['schema'] == 'frontier-omega-alpha/atlas-release-v1'
            and release['workflow_run'] == contract['run'] and release['source_commit'] == contract['source'],
            'Wrong published source or workflow')
    require(independent_sha(files['atlas-ledger.json']) == release['ledger_sha256'] == member['atlas_sha256']
            and independent_sha(files['member-value.json']) == release['member_value_sha256'],
            'Published catalogue digest mismatch')
    require(member['publication'] == 'public-file' and member['protected_member_first'] is None
            and member['member_lead_seconds'] is None and len(member['briefs']) == release['records']
            and len(ledger['records']) == release['records'], 'Unexpected privacy or inventory scope')
    require({brief['id'] for brief in member['briefs']} == {entry['id'] for entry in ledger['records']}
            and all(brief.get('en') and brief.get('fr') for brief in member['briefs']), 'Bilingual decision coverage mismatch')
    require({item['download']: item['sha256'] for item in member['capabilities'].values()}
            == release['public_capability_sha256'], 'Tool version binding mismatch')
    return release


def tar_bytes(files):
    data = BytesIO()
    with tarfile.open(fileobj=data, mode='w', format=tarfile.USTAR_FORMAT) as tar:
        for name in sorted(files):
            item = tarfile.TarInfo(name)
            item.mode = 0o644
            item.size = len(files[name])
            tar.addfile(item, BytesIO(files[name]))
    return data.getvalue()


def tar_restore(raw):
    with tarfile.open(fileobj=BytesIO(raw), mode='r:') as tar:
        return extract(tar)


def zstd_direct(raw, *args):
    # The conventional comparator invokes the vendor's normal CLI separately.
    if '-d' not in args and any(arg.startswith('--patch-from=') for arg in args):
        args = (*args, f'--stream-size={len(raw)}')
    return subprocess.run(('zstd', '-q', '-c', *args), input=raw, capture_output=True, check=True).stdout


def compare(files, original, contract):
    require(files == original, 'Recovered bytes differ from the official witness')
    return validate(files, contract)


def conventional(files, original, contract, base_tar=None):
    content, tar_cost = timed(tar_bytes, files)
    args = (f'--patch-from={base_tar}',) if base_tar is not None else ()
    package, prepare = timed(zstd_direct, content, '-5', *args)
    recovered, restore = timed(lambda: tar_restore(zstd_direct(package, '-d', *args)))
    _, check = timed(compare, recovered, original, contract)
    return package, {'prepare': add(tar_cost, prepare), 'recover': restore, 'verify': check, 'accepted': True}


def add(x, y):
    return {key: x[key] + y[key] for key in x}


def challenger(live, original, contract, base=None):
    # The eligibility/anchor comes from the independent official extraction.
    expected = {name: independent_sha(original[name]) for name in FILES}
    package, make = timed(lambda: delta.zstd(delta.pack(live, base), '-5'))
    recovered, restore = timed(lambda: delta.restore(delta.zstd(package, '-d'), expected, base))
    _, check = timed(compare, recovered, original, contract)
    return package, {'prepare': make, 'recover': restore, 'verify': check, 'accepted': True}


def controls(current, previous, contract, previous_contract, base_tar, full, candidate):
    expected = {name: independent_sha(current[name]) for name in FILES}
    raw = delta.zstd(candidate, '-d')
    spoof = dict(expected)
    spoof['atlas-release.json'] = independent_sha(previous['atlas-release.json'])
    original_tar = tar_bytes(current)
    cases = {
        'wrong_predecessor': lambda: delta.restore(raw, expected, current),
        'wrong_external_anchor': lambda: delta.restore(raw, spoof, previous),
        'absent_predecessor': lambda: delta.restore(raw, expected),
        'truncated_candidate': lambda: delta.restore(delta.zstd(candidate[:len(candidate) // 2], '-d'), expected, previous),
        'truncated_conventional': lambda: tar_restore(zstd_direct(full[:len(full) // 2], '-d')),
        'wrong_workflow_identity': lambda: validate(current, previous_contract),
        'different_edition_same_names': lambda: compare(previous, current, contract),
        'missing_file': lambda: tar_restore(tar_bytes({k: v for k, v in current.items() if k != FILES[0]})),
        'extra_mutable_file': lambda: tar_restore(tar_bytes(current | {'extra.json': b'{}'})),
        'spoofed_untrusted_source_hash': lambda: validate(current | {'atlas-release.json': json.dumps(
            json.loads(current['atlas-release.json']) | {'source_commit': 'a' * 40}).encode()}, contract),
        'malformed_tar': lambda: tar_restore(original_tar[:100]),
        'wrong_native_dictionary': lambda: zstd_direct(zstd_direct(original_tar, '-5',
            f'--patch-from={base_tar}'), '-d', f'--patch-from={base_tar.with_name("absent.tar")}'),
    }
    denied = []
    for name, execute in cases.items():
        try:
            execute()
        except (ValueError, KeyError, TypeError, OSError, tarfile.TarError, subprocess.SubprocessError):
            denied.append(name)
        else:
            raise ValueError(f'Unexpected success on control {name}')
    return denied


def execute(vault, output):
    registration = json.loads(REGISTRATION.read_bytes())
    inputs = registration['runs']
    check_dir = output / 'sealed'
    check_dir.mkdir(parents=True)
    shots = []
    all_files = []
    with TemporaryDirectory() as folder:
        base_tar = Path(folder) / 'registered-prior.tar'
        for index, contract in enumerate(inputs):
            run = contract['run']
            original, extraction = timed(reference, vault / f'{run}.zip', contract)
            all_files.append(original)
            baseline, baseline_cost = conventional(original, original, contract)
            factored, factored_cost = challenger(original, original, contract)
            arms = {'native_actions': {'bytes': contract['archive_bytes'], 'extract_and_verify': extraction,
                                      'accepted': True},
                    'conventional_cold': {'bytes': len(baseline), **baseline_cost},
                    'record_delta_cold': {'bytes': len(factored), **factored_cost}}
            (check_dir / f'{run}.tar.zst').write_bytes(baseline)
            if index == 0:
                _, predecessor_setup = timed(lambda: base_tar.write_bytes(tar_bytes(original)))
            else:
                old = all_files[0]
                warm, warm_cost = conventional(original, original, contract, base_tar)
                proposal, proposal_cost = challenger(original, original, contract, old)
                arms.update({'conventional_warm': {'bytes': len(warm), **warm_cost,
                                                    'predecessor_setup': predecessor_setup},
                             'record_delta_warm': {'bytes': len(proposal), **proposal_cost}})
                denied = controls(original, old, contract, inputs[0], base_tar, baseline, proposal)
            shots.append({'run': run, 'artifact': contract['artifact'], 'source': contract['source'],
                          'original_sha256': contract['archive_sha256'],
                          'files': {name: {'sha256': independent_sha(raw), 'bytes': len(raw)}
                                    for name, raw in original.items()},
                          'packaged_sha256': independent_sha(baseline),
                          'scope': {'records': validate(original, contract)['records']},
                          'arms': arms})
    return {'schema': 'frontier/public-edition-recovery-result-v1',
            'registration': registration['registration_commit'], 'cases': shots, 'denied_controls': denied}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('vault', type=Path)
    cli.add_argument('output', type=Path)
    parsed = cli.parse_args()
    print(json.dumps(execute(parsed.vault.resolve(), parsed.output.resolve()), indent=2, sort_keys=True))
