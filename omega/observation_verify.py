"""Independent exact reference and transcript checker for finite observation design.

The reference reduces decision ambiguity to a hitting-set problem: every group
of hypotheses with no common acceptable action must be separated by some sensor.
It neither imports the candidate nor enumerates its outcome cells. Acceptance is
conditional on declared hypotheses/error bounds; observation truth is not proved.
"""
from itertools import combinations
from mechanism_harness.core import digest


def _keys(item, fields):
    if type(item) is not dict or set(item) != set(fields):
        raise ValueError('EXACT_OBSERVATION_FIELDS_REQUIRED')


def _int(value, nonnegative=False):
    if type(value) is not int or (nonnegative and value < 0):
        raise ValueError('OBSERVATION_INTEGER_REQUIRED')


def _text(value):
    if type(value) is not str or not value:
        raise ValueError('OBSERVATION_NAME_REQUIRED')


def validate_request(request):
    _keys(request, ('schema', 'case_id', 'context_id', 'hypotheses', 'sensors',
                    'budget_cents', 'prior_observations', 'inherited_recipes'))
    if request['schema'] != 'omega-observation/v1':
        raise ValueError('OBSERVATION_SCHEMA_REQUIRED')
    _text(request['case_id']); _text(request['context_id'])
    _int(request['budget_cents'], True)
    for key in ('hypotheses', 'sensors', 'prior_observations', 'inherited_recipes'):
        if type(request[key]) is not list:
            raise ValueError('OBSERVATION_LIST_REQUIRED')
    if not request['hypotheses']:
        raise ValueError('OBSERVATION_HYPOTHESES_REQUIRED')
    for world in request['hypotheses']:
        _keys(world, ('id', 'state', 'accepted_actions'))
        _text(world['id'])
        if type(world['state']) is not list or len(world['state']) != 2:
            raise ValueError('TWO_STATE_COMPONENTS_REQUIRED')
        for n in world['state']:
            _int(n, True)
        if type(world['accepted_actions']) is not list or not world['accepted_actions']:
            raise ValueError('NONEMPTY_ACTIONS_REQUIRED')
        for action in world['accepted_actions']:
            _text(action)
        if len(set(world['accepted_actions'])) != len(world['accepted_actions']):
            raise ValueError('UNIQUE_ACTIONS_REQUIRED')
    for sensor in request['sensors']:
        _keys(sensor, ('id', 'coefficients', 'offset', 'error_bound', 'setup_cost_cents',
                       'sample_cost_cents', 'authorized'))
        _text(sensor['id'])
        if type(sensor['coefficients']) is not list or len(sensor['coefficients']) != 2:
            raise ValueError('TWO_SENSOR_COEFFICIENTS_REQUIRED')
        for n in sensor['coefficients']:
            _int(n)
        _int(sensor['offset'])
        for key in ('error_bound', 'setup_cost_cents', 'sample_cost_cents'):
            _int(sensor[key], True)
        if type(sensor['authorized']) is not bool:
            raise ValueError('EXPLICIT_SENSOR_AUTHORIZATION_REQUIRED')
    for key in ('hypotheses', 'sensors'):
        ids = [x['id'] for x in request[key]]
        if len(set(ids)) != len(ids):
            raise ValueError('UNIQUE_OBSERVATION_IDS_REQUIRED')
    sensors = {s['id']: s for s in request['sensors']}
    _validate_readings(request, request['prior_observations'], sensors)
    ids = []
    for record in request['inherited_recipes']:
        _keys(record, ('sensor_id', 'sensor_sha256'))
        _text(record['sensor_id'])
        if record['sensor_id'] not in sensors or digest(sensors[record['sensor_id']]) != record['sensor_sha256']:
            raise ValueError('INCOMPATIBLE_INHERITED_RECIPE')
        ids.append(record['sensor_id'])
    if len(set(ids)) != len(ids):
        raise ValueError('DUPLICATE_INHERITED_RECIPE')
    return sensors


def _validate_readings(request, readings, sensors):
    ids = []
    for row in readings:
        _keys(row, ('sensor_id', 'sensor_sha256', 'context_id', 'value'))
        _text(row['sensor_id']); _int(row['value'])
        if row['sensor_id'] not in sensors:
            raise ValueError('UNKNOWN_OBSERVATION_SENSOR')
        if row['context_id'] != request['context_id'] or row['sensor_sha256'] != digest(sensors[row['sensor_id']]):
            raise ValueError('STALE_OBSERVATION')
        ids.append(row['sensor_id'])
    if len(ids) != len(set(ids)):
        raise ValueError('DUPLICATE_OBSERVATION')


