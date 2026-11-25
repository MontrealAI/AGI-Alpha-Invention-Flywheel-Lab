"""Evaluate the same game by explicit normal form, double oracle, or a public menu."""

import argparse
from dataclasses import replace
from fractions import Fraction
from itertools import product
from math import comb
from pathlib import Path
from time import perf_counter

import numpy as np

from observation import InstrumentPolicy, allocation, exact_bounds, pack, parse_game, verify
from retained_allocation import load
from solve_observation import DENOMINATOR, solve


baseline = load("baselines")
MATRIX_ENTRIES = 250_000
ORACLE_ITERATIONS = 128


def action_counts(game):
    row, column = baseline.action_counts(game.allocation)
    return sum(row ** len(item.signals) for item in game.instruments), column


def payoff(game, row, column):
    option, plans = row
    scenario_index, opponent = column
    instrument = game.instruments[option]
    scenario = game.allocation.scenarios[scenario_index]
    return sum(
        probability * baseline.payoff(plan, opponent, scenario.weights)
        for probability, plan in zip(instrument.probabilities[scenario_index], plans)
    ) - instrument.cost


def mixed_policies(row_actions, row_mass, column_actions, column_mass):
    groups = {}
    for (index, plan), mass in zip(row_actions, row_mass):
        if not mass:
            continue
        if index not in groups:
            groups[index] = InstrumentPolicy(0, tuple({} for _ in plan))
        policy = groups[index]
        policy.mass += mass
        for move, moves in zip(plan, policy.branches):
            moves[move] = moves.get(move, 0) + mass
    return groups, {action: mass for action, mass in zip(column_actions, column_mass) if mass}


def explicit(game, entry_limit=MATRIX_ENTRIES):
    started = perf_counter()
    rows, columns = action_counts(game)
    if rows * columns > entry_limit:
        return None, {
            "method": "explicit normal form HiGHS",
            "status": "OUTSIDE_REGISTERED_MATRIX_BUDGET",
            "row_policies": rows,
            "opponent_actions": columns,
            "matrix_entries": rows * columns,
            "entry_limit": entry_limit,
        }
    base = game.allocation
    moves = list(baseline.strategies(base.budget, base.lanes))
    source = np.asarray(moves, dtype=np.int64)
    adversary = [
        (index, move)
        for index, scenario in enumerate(base.scenarios)
        for move in baseline.strategies(scenario.budget, base.lanes)
    ]
    scenario_indices = [index for index, _ in adversary]
    targets = np.asarray([move for _, move in adversary], dtype=np.int64)
    core = np.zeros((len(moves), columns), dtype=float)
    for lane in range(base.lanes):
        weights = np.asarray([base.scenarios[index].weights[lane] for index in scenario_indices], dtype=float)
        core += np.sign(source[:, lane, None] - targets[None, :, lane]) * weights
    policies = []
    blocks = []
    for index, instrument in enumerate(game.instruments):
        combinations = list(product(range(len(moves)), repeat=len(instrument.signals)))
        coordinates = np.asarray(combinations, dtype=np.intp)
        payoffs = np.full((len(combinations), columns), -float(instrument.cost))
        for signal, _ in enumerate(instrument.signals):
            probabilities = [float(instrument.probabilities[scenario][signal]) for scenario in scenario_indices]
            payoffs += core[coordinates[:, signal], :] * probabilities
        blocks.append(payoffs)
        policies.extend((index, tuple(moves[move] for move in plan)) for plan in combinations)
    matrix = np.concatenate(blocks, axis=0)
    compiled = perf_counter()
    p, q = baseline.matrix_solution(matrix)
    solved = perf_counter()
    row, column = mixed_policies(policies, p, adversary, q)
    certificate = pack(game, row, column, DENOMINATOR)
    proof = verify(game, certificate)
    return certificate, {
        "method": "explicit normal form HiGHS",
        "status": proof["verdict"],
        "row_policies": rows,
        "opponent_actions": columns,
        "matrix_entries": rows * columns,
        "prepare_seconds": compiled - started,
        "solve_seconds": solved - compiled,
        "whole_seconds": perf_counter() - started,
        "verification": proof,
    }


def double_oracle(game, iteration_limit=ORACLE_ITERATIONS):
    started = perf_counter()
    base = game.allocation
    first = [
        (index, (move,) * len(instrument.signals))
        for index, instrument in enumerate(game.instruments)
        for move in baseline.seeds(base.budget, base.lanes)
    ]
    second = [
        (index, move)
        for index, scenario in enumerate(base.scenarios)
        for move in baseline.seeds(scenario.budget, base.lanes)
    ]
    first_set, second_set = set(first), set(second)
    matrix = np.asarray([[payoff(game, row, col) for col in second] for row in first], dtype=float)
    status = "ITERATION_LIMIT"
    for iteration in range(1, iteration_limit + 1):
        p, q = baseline.matrix_solution(matrix)
        row, column = mixed_policies(first, p, second, q)
        lower, next_column, upper, next_row = exact_bounds(game, row, column, DENOMINATOR)
        if (upper - lower) * 1_000_000 <= base.scale:
            status = "QUALIFIED"
            break
        add_row = next_row not in first_set
        add_column = next_column not in second_set
        if not (add_row or add_column):
            status = "NUMERICAL_STALL"
            break
        if iteration == iteration_limit:
            break
        if add_row:
            matrix = np.vstack((matrix, [float(payoff(game, next_row, col)) for col in second]))
            first.append(next_row)
            first_set.add(next_row)
        if add_column:
            matrix = np.column_stack((matrix, [float(payoff(game, item, next_column)) for item in first]))
            second.append(next_column)
            second_set.add(next_column)
    certificate = pack(game, row, column, DENOMINATOR)
    return certificate, {
        "method": "restricted normal forms with exact double-oracle deviations",
        "status": status,
        "iterations": iteration,
        "iteration_limit": iteration_limit,
        "active_row_policies": len(first),
        "active_opponent_actions": len(second),
        "whole_seconds": perf_counter() - started,
        "verification": verify(game, certificate),
    }


def public_menu(game):
    """When the opponent sees the selected instrument it can best respond to it."""
    controls = {}
    for item in game.instruments:
        restricted = replace(game, instruments=(item,))
        certificate, receipt = solve(restricted)
        controls[item.identity] = {
            "model": restricted.document(),
            "certificate": certificate,
            "verification": receipt["verification"],
            "whole_seconds": receipt["whole_seconds"],
        }
    endpoint = lambda name: max(Fraction(item["verification"][name]) for item in controls.values())
    return {
        "method": "separate certified equilibria by publicly announced observation",
        "lower": str(endpoint("lower")),
        "upper": str(endpoint("upper")),
        "instruments": controls,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("method", choices=("dense", "double-oracle", "public-menu"))
    parser.add_argument("game", type=Path)
    parser.add_argument("--certificate", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    game = parse_game(allocation.read_json(args.game))
    if args.method == "public-menu":
        if args.certificate:
            parser.error("The public menu report includes a certificate per announced instrument")
        certificate, receipt = None, public_menu(game)
    else:
        method = explicit if args.method == "dense" else double_oracle
        certificate, receipt = method(game)
    if certificate is not None and args.certificate:
        allocation.write_json(args.certificate, certificate)
    allocation.write_json(args.receipt, receipt)


if __name__ == "__main__":
    main()
