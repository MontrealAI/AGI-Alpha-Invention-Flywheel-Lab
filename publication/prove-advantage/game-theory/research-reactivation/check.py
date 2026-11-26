# SPDX-License-Identifier: Apache-2.0
"""Replay a source-bound event-order intervention in the retained exact game path."""

import argparse
from collections import deque
from fractions import Fraction
from graphlib import CycleError, TopologicalSorter
from itertools import combinations, permutations
import json
from pathlib import Path
import sys
from time import perf_counter, process_time

import scipy

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
sys.path.insert(0, str(STUDY))

from curriculum import digest, write_json
from replay import certify, decision_partitions, game_document, observation_game, verify


PINNED = {
    'CONFIRMATION-BRIEFS.json': '2acf5f20f86bfd0c1cc2680a03ecc2f205f645d8d29ee13e817f51ec735dbf6d',
    'CONFIRMATION-ORACLE.json': 'f21eea3225905a4a9abd01c0b6ab0b6f433e15ef5a749f0047b43ce55fd28726',
    'PARTITION-REPLAY.json': 'cc3140380862be388d0f728991967a4cbcc56fdbb90fe5bbef5fd0dcee6cd8af',
}

# A receipt is actor-specific effective access. These are reviewed transcriptions,
# with 1-based rule citations from the original briefs, not NLP inference.
CONTRACTS = {
    'order-03': (
        [('quantity readable', 'tally read', 1),
         ('tally read', 'first allocation', 1),
         ('first allocation', 'identity received', 2),
         ('identity received', 'revision', 2)],
        [('quantity readable', 'first allocation', []),
         ('identity received', 'first allocation', []),
         ('correction received', 'revision', [3])]),
    'pupitre-05': (
        [('lot readable', 'set order', 2),
         ('set order', 'reserve code received', 3),
         ('sealed envelope delivered', 'allocate chairs', 4)],
        [('lot readable', 'set order', []),
         ('reserve code received', 'set order', []),
         ('envelope effectively readable', 'allocate chairs', [4])]),
    'cloche-07': (
        [('ticket readable', 'pick route', 1),
         ('pick route', 'bell rings', 1),
         ('pick route', 'flag readable by leader', 2),
         ('bell rings', 'validate journey', 3)],
        [('ticket readable', 'pick route', []),
         ('flag readable by leader', 'pick route', []),
         ('flag readable by controller', 'validate journey', [3])]),
}


def event_graph(events, constraints):
    outgoing = {event: [] for event in events}
    ordering = TopologicalSorter()
    for earlier, later, rule in constraints:
        if earlier not in outgoing or later not in outgoing:
            raise ValueError('Precedence names an undeclared event')
        outgoing[earlier].append((later, rule))
        ordering.add(later, earlier)
    try:
        tuple(ordering.static_order())
    except CycleError as error:
        raise ValueError('Contradictory event precedences') from error
    return outgoing


def proof_path(graph, origin, target):
    queue = deque([(origin, ())])
    seen = {origin}
    while queue:
        event, path = queue.popleft()
        for following, rule in graph[event]:
            if following == target:
                return list(dict.fromkeys((*path, rule)))
            if following not in seen:
                seen.add(following)
                queue.append((following, (*path, rule)))
    return None


def classify(graph, receipt, choice, unresolved):
    if receipt == choice or receipt not in graph or choice not in graph:
        raise ValueError('Declare distinct receipt and binding decision events')
    before = proof_path(graph, receipt, choice)
    if before is not None:
        return {'access': 'known', 'witness': before}
    after = proof_path(graph, choice, receipt)
    if after is not None:
        return {'access': 'hidden', 'witness': after}
    return {'access': 'unclear', 'witness': unresolved}


def reference_orders(events, constraints):
    for order in permutations(events):
        position = {event: rank for rank, event in enumerate(order)}
        if all(position[earlier] < position[later] for earlier, later, _ in constraints):
            yield position


def finite_order_check():
    events = tuple('abcd')
    available = list(combinations(events, 2))
    total = matches = 0
    for mask in range(2 ** len(available)):
        constraints = [(earlier, later, index + 1)
                       for index, (earlier, later) in enumerate(available) if mask & (1 << index)]
        graph = event_graph(events, constraints)
        possible = tuple(reference_orders(events, constraints))
        for receipt, choice in permutations(events, 2):
            seen = {order[receipt] < order[choice] for order in possible}
            label = 'known' if seen == {True} else 'hidden' if seen == {False} else 'unclear'
            matches += classify(graph, receipt, choice, [])['access'] == label
            total += 1
    return {'matches': matches, 'relations': total, 'graphs': 2 ** len(available)}


