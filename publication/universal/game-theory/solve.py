"""Construct certified robust strategies for a finite allocation game."""

import argparse
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

from verify import parse_game, read_json, verify, write_json


DENOMINATOR = 1_000_000_000


class FlowGraph:
    def __init__(self, lanes, budget):
        self.lanes = lanes
        self.budget = budget
        self.edges = []
        self.outgoing = defaultdict(list)
        self.incoming = defaultdict(list)
        self.nodes = [(0, 0)]
        for layer in range(1, lanes):
            self.nodes.extend((layer, amount) for amount in range(budget + 1))
        self.nodes.append((lanes, budget))
        self.indices = {node: number for number, node in enumerate(self.nodes)}
        for lane, start in self.nodes[:-1]:
            targets = (budget,) if lane == lanes - 1 else range(start, budget + 1)
            for stop in targets:
                index = len(self.edges)
                self.edges.append((lane, start, stop))
                self.outgoing[(lane, start)].append(index)
                self.incoming[(lane + 1, stop)].append(index)


class SparseRows:
    def __init__(self):
        self.rows = []
        self.columns = []
        self.data = []
        self.rhs = []

    def add(self, values, rhs=0):
        index = len(self.rhs)
        for column, coefficient in values:
            self.rows.append(index)
            self.columns.append(column)
            self.data.append(coefficient)
        self.rhs.append(rhs)
        return index

    def matrix(self, columns):
        return coo_matrix((self.data, (self.rows, self.columns)), shape=(len(self.rhs), columns)).tocsr()


@dataclass(frozen=True)
class AdversaryVariables:
    graph: FlowGraph
    nodes: int
    contributions: int
    first_arc_row: int
    value_row: int


def quantize(weights, mass):
    """Normalize a float row then use largest remainders for exact integer mass."""
    positive = np.maximum(np.asarray(weights, dtype=float), 0)
    if not np.all(np.isfinite(positive)):
        raise ValueError('Solver returned nonfinite flow')
    if not len(positive):
        raise ValueError('Flow row contains no feasible actions')
    total = positive.sum()
    if total <= 0:
        return [mass] + [0] * (len(positive) - 1)
    float_counts = (positive / total) * mass
    counts = [int(value) for value in float_counts]
    remainder = mass - sum(counts)
    if not 0 <= remainder <= len(counts):
        raise ArithmeticError('Largest-remainder rounding is inconsistent')
    ranked = sorted(range(len(counts)), key=lambda i: (counts[i] - float_counts[i], i))
    for index in ranked[:remainder]:
        counts[index] += 1
    return counts


def integer_paths(graph, weights, mass):
    """Round forward so conservation is exact, then decompose the integer flow."""
    if mass == 0:
        return {}
    node_mass = defaultdict(int, {(0, 0): mass})
    remaining = [0] * len(graph.edges)
    for node in graph.nodes[:-1]:
        if not node_mass[node]:
            continue
        edges = graph.outgoing[node]
        edge_masses = quantize([weights[index] for index in edges], node_mass[node])
        for index, edge_mass in zip(edges, edge_masses):
            lane, start, stop = graph.edges[index]
            remaining[index] = edge_mass
            node_mass[lane + 1, stop] += edge_mass
    paths = defaultdict(int)
    outstanding = mass
    while outstanding:
        prefix = []
        indices = []
        spent = 0
        for lane in range(graph.lanes):
            index = next(i for i in graph.outgoing[lane, spent] if remaining[i] > 0)
            next_spent = graph.edges[index][2]
            prefix.append(next_spent - spent)
            indices.append(index)
            spent = next_spent
        value = min(remaining[i] for i in indices)
        for index in indices:
            remaining[index] -= value
        paths[tuple(prefix)] += value
        outstanding -= value
    return dict(paths)


def pack(game, row, column, denominator=DENOMINATOR):
    return {'schema': 'frontier/strategic-allocation-certificate-v1', 'game_sha256': game.digest(),
            'denominator': denominator,
            'row': [{'allocation': list(path), 'mass': mass} for path, mass in sorted(row.items()) if mass],
            'column': [{'allocation': list(path), 'mass': mass, 'scenario': game.scenarios[index].identity}
                       for (index, path), mass in sorted(column.items()) if mass]}


