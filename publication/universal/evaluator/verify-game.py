"""Independent exact verifier and explicit-matrix minimax control for the held games."""

import argparse
from fractions import Fraction
from hashlib import sha256
from math import comb, lcm
from pathlib import Path
from time import perf_counter_ns
import json


def allocations(budget, lanes):
    if lanes == 1:
        yield (budget,)
        return
    for amount in range(budget + 1):
        for remainder in allocations(budget - amount, lanes - 1):
            yield (amount, *remainder)


def ratio(value):
    if type(value) is int or isinstance(value, str):
        return Fraction(value)
    if isinstance(value, list) and len(value) == 2 and all(type(x) is int for x in value):
        return Fraction(*value)
    if isinstance(value, dict) and set(value) == {'numerator', 'denominator'}:
        return Fraction(value['numerator'], value['denominator'])
    raise ValueError('Expected an exact integer ratio, not a floating approximation')


def distribution(raw, budgets, lanes, sided):
    weighted = []
    seen = set()
    for row in raw:
        scenario = row['scenario'] if sided else None
        allocation = tuple(row['allocation'])
        if (len(allocation) != lanes or any(type(item) is not int or item < 0 for item in allocation)
                or scenario not in budgets or sum(allocation) != budgets[scenario]):
            raise ValueError('Infeasible allocation or scenario')
        support_key = scenario, allocation
        if support_key in seen:
            raise ValueError('Duplicate support entry')
        probability = ratio(row['p'])
        if probability <= 0:
            raise ValueError('Support probability must be positive')
        seen.add(support_key)
        weighted.append((scenario, allocation, probability))
    if sum((x[2] for x in weighted), Fraction()) != 1:
        raise ValueError('Probability masses do not sum to one exactly')
    denom = lcm(*(prob.denominator for _, _, prob in weighted))
    return denom, [(s, a, int(p * denom)) for s, a, p in weighted]


def sign(left, right):
    return (left > right) - (left < right)


def exact_bounds(game, proof):
    rows = game['row_budget']
    scenarios = {case['id']: case for case in game['scenarios']}
    lanes = len(game['scenarios'][0]['weights'])
    columns = {name: case['column_budget'] for name, case in scenarios.items()}
    row_denom, row_support = distribution(proof['row_strategy'], {None: rows}, lanes, False)
    col_denom, col_support = distribution(proof['column_strategy'], columns, lanes, True)
    worst_column = {}
    for name, case in scenarios.items():
        tables = [tuple(sum(q * w * sign(a[lane], piece) for _, a, q in row_support)
                        for piece in range(columns[name] + 1)) for lane, w in enumerate(case['weights'])]
        score, allocation = min((sum(t[x] for t, x in zip(tables, action)), action)
                                for action in allocations(columns[name], lanes))
        worst_column[name] = {'payoff': Fraction(score, row_denom), 'allocation': allocation}
    row_tables = [tuple(sum(q * scenarios[name]['weights'][lane] * sign(piece, b[lane])
                            for name, b, q in col_support) for piece in range(rows + 1))
                  for lane in range(lanes)]
    upper, allocation = max((sum(t[x] for t, x in zip(row_tables, action)), action)
                            for action in allocations(rows, lanes))
    low_scenario = min(worst_column, key=lambda key: worst_column[key]['payoff'])
    low, high = worst_column[low_scenario]['payoff'], Fraction(upper, col_denom)
    if low > high:
        raise ValueError('Invalid exact minimax interval')
    threshold = Fraction(max(1, max(sum(x['weights']) for x in scenarios.values())), 1_000_000)
    return {'row_lower': str(low), 'col_upper': str(high), 'width': str(high - low),
            'tolerance': str(threshold), 'passed_gap': high - low <= threshold,
            'row_support': len(row_support), 'column_support': len(col_support),
            'row_deviation_allocation': allocation, 'worst_scenario': low_scenario,
            'column_deviations': {key: {'payoff': str(val['payoff']), 'allocation': val['allocation']}
                                  for key, val in worst_column.items()}}


def matrix_control(game):
    import numpy as np
    from scipy.optimize import linprog

    lanes = len(game['scenarios'][0]['weights'])
    rows = np.array(tuple(allocations(game['row_budget'], lanes)), dtype=np.int64)

    def payoff(case):
        columns = np.array(tuple(allocations(case['column_budget'], lanes)), dtype=np.int64)
        return np.sign(rows[:, None, :] - columns[None, :, :]) @ np.array(case['weights'], dtype=np.int64)

    def value(matrix):
        row_count, column_count = matrix.shape
        constraints = np.column_stack((-matrix.T, np.ones(column_count)))
        solution = linprog(np.append(np.zeros(row_count), -1.), A_ub=constraints,
                           b_ub=np.zeros(column_count), A_eq=[np.append(np.ones(row_count), 0.)],
                           b_eq=[1.], bounds=[(0, None)] * row_count + [(None, None)], method='highs')
        if not solution.success:
            raise ValueError('Complete matrix control could not solve: ' + solution.message)
        return float(solution.x[-1])

    start = perf_counter_ns()
    matrices = [payoff(case) for case in game['scenarios']]
    combined = np.concatenate(matrices, axis=1)
    robust = value(combined)
    unrestricted = {case['id']: value(matrix) for case, matrix in zip(game['scenarios'], matrices)}
    return {'robust_minimax_value': robust, 'scenario_visible_values': unrestricted,
            'matrix_cells': int(combined.size), 'complete_wall_s': (perf_counter_ns() - start) / 1e9}


def inspect_suite(held, proof_file=None):
    raw = held.read_bytes()
    data = json.loads(raw)
    supplied = json.loads(proof_file.read_bytes()) if proof_file else {}
    outcomes = []
    for row in data['cases']:
        identifier, game = row['id'], row['game']
        lanes = len(game['scenarios'][0]['weights'])
        row_count = comb(game['row_budget'] + lanes - 1, lanes - 1)
        column_count = sum(comb(s['column_budget'] + lanes - 1, lanes - 1) for s in game['scenarios'])
        item = {'id': identifier, 'row_actions': row_count, 'column_actions': column_count,
                'implicit_pairs': row_count * column_count}
        if identifier != 'implicit-scale':
            item['highs_full_matrix'] = matrix_control(game)
        if identifier in supplied:
            start = perf_counter_ns()
            item['exact_independent'] = exact_bounds(game, supplied[identifier])
            item['exact_independent']['complete_wall_s'] = (perf_counter_ns() - start) / 1e9
            if 'highs_full_matrix' in item:
                value = item['highs_full_matrix']['robust_minimax_value']
                low, high = (float(Fraction(item['exact_independent'][k])) for k in ('row_lower', 'col_upper'))
                item['agrees_full_matrix'] = low - 1e-8 <= value <= high + 1e-8
        outcomes.append(item)
    return {'held_sha256': sha256(raw).hexdigest(),
            'candidate_proof_sha256': sha256(proof_file.read_bytes()).hexdigest() if proof_file else None,
            'results': outcomes}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('held', type=Path)
    parser.add_argument('--proof', type=Path)
    options = parser.parse_args()
    report = inspect_suite(options.held, options.proof)
    print(json.dumps(report, sort_keys=True, indent=2))
