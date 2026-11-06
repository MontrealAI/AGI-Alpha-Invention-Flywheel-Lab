"""Exact public-quote planning; no buyer-private input or spending authority.

An opt-in instrument, not a new enterprise controller. Callers must still obtain
voluntary orders and reserve through the canonical native account. Price sources,
scope comparability and the complete cost envelope are supplied assumptions;
this function cannot authenticate a market quote or establish demand.
"""
from __future__ import annotations

import hashlib
import json

SCHEMA = 'genesis-public-quote/v2'
FIELDS = {'schema', 'now_hour', 'acceptance_id', 'friction_microUSD',
          'non_tax_cost_microUSD', 'minimum_contribution_microUSD',
          'tick_microUSD', 'alternatives', 'tax_numerator', 'tax_denominator',
          'tax_deduction_before_closing_microUSD'}
QUOTE_FIELDS = {'source_id', 'acceptance_id', 'price_microUSD',
                'observed_hour', 'valid_until_hour', 'complete'}


def _integer(value, *, positive=False):
    if type(value) is not int or value < int(positive):
        raise ValueError('EXACT_NONNEGATIVE_INTEGER_REQUIRED')


def _text(value):
    if type(value) is not str or not value.strip():
        raise ValueError('NONEMPTY_SOURCE_AND_ACCEPTANCE_REQUIRED')


def decide(observation):
    """Highest price tick strictly cheaper after friction, subject to full cost.

    This is optimal only within the declared comparable-price/tick feasible set.
    It does not optimize unknown demand or guarantee profitable collected work.
    Strict input fields reject accidentally passed hidden world/scenario data.
    """
    if type(observation) is not dict or set(observation) != FIELDS:
        raise ValueError('PUBLIC_OBSERVATION_FIELDS_REQUIRED')
    if observation['schema'] != SCHEMA:
        raise ValueError('PUBLIC_OBSERVATION_SCHEMA_REQUIRED')
    for key in ('now_hour', 'friction_microUSD', 'non_tax_cost_microUSD',
                'tax_numerator', 'tax_deduction_before_closing_microUSD'):
        _integer(observation[key])
    for key in ('tick_microUSD', 'minimum_contribution_microUSD', 'tax_denominator'):
        _integer(observation[key], positive=True)
    _text(observation['acceptance_id'])
    if (observation['tax_numerator']>observation['tax_denominator'] or
            observation['tax_deduction_before_closing_microUSD']>observation['non_tax_cost_microUSD']):
        raise ValueError('SUPPORTED_TAX_PROVISION_REQUIRED')
    alternatives = observation['alternatives']
    if type(alternatives) is not list:
        raise ValueError('PUBLIC_ALTERNATIVES_REQUIRED')
    seen = set()
    usable = bool(alternatives)
    for quote in alternatives:
        if type(quote) is not dict or set(quote) != QUOTE_FIELDS:
            raise ValueError('EXACT_PUBLIC_QUOTE_REQUIRED')
        for key in ('source_id', 'acceptance_id'):
            _text(quote[key])
        for key in ('price_microUSD', 'observed_hour', 'valid_until_hour'):
            _integer(quote[key])
        if type(quote['complete']) is not bool:
            raise ValueError('EXPLICIT_COMPLETE_QUOTE_REQUIRED')
        if quote['source_id'] in seen:
            raise ValueError('UNIQUE_QUOTE_SOURCE_REQUIRED')
        seen.add(quote['source_id'])
        usable = usable and (quote['complete'] and
            quote['acceptance_id'] == observation['acceptance_id'] and
            quote['observed_hour'] <= observation['now_hour'] <= quote['valid_until_hour'])
    raw = json.dumps(observation, sort_keys=True, separators=(',', ':'),
                     allow_nan=False).encode()
    result = {'schema': 'genesis-public-quote-decision/v1',
              'observation_sha256': hashlib.sha256(raw).hexdigest(),
              'action': 'ABSTAIN', 'price_microUSD': None,
              'planned_contribution_microUSD': None, 'spend_authorized': False,
              'reason': 'CURRENT_COMPARABLE_COMPLETE_QUOTES_REQUIRED'}
    if not usable:
        return result
    ceiling = min(q['price_microUSD'] for q in alternatives) - observation['friction_microUSD']
    tick = observation['tick_microUSD']
    price = ((ceiling - 1) // tick) * tick
    provision = max(0,price-observation['tax_deduction_before_closing_microUSD']) * observation['tax_numerator']//observation['tax_denominator']
    contribution = price - observation['non_tax_cost_microUSD'] - provision
    if price <= 0 or contribution < observation['minimum_contribution_microUSD']:
        result['reason'] = 'NO_COMPLETE_COST_PRICE_IN_DECLARED_FEASIBLE_SET'
        return result
    result.update(action='QUOTE', price_microUSD=price,
                  planned_contribution_microUSD=contribution,
                  reason='STRICT_PUBLIC_OUTSIDE_OPTION_WITH_COMPLETE_PLANNED_COST')
    return result
