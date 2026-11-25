# SPDX-License-Identifier: Apache-2.0
from argparse import ArgumentParser
from copy import deepcopy
from fractions import Fraction
from itertools import product
from math import prod
from pathlib import Path
import hashlib
import importlib.util
import json

from independent_reference import observation_game

HERE = Path(__file__).resolve().parent
ORACLE_SHA256 = 'e0b4dd1736379f68a5f55ddfb7928796673d56e76e4099a9db5393c8f7681411'
CHECKS = {
    'case-03': 'non-zero-sum objectives',
    'case-05': 'observable sequential action and subsequent revision',
    'case-07': 'unaccounted joint types and payoffs for the remaining 3/40',
    'case-10': 'unresolved action axes and payoff sign owner',
    'case-12': 'conflicting observations in two current instructions',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def module_at(path):
    info = importlib.util.spec_from_file_location('candidate_strategy_solver', path)
    module = importlib.util.module_from_spec(info)
    info.loader.exec_module(module)
    return module


def game_signature(game):
    def record(item):
        return (Fraction(item['p']), item['row_type'], item['col_type'],
                tuple(tuple(Fraction(x) for x in row) for row in item['payoff']))
    return (tuple(game['actions']), sorted(record(item) for item in game['states']))


def policy_masses(items, types, actions, plans):
    by_type = {'/'.join(row['observed_types']): tuple(map(Fraction, row['probabilities'])) for row in items}
    assert set(by_type) == set(types) and len(items) == len(types)
    assert all(len(line) == actions and sum(line) == 1 and min(line) >= 0 for line in by_type.values())
    weights = [prod(by_type[observation][action] for observation, action in zip(types, plan)) for plan in plans]
    assert sum(weights) == 1
    return weights


def replay_bounds(game, reveal, candidate, oracle):
    row_types, col_types, row_plans, col_plans, matrix = observation_game(game, reveal)
    left, right = game['actions']
    row_mass = policy_masses(candidate['row_policy'], row_types, left, row_plans)
    col_mass = policy_masses(candidate['col_policy'], col_types, right, col_plans)
    lower = min(sum(weight * matrix[i][j] for i, weight in enumerate(row_mass)) for j in range(len(col_plans)))
    upper = max(sum(weight * matrix[i][j] for j, weight in enumerate(col_mass)) for i in range(len(row_plans)))
    assert list(map(Fraction, candidate['exact_interval'])) == [lower, upper]
    assert lower <= Fraction(oracle['value']) <= upper
    assert Fraction(candidate['gap']) == upper - lower
    return {'reference_value': oracle['value'], 'candidate_interval': list(map(str, (lower, upper))),
            'gap': candidate['gap'], 'all_pure_responses_replayed': True,
            'candidate_verdict': candidate['certificate']}


def rejected_inputs(solver, prototype):
    cases = {}
    for ident, mutate in {
        'no_states': lambda x: x['states'].clear(),
        'boolean_action_count': lambda x: x['actions'].__setitem__(0, True),
        'zero_probability': lambda x: x['states'][0].__setitem__('p', '0'),
        'negative_probability': lambda x: x['states'][0].__setitem__('p', '-1/4'),
        'unnormalized_probability': lambda x: x['states'][0].__setitem__('p', '1/2'),
        'undefined_rational': lambda x: x['states'][0].__setitem__('p', '1/0'),
        'ragged_matrix': lambda x: x['states'][0]['payoff'][0].pop(),
        'float_instead_of_rational': lambda x: x['states'][0]['payoff'][0].__setitem__(0, 0.1),
        'empty_private_type': lambda x: x['states'][0].__setitem__('row_type', ''),
    }.items():
        game = deepcopy(prototype)
        mutate(game)
        try:
            solver.certify(game)
        except ValueError as error:
            cases[ident] = str(error)
        else:
            raise AssertionError(f'Invalid case accepted: {ident}')
    try:
        solver.certify(prototype, 'raw_state')
    except ValueError as error:
        cases['unsupported_disclosure'] = str(error)
    else:
        raise AssertionError('Invalid disclosure accepted')
    return cases


def adjudicate(study, predicted, rationale_accepted):
    inputs = study / 'BRIEFS.json'
    oracle = HERE / 'INDEPENDENT-REFERENCE.json'
    assert digest(oracle) == ORACLE_SHA256
    frozen = load(oracle)
    assert frozen['input_sha256'] == digest(inputs)
    source = {item['id']: item for item in load(inputs)['cases']}
    items = load(predicted)['cases']
    results = {}
    exact_solver = study / 'certify.py'
    solver = module_at(exact_solver)
    assert len({item['id'] for item in items}) == len(items)
    submitted = {item['id']: item for item in items}
    assert set(submitted) <= set(source)
    prototype = None
    for ident, case in source.items():
        expected = frozen['cases'][ident]
        item = submitted.get(ident, {})
        evidence = item.get('evidence', [])
        evidence_exact = isinstance(evidence, list) and bool(evidence) and all(
            isinstance(quote, str) and len(quote.strip()) > 0 and quote in case['ambition'] for quote in evidence
        )
        result = results[ident] = {'language': case['language'], 'evidence_quotes_exact': evidence_exact,
            'number_of_quotes': len(evidence), 'expected_disposition': expected['verdict'],
            'reported_disposition': item.get('disposition'), 'qualified': False}
        if expected['verdict'] == 'withhold':
            result['review_criterion'] = CHECKS[ident]
            rationale_passing = ident in rationale_accepted
            result['grounded_refusal'] = (
                item.get('disposition') == 'withheld' and rationale_passing and not item.get('game') and evidence_exact)
            result['qualified'] = result['grounded_refusal']
            continue
        if item.get('disposition') != 'solved':
            continue
        expected_reveal = expected['counterfactual_reveal']
        declared_reveal = item.get('disclosure', 'none')
        if declared_reveal == 'column':
            declared_reveal = 'col'
        correct_reveal = {'column': 'col', None: 'none'}.get(expected_reveal, expected_reveal) == declared_reveal
        result['disclosure_matches'] = correct_reveal
        try:
            game = item['game']
            result['exact_game_declaration'] = game_signature(game) == game_signature(expected['game'])
            prototype = prototype or game
            if result['exact_game_declaration']:
                if expected_reveal and correct_reveal:
                    comparison = solver.compare(game, declared_reveal)
                    result['baseline'] = replay_bounds(game, None, comparison['original'], expected['normal_form'])
                    result['counterfactual'] = replay_bounds(game, expected_reveal, comparison['disclosed'],
                                                            expected['normal_form_counterfactual'])
                    reference_difference = (Fraction(expected['normal_form_counterfactual']['value'])
                                            - Fraction(expected['normal_form']['value']))
                    difference_interval = list(map(Fraction, comparison['change_in_row_value']))
                    assert difference_interval[0] <= reference_difference <= difference_interval[1]
                    result['change_interval'] = comparison['change_in_row_value']
                    result['reference_change'] = str(reference_difference)
                else:
                    result['baseline'] = replay_bounds(game, None, solver.certify(game), expected['normal_form'])
                if 'counterfactual' in result:
                    certifies = all(result[key]['candidate_verdict'] == 'accepted' for key in ('baseline', 'counterfactual'))
                else:
                    certifies = result['baseline']['candidate_verdict'] == 'accepted'
                result['qualified'] = bool(certifies and evidence_exact and correct_reveal)
        except (ValueError, KeyError, IndexError, AttributeError, TypeError) as error:
            result['error'] = str(error)
    return {'input_sha256': digest(inputs), 'predictions_sha256': digest(predicted), 'sealed_oracle_sha256': ORACLE_SHA256,
            'candidate_solver_sha256': digest(exact_solver),
            'engine_checks': rejected_inputs(solver, prototype) if prototype else {},
            'count_qualified': sum(result['qualified'] for result in results.values()), 'cases': results}


if __name__ == '__main__':
    parser = ArgumentParser(description='Compare a frozen structured prediction with independent exact reference strategies')
    parser.add_argument('study', type=Path)
    parser.add_argument('prediction', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--rationale-passing', nargs='*', default=[])
    args = parser.parse_args()
    scored = adjudicate(args.study, args.prediction, set(args.rationale_passing))
    text = json.dumps(scored, ensure_ascii=False, indent=2) + '\n'
    args.output.write_text(text, encoding='utf-8')
    print(f"Qualified {scored['count_qualified']}/{len(scored['cases'])} with {len(scored['engine_checks'])} input denials")
    for ident, result in scored['cases'].items():
        if 'baseline' in result:
            print(ident, result['baseline']['reference_value'], result['baseline']['candidate_interval'],
                  result.get('reference_change', '-'))
