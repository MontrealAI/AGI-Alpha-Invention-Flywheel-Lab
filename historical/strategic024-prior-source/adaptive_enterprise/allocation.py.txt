"""State-bound planning migration of PR20's finite allocation screen.

This module does not reserve money or execute service work. The native Account
must verify its state/action digest and atomically reserve before execution.
"""
from __future__ import annotations
import copy
import hashlib
import json
from fractions import Fraction
from adaptive_enterprise.account import action_digest

KINDS = {'acquisition', 'retention', 'new_service', 'capacity', 'supplier_diversity', 'instrument', 'delivery', 'cash'}
SCHEMA = 'agi-alpha/adaptive012-allocation/v1'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('INTEGER_ALLOCATION_VALUE_REQUIRED')
    return value


def _identifier(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        raise ValueError('BOUNDED_ALLOCATION_IDENTIFIER_REQUIRED')
    return value


def _list_ids(values):
    if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() or len(v) > 160 for v in values) or len(set(values)) != len(values):
        raise ValueError('UNIQUE_ALLOCATION_IDENTIFIERS_REQUIRED')
    return values


def default_riskpolicy():
    return {'scenarios': {'central': 7000, 'adverse': 3000}, 'worst_loss_limit': 50_000_000,
            'downside_penalty_bps': 2500, 'max_states': 4096, 'authorized_allocation': 100_000_000,
            'interactions': []}


def _cash(values, scenarios, *, signed):
    if not isinstance(values, dict) or set(values) != set(scenarios):
        raise ValueError('COMPLETE_SCENARIO_CASH_REQUIRED')
    for amount in values.values():
        if type(amount) is not int or not signed and amount < 0:
            raise ValueError('INTEGER_SCENARIO_CASH_REQUIRED')
    return values


