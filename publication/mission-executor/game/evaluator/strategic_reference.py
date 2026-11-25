"""Independent normal-form and exact-action reference for finite observation games."""

from __future__ import annotations

import itertools
import math
from fractions import Fraction
from time import perf_counter

import numpy as np
from scipy.optimize import linprog


def actions(lanes: int, budget: int) -> list[tuple[int, ...]]:
    """Enumerate actions by finite Cartesian product, then filter conservation."""
    return [allocation for allocation in itertools.product(range(budget + 1), repeat=lanes)
            if sum(allocation) == budget]


def utility(row: tuple[int, ...], column: tuple[int, ...], weights: list[int]) -> int:
    return sum(weight * ((x > y) - (x < y)) for x, y, weight in zip(row, column, weights))


def model_space(game: dict):
    scenarios = {entry["id"]: entry for entry in game["scenarios"]}
    instruments = {entry["id"]: entry for entry in game["instruments"]}
    lanes = len(next(iter(scenarios.values()))["weights"])
    row_actions = actions(lanes, game["row_budget"])
    column_actions = [
        (scenario, allocation)
        for scenario, entry in scenarios.items()
        for allocation in actions(lanes, entry["column_budget"])
    ]
    signals = {
        instrument: tuple(sorted(next(iter(entry["channel"].values()))))
        for instrument, entry in instruments.items()
    }
    probabilities = {
        instrument: {
            scenario: {signal: Fraction(p) for signal, p in vector.items()}
            for scenario, vector in entry["channel"].items()
        }
        for instrument, entry in instruments.items()
    }
    costs = {instrument: Fraction(entry["cost"]) for instrument, entry in instruments.items()}
    return scenarios, row_actions, column_actions, signals, probabilities, costs


def saddle(matrix: np.ndarray, both_sides: bool = True) -> dict:
    """Primal and dual conventional LP over all explicit pure plans and actions."""
    n_rows, n_cols = matrix.shape
    maximin = linprog(
        np.r_[np.zeros(n_rows), -1.0],
        A_ub=np.column_stack((-matrix.T, np.ones(n_cols))),
        b_ub=np.zeros(n_cols),
        A_eq=np.r_[np.ones(n_rows), 0.0][None, :],
        b_eq=[1.0], bounds=[(0, None)] * n_rows + [(None, None)], method="highs",
    )
    if not maximin.success:
        raise RuntimeError("Conventional maximin failed: " + maximin.message)
    v = float(maximin.x[-1])
    achieved = float(np.min(maximin.x[:-1] @ matrix))
    report = {"maximin":v, "achieved_by_row_policy":achieved}
    if both_sides:
        minimax = linprog(
            np.r_[np.zeros(n_cols), 1.0],
            A_ub=np.column_stack((matrix, -np.ones(n_rows))),
            b_ub=np.zeros(n_rows),
            A_eq=np.r_[np.ones(n_cols), 0.0][None, :],
            b_eq=[1.0], bounds=[(0, None)] * n_cols + [(None, None)], method="highs",
        )
        if not minimax.success:
            raise RuntimeError("Conventional minimax failed: " + minimax.message)
        report.update(minimax=float(minimax.x[-1]),
                      achieved_by_column_policy=float(np.max(matrix @ minimax.x[:-1])))
    return report


def normal_form(game: dict, max_cells: int = 6_000_000) -> dict:
    start = perf_counter()
    scenarios, row, column, signals, probabilities, costs = model_space(game)
    new_rows = {instrument: len(row) ** len(labels) for instrument, labels in signals.items()}
    cells = sum(new_rows.values()) * len(column)
    scale = max(1, *(sum(entry["weights"]) for entry in scenarios.values()))
    report = {
        "raw_row_actions": len(row),
        "row_plans_by_instrument": new_rows,
        "columns": len(column),
        "potential_cells": cells,
        "weight_scale": scale,
        "registered_cell_bound": max_cells,
    }
    if cells > max_cells:
        return {**report, "status":"outside_registered_explicit_matrix_budget",
                "preparation_seconds":perf_counter() - start}

    denominator = math.lcm(
        *(p.denominator for channels in probabilities.values() for row in channels.values() for p in row.values()),
        *(cost.denominator for cost in costs.values()),
    )
    payoff_limit = (scale + max(costs.values(), default=0)) * denominator
    if payoff_limit > 2 ** 52:
        raise OverflowError("Registered cases exceed exact float conversion of the integer payoff lattice")
    board = np.array([[utility(r, c, scenarios[s]["weights"]) for s, c in column] for r in row],
                     dtype=np.int64)
    matrix = np.empty((sum(new_rows.values()), len(column)), dtype=np.float64)
    slices = {}
    start_row = 0
    for instrument, labels in signals.items():
        length = new_rows[instrument]
        allocations_by_signal = np.unravel_index(np.arange(length), (len(row),) * len(labels))
        accumulated = np.full((length, len(column)), -int(costs[instrument] * denominator), dtype=np.int64)
        for signal, allocations in zip(labels, allocations_by_signal):
            multiplier = np.array([int(probabilities[instrument][s][signal] * denominator)
                                   for s, _ in column], dtype=np.int64)
            accumulated += board[allocations, :] * multiplier
        where = slice(start_row, start_row + length)
        slices[instrument] = where
        matrix[where] = accumulated / denominator
        start_row += length
    constructed = perf_counter()
    global_optimum = saddle(matrix)
    optimum_finished = perf_counter()
    visible_scope = {instrument: saddle(matrix[where], False)["maximin"]
                     for instrument, where in slices.items()}
    return {
        **report,
        "status":"computed",
        "scale_denominator":denominator,
        "private_mix":global_optimum,
        "announced_instrument_control":visible_scope,
        "private_mixture_gain":global_optimum["maximin"] - max(visible_scope.values()),
        "preparation_seconds":constructed - start,
        "saddle_seconds":optimum_finished - constructed,
        "announcement_controls_seconds":perf_counter() - optimum_finished,
    }


