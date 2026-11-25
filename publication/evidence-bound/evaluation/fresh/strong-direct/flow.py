#!/usr/bin/env python3
"""Exact aggregate flow with a completeness gate. Pass a JSON file or '-' for stdin."""

import argparse
import json
import sys
from fractions import Fraction
from pathlib import Path


def aggregate_flow(logs):
    missing = []
    for row in logs:
        for field, unit in (('litres', 'L'), ('minutes', 'min')):
            if row.get(field) in (None, ''):
                missing.append({'session': row['session'], 'field': field, 'unit': unit})
    if missing:
        return {'status': 'abstain', 'metrics': {}, 'missing': missing}

    minutes = sum(Fraction(row['minutes']) for row in logs)
    if minutes <= 0:
        return {'status': 'undefined', 'metrics': {}, 'reason': 'Total elapsed time must be positive'}
    litres = sum(Fraction(row['litres']) for row in logs)
    rate = litres / minutes
    return {
        'status': 'ok',
        'metrics': {'flow_rate': {'numerator': rate.numerator, 'denominator': rate.denominator, 'unit': 'L/min'}},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    source = parser.parse_args().input
    raw = sys.stdin.read() if source == '-' else Path(source).read_text(encoding='utf-8')
    payload = json.loads(raw, parse_float=Fraction)
    if isinstance(payload, list) and payload and 'data' in payload[0]:
        payload, = [case for case in payload if 'logs' in case['data']]
    if isinstance(payload, dict):
        payload = payload.get('data', payload)['logs']
    print(json.dumps(aggregate_flow(payload), sort_keys=True))


if __name__ == '__main__':
    main()
