"""Bounded, data-only mechanism composition; no financial or external execution authority."""
from __future__ import annotations
import hashlib
import heapq
import json
import re
from dataclasses import dataclass
from pathlib import Path

SCHEMA = 'agi-alpha/mechanism-harness/v1'
IDENTIFIER = re.compile(r'[a-z][a-z0-9_.-]{0,63}\Z')
EFFECTS = frozenset({'pure', 'public_read'})
MAX_MECHANISMS = 128
MAX_STATES = 20000


class ContractError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def exact_keys(value, fields, message):
    if type(value) is not dict or set(value) != set(fields):
        raise ContractError(message)


def identifiers(values, name, *, allow_empty=False):
    if type(values) is not list or (not allow_empty and not values) or len(values) > 128:
        raise ContractError('INVALID_' + name)
    if any(type(x) is not str or not IDENTIFIER.fullmatch(x) for x in values):
        raise ContractError('INVALID_' + name)
    if values != sorted(set(values)):
        raise ContractError('SORTED_UNIQUE_' + name + '_REQUIRED')
    return tuple(values)


@dataclass(frozen=True)
class Mechanism:
    id: str
    requires: frozenset[str]
    provides: frozenset[str]
    cost: int
    effect: str
    kind: str
    origin: str


def validate_spec(spec):
    exact_keys(spec, {'schema', 'purpose', 'mechanisms', 'candidate_bridges'}, 'SPEC_FIELDS')
    if spec['schema'] != SCHEMA:
        raise ContractError('UNKNOWN_SCHEMA')
    purpose = spec['purpose']
    exact_keys(purpose, {'initial', 'goal', 'max_cost', 'max_steps', 'max_states', 'allowed_effects'}, 'PURPOSE_FIELDS')
    initial = frozenset(identifiers(purpose['initial'], 'INITIAL', allow_empty=True))
    goal = frozenset(identifiers(purpose['goal'], 'GOAL'))
    for key, limit in (('max_cost', 1_000_000), ('max_steps', 32), ('max_states', MAX_STATES)):
        v = purpose[key]
        if type(v) is not int or not 1 <= v <= limit:
            raise ContractError('INVALID_' + key.upper())
    effects = set(identifiers(purpose['allowed_effects'], 'EFFECTS'))
    if not effects <= EFFECTS:
        raise ContractError('UNAUTHORIZED_EFFECT_CLASS')
    raw_mechanisms, raw_bridges = spec['mechanisms'], spec['candidate_bridges']
    if type(raw_mechanisms) is not list or type(raw_bridges) is not list or len(raw_mechanisms) + len(raw_bridges) > MAX_MECHANISMS:
        raise ContractError('BOUNDED_MECHANISMS_REQUIRED')
    mechanisms = []
    for raw, kind in [(x, 'existing') for x in raw_mechanisms] + [(x, 'candidate_bridge') for x in raw_bridges]:
        exact_keys(raw, {'id', 'requires', 'provides', 'cost', 'effect', 'origin'}, 'MECHANISM_FIELDS')
        ident = raw['id']
        if type(ident) is not str or not IDENTIFIER.fullmatch(ident):
            raise ContractError('MECHANISM_ID')
        needs = frozenset(identifiers(raw['requires'], 'PRECONDITIONS', allow_empty=True))
        adds = frozenset(identifiers(raw['provides'], 'POSTCONDITIONS'))
        if not adds - needs:
            raise ContractError('NONPROGRESSING_MECHANISM')
        if type(raw['cost']) is not int or not 1 <= raw['cost'] <= 1000000:
            raise ContractError('POSITIVE_INTEGER_RESOURCE_COST_REQUIRED')
        if raw['effect'] not in effects:
            raise ContractError('MECHANISM_EFFECT_NOT_PERMITTED')
        if raw['origin'] not in {'developer_supplied', 'retrieved', 'machine_proposed', 'externally_supplied'}:
            raise ContractError('MECHANISM_ORIGIN_REQUIRED')
        mechanisms.append(Mechanism(ident, needs, adds, raw['cost'], raw['effect'], kind, raw['origin']))
    if len({m.id for m in mechanisms}) != len(mechanisms):
        raise ContractError('DUPLICATE_MECHANISM_ID')
    return purpose, initial, goal, tuple(sorted(mechanisms, key=lambda m: m.id))


