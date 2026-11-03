"""Bounded, predeclared engineering comparison; never a business runner."""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import platform
import resource
import statistics
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'tests'))
from commercial.ledger import TapeExchange, _NativePrefixReplay, canonical, digest
from connected_enterprise.finance import JournalAccount, _audit_journal, audit_journal, source_identity
from omega import product

HERE = Path(__file__).resolve().parent
PROTOCOL = HERE/'PROTOCOL.json'


def stamp():
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    return time.perf_counter(), time.process_time(), children.ru_utime+children.ru_stime


def elapsed(start):
    end = stamp()
    return dict(zip(('wall_seconds', 'own_cpu_seconds', 'waited_child_cpu_seconds'),
                    (b-a for a,b in zip(start,end))))


def measure(records, manifest, account, arm):
    calls = 0
    original = TapeExchange.execute
    def execute(this, *args, **kwargs):
        nonlocal calls
        calls += 1
        return original(this, *args, **kwargs)
    start = stamp()
    session = _NativePrefixReplay(account._prefix_identity) if arm == 'guarded' else None
    try:
        with patch.object(TapeExchange, 'execute', execute):
            results = [(_audit_journal(record, root=ROOT, manifest=manifest, _native_session=session)
                        if session else audit_journal(record, root=ROOT, manifest=manifest))
                       for record in records]
        assert all(row['accepted'] for row in results)
    finally:
        if session: session.close()
    timing = elapsed(start)
    return {**timing, 'native_execute_calls':calls, 'prefixes':len(records),
            'all_accepted':True, 'audit_results_sha256':digest(results)}, results


def trace(directory, jobs):
    manifest = product.prepare_manifest(ROOT, directory/'products', jobs=jobs,
        hypothetical_rights=True, claim_window_hours=4)
    account = JournalAccount(ROOT, manifest, directory/'engineering.sqlite',
        opening=10_000*product.MICRO, working=0, contract='ENGINEERING_ONLY_OMEGA_PREFIX_20261103')
    records = [account.export()]
    execute = account.execute
    def record(*args, **kwargs):
        result = execute(*args, **kwargs)
        records.append(account.export())
        return result
    try:
        with patch.object(account, 'execute', side_effect=record):
            for i, job in enumerate(manifest['jobs']):
                result = product.fulfill(account, ROOT, manifest, job['id'],
                    order_id='engineering-'+str(i), buyer='authored-'+str(i), hour=0)
                assert result['status'] == 'released'
            account.advance_financial(5)
        receipt = account.spend('earned-successor', 'engineering_replay', product.MICRO, 5,
                                {'scope':'ENGINEERING_ONLY', 'jobs':jobs}, 2*product.MICRO)
        assert receipt['funding'] == 'EARNED'
        records.append(account.export())
        return account, manifest, records
    except BaseException:
        account.close()
        raise


def run(output):
    if output.exists(): raise ValueError('NEW_ENGINEERING_RECEIPT_REQUIRED')
    protocol = json.loads(PROTOCOL.read_text())
    result = {'schema':'omega-prefix-engineering-result/v1', 'scope':protocol['scope'],
        'protocol_sha256':hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
        'base_commit':protocol['base_commit'], 'python':platform.python_version(),
        'platform':platform.platform(), 'real_transactions':0, 'business_claims':False,
        'source_files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [ROOT/'connected_enterprise/finance.py', ROOT/'tests/test_omega_prefix_replay.py',
             ROOT/'tests/test_connected_prefix_replay037.py', ROOT/'tests/test_production060_native.py',
             ROOT/'tests/test_omega_market_product.py', Path(__file__)]}, 'measurements':[]}
    suite = unittest.TestSuite()
    for pattern in ['test_connected_prefix_replay037.py', 'test_production060_native.py', 'test_omega_prefix_replay.py']:
        suite.addTests(unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern=pattern))
    captured = io.StringIO(); start = stamp()
    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        tests = unittest.TextTestRunner(stream=captured, verbosity=1).run(suite)
    result['qualification'] = {**elapsed(start), 'tests_run':tests.testsRun,
        'failures':[{'test':str(test), 'trace':error[-6000:]} for test,error in tests.failures],
        'errors':[{'test':str(test), 'trace':error[-6000:]} for test,error in tests.errors],
        'skipped':[{'test':str(test), 'reason':reason} for test,reason in tests.skipped],
        'passed':tests.wasSuccessful()}
    print(json.dumps({'qualification':{k:v for k,v in result['qualification'].items() if k not in {'failures','errors','skipped'}}}), flush=True)
    if not tests.wasSuccessful():
        result['verdict'] = 'UNQUALIFIED_NO_PERFORMANCE_CLAIM'
        output.write_bytes(canonical(result)+b'\n')
        return 1
    try:
        for jobs in protocol['performance']['useful_trace_jobs']:
            with tempfile.TemporaryDirectory(prefix='omega-prefix-engineering-', dir=ROOT) as temp:
                start = stamp()
                account, manifest, records = trace(Path(temp), jobs)
                construction = elapsed(start)
                try:
                    row = {'jobs':jobs, 'construction':construction,
                        'source_identity':source_identity(ROOT, manifest),
                        'manifest_sha256':digest(manifest),
                        'final_native_actions_sha256':records[-1]['ledger']['actions_sha256'],
                        'native_actions':len(records[-1]['ledger']['actions']),
                        'exported_prefixes':len(records), 'runs':[]}
                    expected = None
                    for repeat, arms in enumerate(protocol['performance']['arm_order']):
                        for arm in arms:
                            measured, audited = measure(records, manifest, account, arm)
                            if expected is None: expected = audited
                            assert audited == expected, 'PER_PREFIX_FULL_VS_GUARDED_AUDIT_DIVERGENCE'
                            row['runs'].append({'repeat':repeat, 'arm':arm, **measured})
                            print(json.dumps({'jobs':jobs, 'repeat':repeat, 'arm':arm, **measured}), flush=True)
                    medians = {arm:{metric:statistics.median(r[metric] for r in row['runs'] if r['arm']==arm)
                        for metric in ['wall_seconds','own_cpu_seconds','native_execute_calls']}
                        for arm in ['full','guarded']}
                    row['medians'] = medians
                    row['candidate_faster_on_both_clocks'] = all(
                        medians['guarded'][m] < medians['full'][m]
                        for m in ['wall_seconds','own_cpu_seconds'])
                    row['native_replay_work_reduced'] = medians['guarded']['native_execute_calls'] < medians['full']['native_execute_calls']
                    result['measurements'].append(row)
                finally: account.close()
        result['verdict'] = ('QUALIFIED_BOUNDED_REPLAY_IMPROVEMENT' if all(
            r['candidate_faster_on_both_clocks'] and r['native_replay_work_reduced'] for r in result['measurements'])
            else 'QUALIFIED_SEMANTICS_TIMING_TIE_OR_REGRESSION')
    except BaseException as error:
        result['verdict'] = 'ENGINEERING_MEASUREMENT_FAILED'
        result['failure'] = {'type':type(error).__name__, 'message':str(error)}
        output.write_bytes(canonical(result)+b'\n')
        raise
    output.write_bytes(canonical(result)+b'\n')
    print(json.dumps({'verdict':result['verdict'], 'receipt':str(output),
                      'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}), flush=True)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output.resolve()))