def compile_game(game):
    row = FlowGraph(game.lanes, game.budget)
    equality, inequalities = SparseRows(), SparseRows()
    for node in row.nodes[:-1]:
        outgoing = [(index, 1) for index in row.outgoing[node]]
        incoming = [(index, -1) for index in row.incoming[node]]
        equality.add(outgoing + incoming, int(node == (0, 0)))
    by_lane_amount = defaultdict(list)
    for index, (lane, start, end) in enumerate(row.edges):
        by_lane_amount[lane, end - start].append(index)
    cumulative = len(row.edges)
    for lane in range(game.lanes):
        for amount in range(game.budget + 1):
            upto = cumulative + lane * (game.budget + 1) + amount
            previous = [(upto - 1, -1)] if amount else []
            equality.add([(upto, 1)] + previous + [(index, -1) for index in by_lane_amount[lane, amount]])
    next_var = cumulative + game.lanes * (game.budget + 1)
    value = next_var
    next_var += 1
    alternatives = []
    for scenario in game.scenarios:
        graph = FlowGraph(game.lanes, scenario.budget)
        nodes = next_var
        contributions = next_var + len(graph.nodes)
        next_var = contributions + game.lanes * (scenario.budget + 1)
        equality.add([(nodes, 1)])
        for lane, weight in enumerate(scenario.weights):
            for amount in range(scenario.budget + 1):
                contribution = contributions + lane * (scenario.budget + 1) + amount
                if amount > game.budget:
                    equality.add([(contribution, 1)], -weight)
                    continue
                upto = cumulative + lane * (game.budget + 1) + amount
                # The payoff is weight × (P(row > amount) − P(row < amount)).
                terms = [(upto, weight)] if weight else []
                if weight and amount:
                    terms.append((upto - 1, weight))
                equality.add([(contribution, 1)] + terms, weight)
        first = len(inequalities.rhs)
        for lane, start, stop in graph.edges:
            before = nodes + graph.indices[lane, start]
            after = nodes + graph.indices[lane + 1, stop]
            contribution = contributions + lane * (scenario.budget + 1) + stop - start
            inequalities.add([(after, 1), (before, -1), (contribution, -1)])
        endpoint = nodes + graph.indices[game.lanes, scenario.budget]
        value_row = inequalities.add([(value, 1), (endpoint, -1)])
        alternatives.append(AdversaryVariables(graph, nodes, contributions, first, value_row))
    objective = np.zeros(next_var)
    objective[value] = -1
    bounds = [(0, None)] * value + [(None, None)] * (next_var - value)
    return row, alternatives, objective, bounds, equality, inequalities


def solve(game):
    started = perf_counter()
    row_graph, alternatives, objective, bounds, eq, binding = compile_game(game)
    variables = len(objective)
    full = {'A_eq': eq.matrix(variables), 'b_eq': eq.rhs, 'A_ub': binding.matrix(variables), 'b_ub': binding.rhs}
    compiled = perf_counter()
    solution = linprog(objective, bounds=bounds, method='highs-ipm', **full)
    solved = perf_counter()
    if not solution.success:
        raise RuntimeError(f'HiGHS status {solution.status}: {solution.message}')
    raw = solution.x[:len(row_graph.edges)]
    row = integer_paths(row_graph, raw, DENOMINATOR)
    multipliers = -solution.ineqlin.marginals
    scenario_masses = quantize([multipliers[item.value_row] for item in alternatives], DENOMINATOR)
    column = {}
    for index, (item, mass) in enumerate(zip(alternatives, scenario_masses)):
        end = item.first_arc_row + len(item.graph.edges)
        paths = integer_paths(item.graph, multipliers[item.first_arc_row:end], mass)
        column.update({(index, path): count for path, count in paths.items()})
    certificate = pack(game, row, column)
    verified = verify(game, certificate)
    complete = perf_counter()
    return certificate, {'method': 'sparse allocation flow and scenario shortest-path LP (HiGHS IPM)',
                         'variables': variables, 'equalities': len(eq.rhs), 'inequalities': len(binding.rhs),
                         'matrix_nonzeros': full['A_eq'].nnz + full['A_ub'].nnz, 'lp_value': -float(solution.fun),
                         'prepare_seconds': compiled - started, 'solve_seconds': solved - compiled,
                         'round_and_verify_seconds': complete - solved, 'whole_seconds': complete - started,
                         'verification': verified}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('game', type=Path)
    parser.add_argument('--certificate', type=Path, required=True)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    certificate, receipt = solve(parse_game(read_json(args.game)))
    write_json(args.certificate, certificate)
    write_json(args.receipt, receipt)


if __name__ == '__main__':
    main()