def _interval(world, sensor):
    a, b = sensor['coefficients']
    x, y = world['state']
    center = a*x + b*y + sensor['offset']
    return center - sensor['error_bound'], center + sensor['error_bound']


def _posterior(request, readings, sensors):
    surviving = []
    for world in request['hypotheses']:
        if all(_interval(world, sensors[r['sensor_id']])[0] <= r['value'] <=
               _interval(world, sensors[r['sensor_id']])[1] for r in readings):
            surviving.append(world)
    return surviving


def _actions(worlds):
    return set.intersection(*(set(w['accepted_actions']) for w in worlds)) if worlds else set()


def _charge(request, ids, sensors):
    inherited = {x['sensor_id'] for x in request['inherited_recipes']}
    return sum(sensors[i]['sample_cost_cents'] +
               (0 if i in inherited else sensors[i]['setup_cost_cents']) for i in ids)


def _bounded_power(size, maximum):
    if type(maximum) is not int or maximum < 1:
        raise ValueError('POSITIVE_REFERENCE_SEARCH_BUDGET_REQUIRED')
    if size >= maximum.bit_length() or (1 << size) > maximum:
        raise RuntimeError('REFERENCE_RESOURCE_CHECKPOINT_NOT_INFEASIBILITY')


def conventional_panel(request, *, max_subsets=131072, max_panels=65536):
    sensors = validate_request(request)
    worlds = _posterior(request, request['prior_observations'], sensors)
    result = {'request_sha256': digest(request), 'hypothesis_ids': [w['id'] for w in worlds],
              'status': 'OUT_OF_MODEL' if not worlds else 'UNRESOLVED', 'panel': [], 'cost_cents': 0}
    if not worlds:
        return result
    if _actions(worlds):
        return dict(result, status='PANEL_READY')
    _bounded_power(len(worlds), max_subsets)
    conflicts = []
    for count in range(2, len(worlds) + 1):
        for indices in combinations(range(len(worlds)), count):
            members = frozenset(indices)
            if any(conflict <= members for conflict in conflicts):
                continue
            if not _actions([worlds[i] for i in indices]):
                conflicts.append(members)
    observed = {r['sensor_id'] for r in request['prior_observations']}
    allowed = sorted(s['id'] for s in request['sensors'] if s['authorized'] and s['id'] not in observed)
    _bounded_power(len(allowed), max_panels)
    separators = {}
    for name in allowed:
        separators[name] = set()
        for j, conflict in enumerate(conflicts):
            intervals = [_interval(worlds[i], sensors[name]) for i in conflict]
            if max(lo for lo, _ in intervals) > min(hi for _, hi in intervals):
                separators[name].add(j)
    best = None
    for count in range(len(allowed) + 1):
        for panel in combinations(allowed, count):
            cost = _charge(request, panel, sensors)
            if cost > request['budget_cents']:
                continue
            covered = set().union(*(separators[name] for name in panel))
            if len(covered) == len(conflicts) and (best is None or (cost, panel) < best):
                best = cost, panel
    if best is None:
        return result
    return dict(result, status='PANEL_READY', panel=list(best[1]), cost_cents=best[0])


