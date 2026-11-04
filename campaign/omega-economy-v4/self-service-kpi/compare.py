"""Compare one human-readable SQLite query with the pinned conventional KPI producer."""
import argparse
import copy
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
from time import perf_counter_ns, process_time_ns

HERE = Path(__file__).resolve().parent
COMMIT = 'bc8f1560dd1c1c90cdc246a8469a249024094fac'
PROTOCOL = '8ad228e8ca7b72b4315bf2cb01c7ac1d88af04e2d93d08d497601e3b259a058d'
SOURCE_FILES = ('adaptive_enterprise/instruments.py', 'adaptive_enterprise/checkers.py',
                'enterprise/services.py', 'enterprise/checkers.py', 'commercial/ledger.py')
SEED = 392900


def encoded(obj):
    return json.dumps(obj, separators=(',', ':'), sort_keys=True, allow_nan=False).encode()


def file_sha(path):
    return sha256(path.read_bytes()).hexdigest()


def run(repo):
    if file_sha(HERE / 'PROTOCOL.md') != PROTOCOL:
        raise ValueError('Frozen protocol does not match')
    for path in SOURCE_FILES:
        expected = subprocess.check_output(['git', '-C', repo, 'show', f'{COMMIT}:{path}'])
        if (repo / path).read_bytes() != expected:
            raise ValueError(f'Wrong source file {path}')
    sys.path.insert(0, str(repo))
    from adaptive_enterprise.checkers import audit_delivery
    from adaptive_enterprise import instruments

    query = (HERE / 'kpi.sql').read_text()
    times = defaultdict(Counter)
    counts = Counter()
    volume = Counter()
    failures = []
    cases = []
    negative = None

    def timed(stage, func, *args, **kwargs):
        wall, cpu = perf_counter_ns(), process_time_ns()
        try:
            return func(*args, **kwargs)
        finally:
            times[stage]['cpu_ns'] += process_time_ns() - cpu
            times[stage]['wall_ns'] += perf_counter_ns() - wall
            times[stage]['calls'] += 1

    db = timed('sqlite_open', sqlite3.connect, ':memory:')

    def sql_produce(raw):
        plan = instruments.infer_plan(raw, mode='conventional')
        normalized = instruments.execute_plan(raw, plan)
        value, = db.execute(query, {'raw': encoded(raw).decode()}).fetchone()
        return {'order_id': raw['order_id'], 'service_id': raw['service_id'], 'currency': raw['currency'],
                'scope': raw['scope'], 'outcome_scope': 'complete_outcome', 'method': 'canonical',
                'plan': plan, 'normalized_input': normalized, 'useful_outcome': json.loads(value)}

    arms = {
        'sqlite': sql_produce,
        'conventional': lambda raw: instruments.produce(raw, 'generated_schema', mode='conventional'),
    }
    for index in range(132):
        raw = timed('fixture_generation', instruments.synthetic_raw, 'kpi_variance', index, SEED)
        volume['source_bytes'] += len(encoded(raw))
        counts['metrics'] += len(raw['source_order']['metrics'])
        record = {'index': index, 'input_sha256': sha256(encoded(raw)).hexdigest()}
        for name in (('sqlite', 'conventional') if index % 2 == 0 else ('conventional', 'sqlite')):
            try:
                artifact = timed(name + '_production', arms[name], raw)
                verdict = timed(name + '_checking', audit_delivery, 'kpi_variance', raw, artifact)
                accepted = verdict['accepted'] and artifact['outcome_scope'] == 'complete_outcome'
                if not accepted:
                    failures.append({'index': index, 'arm': name, 'rejection': verdict['errors']})
                counts[name + '_accepted'] += int(accepted)
                semantics = encoded(instruments._semantics(artifact))
                volume[name + '_semantics_bytes'] += len(semantics)
                record[name] = sha256(semantics).hexdigest()
                if name == 'sqlite' and index == 0:
                    altered = copy.deepcopy(artifact)
                    altered['useful_outcome']['rows'][0]['delta_cents'] += 1
                    negative = timed('negative_check', audit_delivery, 'kpi_variance', raw, altered)
            except Exception as exc:
                failures.append({'index': index, 'arm': name, 'error': f'{type(exc).__name__}: {exc}'})
        is_match = 'sqlite' in record and record['sqlite'] == record.get('conventional')
        counts['matching_semantics'] += int(is_match)
        if not is_match:
            failures.append({'index': index, 'comparison': 'MISSING_OR_DIFFERENT_SEMANTICS'})
        cases.append(record)
    timed('sqlite_close', db.close)
    return {
        'schema': 'omega/sqlite-kpi-self-service/v1', 'repo_commit': COMMIT, 'seed': SEED, 'indices': [0, 131],
        'index_bounds_inclusive': True, 'cases': len(cases), 'counts': dict(counts), 'bytes': dict(volume),
        'wall_and_process_cpu': times, 'failures': failures, 'negative_control': negative,
        'fixed_cases_and_content_sha256': sha256(encoded(cases)).hexdigest(),
        'all_pass': counts['matching_semantics'] == counts['sqlite_accepted'] == counts['conventional_accepted'] == 132
                    and negative is not None and not negative['accepted'] and not failures,
        'software': {'python': platform.python_version(), 'sqlite': sqlite3.sqlite_version,
                     'platform': platform.platform()},
        'repo_files_sha256': {p: file_sha(repo / p) for p in SOURCE_FILES},
        'comparison_files_sha256': {p: file_sha(HERE / p) for p in ('PROTOCOL.md', 'compare.py', 'kpi.sql')},
        'real_human_attention_minutes': None, 'actual_full_lifecycle_cost_usd': None, 'actual_revenue_usd': 0,
        'billing': 'In-process DB in memory, local CPU; no network or paid API requests in either production path.',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True, help='Checkout containing the pinned Git commit')
    args = parser.parse_args()
    result = run(args.repo.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    sys.exit(0 if result['all_pass'] else 1)
