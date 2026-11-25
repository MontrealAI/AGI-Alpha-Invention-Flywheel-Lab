# SPDX-License-Identifier: Apache-2.0
"""Construct an information partition from reviewed observation facts and finite histories."""

import argparse
from collections import defaultdict
import json
from pathlib import Path

from curriculum import validate_case, validate_oracle, write_json


def decision_partitions(case, reviewed, histories):
    """Include only the variables whose pre-decision access was independently reviewed.

    Histories must have the same available action set for each named choice, and the
    case's observation queries must cover everything that could distinguish those
    histories, including any relevant own actions. This function has no authority to
    declare completeness or determine the meaning of source language.
    """
    validate_case(case)
    validate_oracle(case, reviewed)
    if not isinstance(histories, list) or not histories:
        raise ValueError('Supply a nonempty list of possible histories')
    paths = {}
    for history in histories:
        if set(history) != {'id', 'signals'} or not isinstance(history['id'], str) or not history['id'].strip():
            raise ValueError('A history requires an ID and a signal record')
        if history['id'] in paths:
            raise ValueError('Duplicate history identifier')
        signals = history['signals']
        if not isinstance(signals, dict) or any(
                not name.strip() or type(value) not in (str, int, bool) for name, value in signals.items()):
            raise ValueError('Use named categorical signal values')
        paths[history['id']] = signals
    observations = defaultdict(dict)
    for query, answer in zip(case['queries'], reviewed, strict=True):
        key = (query['observer'], query['decision'])
        datum = query['datum']
        if datum in observations[key]:
            raise ValueError('Repeated observation declaration')
        observations[key][datum] = answer
    result = []
    for (actor, choice), answers in observations.items():
        admitted = [datum for datum, answer in answers.items() if answer['access'] == 'known']
        unresolved = [datum for datum, answer in answers.items() if answer['access'] == 'unclear']
        receipt = {'observer': actor, 'decision': choice, 'reviewed_claims': answers, 'visible_signals': admitted}
        if unresolved:
            result.append({**receipt, 'status': 'withheld', 'unresolved_signals': unresolved})
            continue
        groups = defaultdict(list)
        for identifier, path in sorted(paths.items()):
            if any(datum not in path for datum in admitted):
                raise ValueError(f'History {identifier} omits a known signal')
            key = tuple((type(path[datum]).__name__, path[datum]) for datum in admitted)
            groups[key].append(identifier)
        result.append({**receipt, 'status': 'compiled', 'classes': sorted(groups.values())})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='JSON containing case, independently reviewed claims, histories')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    inputs = json.loads(args.input.read_bytes())
    partitions = decision_partitions(inputs['case'], inputs['reviewed'], inputs['histories'])
    write_json(args.output, {'case_id': inputs['case']['id'], 'decisions': partitions})
