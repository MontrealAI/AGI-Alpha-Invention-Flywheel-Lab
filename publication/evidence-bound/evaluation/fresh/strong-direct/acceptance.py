#!/usr/bin/env python3
"""Exact pooled acceptance from latest lane revisions. Pass JSON or '-' for stdin."""

import argparse
import json
import sys
from fractions import Fraction
from pathlib import Path


def pooled_acceptance(ledger):
    latest_revision = {}
    for row in ledger:
        lane, revision = row['lane'], row['revision']
        latest_revision[lane] = max(revision, latest_revision.get(lane, revision))

    latest_record = {}
    for row in ledger:
        lane = row['lane']
        if row['revision'] != latest_revision[lane]:
            continue
        state = row['state']
        record = (state, 0, 0) if state == 'retired' else (state, row['accepted'], row['attempts'])
        if latest_record.setdefault(lane, record) != record:
            raise ValueError(f'Conflicting latest revision for lane {lane!r}')

    accepted = sum(record[1] for record in latest_record.values())
    attempts = sum(record[2] for record in latest_record.values())
    ratio = exact(Fraction(accepted, attempts), 'ratio') if attempts else None
    return {
        'status': 'ok' if attempts else 'undefined',
        'metrics': {
            'acceptance_ratio': ratio,
            'accepted_total': exact(accepted, 'count'),
            'attempt_total': exact(attempts, 'count'),
        },
    }


def exact(value, unit):
    return {'numerator': value.numerator, 'denominator': value.denominator, 'unit': unit}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    source = parser.parse_args().input
    raw = sys.stdin.read() if source == '-' else Path(source).read_text(encoding='utf-8')
    payload = json.loads(raw)
    if isinstance(payload, list) and payload and 'data' in payload[0]:
        payload, = [case for case in payload if 'ledger' in case['data']]
    if isinstance(payload, dict):
        payload = payload.get('data', payload)['ledger']
    print(json.dumps(pooled_acceptance(payload), sort_keys=True))


if __name__ == '__main__':
    main()
