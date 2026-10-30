import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    with Path(path).open('x') as stream:
        json.dump(data, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def evaluate(root, worker, protocol_path, output):
    root, worker, protocol_path, output = [Path(p).resolve() for p in (root, worker, protocol_path, output)]
    if output.exists():
        raise FileExistsError(output)
    protocol = json.loads(protocol_path.read_text())
    if sha(__file__) != protocol['verifier_sha256'] or sha(worker) != protocol['protected_worker_sha256']:
        raise ValueError('FROZEN_VERIFIER_IDENTITY')
    for name, digest in protocol['candidate_files'].items():
        target = root / name
        if target.is_symlink() or sha(target) != digest:
            raise ValueError('FROZEN_CANDIDATE_IDENTITY:' + name)
    output.mkdir(parents=True)
    freeze = {'schema': 'agi-alpha/temporal-final-freeze007/v1', 'candidate_files': protocol['candidate_files'],
              'verifier_sha256': sha(__file__), 'protected_worker_sha256': sha(worker), 'protocol_sha256': sha(protocol_path),
              'task_identity_sha256': protocol['task_identity_sha256'], 'before_protected_execution': True,
              'scope': 'One fixed descriptive engineering panel; no statistical superiority claim or error-budget reset.'}
    write(output / 'FREEZE.json', freeze)
    started = time.monotonic()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    command = [sys.executable, str(worker), '--root', str(root), '--output', str(output / 'cases')]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1')
    with (output / 'worker.log').open('xb') as stream:
        process = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, env=env, timeout=60)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = json.loads((output / 'cases/REPORT.json').read_text()) if (output / 'cases/REPORT.json').is_file() else {}
    final_sources_match = all(sha(root/name) == digest for name, digest in protocol['candidate_files'].items())
    expected_count = protocol['acceptance']['checks_total']
    accepted = (process.returncode == 0 and result.get('schema') == 'agi-alpha/temporal-verifier-cases007/v1' and
                result.get('accepted') is True and result.get('checks_passed') == expected_count and result.get('checks_total') == expected_count and
                all(check.get('passed') is True for check in result.get('checks', [])) and len(result.get('checks', [])) == expected_count and
                result.get('case_source_sha256') == freeze['protected_worker_sha256'] and result.get('task_identity_sha256') == freeze['task_identity_sha256'] and
                final_sources_match and sha(worker) == freeze['protected_worker_sha256'] and sha(__file__) == freeze['verifier_sha256'] and sha(protocol_path) == freeze['protocol_sha256'])
    report = {'schema': 'agi-alpha/temporal-acceptance007/v1', 'accepted': accepted,
              'checks_passed': result.get('checks_passed'), 'checks_total': result.get('checks_total'),
              'candidate_files': freeze['candidate_files'], 'verifier_sha256': freeze['verifier_sha256'], 'protocol_sha256': freeze['protocol_sha256'],
              'worker_sha256': freeze['protected_worker_sha256'], 'task_identity_sha256': freeze['task_identity_sha256'],
              'case_report_sha256': sha(output/'cases/REPORT.json') if (output/'cases/REPORT.json').exists() else None,
              'case_report': 'cases/REPORT.json', 'command': command, 'returncode': process.returncode,
              'source_unchanged': final_sources_match, 'wall_seconds': time.monotonic()-started,
              'waited_child_cpu_seconds': after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
              'log_sha256': sha(output/'worker.log'), 'statistical_alpha_spent': 0,
              'engineering_scope': 'Typed effect factoring/order construction and remapped equivalent-content reuse execute actual SQLite or file fsync operations, observed real handle closure and retained payload bytes under normal and injected failure paths.',
              'comparison': 'Conventional explicit commit/fsync before consumption and finally-close meets the same tested complete contract. Equal-content ordinary reuse matches the retained operator. No competitive advantage is established.',
              'limits': 'Developer/model supplied operation semantics, donor roles and grammar. Injected exceptions are not OS cancellation; fsync calls are not hardware power-loss certification. Fixed tiny constructed programs do not establish a consequential application/cohort, autonomous policy improvement, profitability or commercial demand.',
              'independence': 'Separate verifier agent authored private cases and independently instrumented real resource handles/persisted bytes, without candidate edits. Shared model family, standard libraries, host/filesystem; procedural separation, not independent external certification.'}
    write(output / 'REPORT.json', report)
    shutil.copyfile(worker, output / 'EXPOSED_PROTECTED_CASES.py')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('root', 'worker', 'protocol', 'output'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    result = evaluate(args.root, args.worker, args.protocol, args.output)
    print(json.dumps({'accepted': result['accepted'], 'checks_passed': result['checks_passed'], 'checks_total': result['checks_total']}))
    sys.exit(0 if result['accepted'] else 1)
