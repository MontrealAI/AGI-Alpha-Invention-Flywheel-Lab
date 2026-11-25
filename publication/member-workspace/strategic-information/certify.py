# SPDX-License-Identifier: Apache-2.0
"""Solve finite zero-sum games with private types and certify the policies."""

from argparse import ArgumentParser
from collections import defaultdict
from fractions import Fraction
import json
from pathlib import Path
import re

from scipy.optimize import linprog
from scipy.sparse import coo_matrix


def rational(value):
    if type(value) is int:
        return Fraction(value)
    if not isinstance(value, str) or not re.fullmatch(r"-?\d+(?:/[1-9]\d*)?", value):
        raise ValueError("Use exact integers or rational strings.")
    return Fraction(value)


def observations(state, disclosure):
    row, col = state["row_type"], state["col_type"]
    return ((row, col) if disclosure in ("row", "both") else (row,),
            (col, row) if disclosure in ("col", "both") else (col,))


def read_game(game, disclosure):
    if disclosure not in ("none", "row", "col", "both"):
        raise ValueError("Declare whose observation rights change.")
    if not isinstance(game, dict) or set(game) != {"actions", "states"}:
        raise ValueError("Declare action counts and chance states.")
    actions = game["actions"]
    if not isinstance(actions, list) or len(actions) != 2 or any(type(n) is not int or n < 1 for n in actions):
        raise ValueError("An ordered action set is required for each player.")
    raw_states = game["states"]
    if not isinstance(raw_states, list) or not raw_states:
        raise ValueError("At least one complete chance state is required.")
    total = Fraction()
    scale = Fraction()
    cells = defaultdict(Fraction)
    rows, columns = set(), set()
    for state in raw_states:
        if not isinstance(state, dict) or set(state) != {"p", "row_type", "col_type", "payoff"}:
            raise ValueError("Every state needs a probability, private types and payoff table.")
        if any(not isinstance(state[key], str) or not state[key].strip() for key in ("row_type", "col_type")):
            raise ValueError("Each private type needs a stable label.")
        p = rational(state["p"])
        if p <= 0:
            raise ValueError("Each included state needs positive probability.")
        payoff = state["payoff"]
        if not isinstance(payoff, list) or len(payoff) != actions[0] or any(
                not isinstance(row, list) or len(row) != actions[1] for row in payoff):
            raise ValueError("Every payoff table must follow the declared action order.")
        total += p
        row_type, col_type = observations(state, disclosure)
        rows.add(row_type)
        columns.add(col_type)
        for i, raw in enumerate(payoff):
            for j, value in enumerate(raw):
                amount = rational(value)
                scale = max(scale, abs(amount))
                cells[row_type, i, col_type, j] += p * amount
    if total != 1:
        raise ValueError("Joint probabilities must sum to one exactly.")
    return actions, sorted(rows), sorted(columns), cells, scale or Fraction(1)


def matrix(entries, shape):
    rows, cols, values = zip(*entries)
    return coo_matrix((values, (rows, cols)), shape=shape).tocsr()


def optimize(player_types, rival_types, actions, rival_actions, cells, scale):
    own = [(label, action) for label in player_types for action in range(actions)]
    rival = [(label, action) for label in rival_types for action in range(rival_actions)]
    indices = {point: index for index, point in enumerate(own)}
    constraints = {point: index for index, point in enumerate(rival)}
    guarantees = {label: len(own) + index for index, label in enumerate(rival_types)}
    count = len(own) + len(rival_types)
    entries = [(constraints[label, j], guarantees[label], 1.0) for label, j in rival]
    entries.extend((constraints[them, j], indices[us, i], -float(amount / scale))
                   for (us, i, them, j), amount in cells.items() if amount)
    equalities = [(index, indices[label, i], 1.0) for index, label in enumerate(player_types) for i in range(actions)]
    result = linprog([0] * len(own) + [-1] * len(rival_types),
                     A_ub=matrix(entries, (len(rival), count)), b_ub=[0] * len(rival),
                     A_eq=matrix(equalities, (len(player_types), count)), b_eq=[1] * len(player_types),
                     bounds=[(0, 1)] * len(own) + [(None, None)] * len(rival_types), method="highs")
    if not result.success:
        raise ValueError("The optimizer did not return a policy.")
    return {label: quantize(result.x[index * actions:(index + 1) * actions])
            for index, label in enumerate(player_types)}


def quantize(values):
    # Normalize first, then round cumulative mass. The final distribution sums to one exactly.
    nonnegative = [max(0.0, float(value)) for value in values]
    total = sum(nonnegative)
    denominator = 10**10
    previous = cumulative = 0
    pieces = []
    for index, value in enumerate(nonnegative):
        cumulative += value
        target = denominator if index == len(nonnegative) - 1 else round(cumulative / total * denominator)
        pieces.append(Fraction(target - previous, denominator))
        previous = target
    return pieces


def bounds(actions, row_types, col_types, cells, row_policy, col_policy):
    gains = {(label, j): Fraction() for label in col_types for j in range(actions[1])}
    losses = {(label, i): Fraction() for label in row_types for i in range(actions[0])}
    for (row, i, col, j), amount in cells.items():
        gains[col, j] += amount * row_policy[row][i]
        losses[row, i] += amount * col_policy[col][j]
    lower = sum(min(gains[col, j] for j in range(actions[1])) for col in col_types)
    upper = sum(max(losses[row, i] for i in range(actions[0])) for row in row_types)
    if lower > upper:
        raise ArithmeticError("The policies produced inconsistent exact bounds.")
    return lower, upper


def certify(game, disclosure="none"):
    actions, rows, cols, cells, scale = read_game(game, disclosure)
    row_policy = optimize(rows, cols, *actions, cells, scale)
    reversed_cells = {(col, j, row, i): -amount for (row, i, col, j), amount in cells.items()}
    col_policy = optimize(cols, rows, *reversed(actions), reversed_cells, scale)
    lower, upper = bounds(actions, rows, cols, cells, row_policy, col_policy)
    return {"disclosure": disclosure, "exact_interval": [str(lower), str(upper)],
            "gap": str(upper - lower), "certificate": "accepted" if upper - lower <= scale / 10**7 else "wide",
            "row_policy": describe(row_policy), "col_policy": describe(col_policy)}


def describe(policy):
    return [{"observed_types": list(label), "probabilities": [str(value) for value in values]}
            for label, values in policy.items()]


def compare(game, disclosure):
    base = certify(game)
    changed = certify(game, disclosure)
    lower, upper = map(Fraction, base["exact_interval"])
    changed_lower, changed_upper = map(Fraction, changed["exact_interval"])
    return {"original": base, "disclosed": changed,
            "change_in_row_value": [str(changed_lower - upper), str(changed_upper - lower)]}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("game", type=Path)
    parser.add_argument("--reveal-to", choices=("row", "col", "both"))
    args = parser.parse_args()
    game = json.loads(args.game.read_text(encoding="utf-8"))
    outcome = compare(game, args.reveal_to) if args.reveal_to else certify(game)
    print(json.dumps(outcome, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
