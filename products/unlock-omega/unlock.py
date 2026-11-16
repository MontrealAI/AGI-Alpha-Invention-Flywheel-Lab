"""UNLOCK Ω: a one-job computational breakthrough contract, evaluated before promotion.

Standard-library CLI; execution defaults to a locked-down Docker container.
No model API keys or paid services are built into this product.
"""
import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IMAGE = 'python:3.12-alpine'  # Docker downloads this if absent; pin digest for production.


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_project(project):
    project = Path(project).expanduser().resolve()
    for filename in ('reference.py', 'heldout.json', 'acceptance.json'):
        if not (project / filename).is_file():
            raise ValueError('missing ' + filename)
    config = json.loads((project / 'acceptance.json').read_text())
    cases = json.loads((project / 'heldout.json').read_text())
    if not isinstance(cases, list) or not 3 <= len(cases) <= 1000:
        raise ValueError('heldout must contain 3–1000 cases')
    ids = []
    for case in cases:
        if not isinstance(case, dict) or set(case) != {'id', 'input', 'kind'}:
            raise ValueError('case requires exactly id, input and kind')
        if not isinstance(case['id'], str) or len(case['id']) > 80:
            raise ValueError('case id must be a short string')
        if case['kind'] not in ('correctness', 'performance'):
            raise ValueError('invalid case kind')
        ids.append(case['id'])
    if len(set(ids)) != len(ids):
        raise ValueError('case ids must be unique')
    if sum(c['kind'] == 'performance' for c in cases) < 2:
        raise ValueError('at least two heldout performance cases required')
    if sum(c['kind'] == 'correctness' for c in cases) < 1:
        raise ValueError('at least one heldout correctness case required')
    threshold = float(config.get('min_speedup', 3.0))
    regression = float(config.get('max_perf_regression', 1.10))
    if not 1 < threshold <= 100000 or not 1 <= regression <= 3:
        raise ValueError('invalid preregistered performance thresholds')
    return project, cases, {'min_speedup': threshold, 'max_perf_regression': regression}


def execute(source, cases, mode, name, repeats=3, warmups=1):
    if mode == 'docker' and not shutil.which('docker'):
        raise RuntimeError('Docker is required by default; no untrusted Python was executed.')
    with tempfile.TemporaryDirectory(prefix='unlock-sandbox-') as directory:
        isolated = Path(directory)
        isolated.chmod(0o755)  # Unprivileged Docker worker needs read/traverse access.
        candidate = isolated / 'unit.py'
        shutil.copy2(source, candidate)
        candidate.chmod(0o644)
        job = {'cases': cases, 'repeats': repeats, 'warmups': warmups}
        if mode == 'docker':
            cmd = [
                'docker', 'run', '--rm', '--network=none', '--read-only',
                '--cap-drop=ALL', '--security-opt=no-new-privileges',
                '--pids-limit=64', '--memory=512m', '--cpus=1',
                '--user=65534:65534', '--tmpfs=/tmp:rw,noexec,nosuid,size=16m',
                f'--mount=type=bind,src={isolated},dst=/task,readonly',
                f'--mount=type=bind,src={ROOT},dst=/engine,readonly',
                IMAGE, 'python', '-I', '/engine/worker.py', name, '/task/unit.py'
            ]
        else:
            cmd = [sys.executable, '-I', str(ROOT / 'worker.py'), name, str(candidate)]
        result = subprocess.run(cmd, input=json.dumps(job), text=True,
                                capture_output=True, timeout=120, check=False)
        if result.returncode != 0:
            raise RuntimeError(f'sandbox exited {result.returncode}: {result.stderr[-650:]}')
        data = json.loads(result.stdout)
        if len(data['rows']) != len(cases):
            raise RuntimeError('incomplete evaluation')
        return data['rows']


