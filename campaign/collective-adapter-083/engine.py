"""Finite authored collective-commissioning construction; never real commerce."""
import hashlib
import itertools
import json
from pathlib import Path

SCHEMA = 'agi-alpha/collective-adapter-083/v1'


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def digest(value):
    return hashlib.sha256(wire(value)).hexdigest()


def fixtures():
    people = [
        {'id': 'alpha', 'fields': {'event_type': 'kind', 'measurement': 'value'}, 'value': 120, 'outside': 0, 'budget': 120, 'consent': True, 'rights': True, 'tests': [{'input': {'kind': 'temp', 'value': 12}, 'expected': {'event_type': 'temp', 'measurement': 12}}, {'input': {'kind': 'pressure', 'value': 7}, 'expected': {'event_type': 'pressure', 'measurement': 7}}]},
        {'id': 'beta', 'fields': {'event_type': 'action', 'measurement': 'count'}, 'value': 120, 'outside': 0, 'budget': 120, 'consent': True, 'rights': True, 'tests': [{'input': {'action': 'heat', 'count': 3}, 'expected': {'event_type': 'heat', 'measurement': 3}}, {'input': {'action': 'cool', 'count': 4}, 'expected': {'event_type': 'cool', 'measurement': 4}}]},
        {'id': 'gamma', 'fields': {'event_type': 'tag', 'measurement': 'magnitude'}, 'value': 120, 'outside': 0, 'budget': 120, 'consent': True, 'rights': True, 'tests': [{'input': {'tag': 'up', 'magnitude': 8}, 'expected': {'event_type': 'up', 'measurement': 8}}, {'input': {'tag': 'down', 'magnitude': 9}, 'expected': {'event_type': 'down', 'measurement': 9}}]}
    ]
    base = {'buyers': people, 'fixed': 200, 'variable': 20, 'seller_margin': 10, 'seller_refund_collateral': 260, 'buyer_escrow_is_simulated': True}
    result = {}
    for name in ('compatible_three', 'withdrawal', 'failure_and_refund', 'rights_block', 'adverse_cost'):
        c = json.loads(wire(base))
        if name == 'withdrawal': c['buyers'][1]['consent'] = False
        if name == 'rights_block': c['buyers'][2]['rights'] = False
        if name == 'failure_and_refund': c['buyers'][1]['tests'][1]['expected']['measurement'] = 999
        if name == 'adverse_cost': c.update(fixed=360, variable=35)
        result[name] = c
    return result


def prospective_plan(case):
    people = case['buyers']
    if len({b['id'] for b in people}) != len(people):
        raise ValueError('DUPLICATE_BUYER_ID')
    if any(type(case[k]) is not int or case[k] < 0 for k in ('fixed', 'variable', 'seller_margin', 'seller_refund_collateral')):
        raise ValueError('INVALID_COST')
    eligible = [b for b in people if b['consent'] is True and b['rights'] is True]
    candidates = []
    for count in range(1, len(eligible) + 1):
        for coalition in itertools.combinations(eligible, count):
            cost = case['fixed'] + count * case['variable']
            required = cost + case['seller_margin']
            caps = [max(0, min(b['budget'], b['value'] - b['outside'])) for b in coalition]
            if sum(caps) >= required:
                candidates.append((sum(b['value'] - b['outside'] for b in coalition) - required, count, tuple(b['id'] for b in coalition), coalition, caps, cost, required))
    if not candidates:
        return {'status': 'NO_FEASIBLE_VOLUNTARY_COALITION', 'buyers': [], 'construction_cost': 0, 'price_total': 0, 'shares': {}}
    _, _, _, chosen, caps, cost, required = max(candidates, key=lambda t: (t[0], t[1], t[2]))
    shares = [0] * len(chosen)
    remaining = required
    while remaining:
        active = [i for i, cap in enumerate(caps) if shares[i] < cap]
        if not active: raise ValueError('INTERNAL_FEASIBILITY_ERROR')
        q, r = divmod(remaining, len(active))
        paid = 0
        for rank, i in enumerate(active):
            step = min(caps[i] - shares[i], q + (rank < r))
            shares[i] += step
            paid += step
        if not paid: raise ValueError('INTERNAL_ALLOCATION_ERROR')
        remaining -= paid
    return {'status': 'CONDITIONALLY_FEASIBLE_PLEDGES', 'buyers': [b['id'] for b in chosen], 'construction_cost': cost, 'price_total': required, 'shares': dict(zip((b['id'] for b in chosen), shares))}


