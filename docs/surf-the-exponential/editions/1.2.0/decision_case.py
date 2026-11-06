#!/usr/bin/env python3
"""Decision-sufficient evidence and robust redesign: exact, authored finite study.

No LLM, customer, supplier, API or financial account is invoked. Predicate and
production semantics are supplied. The checker deliberately does not import this
module. All prices are arbitrary model units, not quotes or measured costs.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCHEMA = 'surf/decision-bridge/v1'
PROTOCOL = {
    'schema': SCHEMA,
    'states': ['A_down', 'B_down', 'C_down'],
    'state_semantics': 'Exactly one of three sources is unavailable; each other source supplies one unit.',
    'dispatch': 'Prepay four units per reserved source, including a source that proves unavailable. Surplus output is permitted and counted as cost.',
    'observations': 'A chosen subset of truthful source-status predicates is paid and observed before dispatch. This is stipulated access, not a new measured sensor.',
    'fallback': 'A supplied independent route can deliver the whole declared demand, at fallback_unit_cost per delivered unit, in every modeled state.',
    'funding': 'The maximum branch cost must be prefunded; the stated quote arrives only after accepted delivery. No advance, debt, tax, unmodeled support or real trade is simulated.',
    'criterion': 'Minimize maximum complete modeled cost; tie break by fewer predicates, then lexical names and policy. Enter only for strictly positive modeled surplus and sufficient opening cash.',
    'matrix_grid': 'All 512 binary 3-state/3-action admissibility relations, including empty state action sets; all five state partitions.',
    'economic_grid': {'query_cost': list(range(7)), 'fallback_unit_cost': [4, 5, 7, 9, 12], 'demand': [1, 2], 'quote': [6, 10, 14, 18], 'opening_cash': [0, 5, 12]},
    'status': 'Authored exact-model analysis examined during design, not fresh empirical confirmation or autonomous discovery.',
}

def encode(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def digest(x):
    return hashlib.sha256(encode(x)).hexdigest()

def subsets(n):
    return [tuple(i for i in range(n) if mask >> i & 1) for mask in range(1 << n)]

def partitions(n):
    """Restricted-growth strings, canonical labels by first occurrence."""
    if n == 0:
        return [()]
    result = []
    def visit(labels):
        if len(labels) == n:
            result.append(tuple(labels)); return
        for label in range(max(labels) + 2):
            visit(labels + [label])
    visit([0])
    return result

def shared_actions(rows, states):
    common = set(range(3))
    for state in states:
        common &= {a for a in range(3) if rows[state] >> a & 1}
    return sorted(common)

def incompatible_sets(rows):
    bad = []
    for group in sorted(subsets(3)[1:], key=lambda g: (len(g), g)):
        if not shared_actions(rows, group) and not any(set(g).issubset(group) for g in bad):
            bad.append(group)
    return [list(g) for g in bad]

def relation_result(mask):
    rows = tuple((mask >> (3 * s)) & 7 for s in range(3))
    valid = []
    policies = []
    for labels in partitions(3):
        cells = [[s for s in range(3) if labels[s] == label] for label in range(max(labels) + 1)]
        options = [shared_actions(rows, group) for group in cells]
        ok = all(options)
        valid.append(ok)
        policies.append([x[0] for x in options] if ok else None)
    widths = [max(p) + 1 for p, ok in zip(partitions(3), valid) if ok]
    return {'mask': mask, 'rows': list(rows), 'valid_partitions': valid,
            'witness_policies': policies, 'minimum_labels': min(widths) if widths else None,
            'minimal_incompatible_sets': incompatible_sets(rows)}

def config(**updates):
    result = dict(demand=1, query_cost=1, fallback_unit_cost=7, quote=6,
                  opening_cash=5, allowed_queries=[0, 1, 2], fallback_available=True)
    result.update(updates)
    return result

def validate(c):
    required = set(config())
    if type(c) is not dict or set(c) != required:
        raise ValueError('EXACT_CONFIG_REQUIRED')
    for k in ('demand', 'query_cost', 'fallback_unit_cost', 'quote', 'opening_cash'):
        if type(c[k]) is not int or c[k] < 0:
            raise ValueError('NONNEGATIVE_INTEGER_REQUIRED:' + k)
    if c['demand'] not in (1, 2):
        raise ValueError('DECLARED_DEMAND_ONLY')
    q = c['allowed_queries']
    if type(q) is not list or q != sorted(set(q)) or any(type(x) is not int or x not in range(3) for x in q):
        raise ValueError('AUTHORIZED_QUERY_SET_REQUIRED')
    if type(c['fallback_available']) is not bool:
        raise ValueError('EXPLICIT_FALLBACK_ACCESS_REQUIRED')

def actions(c):
    out = []
    for group in subsets(3)[1:]:
        out.append({'name': ''.join('ABC'[i] for i in group), 'sources': list(group),
                    'cost': 4 * len(group), 'capacity': [len(group) - int(s in group) for s in range(3)]})
    if c['fallback_available']:
        out.append({'name': 'FALLBACK', 'sources': [], 'cost': c['demand'] * c['fallback_unit_cost'],
                    'capacity': [c['demand']] * 3})
    return sorted(out, key=lambda a: a['name'])

def channel(q):
    return {s: tuple(int(s == i) for i in q) for s in range(3)}

def construct(c):
    validate(c)
    routes = actions(c)
    candidates = []
    considered = 0
    for local in subsets(len(c['allowed_queries'])):
        q = tuple(c['allowed_queries'][i] for i in local)
        obs = channel(q)
        cells = sorted(set(obs.values()))
        policy = []
        impossible = False
        for signal in cells:
            compatible = [s for s in range(3) if obs[s] == signal]
            suitable = [a for a in routes if all(a['capacity'][s] >= c['demand'] for s in compatible)]
            if not suitable:
                impossible = True; break
            best = min(suitable, key=lambda a: (a['cost'], a['name']))
            policy.append({'signal': list(signal), 'action': best['name']})
        considered += 1
        if impossible:
            continue
        traces = []
        for s in range(3):
            name = next(p['action'] for p in policy if tuple(p['signal']) == obs[s])
            a = next(a for a in routes if a['name'] == name)
            spent = len(q) * c['query_cost'] + a['cost']
            traces.append({'state': s, 'signal': list(obs[s]), 'action': name,
                           'delivered_units': a['capacity'][s], 'cost': spent})
        worst = max(t['cost'] for t in traces)
        key = (worst, len(q), q, tuple(p['action'] for p in policy))
        candidates.append((key, {'queries': list(q), 'policy': policy, 'traces': traces,
                                  'maximum_cost': worst, 'signal_labels': len(cells)}))
    if not candidates:
        return {'decision': 'NO_TECHNICAL_ROUTE', 'route': None, 'minimum_cost': None,
                'minimum_prefunding': None, 'worst_case_surplus': None,
                'channels_examined': considered}
    key, route = min(candidates, key=lambda pair: pair[0])
    worst = key[0]
    # Route selection and commercial admission are separate decisions.
    reason = ('DECLINE_NO_SURPLUS' if c['quote'] <= worst else
              'DECLINE_UNFUNDED' if c['opening_cash'] < worst else 'ADMIT_MODEL_ONLY')
    return {'decision': reason, 'route': route, 'minimum_cost': worst,
            'minimum_prefunding': worst, 'worst_case_surplus': c['quote'] - worst,
            'channels_examined': considered}

def named_cases():
    return {
        'before_frontier': config(query_cost=5),
        'after_frontier': config(),
        'cash_still_missing': config(opening_cash=4),
        'redesign_beats_information': config(fallback_unit_cost=4),
        'competition_erases_capture': config(quote=4),
        'query_access_not_granted': config(allowed_queries=[]),
        'changed_successor': config(demand=2, quote=11, opening_cash=10),
        'naive_channel_inheritance': config(demand=2, quote=11, opening_cash=10, allowed_queries=[0]),
        'successor_without_status_queries': config(demand=2, quote=11, opening_cash=10, allowed_queries=[]),
    }

def study():
    matrices = [relation_result(i) for i in range(512)]
    matrix_summary = {
        'relations': len(matrices), 'partitions_per_relation': len(partitions(3)),
        'checks': len(matrices) * len(partitions(3)),
        'no_feasible_partition': sum(r['minimum_labels'] is None for r in matrices),
        'minimum_label_counts': {str(n): sum(r['minimum_labels'] == n for r in matrices) for n in (1, 2, 3)},
        'three_way_only_obstructions': sum(r['minimal_incompatible_sets'] == [[0, 1, 2]] for r in matrices),
    }
    economic = []
    grid = PROTOCOL['economic_grid']
    for values in itertools.product(*(grid[k] for k in grid)):
        c = config(**dict(zip(grid, values)))
        r = construct(c)
        economic.append({'config': c, 'decision': r['decision'], 'minimum_cost': r['minimum_cost'],
                         'minimum_prefunding': r['minimum_prefunding'], 'worst_case_surplus': r['worst_case_surplus']})
    cases = {k: {'config': c, 'result': construct(c)} for k, c in named_cases().items()}
    # F(A_down)={B,C}, F(B_down)={A,C}, F(C_down)={A,B}.
    threeway = relation_result(6 + (5 << 3) + (3 << 6))
    return {'schema': SCHEMA, 'protocol': PROTOCOL, 'protocol_sha256': digest(PROTOCOL),
            'partitions': [list(p) for p in partitions(3)],
            'matrices': matrices, 'matrix_summary': matrix_summary, 'three_way_witness': threeway,
            'cases': cases, 'economic_grid': economic,
            'economic_summary': {'cases': len(economic), **{k: sum(r['decision'] == k for r in economic) for k in ('ADMIT_MODEL_ONLY', 'DECLINE_NO_SURPLUS', 'DECLINE_UNFUNDED')}},
            'scope': {'actual_revenue': 0, 'empirical_model_trials': 0,
                      'field_qualification': False, 'conventional_optimal_route_can_tie': True,
                      'improved_discovery_established': False,
                      'new_capability_delta_measured': False}}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=ROOT / 'evidence')
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    result = study()
    (a.output / 'decision_results.json').write_bytes(json.dumps(result, indent=2, sort_keys=True).encode() + b'\n')
    print(json.dumps({'matrix': result['matrix_summary'], 'economics': result['economic_summary'],
                      'cases': {k: (v['result']['decision'], v['result']['minimum_cost']) for k, v in result['cases'].items()}}, indent=2))

if __name__ == '__main__':
    main()