def verify_receipt(request, receipt):
    sensors = validate_request(request)
    fields = {'request_sha256', 'hypothesis_ids', 'status', 'panel', 'cost_cents', 'schema',
              'observations', 'attempted_sensors', 'incurred_cost_cents', 'action', 'scope',
              'physical_validity', 'model_completeness'}
    _keys(receipt, fields)
    if receipt['schema'] != 'omega-observation-receipt/v1' or receipt['scope'] != 'FINITE_AUTHORED_MODEL_ONLY':
        raise ValueError('FINITE_OBSERVATION_RECEIPT_REQUIRED')
    if receipt['physical_validity'] != 'UNKNOWN' or receipt['model_completeness'] != 'UNKNOWN':
        raise ValueError('UNSUPPORTED_PHYSICAL_OR_COMPLETENESS_CLAIM')
    expected = conventional_panel(request)
    for key in ('request_sha256', 'panel', 'cost_cents'):
        if type(receipt[key]) is not type(expected[key]) or receipt[key] != expected[key]:
            raise ValueError('REFERENCE_OBSERVATION_PLAN_MISMATCH:' + key)
    for key in ('observations', 'attempted_sensors', 'hypothesis_ids'):
        if type(receipt[key]) is not list:
            raise ValueError('OBSERVATION_TRANSCRIPT_LIST_REQUIRED')
    _int(receipt['incurred_cost_cents'], True)
    attempted = receipt['attempted_sensors']
    if attempted != expected['panel'][:len(attempted)] or len(attempted) > len(expected['panel']):
        raise ValueError('OBSERVATION_ATTEMPT_ORDER_CHANGED')
    readings = receipt['observations']
    prior = request['prior_observations']
    if readings[:len(prior)] != prior:
        raise ValueError('PRIOR_OBSERVATIONS_CHANGED')
    _validate_readings(request, readings, sensors)
    acquired = readings[len(prior):]
    if [r['sensor_id'] for r in acquired] != attempted[:len(acquired)] or len(acquired) > len(attempted):
        raise ValueError('OBSERVATION_TRANSCRIPT_ORDER_CHANGED')
    if receipt['incurred_cost_cents'] != _charge(request, attempted, sensors):
        raise ValueError('OBSERVATION_CHARGE_MISMATCH')
    worlds = _posterior(request, readings, sensors)
    if receipt['hypothesis_ids'] != [w['id'] for w in worlds]:
        raise ValueError('OBSERVATION_POSTERIOR_MISMATCH')
    status = receipt['status']
    if expected['status'] != 'PANEL_READY':
        if attempted or acquired or status != expected['status'] or receipt['action'] is not None:
            raise ValueError('UNAVAILABLE_PLAN_WAS_EXECUTED')
    elif status in ('OBSERVATION_UNAVAILABLE', 'INVALID_OBSERVATION'):
        if not worlds or len(attempted) != len(acquired) + 1 or receipt['action'] is not None:
            raise ValueError('INVALID_OBSERVATION_FAILURE_TRANSCRIPT')
    elif status == 'OUT_OF_MODEL':
        if worlds or not acquired or len(acquired) != len(attempted) or receipt['action'] is not None:
            raise ValueError('INVALID_OUT_OF_MODEL_TRANSCRIPT')
        if not _posterior(request, readings[:-1], sensors):
            raise ValueError('EXECUTION_CONTINUED_AFTER_OUT_OF_MODEL')
    elif status == 'MODEL_DECISION':
        if attempted != expected['panel'] or len(acquired) != len(attempted) or not worlds:
            raise ValueError('INCOMPLETE_OBSERVATION_DECISION')
        actions = sorted(_actions(worlds))
        if not actions or receipt['action'] != actions[0]:
            raise ValueError('UNSUPPORTED_OBSERVATION_ACTION')
    else:
        raise ValueError('UNSUPPORTED_OBSERVATION_STATUS')
    return {'accepted': True, 'scope': 'FINITE_DECLARED_MODEL_AND_TRANSCRIPT',
            'request_sha256': digest(request), 'receipt_sha256': digest(receipt),
            'reference_status': expected['status'], 'reference_cost_cents': expected['cost_cents'],
            'observation_truth_verified': False, 'physical_calibration_verified': False,
            'failure_origin_verified': False}


def conventional_execute(request, observe):
    plan = conventional_panel(request)
    receipt = dict(plan, schema='omega-observation-receipt/v1',
                   observations=[dict(r) for r in request['prior_observations']],
                   attempted_sensors=[], incurred_cost_cents=0, action=None,
                   scope='FINITE_AUTHORED_MODEL_ONLY', physical_validity='UNKNOWN',
                   model_completeness='UNKNOWN')
    if plan['status'] != 'PANEL_READY':
        return receipt
    sensors = {s['id']: s for s in request['sensors']}
    for name in plan['panel']:
        receipt['attempted_sensors'].append(name)
        receipt['incurred_cost_cents'] = _charge(request, receipt['attempted_sensors'], sensors)
        try:
            value = observe(name)
        except (OSError, TimeoutError):
            receipt['status'] = 'OBSERVATION_UNAVAILABLE'
            return receipt
        if value is None:
            receipt['status'] = 'OBSERVATION_UNAVAILABLE'
            return receipt
        if type(value) is not int:
            receipt['status'] = 'INVALID_OBSERVATION'
            return receipt
        receipt['observations'].append({'sensor_id': name, 'sensor_sha256': digest(sensors[name]),
                                        'context_id': request['context_id'], 'value': value})
        worlds = _posterior(request, receipt['observations'], sensors)
        receipt['hypothesis_ids'] = [w['id'] for w in worlds]
        if not worlds:
            receipt['status'] = 'OUT_OF_MODEL'
            return receipt
    actions = sorted(_actions(_posterior(request, receipt['observations'], sensors)))
    receipt['status'] = 'MODEL_DECISION' if actions else 'UNRESOLVED'
    receipt['action'] = actions[0] if actions else None
    return receipt