def _distribution_mass(value):
    if type(value) is not int or value <= 0:
        raise ValueError("Expected a positive integer certificate mass")
    return value


def independent_certificate(game: dict, certificate: dict) -> dict:
    """Read candidate plans as data and compute both best responses exactly."""
    if certificate["schema"] != "frontier/costly-observation-certificate-v1":
        raise ValueError("Unexpected certificate schema")
    scenarios, rows, columns, signals, probabilities, costs = model_space(game)
    denominator = _distribution_mass(certificate["denominator"])
    rowset = set(rows)
    colset = set(columns)
    row_operations = {}
    instrument_payoff = Fraction(0)
    total = 0
    for plan in certificate["row"]:
        instrument = plan["instrument"]
        if instrument in row_operations or instrument not in signals:
            raise ValueError("Unknown or repeated instrument")
        mass = _distribution_mass(plan["mass"])
        total += mass
        instrument_payoff -= costs[instrument] * Fraction(mass, denominator)
        tables = plan["signals"]
        if set(tables) != set(signals[instrument]):
            raise ValueError("Signal coverage differs from the scenario model")
        clean_tables = {}
        for signal, entries in tables.items():
            allocations = {}
            for entry in entries:
                allocation = tuple(entry["allocation"])
                if any(type(x) is not int for x in allocation) or allocation in allocations or allocation not in rowset:
                    raise ValueError("Invalid conditional allocation")
                allocations[allocation] = _distribution_mass(entry["mass"])
            if sum(allocations.values()) != mass:
                raise ValueError("Conditional masses differ from instrument mass")
            clean_tables[signal] = allocations
        row_operations[instrument] = clean_tables
    if total != denominator:
        raise ValueError("Instrument masses do not form a probability distribution")
    adversary = {}
    for point in certificate["column"]:
        allocation = tuple(point["allocation"])
        key = (point["scenario"], allocation)
        if any(type(x) is not int for x in allocation) or key in adversary or key not in colset:
            raise ValueError("Invalid adversary allocation")
        adversary[key] = Fraction(_distribution_mass(point["mass"]), denominator)
    if sum(adversary.values()) != 1:
        raise ValueError("Adversary masses do not form a probability distribution")

    lower_by_action = {}
    for scenario, col in columns:
        weights = scenarios[scenario]["weights"]
        expected = instrument_payoff
        for instrument, tables in row_operations.items():
            for signal, allocations in tables.items():
                expected += probabilities[instrument][scenario][signal] * sum(
                    Fraction(mass, denominator) * utility(row, col, weights)
                    for row, mass in allocations.items()
                )
        lower_by_action[(scenario,col)] = expected
    lower_key = min(lower_by_action, key=lower_by_action.get)
    lower = lower_by_action[lower_key]

    upper_by_instrument = {}
    upper_plans = {}
    for instrument, labels in signals.items():
        instrument_value = -costs[instrument]
        contingent_plan = {}
        for signal in labels:
            values = {
                row: sum(mass * probabilities[instrument][s][signal] * utility(row, col, scenarios[s]["weights"])
                         for (s, col), mass in adversary.items())
                for row in rows
            }
            optimal = max(values, key=values.get)
            instrument_value += values[optimal]
            contingent_plan[signal] = optimal
        upper_by_instrument[instrument] = instrument_value
        upper_plans[instrument] = contingent_plan
    upper_key = max(upper_by_instrument, key=upper_by_instrument.get)
    upper = upper_by_instrument[upper_key]
    if upper < lower:
        raise ValueError("Inconsistent certified bounds")
    return {
        "lower":str(lower),
        "upper":str(upper),
        "width":str(upper-lower),
        "lower_best_adversary":{"scenario":lower_key[0], "allocation":list(lower_key[1])},
        "upper_best_instrument":upper_key,
        "upper_best_contingent_plan":upper_plans[upper_key],
        "upper_by_instrument":{key:str(value) for key,value in upper_by_instrument.items()},
        "row_instrument_count":len(row_operations),
        "column_support":len(adversary),
    }
