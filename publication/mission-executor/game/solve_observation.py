"""Solve a finite strategic allocation game with a private observation menu."""

import argparse
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from time import perf_counter

import numpy as np
from scipy.optimize import linprog

from observation import InstrumentPolicy, allocation, pack, parse_game, verify
from retained_allocation import SOURCE_COMMIT, SOURCE_SHA256, load


retained = load("solve")
DENOMINATOR = retained.DENOMINATOR


@dataclass(frozen=True)
class RowBranch:
    edges: int
    cumulative: int


@dataclass(frozen=True)
class Opponent:
    graph: object
    first_arc: int
    value_row: int


def compile_game(game):
    base = game.allocation
    main = retained.FlowGraph(base.lanes, base.budget)
    eq, ub = retained.SparseRows(), retained.SparseRows()
    instruments = len(game.instruments)
    stride = base.budget + 1
    by_amount = defaultdict(list)
    for index, (lane, low, high) in enumerate(main.edges):
        by_amount[lane, high - low].append(index)

    eq.add([(i, 1) for i in range(instruments)], 1)
    next_variable = instruments
    branch_groups = []
    for instrument_index, instrument in enumerate(game.instruments):
        group = []
        for _ in instrument.signals:
            edge_start = next_variable
            cumulative_start = edge_start + len(main.edges)
            next_variable = cumulative_start + base.lanes * stride
            for node in main.nodes[:-1]:
                flow_out = [(edge_start + i, 1) for i in main.outgoing[node]]
                flow_in = [(edge_start + i, -1) for i in main.incoming[node]]
                source = [(instrument_index, -1)] if node == (0, 0) else []
                eq.add(flow_out + flow_in + source)
            for lane in range(base.lanes):
                for amount in range(stride):
                    index = cumulative_start + lane * stride + amount
                    preceding = [(index - 1, -1)] if amount else []
                    new_mass = [(edge_start + i, -1) for i in by_amount[lane, amount]]
                    eq.add([(index, 1)] + preceding + new_mass)
            group.append(RowBranch(edge_start, cumulative_start))
        branch_groups.append(group)

    scale = max(Fraction(base.scale), *(item.cost for item in game.instruments))
    costs = [(i, float(item.cost / scale)) for i, item in enumerate(game.instruments) if item.cost]
    value = next_variable
    next_variable += 1
    opponents = []
    for scenario_index, scenario in enumerate(base.scenarios):
        graph = retained.FlowGraph(base.lanes, scenario.budget)
        nodes = next_variable
        values = nodes + len(graph.nodes)
        size = scenario.budget + 1
        next_variable = values + base.lanes * size
        eq.add([(nodes, 1)])
        weighted_branches = [
            (branch.cumulative, probability)
            for instrument, branches in zip(game.instruments, branch_groups)
            for branch, probability in zip(branches, instrument.probabilities[scenario_index])
            if probability
        ]
        for lane, weight in enumerate(scenario.weights):
            scaled_weight = float(weight / scale)
            for amount in range(size):
                index = values + lane * size + amount
                if amount > base.budget:
                    eq.add([(index, 1)], -scaled_weight)
                    continue
                terms = [(index, 1)]
                if weight:
                    for start, probability in weighted_branches:
                        coefficient = float(probability * weight / scale)
                        cumulative = start + lane * stride + amount
                        terms.append((cumulative, coefficient))
                        if amount:
                            terms.append((cumulative - 1, coefficient))
                eq.add(terms, scaled_weight)
        first_arc = len(ub.rhs)
        for lane, low, high in graph.edges:
            source = nodes + graph.indices[lane, low]
            target = nodes + graph.indices[lane + 1, high]
            contribution = values + lane * size + high - low
            ub.add([(target, 1), (source, -1), (contribution, -1)])
        last_node = nodes + graph.indices[base.lanes, scenario.budget]
        limit = ub.add([(value, 1), (last_node, -1)] + costs)
        opponents.append(Opponent(graph, first_arc, limit))
    objective = np.zeros(next_variable)
    objective[value] = -1
    bounds = [(0, None)] * value + [(None, None)] * (next_variable - value)
    matrices = {
        "A_eq": eq.matrix(next_variable), "b_eq": eq.rhs,
        "A_ub": ub.matrix(next_variable), "b_ub": ub.rhs,
    }
    return main, branch_groups, opponents, objective, bounds, matrices, scale


def solve(game):
    started = perf_counter()
    graph, branches, opponents, objective, bounds, matrices, scale = compile_game(game)
    compiled = perf_counter()
    solution = linprog(objective, bounds=bounds, method="highs-ipm", **matrices)
    solved = perf_counter()
    if not solution.success:
        raise RuntimeError(f"HiGHS status {solution.status}: {solution.message}")

    denominator = DENOMINATOR
    row_mix = retained.quantize(solution.x[:len(branches)], denominator)
    row = {}
    for index, (group, mass) in enumerate(zip(branches, row_mix)):
        if mass:
            rows = tuple(
                retained.integer_paths(graph, solution.x[branch.edges:branch.edges + len(graph.edges)], mass)
                for branch in group
            )
            row[index] = InstrumentPolicy(mass, rows)

    multipliers = -solution.ineqlin.marginals
    scenario_mix = retained.quantize([multipliers[item.value_row] for item in opponents], denominator)
    column = {}
    for index, (item, mass) in enumerate(zip(opponents, scenario_mix)):
        arc_flow = multipliers[item.first_arc:item.first_arc + len(item.graph.edges)]
        paths = retained.integer_paths(item.graph, arc_flow, mass)
        column.update({(index, path): count for path, count in paths.items()})

    certificate = pack(game, row, column, denominator)
    verified = verify(game, certificate)
    receipt = {
        "method": "sparse allocation flows with costly private observations and HiGHS IPM",
        "retained_source_commit": SOURCE_COMMIT,
        "retained_source_sha256": {name: SOURCE_SHA256[name] for name in ("solve", "verify")},
        "variables": len(objective),
        "equalities": len(matrices["b_eq"]),
        "inequalities": len(matrices["b_ub"]),
        "nonzeros": matrices["A_eq"].nnz + matrices["A_ub"].nnz,
        "lp_value_scaled": -float(solution.fun),
        "payoff_scale": str(scale),
        "prepare_seconds": compiled - started,
        "solve_seconds": solved - compiled,
        "round_and_verify_seconds": perf_counter() - solved,
        "whole_seconds": perf_counter() - started,
        "verification": verified,
    }
    return certificate, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", type=Path)
    parser.add_argument("--certificate", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    options = parser.parse_args()
    game = parse_game(allocation.read_json(options.game))
    certificate, receipt = solve(game)
    allocation.write_json(options.certificate, certificate)
    allocation.write_json(options.receipt, receipt)


if __name__ == "__main__":
    main()
