"""Optional externally funded recurring buyer purchasing capacity in native commerce.

An authored outside-buyer income schedule is neither buyer demand nor a
receipt of enterprise revenue. Native accounts remain sole financial authority.
"""
from __future__ import annotations

SCHEMA = 'agi-alpha/connected014-buyer-income/v1'
EVIDENCE = 'AUTHORED_EXOGENOUS_BUYER_INCOME_NOT_ENTERPRISE_REVENUE'


def validate_policy(value, horizon_days):
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
