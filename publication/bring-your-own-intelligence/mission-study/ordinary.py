# SPDX-License-Identifier: Apache-2.0
"""Direct standard-library minimax-regret allocation for a registered rehearsal case."""

from itertools import product


def _rows(tables, name, columns, minimum, maximum):
    rows = tables[name]
    if type(rows) is not list or not minimum <= len(rows) <= maximum:
        raise ValueError(name)
    expected = set(columns)
    if any(type(row) is not dict or row.keys() != expected for row in rows):
        raise ValueError(name)
    return rows


def _identifier(value):
    if type(value) is not str or not 1 <= len(value.encode("utf-8")) <= 64:
        raise ValueError("identifier")
    return value


def _integer(value, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("quantity")
    return value


def _read_snapshot(tables):
    if type(tables) is not dict or tables.keys() != {"budget", "groups", "scenarios", "forecasts"}:
        raise ValueError("snapshot tables")
    [budget] = _rows(tables, "budget", ("total_slots",), 1, 1)
    limit = _integer(budget["total_slots"], 8)

    groups = {}
    for row in _rows(tables, "groups", ("group_id", "min_slots", "max_slots"), 1, 3):
        group = _identifier(row["group_id"])
        low = _integer(row["min_slots"], 8)
        high = _integer(row["max_slots"], 8)
        if group in groups or low > high:
            raise ValueError("group bounds")
        groups[group] = range(low, high + 1)

    scenario_rows = _rows(tables, "scenarios", ("scenario_id",), 1, 4)
    scenarios = sorted({_identifier(row["scenario_id"]) for row in scenario_rows})
    if len(scenarios) != len(scenario_rows):
        raise ValueError("duplicate scenario")

    demands = {}
    group_order = sorted(groups)
    grid = list(product(scenarios, group_order))
    for row in _rows(tables, "forecasts", ("scenario_id", "group_id", "demand"), 0, len(grid)):
        pair = (_identifier(row["scenario_id"]), _identifier(row["group_id"]))
        if pair in demands or pair not in grid:
            raise ValueError("forecast pair")
        demand = row["demand"]
        demands[pair] = None if demand is None else _integer(demand, 1_000_000)
    return limit, groups, group_order, scenarios, grid, demands


def _disposition(status, scenario=None, group=None):
    return [status, scenario, group] + [None] * 10


def solve(tables):
    """Return sorted group/scenario evidence rows or a disposition without allocation."""
    try:
        limit, groups, group_order, scenarios, grid, demands = _read_snapshot(tables)
    except ValueError:
        return [_disposition("INVALID_INPUT")]

    missing = [_disposition("MISSING_FORECAST", *pair) for pair in grid if demands.get(pair) is None]
    if missing:
        return missing

    def served(allocation, scenario):
        return tuple(min(slots, demands[scenario, group]) for slots, group in zip(allocation, group_order))

    totals = {}
    for allocation in product(*(groups[group] for group in group_order)):
        if sum(allocation) <= limit:
            totals[allocation] = tuple(sum(served(allocation, scenario)) for scenario in scenarios)
    if not totals:
        return [_disposition("INFEASIBLE_MINIMA")]

    oracles = [min(totals, key=lambda allocation: (-totals[allocation][index], allocation))
               for index in range(len(scenarios))]
    best_service_by_scenario = tuple(totals[allocation][index] for index, allocation in enumerate(oracles))

    def objective(allocation):
        service = totals[allocation]
        worst_regret = max(best - actual for best, actual in zip(best_service_by_scenario, service))
        return worst_regret, -sum(service), allocation

    selected = min(totals, key=objective)
    worst_regret, negative_total_served, _ = objective(selected)
    rows = []
    for index, scenario in enumerate(scenarios):
        oracle = oracles[index]
        observed = served(selected, scenario)
        attainable = served(oracle, scenario)
        regret = sum(attainable) - sum(observed)
        for group_index, group in enumerate(group_order):
            demand = demands[scenario, group]
            service = observed[group_index]
            oracle_service = attainable[group_index]
            rows.append(["OK", scenario, group, selected[group_index], demand, service, demand - service,
                         oracle[group_index], oracle_service, oracle_service - service,
                         regret, worst_regret, -negative_total_served])
    return rows