def compile_adapter(buyer):
    fields = buyer['fields']
    if set(fields) != {'event_type', 'measurement'} or len(set(fields.values())) != 2:
        raise ValueError('UNSUPPORTED_OR_COLLIDING_FIELD_MAPPING')
    return {'schema': SCHEMA, 'buyer_id': buyer['id'], 'normalizer': {'output_fields': ['event_type', 'measurement'], 'source_fields': fields}}


def apply_adapter(adapter, record):
    if adapter['schema'] != SCHEMA or set(adapter['normalizer']['source_fields']) != {'event_type', 'measurement'}:
        raise ValueError('UNSUPPORTED_ADAPTER')
    mapping = adapter['normalizer']['source_fields']
    if not all(key in record for key in mapping.values()): raise ValueError('MISSING_REQUIRED_SOURCE_FIELD')
    return {key: record[mapping[key]] for key in ('event_type', 'measurement')}


def construct(case):
    plan = prospective_plan(case)
    produced = {}
    if not plan['buyers']:
        return {'plan': plan, 'artifacts': {}, 'acceptance': {}, 'economic_status': 'NO_DEPLOY', 'conditional_cost_incurred': 0, 'conditional_refund_liability': 0}
    lookup = {b['id']: b for b in case['buyers']}
    accepted = {}
    for identity in plan['buyers']:
        buyer = lookup[identity]
        art = compile_adapter(buyer)
        produced[identity] = art
        accepted[identity] = all(apply_adapter(art, t['input']) == t['expected'] for t in buyer['tests'])
    success = all(accepted.values())
    refund = 0 if success else plan['price_total']
    risk_capital_needed = plan['construction_cost']
    collateral_sufficient = case['seller_refund_collateral'] >= risk_capital_needed
    status = ('CONDITIONAL_ACCEPTED_NOT_COLLECTED' if success and collateral_sufficient else
              'FAILED_ACCEPTANCE_REFUND_DUE' if not success else 'INSUFFICIENT_REFUND_COLLATERAL')
    # Hypothetical buyer escrow cannot be spent while it backs an unresolved refund.
    # At construction time escrow + independent seller collateral must cover both
    # all production costs and the full refund reserve. None of it is actual cash.
    escrow = plan['price_total']
    initial = escrow + case['seller_refund_collateral']
    post_spend = initial - plan['construction_cost']
    return {'plan': plan, 'artifacts': produced, 'acceptance': accepted, 'economic_status': status,
            'conditional_cost_incurred': plan['construction_cost'],
            'conditional_refund_liability': refund, 'required_preconstruction_refund_collateral': risk_capital_needed,
            'declared_hypothetical_collateral': case['seller_refund_collateral'],
            'hypothetical_escrow_receipts': escrow, 'hypothetical_preconstruction_cash': initial,
            'hypothetical_cash_after_cost': post_spend, 'refund_reserve_before_acceptance': escrow,
            'refund_reserve_covered_before_acceptance': post_spend >= escrow,
            'hypothetical_cash_after_full_refund': post_spend - refund}


def run(output):
    output = Path(output)
    if output.exists(): raise FileExistsError('CREATE_ONLY_EVIDENCE_DIRECTORY')
    output.mkdir(parents=True)
    worlds = fixtures()
    evidence = {'schema': SCHEMA, 'scope': 'AUTHOR_CREATED_ONLY_NO_CUSTOMER_OR_NATIVE_COMMERCE', 'source_world_digest': digest(worlds), 'worlds': {}}
    for name, case in worlds.items():
        result = construct(case)
        artifacts = {}
        for ident, artifact in result['artifacts'].items():
            path = output / name / f'{ident}.json'
            path.parent.mkdir(exist_ok=True, parents=True)
            path.write_bytes(wire(artifact) + b'\n')
            artifacts[ident] = hashlib.sha256(path.read_bytes()).hexdigest()
        result.pop('artifacts')
        evidence['worlds'][name] = {'case_sha256': digest(case), **result, 'artifact_file_sha256': artifacts}
    evidence['actual_buyers'] = 0
    evidence['actual_collections'] = 0
    evidence['actual_365_day_complete_cost_profit'] = None
    evidence['target_3b_achieved'] = False
    evidence['deployment_authorized'] = False
    (output/'RESULT.json').write_bytes(wire(evidence) + b'\n')
    return evidence