def compose(spec):
    """Finite cost-first search. A successful symbolic plan is NOT real-world qualification."""
    purpose, initial, goal, operators = validate_spec(spec)
    stamp = digest(spec)
    if goal <= initial:
        return {'schema': 'agi-alpha/mechanism-plan/v1', 'spec_sha256': stamp, 'status': 'GOAL_ALREADY_SATISFIED', 'sequence': [], 'candidate_bridge_provenance': {}, 'cost_units': 0, 'states_expanded': 0, 'candidate_bridge_ids': [], 'goal': sorted(goal), 'claim': 'SYMBOLIC_ONLY_NO_OPERATING_AUTHORITY'}
    queue = [(0, 0, (), tuple(sorted(initial)))]
    best = {(tuple(sorted(initial)), 0): (0, ())}
    expanded = 0
    while queue:
        cost, depth, sequence, facts_tuple = heapq.heappop(queue)
        key = (facts_tuple, depth)
        if best.get(key) != (cost, sequence):
            continue
        state = frozenset(facts_tuple)
        if goal <= state:
            chosen = {m.id: m for m in operators}
            return {'schema': 'agi-alpha/mechanism-plan/v1', 'spec_sha256': stamp, 'status': 'CANDIDATE_REQUIRES_INDEPENDENT_QUALIFICATION' if any(chosen[x].kind == 'candidate_bridge' for x in sequence) else 'SYMBOLIC_PLAN_FOUND', 'sequence': list(sequence), 'candidate_bridge_provenance': {x: chosen[x].origin for x in sequence if chosen[x].kind == 'candidate_bridge'}, 'cost_units': cost, 'states_expanded': expanded, 'candidate_bridge_ids': [x for x in sequence if chosen[x].kind == 'candidate_bridge'], 'goal': sorted(goal), 'claim': 'SYMBOLIC_ONLY_NO_OPERATING_AUTHORITY'}
        if expanded >= purpose['max_states']:
            return unresolved(stamp, goal, expanded, 'SEARCH_BOUND_EXHAUSTED')
        expanded += 1
        if depth >= purpose['max_steps']:
            continue
        for op in operators:
            if op.requires <= state and not op.provides <= state:
                next_cost = cost + op.cost
                if next_cost > purpose['max_cost']:
                    continue
                new_facts = tuple(sorted(state | op.provides))
                new_sequence = sequence + (op.id,)
                nxt = (new_facts, depth + 1)
                quality = (next_cost, new_sequence)
                if nxt not in best or quality < best[nxt]:
                    best[nxt] = quality
                    heapq.heappush(queue, (next_cost, depth + 1, new_sequence, new_facts))
    return unresolved(stamp, goal, expanded, 'NO_SUPPORTED_PLAN_FOUND_WITHIN_BOUNDS')


def unresolved(stamp, goal, expanded, status):
    return {'schema': 'agi-alpha/mechanism-plan/v1', 'spec_sha256': stamp, 'status': status, 'sequence': [], 'candidate_bridge_provenance': {}, 'cost_units': None, 'states_expanded': expanded, 'candidate_bridge_ids': [], 'goal': sorted(goal), 'claim': 'NO_IMPOSSIBILITY_OR_OPERATING_AUTHORITY_ASSERTED'}


