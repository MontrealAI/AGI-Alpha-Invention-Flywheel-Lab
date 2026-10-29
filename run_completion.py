"""One bounded mechanism-completion path, with explicit development/confirmation separation."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    pending = path.with_name('PENDING_COMPLETE.json') if path.name == 'COMPLETE.json' else path
    with pending.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    if pending != path:
        os.link(pending, path)


def sources():
    frozen = json.loads((ROOT / 'campaign/cycle-005/FREEZE.json').read_text())
    for name, expected in frozen['sources'].items():
        path = ROOT / name
        if path.is_symlink() or sha(path) != expected:
            raise ValueError('SOURCE_IDENTITY_MISMATCH ' + name)
    return frozen


def worker(output, task_file=None):
    started, cpu = time.monotonic(), time.process_time()
    frozen = sources()
    sys.path.insert(0, str(ROOT))
    from mechanisms import pipeline
    from flywheel import sandbox, commercial
    qualification = sandbox.qualify()
    write(output / 'SANDBOX.json', qualification)
    if not qualification['qualified']:
        raise ValueError('SANDBOX_UNQUALIFIED')
    task, donors, target = pipeline.example()
    if task_file:
        supplied = json.loads(task_file.read_text())
        task, donors, target = supplied['task'], supplied['donors'], supplied['target_graph']
    write(output / 'TASK.json', {'task': task, 'donors': donors, 'target_graph': target,
                                 'origin': 'Supplied typed engineering semantics; mapping and rules constructed by actual runtime'})
    developed = pipeline.develop(task, donors, target, output / 'development', output / 'memory')
    if developed.get('retained') is None:
        raise ValueError('NO_VERIFIED_ACQUIRED_OPERATOR; preserve development evidence')
    successor, _, graph = pipeline.example('successor-renamed-permuted', True)
    arms = {}
    for mode in ('inheritance', 'ordinary', 'removed', 'conventional', 'reset'):
        arms[mode] = pipeline.reuse(successor, donors, graph, output / ('successor-' + mode), output / 'memory', mode)
    write(output / 'SUCCESSOR.json', {'arms': arms, 'selection': 'Developer-selected engineering successor; separate verifier selects post-freeze cases',
                                     'no_policy_learning_claim': True, 'no_complete_cost_claim': True})
    bundles = pipeline.combinations(task, donors, target, output / 'combinations', output / 'bundle-memory')
    policies = pipeline.policy_comparison(output / 'policy-comparison')
    enabling = pipeline.archive_enabling(output / 'archive-enabling')
    market = commercial.run(output / 'development/AFTER.json', output / 'commercial',
                            technical_acceptance={'passed': developed['after_passed']})
    report = {'schema': 'agi-alpha-mechanism-completion/v1',
              'freeze_sha256': sha(ROOT / 'campaign/cycle-005/FREEZE.json'),
              'development_verified': developed['after_passed'], 'acquired_record_id': developed['retained']['id'],
              'successor_passes': {name: arm['passed'] for name, arm in arms.items()},
              'complementary_bundle_passes': {name: arm['passed'] for name, arm in bundles['arms'].items()},
              'policy_cross_scores': policies['scores'], 'archive_dependency_removed_with_same_obligations': enabling['passed'],
              'verdicts': {'connected_engineering': 'EXECUTED_IN_DECLARED_SCOPE; independent verification separately required',
                           'scientific_advantage': 'NOT_ESTABLISHED', 'improved_discovery_policy': 'NOT_ESTABLISHED',
                           'complete_cost_commercial_viability': 'UNKNOWN', 'available_earned_funding': 'ZERO',
                           'funded_successor': 'NOT_ESTABLISHED', 'commercial_flywheel': 'NOT_ESTABLISHED'},
              'lineage': ['TASK.json', 'development/DISCOVERY.json', 'development/BEFORE.json', 'development/CRITICISM.json',
                          'development/AFTER.json', 'development/after-check/VERIFICATION.json', 'memory/', 'SUCCESSOR.json', 'commercial/COMMERCIAL.json'],
              'resources': {'wall_seconds': time.monotonic()-started, 'process_cpu_seconds': time.process_time()-cpu,
                            'child_cpu_seconds': resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime + resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,
                            'complete_monetary_cost': None, 'external_model_calls': 0, 'agent_inference_cost': None},
              'model_limit': 'No external live frontier-model provider available or invoked; deterministic mechanisms and implementation-team inference are not live autonomous discovery evidence',
              'statistics': {'alpha_spent': 0, 'exposed_regressions_remain_exposed': True},
              'simulated_receipts': 0, 'available_earned_funds': 0,
              'limits': ['One-reservation/one-terminal-publication actual broker class', 'No host-crash durability', 'Finite developer-supplied grammar and donor schemas',
                         'Equivalent ordinary reuse and conventional construction can tie', 'No independent buyer, price, full cost or physical validation']}
    write(output / 'REPORT.json', report)


def limits():
    parent = os.getppid()
    if ctypes.CDLL(None).prctl(1, 9, 0, 0, 0) != 0 or os.getppid() != parent:
        os._exit(125)
    resource.setrlimit(resource.RLIMIT_CPU, (180, 180))
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (20*1024**2, 20*1024**2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--task', type=Path)
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    if args.worker:
        worker(output, args.task)
        return 0
    owned = False
    try:
        output.mkdir(parents=True, exist_ok=False)
        owned = True
        write(output / 'STARTED.json', {'state': 'STARTED', 'scope': 'Mechanism completion engineering replay'})
        command = [sys.executable, '-I', str(ROOT / 'run_completion.py'), '--worker', '--output', str(output)]
        if args.task:
            command += ['--task', str(args.task.resolve())]
        with (output / 'WORKER.log').open('xb') as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=150,
                        start_new_session=True, preexec_fn=limits,
                        env={'PATH': os.defpath, 'LANG': 'C.UTF-8', 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'})
        if result.returncode:
            raise RuntimeError('WORKER_FAILED; preserve partial evidence')
        write(output / 'COMPLETE.json', {'state': 'COMPLETE', 'report_sha256': sha(output / 'REPORT.json')})
        print(json.dumps({'output': str(output), 'report_sha256': sha(output / 'REPORT.json')}))
    except BaseException as error:
        if owned and not (output / 'COMPLETE.json').exists():
            write(output / 'INTERRUPTED.json', {'state': 'INCOMPLETE', 'reason': type(error).__name__,
                                               'recovery': 'Preserve output; rerun at a new exclusive path'})
        raise
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
