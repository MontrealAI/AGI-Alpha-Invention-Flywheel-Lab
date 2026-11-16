"""Reproducible finite ignition demonstration. Inputs are synthetic, execution is real."""
from __future__ import annotations
import argparse
import contextlib
import json
import os
from pathlib import Path
import random
import signal
import sqlite3
import subprocess
import sys
import time
from .alpha_runtime import Engine, atomic, encoded, filehash, load, solve, source_identity


def make_workload(path, seed=41, rows=80000, indexed=False):
    rng = random.Random(seed)
    with contextlib.closing(sqlite3.connect(path)) as c:
        c.execute('CREATE TABLE events(tenant INTEGER,status INTEGER,epoch INTEGER,amount INTEGER)')
        data = ((rng.randrange(200), rng.randrange(4), rng.randrange(10000), rng.randrange(-50, 30000)) for _ in range(rows))
        c.executemany('INSERT INTO events VALUES(?,?,?,?)', data)
        if indexed:
            c.execute('CREATE INDEX incumbent_cover ON events(tenant,status,epoch,amount)')
            c.execute('ANALYZE')
        c.commit()
    return path


def request(job, seed=41):
    rng = random.Random(seed)
    probes = [[rng.randrange(200), rng.randrange(4), i*800, i*800+1700] for i in range(8)]
    return {'version': 1, 'id': job, 'table': 'events', 'equals': ['tenant', 'status'],
            'range': 'epoch', 'measure': 'amount', 'discovery': probes[:4], 'confirmation': probes[4:],
            'min_gain': 2.0, 'max_index_bytes': 64*1024*1024}


def wait_for(engine, job, proc, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError('Worker stopped before completing ' + job)
        state = next((x['status'] for x in engine.status()['jobs'] if x['id'] == job), None)
        if state in ('DELIVERED_AWAITING_SETTLEMENT', 'DECLINED'):
            return state
        if state == 'FAILED':
            raise RuntimeError('Work failed; inspect persistent events: ' + job)
        time.sleep(.05)
    raise TimeoutError('Finite demonstration observation window exceeded: ' + job)


def demo(output, rows=80000):
    output = Path(output).absolute()
    output.mkdir(parents=True, mode=0o700)
    engine = Engine(output / 'machine')
    a = make_workload(output / 'first.sqlite', 41, rows)
    b = make_workload(output / 'successor.sqlite', 83, rows)
    c = make_workload(output / 'already-optimized.sqlite', 129, rows, True)
    original = {p.name: filehash(p) for p in (a, b, c)}
    # One daemon receives successive work while alive; no per-cycle CLI invocation.
    command = [sys.executable, '-m', 'connected_enterprise.alpha_runtime', '--root', str(engine.root), 'run', '--watch', '--poll', '.05']
    start = time.perf_counter()
    log = open(output / 'worker.log', 'w')
    proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
    pid = proc.pid
    statuses = []
    try:
        for p, job, seed in ((a, 'cycle-001', 41), (b, 'cycle-002', 83), (c, 'cycle-003', 129)):
            engine.submit(p, request(job, seed))
            statuses.append(wait_for(engine, job, proc))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        log.close()
    if proc.returncode != 0:
        raise RuntimeError((output / 'worker.log').read_text())
    first = load(engine.root / 'outbox/cycle-001/receipt.json')
    second = load(engine.root / 'outbox/cycle-002/receipt.json')
    third = load(engine.root / 'outbox/cycle-003/receipt.json')
    # Equal-content conventional cold search on the identical fresh successor.
    cold = solve(engine.root / 'inbox/cycle-002/source.sqlite', request('cycle-002', 83))
    audit = engine.audit()
    before = engine.status()
    engine.run()
    after = engine.status()
    if before != after:
        raise AssertionError('A quiescent restart duplicated work')
    if original != {p.name: filehash(p) for p in (a, b, c)}:
        raise AssertionError('Source database changed')
    summary = {
        'demonstration': 'ALPHA production ignition 0.1.0',
        'inputs': 'SYNTHETIC_INTEGER_EVENT_WORKLOADS', 'rows_per_workload': rows,
        'daemon_pid': pid, 'single_daemon_received_successive_jobs': True,
        'daemon_stopped_after_demo': proc.poll() is not None,
        'cycle_statuses': statuses,
        'cycle_001': {k: first['result'][k] for k in ('accepted','search_candidates','vm_work_reduction_factor','ordinary_work_ratio','wall_ratio_observation','total_cpu_ns','total_wall_ns')},
        'cycle_002': {k: second['result'][k] for k in ('accepted','search_candidates','vm_work_reduction_factor','ordinary_work_ratio','used_retained_configuration','wall_ratio_observation','total_cpu_ns','total_wall_ns')},
        'cycle_003': {k: third['result'][k] for k in ('accepted','reason','search_candidates','vm_work_reduction_factor','total_cpu_ns','total_wall_ns')},
        'successor_control': {'same_source_sha256': second['result']['source_sha256'] == cold['source_sha256'],
                              'cold_candidates': cold['search_candidates'], 'warm_candidates': second['result']['search_candidates'],
                              'cold_total_cpu_ns': cold['total_cpu_ns'], 'warm_total_cpu_ns': second['result']['total_cpu_ns'],
                              'same_confirmation_answers': cold['selected']['answers'] == second['result']['selected']['answers'],
                              'interpretation': 'ORDINARY_VALIDATED_REUSE_NOT_SUPERIOR_INVENTIVE_INTELLIGENCE'},
        'audit': audit, 'restart_idempotent': before == after, 'original_databases_unchanged': True,
        'total_demonstration_wall_seconds': time.perf_counter() - start,
        'real_customers_observed': 0, 'actual_money_collected': 0,
        'complete_cost_profit': None, 'commercial_cycle_proven': False,
        'new_financial_ledger_created': False, 'paid_model_calls': 0,
        'runtime_model_inference': False, 'source_identity': source_identity(),
        'limits': ['Known database indexing methods; ordinary specialist control ties or wins',
                   'No external deployment, sales, customer acceptance, settlement or reinvestment',
                   'Warm-cache timings are observations, not guaranteed service performance',
                   'Inputs supplied by demonstration harness, not autonomous market discovery',
                   'Host billing and complete commercial costs unknown']}
    atomic(output / 'RESULTS.json', encoded(summary))
    atomic(output / 'CONTROL.json', encoded(cold))
    atomic(output / 'REQUEST-example.json', encoded(request('my-workload')))
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--rows', default=80000, type=int)
    a = p.parse_args()
    if a.rows < 1000:
        p.error('--rows must be at least 1000')
    print(json.dumps(demo(a.output, a.rows), indent=2))


if __name__ == '__main__':
    main()
