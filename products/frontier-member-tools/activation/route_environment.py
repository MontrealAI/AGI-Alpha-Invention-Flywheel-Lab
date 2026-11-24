"""Compose observed endpoint measurements into a qualified local research task.

Inputs are one workload only. Multiple tested systems say nothing about live
failover, correlated outages, or operating readiness.
"""

import argparse
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3


FIELDS = ('rate_min', 'latency_max', 'system_count', 'rows')
ROW_FIELDS = ('evidence', 'system', 'load', 'rate', 'latency', 'verified')
NULL = {'load': None, 'witnesses': []}
NAME = re.compile(r'[A-Za-z0-9._/-]{1,80}')
MAX_SQL_INTEGER = 2**63 - 1


def checked(problem):
    if type(problem) is not dict or set(problem) != set(FIELDS):
        raise ValueError('ROUTE_CONTRACT')
    floor, ceiling, count, rows = (problem[key] for key in FIELDS)
    if (type(floor) is not int or type(ceiling) is not int or type(count) is not int
            or not 0 <= floor <= MAX_SQL_INTEGER or not 0 <= ceiling <= MAX_SQL_INTEGER
            or not 1 <= count <= MAX_SQL_INTEGER or type(rows) is not list):
        raise ValueError('ROUTE_LIMIT')
    evidence = set()
    for row in rows:
        if type(row) is not list or len(row) != len(ROW_FIELDS):
            raise ValueError('MEASUREMENT_SHAPE')
        key, system, load, rate, latency, verified = row
        if (type(key) is not str or not NAME.fullmatch(key) or key in evidence or type(system) is not str
                or not NAME.fullmatch(system) or type(load) is not int or not 1 <= load <= MAX_SQL_INTEGER
                or any(v is not None and (type(v) is not int or not 0 <= v <= MAX_SQL_INTEGER) for v in (rate, latency))
                or type(verified) is not bool):
            raise ValueError('MEASUREMENT_IDENTITY_OR_UNITS')
        evidence.add(key)
    return floor, ceiling, count, rows


def conventional(problem):
    floor, ceiling, count, rows = checked(problem)
    with closing(sqlite3.connect(':memory:')) as sql:
        sql.execute('CREATE TABLE measured(evidence TEXT, system TEXT, load INTEGER, rate INTEGER, '
                    'latency INTEGER, verified INTEGER)')
        sql.executemany('INSERT INTO measured VALUES(?,?,?,?,?,?)', rows)
        eligible = sql.execute('''
            SELECT load, evidence FROM (
                SELECT load, evidence, ROW_NUMBER() OVER (
                    PARTITION BY system ORDER BY load DESC, evidence ASC
                ) AS position
                FROM measured WHERE verified = 1 AND rate >= ? AND latency <= ?
            ) WHERE position = 1 ORDER BY load DESC, evidence ASC LIMIT ?
        ''', (floor, ceiling, count)).fetchall()
    return {'load': eligible[-1][0], 'witnesses': [r[1] for r in eligible]} if len(eligible) == count else dict(NULL)


def independent(problem):
    """Calculate capacity by descending feasibility and verify witnesses separately."""
    floor, ceiling, count, rows = checked(problem)
    eligible = [(key, system, load) for key, system, load, rate, latency, ok in rows
                if ok and rate is not None and latency is not None and rate >= floor and latency <= ceiling]
    # Binary search the tested loads. It is feasible iff count distinct
    # measured systems have at least one eligible row at or above that load.
    tested = sorted({load for _, _, load in eligible})
    lo, hi = 0, len(tested)
    while lo < hi:
        middle = (lo + hi) // 2
        if len({system for _, system, load in eligible if load >= tested[middle]}) >= count:
            lo = middle + 1
        else:
            hi = middle
    if lo == 0:
        return dict(NULL)
    capacity = tested[lo - 1]
    witnesses, represented = [], set()
    for key, system, _ in sorted(eligible, key=lambda row: (-row[2], row[0])):
        if system not in represented:
            witnesses.append(key)
            represented.add(system)
            if len(witnesses) == count:
                return {'load': capacity, 'witnesses': witnesses}
    raise ValueError('WITNESS_CAPACITY_DISAGREEMENT')


def verify(cases):
    results = []
    for case in cases:
        sql = conventional(case['input'])
        oracle = independent(case['input'])
        if sql != oracle or sql != case['expected']:
            raise ValueError('EXACT_CONTROL_DIVERGENCE:'+case['id'])
        results.append({'id': case['id'], **oracle})
    return results


def load(path):
    with path.open('rb') as stream:
        body = stream.read(1_000_001)
    if len(body) > 1_000_000:
        raise ValueError('ROUTE_FILE_SIZE')
    return json.loads(body)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case', type=Path, help='An authorized single-workload measurement contract')
    parser.add_argument('--cohort', action='store_true', help='Check both exact implementations against a committed cohort')
    args=parser.parse_args()
    value=load(args.case)
    if args.cohort:
        result=verify(value)
    else:
        result=conventional(value)
        if independent(value)!=result:
            raise ValueError('EXACT_CONTROL_DIVERGENCE')
        result={**result,'operational_adoption':'ABSTAIN'}
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    main()
