"""Bounded connected engineering pilot. Does not establish a Blue Sky or commercial win."""
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


def write(path, value):
    path = Path(path)
    pending = path.with_name('PENDING_COMPLETE.json') if path.name == 'COMPLETE.json' else path
    with pending.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    if path.name == 'COMPLETE.json':
        os.link(pending, path)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_sources():
    manifest = json.loads((ROOT / 'campaign/cycle-004/FREEZE.json').read_text())
    for path, expected in manifest['sources'].items():
        leaf = ROOT / path
        if leaf.is_symlink() or digest(leaf) != expected:
            raise ValueError('SOURCE_IDENTITY_MISMATCH ' + path)
    return manifest


def worker(output):
    start, cpu = time.monotonic(), time.process_time()
    freeze = check_sources()
    sys.path.insert(0, str(ROOT))
    from flywheel import strategy, retention, sandbox, foundation, commercial, evidence_executor
    qualification = sandbox.qualify()
    write(output / 'SANDBOX.json', qualification)
    if not qualification['qualified']:
        raise ValueError('SANDBOX_UNQUALIFIED')
    task = {'id': 'legacy-evidence-initialization', 'phases': ['reserve', 'start', 'work', 'complete'],
            'dependencies': [['reserve', 'start'], ['start', 'work'], ['work', 'complete']]}
    foundation.write_new(output / 'TASK.json', task)
    write(output / 'FOUNDATION.json', foundation.qualify())
    representation = {'id': task['id'], 'nodes': [
        {'id': 'exception_scope', 'kind': 'guard', 'unit': 'event'},
        {'id': 'started_write', 'kind': 'effect', 'unit': 'event'},
        {'id': 'worker', 'kind': 'action', 'unit': 'event'}],
        'relations': [['exception_scope', 'protects', 'started_write'], ['started_write', 'precedes', 'worker']],
        'conditions': {'failure': 'catchable_exception', 'effects': 'exclusive_local_output'},
        'changed_assumptions': ['Database durability is not transferred; this target covers catchable process interruption only']}
    donors = [{'id': 'transaction-before-mutation', 'domain': 'database transaction discipline',
               'provenance': 'developer supplied abstract failure-atomicity mechanism, not autonomous new discovery',
               'nodes': [{'id': 'transaction', 'kind': 'guard', 'unit': 'event'},
                         {'id': 'prepare', 'kind': 'effect', 'unit': 'event'},
                         {'id': 'apply', 'kind': 'action', 'unit': 'event'}],
               'relations': [['transaction', 'protects', 'prepare'], ['prepare', 'precedes', 'apply']],
               'conditions': {'failure': 'catchable_exception', 'effects': 'exclusive_local_output'}},
              {'id': 'similar-labels-incompatible-causality', 'domain': 'misleading surface labels',
               'nodes': [{'id': 'transaction', 'kind': 'guard', 'unit': 'event'},
                         {'id': 'prepare', 'kind': 'effect', 'unit': 'event'},
                         {'id': 'apply', 'kind': 'action', 'unit': 'event'}],
               'relations': [['prepare', 'protects', 'transaction'], ['apply', 'precedes', 'prepare']],
               'conditions': {'failure': 'catchable_exception', 'effects': 'exclusive_local_output'}}]
    mappings = strategy.discover(donors, representation)
    write(output / 'DISCOVERY.json', {'target': representation, 'donors': donors, 'mappings': mappings})
    if not any(m['applicable'] for m in mappings):
        raise ValueError('NO_APPLICABLE_MECHANISM')
    original = strategy.synthesize(task, [])
    failure = sandbox.run(ROOT / 'flywheel/strategy.py', 'interpret',
                          {'task': task, 'program': original['program'], 'interrupt_at': 'start'}, digest(ROOT / 'flywheel/strategy.py'))
    actual_original = evidence_executor.execute(task, original['program'], output / 'actual-original', 'start')
    write(output / 'ORIGINAL.json', {'strategy': original, 'failure': failure, 'actual_effect_execution': actual_original})
    if failure.get('worker', {}).get('result', {}).get('state') != 'UNMARKED':
        raise ValueError('EXPECTED_ORIGINAL_FAILURE_NOT_REPRODUCED')
    legacy = json.loads((ROOT / 'evidence/cycle-004/verifier-legacy-interruption/report.json').read_text())
    established = not legacy['all_passed'] and legacy['checks'][0]['interrupted_marker'] is False
    criticism = {'claim': 'Initialization interruptions preserve an incomplete marker',
                 'evidence': 'evidence/cycle-004/verifier-legacy-interruption/report.json',
                 'candidate_sha256': digest(ROOT / 'reproduce.py'), 'origin': 'real pre-existing source defect; verifier fault-injection reproduces it',
                 'reproduction': 'python verification/cycle004_probe_runner.py --runner reproduce.py --output NEW',
                 'expected_failure': 'STARTED exists but no INTERRUPTED marker', 'severity': 'evidence integrity',
                 'uncertainty': 'Catchable interruption only, not SIGKILL/host durability'}
    constraint = {'status': 'established' if established else 'unresolved', 'kind': 'protect_phase', 'phase': 'start'}
    write(output / 'CRITICISM.json', criticism)
    write(output / 'ADJUDICATION.json', {'constraint': constraint, 'verifier_receipt_sha256': digest(ROOT / criticism['evidence'])})
    repair = strategy.synthesize(task, [constraint])
    checks = [sandbox.run(ROOT / 'flywheel/strategy.py', 'interpret',
                         {'task': task, 'program': repair['program'], 'interrupt_at': phase}, digest(ROOT / 'flywheel/strategy.py'))
              for phase in ['start', 'work', 'complete']]
    actual_repairs = [evidence_executor.execute(task, repair['program'], output / ('actual-repair-' + phase), phase)
                      for phase in ['start', 'work', 'complete']]
    passed = all(r.get('worker', {}).get('result', {}).get('interrupted_marker') is True for r in checks) and all(r['interrupted_marker'] for r in actual_repairs)
    write(output / 'REPAIR.json', {'construction': repair, 'checks': checks, 'passed': passed,
                                  'actual_effect_execution': actual_repairs,
                                  'actual_instrument': 'flywheel/evidence_executor.py consumes the selected generated guard scope; run_cycle.py supervisor is separately hand-written and verified'})
    if not passed:
        raise ValueError('REPAIR_FAILED_UNCHANGED_SPEC')
    record = {'instrument': {'path': 'flywheel/strategy.py', 'sha256': digest(ROOT / 'flywheel/strategy.py')},
              'applicability': {'schema_version': 1, 'conditions': {'failure': 'catchable_exception', 'effects': 'exclusive_local_output'},
                                'assumptions': ['No SIGKILL or host crash durability claim'], 'uncertainty': 'Engineering scope only',
                                'failures': [{'conditions': {'failure': 'power_loss'}, 'reason': 'Process exception handling cannot guarantee durable recovery'}]},
              'generative_operator': {'language': 'bounded-evidence.v1', 'program': {'operator': 'protect_initialization', 'language': 'bounded-evidence/v1'}},
              'provenance': {'mapping': 'DISCOVERY.json', 'construction': 'REPAIR.json', 'source': freeze['base_commit']},
              'verification': {'status': 'verified-in-scope', 'receipt_sha256': digest(output / 'REPAIR.json')},
              'costs': {'acquisition_monetary': None}, 'exposure': ['public legacy bug', 'development initialization case'], 'supersedes': []}
    capability_id = retention.store(output / 'memory', record)
    retrieved = retention.retrieve(output / 'memory', {'schema_version': 1, 'conditions': {'failure': 'catchable_exception', 'effects': 'exclusive_local_output'}}, ROOT)
    operator = retrieved['records'][0]['record']['generative_operator']['program']
    successor_task = {'id': 'fresh-artifact-publication', 'phases': ['reserve', 'manifest', 'build', 'publish', 'complete'],
                      'dependencies': [['reserve', 'manifest'], ['manifest', 'build'], ['build', 'publish'], ['publish', 'complete']]}
    arms = {}
    for name, inherited, constraints in [('inheritance', operator, []), ('ordinary_reuse', operator, []),
                                        ('reset', None, []), ('operator_removed', None, []),
                                        ('conventional_wrap_all', None, [{'status': 'established', 'kind': 'protect_phase', 'phase': 'manifest'}])]:
        built = strategy.synthesize(successor_task, constraints, inherited=inherited)
        runs = [sandbox.run(ROOT / 'flywheel/strategy.py', 'interpret',
                            {'task': successor_task, 'program': built['program'], 'interrupt_at': p}, digest(ROOT / 'flywheel/strategy.py'))
                for p in successor_task['phases'][1:]]
        actual = [evidence_executor.execute(successor_task, built['program'], output / ('successor-' + name + '-' + p), p)
                  for p in successor_task['phases'][1:]]
        arms[name] = {'construction': built, 'checks': runs, 'actual_effect_execution': actual,
                      'passed': all(r.get('worker', {}).get('result', {}).get('interrupted_marker') is True for r in runs) and all(r['interrupted_marker'] for r in actual)}
    write(output / 'SUCCESSOR.json', {'task': successor_task, 'capability_id': capability_id, 'retrieval': retrieved, 'arms': arms,
                                     'freshness': 'Different engineering task; parent selected, separately verifier-selected cases published separately',
                                     'conclusion': 'Ordinary equivalent-content reuse remains tied; structured memory/policy/lifecycle superiority not established'})
    market = commercial.run(output / 'REPAIR.json', output / 'commercial', technical_acceptance={'passed': passed})
    report = {'schema': 'agi-alpha-connected-pilot/v1', 'source_freeze_sha256': digest(ROOT / 'campaign/cycle-004/FREEZE.json'),
              'mechanisms_executed': ['structural compatibility matching', 'finite executable strategy composition', 'reproduced criticism and constraint-driven repair', 'applicability-aware generative retention and fresh engineering successor'],
              'verdicts': {'connected_engineering_pilot': 'PASS_IN_DECLARED_SCOPE', 'full_engineering_completion': 'NOT_YET_ESTABLISHED',
                           'consequential_invention': 'NOT_ESTABLISHED', 'scientific_advantage': 'NOT_ESTABLISHED',
                           'progressive_lifecycle_advantage': 'NOT_ESTABLISHED', 'commercial_success': 'NOT_ESTABLISHED', 'complete_flywheel': 'NOT_ESTABLISHED'},
              'commercial_receipt': 'commercial/COMMERCIAL.json', 'model_access': 'No external frontier provider ran; agent/model identity and inference bills unavailable',
              'resources': {'worker_wall_seconds': time.monotonic()-start, 'worker_cpu_seconds': time.process_time()-cpu,
                            'children_cpu_seconds': resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime + resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,
                            'complete_cost': None, 'agent_inference_cost': None},
              'decision': 'RETAIN_CONVENTIONAL_CONTROL; machinery qualified for further consequential baseline-gap investigation',
              'statistical_alpha_spent': 0, 'simulated_receipts': 0, 'available_earned_funds': 0,
              'limitations': ['Developer-authored representations and finite grammar', 'No live model discovery performance', 'No superiority over equivalent ordinary reuse', 'No qualified demand, full costs or funded successor']}
    write(output / 'REPORT.json', report)


