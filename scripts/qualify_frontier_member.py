"""Exercise the distributed bundles in temporary independent installations."""

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter_ns
from zipfile import ZipFile

import frontier_member_value as member


def require(ok, message):
    if not ok:
        raise ValueError(message)


def install(path, destination, expected):
    require(member.digest(path.read_bytes()) == expected['sha256'], 'Published package digest mismatch')
    with ZipFile(path) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        require(set(archive.namelist()) == {'manifest.json', *manifest['file_sha256']}
                and len(archive.namelist()) == len(manifest['file_sha256']) + 1, 'Unexpected package member')
        for name, fingerprint in manifest['file_sha256'].items():
            binding = PurePosixPath(name)
            require(not binding.is_absolute() and '..' not in binding.parts, 'Unsafe package path')
            data = archive.read(name)
            require(member.digest(data) == fingerprint, 'Package file digest mismatch')
            target = destination.joinpath(*binding.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    return manifest


def call(directory, *command, expected=0):
    start = perf_counter_ns()
    result = subprocess.run(command, cwd=directory, capture_output=True, check=False)
    elapsed = perf_counter_ns() - start
    require(result.returncode == expected, f'{command[0]} {command[1]} exit {result.returncode}: {result.stderr[:500].decode(errors="replace")}')
    return (json.loads(result.stdout) if result.stdout.strip() else None), elapsed


def qualify_endpoint(package, root, expected, reference):
    install(package, root, expected)
    sample = json.loads((root / 'sample.json').read_bytes())
    require(member.digest(member.stable(sample)) == reference['input_sha256'], 'Public benchmark fixture changed')
    strict = {**sample, 'maximum_p90_ttft_ms': '100'}
    floor = {**sample, 'minimum_tokens_per_s': '500'}
    altered = deepcopy(sample)
    altered['rows'][3]['published'] = '2026-11-24'
    altered['rows'][2]['p90_ttft_ms'] = None
    altered['rows'][1]['published'] = None
    measured = []
    for name, batch, wanted in (('registered', sample, 140), ('new-ceiling', strict, 35),
                                 ('infeasible', floor, None), ('withheld', altered, 17)):
        path = root / 'run.json'
        path.write_bytes(member.stable(batch))
        candidate, js_ns = call(root, 'node', 'endpoint-cli.mjs', path)
        independent, sql_ns = call(root, sys.executable, 'endpoint-sqlite.py', path)
        require(candidate == independent and candidate['highest_tested_load'] == wanted, 'Exact SQLite comparison failed')
        require(candidate['operating_adoption'] == 'ABSTAIN', 'Benchmark promoted to operating authority')
        if name == 'registered':
            require(member.digest(member.stable(independent)) == reference['result_sha256'], 'Independent result digest mismatch')
        measured.append({'case': name, 'documented_load': wanted, 'node_wall_ns': js_ns, 'sqlite_wall_ns': sql_ns})
    broken = deepcopy(sample)
    broken['rows'][3]['load'] = broken['rows'][2]['load']
    path.write_bytes(member.stable(broken))
    call(root, 'node', 'endpoint-cli.mjs', path, expected=2)
    broken['rows'][3]['load'] = sample['rows'][3]['load']
    broken['minimum_tokens_per_s'] = '1e2'
    path.write_bytes(member.stable(broken))
    call(root, 'node', 'endpoint-cli.mjs', path, expected=2)
    return {'comparisons': measured, 'denied_inputs': 2, 'full_cost': None, 'test_case': 'controlled-public'}


def qualify_archive(package, root, expected, live):
    install(package, root, expected)
    audit, wall = call(root, sys.executable, 'archive-verify.py')
    require(audit['signature_verified'] and audit['registered_cases'] == 6
            and audit['direct_origin_budget_cases'] == 6, 'Signed archive reference was not recovered')
    original = root / member.ARCHIVE_PATH / 'evidence/standalone-query.json'
    known, _ = call(root, sys.executable, 'archive-verify.py', original)
    require(known['state'] == 'MATCHED_SIGNED_REFERENCE', 'Prior real query fails separate verification')
    sample = json.loads(original.read_bytes())
    sample['field']['temperature_k'] += 1
    changed = root / 'changed.json'
    changed.write_bytes(member.stable(sample))
    failed, _ = call(root, sys.executable, 'archive-verify.py', changed, expected=2)
    require(failed['state'] == 'REJECTED', 'Tampered measurement was accepted')
    sample['case']['latitude'] = 46.76
    changed.write_bytes(member.stable(sample))
    missing, _ = call(root, sys.executable, 'archive-verify.py', changed, expected=2)
    require(missing['state'] == 'ABSTAIN', 'Unknown case was accepted')
    actual = []
    if live:
        for day, cycle, lat, lon in (('2024-01-18', '00', '46.75', '-71.25'),
                                     ('2025-06-06', '12', '43.75', '-79.5')):
            point, elapsed = call(root, sys.executable, 'archive-query.py', '--day', day,
                                  '--cycle', cycle, '--latitude', lat, '--longitude', lon)
            output = root / 'point.json'
            output.write_bytes(member.stable(point))
            result, _ = call(root, sys.executable, 'archive-verify.py', output)
            require(result['state'] == 'MATCHED_SIGNED_REFERENCE', 'New public query did not match reference')
            actual.append({'day': day, 'cycle': cycle, 'latitude': lat, 'longitude': lon, 'wall_ns': elapsed,
                           'temperature_k': point['field']['temperature_k'], 'body_bytes': point['body_bytes']})
    return {'offline_audit_wall_ns': wall, 'signed_case_count': audit['registered_cases'], 'denied_inputs': 2,
            'live_queries': actual, 'full_cost': None, 'test_case': 'controlled-public'}


def qualify_foundry(directory, root, release):
    expected = release['foundry_sha256'][member.FOUNDRY_ZIP]
    install(directory / member.FOUNDRY_ZIP, root, {'sha256': expected})
    example = json.loads((root / 'example.json').read_bytes())
    demo, wall_ns = call(root, 'node', 'foundry-cli.mjs', 'demo')
    require(demo['summary']['matched'] == demo['summary']['total'] == 6
            and demo['result'] == {'bytes':327680,'ordered':True}, 'Public archive replay changed')
    retained, _ = call(root, 'node', 'foundry-cli.mjs', 'recheck', 'retained/noaa-window.json', 'retained/noaa-cases.json')
    reused, _ = call(root, 'node', 'foundry-cli.mjs', 'run', 'retained/noaa-window.json', 'retained/noaa-cases.json',
                     'retained/noaa-reuse-input.json')
    require(retained['summary']['matched'] == 14 and reused == {'bytes':32,'ordered':True},
            'The packaged reference model candidate failed reproducible verification')
    subprocess.run([sys.executable,'-c', "import json; from formulas import formula_candidate; "
                    "a=json.load(open('example.json')); "
                    "d=formula_candidate(a['task'],'bytes = end - start + 1\\nordered = start <= end'); "
                    "assert d['outputs'] == a['candidate']['outputs']"], cwd=root, check=True)
    for name, value in (('task', 'task'), ('draft','candidate'), ('cases','suite'), ('input','sample')):
        (root / f'{name}.json').write_bytes(member.stable(example[value]))
    sealed, _ = call(root, 'node', 'foundry-cli.mjs', 'retain', 'task.json', 'draft.json', 'cases.json')
    (root / 'asset.json').write_bytes(member.stable(sealed))
    original, _ = call(root, 'node', 'foundry-cli.mjs', 'recheck', 'asset.json', 'cases.json')
    recalc, reuse_ns = call(root, 'node', 'foundry-cli.mjs', 'run', 'asset.json', 'cases.json', 'input.json')
    require(original['summary']['matched'] == 6 and recalc == demo['result'], 'Retained instrument could not be reused')
    modified = deepcopy(sealed)
    modified['asset']['candidate']['outputs']['bytes'] = 1
    (root / 'altered.json').write_bytes(member.stable(modified))
    call(root, 'node', 'foundry-cli.mjs', 'recheck', 'altered.json', 'cases.json', expected=2)
    modified['asset']['candidate_sha256'] = member.digest(member.stable(modified['asset']['candidate']))
    modified['sha256'] = member.digest(member.stable(modified['asset']))
    (root / 'altered.json').write_bytes(member.stable(modified))
    call(root, 'node', 'foundry-cli.mjs', 'recheck', 'altered.json', 'cases.json', expected=2)
    wrong = deepcopy(example['suite'])
    wrong['cases'][0]['expected']['bytes'] = 17
    (root / 'other-cases.json').write_bytes(member.stable(wrong))
    call(root, 'node', 'foundry-cli.mjs', 'recheck', 'asset.json', 'other-cases.json', expected=2)
    (root / 'input.json').write_bytes(b'{"start":1,"end":2000000001}')
    call(root, 'node', 'foundry-cli.mjs', 'run', 'asset.json', 'cases.json', 'input.json', expected=2)
    (root / 'draft.json').write_bytes(b'{"name":"refuse","inputs":["start","end"],"outputs":{"bytes":{"op":"exec","args":["rejected"]},"ordered":true}}')
    call(root, 'node', 'foundry-cli.mjs', 'seal', 'task.json', 'draft.json', expected=2)
    cfg = json.loads((root / 'local.example.json').read_bytes())
    state, _ = call(root, sys.executable, 'provider.py', '--config', 'local.example.json', 'status')
    require(state['local_only'] is True and state['providers'][0]['local'], 'Offline provider default cannot be reproduced')
    cfg['providers']['localhost-inference']['base_url'] = 'https://example.invalid/v1'
    (root / 'held.json').write_bytes(member.stable(cfg))
    call(root, sys.executable, 'provider.py', '--config', 'held.json', 'status', expected=2)
    cfg['local_only'], cfg['allow_paid_requests'], cfg['session_budget_usd'] = False,True,1
    provider = cfg['providers']['localhost-inference']
    provider['key_env'] = 'FOUNDRY_TEST_ONLY'
    provider['models']['replace-with-your-model-id']['input_per_million'] = 1
    (root / 'held.json').write_bytes(member.stable(cfg))
    (root / 'prompt.txt').write_text('This is a denial fixture. No request may be sent.')
    attempt = subprocess.run([sys.executable,'provider.py','--config','held.json','generate',
                              '--provider','localhost-inference','--model','replace-with-your-model-id',
                              '--prompt','prompt.txt'], capture_output=True, cwd=root,
                             env={**os.environ,'FOUNDRY_TEST_ONLY':'fixture-never-a-real-credential'})
    require(attempt.returncode == 2 and b'CONSENT' in attempt.stderr and b'Dispatching' not in attempt.stderr
            and b'fixture-never-a-real-credential' not in attempt.stderr, 'Unapproved remote dispatch was not refused')
    return {'archive_sample_matches':6,'reference_model_candidate_matches':14,'offline_reuse':True,'demo_wall_ns':wall_ns,'reuse_wall_ns':reuse_ns,
            'package_sha256':expected,'negative_controls':7,'real_member_trial':None}


def qualify(directory, live=False):
    manifest = json.loads((directory / member.MEMBER_JSON).read_bytes())
    tools = manifest['capabilities']
    with TemporaryDirectory() as work:
        root = Path(work)
        results = {
            'endpoint': qualify_endpoint(directory / member.ENDPOINT_ZIP, root / 'endpoint',
                                         tools['endpoint'], manifest['endpoint_reference']),
            'archive': qualify_archive(directory / member.ARCHIVE_ZIP, root / 'archive',
                                       tools['archive'], live),
            'measured_productivity': None,
        }
        if (directory / 'atlas-release.json').is_file():
            release = json.loads((directory / 'atlas-release.json').read_bytes())
            if 'foundry_sha256' in release:
                results['foundry'] = qualify_foundry(directory, root / 'foundry', release)
        return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--live-archive', action='store_true')
    options = parser.parse_args()
    print(json.dumps(qualify(options.directory.resolve(), options.live_archive), sort_keys=True))
