# SPDX-License-Identifier: Apache-2.0
"""Replay the reviewed partition-to-strategy handoff against an independent exact reference."""

import argparse
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import sys
from time import perf_counter, process_time

from curriculum import digest, write_json
from partition import decision_partitions

RETAINED_CERTIFICATION = Path(__file__).resolve().parents[2] / 'member-workspace' / 'strategic-information'
sys.path.insert(0, str(RETAINED_CERTIFICATION))
from certify import certify
from independent_reference import verify


def observation_game(mode):
    disclosure = {
        'early': ('The reserve colour appears only on the planner’s terminal before bids are locked.',
                  {'access': 'known', 'witness': [1]}),
        'late': ('The reserve colour stays locked until both bids are final; the planner receives it after.',
                 {'access': 'hidden', 'witness': [1]}),
        'conditional': ('The planner might receive the reserve colour early, depending on an unrecorded approval.',
                        {'access': 'unclear', 'witness': [1]}),
    }
    report, reviewed = disclosure[mode]
    case = {'id': 'independent-bids-' + mode, 'language': 'en', 'family': 'observation-policy-handoff',
            'rules': [report, 'The competing shipper decides at the same time and cannot read the reserve colour.'],
            'queries': [{'observer': actor, 'decision': 'sealed bid', 'datum': 'reserve colour'}
                        for actor in ('planner', 'shipper')]}
    catalogue = [{'id': 'north', 'signals': {'reserve colour': 'green'}},
                 {'id': 'south', 'signals': {'reserve colour': 'red'}}]
    answers = [reviewed, {'access': 'hidden', 'witness': [2]}]
    if mode == 'early':
        comparator = [[['north'], ['south']], [['north', 'south']]]
    elif mode == 'late':
        comparator = [[['north', 'south']], [['north', 'south']]]
    else:
        comparator = [None, [['north', 'south']]]
    return case, answers, catalogue, comparator


def separate_pairwise_check(classes, histories, separating_condition):
    group = {identifier: index for index, group in enumerate(classes) for identifier in group}
    if set(group) != {history['id'] for history in histories} or sum(map(len, classes)) != len(histories):
        raise AssertionError('Partition does not cover each history exactly once')
    for first, second in combinations(histories, 2):
        if (group[first['id']] == group[second['id']]) == separating_condition(first, second):
            raise AssertionError('Two histories were grouped contrary to direct observation comparison')


def game_document(left, right):
    mapping = lambda partition: {key: f'type{index}' for index, group in enumerate(partition) for key in group}
    row, column = mapping(left), mapping(right)
    matrices = {'north': [[2, -1], [0, 0]], 'south': [[0, 0], [-1, 2]]}
    return {'actions': [2, 2], 'states': [
        {'p': '1/2', 'row_type': row[key], 'col_type': column[key], 'payoff': matrix}
        for key, matrix in matrices.items()]}


def replay():
    start, compute = perf_counter(), process_time()
    records = {}
    for mode, value in (('early', Fraction(1, 2)), ('late', Fraction(1, 4)), ('conditional', None)):
        case, answers, histories, expected = observation_game(mode)
        actual = decision_partitions(case, answers, list(reversed(histories)))
        assert [item.get('classes') for item in actual] == expected
        assert decision_partitions(case, answers, histories) == actual
        assert actual[1]['status'] == 'compiled'
        separate_pairwise_check(actual[1]['classes'], histories, lambda a, b: False)
        record = {'case': case, 'reviewed': answers, 'histories': histories,
                  'partitions': actual, 'separate_observation_reference': expected}
        if value is not None:
            split = mode == 'early'
            separate_pairwise_check(actual[0]['classes'], histories,
                                    lambda a, b: split and a['signals']['reserve colour'] != b['signals']['reserve colour'])
            document = game_document(actual[0]['classes'], actual[1]['classes'])
            evidence, independent = certify(document), verify(document)
            declared = evidence['exact_interval']
            assert evidence['certificate'] == 'accepted' and Fraction(independent['value']) == value
            assert Fraction(declared[0]) <= value <= Fraction(declared[1])
            record.update({'game': document, 'certificate': evidence, 'enumeration_reference': independent,
                           'analytical_value': str(value)})
        else:
            assert actual[0]['status'] == 'withheld'
            record['status'] = 'withheld before policy construction'
        records[mode] = record
    case, answers, histories, _ = observation_game('early')
    wrong = deepcopy(histories)
    wrong[0]['signals'] = {}
    try:
        decision_partitions(case, answers, wrong)
    except ValueError as error:
        assert 'omits a known signal' in str(error)
    else:
        raise AssertionError('Missing declared signal received a policy')
    return {
        'schema': 'frontier/strategic-reviewed-partition-replay/v1',
        'status': 'scoped reviewed partition and certified value',
        'scope': 'Explicit complete access record, finite histories and fixed action sets. Synthetic examples.',
        'independent_reference': 'retained exact rational normal-form enumeration plus explicit pair comparisons',
        'value_of_earlier_disclosure': '1/4', 'incomplete_input_refused': True,
        'code_sha256': {'partition.py': digest(Path(__file__).with_name('partition.py')),
                        'retained_certifier': digest(RETAINED_CERTIFICATION / 'certify.py'),
                        'retained_normal_form': digest(RETAINED_CERTIFICATION / 'independent_reference.py')},
        'records_sha256': sha256(json.dumps(records, sort_keys=True).encode()).hexdigest(),
        'records': records, 'wall_seconds': perf_counter() - start, 'cpu_seconds': process_time() - compute,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    write_json(parser.parse_args().output, replay())
