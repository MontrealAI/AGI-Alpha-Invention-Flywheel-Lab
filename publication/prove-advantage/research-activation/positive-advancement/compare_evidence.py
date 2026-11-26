"""Build the verified extent index and run the two real evidence-recovery cases."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic, process_time

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
from frontier_evidence_packets import (ARCHIVE_PINS, INDEX, SITE, SOURCE_HASHES, fetch, fingerprint,
                                       full_archive, index_archive, restore, verify_contract)


BASE = 'f0c8db6c7a1110dc614ab8a02c7a0bd5f79260de'
FACTORY = '436bb1b142a0da1f2c272f77821b75c3efdd73fe'
RAW = 'https://raw.githubusercontent.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/'
SOURCES = {
    'ACT15': ('frontier-activation-1.5.0.zip', FACTORY, {
        'evidence_control.py': 'products/frontier-member-tools/activation/evidence_control.py',
        'study/factory/EVIDENCE.json': 'publication/factory/EVIDENCE.json',
    }),
    'INV10': ('frontier-inventor-1.0.0.zip', BASE, {
        'relational.py': 'products/frontier-member-tools/inventor/relational.py',
        'study/reproduction.json': 'publication/inventor/reproduction.json',
        'study/evidence.json': 'publication/inventor/evidence.json',
    }),
}
def verify_sources(case, files):
    if {name: fingerprint(body) for name, body in files.items()} != SOURCE_HASHES[case]:
        raise ValueError('Work did not obtain the independently pinned evidence and verifier bytes.')


def ordinary_direct(case):
    _, revision, paths = SOURCES[case]
    start, cpu = monotonic(), process_time()
    with ThreadPoolExecutor(max_workers=len(paths)) as readers:
        bodies = readers.map(lambda path: fetch(f'{RAW}{revision}/{path}', 500_000), paths.values())
        result = dict(zip(paths, bodies, strict=True))
    verify_sources(case, result)
    return result, {'requests': len(result), 'response_body_bytes': sum(map(len, result.values())),
                    'wall_seconds': round(monotonic() - start, 6), 'cpu_seconds': round(process_time() - cpu, 6)}


def build():
    start, cpu = monotonic(), process_time()
    manifest_raw = fetch(SITE + 'atlas-release.json', 16_000)
    release = json.loads(manifest_raw)
    setup = {}
    packets = {}
    for case, (archive, _, paths) in SOURCES.items():
        tick, processor = monotonic(), process_time()
        expected_archive, expected_hash = ARCHIVE_PINS[case]
        if archive != expected_archive or release['foundry_sha256'][archive] != expected_hash:
            raise ValueError('An immutable archive fingerprint changed.')
        docs, direct = ordinary_direct(case)
        raw = fetch(SITE + archive, 3_000_000)
        packets[case] = index_archive(raw, archive, expected_hash, {k: fingerprint(v) for k, v in docs.items()})
        setup[case] = {'requests': len(paths) + 1, 'response_body_bytes': len(raw) + direct['response_body_bytes'],
                       'wall_seconds': round(monotonic() - tick, 6), 'cpu_seconds': round(process_time() - processor, 6)}
    latest = fetch(SITE + 'atlas-release.json', 16_000)
    if latest != manifest_raw:
        raise ValueError('The live release changed during index preparation.')
    index = {'schema': 'frontier/verified-evidence-packets-v1', 'registered_source_commit': BASE, 'packets': packets}
    return index, {'release_source': release['source_commit'], 'workflow_run': release['workflow_run'],
                   'release_sha256': fingerprint(manifest_raw), 'shared_manifest_requests': 2,
                   'shared_manifest_bytes': len(manifest_raw) + len(latest), 'case_setup_all_in': setup,
                   'wall_seconds': round(monotonic() - start, 6), 'cpu_seconds': round(process_time() - cpu, 6)}


def independent_replay(case, files):
    verify_sources(case, files)
    started = monotonic()
    with TemporaryDirectory(prefix='frontier-packet-replay-') as directory:
        workspace = Path(directory)
        for name, raw in files.items():
            path = workspace / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        if case == 'ACT15':
            args = ['evidence_control.py', 'study/factory/EVIDENCE.json']
            ran = subprocess.check_output([sys.executable, '-I', '-B', *args], cwd=workspace)
            values = json.loads(ran)
            supported = {row['id'] for row in values if row['verdict'] == 'DOCUMENTED_BY_CUTOFF'}
            withheld = sum(row['verdict'] == 'ABSTAIN_UNESTABLISHED' for row in values)
            if (supported != {'prusa_offer', 'bambu_software'} or len(values) != 9 or withheld != 7
                    or any(row['onset_established'] or row['continuity_established'] for row in values)):
                raise ValueError('Published availability decisions did not reproduce.')
            result = {'documentary_cutoffs': sorted(supported), 'withheld': withheld, 'checks': len(values)}
        else:
            runner = '''import json, runpy
from pathlib import Path
check = runpy.run_path('relational.py')['check']
study = json.loads(Path('study/reproduction.json').read_bytes())
evidence = json.loads(Path('study/evidence.json').read_bytes())
accepted = {}
for key, row in evidence['assessments'].items():
    record = row['assessment']
    if record['arm'] != 'conventional':
        continue
    plan = study['missions'][record['mission']]
    obtained = check(plan['mission'], plan['confirmation'], plan['incumbent']['sql'])
    if obtained != record['checks'] or len(obtained) != 9 or not all(x['pass'] for x in obtained):
        raise ValueError('A published independent SQL replay failed.')
    accepted[key] = len(obtained)
print(json.dumps(accepted, sort_keys=True))
'''
            ran = subprocess.check_output([sys.executable, '-I', '-B', '-c', runner], cwd=workspace)
            result = json.loads(ran)
            if result != {'editions-conventional': 9, 'endpoint-conventional': 9, 'impact-conventional': 9}:
                raise ValueError('Unexpected independently reproduced SQL scope.')
    return result, round(monotonic() - started, 6)


def compare(index):
    output = {}
    for i, (case, packet) in enumerate(index['packets'].items()):
        verify_contract(case, packet)
        operations = {'range': lambda: restore(packet, 2), 'full_archive': lambda: full_archive(packet),
                      'direct_git': lambda: ordinary_direct(case)}
        arms = {}
        for name in (('range', 'full_archive', 'direct_git') if i == 0 else ('direct_git', 'full_archive', 'range')):
            before = monotonic()
            docs, acquisition = operations[name]()
            result, elapsed = independent_replay(case, docs)
            arms[name] = {**acquisition, 'output': result, 'replay_wall_seconds': elapsed,
                          'acquisition_to_decision_wall_seconds': round(monotonic() - before, 6)}
        if any(row['output'] != arms['range']['output'] for row in arms.values()):
            raise ValueError('Recovered work differs across the complete controls.')
        candidate, incumbent = arms['range'], arms['full_archive']
        output[case] = {'arms': arms, 'gate_at_most_half_bytes_and_two_reads': candidate['range_requests'] <= 2
                        and candidate['response_body_bytes'] * 2 <= incumbent['response_body_bytes'],
                        'paid_model_calls': 0, 'complete_economic_cost': None}
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('build', 'compare'))
    parser.add_argument('--index', type=Path, default=INDEX)
    args = parser.parse_args()
    if args.operation == 'build':
        index, setup = build()
        with args.index.open('x', encoding='utf-8') as stream:
            json.dump(index, stream, indent=2)
            stream.write('\n')
        print(json.dumps(setup, indent=2))
    else:
        print(json.dumps(compare(json.loads(args.index.read_bytes())), indent=2))


if __name__ == '__main__':
    main()
