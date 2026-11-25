"""Verify finite costly-observation strategies by exact best responses."""

import argparse
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import re

from retained_allocation import load


allocation = load("verify")
GAME_SCHEMA = "frontier/costly-observation-game-v1"
CERTIFICATE_SCHEMA = "frontier/costly-observation-certificate-v1"
RATIONAL = re.compile(r"[0-9]+(?:/[1-9][0-9]*|\.[0-9]+)?")
PPM = 1_000_000


@dataclass(frozen=True)
class Instrument:
    identity: str
    cost: Fraction
    signals: tuple[str, ...]
    probabilities: tuple[tuple[Fraction, ...], ...]


@dataclass(frozen=True)
class Game:
    allocation: allocation.Game
    instruments: tuple[Instrument, ...]

    def document(self):
        return {
            "schema": GAME_SCHEMA,
            **self.allocation.document(),
            "instruments": [
                {
                    "id": instrument.identity,
                    "cost": str(instrument.cost),
                    "channel": {
                        scenario.identity: dict(zip(instrument.signals, map(str, probabilities)))
                        for scenario, probabilities in zip(self.allocation.scenarios, instrument.probabilities)
                    },
                }
                for instrument in self.instruments
            ],
        }

    def digest(self):
        return sha256(allocation.canonical(self.document())).hexdigest()


@dataclass
class InstrumentPolicy:
    mass: int
    branches: tuple[dict[tuple[int, ...], int], ...]


def exact_number(value, label):
    if type(value) is int and value >= 0:
        return Fraction(value)
    if type(value) is str and RATIONAL.fullmatch(value):
        return Fraction(value)
    raise ValueError(f"{label} must be a nonnegative integer or exact rational string")


def label(value, kind):
    if type(value) is not str or not value.strip():
        raise ValueError(f"{kind} must be a nonempty string")
    return value


def parse_game(value):
    allocation.fields(value, ("schema", "row_budget", "scenarios", "instruments"))
    if value["schema"] != GAME_SCHEMA:
        raise ValueError("Unsupported game schema")
    base = allocation.parse_game({key: value[key] for key in ("row_budget", "scenarios")})
    if type(value["instruments"]) is not list or not value["instruments"]:
        raise ValueError("Supply at least one observation option")
    scenario_ids = [scenario.identity for scenario in base.scenarios]
    known = set()
    options = []
    for item in value["instruments"]:
        allocation.fields(item, ("id", "cost", "channel"))
        name = label(item["id"], "Option id")
        if name in known:
            raise ValueError("Duplicate observation option")
        known.add(name)
        cost = exact_number(item["cost"], "Observation cost")
        channel = item["channel"]
        allocation.fields(channel, scenario_ids)
        first = channel[scenario_ids[0]]
        if type(first) is not dict or not first:
            raise ValueError("An observation option must have a nonempty signal alphabet")
        signals = tuple(sorted(label(signal, "Signal id") for signal in first))
        probabilities = []
        for scenario in scenario_ids:
            row = channel[scenario]
            allocation.fields(row, signals)
            p = tuple(exact_number(row[signal], "Signal probability") for signal in signals)
            if sum(p) != 1:
                raise ValueError(f"Signal probabilities for {name!r} / {scenario!r} must sum exactly to one")
            probabilities.append(p)
        options.append(Instrument(name, cost, signals, tuple(probabilities)))
    return Game(base, tuple(options))


def pack(game, row, column, denominator):
    return {
        "schema": CERTIFICATE_SCHEMA,
        "game_sha256": game.digest(),
        "denominator": denominator,
        "row": [
            {
                "instrument": game.instruments[index].identity,
                "mass": policy.mass,
                "signals": {
                    signal: [{"allocation": list(path), "mass": mass} for path, mass in sorted(paths.items()) if mass]
                    for signal, paths in zip(game.instruments[index].signals, policy.branches)
                },
            }
            for index, policy in sorted(row.items()) if policy.mass
        ],
        "column": [
            {"scenario": game.allocation.scenarios[index].identity, "allocation": list(path), "mass": mass}
            for (index, path), mass in sorted(column.items()) if mass
        ],
    }


