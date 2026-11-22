"""Verify retained complete outcome rows and source identity without a new run."""
import csv
import hashlib
import json
from pathlib import Path
from .summarize import validate


def audit(folder):
    folder = Path(folder)
    summary = json.loads((folder / 'SUMMARY.json').read_text())
    data = (folder / 'RESULTS.csv').read_bytes()
    if hashlib.sha256(data).hexdigest() != summary['csv_sha256']:
        raise ValueError('CSV digest mismatch')
    model = Path(__file__).with_name('model.py').read_bytes()
    if hashlib.sha256(model).hexdigest() != summary['model_sha256']:
        raise ValueError('executing model differs from frozen confirmation')
    rows = []
    integer = {'capital', 'seed', 'months', 'accepted_orders'}
    boolean = {'stopped_entry', 'investor_hurdle_met', 'unfunded_obligation_observed'}
    with (folder / 'RESULTS.csv').open() as stream:
        for raw in csv.DictReader(stream):
            row = {}
            for key, value in raw.items():
                if key in ('scenario', 'policy'):
                    row[key] = value
                elif key in boolean:
                    if value not in ('True', 'False'):
                        raise ValueError('invalid boolean')
                    row[key] = value == 'True'
                else:
                    row[key] = int(value) if key in integer else float(value)
            rows.append(row)
    validate(rows)
    if len(rows) != summary['registered_rows']:
        raise ValueError('row count mismatch')
    for key, threshold in [('positive_final_years', 0), ('three_billion_final_years', 3e9), ('ten_billion_final_years', 1e10)]:
        count = sum(r['trailing_year_profit'] > 0 if threshold == 0 else r['trailing_year_profit'] >= threshold for r in rows)
        if count != summary[key]:
            raise ValueError('milestone count mismatch')
    return {'accepted': True, 'rows': len(rows), 'native_profit_qualification': False}


if __name__ == '__main__':
    import sys
    print(json.dumps(audit(sys.argv[1]), indent=2))