def worker_limits():
    parent = os.getppid()
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, 9, 0, 0, 0) != 0 or os.getppid() != parent:
        os._exit(125)
    resource.setrlimit(resource.RLIMIT_CPU, (180, 180))
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (10*1024**2, 10*1024**2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    if args.worker:
        worker(output)
        return 0
    owned = False
    try:
        output.mkdir(parents=True, exist_ok=False)
        owned = True
        write(output / 'STARTED.json', {'state': 'STARTED', 'scope': 'bounded engineering pilot; initialization is covered'})
        with (output / 'WORKER.log').open('xb') as stream:
            result = subprocess.run([sys.executable, '-I', str(ROOT / 'run_cycle.py'), '--worker', '--output', str(output)],
                                    stdout=stream, stderr=subprocess.STDOUT, timeout=120, start_new_session=True, preexec_fn=worker_limits,
                                    env={'PATH': os.defpath, 'LANG': 'C.UTF-8', 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'})
        if result.returncode:
            raise RuntimeError('WORKER_FAILED; preserve partial evidence')
        write(output / 'COMPLETE.json', {'state': 'COMPLETE', 'report_sha256': digest(output / 'REPORT.json')})
        print(json.dumps({'output': str(output), 'report_sha256': digest(output / 'REPORT.json')}))
    except BaseException as error:
        if owned and not (output / 'COMPLETE.json').exists():
            write(output / 'INTERRUPTED.json', {'state': 'INCOMPLETE', 'reason': type(error).__name__, 'resume': 'Preserve; replay to a new exclusive path'})
        raise
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