def allocate(observation, options, riskpolicy):
    if not isinstance(observation, dict) or observation.get('scope') != 'SIMULATED' or not isinstance(observation.get('summary'), dict):
        raise ValueError('NATIVE_SIMULATED_ACCOUNT_OBSERVATION_REQUIRED')
    state_digest = observation.get('state_digest')
    if not isinstance(state_digest, str) or len(state_digest) != 64 or any(x not in '0123456789abcdef' for x in state_digest):
        raise ValueError('NATIVE_STATE_DIGEST_REQUIRED')
    summary = observation['summary']
    for key in ('available', 'unrestrictedEarned'):
        _integer(summary.get(key))
    if not isinstance(riskpolicy, dict) or set(riskpolicy) != set(default_riskpolicy()):
        raise ValueError('EXACT_ALLOCATION_RISK_POLICY_REQUIRED')
    scenarios = riskpolicy['scenarios']
    if not isinstance(scenarios, dict) or not scenarios or len(scenarios) > 128:
        raise ValueError('BOUNDED_ALLOCATION_SCENARIOS_REQUIRED')
    for ident, weight in scenarios.items():
        _identifier(ident); _integer(weight, 1)
    if sum(scenarios.values()) != 10000:
        raise ValueError('ALLOCATION_WEIGHTS_MUST_SUM_10000')
    for key in ('worst_loss_limit', 'downside_penalty_bps', 'authorized_allocation'):
        _integer(riskpolicy[key])
    max_states = _integer(riskpolicy['max_states'], 1)
    if max_states > 1_048_576:
        raise ValueError('FINITE_ALLOCATION_RESOURCE_BOUND_REQUIRED')
    if not isinstance(options, list) or len(options) > 128:
        raise ValueError('BOUNDED_ACTION_SHORTLIST_REQUIRED')
    required = {'id', 'kind', 'upfront_cost', 'later_liabilities', 'future_net_cash', 'benefit_ids', 'requires', 'exclusive_group', 'authorized', 'evidence', 'execution'}
    by_id, unknown = {}, []
    for option in options:
        if not isinstance(option, dict) or set(option) != required:
            raise ValueError('EXACT_EXECUTABLE_ALLOCATION_OPTION_REQUIRED')
        ident = _identifier(option['id'])
        if ident in by_id:
            raise ValueError('DUPLICATE_ALLOCATION_ACTION')
        if option['kind'] not in KINDS or type(option['authorized']) is not bool:
            raise ValueError('DECLARED_ACTION_KIND_AND_AUTHORIZATION_REQUIRED')
        _integer(option['upfront_cost'])
        _cash(option['later_liabilities'], scenarios, signed=False)
        _list_ids(option['requires']); _list_ids(option['benefit_ids'])
        if ident in option['requires']:
            raise ValueError('SELF_DEPENDENCY_REFUSED')
        if option['exclusive_group'] is not None:
            _identifier(option['exclusive_group'])
        _identifier(option['evidence'])
        if not isinstance(option['execution'], dict):
            raise ValueError('EXECUTION_PAYLOAD_REQUIRED')
        digest(option['execution'])
        if option['future_net_cash'] is None:
            unknown.append(ident)
        else:
            _cash(option['future_net_cash'], scenarios, signed=True)
        if option['kind'] == 'cash' and (option['upfront_cost'] or any(option['later_liabilities'].values()) or option['future_net_cash'] is not None and any(option['future_net_cash'].values())):
            raise ValueError('CASH_RETENTION_CANNOT_MANUFACTURE_RETURNS')
        by_id[ident] = option
    for option in options:
        if not set(option['requires']) <= set(by_id):
            raise ValueError('ALLOCATION_DEPENDENCY_MISSING')
    visiting, visited = set(), set()
    def visit(ident):
        if ident in visiting:
            raise ValueError('CYCLIC_ALLOCATION_DEPENDENCY')
        if ident in visited:
            return
        visiting.add(ident)
        for dependency in by_id[ident]['requires']:
            visit(dependency)
        visiting.remove(ident); visited.add(ident)
    for ident in by_id:
        visit(ident)
    interactions = riskpolicy['interactions']
    if not isinstance(interactions, list) or len(interactions) > 128:
        raise ValueError('BOUNDED_INTERACTION_LIST_REQUIRED')
    joint_ids = set()
    for joint in interactions:
        if not isinstance(joint, dict) or set(joint) != {'id', 'members', 'net_cash', 'benefit_ids'}:
            raise ValueError('EXACT_SIGNED_INTERACTION_REQUIRED')
        _identifier(joint['id'])
        if joint['id'] in joint_ids:
            raise ValueError('DUPLICATE_INTERACTION')
        joint_ids.add(joint['id'])
        _list_ids(joint['members']); _list_ids(joint['benefit_ids'])
        if len(joint['members']) < 2 or not set(joint['members']) <= set(by_id):
            raise ValueError('EXISTING_DISTINCT_JOINT_MEMBERS_REQUIRED')
        _cash(joint['net_cash'], scenarios, signed=True)
    budget = min(summary['available'], summary['unrestrictedEarned'], riskpolicy['authorized_allocation'])
    base = {'schema': SCHEMA, 'scope': 'SIMULATED_PLANNING_ONLY', 'currency': 'simulated-microUSD',
            'expected_state_digest': state_digest, 'observation_sha256': digest(observation),
            'options_sha256': digest(options), 'riskpolicy_sha256': digest(riskpolicy),
            'selected': [], 'selected_options': [], 'predicted_scenario_cash': dict.fromkeys(scenarios, 0),
            'upfront_cost': 0, 'worst_later_reserve': 0, 'reserve_amount': 0, 'expected_net': 0,
            'expected_net_fraction': '0', 'risk_adjusted_value': '0', 'budget': budget,
            'decision': 'RETAIN_CASH', 'states_evaluated': 0, 'unknown_return_actions': sorted(unknown),
            'planning_provenance': 'Migration of portfolio_scale/transformational.py PR20 finite subset search. Added native state/action binding, signed future net cash, negative interactions, later-cash protection and shared-benefit deduplication. Historical planner remains unchanged.',
            'money_authority': 'Native Account only. This recommendation is not a reservation or signed external authority. Account.reserve must check this current state and exact action digest before effects.',
            'cash_semantics': 'future_net_cash is hypothetical future net cash AFTER explicit later liabilities and BEFORE upfront cost. Reservation covers upfront plus each action\'s worst later cost, at least any forecast negative future cash, plus worst negative interactions. Future receipts never fund present commitments.',
            'optimality_scope': 'EXACT_FINITE_SHORTLIST_WITH_DECLARED_SCENARIOS',
            'later_obligation_release_rule': 'Do not release a reservation before its later obligations are incurred/settled or protected by an additional native reservation. Forecast returns are not permission to release.'}
    eligible = [o for o in options if o['authorized'] and o['future_net_cash'] is not None and o['kind'] != 'cash']
    if len(eligible) >= max_states.bit_length() or (1 << len(eligible)) > max_states:
        return {**base, 'decision': 'DECOMPOSE_SHORTLIST_OR_INCREASE_AUTHORIZED_PLANNING_BUDGET', 'optimality_scope': 'NONE'}
    best_key = (Fraction(0), Fraction(0), 0)
    for mask in range(1 << len(eligible)):
        base['states_evaluated'] += 1
        chosen = [o for index, o in enumerate(eligible) if mask & (1 << index)]
        selected = {o['id'] for o in chosen}
        if any(not set(o['requires']) <= selected for o in chosen):
            continue
        groups = [o['exclusive_group'] for o in chosen if o['exclusive_group'] is not None]
        if len(groups) != len(set(groups)):
            continue
        joints = [j for j in interactions if set(j['members']) <= selected]
        identities = [identity for o in chosen for identity in o['benefit_ids']] + [identity for j in joints for identity in j['benefit_ids']]
        if len(identities) != len(set(identities)):
            continue
        upfront = sum(o['upfront_cost'] for o in chosen)
        later = sum(max(max(o['later_liabilities'].values()), max(0, -min(o['future_net_cash'].values()))) for o in chosen)
        later += sum(max(0, -min(j['net_cash'].values())) for j in joints)
        reservation = upfront + later
        if reservation > budget:
            continue
        net = {s: sum(o['future_net_cash'][s] for o in chosen) + sum(j['net_cash'][s] for j in joints) - upfront for s in scenarios}
        downside = max(0, -min(net.values()))
        if downside > riskpolicy['worst_loss_limit']:
            continue
        expected = sum((Fraction(scenarios[s], 10000) * net[s] for s in scenarios), Fraction(0))
        score = expected - Fraction(riskpolicy['downside_penalty_bps'], 10000) * downside
        key = (score, expected, -reservation)
        if reservation <= 0 or expected < 1 or key <= best_key:
            continue
        best_key = key
        base.update(selected=sorted(selected), selected_options=copy.deepcopy(chosen),
                    predicted_scenario_cash=net, upfront_cost=upfront, worst_later_reserve=later,
                    reserve_amount=reservation, expected_net=expected.numerator // expected.denominator,
                    expected_net_fraction=str(expected), risk_adjusted_value=str(score),
                    interactions=copy.deepcopy(joints), decision='CANDIDATE_ALLOCATION')
    base['unallocated_budget'] = budget - base['reserve_amount']
    plan_content = {'selected': base['selected'], 'options_sha256': base['options_sha256'],
                    'riskpolicy_sha256': base['riskpolicy_sha256'], 'state_digest': state_digest,
                    'reserve_amount': base['reserve_amount'], 'predicted_scenario_cash': base['predicted_scenario_cash']}
    base['plan_id'] = 'adaptive012-allocation-' + digest(plan_content)[:24]
    base['action_id'] = 'allocation-' + digest(plan_content)[:24]
    if base['selected']:
        base['authorized_digest'] = action_digest(base, state_digest, base['reserve_amount'], base['expected_net'])
    else:
        base['authorized_digest'] = None
    return base
