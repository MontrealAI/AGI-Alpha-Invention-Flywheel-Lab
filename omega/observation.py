"""Finite authored observation construction; no physical calibration or external calls.

The constructor sees declared hypotheses and sensor recipes, never the evaluator's
actual state. Sensors run only through a caller-supplied observation boundary.
This is established finite decision-focused experiment design, not a new method.
"""
from __future__ import annotations
from itertools import combinations, product
from math import prod
from mechanism_harness.core import digest, exact_keys

SCHEMA = 'omega-observation/v1'


def _integer(value, label, nonnegative=False):
    if type(value) is not int or (nonnegative and value < 0):
        raise ValueError('INTEGER_REQUIRED:' + label)


def _name(value, label):
    if type(value) is not str or not value:
        raise ValueError('NAME_REQUIRED:' + label)


def recipe_hash(sensor):
    return digest(sensor)


def validate(request):
    exact_keys(request, {'schema', 'case_id', 'context_id', 'hypotheses', 'sensors',
                         'budget_cents', 'prior_observations', 'inherited_recipes'}, 'REQUEST_FIELDS')
    if request['schema'] != SCHEMA:
        raise ValueError('UNKNOWN_SCHEMA')
    _name(request['case_id'], 'case_id'); _name(request['context_id'], 'context_id')
    _integer(request['budget_cents'], 'budget_cents', True)
    for field in ('hypotheses', 'sensors', 'prior_observations', 'inherited_recipes'):
        if type(request[field]) is not list:
            raise ValueError('LIST_REQUIRED:' + field)
    if not request['hypotheses']:
        raise ValueError('HYPOTHESES_REQUIRED')
    for world in request['hypotheses']:
        exact_keys(world, {'id', 'state', 'accepted_actions'}, 'HYPOTHESIS_FIELDS')
        _name(world['id'], 'hypothesis_id')
        if type(world['state']) is not list or len(world['state']) != 2:
            raise ValueError('TWO_COMPONENT_STATE_REQUIRED')
        for value in world['state']:
            _integer(value, 'state', True)
        if type(world['accepted_actions']) is not list or not world['accepted_actions']:
            raise ValueError('ACCEPTED_ACTIONS_REQUIRED')
        for action in world['accepted_actions']:
            _name(action, 'action')
        if len(set(world['accepted_actions'])) != len(world['accepted_actions']):
            raise ValueError('DUPLICATE_ACTION')
    for sensor in request['sensors']:
        exact_keys(sensor, {'id', 'coefficients', 'offset', 'error_bound',
                           'setup_cost_cents', 'sample_cost_cents', 'authorized'}, 'SENSOR_FIELDS')
        _name(sensor['id'], 'sensor_id')
        if type(sensor['coefficients']) is not list or len(sensor['coefficients']) != 2:
            raise ValueError('TWO_COEFFICIENTS_REQUIRED')
        for value in sensor['coefficients']:
            _integer(value, 'coefficient')
        _integer(sensor['offset'], 'offset')
        for field in ('error_bound', 'setup_cost_cents', 'sample_cost_cents'):
            _integer(sensor[field], field, True)
        if type(sensor['authorized']) is not bool:
            raise ValueError('EXPLICIT_AUTHORIZATION_REQUIRED')
    for field in ('hypotheses', 'sensors'):
        ids = [x['id'] for x in request[field]]
        if len(ids) != len(set(ids)):
            raise ValueError('DUPLICATE_ID:' + field)
    sensors = {s['id']: s for s in request['sensors']}
    observed, inherited = set(), set()
    for record in request['prior_observations']:
        exact_keys(record, {'sensor_id', 'sensor_sha256', 'context_id', 'value'}, 'OBSERVATION_FIELDS')
        ident = record['sensor_id']
        if ident not in sensors or ident in observed:
            raise ValueError('UNKNOWN_OR_REPEATED_OBSERVATION')
        if record['context_id'] != request['context_id'] or record['sensor_sha256'] != recipe_hash(sensors[ident]):
            raise ValueError('STALE_OBSERVATION')
        _integer(record['value'], 'observation_value')
        observed.add(ident)
    for record in request['inherited_recipes']:
        exact_keys(record, {'sensor_id', 'sensor_sha256'}, 'RECIPE_FIELDS')
        ident = record['sensor_id']
        if ident not in sensors or ident in inherited or record['sensor_sha256'] != recipe_hash(sensors[ident]):
            raise ValueError('INCOMPATIBLE_INHERITED_RECIPE')
        inherited.add(ident)
    return request


def nominal(sensor, world):
    return sum(a*b for a, b in zip(sensor['coefficients'], world['state'])) + sensor['offset']


def consistent(world, sensor, value):
    return abs(nominal(sensor, world) - value) <= sensor['error_bound']


def common_actions(worlds):
    if not worlds:
        return []
    actions = set(worlds[0]['accepted_actions'])
    for world in worlds[1:]:
        actions.intersection_update(world['accepted_actions'])
    return sorted(actions)


def posterior(request, observations):
    sensors = {s['id']: s for s in request['sensors']}
    return [world for world in request['hypotheses']
            if all(consistent(world, sensors[r['sensor_id']], r['value']) for r in observations)]


def panel_cost(request, panel):
    inherited = {r['sensor_id'] for r in request['inherited_recipes']}
    return sum(s['sample_cost_cents'] + (0 if s['id'] in inherited else s['setup_cost_cents']) for s in panel)


