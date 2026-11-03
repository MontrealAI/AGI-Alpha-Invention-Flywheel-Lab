"""Independent, exact acceptance replay; it never invokes either producer."""
from itertools import product
from mechanism_harness.core import digest
from .water import validate


def verify(request, plan):
    validate(request)  # Shared schema only; no producer/search invocation.
    if set(plan) != {"request_sha256", "status", "allocation", "freshwater", "objective"}:
        raise ValueError("EXACT_PLAN_FIELDS_REQUIRED")
    if plan.get('request_sha256') != digest(request):
        raise ValueError('REQUEST_BINDING_MISMATCH')
    if plan.get('status') != 'MODEL_PLAN':
        raise ValueError('NO_DELIVERED_PLAN_TO_ACCEPT')
    sinks, sources = request['sinks'], request['sources']
    if type(plan.get('allocation')) is not list or len(plan['allocation']) != len(sinks) or type(plan.get('freshwater')) is not list or len(plan['freshwater']) != len(sinks):
        raise ValueError('PLAN_DIMENSIONS')
    total = [0] * len(sources)
    cost, fresh_total = 0, 0
    for sink, row, fresh in zip(sinks, plan['allocation'], plan['freshwater']):
        if type(row) is not list or len(row) != len(sources) or any(type(x) is not int or x < 0 for x in row) or type(fresh) is not int or fresh < 0:
            raise ValueError('EXACT_NONNEGATIVE_PLAN_REQUIRED')
        if not sink['consent'] or sum(row) + fresh != sink['demand']:
            raise ValueError('SINK_CONSENT_OR_BALANCE')
        sink_cost = fresh * sink['fresh_unit_cost_cents']
        for i, (source, amount) in enumerate(zip(sources, row)):
            if amount and not source['consent']:
                raise ValueError('SOURCE_DID_NOT_CONSENT')
            total[i] += amount
            sink_cost += amount * source['unit_cost_cents']
        for q in range(2):
            load = sum(row[i] * sources[i]['upper_quality'][q] for i in range(len(sources)))
            if load > sink['demand'] * sink['max_quality'][q]:
                raise ValueError('WORST_CASE_QUALITY_EXCEEDED')
        if sink_cost > sink['demand'] * sink['fresh_unit_cost_cents']:
            raise ValueError('SINK_OUTSIDE_OPTION_EXCEEDED')
        cost += sink_cost
        fresh_total += fresh
    if any(x > s['capacity'] for x,s in zip(total,sources)) or fresh_total > request['freshwater_cap']:
        raise ValueError('SHARED_CAPACITY_EXCEEDED')
    if type(plan.get('objective')) is not list or len(plan['objective']) != 2 or any(type(x) is not int or x < 0 for x in plan['objective']):
        raise ValueError('EXACT_INTEGER_OBJECTIVE_REQUIRED')
    if plan.get('objective') != [fresh_total, cost]:
        raise ValueError('OBJECTIVE_MISMATCH')
    return {'accepted': True, 'request_sha256': digest(request), 'plan_sha256': digest(plan), 'freshwater_units': fresh_total, 'reuse_units': sum(total), 'operating_cost_cents': cost, 'scope': 'EXACT_AUTHORED_MODEL_ONLY_NOT_PHYSICAL_OR_REGULATORY_QUALIFICATION', 'authority': []}


def corner_check(request, plan):
    """Check every independent 0/upper quality corner for these tiny fixtures.

    Nonnegative flows and monotone upper-bound constraints justify upper-endpoint
    robustness. This does not cover nonlinear reactions, pathogens, correlations
    with decisions, measurement error outside declared intervals or safety.
    """
    verify(request, plan)
    if 2 ** (2 * len(request["sources"])) > 4096:
        raise RuntimeError("CORNER_RESOURCE_CHECKPOINT_NOT_INFEASIBILITY")
    corners = 0
    for bits in product((0, 1), repeat=2*len(request['sources'])):
        corners += 1
        for sink, amounts in zip(request['sinks'], plan['allocation']):
            for q in range(2):
                load = sum(amounts[i]*source['upper_quality'][q]*bits[2*i+q] for i,source in enumerate(request['sources']))
                if load > sink['demand']*sink['max_quality'][q]:
                    raise ValueError('CORNER_FAILED')
    return corners


def exhaustive_optimum(request, *, max_candidates=1000000):
    """Independent integer oracle for the finite fixtures, no floating tolerance.

    Enumerates every source-to-sink integer allocation, deriving freshwater from
    each demand. Never invokes either constructor. Resource refusal is not an
    infeasibility proof. This is a verification oracle, not a scalable competitor.
    """
    validate(request)
    if type(max_candidates) is not int or max_candidates <= 0:
        raise ValueError('POSITIVE_CANDIDATE_BUDGET_REQUIRED')
    sources, sinks = request['sources'], request['sinks']
    widths = [min(source['capacity'],sink['demand'])+1 for sink in sinks for source in sources]
    candidate_count = 1
    for width in widths:
        if width > max_candidates // candidate_count:
            raise RuntimeError('EXACT_ORACLE_RESOURCE_CHECKPOINT_NOT_INFEASIBILITY')
        candidate_count *= width
    ranges = [range(width) for width in widths]
    best, examined = None, 0
    ns = len(sources)
    for flat in product(*ranges):
        examined += 1
        allocation = [list(flat[j*ns:(j+1)*ns]) for j in range(len(sinks))]
        fresh = [sink['demand']-sum(row) for sink,row in zip(sinks,allocation)]
        cost = sum(sum(amount*source['unit_cost_cents'] for amount,source in zip(row,sources))+f*sink['fresh_unit_cost_cents'] for sink,row,f in zip(sinks,allocation,fresh))
        proposal = {'request_sha256': digest(request), 'status':'MODEL_PLAN', 'allocation':allocation, 'freshwater':fresh, 'objective':[sum(fresh),cost]}
        try:
            verify(request,proposal)
        except ValueError:
            continue
        if best is None or proposal['objective'] < best:
            best = proposal['objective']
    return {'objective':best, 'allocations_exhausted':examined, 'scope':'EXHAUSTIVE_INTEGER_MODEL_OPTIMUM_ONLY'}
