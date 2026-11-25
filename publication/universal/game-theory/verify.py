"""Independent integer-arithmetic checks for finite allocation-game certificates."""

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path


@dataclass(frozen=True)
class Scenario:
    identity: str
    budget: int
    weights: tuple[int, ...]


@dataclass(frozen=True)
class Game:
    budget: int
    scenarios: tuple[Scenario, ...]

    @property
    def lanes(self):
        return len(self.scenarios[0].weights)

    @property
    def scale(self):
        return max(1, max(sum(scenario.weights) for scenario in self.scenarios))

    def document(self):
        return {'row_budget': self.budget, 'scenarios': [
            {'id': scenario.identity, 'column_budget': scenario.budget, 'weights': list(scenario.weights)}
            for scenario in self.scenarios]}

    def digest(self):
        return sha256(canonical(self.document())).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key {key!r}')
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f'Nonfinite JSON constant {value!r}')


def read_json(path):
    return json.loads(path.read_bytes(), object_pairs_hook=unique_object, parse_constant=reject_constant)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()


def write_json(path, value):
    document = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + '\n'
    if path is None:
        print(document, end='')
    else:
        with path.open('x', encoding='utf-8') as stream:
            stream.write(document)


def fields(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError(f'Expected fields {sorted(expected)}')


def integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f'{label} must be an integer of at least {minimum}')
    return value


def parse_game(value):
    fields(value, ('row_budget', 'scenarios'))
    budget = integer(value['row_budget'], 'row_budget')
    if type(value['scenarios']) is not list or not value['scenarios']:
        raise ValueError('At least one scenario is required')
    known = set()
    scenarios = []
    for item in value['scenarios']:
        fields(item, ('id', 'column_budget', 'weights'))
        identity = item['id']
        if type(identity) is not str or not identity.strip() or identity in known:
            raise ValueError('Scenario identifiers must be nonempty and unique')
        known.add(identity)
        if type(item['weights']) is not list or not item['weights']:
            raise ValueError('At least one lane is required')
        weights = tuple(integer(weight, 'lane weights') for weight in item['weights'])
        if scenarios and len(weights) != len(scenarios[0].weights):
            raise ValueError('Every scenario must have the same lanes')
        scenarios.append(Scenario(identity, integer(item['column_budget'], 'column_budget'), weights))
    return Game(budget, tuple(scenarios))


def marginal_counts(paths, lanes, budget):
    counts = [[0] * (budget + 1) for _ in range(lanes)]
    for allocation, mass in paths:
        for lane, amount in enumerate(allocation):
            counts[lane][amount] += mass
    return counts


def row_against_column_amounts(row_counts, scenario):
    """For each lane and opponent amount, row payoff numerator."""
    result = []
    for counts, weight in zip(row_counts, scenario.weights):
        gains = []
        below, total = 0, sum(counts)
        for used in range(scenario.budget + 1):
            equal = counts[used] if used < len(counts) else 0
            gains.append(weight * (total - 2 * below - equal))
            below += equal
        result.append(gains)
    return result


def column_against_row_amounts(column_counts, game):
    """For each lane and row amount, payoff against the entire adversary mix."""
    result = [[0] * (game.budget + 1) for _ in range(game.lanes)]
    for scenario, count_table in zip(game.scenarios, column_counts):
        for lane, (counts, weight) in enumerate(zip(count_table, scenario.weights)):
            below, total = 0, sum(counts)
            for used in range(game.budget + 1):
                equal = counts[used] if used < len(counts) else 0
                result[lane][used] += weight * (2 * below + equal - total)
                below += equal
    return result


def allocate(scores, budget, *, maximize):
    """Exact best response with the last lane completing the budget."""
    initial = scores[0]
    if len(scores) == 1:
        return initial[budget], (budget,)
    choose = max if maximize else min
    options = [(value, (amount,)) for amount, value in enumerate(initial)]
    for lane in scores[1:]:
        options = [choose((options[cost - used][0] + lane[used], options[cost - used][1] + (used,))
                          for used in range(cost + 1)) for cost in range(budget + 1)]
    return options[budget]


