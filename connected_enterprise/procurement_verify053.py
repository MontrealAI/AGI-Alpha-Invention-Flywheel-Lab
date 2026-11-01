"""Ordinary all-or-none quote enumeration and independent selection checking.

No producer/search imports; no execution, source authority, finance or demand.
The caller separately binds quotes to actual current inputs and executable source.
"""
from itertools import combinations
import re

SERVICES = frozenset(('evidence_matrix', 'kpi_variance', 'reconciliation'))
KEYS = {'id', 'service_id', 'cost_microUSD', 'valid_from', 'valid_until', 'available',
        'input_sha256', 'source_sha256', 'scope'}
METADATA = {'search', 'policy', 'observation_sha256', 'budget_microUSD', 'now'}


def _validate(quotes, required_services, now, budget, assembly):
    if (type(required_services) not in (list, tuple) or len(required_services) != 3
            or set(required_services) != SERVICES):
        raise ValueError('EXACT_THREE_REQUIRED_SERVICES')
    if (type(now) is not int or now < 0 or type(budget) is not int or budget < 0
            or type(assembly) is not int or assembly < 0):
        raise ValueError('EXACT_CURRENT_TIME_BUDGET_AND_ASSEMBLY')
    if type(quotes) is not list or not quotes or len(quotes) > 24:
        raise ValueError('BOUNDED_QUOTE_OBSERVATIONS')
    seen = set()
    for q in quotes:
        if (type(q) is not dict or set(q) != KEYS or type(q['id']) is not str
                or not re.fullmatch(r'[a-z][a-z0-9_.-]{0,63}', q['id']) or q['id'] in seen
                or q['service_id'] not in SERVICES | {'operations_bundle'}):
            raise ValueError('EXACT_UNIQUE_SCOPED_QUOTE')
        seen.add(q['id'])
        if (type(q['cost_microUSD']) is not int or q['cost_microUSD'] <= 0
                or q['cost_microUSD'] % 10000 or type(q['available']) is not bool
                or type(q['valid_from']) is not int or type(q['valid_until']) is not int
                or not 0 <= q['valid_from'] < q['valid_until']):
            raise ValueError('EXACT_QUOTE_COST_AND_AVAILABILITY')
        if (q['scope'] != 'LOCAL_AUTHORED_CONTRACT_NOT_EXTERNAL_AGREEMENT'
                or any(type(q[k]) is not str or not re.fullmatch('[0-9a-f]{64}', q[k])
                       for k in ('input_sha256', 'source_sha256'))):
            raise ValueError('DECLARED_QUOTE_SOURCE_SCOPE')


def ordinary_select(quotes, required_services, now, budget_microUSD, assembly_cost_microUSD):
    """Find least complete cost, then fewest quotes, then sorted quote IDs.

    Enumerates all potentially optimal subsets, including integrated providers.
    Every quote has strictly positive cost and covers at least one of 3 services:
    any minimal cover has at most 3 quotes. A larger subset necessarily contains
    a redundant positive-cost quote and cannot be optimal. No supplier is omitted.
    """
    _validate(quotes, required_services, now, budget_microUSD, assembly_cost_microUSD)
    valid = [q for q in quotes if q['available'] and q['valid_from'] <= now < q['valid_until']]
    best = None
    for size in range(1, min(3, len(valid))+1):
        for chosen in combinations(valid, size):
            coverage = set()
            for q in chosen:
                coverage.update(SERVICES if q['service_id'] == 'operations_bundle' else [q['service_id']])
            if coverage != SERVICES:
                continue
            cost = sum(q['cost_microUSD'] for q in chosen) + assembly_cost_microUSD
            if cost > budget_microUSD:
                continue
            score = cost, len(chosen), tuple(sorted(q['id'] for q in chosen))
            if best is None or score < best:
                best = score
    if best is None:
        return dict(status='NO_COMPLETE_AFFORDABLE_BUNDLE', quote_ids=[], total_microUSD=None)
    return dict(status='READY', quote_ids=list(best[2]), total_microUSD=best[0])


def audit_selection(result, quotes, required_services, now, budget_microUSD, assembly_cost_microUSD):
    """Check optimum against independent ordinary enumeration, not claimed search.

    Does not authenticate supplied quote hashes, providers or demand. A READY
    receipt is a local arithmetic procurement proposal, never spending authority.
    """
    errors = []
    expected = None
    try:
        expected = ordinary_select(quotes, required_services, now, budget_microUSD, assembly_cost_microUSD)
        if (type(result) is not dict or not set(expected) <= set(result)
                or set(result) - set(expected) - METADATA):
            raise ValueError('EXACT_SELECTION_FIELDS')
        if type(result['quote_ids']) is not list or any(type(x) is not str for x in result['quote_ids']):
            raise ValueError('EXACT_QUOTE_ID_LIST')
        if result['total_microUSD'] is not None and type(result['total_microUSD']) is not int:
            raise ValueError('EXACT_INTEGER_SELECTION_COST')
        if any(result[k] != expected[k] for k in expected):
            raise ValueError('NOT_CURRENT_COMPLETE_ORDINARY_OPTIMUM')
        if 'now' in result and (type(result['now']) is not int or result['now'] != now):
            raise ValueError('STALE_SELECTION_TIME')
        if 'budget_microUSD' in result and (type(result['budget_microUSD']) is not int or result['budget_microUSD'] != budget_microUSD):
            raise ValueError('CHANGED_SELECTION_BUDGET')
    except (ValueError, TypeError, KeyError) as error:
        errors.append(str(error))
    return dict(accepted=not errors, errors=errors, ordinary_optimum=expected,
                scope='FINITE_LOCAL_QUOTE_OPTIMUM_NOT_EXECUTION_DEMAND_OR_AUTHORITY')
