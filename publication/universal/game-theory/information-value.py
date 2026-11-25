"""Evaluate exact binary scenario disclosures using the retained allocation solver."""

import argparse
from fractions import Fraction
from itertools import combinations
from pathlib import Path

from solve import solve
from verify import parse_game, read_json, write_json


def evaluate(document):
    scenarios = document['scenarios']
    scenario_count = len(scenarios)
    indices = tuple(range(scenario_count))
    known = {}

    def interval(group):
        if group not in known:
            game = parse_game({'row_budget': document['row_budget'],
                               'scenarios': [scenarios[index] for index in group]})
            certificate, run = solve(game)
            proof = run['verification']
            bounds = tuple(Fraction(proof[f'{end}_numerator'], proof['denominator'])
                           for end in ('lower', 'upper'))
            known[group] = bounds, {'scenario_ids': [item.identity for item in game.scenarios],
                                   'interval': list(map(str, bounds)), 'verification': proof,
                                   'certificate': certificate}
        return known[group][0]

    no_signal = interval(indices)
    full_signal = tuple(min(bound) for bound in zip(*(interval((index,)) for index in indices)))
    design_results = []
    optimum = no_signal
    for length in range(scenario_count - 1):
        for additional in combinations(indices[1:], length):
            left = (0, *additional)
            right = tuple(index for index in indices if index not in left)
            bounds = tuple(min(pair) for pair in zip(interval(left), interval(right)))
            optimum = tuple(max(pair) for pair in zip(optimum, bounds))
            design_results.append({'yes': known[left][1]['scenario_ids'],
                                   'no': known[right][1]['scenario_ids'],
                                   'interval': list(map(str, bounds))})

    return {'policy': 'Choose an allocation after a truthful binary or complete disclosure.',
            'no_signal_interval': list(map(str, no_signal)),
            'best_optional_binary_interval': list(map(str, optimum)),
            'binary_gain_interval': [str(max(0, optimum[0] - no_signal[1])), str(optimum[1] - no_signal[0])],
            'complete_disclosure_interval': list(map(str, full_signal)),
            'evaluated_binary_designs': design_results,
            'subgame_certificates': [entry for _, entry in known.values()]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('game', type=Path)
    parser.add_argument('--output', type=Path)
    options = parser.parse_args()
    game = parse_game(read_json(options.game))
    write_json(options.output, evaluate(game.document()))


if __name__ == '__main__':
    main()