def read_strategy(items, game, *, adversary):
    if type(items) is not list or not items:
        raise ValueError('A strategy must have at least one positive-mass action')
    scenarios = {scenario.identity: index for index, scenario in enumerate(game.scenarios)}
    paths = {}
    for item in items:
        fields(item, ('allocation', 'mass', 'scenario') if adversary else ('allocation', 'mass'))
        allocation = item['allocation']
        if type(allocation) is not list or len(allocation) != game.lanes:
            raise ValueError('An allocation must have one amount per lane')
        path = tuple(integer(amount, 'lane allocation') for amount in allocation)
        if adversary:
            scenario = item['scenario']
            if type(scenario) is not str or scenario not in scenarios:
                raise ValueError('Unknown opponent scenario')
            index = scenarios[scenario]
            limit = game.scenarios[index].budget
            key = index, path
        else:
            limit = game.budget
            key = path
        if sum(path) != limit or key in paths:
            raise ValueError('Budget mismatch or duplicate allocation')
        paths[key] = integer(item['mass'], 'probability mass', 1)
    return paths


def exact_bounds(game, row, column):
    row_counts = marginal_counts(row.items(), game.lanes, game.budget)
    lower_responses = [(allocate(row_against_column_amounts(row_counts, scenario), scenario.budget,
                                 maximize=False), index)
                       for index, scenario in enumerate(game.scenarios)]
    (lower, lower_action), lower_index = min(lower_responses)
    paths_by_scenario = [[] for scenario in game.scenarios]
    for (index, action), mass in column.items():
        paths_by_scenario[index].append((action, mass))
    column_counts = [marginal_counts(paths, game.lanes, scenario.budget)
                     for paths, scenario in zip(paths_by_scenario, game.scenarios)]
    upper, upper_action = allocate(column_against_row_amounts(column_counts, game), game.budget, maximize=True)
    if lower > upper:
        raise ArithmeticError('Strategies gave inconsistent exact bounds')
    return (lower, (lower_index, lower_action), upper, upper_action)


def verify(game, certificate):
    fields(certificate, ('schema', 'game_sha256', 'denominator', 'row', 'column'))
    if certificate['schema'] != 'frontier/strategic-allocation-certificate-v1' or certificate['game_sha256'] != game.digest():
        raise ValueError('The certificate does not match this game')
    denominator = integer(certificate['denominator'], 'probability denominator', 1)
    row = read_strategy(certificate['row'], game, adversary=False)
    column = read_strategy(certificate['column'], game, adversary=True)
    if sum(row.values()) != denominator or sum(column.values()) != denominator:
        raise ValueError('Each strategy must sum to the probability denominator')
    lower, (index, lower_action), upper, upper_action = exact_bounds(game, row, column)
    width = upper - lower
    qualified = width * 1_000_000 <= denominator * game.scale
    return {'scope': 'declared finite zero-sum game and hidden payoff scenarios',
            'game_sha256': game.digest(), 'certificate_sha256': sha256(canonical(certificate)).hexdigest(),
            'denominator': denominator, 'lower_numerator': lower, 'upper_numerator': upper,
            'width_numerator': width, 'scale': game.scale, 'tolerance_parts_per_million': 1,
            'verdict': 'QUALIFIED' if qualified else 'BOUND_ONLY', 'row_support': len(row),
            'column_support': len(column), 'lower_witness': {'scenario': game.scenarios[index].identity,
                                                               'allocation': list(lower_action)},
            'upper_witness': {'allocation': list(upper_action)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('game', type=Path)
    parser.add_argument('certificate', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    write_json(args.output, verify(parse_game(read_json(args.game)), read_json(args.certificate)))


if __name__ == '__main__':
    main()