def _representatives(worlds, sensor):
    intervals = [(nominal(sensor, w)-sensor['error_bound'], nominal(sensor, w)+sensor['error_bound']) for w in worlds]
    cuts = sorted({n for lo, hi in intervals for n in (lo, hi+1)})
    return [x for x in cuts if any(lo <= x <= hi for lo, hi in intervals)]


def _guarantees_decision(worlds, panel, budget):
    axes = [_representatives(worlds, sensor) for sensor in panel]
    points = prod(len(axis) for axis in axes)
    if points > budget[0]:
        raise RuntimeError('RESOURCE_LIMIT_NOT_IMPOSSIBILITY')
    budget[0] -= points
    for values in product(*axes):
        remaining = [w for w in worlds if all(consistent(w, s, y) for s, y in zip(panel, values))]
        if remaining and not common_actions(remaining):
            return False
    return True


def select_panel(request, *, max_cells=200000, max_panels=65536):
    """Minimum declared cost fixed panel, conditional on finite hypothesis closure.

    Integer interval breakpoints compress observationally equivalent outcomes.
    The independent baseline uses an incompatible-hypothesis hitting set.
    """
    validate(request)
    for value in (max_cells, max_panels):
        if type(value) is not int or value <= 0:
            raise ValueError('POSITIVE_RESOURCE_BUDGET_REQUIRED')
    worlds = posterior(request, request['prior_observations'])
    base = {'request_sha256': digest(request), 'hypothesis_ids': [w['id'] for w in worlds]}
    if not worlds:
        return dict(base, status='OUT_OF_MODEL', panel=[], cost_cents=0)
    if common_actions(worlds):
        return dict(base, status='PANEL_READY', panel=[], cost_cents=0)
    already = {r['sensor_id'] for r in request['prior_observations']}
    available = sorted([s for s in request['sensors'] if s['authorized'] and s['id'] not in already], key=lambda s: s['id'])
    if len(available) >= max_panels.bit_length() and 2**len(available) > max_panels:
        raise RuntimeError('RESOURCE_LIMIT_NOT_IMPOSSIBILITY')
    choices = []
    for size in range(1, len(available)+1):
        for panel in combinations(available, size):
            cost = panel_cost(request, panel)
            if cost <= request['budget_cents']:
                choices.append((cost, tuple(s['id'] for s in panel), panel))
    cells = [max_cells]
    for cost, ids, panel in sorted(choices):
        if _guarantees_decision(worlds, panel, cells):
            return dict(base, status='PANEL_READY', panel=list(ids), cost_cents=cost)
    return dict(base, status='UNRESOLVED', panel=[], cost_cents=0)


def execute(request, observe, *, max_cells=200000, max_panels=65536):
    """Run the constructed panel through an authorized observation callback.

    Callback accepts only a sensor ID and returns an integer or None (missing).
    Every attempted measurement incurs its declared recipe/sample cost, including
    missing or out-of-model results. There is no external execution in this module.
    """
    plan = select_panel(request, max_cells=max_cells, max_panels=max_panels)
    receipt = dict(plan, schema='omega-observation-receipt/v1', observations=list(request['prior_observations']),
                   attempted_sensors=[], incurred_cost_cents=0, action=None,
                   scope='FINITE_AUTHORED_MODEL_ONLY', physical_validity='UNKNOWN', model_completeness='UNKNOWN')
    if plan['status'] != 'PANEL_READY':
        return receipt
    sensors = {s['id']: s for s in request['sensors']}
    for ident in plan['panel']:
        sensor = sensors[ident]
        receipt['attempted_sensors'].append(ident)
        receipt['incurred_cost_cents'] += panel_cost(request, [sensor])
        try:
            value = observe(ident)
        except (OSError, TimeoutError):
            receipt['status'] = 'OBSERVATION_UNAVAILABLE'
            return receipt
        if value is None:
            receipt['status'] = 'OBSERVATION_UNAVAILABLE'
            return receipt
        if type(value) is not int:
            receipt['status'] = 'INVALID_OBSERVATION'
            return receipt
        receipt['observations'].append({'sensor_id': ident, 'sensor_sha256': recipe_hash(sensor),
                                        'context_id': request['context_id'], 'value': value})
        worlds = posterior(request, receipt['observations'])
        receipt['hypothesis_ids'] = [w['id'] for w in worlds]
        if not worlds:
            receipt['status'] = 'OUT_OF_MODEL'
            receipt['hypothesis_ids'] = []
            return receipt
    worlds = posterior(request, receipt['observations'])
    actions = common_actions(worlds)
    receipt['hypothesis_ids'] = [w['id'] for w in worlds]
    receipt['status'] = 'MODEL_DECISION' if actions else 'UNRESOLVED'
    receipt['action'] = actions[0] if actions else None
    return receipt


def retained_recipes(request, receipt):
    """Retain recipes actually acquired, not observations or current acceptance.

    This local content hash establishes recipe compatibility only. It does not
    authenticate laboratory calibration, IP permissions, or a financial payment.
    """
    if receipt['request_sha256'] != digest(request):
        raise ValueError('REQUEST_MISMATCH')
    acquired = set(receipt['attempted_sensors'])
    return [{'sensor_id': s['id'], 'sensor_sha256': recipe_hash(s)}
            for s in request['sensors'] if s['id'] in acquired]
