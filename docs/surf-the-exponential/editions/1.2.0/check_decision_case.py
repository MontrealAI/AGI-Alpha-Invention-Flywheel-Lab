#!/usr/bin/env python3
"""Independent finite policy oracle and artifact checker. Does not import producer.

It enumerates observation-conditioned policies instead of using intersections to
choose cellwise actions, and separately replays delivered quantities and cash.
Independence means implementation separation, not external empirical validation.
"""
from __future__ import annotations
import argparse
import functools
import hashlib
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def need(ok, why):
    if not ok:
        raise ValueError(why)

def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def canonical_partitions():
    result = []
    for labels in itertools.product(range(3), repeat=3):
        names = {}
        normalized = tuple(names.setdefault(v, len(names)) for v in labels)
        if normalized == labels and normalized not in result:
            result.append(labels)
    return result

def check_relations(r):
    parts = canonical_partitions()
    need(r['partitions'] == [list(p) for p in parts], 'PARTITIONS_CHANGED')
    need(len(r['matrices']) == 512, 'RELATION_DENOMINATOR_CHANGED')
    minima = []
    triple_count = 0
    for mask, record in enumerate(r['matrices']):
        rows = [(mask // (8 ** s)) % 8 for s in range(3)]
        need(record['mask'] == mask and record['rows'] == rows, 'SOURCE_RELATION_CHANGED')
        allowed = [[(rows[s] // (2 ** a)) % 2 == 1 for a in range(3)] for s in range(3)]
        truth = []
        for index, labels in enumerate(parts):
            good = []
            for policy in itertools.product(range(3), repeat=max(labels) + 1):
                if all(allowed[s][policy[labels[s]]] for s in range(3)):
                    good.append(list(policy))
            truth.append(bool(good))
            need(record['witness_policies'][index] in good if good else record['witness_policies'][index] is None,
                 'UNREALIZABLE_POLICY')
        need(record['valid_partitions'] == truth, 'VALIDITY_CHANGED')
        minimum = min((max(p) + 1 for p, good in zip(parts, truth) if good), default=None)
        need(record['minimum_labels'] == minimum, 'MINIMUM_LABEL_COUNT_CHANGED')
        minima.append(minimum)
        invalid = []
        for bits in range(1, 8):
            states = [s for s in range(3) if bits & (1 << s)]
            if not any(all(allowed[s][a] for s in states) for a in range(3)):
                invalid.append(bits)
        minimal = [bits for bits in invalid if not any(other != bits and other & bits == other for other in invalid)]
        expected = sorted(([s for s in range(3) if b & (1 << s)] for b in minimal), key=lambda a: (len(a), a))
        need(record['minimal_incompatible_sets'] == expected, 'INCOMPATIBLE_WITNESS_CHANGED')
        # Independently check hyperedge characterization against policy existence.
        for p, good in zip(parts, truth):
            avoids = all(len({p[s] for s in edge}) > 1 for edge in expected)
            need(avoids == good, 'HYPEREDGE_CRITERION_FAILED')
        triple_count += expected == [[0, 1, 2]]
    expected_summary = {'relations': 512, 'partitions_per_relation': 5, 'checks': 2560,
                        'no_feasible_partition': minima.count(None),
                        'minimum_label_counts': {str(n): minima.count(n) for n in (1, 2, 3)},
                        'three_way_only_obstructions': triple_count}
    need(r['matrix_summary'] == expected_summary, 'MATRIX_SUMMARY_CHANGED')
    need(r['three_way_witness'] == r['matrices'][238], 'THREE_WAY_WITNESS_CHANGED')
    need(expected_summary == {'relations': 512, 'partitions_per_relation': 5, 'checks': 2560,
        'no_feasible_partition': 169, 'minimum_label_counts': {'1': 169, '2': 168, '3': 6},
        'three_way_only_obstructions': 6}, 'REGISTERED_COUNTS_DIFFER')

def action_table(demand, fallback, enabled):
    table = {}
    # Boolean construction, rather than producer's subset enumerator.
    for used in itertools.product((False, True), repeat=3):
        if not any(used):
            continue
        name = ''.join(chr(65 + i) for i, active in enumerate(used) if active)
        produced = tuple(sum(used[i] and i != failed for i in range(3)) for failed in range(3))
        table[name] = (4 * sum(used), produced)
    if enabled:
        table['FALLBACK'] = (demand * fallback, (demand,) * 3)
    return table

@functools.lru_cache(None)
def exhaustive_cost(demand, query_cost, fallback, authorized, enabled):
    """Strong ordinary comparator: enumerate full policies for every channel."""
    table = action_table(demand, fallback, enabled)
    best = None
    for choose in itertools.product((False, True), repeat=len(authorized)):
        probes = tuple(q for q, active in zip(authorized, choose) if active)
        signals = [tuple(failed == q for q in probes) for failed in range(3)]
        cells = sorted(set(signals))
        for policy in itertools.product(sorted(table), repeat=len(cells)):
            schedule = [policy[cells.index(s)] for s in signals]
            if not all(table[schedule[w]][1][w] >= demand for w in range(3)):
                continue
            cost = len(probes) * query_cost + max(table[a][0] for a in schedule)
            if best is None or cost < best:
                best = cost
    return best

def validate_config(c):
    need(set(c) == {'demand', 'query_cost', 'fallback_unit_cost', 'quote', 'opening_cash', 'allowed_queries', 'fallback_available'}, 'CONFIG_FIELDS_CHANGED')
    for k in ('demand', 'query_cost', 'fallback_unit_cost', 'quote', 'opening_cash'):
        need(type(c[k]) is int and c[k] >= 0, 'INVALID_CONFIG_AMOUNT')
    need(c['demand'] in (1, 2) and type(c['fallback_available']) is bool, 'INVALID_CONFIG')
    q = c['allowed_queries']
    need(type(q) is list and all(type(x) is int and x in range(3) for x in q) and q == sorted(set(q)), 'INVALID_QUERY_ACCESS')

def audit_route(c, result):
    validate_config(c)
    best = exhaustive_cost(c['demand'], c['query_cost'], c['fallback_unit_cost'], tuple(c['allowed_queries']), c['fallback_available'])
    need(result['minimum_cost'] == best and result['minimum_prefunding'] == best, 'FALSE_COST_OR_PREFUNDING')
    need(result['channels_examined'] == 2 ** len(c['allowed_queries']), 'OMITTED_CHANNEL')
    if best is None:
        need(result['decision'] == 'NO_TECHNICAL_ROUTE' and result['route'] is None and result['worst_case_surplus'] is None, 'FALSE_FEASIBILITY')
        return
    expected_decision = ('DECLINE_NO_SURPLUS' if c['quote'] - best <= 0 else
                         'DECLINE_UNFUNDED' if c['opening_cash'] < best else 'ADMIT_MODEL_ONLY')
    need(result['decision'] == expected_decision and result['worst_case_surplus'] == c['quote'] - best, 'FALSE_ADMISSION_OR_SURPLUS')
    route = result['route']; probes = route['queries']
    need(probes == sorted(set(probes)) and all(q in c['allowed_queries'] for q in probes), 'UNAUTHORIZED_QUERY')
    signals = [tuple(int(w == q) for q in probes) for w in range(3)]
    labels = sorted(set(signals))
    need(route['signal_labels'] == len(labels), 'SIGNAL_LABELS_CHANGED')
    need([tuple(p['signal']) for p in route['policy']] == labels, 'POLICY_MISSING_OR_DUPLICATED_SIGNAL')
    table = action_table(c['demand'], c['fallback_unit_cost'], c['fallback_available'])
    trace = []
    for w, signal in enumerate(signals):
        action = next(p['action'] for p in route['policy'] if tuple(p['signal']) == signal)
        need(action in table, 'UNCONSTRUCTED_ACTION')
        dispatch_cost, output = table[action]
        spent = len(probes) * c['query_cost'] + dispatch_cost
        need(output[w] >= c['demand'], 'UNFULFILLED_PROMISE')
        trace.append({'state': w, 'signal': list(signal), 'action': action, 'delivered_units': output[w], 'cost': spent})
        if expected_decision == 'ADMIT_MODEL_ONLY':
            cash = c['opening_cash']
            cash -= len(probes) * c['query_cost']; need(cash >= 0, 'UNFUNDED_OBSERVATION')
            cash -= dispatch_cost; need(cash >= 0, 'UNFUNDED_DISPATCH')
            cash += c['quote']; need(cash > c['opening_cash'], 'NONPOSITIVE_PATH_SURPLUS')
    need(route['traces'] == trace and route['maximum_cost'] == best == max(x['cost'] for x in trace), 'TRACE_CHANGED')

def audit(r):
    need(r['schema'] == 'surf/decision-bridge/v1', 'SCHEMA_CHANGED')
    need(r['protocol_sha256'] == digest(r['protocol']), 'PROTOCOL_ID_CHANGED')
    protocol_path = ROOT / 'decision_protocol.json'
    need(r['protocol'] == json.loads(protocol_path.read_text()), 'FROZEN_PROTOCOL_CHANGED')
    check_relations(r)
    need(set(r['cases']) == {'before_frontier', 'after_frontier', 'cash_still_missing', 'redesign_beats_information', 'competition_erases_capture', 'query_access_not_granted', 'changed_successor', 'naive_channel_inheritance', 'successor_without_status_queries'}, 'NAMED_CASES_CHANGED')
    base = dict(demand=1, query_cost=1, fallback_unit_cost=7, quote=6, opening_cash=5, allowed_queries=[0,1,2], fallback_available=True)
    changes = {'before_frontier': {'query_cost':5}, 'after_frontier':{}, 'cash_still_missing':{'opening_cash':4}, 'redesign_beats_information':{'fallback_unit_cost':4}, 'competition_erases_capture':{'quote':4}, 'query_access_not_granted':{'allowed_queries':[]}, 'changed_successor':{'demand':2,'quote':11,'opening_cash':10}, 'naive_channel_inheritance':{'demand':2,'quote':11,'opening_cash':10,'allowed_queries':[0]}, 'successor_without_status_queries':{'demand':2,'quote':11,'opening_cash':10,'allowed_queries':[]}}
    for name, update in changes.items():
        c = {**base, **update}
        need(r['cases'][name]['config'] == c, 'NAMED_SCENARIO_CHANGED')
        audit_route(c, r['cases'][name]['result'])
    expected = list(itertools.product(range(7), (4,5,7,9,12), (1,2), (6,10,14,18), (0,5,12)))
    need(len(r['economic_grid']) == len(expected) == 840, 'ECONOMIC_DENOMINATOR_CHANGED')
    counts = {'cases':840, 'ADMIT_MODEL_ONLY':0, 'DECLINE_NO_SURPLUS':0, 'DECLINE_UNFUNDED':0}
    for row, (q,f,d,p,b) in zip(r['economic_grid'], expected):
        c = {**base, 'query_cost':q, 'fallback_unit_cost':f, 'demand':d, 'quote':p, 'opening_cash':b}
        need(row['config'] == c, 'GRID_INPUT_CHANGED')
        cost = exhaustive_cost(d,q,f,(0,1,2),True)
        decision = 'DECLINE_NO_SURPLUS' if p <= cost else 'DECLINE_UNFUNDED' if b < cost else 'ADMIT_MODEL_ONLY'
        need(row['minimum_cost'] == row['minimum_prefunding'] == cost and row['worst_case_surplus'] == p-cost and row['decision'] == decision, 'GRID_RESULT_CHANGED')
        counts[decision] += 1
    need(r['economic_summary'] == counts, 'ECONOMIC_SUMMARY_CHANGED')
    need(r['scope'] == {'actual_revenue':0, 'empirical_model_trials':0, 'field_qualification':False, 'conventional_optimal_route_can_tie':True, 'improved_discovery_established':False, 'new_capability_delta_measured':False}, 'UNSUPPORTED_CLAIM')
    return {'status':'PASS', 'matrix_checks':2560, 'economic_cases':840, 'named_cases':9,
            'conventional_optimum_agrees':True, 'actual_revenue':0}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence', type=Path, default=ROOT / 'evidence')
    a = p.parse_args()
    r = json.loads((a.evidence / 'decision_results.json').read_text())
    print(json.dumps(audit(r), sort_keys=True))

if __name__ == '__main__':
    main()
