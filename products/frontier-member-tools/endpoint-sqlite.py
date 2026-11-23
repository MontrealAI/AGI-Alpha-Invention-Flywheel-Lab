"""Independent screening entry point using the pinned exact SQLite baseline."""
from argparse import ArgumentParser
import json
from pathlib import Path

from reference import evaluate_many


def evaluate(batch):
    selections = [{
        'id': r['id'], 'published': r['published'], 'facts': batch['scope'],
        'metric': r['tokens_per_s'] if r['p90_ttft_ms'] is not None else None,
        'upper_metric': r['p90_ttft_ms'], 'objective': str(r['load']),
    } for r in batch['rows']]
    expected, = evaluate_many(selections, batch['scope'], batch['cutoff'],
                              [batch['minimum_tokens_per_s']], batch['maximum_p90_ttft_ms'])
    row = next((r for r in batch['rows'] if r['id'] in expected['winners']), None)
    return {
        'schema': 'frontier/endpoint-result-v1',
        'screening': 'QUALIFIED_TESTED_POINT' if row else 'ABSTAIN',
        'highest_tested_load': row['load'] if row else None,
        'evidence_id': row['id'] if row else None,
        'operating_adoption': 'ABSTAIN',
        'rows': [{'id': r['id'], 'load': r['load'], 'disposition': expected['dispositions'][r['id']]}
                 for r in sorted(batch['rows'], key=lambda r: r['load'])],
    }


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('batch', type=Path)
    selected = parser.parse_args().batch
    with selected.open('rb') as handle:
        raw = handle.read(256_001)
    if len(raw) > 256_000:
        parser.error('Input too large')
    print(json.dumps(evaluate(json.loads(raw)), sort_keys=True, separators=(',', ':')))
