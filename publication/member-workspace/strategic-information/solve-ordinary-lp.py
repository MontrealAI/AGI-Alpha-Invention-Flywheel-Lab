import hashlib
from fractions import Fraction
from itertools import product
import json
from pathlib import Path
import time

import numpy as np
from scipy import __version__, optimize


def strategic_matrix(game, disclosure):
    states = []
    for state in game['states']:
        row_type, col_type = state['row_type'], state['col_type']
        row_obs = (row_type, col_type) if disclosure in {'row', 'both'} else (row_type,)
        col_obs = (col_type, row_type) if disclosure in {'col', 'both'} else (col_type,)
        payoff = [[Fraction(value) for value in row] for row in state['payoff']]
        states.append((row_obs, col_obs, Fraction(state['p']), payoff))

    row_info = {obs: i for i, obs in enumerate(dict.fromkeys(state[0] for state in states))}
    col_info = {obs: i for i, obs in enumerate(dict.fromkeys(state[1] for state in states))}
    row_plans = list(product(range(game['actions'][0]), repeat=len(row_info)))
    col_plans = list(product(range(game['actions'][1]), repeat=len(col_info)))
    matrix = [
        [sum(p * payoff[row[row_info[ro]]][col[col_info[co]]] for ro, co, p, payoff in states)
         for col in col_plans]
        for row in row_plans
    ]
    return matrix, row_plans, col_plans, list(row_info), list(col_info)


def policy(weights):
    rounded = [Fraction(float(max(0, value))).limit_denominator(1_000_000) for value in weights]
    total = sum(rounded)
    assert total > 0
    return [value / total for value in rounded]


def solve(game, disclosure):
    matrix, row_plans, col_plans, row_info, col_info = strategic_matrix(game, disclosure)
    floating = np.array(matrix, dtype=float)
    rows, cols = floating.shape
    row = optimize.linprog([0] * rows + [-1], A_ub=np.column_stack((-floating.T, np.ones(cols))),
                           b_ub=np.zeros(cols), A_eq=[[1] * rows + [0]], b_eq=[1],
                           bounds=[(0, 1)] * rows + [(None, None)], method='highs')
    col = optimize.linprog([0] * cols + [1], A_ub=np.column_stack((floating, -np.ones(rows))),
                           b_ub=np.zeros(rows), A_eq=[[1] * cols + [0]], b_eq=[1],
                           bounds=[(0, 1)] * cols + [(None, None)], method='highs')
    assert row.success and col.success
    row_policy, col_policy = policy(row.x[:-1]), policy(col.x[:-1])
    lower = min(sum(row_policy[i] * payoff for i, payoff in enumerate(column)) for column in zip(*matrix))
    upper = max(sum(prob * payoff for prob, payoff in zip(col_policy, row)) for row in matrix)
    scale = max(abs(Fraction(value)) for state in game['states'] for row in state['payoff'] for value in row)
    assert 0 <= upper - lower <= scale / 10_000_000
    return {'information': disclosure, 'row_observations': row_info, 'column_observations': col_info,
            'row_pure_plans': rows, 'column_pure_plans': cols,
            'row_policy_mixture': [{'plan': plan, 'p': str(prob)} for plan, prob in zip(row_plans, row_policy) if prob],
            'column_policy_mixture': [{'plan': plan, 'p': str(prob)} for plan, prob in zip(col_plans, col_policy) if prob],
            'lower': str(lower), 'upper': str(upper), 'gap': str(upper - lower),
            'exact_value': str(lower) if lower == upper else None}


root = Path(__file__).resolve().parent
input_bytes = (root / 'DIRECT-PREDICTIONS.json').read_bytes()
cases = json.loads(input_bytes)['cases']
results = []
start = time.perf_counter_ns()
for case in cases:
    if case['disposition'] != 'solved':
        continue
    contexts = ['none', case['disclosure']] if case['disclosure'] != 'none' else ['none']
    results.append({'id': case['id'], 'conditions': [solve(case['game'], context) for context in contexts]})

receipt = {'source_prediction_sha256': hashlib.sha256(input_bytes).hexdigest(),
           'scipy': __version__, 'wall_seconds': (time.perf_counter_ns() - start) / 1_000_000_000,
           'mathematical_qualification': 'Exact lower and upper values recomputed on all pure plans for the frozen direct interpretations.',
           'cases': results}
output = root / 'DIRECT-LP-RECEIPT.json'
with output.open('x', encoding='utf-8') as stream:
    json.dump(receipt, stream, ensure_ascii=False, indent=2, sort_keys=True)
    stream.write('\n')
print(json.dumps({'evaluated_cases': len(results), 'seconds': receipt['wall_seconds'],
                  'receipt_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                  'exact_values': {case['id']: {item['information']: item['exact_value'] for item in case['conditions']}
                                   for case in results}}))
