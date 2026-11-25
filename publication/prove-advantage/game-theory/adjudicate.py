# SPDX-License-Identifier: Apache-2.0
"""Score frozen observation claims against a separately authored reviewed panel."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from curriculum import ACCESS, digest, read_cases, validate_oracle, write_json


def assess(cases, oracle, predictions):
    if set(predictions) != {case['id'] for case in cases} or set(oracle) != set(predictions):
        raise ValueError('Case coverage differs between briefs, predictions and oracle')
    details, groups, all_cases = [], defaultdict(Counter), Counter()
    for case in cases:
        case_id = case['id']
        actual = validate_oracle(case, oracle[case_id])
        proposed = predictions[case_id]
        if not isinstance(proposed, list) or len(proposed) != len(actual):
            raise ValueError(f'Missing query predictions for {case_id}')
        row = Counter(cases=1, queries=len(actual))
        exclusions = []
        for position, (reference, candidate) in enumerate(zip(actual, proposed, strict=True)):
            expected = reference['access']
            if candidate.get('access') not in ACCESS or type(candidate.get('witness')) is not int:
                raise ValueError('Malformed or unsupported prediction')
            label = candidate['access']
            witness = candidate['witness']
            row['label_correct'] += label == expected
            row['cited_correct'] += label == expected and witness in reference['witness']
            row['false_known'] += label == 'known' and expected != 'known'
            row['abstained'] += label == 'unclear'
            if label != expected or witness not in reference['witness']:
                exclusions.append({'query': position + 1, 'oracle': reference, 'predicted': {
                    'access': label, 'witness': witness}})
        row['exact_cases'] = int(not exclusions)
        for bucket in (all_cases, groups[case['language']], groups[case['family']]):
            bucket.update(row)
        details.append({'id': case_id, **row, 'misses': exclusions})
    return {'total': dict(all_cases), 'groups': {name: dict(count) for name, count in groups.items()},
            'cases': details}


def adjudicate(args):
    register = json.loads(args.registration.read_bytes())
    freeze = json.loads(args.held_freeze.read_bytes())
    for path, key in ((args.cases, 'held_cases_sha256'), (args.oracle, 'held_oracle_sha256')):
        if digest(path) != freeze[key]:
            raise ValueError('Held brief or oracle differs from freeze')
    prediction = json.loads(args.predictions.read_bytes())
    if (prediction['cases_sha256'] != digest(args.cases)
            or prediction['held_freeze_sha256'] != digest(args.held_freeze)
            or prediction['registration_sha256'] != digest(args.registration)):
        raise ValueError('Misbound prediction receipt')
    cases = read_cases(args.cases)
    oracle = json.loads(args.oracle.read_bytes())
    arms = {name: assess(cases, oracle, arm['predictions']) for name, arm in prediction['arms'].items()}
    if args.assisted:
        arms['included_codex_direct'] = assess(cases, oracle, json.loads(args.assisted.read_bytes()))
    candidate = arms['adapted_direct']['total']
    baseline = max(arm['total']['exact_cases'] for name, arm in arms.items() if name.startswith('base_'))
    gate = register['primary_go']
    exact_case_improvement = (candidate['exact_cases'] - baseline) / candidate['cases']
    result = {
        'schema': 'frontier/strategic-evidence-pointer-adjudication/v1',
        'source': {name: digest(value) for name, value in (
            ('registration', args.registration), ('held_freeze', args.held_freeze), ('cases', args.cases),
            ('oracle', args.oracle), ('predictions', args.predictions))},
        'arms': arms, 'adapted_exact_case_gain_over_strongest_base': exact_case_improvement,
        'preregistered_model_criteria': {
            'citation': candidate['cited_correct'] / candidate['queries'] >= gate['minimum_cited_query_accuracy'],
            'complete_case': candidate['exact_cases'] / candidate['cases'] >= gate['minimum_exact_case_accuracy'],
            'learned_gain': exact_case_improvement >= gate['minimum_exact_case_improvement_over_strongest_base'],
            'false_known': candidate['false_known'] <= gate['maximum_false_known'],
        },
    }
    if args.assisted:
        result['source']['included_codex_direct'] = digest(args.assisted)
    write_json(args.output, result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('registration', 'held-freeze', 'cases', 'oracle', 'predictions', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--assisted', type=Path)
    adjudicate(parser.parse_args())