def compare_reviewed():
    oracle = json.loads((STUDY / 'CONFIRMATION-ORACLE.json').read_bytes())
    records = {}
    false_known = matches = 0
    for name, (edges, queries) in CONTRACTS.items():
        events = {event for left, right, _ in (*edges, *queries) for event in (left, right)}
        graph = event_graph(events, edges)
        actual = [classify(graph, *query) for query in queries]
        for answer, expected in zip(actual, oracle[name], strict=True):
            matches += answer['access'] == expected['access'] and bool(
                set(answer['witness']).intersection(expected['witness']))
            false_known += answer['access'] == 'known' and expected['access'] != 'known'
        records[name] = {'answers': actual, 'reviewed': oracle[name]}
    edges, queries = CONTRACTS['pupitre-05']
    events = {event for left, right, _ in (*edges, *queries) for event in (left, right)}
    withdrawn = classify(event_graph(events, edges), 'sealed envelope delivered', 'allocate chairs', [])
    return {'matched_cited_claims': matches, 'claims': sum(len(queries) for _, queries in CONTRACTS.values()),
            'false_known': false_known, 'cases': records,
            'physical_receipt_substituted': withdrawn, 'reviewed_effective_access': oracle['pupitre-05'][-1]}


def compare_sealed_bids():
    events = ('reserve readable', 'planner bid binds')
    cases = (
        ('early', [(events[0], events[1], 1)], '1/2'),
        ('late', [(events[1], events[0], 1)], '1/4'),
        ('conditional', [], None),
    )
    records = {}
    for mode, edges, expected_value in cases:
        case, reviewed, histories, reference_classes = observation_game(mode)
        candidate = classify(event_graph(events, edges), *events, [1])
        ordinary = decision_partitions(case, reviewed, histories)
        treatment = decision_partitions(case, [candidate, reviewed[1]], histories)
        classes = [row.get('classes') for row in treatment]
        record = {'identical_partitions': classes == reference_classes == [row.get('classes') for row in ordinary],
                  'treatment_access': candidate['access'], 'treatment_status': treatment[0]['status'],
                  'ordinary_status': ordinary[0]['status'], 'expected_value': expected_value}
        if expected_value is not None:
            ordinary_game = game_document(*(row['classes'] for row in ordinary))
            treatment_game = game_document(*classes)
            ordinary_proof = certify(ordinary_game)
            treatment_proof = certify(treatment_game)
            reference = verify(treatment_game)
            exact = reference['value']
            lower, upper = map(Fraction, treatment_proof['exact_interval'])
            record.update({'ordinary_exact_interval': ordinary_proof['exact_interval'],
                           'treatment_exact_interval': treatment_proof['exact_interval'],
                           'exact_reference': exact, 'solver_called': True,
                           'accepted': ordinary_proof['certificate'] == treatment_proof['certificate'] == 'accepted'
                           and ordinary_proof['exact_interval'] == treatment_proof['exact_interval']
                           and lower <= Fraction(exact) <= upper
                           and exact == expected_value
                           == reference['row_minimum_achieved'] == reference['column_maximum_achieved']})
        else:
            record.update({'solver_called': False,
                           'accepted': treatment[0]['status'] == ordinary[0]['status'] == 'withheld'})
        records[mode] = record
    return records


def rejects_cycle():
    try:
        event_graph(('receipt', 'choice'), [('receipt', 'choice', 1), ('choice', 'receipt', 2)])
    except ValueError as error:
        return str(error) == 'Contradictory event precedences'
    return False


def run():
    start, cpu_start = perf_counter(), process_time()
    source_hashes = {name: digest(STUDY / name) for name in PINNED}
    if source_hashes != PINNED:
        raise ValueError('The registered public Game Theory references changed')
    structures = finite_order_check()
    cited = compare_reviewed()
    bids = compare_sealed_bids()
    gates = {
        'finite_order_agreement': structures['matches'] == structures['relations'] == 768,
        'reviewed_cited_claims': cited['matched_cited_claims'] == cited['claims'] == 9 and cited['false_known'] == 0,
        'ordinary_exact_control': all(row['identical_partitions'] and row['accepted'] for row in bids.values()),
        'rejects_contradiction': rejects_cycle(),
        'withdrawal_exposes_false_access': cited['physical_receipt_substituted']['access'] == 'known'
        and cited['reviewed_effective_access']['access'] == 'unclear',
    }
    return {
        'schema': 'frontier/game-theory-event-order-research-v1',
        'scope': 'Strict precedences transcribed by hand. Existing public cases and separately executed exact controls.',
        'lead': 'https://arxiv.org/abs/2611.34656v1',
        'registration_sha256': digest(HERE / 'REGISTRATION.md'),
        'code_sha256': digest(__file__),
        'input_sha256': source_hashes,
        'retained_code_sha256': {name: digest(STUDY / name) for name in
                                 ('curriculum.py', 'partition.py', 'replay.py')},
        'scipy_version': scipy.__version__,
        'gates': gates,
        'finite_orders': structures,
        'reviewed_transcriptions': cited,
        'sealed_bid_control': bids,
        'observed_cost': {'wall_seconds': perf_counter() - start, 'cpu_seconds': process_time() - cpu_start,
                          'model_calls': 0, 'paid_service_calls': 0, 'transcribed_queries': 9,
                          'source_transcription_time': None, 'complete_economic_cost': None},
        'disposition': 'PARTIAL' if all(gates.values()) else 'FAIL',
        'limitation': 'The exact control ties. Equal-content ordinary reachability has the same mechanism. '
                      'Source transcription, live acceptance, training and raw-text generalization were not evaluated.',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', nargs='?', type=Path, help='Receipt path. Omit to write to stdout.')
    options = parser.parse_args()
    result = run()
    if options.output is None:
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    else:
        write_json(options.output, result)
    raise SystemExit(0 if all(result['gates'].values()) else 1)
