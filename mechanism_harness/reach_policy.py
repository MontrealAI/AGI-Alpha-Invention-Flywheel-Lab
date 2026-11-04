"""Public decision rule and separate, finite synthetic buyer environment.

An exposure is a contact right. Only the native operator can spend or collect.
The investment function accepts dated business observations, never buyer types,
simulation seeds, scenario labels or the other arm's results.
"""
from __future__ import annotations

import hashlib
import json

from connected_enterprise.channels import default_contracts
from . import cart_program


ARMS = ('organic', 'pilot')
SCENARIOS = ('central', 'weak', 'copycat', 'no_demand', 'failed_activation')
COHORT_SEED = 2026110401
CHANNEL_SEED = 2026110403
JOB_SEED = 392900
JOBS_PER_SERVICE = 132
DAILY_UNITS = 2
ANNUAL_UNITS = 48
DECISION_DAYS = (90, 118)
CENT = 10_000
MAINTENANCE_MICROUSD = 1200 * CENT
QUOTE_MICROUSD = 10 * CENT
PROSPECTS = tuple(f'reach-{n:03d}' for n in range(24))
ORGANIC_ROSTER = PROSPECTS[:12]


def _integer(value, *, signed=False):
    if type(value) is not int or (not signed and value < 0):
        raise ValueError('INTEGER_REACH_OBSERVATION_REQUIRED')
    return value


def _day(value):
    if not 0 <= _integer(value) < 365:
        raise ValueError('REGISTERED_DAY_REQUIRED')
    return value


def _prospect(customer_id):
    if customer_id not in PROSPECTS:
        raise ValueError('REGISTERED_FRESH_PROSPECT_REQUIRED')
    return customer_id


def _scenario(value):
    if value not in SCENARIOS:
        raise ValueError('REGISTERED_SCENARIO_REQUIRED')


def _draw(seed, purpose, customer_id, day):
    raw = json.dumps([_integer(seed), purpose, _prospect(customer_id), _day(day)],
                     separators=(',', ':')).encode('ascii')
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], 'big')


def population():
    """Only public identifiers, including the organic/paid overlap."""
    return [{'id': customer_id} for customer_id in PROSPECTS]


