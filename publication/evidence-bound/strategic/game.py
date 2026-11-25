"""Exact environment for buying one public, noisy measurement in a finite game."""

from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import random
import re


ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
DECISIONS = ("BUY", "SKIP")


def digest_document(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256(raw.encode()).hexdigest()


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


@dataclass(frozen=True)
class Game:
    id: str
    payoffs: tuple[tuple[int, int], ...]
    accuracy: tuple[int, int]
    fee: int

    @classmethod
    def from_document(cls, document):
        _require(type(document) is dict and set(document) == {"id", "payoffs", "accuracy", "fee"},
                 "Expected only id, payoffs, accuracy and fee")
        game_id, payoffs = document["id"], document["payoffs"]
        accuracy, fee = document["accuracy"], document["fee"]
        _require(type(game_id) is str and ID.fullmatch(game_id), "Invalid game ID")
        _require(type(payoffs) is list and 2 <= len(payoffs) <= 5, "Expected 2–5 payoff rows")
        for row in payoffs:
            _require(type(row) is list and len(row) == 2 and all(_integer(item, -32, 32) for item in row),
                     "Expected two integer payoffs in [-32, 32] per row")
        _require(type(accuracy) is list and len(accuracy) == 2 and all(_integer(item, 0, 100) for item in accuracy),
                 "Expected two integer accuracy percentages")
        _require(_integer(fee, 0, 32), "Expected a nonnegative integer fee no greater than 32")
        return cls(game_id, tuple(map(tuple, payoffs)), tuple(accuracy), fee)

    def document(self):
        return {"id": self.id, "payoffs": [list(row) for row in self.payoffs],
                "accuracy": list(self.accuracy), "fee": self.fee}

    def likelihood(self, scenario, signal):
        probability = Fraction(self.accuracy[scenario], 100)
        return probability if scenario == signal else 1 - probability

    def vectors(self, decision):
        _require(decision in DECISIONS, "Unknown purchase decision")
        if decision == "SKIP":
            return {(row,): tuple(map(Fraction, values)) for row, values in enumerate(self.payoffs)}
        return {
            (row0, row1): tuple(sum(self.likelihood(scenario, signal) * self.payoffs[row][scenario]
                                   for signal, row in enumerate((row0, row1))) - self.fee
                                for scenario in (0, 1))
            for row0, row1 in product(range(len(self.payoffs)), repeat=2)
        }


@dataclass(frozen=True)
class Bounds:
    value: Fraction
    policy: tuple[tuple[tuple[int, ...], Fraction], ...]
    column0_probability: Fraction

    def document(self):
        return {"value": str(self.value), "column0_probability": str(self.column0_probability),
                "policy": [{"rows": list(rows), "mass": str(mass)} for rows, mass in self.policy]}


def check(game, decision, bounds):
    """Check both exact inequalities against all legal policies."""
    vectors = game.vectors(decision)
    policy = bounds.policy
    _require(bool(policy) and len({key for key, _ in policy}) == len(policy), "Invalid policy support")
    _require(all(key in vectors and mass > 0 for key, mass in policy) and sum(mass for _, mass in policy) == 1,
             "Policy masses must be positive, feasible, and sum to one")
    p = bounds.column0_probability
    _require(0 <= p <= 1, "Invalid adversarial probability")
    lower = min(sum(vectors[key][column] * mass for key, mass in policy) for column in (0, 1))
    upper = max(p * left + (1 - p) * right for left, right in vectors.values())
    _require(lower == bounds.value == upper, "Exact maximin lower and upper bounds must agree")
    return bounds.value


def solve(game, decision):
    """Optimize the convex hull of pure-policy payoff pairs against two columns."""
    vectors = game.vectors(decision)
    point = max(vectors, key=lambda key: min(vectors[key]))
    value, policy = min(vectors[point]), ((point, Fraction(1)),)
    edge_intersections = {Fraction(0), Fraction(1)}
    for (a, (x0, x1)), (b, (y0, y1)) in combinations(vectors.items(), 2):
        slope_a, slope_b = x0 - x1, y0 - y1
        if slope_a == slope_b:
            continue
        if slope_a * slope_b < 0:
            mass = -slope_b / (slope_a - slope_b)
            at_diagonal = mass * x0 + (1 - mass) * y0
            if at_diagonal > value:
                value, policy = at_diagonal, ((a, mass), (b, 1 - mass))
        intersection = (y1 - x1) / (slope_a - slope_b)
        if 0 < intersection < 1:
            edge_intersections.add(intersection)
    p = min(sorted(edge_intersections),
            key=lambda mass: max(mass * left + (1 - mass) * right for left, right in vectors.values()))
    bounds = Bounds(value, policy, p)
    check(game, decision, bounds)
    return bounds


def compare(game):
    bounds = {decision: solve(game, decision) for decision in DECISIONS}
    return ("BUY" if bounds["BUY"].value > bounds["SKIP"].value else "SKIP"), bounds


class PurchaseEnvironment:
    """One strategic decision, followed by an exact worst-case reward.

    Observation exposes the payoff rules, signal channel and fee. There is no
    opponent choice, strategy witness, reference value or label in the input.
    A negative reward measures the exact robust opportunity loss of the choice.
    """

    def __init__(self, game):
        self.game = game
        self._terminal = True

    def reset(self):
        self._terminal = False
        return self.game.document()

    def step(self, decision):
        _require(not self._terminal and decision in DECISIONS, "Expected one valid purchase decision")
        best, bounds = compare(self.game)
        self._terminal = True
        regret = bounds[best].value - bounds[decision].value
        return None, -regret, True, {"accepted": decision == best, "secure_value": str(bounds[decision].value)}


def play(game, decision, policy, seed):
    """Replay one realized episode with hidden adversary and signal draws.

    Use the first worst-case column when tied. See `check` for exact expected
    guarantees. Sampling is deterministic under the provided replay seed.
    """
    vectors = game.vectors(decision)
    _require(all(key in vectors and mass > 0 for key, mass in policy) and sum(mass for _, mass in policy) == 1,
             "Expected a valid announced policy")
    column = min((0, 1), key=lambda index: sum(mass * vectors[key][index] for key, mass in policy))
    rng = random.Random(seed)
    threshold = rng.random()
    cumulative = Fraction(0)
    for rows, mass in policy:
        cumulative += mass
        if threshold < cumulative:
            break
    signal = None if decision == "SKIP" else (0 if rng.randrange(100) < 100 * game.likelihood(column, 0) else 1)
    row = rows[signal or 0]
    payoff = game.payoffs[row][column] - (game.fee if decision == "BUY" else 0)
    return {"column": column, "signal": signal, "row": row, "payoff": payoff}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, f"Repeated JSON field {key}")
        result[key] = value
    return result


def read_games(path):
    games = [Game.from_document(json.loads(row, object_pairs_hook=_unique))
             for row in Path(path).read_text(encoding="utf8").splitlines() if row.strip()]
    _require(bool(games) and len({case.id for case in games}) == len(games), "Expected distinct game identifiers")
    return games
