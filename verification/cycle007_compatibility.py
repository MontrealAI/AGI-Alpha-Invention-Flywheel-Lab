import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

SCOPE = 'pinned FastAPI documentation create/read, WebSocket, startup compatibility only; no production or security qualification'
BASELINE = {'fastapi': '0.99.1', 'starlette': '0.27.0', 'httpx': '0.27.2', 'pydantic': '1.10.27'}
TARGET = {'fastapi': '0.110.1', 'starlette': '0.37.2', 'httpx': '0.28.1', 'pydantic': '1.10.27'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def hashes(source, manifest):
    values = {}
    for name, row in manifest.items():
        path = source / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise ValueError('SOURCE_IDENTITY_MISMATCH:' + name)
        values[name] = row['sha256']
    return values


def run(command, cwd, logfile, timeout=45):
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    with Path(logfile).open('xb') as stream:
        completed = subprocess.run(command, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout, env=env)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {'command': command, 'returncode': completed.returncode, 'wall_seconds': time.monotonic()-started,
            'waited_child_cpu_seconds': after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime, 'log_sha256': sha(logfile)}


def evaluate(source, manifest_path, candidate, baseline_python, target_python, worker, protocol_path, output):
    source, manifest_path, candidate, worker, protocol_path, output = [Path(p).resolve() for p in (source, manifest_path, candidate, worker, protocol_path, output)]
    if output.exists():
        raise FileExistsError(output)
    protocol = json.loads(protocol_path.read_text())
    if protocol['scope'] != SCOPE or protocol['protected_worker_sha256'] != sha(worker):
        raise ValueError('FROZEN_PROTOCOL_OR_WORKER_MISMATCH')
    if protocol['verifier_sha256'] != sha(__file__) or protocol['source_manifest_sha256'] != sha(manifest_path):
        raise ValueError('FROZEN_VERIFIER_OR_SOURCE_MISMATCH')
    if protocol['candidate_sha256'] != sha(candidate):
        raise ValueError('FROZEN_CANDIDATE_MISMATCH')
    specification = json.loads(candidate.read_text())
    if specification != {'schema': 'agi-alpha/compatibility-target007/v1', 'baseline': BASELINE, 'target': TARGET}:
        raise ValueError('TARGET_SPECIFICATION_MISMATCH')
    manifest = json.loads(manifest_path.read_text())
    original = hashes(source, manifest)
    output.mkdir(parents=True)
    freeze = {'schema': 'agi-alpha/compatibility-final-freeze007/v1', 'candidate_sha256': sha(candidate),
              'verifier_sha256': sha(__file__), 'contract_sha256': sha(protocol_path), 'protected_worker_sha256': sha(worker),
              'source_manifest_sha256': sha(manifest_path), 'source_files': original, 'before_any_protected_execution': True}
    write(output / 'FREEZE.json', freeze)
    results = {}
    for arm, python, expected in [('baseline', baseline_python, BASELINE), ('target', target_python, TARGET)]:
        arm_out = output / arm
        arm_out.mkdir()
        with tempfile.TemporaryDirectory(prefix='alpha007-verifier-' + arm + '-') as temporary:
            copied = Path(temporary) / 'source'
            for name in manifest:
                destination = copied / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / name, destination)
            xml = arm_out / 'upstream.xml'
            upstream = run([str(Path(python).absolute()), '-m', 'pytest', '-q', 'app_b', 'tutorial002.py', 'tutorial003.py', '--junitxml=' + str(xml)], copied, arm_out / 'upstream.log')
            summary = {'tests': 0, 'failures': 0, 'errors': 0, 'skipped': 0}
            if xml.exists():
                tree = ET.parse(xml)
                for suite in tree.iter('testsuite'):
                    for key in summary:
                        summary[key] += int(suite.attrib.get(key, 0))
            protected = run([str(Path(python).absolute()), str(worker), '--source', str(copied), '--output', str(arm_out / 'protected.json')], copied, arm_out / 'protected.log')
            observed = json.loads((arm_out / 'protected.json').read_text()) if (arm_out / 'protected.json').exists() else {}
            versions_match = all(observed.get('versions', {}).get(name) == version for name, version in expected.items())
            unchanged = hashes(copied, manifest) == original
            results[arm] = {'upstream': upstream, 'upstream_summary': summary, 'protected': protected, 'observed': observed,
                            'versions_match': versions_match, 'source_unchanged': unchanged}
    agreement = results['baseline']['observed'].get('checks') == results['target']['observed'].get('checks')
    upstream_pass = all(row['upstream']['returncode'] == 0 and row['upstream_summary'] == {'tests': 9, 'failures': 0, 'errors': 0, 'skipped': 0} for row in results.values())
    protected_pass = all(row['protected']['returncode'] == 0 and len(row['observed'].get('checks', [])) == protocol['protected_checks_total'] and row['versions_match'] and row['source_unchanged'] for row in results.values())
    unchanged = hashes(source, manifest) == original and all(row['source_unchanged'] for row in results.values())
    final_identities = sha(candidate) == freeze['candidate_sha256'] and sha(worker) == freeze['protected_worker_sha256'] and sha(__file__) == freeze['verifier_sha256'] and sha(protocol_path) == freeze['contract_sha256']
    accepted = upstream_pass and protected_pass and agreement and unchanged and final_identities
    delivery = {'schema': 'agi-alpha/scoped-compatibility-delivery007/v1', 'accepted': accepted, 'scope': SCOPE,
                'candidate_sha256': freeze['candidate_sha256'], 'source_manifest_sha256': freeze['source_manifest_sha256'],
                'source_commit': protocol['source_commit'], 'baseline_versions': BASELINE, 'target_versions': TARGET,
                'upstream_tests_per_arm': 9, 'protected_checks_per_arm': protocol['protected_checks_total'],
                'behavior_agreement': agreement, 'results': results,
                'limits': 'Existing documented upgrade; no vulnerability advisory qualification, unknown production behavior, scientific superiority or buyer demand inferred.'}
    write(output / 'ACCEPTED_DELIVERY.json', delivery)
    report = {'schema': 'agi-alpha/compatibility-acceptance007/v1', 'accepted': accepted, 'scope': SCOPE,
              **{key: freeze[key] for key in ('candidate_sha256', 'verifier_sha256', 'contract_sha256', 'source_manifest_sha256')},
              'artifact_sha256': sha(output / 'ACCEPTED_DELIVERY.json'), 'artifact': 'ACCEPTED_DELIVERY.json',
              'tests': {'upstream_passed': 18 if upstream_pass else 0, 'upstream_total': 18, 'upstream_skipped': sum(row['upstream_summary']['skipped'] for row in results.values()),
                        'upstream_source_unchanged': unchanged, 'protected_checks_passed': 2*protocol['protected_checks_total'] if protected_pass and agreement else 0,
                        'protected_checks_total': 2*protocol['protected_checks_total']},
              'protected_cases_first_exposure': 'After candidate/verifier/protocol/source freeze in this run; subsequent replay is exposed reproduction.',
              'statistical_alpha_spent': 0, 'statistical_superiority_claim': False,
              'independence': 'Separate verifier agent did not modify candidate or upstream source/tests; shared model family, libraries, host and filesystem. Procedural separation, no OS-enforced builder exclusion or external certification.'}
    write(output / 'REPORT.json', report)
    shutil.copyfile(worker, output / 'EXPOSED_PROTECTED_CASES.py')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('source', 'manifest', 'candidate', 'baseline-python', 'target-python', 'worker', 'protocol', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    result = evaluate(args.source, args.manifest, args.candidate, args.baseline_python, args.target_python, args.worker, args.protocol, args.output)
    print(json.dumps({'accepted': result['accepted'], 'artifact_sha256': result['artifact_sha256']}))
    sys.exit(0 if result['accepted'] else 1)
