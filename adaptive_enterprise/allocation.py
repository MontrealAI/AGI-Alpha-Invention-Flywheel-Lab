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


def allocate(observation, options, riskpolicy, *, allow_seed=False, max_delivery_slots=None, earned_deduction=0, _diagnostic_cash_limit=None):
    if type(earned_deduction) is not int or earned_deduction<0:raise ValueError("NONNEGATIVE_EARNED_OPERATING_DEDUCTION_REQUIRED")
    if max_delivery_slots is not None and (type(max_delivery_slots) is not int or max_delivery_slots<0):raise ValueError("FINITE_DELIVERY_CAPACITY_REQUIRED")
    if type(allow_seed) is not bool:raise ValueError("EXPLICIT_SEED_PERMISSION_REQUIRED")
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
        if 'capacity_units' in option['execution']:
            _integer(option['execution']['capacity_units'], 1 if option['kind']=='delivery' else 0)
            if option['kind']!='delivery' and option['execution']['capacity_units']:
                raise ValueError('ONLY_DELIVERY_CONSUMES_CURRENT_CAPACITY')
        if 'work_keys' in option['execution']:
            _list_ids(option['execution']['work_keys'])
            if option['kind']=='delivery' and not option['execution']['work_keys']:
                raise ValueError('DECLARED_DELIVERY_WORK_KEYS_NONEMPTY')
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
    if any(type(o['execution'].get('cash_lock',0)) is not int or o['execution'].get('cash_lock',0)<0 for o in options):raise ValueError('NONNEGATIVE_NEUTRAL_CASH_LOCK_REQUIRED')
    if allow_seed and any(o['execution'].get('funding') not in {'SEED_OR_EARNED','EARNED'} for o in options):
        raise ValueError('EXPLICIT_PER_ACTION_FUNDING_REQUIRED')
    if _diagnostic_cash_limit is not None:
        _integer(_diagnostic_cash_limit)
        if _diagnostic_cash_limit < summary['available']:raise ValueError('DIAGNOSTIC_MUST_ONLY_RELAX_CASH')
    spendable_earned=max(0,summary['unrestrictedEarned']-earned_deduction)
    cash_limit=summary['available'] if _diagnostic_cash_limit is None else _diagnostic_cash_limit
    budget = min(cash_limit, riskpolicy['authorized_allocation']) if allow_seed else min(cash_limit, spendable_earned, riskpolicy['authorized_allocation'])
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
    if allow_seed:base['funding_policy']='EXPLICIT_PER_ACTION_SEED_OR_EARNED'
    if max_delivery_slots is not None:base['max_delivery_slots']=max_delivery_slots
    if earned_deduction:base['earned_operating_deduction']=earned_deduction
    eligible = [o for o in options if o['authorized'] and o['future_net_cash'] is not None and o['kind'] != 'cash']
    if max_delivery_slots is None:
        if len(eligible) >= max_states.bit_length() or (1 << len(eligible)) > max_states:
            return _diagnostic_result({**base, 'decision': 'DECOMPOSE_SHORTLIST_OR_INCREASE_AUTHORIZED_PLANNING_BUDGET', 'optimality_scope': 'NONE'}) if _diagnostic_cash_limit is not None else {**base, 'decision': 'DECOMPOSE_SHORTLIST_OR_INCREASE_AUTHORIZED_PLANNING_BUDGET', 'optimality_scope': 'NONE'}
        baskets=([o for index,o in enumerate(eligible) if mask & (1 << index)] for mask in range(1 << len(eligible)))
    else:
        # Mutually exclusive quote/method variants are one categorical choice,
        # not 2**N independent booleans. Capacity is enforced during generation.
        grouped={}
        for o in eligible:grouped.setdefault(('group',o['exclusive_group']) if o['exclusive_group'] is not None else ('single',o['id']),[]).append(o)
        baskets=[[]]
        for group in grouped.values():
            expanded=[]
            for basket in baskets:
                expanded.append(basket)
                for o in group:
                    if sum(x['execution'].get('capacity_units',1) for x in basket if x['kind']=='delivery')+(o['execution'].get('capacity_units',1) if o['kind']=='delivery' else 0)<=max_delivery_slots:
                        expanded.append([*basket,o])
                    if len(expanded)>max_states:
                        return _diagnostic_result({**base,'decision':'DECOMPOSE_SHORTLIST_OR_INCREASE_AUTHORIZED_PLANNING_BUDGET','optimality_scope':'NONE'}) if _diagnostic_cash_limit is not None else {**base,'decision':'DECOMPOSE_SHORTLIST_OR_INCREASE_AUTHORIZED_PLANNING_BUDGET','optimality_scope':'NONE'}
            baskets=expanded
    best_key = (Fraction(0), Fraction(0), 0)
    for chosen in baskets:
        base['states_evaluated'] += 1
        selected = {o['id'] for o in chosen}
        if max_delivery_slots is not None and sum(o['execution'].get('capacity_units',1) for o in chosen if o['kind']=='delivery')>max_delivery_slots:continue
        if any(not set(o['requires']) <= selected for o in chosen):
            continue
        groups = [o['exclusive_group'] for o in chosen if o['exclusive_group'] is not None]
        if len(groups) != len(set(groups)):
            continue
        work_keys=[k for o in chosen if o['kind']=='delivery' for k in o['execution'].get('work_keys',[])]
        if len(work_keys)!=len(set(work_keys)):continue
        joints = [j for j in interactions if set(j['members']) <= selected]
        identities = [identity for o in chosen for identity in o['benefit_ids']] + [identity for j in joints for identity in j['benefit_ids']]
        if len(identities) != len(set(identities)):
            continue
        upfront = sum(o['upfront_cost'] for o in chosen)
        later = sum(max(max(o['later_liabilities'].values()), max(0, -min(o['future_net_cash'].values()))) for o in chosen)
        later += sum(max(0, -min(j['net_cash'].values())) for j in joints)
        locks=sum(o['execution'].get('cash_lock',0) for o in chosen)
        reservation = upfront + later + locks
        if reservation > budget:
            continue
        if allow_seed:
            earned_reserve=sum(o['upfront_cost']+o['execution'].get('cash_lock',0)+max(max(o['later_liabilities'].values()),max(0,-min(o['future_net_cash'].values()))) for o in chosen if o['execution']['funding']=='EARNED')
            # Negative interaction reserves also require earned funding.
            earned_reserve+=sum(max(0,-min(j['net_cash'].values())) for j in joints)
            if earned_reserve>spendable_earned:continue
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
    if _diagnostic_cash_limit is not None:return _diagnostic_result(base)
    base['unallocated_budget'] = budget - base['reserve_amount']
    plan_content = {'selected': base['selected'], 'options_sha256': base['options_sha256'],
                    'riskpolicy_sha256': base['riskpolicy_sha256'], 'state_digest': state_digest,
                    'reserve_amount': base['reserve_amount'], 'predicted_scenario_cash': base['predicted_scenario_cash']}
    if allow_seed:plan_content['funding_policy']=base['funding_policy']
    if max_delivery_slots is not None:plan_content['max_delivery_slots']=max_delivery_slots
    if earned_deduction:plan_content['earned_operating_deduction']=earned_deduction
    base['plan_id'] = 'adaptive012-allocation-' + digest(plan_content)[:24]
    base['action_id'] = 'allocation-' + digest(plan_content)[:24]
    if base['selected']:
        base['authorized_digest'] = action_digest(base, state_digest, base['reserve_amount'], base['expected_net'])
    else:
        base['authorized_digest'] = None
    return base


def _diagnostic_result(result):
    """Deliberately omit action IDs, execution payloads, reservation and authority."""
    work=[]
    for option in result['selected_options']:
        execution=option['execution']
        if option['kind']=='delivery':
            row=execution.get('row',{})
            work.append({'kind':'delivery','job_id':execution.get('job_id'),
                         'customer_id':execution.get('customer_id'),
                         'mode':row.get('mode'),'price':row.get('price')})
        else:
            work.append({'kind':option['kind'],'evidence_sha256':digest(option['evidence'])})
    return {'scope':'COUNTERFACTUAL_CASH_OPPORTUNITY_NOT_EXECUTABLE_OR_REALIZED_PROFIT',
            'selected_work':work, 'id_scope':'Positional labels local to each enumeration; compare selected_work semantics, not ID equality.',
            'selected_ids':result['selected'], 'selected_count':len(result['selected']),
            'delivery_count':sum(o['kind']=='delivery' for o in result['selected_options']),
            'risk_adjusted_value':result['risk_adjusted_value'],
            'expected_net_fraction':result['expected_net_fraction'],
            'states_evaluated':result['states_evaluated'], 'optimality_scope':result['optimality_scope'],
            'authorized_digest':None}