def warm(day):
    day = _day(day)
    if 5 <= day <= 83 and (day - 2) % 3 == 0:
        return [(day - 2) // 3]
    return []


def organic(day):
    day = _day(day)
    if 92 <= day <= 169 and (day - 92) % 7 == 0:
        return [ORGANIC_ROSTER[(day - 92) // 7]]
    return []


def contracts(scenario):
    _scenario(scenario)
    terms = default_contracts()['pilot']
    if scenario == 'failed_activation':
        terms['activation_reliability_bps'] = 0
    return {'pilot': terms}


def route(day, organic_ids, paid_exposures):
    """Deduplicate across sources. Preserve native ChannelBook ordering."""
    if organic_ids != organic(day):
        raise ValueError('REGISTERED_ORGANIC_ROSTER_REQUIRED')
    result = [{'customer_id': buyer, 'source': 'organic', 'source_plan_id': None,
               'exposure_id': f'organic-{day}-{buyer}', 'paid_exclusive': False}
              for buyer in organic_ids]
    seen_paid = set()
    seen_exposures = set()
    for exposure in paid_exposures:
        buyer = _prospect(exposure['customer_id'])
        plan, ident = exposure['source_plan_id'], exposure['exposure_id']
        if (not isinstance(plan, str) or not plan or not isinstance(ident, str) or not ident
                or buyer in seen_paid or ident in seen_exposures):
            raise ValueError('UNIQUE_SOURCE_BOUND_CHANNEL_EXPOSURE_REQUIRED')
        seen_paid.add(buyer)
        seen_exposures.add(ident)
        if buyer not in organic_ids:
            result.append({'customer_id': buyer, 'source': 'paid', 'source_plan_id': plan,
                           'exposure_id': ident, 'paid_exclusive': buyer not in ORGANIC_ROSTER})
    return result


def qualification(customer_id, day, prior_settled, *, seed=COHORT_SEED):
    """Invoke only after the contact's quote cost. Retention is a hypothesis."""
    threshold = 5000 if _integer(prior_settled) else 7500
    return _draw(seed, 'qualify', customer_id, day) % 10_000 < threshold


def _type(market, customer_id, seed):
    types = market['types']
    total = sum(_integer(t['weight']) for t in types)
    if not total:
        raise ValueError('POSITIVE_TYPE_WEIGHT_REQUIRED')
    point = _draw(seed, 'type', customer_id, 0) % total
    for typ in types:
        if point < typ['weight']:
            return typ
        point -= typ['weight']
    raise ValueError('UNREACHABLE_TYPE_WEIGHT')


def lifetime_budget(market, customer_id, *, seed=COHORT_SEED):
    return 2 * _integer(_type(market, customer_id, seed)['budget_cents'])


def profile(market, program, customer_id, day, scenario, spent_cents, *,
            chooser=cart_program.buyer_choose, seed=COHORT_SEED):
    """Private fresh-buyer environment. The wallet is never itself a sale."""
    _day(day)
    _scenario(scenario)
    typ = _type(market, customer_id, seed)
    cap = _integer(typ['budget_cents'])
    remaining = 2 * cap - _integer(spent_cents)
    if remaining < 0:
        raise ValueError('LIFETIME_WALLET_OVERSPENT')
    values = list(typ['values'])
    if scenario == 'weak':
        values = [v // 2 for v in values]
    elif scenario == 'no_demand':
        values = [0] * len(values)
    private = {'values': values, 'budget_cents': min(cap, remaining),
               'outside_utility': typ['outside_utility']}
    if scenario == 'copycat':
        private['outside_utility'] += chooser(market, program, private)['utility_cents']
    return private


def tranche_id(day):
    if _day(day) not in DECISION_DAYS:
        raise ValueError('REGISTERED_TRANCHE_DAY_REQUIRED')
    return f'reach-pilot-{DECISION_DAYS.index(day) + 1}'


def decide(arm, day, available_microUSD, earned_microUSD, warm_settled,
           first_invoice_microUSD, first_exclusive_settled, first_exclusive_collections_microUSD,
           first_paid_variable_costs_microUSD, warm_contribution_microUSD):
    """Compare a bounded trial or renewal against the option to decline."""
    plan = tranche_id(day)
    if arm not in ARMS:
        raise ValueError('REGISTERED_ARM_REQUIRED')
    terms = default_contracts()['pilot']
    invoice = terms['price_microUSD'] + terms['support_microUSD']
    max_quotes = terms['slots_per_day'] * terms['duration_days']
    observed = {
        'available_microUSD': _integer(available_microUSD, signed=True),
        'earned_microUSD': _integer(earned_microUSD, signed=True),
        'warm_settled': _integer(warm_settled),
        'warm_contribution_microUSD': _integer(warm_contribution_microUSD, signed=True),
        'first_invoice_microUSD': _integer(first_invoice_microUSD),
        'first_exclusive_settled': _integer(first_exclusive_settled),
        'first_exclusive_collections_microUSD': _integer(first_exclusive_collections_microUSD),
        'first_paid_variable_costs_microUSD': _integer(first_paid_variable_costs_microUSD),
    }
    if (first_invoice_microUSD not in (0, invoice)
            or (first_invoice_microUSD and day == DECISION_DAYS[0])
            or (not first_invoice_microUSD and
                any((first_exclusive_settled, first_exclusive_collections_microUSD, first_paid_variable_costs_microUSD)))
            or (not first_exclusive_settled and first_exclusive_collections_microUSD)):
        raise ValueError('DUE_PRIOR_TRANCHE_OBSERVATIONS_REQUIRED')
    attribution = first_exclusive_collections_microUSD - first_paid_variable_costs_microUSD - first_invoice_microUSD
    if day == DECISION_DAYS[0]:
        gross = 2 * warm_contribution_microUSD // warm_settled if warm_settled else 0
        expected = gross - invoice - max_quotes * QUOTE_MICROUSD
    else:
        expected = attribution
    if arm == 'organic':
        reason = 'ORGANIC_CONTROL'
    elif not warm_settled:
        reason = 'NO_WARM_COLLECTION'
    elif day == DECISION_DAYS[1] and not first_invoice_microUSD:
        reason = 'FIRST_INVOICE_ABSENT'
    elif day == DECISION_DAYS[1] and not first_exclusive_settled:
        reason = 'NO_EXCLUSIVE_COLLECTION'
    elif expected <= 0:
        reason = 'NONPOSITIVE_EXPECTED_NET'
    elif earned_microUSD < invoice:
        reason = 'INSUFFICIENT_UNRESTRICTED_EARNINGS'
    elif available_microUSD < invoice + MAINTENANCE_MICROUSD:
        reason = 'INSUFFICIENT_AVAILABLE_AFTER_MAINTENANCE'
    else:
        reason = 'FUNDED_TRIAL' if day == DECISION_DAYS[0] else 'FUNDED_RENEWAL'
    action = 'BUY' if reason in ('FUNDED_TRIAL', 'FUNDED_RENEWAL') else 'SKIP'
    return {'arm': arm, 'day': day, 'plan': plan, 'action': action, 'reason': reason,
            'observed': observed, 'invoice_microUSD': invoice, 'expected_net_microUSD': expected,
            'attributed_pretax_microUSD': attribution}
