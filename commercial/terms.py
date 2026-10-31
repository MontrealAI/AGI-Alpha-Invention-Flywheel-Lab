"""Explicit prospective simulation terms; no legal or provider guarantee."""
from __future__ import annotations

import copy

SCHEMA = 'agi-alpha/native-prospective-terms/v1'
FIELDS = {'schema', 'clock_unit', 'version', 'order_id', 'price_microUSD', 'payment_schedule',
          'expected_collection_day', 'exposure_microUSD', 'maturity_day',
          'residual_microUSD', 'acceptance_rule', 'dispute_rule', 'late_claim_rule',
          'premium_microUSD', 'fee_microUSD', 'coverage_limit_microUSD',
          'deductible_microUSD', 'coverage_exclusions', 'payout_delay_hours',
          'default_rule', 'counterparty_obligations', 'jurisdiction', 'legal_status',
          'accounting_policy'}
RULES = {'schema': SCHEMA, 'clock_unit': 'INTEGER_HOURS', 'payment_schedule': 'ON_NATIVE_ACCEPTED_RELEASE',
         'acceptance_rule': 'INDEPENDENT_NATIVE_PREPARE_AND_RELEASE',
         'dispute_rule': 'CLAIMS_THROUGH_MATURITY_INCLUSIVE',
         'late_claim_rule': 'RETAIN_ALL_CLAIMS_EXCESS_OVER_RESIDUAL_STOPS_INVESTMENT',
         'default_rule': 'RETAIN_UNPAID_LIABILITY_AND_STOP_INVESTMENT',
         'legal_status': 'HYPOTHETICAL_SIMULATION_NO_ENFORCEABILITY_OR_PROVIDER_GUARANTEE',
         'accounting_policy': 'INCURRED_COST_COLLECTED_RECOVERY_MATURITY_NOT_INCOME_V1'}


def validate_terms(terms, *, registered_at=None):
    if not isinstance(terms, dict) or set(terms) != FIELDS or any(terms.get(k) != v for k, v in RULES.items()):
        raise ValueError('EXACT_NATIVE_PROSPECTIVE_TERMS_REQUIRED')
    for key in ['version', 'price_microUSD', 'expected_collection_day', 'exposure_microUSD',
                'maturity_day', 'residual_microUSD', 'premium_microUSD', 'fee_microUSD',
                'coverage_limit_microUSD', 'deductible_microUSD', 'payout_delay_hours']:
        if type(terms[key]) is not int or not 0 <= terms[key] <= 10**15:
            raise ValueError('BOUNDED_NATIVE_TERM_INTEGER_REQUIRED:' + key)
    if terms['version'] < 1 or not 200_000 <= terms['price_microUSD'] <= 10**12:
        raise ValueError('NATIVE_TERM_VERSION_OR_PRICE_INVALID')
    if terms['exposure_microUSD'] < terms['price_microUSD'] + 200_000:
        raise ValueError('PROSPECTIVE_PRINCIPAL_AND_FEE_EXPOSURE_REQUIRED')
    if terms['residual_microUSD'] > terms['exposure_microUSD'] or terms['expected_collection_day'] >= terms['maturity_day']:
        raise ValueError('PROSPECTIVE_EXPOSURE_INTERVAL_OR_RESIDUAL_INVALID')
    if terms['coverage_limit_microUSD'] and not terms['premium_microUSD']:
        raise ValueError('COSTED_PROSPECTIVE_COVERAGE_REQUIRED')
    if registered_at is not None and (type(registered_at) is not int or registered_at < 0 or registered_at > terms['expected_collection_day']):
        raise ValueError('TERMS_MUST_PRECEDE_EXPECTED_COLLECTION')
    for key in ['order_id', 'counterparty_obligations', 'jurisdiction']:
        if not isinstance(terms[key], str) or not terms[key].strip() or len(terms[key]) > (160 if key == 'order_id' else 1000):
            raise ValueError('BOUNDED_EXPLICIT_NATIVE_TERM_REQUIRED:' + key)
    excluded = terms['coverage_exclusions']
    if (not isinstance(excluded, list) or any(not isinstance(x, str) or x not in {'ordinary', 'disputed', 'covered', 'provider_default'} for x in excluded)
            or len(excluded) != len(set(excluded))):
        raise ValueError('EXPLICIT_NATIVE_COVERAGE_EXCLUSIONS_REQUIRED')
    return copy.deepcopy(terms)


def prospective_terms(order_id, price, maturity_day, expected_collection_day, *, version=1,
                      exposure=None, residual=0, premium=0, fee=0, coverage_limit=0,
                      deductible=0, exclusions=None, payout_delay_hours=0,
                      jurisdiction='Authored synthetic jurisdiction; no legal finality established',
                      counterparty_obligations='Buyer pays modeled price; producer supplies independently accepted artifact; claims remain producer obligations'):
    terms = dict(RULES, version=version, order_id=order_id, price_microUSD=price,
                 expected_collection_day=expected_collection_day, exposure_microUSD=price + 200_000 if exposure is None else exposure,
                 maturity_day=maturity_day, residual_microUSD=residual, premium_microUSD=premium,
                 fee_microUSD=fee, coverage_limit_microUSD=coverage_limit, deductible_microUSD=deductible,
                 coverage_exclusions=[] if exclusions is None else list(exclusions), payout_delay_hours=payout_delay_hours,
                 jurisdiction=jurisdiction, counterparty_obligations=counterparty_obligations)
    return validate_terms(terms)
