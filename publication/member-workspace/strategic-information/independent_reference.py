# SPDX-License-Identifier: Apache-2.0
from fractions import Fraction
from itertools import combinations, product
from pathlib import Path
import hashlib
import json

import numpy as np
from scipy.optimize import linprog

HERE = Path(__file__).resolve().parent
ONE = Fraction(1)
ZERO = Fraction(0)


def observation_game(game, reveal):
    rows, cols = game['actions']
    states = game['states']
    if reveal:
        states = [
            dict(item, row_type=item['row_type'] + '/' + item['col_type'] if reveal in ('row', 'both') else item['row_type'],
                 col_type=item['col_type'] + '/' + item['row_type'] if reveal in ('column', 'both') else item['col_type'])
            for item in states
        ]
    left = sorted({item['row_type'] for item in states})
    right = sorted({item['col_type'] for item in states})
    concrete = [
        (Fraction(item['p']), left.index(item['row_type']), right.index(item['col_type']),
         [[Fraction(payoff) for payoff in payoffs] for payoffs in item['payoff']])
        for item in states
    ]
    assert all(p > ZERO for p, *_ in concrete)
    assert sum(p for p, *_ in concrete) == ONE
    row_policies = tuple(product(range(rows), repeat=len(left)))
    col_policies = tuple(product(range(cols), repeat=len(right)))
    scores = [
        [sum(p * matrix[row_policy[row]][col_policy[col]] for p, row, col, matrix in concrete)
         for col_policy in col_policies]
        for row_policy in row_policies
    ]
    return left, right, row_policies, col_policies, scores


def solve_basis(equations):
    size = len(equations)
    for column in range(size):
        chosen = next((i for i in range(column, size) if equations[i][column] != ZERO), None)
        if chosen is None:
            return None
        equations[column], equations[chosen] = equations[chosen], equations[column]
        equation = equations[column]
        pivot = equation[column]
        equations[column] = [value / pivot for value in equation]
        for row, entry in enumerate(equations):
            if row != column and entry[column] != ZERO:
                multiple = entry[column]
                equations[row] = [a - multiple * b for a, b in zip(entry, equations[column])]
    return [equation[-1] for equation in equations]


def rational_guarantee(matrix):
    n_rows = len(matrix)
    n_columns = len(matrix[0])
    float_matrix = np.array(matrix, dtype=float)
    result = linprog(np.array([0.] * n_rows + [-1.]),
                     A_ub=np.column_stack((-float_matrix.T, np.ones(n_columns))),
                     b_ub=np.zeros(n_columns),
                     A_eq=np.array([[1.] * n_rows + [0.]]), b_eq=np.array([1.]),
                     bounds=[(0, None)] * n_rows + [(None, None)], method='highs')
    assert result.success, result.message
    probabilities, value = result.x[:-1], result.x[-1]
    support = [j for j, probability in enumerate(probabilities) if probability > 1e-8]
    differences = probabilities @ float_matrix - value
    tight_constraints = [j for j, difference in enumerate(differences) if abs(difference) < 1e-7]
    for active in combinations(tight_constraints, len(support)):
        equations = [[ONE] * len(support) + [ZERO, ONE]]
        equations.extend([matrix[i][j] for i in support] + [-ONE, ZERO] for j in active)
        exact = solve_basis(equations)
        if not exact:
            continue
        positive, guarantee = exact[:-1], exact[-1]
        if min(positive) >= ZERO and all(
            sum(matrix[i][j] * probability for i, probability in zip(support, positive)) >= guarantee
            for j in range(n_columns)
        ):
            assert sum(positive) == ONE
            return {i: p for i, p in zip(support, positive) if p}, guarantee
    raise ValueError('No exact certificate found from the suggested basis')


def verify(game, reveal=None):
    row_types, col_types, row_policies, col_policies, score = observation_game(game, reveal)
    row_mass, row_bound = rational_guarantee(score)
    opponent_score = [[-value for value in column] for column in zip(*score)]
    col_mass, col_negative_bound = rational_guarantee(opponent_score)
    assert row_bound == -col_negative_bound
    row_promise = min(sum(prob * score[i][j] for i, prob in row_mass.items()) for j in range(len(col_policies)))
    col_promise = max(sum(prob * score[i][j] for j, prob in col_mass.items()) for i in range(len(row_policies)))
    assert row_promise == col_promise == row_bound
    distribution = lambda policies, mass: [{'moves': list(policies[index]), 'mass': str(weight)}
                                          for index, weight in sorted(mass.items())]
    public_score = [[str(value) for value in row] for row in score]
    return {'value': str(row_bound), 'row_types': row_types, 'column_types': col_types,
            'pure_policy_matrix_shape': [len(row_policies), len(col_policies)],
            'pure_policy_matrix_sha256': hashlib.sha256(json.dumps(public_score, separators=(',', ':')).encode()).hexdigest(),
            'row_policy_mix': distribution(row_policies, row_mass), 'column_policy_mix': distribution(col_policies, col_mass),
            'row_minimum_achieved': str(row_promise), 'column_maximum_achieved': str(col_promise)}


def main():
    receipt = json.loads((HERE / 'INDEPENDENT-DECLARATIONS.json').read_bytes())
    actual = hashlib.sha256((HERE / 'BRIEFS.json').read_bytes()).hexdigest()
    assert receipt['input_sha256'] == actual
    for key, expected in receipt['cases'].items():
        if expected['verdict'] == 'withhold':
            source = next(case['ambition'] for case in json.loads((HERE / 'BRIEFS.json').read_bytes())['cases'] if case['id'] == key)
            assert expected['source'] in source
            continue
        game = expected['game']
        baseline = expected['normal_form'] = verify(game)
        reveal = expected['counterfactual_reveal']
        if reveal:
            alternate = expected['normal_form_counterfactual'] = verify(game, reveal)
            if reveal == 'column':
                assert Fraction(alternate['value']) <= Fraction(baseline['value'])
    receipt['reference_method'] = ('Enumerate each player’s pure type-conditioned strategies. Solve for candidate supports '
        'with HiGHS. Recover exact Fraction weights and certify both minimax inequalities against all opposing pure strategies.')
    path = HERE / 'INDEPENDENT-REFERENCE.json'
    payload = json.dumps(receipt, ensure_ascii=False, indent=2) + '\n'
    path.write_text(payload, encoding='utf-8')
    print(f"Frozen reference sha256={hashlib.sha256(payload.encode()).hexdigest()} for {len(receipt['cases'])} briefs")


if __name__ == '__main__':
    main()
