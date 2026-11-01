"""Explicit outside purchasing capacity; never enterprise revenue or authority.

Adapts PR72's native income schedule to current complete-offer commerce.
Stochastic income remains environment-private on legacy offers. Complete-offer
forecasts support deterministic receipt/failure only, rather than leaking the
realized private draw or pretending to solve the missing posterior problem.
"""
from __future__ import annotations
import copy
from bisect import bisect_right

SCHEMA = 'agi-alpha/connected014-buyer-income/v1'
EVIDENCE = 'AUTHORED_EXOGENOUS_BUYER_INCOME_NOT_ENTERPRISE_REVENUE'


def validate_policy(value, horizon_days):
    if type(horizon_days) is not int or horizon_days < 1:
        raise ValueError('POSITIVE_OPERATING_HORIZON_REQUIRED')
    if not isinstance(value, dict) or set(value) != {'schema', 'first_day', 'period_days', 'income_microUSD', 'receipt_bps'} or value.get('schema') != SCHEMA:
        raise ValueError('EXACT_EXTERNAL_BUYER_INCOME_POLICY_REQUIRED')
    for name in ('first_day', 'period_days', 'income_microUSD'):
        if type(value[name]) is not int or value[name] < 1:
            raise ValueError('POSITIVE_EXTERNAL_BUYER_INCOME_TERM_REQUIRED:' + name)
    if type(value['receipt_bps']) is not int or not 0 <= value['receipt_bps'] <= 10000:
        raise ValueError('EXOGENOUS_BUYER_INCOME_BPS_REQUIRED')
    if value['first_day'] >= horizon_days:
        raise ValueError('EXTERNAL_INCOME_MUST_OCCUR_WITHIN_OPERATING_HORIZON')
    return value


def due_days(policy, horizon_days):
    validate_policy(policy, horizon_days)
    return range(policy['first_day'], horizon_days, policy['period_days'])


def validate_configuration(cfg):
    p = cfg.get('buyer_income_policy')
    if p is None:
        return
    validate_policy(p, cfg['horizon_days'])
    if 'complete_offer_policy' in cfg:
        if p['receipt_bps'] not in (0, 10000):
            raise ValueError('STOCHASTIC_COMPLETE_INCOME_POSTERIOR_UNAVAILABLE')
        maximum = len(due_days(p, cfg['horizon_days'])) * p['income_microUSD'] if p['receipt_bps'] else 0
        # Preserve the existing market's numeric validation, before any account.
        from .complete_offer_market import _int
        for profile in cfg['complete_offer_policy']['profiles']:
            for atom in profile['atoms']:
                _int(atom['budget_microUSD'] + maximum)


def public_accrued(cfg, moment):
    """Only publicly certain funding ALREADY due in this declared scenario."""
    if type(moment) is not int or moment < 0:
        raise ValueError('NONNEGATIVE_INTEGER_OBSERVATION_TIME_REQUIRED')
    p = cfg.get('buyer_income_policy')
    if p is None:
        return 0
    validate_policy(p, cfg['horizon_days'])
    if p['receipt_bps'] not in (0, 10000):
        raise ValueError('STOCHASTIC_COMPLETE_INCOME_POSTERIOR_UNAVAILABLE')
    last_day = min(moment // 24, cfg['horizon_days'] - 1)
    count = max(0, (last_day - p['first_day']) // p['period_days'] + 1)
    return count * p['income_microUSD'] if p['receipt_bps'] else 0


def public_context(context, cfg, moment):
    """Shift all public budget hypotheses equally; no seed or private state."""
    increment = public_accrued(cfg, moment)
    result = copy.deepcopy(context)
    if increment:
        for atom in result['profile']['atoms']:
            atom['budget_microUSD'] += increment
        from .complete_offer_market import validate_context
        validate_context(result)
    return result


def income_index(result):
    """Read-only dated receipts; caller must independently validate the trace."""
    indexed = {}
    for event in result['events']:
        if event['kind'] == 'EXTERNAL_BUYER_INCOME':
            times, sums = indexed.setdefault(event['customer_id'], ([], []))
            if times and event['time'] <= times[-1]:
                raise ValueError('STRICT_DATED_BUYER_INCOME_REQUIRED')
            times.append(event['time'])
            sums.append(event['amount_microUSD'] + (sums[-1] if sums else 0))
    return indexed


def received_by(indexed, customer, moment):
    times, sums = indexed.get(customer, ([], []))
    i = bisect_right(times, moment)
    return sums[i - 1] if i else 0


def audit_income(result):
    """Independently reconstruct receipts, totals and causal placement."""
    from .verify import _private_draw
    cfg, seed = result['config'], result['seed']
    buyers = result['buyers']
    actual = [e for e in result['events'] if e['kind'] == 'EXTERNAL_BUYER_INCOME']
    if any(type(e.get('amount_microUSD')) is not int or type(e.get('time')) is not int for e in actual):
        raise ValueError('TYPED_EXTERNAL_BUYER_INCOME_RECEIPT_REQUIRED')
    p = cfg.get('buyer_income_policy')
    if p is None:
        if actual or any('external_income_total' in b for b in buyers):
            raise ValueError('UNREGISTERED_EXTERNAL_BUYER_INCOME')
        return {}
    validate_configuration(cfg)
    expected, totals = [], {b['id']: 0 for b in buyers}
    for day in due_days(p, cfg['horizon_days']):
        for buyer in sorted(buyers, key=lambda b: int(b['id'].rsplit('-', 1)[1])):
            if _private_draw(seed, [day, buyer['id']], 'buyer-external-income') < p['receipt_bps'] / 10000:
                amount = p['income_microUSD']
                expected.append({'id': f"external-income-{day:06d}-{buyer['id']}", 'time': day * 24,
                    'kind': 'EXTERNAL_BUYER_INCOME', 'customer_id': buyer['id'],
                    'amount_microUSD': amount, 'evidence_role': EVIDENCE})
                totals[buyer['id']] += amount
    if actual != expected or any(type(b.get('external_income_total')) is not int or b['external_income_total'] != totals[b['id']] for b in buyers):
        raise ValueError('EXOGENOUS_BUYER_INCOME_NOT_REDERIVED_FROM_FROZEN_POLICY')
    first_business = {}
    for position, event in enumerate(result['events']):
        if event['kind'] in {'EXPOSURE', 'REACTIVATION_RESPONSE', 'INVESTMENT', 'QUALIFIED_ORDER', 'BUSINESS_DECISION'}:
            first_business.setdefault(event['time'], position)
        if event['kind'] == 'EXTERNAL_BUYER_INCOME' and first_business.get(event['time'], position + 1) < position:
            raise ValueError('EXOGENOUS_BUYER_INCOME_AFTER_SAME_DAY_BUSINESS_DECISION')
    return {'external_buyer_income_events_recomputed': len(expected),
        'external_buyer_income_microUSD_recomputed': sum(totals.values()),
        'income_is_enterprise_collection': False}
