#!/usr/bin/env python3
"""Offline bounded infrastructure demo; no generated code execution."""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

MAX_INPUT_BYTES = 65536


def read_opportunity(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError('opportunity JSON exceeds 65536-byte limit')
    return json.loads(raw.decode('utf-8'))


POLICIES = ('input_order', 'shortest_first', 'longest_first')
COST_NAMES = ('discovery', 'failed_attempts', 'construction', 'confirmation', 'integration',
              'execution', 'verification', 'human_work', 'maintenance', 'overhead', 'liabilities')
DEVELOPMENT = ((8, 1, 3), (6, 2, 4))
SUCCESSOR = ((9, 2, 5, 1), (3, 7, 2, 6), (4, 4, 1, 8))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate_jobs(jobs):
    if not isinstance(jobs, (list, tuple)) or not 1 <= len(jobs) <= 7:
        raise ValueError('expected 1..7 jobs')
    if any(type(x) is not int or not 1 <= x <= 100 for x in jobs):
        raise ValueError('durations must be integers in 1..100')


def execute(policy, jobs):
    validate_jobs(jobs)
    if policy not in POLICIES:
        raise ValueError('unknown registered policy; arbitrary code forbidden')
    order = list(jobs)
    if policy != 'input_order':
        order.sort(reverse=policy == 'longest_first')
    elapsed = total = 0
    for duration in order:
        elapsed += duration
        total += elapsed
    return {'order': order, 'total_completion_time': total}


def oracle(jobs):
    """Separate exhaustive verifier, bounded to 7! orders."""
    validate_jobs(jobs)
    return min(sum((len(order)-i)*duration for i, duration in enumerate(order))
               for order in itertools.permutations(jobs))


def evaluate(policy, cases):
    if not 1 <= len(cases) <= 16:
        raise ValueError('expected 1..16 cases')
    rows = []
    for case in cases:
        score = execute(policy, case)['total_completion_time']
        best = oracle(case)
        rows.append({'input': list(case), 'candidate': score, 'exhaustive_optimum': best,
                     'competent_baseline': execute('shortest_first', case)['total_completion_time'],
                     'counterexample': score != best})
    return rows


def screen(opportunity):
    required = ('id', 'beneficiary', 'blocked_productive_outcome', 'strongest_complete_alternative',
                'residual_constraint', 'source_evidence', 'evidence_gaps')
    if not isinstance(opportunity, dict) or any(k not in opportunity for k in required):
        raise ValueError('missing opportunity fields: ' + ', '.join(required))
    if any(not isinstance(opportunity[k], str) or not opportunity[k].strip() for k in required[:5]):
        raise ValueError('descriptions must be nonempty strings')
    for key in required[5:]:
        if not isinstance(opportunity[key], list) or not all(isinstance(x, str) for x in opportunity[key]):
            raise ValueError(key + ' must be a list of strings')
    return {'schema_version': 1, 'opportunity_id': opportunity['id'], 'record_valid': True,
            'admission': 'NOT_ADMITTED', 'reason': 'Schema validity is not evidence of demand or a feasibility boundary.'}


def economics(costs):
    if set(costs) != set(COST_NAMES):
        raise ValueError('all lifecycle cost categories required')
    for value in costs.values():
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            raise ValueError('cost must be finite nonnegative number or null')
    return {'currency': 'unspecified', 'costs': costs,
            'complete_cost': None if any(v is None for v in costs.values()) else sum(costs.values()),
            'actual_revenue': None, 'profit': None, 'verdict': 'UNKNOWN',
            'reason': 'No authorized market experiment or complete monetary accounting.'}


def demo(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    protocol = {'schema_version': 1, 'experiment': 'queue_transfer_bootstrap_v1',
        'mode': 'INFRASTRUCTURE_DEMO_ONLY', 'max_jobs': 7, 'max_cases_per_evaluation': 16,
        'candidate_limit': 2, 'evaluator': 'exhaustive_permutation_total_completion_time',
        'baseline': 'shortest_first', 'candidate_ids': ['longest_first', 'shortest_first'],
        'development': DEVELOPMENT, 'successor': SUCCESSOR,
        'confirmation': 'NOT_RUN: public fixtures, not protected holdouts',
        'campaign_error_budget': {'alpha': 0.05, 'allocated': 0.0,
            'claim_status': 'NO_INFERENTIAL_CLAIMS', 'reset_allowed': False}}
    (output / 'protocol.json').write_text(json.dumps(protocol, indent=2) + '\n')
    results = []
    for policy in protocol['candidate_ids']:
        rows = evaluate(policy, DEVELOPMENT)
        failed = any(row['counterexample'] for row in rows)
        results.append({'schema_version': 1, 'candidate_id': policy,
            'protocol_sha256': digest(protocol), 'structural_mapping': {
                'source_domain': 'single-server queue theory',
                'target_domain': 'serial document-check batches (synthetic)',
                'relation': 'One server; order changes total waiting plus processing time',
                'adaptation': {'registered_policy': policy},
                'conditions': ['all jobs ready at zero', 'known durations', 'equal importance', 'no deadlines'],
                'failure_boundary': 'Release times, weights, deadlines, or uncertain durations require new tests.'},
            'development': rows, 'retention': 'FAILED_TRANSFER' if failed else 'VERIFIED_IN_PUBLIC_FIXTURE_SCOPE',
            'counterexamples': [r for r in rows if r['counterexample']],
            'technical_verdict': 'REJECTED' if failed else 'WORKS_IN_FIXTURE_SCOPE',
            'economic': economics(dict.fromkeys(COST_NAMES)), 'successor': None})
    retained = next(r for r in results if r['retention'] == 'VERIFIED_IN_PUBLIC_FIXTURE_SCOPE')
    inherited = evaluate(retained['candidate_id'], SUCCESSOR)
    controls = {name: evaluate('shortest_first', SUCCESSOR)
                for name in ('no_inheritance_competent_solver', 'ordinary_reuse')}
    inherited_total = sum(row['candidate'] for row in inherited)
    strongest_control_total = min(sum(row['candidate'] for row in rows) for rows in controls.values())
    retained['successor'] = {'domain': 'synthetic serial inspection batches',
        'exposure': 'new to selection, but public and not independently protected',
        'inherited': inherited, 'controls': controls,
        'budget': 'same cases, permissions, bounds and exhaustive evaluator for every arm',
        'observed_gain_over_strongest_control': strongest_control_total - inherited_total,
        'causal_successor_benefit_verdict': 'NOT_ESTABLISHED',
        'reason': 'Inherited policy ties competent controls; complete lifecycle costs unknown.'}
    for result in results:
        (output / (result['candidate_id'] + '.json')).write_text(json.dumps(result, indent=2) + '\n')
    summary = {'schema_version': 1, 'mode': protocol['mode'], 'protocol_sha256': digest(protocol),
        'retained_records': len(results), 'technical': 'WORKS_IN_FIXTURE_SCOPE',
        'economically_viable': 'UNKNOWN', 'causally_helps_fresh_successor': 'NOT_ESTABLISHED',
        'blue_sky_admission': 'NOT_ADMITTED', 'limitations': [
            'No autonomous opportunity discovery or general invention demonstrated',
            'No independent external verifier or secret holdout', 'No real demand, revenue, or profit measured',
            'Finite registered policies; no generated Python or shell execution']}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('demo', help='infrastructure test, not Blue Sky admission')
    run.add_argument('--output', required=True)
    check = sub.add_parser('screen', help='validate an unadmitted opportunity record')
    check.add_argument('opportunity')
    args = parser.parse_args()
    try:
        result = demo(args.output) if args.command == 'demo' else screen(read_opportunity(args.opportunity))
    except (ValueError, OSError, RecursionError) as exc:
        parser.exit(2, str(exc) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
