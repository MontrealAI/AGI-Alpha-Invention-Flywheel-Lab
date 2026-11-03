"""Integer water reuse constructor. A blueprint is not physical safety evidence."""
from __future__ import annotations
from itertools import product
from math import prod
from mechanism_harness.core import digest


def _integer(value, label):
    if type(value) is not int or value < 0:
        raise ValueError('NONNEGATIVE_INTEGER_REQUIRED:' + label)
    return value


def validate(request):
    if set(request) != {'schema', 'name', 'sources', 'sinks', 'freshwater_cap', 'model_route'}:
        raise ValueError('EXACT_REQUEST_FIELDS_REQUIRED')
    if request['schema'] != 'omega-water/v1' or request['model_route'] not in {'local', 'buyer_owned_account_external'}:
        raise ValueError('UNKNOWN_SCHEMA_OR_MODEL_ROUTE')
    if not isinstance(request['name'], str) or not request['name']:
        raise ValueError('REQUEST_NAME_REQUIRED')
    if not isinstance(request['sources'], list) or not isinstance(request['sinks'], list) or not request['sinks']:
        raise ValueError('SOURCE_AND_SINK_LIST_REQUIRED')
    _integer(request['freshwater_cap'], 'freshwater_cap')
    ids = []
    for source in request['sources']:
        if set(source) != {'id', 'capacity', 'upper_quality', 'unit_cost_cents', 'consent'}:
            raise ValueError('EXACT_SOURCE_FIELDS_REQUIRED')
        _integer(source['capacity'], 'capacity')
        _integer(source['unit_cost_cents'], 'unit_cost_cents')
        if type(source['consent']) is not bool:
            raise ValueError('EXPLICIT_SOURCE_CONSENT_REQUIRED')
        ids.append(source['id'])
        if not isinstance(source['upper_quality'], list) or len(source['upper_quality']) != 2:
            raise ValueError('TWO_CONTAMINANTS_REQUIRED')
        for value in source['upper_quality']:
            _integer(value, 'upper_quality')
    for sink in request['sinks']:
        if set(sink) != {'id', 'demand', 'max_quality', 'fresh_unit_cost_cents', 'consent'}:
            raise ValueError('EXACT_SINK_FIELDS_REQUIRED')
        _integer(sink['demand'], 'demand')
        _integer(sink['fresh_unit_cost_cents'], 'fresh_unit_cost_cents')
        if type(sink['consent']) is not bool:
            raise ValueError('EXPLICIT_SINK_CONSENT_REQUIRED')
        ids.append(sink['id'])
        if not isinstance(sink['max_quality'], list) or len(sink['max_quality']) != 2:
            raise ValueError('TWO_CONTAMINANTS_REQUIRED')
        for value in sink['max_quality']:
            _integer(value, 'max_quality')
    if any(type(x) is not str or not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError('UNIQUE_PARTICIPANT_IDS_REQUIRED')
    return request


def _sink_options(request, sink, max_options):
    """Construct robust endpoint-feasible integer choices for one sink."""
    sources = request['sources']
    if not sink['consent']:
        return []  # Cannot deliver its required production without its participation.
    choices = []
    ranges = [range(min(s['capacity'], sink['demand']) + 1) if s['consent'] else range(1) for s in sources]
    if prod(len(values) for values in ranges) > max_options:
        raise RuntimeError('RESOURCE_CHECKPOINT_NOT_INFEASIBILITY')
    for count, amounts in enumerate(product(*ranges), 1):
        if count > max_options:
            raise RuntimeError("RESOURCE_CHECKPOINT_NOT_INFEASIBILITY")
        fresh = sink['demand'] - sum(amounts)
        if fresh < 0:
            continue
        if any(sum(x * s['upper_quality'][c] for x, s in zip(amounts, sources)) > sink['demand'] * sink['max_quality'][c] for c in range(2)):
            continue
        cost = sum(x * s['unit_cost_cents'] for x, s in zip(amounts, sources)) + fresh * sink['fresh_unit_cost_cents']
        if cost <= sink['demand'] * sink['fresh_unit_cost_cents']:
            choices.append((amounts, fresh, cost))
    return choices


def construct(request, *, max_states=200000):
    """DP over cumulative source use; finite resource exhaustion is not infeasibility."""
    validate(request)
    if type(max_states) is not int or max_states <= 0:
        raise ValueError('POSITIVE_STATE_BUDGET_REQUIRED')
    zero = tuple(0 for _ in request['sources'])
    # Dominance: identical cumulative source use has identical remaining capacity
    # and freshwater requirement; keep the least-cost allocation at that state.
    frontier = {zero: (0, [], [])}
    examined = 0
    for sink in request['sinks']:
        options = _sink_options(request, sink, max_states)
        nxt = {}
        for used, (cost, allocations, freshwaters) in frontier.items():
            for amounts, fresh, sink_cost in options:
                examined += 1
                if examined > max_states:
                    raise RuntimeError('RESOURCE_CHECKPOINT_NOT_INFEASIBILITY')
                total = tuple(a + b for a, b in zip(used, amounts))
                if any(x > s['capacity'] for x, s in zip(total, request['sources'])):
                    continue
                record = (cost + sink_cost, allocations + [list(amounts)], freshwaters + [fresh])
                if sum(record[2]) > request['freshwater_cap']:
                    continue
                if total not in nxt or record < nxt[total]:
                    nxt[total] = record
        frontier = nxt
    if not frontier:
        return {'request_sha256': digest(request), 'status': 'MODEL_INFEASIBLE', 'allocation': None, 'freshwater': None, 'objective': None}
    best = min(frontier.values(), key=lambda row: (sum(row[2]), row[0], row[1]))
    return {'request_sha256': digest(request), 'status': 'MODEL_PLAN', 'allocation': best[1], 'freshwater': best[2], 'objective': [sum(best[2]), best[0]]}


def conventional_milp(request):
    """Independent complete MILP. Software is not slowed to human work speed.

    Lexicographic objective: min freshwater, then total operating cost. The
    upper cost bound makes the integer scalarization exact. No use of the DP's
    options, transitions or checker. Returned float values are rounded only
    after explicit integer tolerance and then independently checked.
    """
    validate(request)
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    ns, nk = len(request['sources']), len(request['sinks'])
    stride = ns + 1
    n = nk * stride
    c = np.zeros(n)
    upper = np.zeros(n)
    max_cost = sum(k['demand'] * k['fresh_unit_cost_cents'] for k in request['sinks'])
    weight = max_cost + 1
    rows, lo, hi = [], [], []
    def constraint(coefficients, lower, upper_bound):
        rows.append(coefficients); lo.append(lower); hi.append(upper_bound)
    for j, sink in enumerate(request['sinks']):
        row = np.zeros(n)
        for i, source in enumerate(request['sources']):
            idx = j * stride + i
            upper[idx] = min(source['capacity'], sink['demand']) if source['consent'] and sink['consent'] else 0
            c[idx] = source['unit_cost_cents']
            row[idx] = 1
        f = j * stride + ns
        upper[f] = sink['demand'] if sink['consent'] else 0
        c[f] = weight + sink['fresh_unit_cost_cents']
        row[f] = 1
        constraint(row, sink['demand'], sink['demand'])
        for contaminant in range(2):
            quality = np.zeros(n)
            for i, source in enumerate(request['sources']):
                quality[j * stride + i] = source['upper_quality'][contaminant]
            constraint(quality, -np.inf, sink['demand'] * sink['max_quality'][contaminant])
        cost = np.zeros(n)
        for i, source in enumerate(request['sources']):
            cost[j * stride + i] = source['unit_cost_cents']
        cost[f] = sink['fresh_unit_cost_cents']
        constraint(cost, -np.inf, sink['demand'] * sink['fresh_unit_cost_cents'])
    for i, source in enumerate(request['sources']):
        row = np.zeros(n)
        row[i::stride] = 1
        constraint(row, -np.inf, source['capacity'])
    row = np.zeros(n); row[ns::stride] = 1
    constraint(row, -np.inf, request['freshwater_cap'])
    answer = milp(c=c, integrality=np.ones(n), bounds=Bounds(np.zeros(n), upper), constraints=LinearConstraint(np.array(rows), np.array(lo), np.array(hi)), options={'mip_rel_gap': 0.0})
    if answer.status == 2:
        return {'request_sha256': digest(request), 'status': 'MODEL_INFEASIBLE', 'allocation': None, 'freshwater': None, 'objective': None}
    if answer.status != 0 or answer.x is None or max(abs(x-round(x)) for x in answer.x) > 1e-6:
        raise RuntimeError('CONVENTIONAL_SOLVER_UNRESOLVED_NOT_INFEASIBLE')
    amounts = [[round(answer.x[j*stride+i]) for i in range(ns)] for j in range(nk)]
    fresh = [round(answer.x[j*stride+ns]) for j in range(nk)]
    cost = sum(sum(x*s['unit_cost_cents'] for x,s in zip(row, request['sources']))+f*k['fresh_unit_cost_cents'] for row,f,k in zip(amounts,fresh,request['sinks']))
    return {'request_sha256': digest(request), 'status': 'MODEL_PLAN', 'allocation': amounts, 'freshwater': fresh, 'objective': [sum(fresh), cost]}