def read_policies(game, certificate):
    allocation.fields(certificate, ("schema", "game_sha256", "denominator", "row", "column"))
    if certificate["schema"] != CERTIFICATE_SCHEMA or certificate["game_sha256"] != game.digest():
        raise ValueError("The certificate does not match this game")
    denominator = allocation.integer(certificate["denominator"], "Probability denominator", 1)
    if type(certificate["row"]) is not list or not certificate["row"]:
        raise ValueError("The row policy must use at least one observation option")
    instrument_indices = {item.identity: index for index, item in enumerate(game.instruments)}
    row = {}
    for policy in certificate["row"]:
        allocation.fields(policy, ("instrument", "mass", "signals"))
        name = label(policy["instrument"], "Policy option id")
        if name not in instrument_indices or instrument_indices[name] in row:
            raise ValueError("Unknown or duplicate policy option")
        index = instrument_indices[name]
        instrument = game.instruments[index]
        mass = allocation.integer(policy["mass"], "Option probability mass", 1)
        allocation.fields(policy["signals"], instrument.signals)
        paths = tuple(
            allocation.read_strategy(policy["signals"][signal], game.allocation, adversary=False)
            for signal in instrument.signals
        )
        if any(sum(branch.values()) != mass for branch in paths):
            raise ValueError("Every conditional flow must carry its option's probability mass")
        row[index] = InstrumentPolicy(mass, paths)
    column = allocation.read_strategy(certificate["column"], game.allocation, adversary=True)
    if sum(policy.mass for policy in row.values()) != denominator or sum(column.values()) != denominator:
        raise ValueError("Both players' probability masses must equal the denominator")
    return denominator, row, column


def lower_response(game, row):
    base = game.allocation
    branches = [
        (game.instruments[index], tuple(
            allocation.marginal_counts(paths.items(), base.lanes, base.budget)
            for paths in policy.branches
        ))
        for index, policy in row.items()
    ]
    cost = sum(game.instruments[index].cost * policy.mass for index, policy in row.items())
    responses = []
    for index, scenario in enumerate(base.scenarios):
        marginal = [[0] * (base.budget + 1) for _ in range(base.lanes)]
        for instrument, branch_counts in branches:
            for probability, counts in zip(instrument.probabilities[index], branch_counts):
                if probability:
                    for lane, lane_counts in enumerate(counts):
                        for amount, mass in enumerate(lane_counts):
                            if mass:
                                marginal[lane][amount] += probability * mass
        scores = allocation.row_against_column_amounts(marginal, scenario)
        gross, reply = allocation.allocate(scores, scenario.budget, maximize=False)
        responses.append((gross - cost, (index, reply)))
    return min(responses)


def upper_response(game, column, denominator):
    base = game.allocation
    paths = [[] for _ in base.scenarios]
    for (index, action), mass in column.items():
        paths[index].append((action, mass))
    unconditional = [
        allocation.column_against_row_amounts(
            [allocation.marginal_counts(paths[index], base.lanes, scenario.budget)],
            allocation.Game(base.budget, (scenario,)),
        )
        for index, scenario in enumerate(base.scenarios)
    ]
    responses = []
    for index, instrument in enumerate(game.instruments):
        gross = 0
        actions = []
        for signal_probabilities in zip(*instrument.probabilities):
            scores = [[0] * (base.budget + 1) for _ in range(base.lanes)]
            for probability, by_lane in zip(signal_probabilities, unconditional):
                if probability:
                    for lane, lane_scores in enumerate(by_lane):
                        for amount, score in enumerate(lane_scores):
                            if score:
                                scores[lane][amount] += probability * score
            branch, move = allocation.allocate(scores, base.budget, maximize=True)
            gross += branch
            actions.append(move)
        responses.append((gross - instrument.cost * denominator, (index, tuple(actions))))
    return max(responses)


def exact_bounds(game, row, column, denominator):
    lower, column_reply = lower_response(game, row)
    upper, row_reply = upper_response(game, column, denominator)
    if lower > upper:
        raise ArithmeticError("Invalid range from the feasible policies")
    return Fraction(lower, denominator), column_reply, Fraction(upper, denominator), row_reply


def verify(game, certificate):
    denominator, row, column = read_policies(game, certificate)
    lower, (scenario_index, column_reply), upper, (option_index, row_reply) = exact_bounds(
        game, row, column, denominator
    )
    width = upper - lower
    opportunity = game.instruments[option_index]
    return {
        "verdict": "QUALIFIED" if width * PPM <= game.allocation.scale else "BOUND_ONLY",
        "lower": str(lower),
        "upper": str(upper),
        "width": str(width),
        "scale": game.allocation.scale,
        "tolerance_parts_per_million": 1,
        "game_sha256": game.digest(),
        "certificate_sha256": sha256(allocation.canonical(certificate)).hexdigest(),
        "instrument_mixture": {
            game.instruments[index].identity: str(Fraction(policy.mass, denominator))
            for index, policy in sorted(row.items())
        },
        "lower_witness": {
            "scenario": game.allocation.scenarios[scenario_index].identity,
            "allocation": list(column_reply),
        },
        "upper_witness": {
            "instrument": opportunity.identity,
            "allocations": dict(zip(opportunity.signals, map(list, row_reply))),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", type=Path)
    parser.add_argument("certificate", type=Path)
    parser.add_argument("--output", type=Path)
    options = parser.parse_args()
    game = parse_game(allocation.read_json(options.game))
    allocation.write_json(options.output, verify(game, allocation.read_json(options.certificate)))


if __name__ == "__main__":
    main()
