"""Separately implemented result check; same host, not external certification."""
from __future__ import annotations
import argparse
import hashlib
import contextlib
import json
from pathlib import Path
import sqlite3

LOADED_VERIFY_HASH = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def reference_answers(source_path, request, probes):
    # Python row reduction, deliberately not the producer's SQL aggregate.
    from .alpha_runtime import quote, read_source
    fields = request['equals'] + [request['range'], request['measure']]
    answers = [[0, 0] for _ in probes]
    magnitude = 0
    with contextlib.closing(read_source(source_path)) as c:
        for row in c.execute('SELECT ' + ','.join(map(quote, fields)) + ' FROM ' + quote(request['table'])):
            if any(type(x) is not int for x in row):
                raise ValueError('Independent checker requires integer data')
            magnitude += abs(row[-1])
            if magnitude >= 2**63:
                raise ValueError('Potential SQLite integer sum overflow')
            for i, p in enumerate(probes):
                if tuple(row[:-2]) == tuple(p[:-2]) and p[-2] <= row[-2] < p[-1]:
                    answers[i][0] += row[-1]
                    answers[i][1] += 1
    return answers


def verify(source_path, payload):
    from .alpha_runtime import (digest, filehash, validate_request, read_source, inspect,
                                index_sql, query, source_identity, variant, measure)
    r = validate_request(payload['request'])
    result = payload['result']
    if payload['job'] != r['id'] or not result['accepted']:
        raise ValueError('Not an accepted, bound receipt')
    if result['source_sha256'] != filehash(source_path) or result['request_sha256'] != digest(r):
        raise ValueError('Request/source binding failed')
    if payload['source_identity'] != source_identity():
        raise ValueError('Execution code changed; requalification required')
    apply, rollback = index_sql(r, result['columns'])
    if result['apply_sql'] != apply or result['rollback_sql'] != rollback or result['query_sql'] != query(r):
        raise ValueError('SQL artifact not derived from the allowed grammar')
    if result['economic_status'] != 'NOT_SETTLED' or result['cash_collected'] is not None or result['complete_cost_profit'] is not None:
        raise ValueError('Production output cannot assert monetary settlement')
    expected = reference_answers(source_path, r, r['confirmation'])
    if expected != result['selected']['answers'] or expected != result['baseline']['answers'] or expected != result['ordinary']['answers']:
        raise ValueError('Independent expected result mismatch')
    with contextlib.closing(read_source(source_path)) as source:
        if inspect(source, r) != result['signature']:
            raise ValueError('Capability scope mismatch')
        ordinary = r['equals'] + [r['range'], r['measure']]
        with variant(source, r, None) as (b, _, _), variant(source, r, result['columns']) as (c, size, _), variant(source, r, ordinary) as (o, ordinary_size, _):
            bm = measure(b, query(r), r['confirmation'])
            cm = measure(c, query(r), r['confirmation'])
            om = measure(o, query(r), r['confirmation'])
    if cm['answers'] != expected or bm['answers'] != expected or om['answers'] != expected:
        raise ValueError('Fresh execution did not reproduce results')
    for fresh, recorded in ((bm, result['baseline']), (cm, result['selected']), (om, result['ordinary'])):
        if fresh['vm_steps'] != recorded['vm_steps']:
            raise ValueError('Recorded work metric did not reproduce')
    gain = bm['vm_steps'] / cm['vm_steps']
    if gain < r['min_gain'] or gain != result['vm_work_reduction_factor'] or size > r['max_index_bytes'] or size != result['index_bytes']:
        raise ValueError('Acceptance threshold failed')
    if ordinary_size <= r['max_index_bytes'] and cm['vm_steps'] > om['vm_steps']:
        raise ValueError('Stronger conventional alternative wins')
    return {'verified': True, 'confirmation_cases': len(expected), 'vm_work_reduction_factor': gain,
            'scope': 'FINITE_DECLARED_READ_WORKLOAD', 'commercial_success': False}


def main():
    from .alpha_runtime import load
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database', type=Path, required=True)
    p.add_argument('--receipt', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(verify(a.database, load(a.receipt)), indent=2))


if __name__ == '__main__':
    main()