def verify(project, candidate, mode='docker'):
    project, cases, acceptance = read_project(project)
    candidate = Path(candidate).expanduser().resolve()
    if not candidate.is_file() or candidate.suffix != '.py':
        raise ValueError('candidate must be an existing .py file')
    inputs = {c['id']: c for c in cases}
    reference = project / 'reference.py'
    metadata = {
        'product': 'UNLOCK OMEGA / local prototype',
        'utc': datetime.now(timezone.utc).isoformat(),
        'reference_sha256': digest(reference),
        'candidate_sha256': digest(candidate),
        'heldout_sha256': digest(project / 'heldout.json'),
        'acceptance_sha256': digest(project / 'acceptance.json'),
        'mode': mode, 'acceptance': acceptance,
        'qualification': 'LOCAL_EVALUATION_ONLY_NOT_EXTERNAL_AUDIT',
    }
    try:
        baseline = execute(reference, cases, mode, name='reference')
        challenger = execute(candidate, cases, mode, name='candidate')
        diffs = []
        perf = []
        for a, b in zip(baseline, challenger):
            if a['id'] != b['id'] or a['response'] != b['response']:
                diffs.append(a['id'])
            if inputs[a['id']]['kind'] == 'performance':
                ratio = a['median_ns'] / max(b['median_ns'], 1)
                perf.append({'id': a['id'], 'baseline_ms': round(a['median_ns'] / 1e6, 4),
                             'candidate_ms': round(b['median_ns'] / 1e6, 4),
                             'speedup': round(ratio, 4)})
        speedup = math.exp(sum(math.log(a['median_ns'] / max(b['median_ns'], 1)) for a, b in zip(baseline, challenger) if inputs[a['id']]['kind'] == 'performance') / len(perf))
        minimum = min(a['median_ns'] / max(b['median_ns'], 1) for a, b in zip(baseline, challenger) if inputs[a['id']]['kind'] == 'performance')
        passed = (not diffs and speedup >= acceptance['min_speedup']
                  and minimum >= 1 / acceptance['max_perf_regression'])
        metadata.update({'status': 'PASS' if passed else 'HOLD',
                         'correctness': {'tested': len(cases), 'mismatches': diffs},
                         'performance': {'geomean_speedup': round(speedup, 4),
                                         'slowest_case_speedup': round(minimum, 4),
                                         'cases': perf}})
    except (RuntimeError, subprocess.TimeoutExpired, ValueError) as exc:
        metadata.update({'status': 'HOLD', 'execution_error': str(exc)[:1000]})
    return metadata


def invent(project, mode):
    project, _, _ = read_project(project)
    if not (project / 'examples.json').is_file():
        raise ValueError('provide examples.json, separate from the heldout cases')
    if not shutil.which('codex'):
        raise RuntimeError('Codex CLI is not installed/authenticated. No model inference was run.')
    with tempfile.TemporaryDirectory(prefix='unlock-proposal-') as temp:
        task = Path(temp)
        for filename in ('reference.py', 'examples.json', 'acceptance.json'):
            shutil.copy2(project / filename, task / filename)
        prompt = (
            'Create candidate.py containing solve(payload) with precisely the same JSON-serializable '
            'behavior as reference.py. This is a commercial computational-feasibility task. '
            'Examine examples.json and acceptance.json. Identify a better algorithm, not mere '
            'constant-factor tricks. Use only Python standard library. Do not modify any existing '
            'files. Do not read any hidden heldout tests (they are intentionally unavailable). '
            'Do not call networks, access external accounts, cheat the evaluator, return hard-coded '
            'outputs, or tamper with measurements. Your sole deliverable is candidate.py.'
        )
        cmd = ['codex', 'exec', '--sandbox', 'workspace-write', '--cd', str(task), prompt]
        run = subprocess.run(cmd, text=True, capture_output=True, timeout=900, check=False)
        if run.returncode != 0 or not (task / 'candidate.py').is_file():
            raise RuntimeError('agent produced no candidate; no acceptance claimed: ' + run.stderr[-500:])
        out = project / 'proposals'
        out.mkdir(exist_ok=True)
        name = 'candidate-' + digest(task / 'candidate.py')[:16] + '.py'
        target = out / name
        shutil.copy2(task / 'candidate.py', target)
    report = verify(project, target, mode)
    destination = project / ('report-' + digest(target)[:16] + '.json')
    destination.write_text(json.dumps(report, indent=2) + '\n')
    return {'candidate': str(target), 'report': str(destination), 'status': report['status']}


def main(argv=None):
    parser = argparse.ArgumentParser(description='UNLOCK OMEGA — computational feasibility as an outcome')
    sub = parser.add_subparsers(dest='cmd', required=True)
    check = sub.add_parser('verify', help='run frozen independent functional/performance gates')
    check.add_argument('project', help='directory containing reference.py, heldout.json, acceptance.json')
    check.add_argument('candidate', help='candidate .py file with solve(payload)')
    make = sub.add_parser('invent', help='create one candidate with installed Codex CLI and test it')
    make.add_argument('project')
    demo = sub.add_parser('demo', help='run transparent example; known algorithms, not frontier proof')
    for p in (check, make, demo):
        p.add_argument('--unsafe-local', action='store_true',
                       help='ONLY for code you personally trust; bypasses Docker isolation')
    args = parser.parse_args(argv)
    mode = 'local' if args.unsafe_local else 'docker'
    try:
        if args.cmd == 'verify':
            result = verify(args.project, args.candidate, mode)
        elif args.cmd == 'invent':
            result = invent(args.project, mode)
        else:
            from make_demo import make_demo
            with tempfile.TemporaryDirectory(prefix='unlock-demo-') as temp:
                make_demo(Path(temp))
                result = verify(temp, Path(temp) / 'candidate.py', mode)
        print(json.dumps(result, indent=2))
        return 0 if result['status'] == 'PASS' else 2
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({'status': 'HOLD', 'error': str(exc)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