def audit(spec, candidate):
    """Independently replay declared effects; does not call compose or trust claimed cost/status."""
    purpose, initial, goal, operators = validate_spec(spec)
    exact_keys(candidate, {'schema', 'spec_sha256', 'status', 'sequence', 'candidate_bridge_provenance', 'cost_units', 'states_expanded', 'candidate_bridge_ids', 'goal', 'claim'}, 'PLAN_FIELDS')
    if candidate['schema'] != 'agi-alpha/mechanism-plan/v1' or candidate['spec_sha256'] != digest(spec):
        raise ContractError('SOURCE_BOUND_PLAN_REQUIRED')
    if candidate['goal'] != sorted(goal):
        raise ContractError('PLAN_GOAL_CHANGED')
    if type(candidate['sequence']) is not list or len(candidate['sequence']) > purpose['max_steps']:
        raise ContractError('PLAN_LENGTH_BOUNDS')
    if type(candidate['states_expanded']) is not int or not 0 <= candidate['states_expanded'] <= purpose['max_states']:
        raise ContractError('PLAN_SEARCH_BOUNDS')
    found = {m.id: m for m in operators}
    state = set(initial)
    incurred = 0
    bridges = []
    for ident in candidate['sequence']:
        if type(ident) is not str or ident not in found:
            raise ContractError('UNKNOWN_STEP')
        op = found[ident]
        if not op.requires <= state or op.provides <= state:
            raise ContractError('ORDER_OR_PROGRESS_VIOLATION')
        state.update(op.provides)
        incurred += op.cost
        if op.kind == 'candidate_bridge':
            bridges.append(ident)
    if candidate['candidate_bridge_ids'] != bridges or candidate['candidate_bridge_provenance'] != {x: found[x].origin for x in bridges}:
        raise ContractError('UNDECLARED_BRIDGE')
    if candidate['sequence']:
        expected_status = 'CANDIDATE_REQUIRES_INDEPENDENT_QUALIFICATION' if bridges else 'SYMBOLIC_PLAN_FOUND'
        if not goal <= state or incurred != candidate['cost_units'] or incurred > purpose['max_cost'] or candidate['status'] != expected_status or candidate['claim'] != 'SYMBOLIC_ONLY_NO_OPERATING_AUTHORITY':
            raise ContractError('WRONG_PLAN_RESULT_OR_COST')
    else:
        if goal <= initial:
            if candidate['status'] != 'GOAL_ALREADY_SATISFIED' or candidate['cost_units'] != 0 or candidate['claim'] != 'SYMBOLIC_ONLY_NO_OPERATING_AUTHORITY':
                raise ContractError('INITIAL_GOAL_RESULT')
        else:
            if candidate['status'] not in {'NO_SUPPORTED_PLAN_FOUND_WITHIN_BOUNDS', 'SEARCH_BOUND_EXHAUSTED'} or candidate['cost_units'] is not None or candidate['claim'] != 'NO_IMPOSSIBILITY_OR_OPERATING_AUTHORITY_ASSERTED':
                raise ContractError('INVALID_ABSTENTION')
            # Independently rerunning the bounded search is required to validate absence of a plan.
            reference = compose(spec)
            if reference != candidate:
                raise ContractError('UNVERIFIED_ABSTENTION')
    return {'schema': 'agi-alpha/mechanism-check/v1', 'spec_sha256': digest(spec), 'plan_sha256': digest(candidate), 'accepted': True, 'goal_achieved_symbolically': goal <= state, 'verified_cost_units': incurred if candidate['sequence'] else candidate['cost_units'], 'candidate_bridges_require_separate_qualification': bool(bridges), 'current_proof': None, 'authority': [], 'scope': 'FINITE_SYMBOLIC_REPLAY_NOT_REAL_WORLD_SEMANTICS'}


def capability_capsule(spec, candidate, check):
    """Record a candidate composite. No inherited current proof or authority."""
    if audit(spec, candidate) != check:
        raise ContractError('INDEPENDENT_CHECK_MISMATCH')
    if not check['goal_achieved_symbolically']:
        raise ContractError('NO_CAPABILITY_FROM_UNRESOLVED_PLAN')
    return {'schema': 'agi-alpha/mechanism-capsule/v1', 'id': 'composite-' + digest(candidate)[:24], 'spec_sha256': digest(spec), 'plan_sha256': digest(candidate), 'components': candidate['sequence'], 'acquisition_cost_units': candidate['cost_units'], 'evidence': {'symbolic_check_sha256': digest(check), 'scope': check['scope']}, 'inherited_history': [], 'current_proof': None, 'authority': [], 'promotion_status': 'CANDIDATE_ONLY_REQUIRES_FRESH_MISSION_QUALIFICATION'}
