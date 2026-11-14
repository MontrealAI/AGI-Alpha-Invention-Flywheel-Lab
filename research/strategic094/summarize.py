"""Compact all registered outcomes; never pool enterprises for a milestone."""
import argparse
import csv
import hashlib
import itertools
import json
import statistics
from pathlib import Path

from .model import CAPITALS, POLICIES, SCENARIOS

FIELDS = (
    'capital', 'scenario', 'policy', 'seed', 'months', 'trailing_year_profit',
    'cumulative_profit', 'cash', 'receivables', 'obligations',
    'future_production_reserve', 'tax_arrears', 'min_available',
    'accepted_orders', 'acquisition_total', 'acquisition_from_collected_surplus',
    'stopped_entry', 'investor_hurdle_met', 'unfunded_obligation_observed',
    'book_equity_before_future_delivery', 'cash_reconciliation_error',
)


def validate(rows):
    expected = set(itertools.product(SCENARIOS, CAPITALS, POLICIES, range(94100, 94124)))
    keys = [(r['scenario'], r['capital'], r['policy'], r['seed']) for r in rows]
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError('complete unique registered matrix required')
    for r in rows:
        if r['months'] != 60:
            raise ValueError('fixed five-year endpoint required')
        error = r['cash'] + r['receivables'] - r['tax_arrears'] - r['capital'] - r['cumulative_profit']
        if abs(error) > max(1e-4, r['capital'] * 1e-10):
            raise ValueError('independent book-equity reconciliation failed')
        if abs(r['obligations'] - r['future_production_reserve'] - r['tax_arrears']) > 1e-4:
            raise ValueError('obligation decomposition failed')
        if r['cash'] < -1e-5 or r['receivables'] < -1e-5:
            raise ValueError('negative cash or receivables')
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument('input', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    raw = a.input.read_bytes()
    data = json.loads(raw)
    rows = data['rows']
    validate(rows)
    a.output.mkdir(exist_ok=True, parents=True)
    with (a.output / 'RESULTS.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows({k: row[k] for k in FIELDS} for row in rows)
    groups = []
    for scenario, capital, policy in itertools.product(SCENARIOS, CAPITALS, POLICIES):
        selected = [r for r in rows if (r['scenario'], r['capital'], r['policy']) == (scenario, capital, policy)]
        profits = [r['trailing_year_profit'] for r in selected]
        groups.append({
            'scenario': scenario, 'capital': capital, 'policy': policy, 'count': len(selected),
            'year_profit_min': min(profits), 'year_profit_median': statistics.median(profits),
            'year_profit_max': max(profits),
            'cumulative_profit_median': statistics.median(r['cumulative_profit'] for r in selected),
            'accepted_orders_median': statistics.median(r['accepted_orders'] for r in selected),
            'entry_closed': sum(r['stopped_entry'] for r in selected),
            'investor_hurdle_met': sum(r['investor_hurdle_met'] for r in selected),
        })
    summary = {
        'scope': 'Conditional projection; no new native qualification or actual commerce',
        'model_sha256': hashlib.sha256(Path(__file__).with_name('model.py').read_bytes()).hexdigest(),
        'raw_result_sha256': hashlib.sha256(raw).hexdigest(),
        'csv_sha256': hashlib.sha256((a.output / 'RESULTS.csv').read_bytes()).hexdigest(),
        'registered_rows': len(rows), 'all_registered_rows_present': True,
        'elapsed_seconds': data['elapsed_seconds'],
        'positive_final_years': sum(r['trailing_year_profit'] > 0 for r in rows),
        'three_billion_final_years': sum(r['trailing_year_profit'] >= 3e9 for r in rows),
        'ten_billion_final_years': sum(r['trailing_year_profit'] >= 1e10 for r in rows),
        'non_entry_operating_profit': 0,
        'non_entry_is_not_investor_opportunity_return': True,
        'groups': groups,
    }
    (a.output / 'SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'groups'}, indent=2))


if __name__ == '__main__':
    main()
