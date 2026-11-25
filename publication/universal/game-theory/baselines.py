"""Conventional HiGHS and double-oracle comparisons on the same declared game."""

import argparse
from math import comb
from pathlib import Path
from time import perf_counter

import numpy as np
from scipy.optimize import linprog

from solve import DENOMINATOR, pack, quantize
from verify import exact_bounds, parse_game, read_json, verify, write_json


MATRIX_LIMIT = 250_000
MAX_ITERATIONS = 128


def strategies(budget, lanes):
    if lanes == 1:
        yield (budget,)
        return
    for amount in range(budget + 1):
        for tail in strategies(budget - amount, lanes - 1):
            yield (amount, *tail)


def action_counts(game):
    row = comb(game.budget + game.lanes - 1, game.lanes - 1)
    column = sum(comb(scenario.budget + game.lanes - 1, game.lanes - 1) for scenario in game.scenarios)
    return row, column


def payoff(row, column, weights):
    return sum(weight * ((first > second) - (first < second))
               for first, second, weight in zip(row, column, weights))


def matrix_solution(matrix):
    rows, columns = matrix.shape
    objective = np.zeros(rows + 1)
    objective[-1] = -1
    constraints = np.column_stack((-matrix.T, np.ones(columns)))
    normalization = np.ones(rows + 1)
    normalization[-1] = 0
    result = linprog(objective, A_ub=constraints, b_ub=np.zeros(columns), A_eq=[normalization], b_eq=[1],
                     bounds=[(0, None)] * rows + [(None, None)], method='highs')
    if not result.success:
        raise RuntimeError(f'Restricted HiGHS status {result.status}: {result.message}')
    return quantize(result.x[:-1], DENOMINATOR), quantize(-result.ineqlin.marginals, DENOMINATOR)


def dense(game):
    started = perf_counter()
    row_count, column_count = action_counts(game)
    if row_count * column_count > MATRIX_LIMIT:
        return None, {'method': 'explicit matrix HiGHS', 'status': 'OUTSIDE_REGISTERED_MATRIX_BUDGET',
                      'rows': row_count, 'columns': column_count, 'entry_limit': MATRIX_LIMIT}
    first = list(strategies(game.budget, game.lanes))
    row_vectors = np.asarray(first, dtype=np.int64)
    opponent = []
    matrices = []
    for index, scenario in enumerate(game.scenarios):
        moves = list(strategies(scenario.budget, game.lanes))
        opponent.extend((index, move) for move in moves)
        column_vectors = np.asarray(moves, dtype=np.int64)
        scores = np.zeros((len(first), len(moves)), dtype=float)
        for lane, weight in enumerate(scenario.weights):
            scores += weight * np.sign(row_vectors[:, lane, None] - column_vectors[None, :, lane])
        matrices.append(scores)
    matrix = np.concatenate(matrices, axis=1)
    prepared = perf_counter()
    p, q = matrix_solution(matrix)
    solved = perf_counter()
    certificate = pack(game, dict(zip(first, p)), dict(zip(opponent, q)))
    proof = verify(game, certificate)
    return certificate, {'method': 'explicit matrix HiGHS', 'rows': row_count, 'columns': column_count,
                         'entries': matrix.size, 'prepare_seconds': prepared - started,
                         'solve_seconds': solved - prepared, 'whole_seconds': perf_counter() - started,
                         'verification': proof}


def seeds(budget, lanes):
    moves = {tuple(budget if lane == target else 0 for lane in range(lanes)) for target in range(lanes)}
    base, extra = divmod(budget, lanes)
    moves.add(tuple(base + (lane < extra) for lane in range(lanes)))
    return sorted(moves)


def double_oracle(game):
    started = perf_counter()
    first = seeds(game.budget, game.lanes)
    opponent = [(index, move) for index, scenario in enumerate(game.scenarios)
                for move in seeds(scenario.budget, game.lanes)]
    first_set, opponent_set = set(first), set(opponent)
    matrix = np.asarray([[payoff(row, move, game.scenarios[index].weights) for index, move in opponent]
                         for row in first], dtype=float)
    profiles = []
    status = 'ITERATION_LIMIT'
    for iteration in range(1, MAX_ITERATIONS + 1):
        p, q = matrix_solution(matrix)
        row = {action: mass for action, mass in zip(first, p) if mass}
        column = {action: mass for action, mass in zip(opponent, q) if mass}
        low, column_reply, high, row_reply = exact_bounds(game, row, column)
        profiles.append([iteration, len(first), len(opponent), low, high])
        if (high - low) * 1_000_000 <= DENOMINATOR * game.scale:
            status = 'QUALIFIED'
            break
        new_row = row_reply not in first_set
        new_column = column_reply not in opponent_set
        if not (new_row or new_column):
            status = 'NUMERICAL_STALL'
            break
        if new_row:
            row_scores = [payoff(row_reply, move, game.scenarios[index].weights) for index, move in opponent]
            matrix = np.vstack((matrix, row_scores))
            first.append(row_reply)
            first_set.add(row_reply)
        if new_column:
            index, move = column_reply
            column_scores = [payoff(action, move, game.scenarios[index].weights) for action in first]
            matrix = np.column_stack((matrix, column_scores))
            opponent.append(column_reply)
            opponent_set.add(column_reply)
    certificate = pack(game, row, column)
    proof = verify(game, certificate)
    return certificate, {'method': 'double oracle with exact knapsack deviation search and HiGHS restricted games',
                         'status': status, 'iterations': iteration, 'iteration_limit': MAX_ITERATIONS,
                         'whole_seconds': perf_counter() - started, 'profiles': profiles, 'verification': proof}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('method', choices=('dense', 'double-oracle'))
    parser.add_argument('game', type=Path)
    parser.add_argument('--certificate', type=Path, required=True)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    game = parse_game(read_json(args.game))
    constructor = dense if args.method == 'dense' else double_oracle
    certificate, receipt = constructor(game)
    if certificate is not None:
        write_json(args.certificate, certificate)
    write_json(args.receipt, receipt)


if __name__ == '__main__':
    main()
