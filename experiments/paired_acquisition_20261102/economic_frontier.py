"""Conditional acquisition choices; no account, ledger, sales or spending API.

Quality verdicts and resource quantities come from a separately frozen scientific
contract. USD values are externally supplied hypotheses or measurements. Unknown
costs remain unknown, including when a resource frontier can still be computed.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import itertools
import json
from pathlib import Path
import re


SCHEMA = 'paired-acquisition/economic-input/v1'
RESOURCES = ('light_frames', 'light_readings', 'dark_frames', 'dark_readings',
             'blank_frames', 'specimen_exposures', 'source_photons',
             'specimen_photons', 'elapsed_seconds', 'swap_operations')
METHODS = ('single_read', 'independent_calibration', 'paired_swap',
           'ordinary_paired_swap')
COUNT_RESOURCES = set(RESOURCES) - {'source_photons', 'specimen_photons', 'elapsed_seconds'}
QUALITY = {'accepted', 'refused', 'unresolved'}
RIGHTS = {'admitted', 'refused', 'unresolved'}


def number(value, name):
    """Read an exact nonnegative planning quantity, preserving missing inputs."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError('NONNEGATIVE_FINITE_NUMBER_REQUIRED:' + name)
    try:
        result = Fraction(str(value))
    except (ValueError, ZeroDivisionError):
        raise ValueError('NONNEGATIVE_FINITE_NUMBER_REQUIRED:' + name) from None
    if result < 0:
        raise ValueError('NONNEGATIVE_FINITE_NUMBER_REQUIRED:' + name)
    return result


def hashed(value, name):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('EXACT_SHA256_REQUIRED:' + name)
    return value


def vector(value, name):
    if not isinstance(value, dict) or set(value) != set(RESOURCES):
        raise ValueError('EXACT_RESOURCE_VECTOR_REQUIRED:' + name)
    return {key: number(value[key], name + '.' + key) for key in RESOURCES}


def encoded(value):
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, dict):
        return {key: encoded(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [encoded(item) for item in value]
    return value


def budget_status(resources, budgets):
    unknown = False
    for key in RESOURCES:
        cap = budgets[key]
        if cap == 'unbounded':
            continue
        cap = number(cap, 'budgets.' + key)
        if cap is None or resources[key] is None:
            unknown = True
        elif resources[key] > cap:
            return 'refused'
    return 'unresolved' if unknown else 'within_declared_budget'


def cost(resources, rates, other):
    known = other if other is not None else Fraction(0)
    missing = [] if other is not None else ['other_episode_cost_usd']
    for key in RESOURCES:
        amount, rate = resources[key], rates[key]
        if amount == 0:
            continue
        if amount is None or rate is None:
            missing.append(key)
        else:
            known += amount * rate
    return {'known_subtotal_usd': known, 'missing': missing,
            'total_usd': None if missing else known}


def delta(left, right):
    return None if left is None or right is None else left - right


def compare(document):
    if document.get('schema') != SCHEMA:
        raise ValueError('REGISTERED_ECONOMIC_INPUT_SCHEMA_REQUIRED')
    if not isinstance(document.get('case_id'), str) or not document['case_id'].strip():
        raise ValueError('NAMED_REGISTERED_CASE_REQUIRED')
    for key in ('scientific_contract_sha256', 'permission_contract_sha256'):
        hashed(document.get(key), key)
    budgets = document.get('budgets')
    if not isinstance(budgets, dict) or set(budgets) != set(RESOURCES):
        raise ValueError('EXACT_RESOURCE_BUDGET_REQUIRED')
    for key, value in budgets.items():
        if value != 'unbounded':
            number(value, 'budgets.' + key)
    cash_rates = vector(document['cash_usd_per_unit'], 'cash_usd_per_unit')
    opportunity_rates = vector(document['opportunity_usd_per_unit'], 'opportunity_usd_per_unit')
    choices = document.get('choices')
    if not isinstance(choices, list) or len(choices) != len(METHODS):
        raise ValueError('FOUR_EXPLICIT_METHODS_REQUIRED')
    if {c.get('method') for c in choices} != set(METHODS):
        raise ValueError('EXACT_METHOD_SET_REQUIRED')
    costs_specified = any(v is not None for v in (*cash_rates.values(), *opportunity_rates.values()))
    normalized = {}
    for choice in choices:
        method = choice['method']
        if choice.get('quality') not in QUALITY or choice.get('rights_and_capacity') not in RIGHTS:
            raise ValueError('EXPLICIT_QUALITY_RIGHTS_STATUS_REQUIRED:' + method)
        if choice['quality'] != 'unresolved':
            hashed(choice.get('quality_receipt_sha256'), method + '.quality_receipt_sha256')
        if type(choice.get('complete_episode_cost_scope')) is not bool:
            raise ValueError('EXPLICIT_COST_SCOPE_REQUIRED:' + method)
        resources = vector(choice['resources'], method + '.resources')
        if any(resources[key] is not None and resources[key].denominator != 1 for key in COUNT_RESOURCES):
            raise ValueError('INTEGER_OPERATION_COUNTS_REQUIRED:' + method)
        other_cash = number(choice.get('other_cash_cost_usd'), method + '.other_cash_cost_usd')
        other_opportunity = number(choice.get('other_opportunity_cost_usd'), method + '.other_opportunity_cost_usd')
        costs_specified |= other_cash is not None or other_opportunity is not None
        normalized[method] = {**choice, 'resources': resources,
                              'other_cash_cost_usd': other_cash,
                              'other_opportunity_cost_usd': other_opportunity}
    if costs_specified and not document.get('price_basis'):
        raise ValueError('PRICE_PROVENANCE_OR_AUTHORED_SENSITIVITY_LABEL_REQUIRED')
    # An ordinary constructor has exactly the same acquisition permissions and
    # stipulated acquisition costs. This is a comparator design, not a measured
    # equality of upstream human and AI engineering effort.
    for key in ('resources', 'other_cash_cost_usd', 'other_opportunity_cost_usd',
                'complete_episode_cost_scope', 'rights_and_capacity'):
        if normalized['paired_swap'][key] != normalized['ordinary_paired_swap'][key]:
            raise ValueError('MATCHED_ORDINARY_PAIR_COSTS_AND_PERMISSIONS_REQUIRED:' + key)
    cash = number(document.get('available_cash_usd'), 'available_cash_usd')
    reserve = number(document.get('protected_cash_usd'), 'protected_cash_usd')
    prior = number(document.get('prior_campaign_cost_usd'), 'prior_campaign_cost_usd')
    terms = document.get('offer_hypothesis') or {}
    terms = {key: number(terms.get(key), 'offer_hypothesis.' + key) for key in (
        'buyer_gross_value_usd', 'buyer_adoption_cost_usd',
        'buyer_outside_surplus_usd', 'provider_hurdle_usd')}
    reports = {}
    for method in METHODS:
        choice = normalized[method]
        money = cost(choice['resources'], cash_rates, choice['other_cash_cost_usd'])
        opportunity = cost(choice['resources'], opportunity_rates, choice['other_opportunity_cost_usd'])
        scope = choice['complete_episode_cost_scope']
        cash_cost = money['total_usd'] if scope else None
        full_cost = (cash_cost + opportunity['total_usd']
                     if cash_cost is not None and opportunity['total_usd'] is not None else None)
        budget = budget_status(choice['resources'], budgets)
        reasons = []
        if choice['quality'] != 'accepted':
            reasons.append('QUALITY_' + choice['quality'].upper())
        if budget != 'within_declared_budget':
            reasons.append('RESOURCE_BUDGET_' + budget.upper())
        if choice['rights_and_capacity'] != 'admitted':
            reasons.append('RIGHTS_CAPACITY_' + choice['rights_and_capacity'].upper())
        finance = ('unresolved' if cash_cost is None or cash is None or reserve is None
                   else 'conditional_cash_requirement_met' if cash >= cash_cost + reserve
                   else 'refused_insufficient_cash')
        if finance != 'conditional_cash_requirement_met':
            reasons.append('FINANCE_' + finance.upper())
        floor = full_cost + terms['provider_hurdle_usd'] if full_cost is not None and terms['provider_hurdle_usd'] is not None else None
        buyer_values = [terms[k] for k in ('buyer_gross_value_usd', 'buyer_adoption_cost_usd', 'buyer_outside_surplus_usd')]
        ceiling = buyer_values[0] - buyer_values[1] - buyer_values[2] if all(v is not None for v in buyer_values) else None
        if floor is None or ceiling is None:
            reasons.append('COMPLETE_COST_OR_PARTICIPATION_TERMS_UNKNOWN')
        elif ceiling < floor:
            reasons.append('NO_VOLUNTARY_PRICE_INTERVAL')
        refused = any('REFUSED' in reason or reason == 'NO_VOLUNTARY_PRICE_INTERVAL' for reason in reasons)
        reports[method] = {
            'quality': choice['quality'], 'quality_receipt_sha256': choice.get('quality_receipt_sha256'),
            'resources': choice['resources'], 'budget': budget,
            'cash_cost': money, 'opportunity_cost': opportunity,
            'complete_episode_cost_scope': scope, 'complete_episode_cost_usd': full_cost,
            'conditional_cash_feasibility': finance,
            'required_cash_including_protection_usd': cash_cost + reserve if cash_cost is not None and reserve is not None else None,
            'conditional_offer_price_interval_usd': None if floor is None or ceiling is None or ceiling < floor else [floor, ceiling],
            'offer_state': 'REFUSE' if refused else 'HOLD' if reasons else 'CONDITIONAL_PROPOSAL_ONLY',
            'reasons': reasons,
        }
    eligible = [m for m in METHODS if reports[m]['quality'] == 'accepted'
                and reports[m]['budget'] == 'within_declared_budget'
                and all(v is not None for v in normalized[m]['resources'].values())]
    frontier = []
    for method in eligible:
        use = normalized[method]['resources']
        dominated = any(all(normalized[other]['resources'][k] <= use[k] for k in RESOURCES)
                        and any(normalized[other]['resources'][k] < use[k] for k in RESOURCES)
                        for other in eligible if other != method)
        if not dominated:
            frontier.append(method)
    inequalities = []
    for left, right in itertools.combinations(METHODS, 2):
        a, b = normalized[left], normalized[right]
        matched_pair = {left, right} == {'paired_swap', 'ordinary_paired_swap'}
        inequalities.append({
            'left': left, 'right': right,
            'condition': 'delta_other_cash + delta_other_opportunity + sum(delta_resource * (cash_rate + opportunity_rate)) <= 0',
            'resource_deltas': {key: delta(a['resources'][key], b['resources'][key]) for key in RESOURCES},
            'other_cash_delta_usd': delta(a['other_cash_cost_usd'], b['other_cash_cost_usd']),
            'other_opportunity_delta_usd': delta(a['other_opportunity_cost_usd'], b['other_opportunity_cost_usd']),
            'complete_cost_delta_usd': delta(reports[left]['complete_episode_cost_usd'], reports[right]['complete_episode_cost_usd']),
            'quality_and_budget_comparison_admitted': left in eligible and right in eligible,
            'stipulated_protocol_cost_tie': matched_pair,
            'matched_tie_scope': 'Same stipulated acquisition resources and episode cost assumptions, including shared unknowns; upstream AI/human labor advantage unmeasured.' if matched_pair else None,
        })
    serialized = json.dumps(document, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return encoded({
        'schema': 'paired-acquisition/economic-frontier/v1',
        'scope': 'CONDITIONAL_FINITE_ACQUISITION_DECISION_NOT_COMMERCIAL_PROFIT',
        'case_id': document['case_id'],
        'input_sha256': hashlib.sha256(serialized).hexdigest(),
        'economic_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scientific_contract_sha256': document['scientific_contract_sha256'],
        'permission_contract_sha256': document['permission_contract_sha256'],
        'price_basis': document.get('price_basis'), 'choices': reports,
        'conditional_resource_pareto_frontier': frontier,
        'break_even_inequalities': inequalities,
        'non_entry': {'available': True, 'delivers_required_measurement': False,
                      'incremental_acquisition_cash_cost_usd': Fraction(0),
                      'prior_campaign_cost_usd': prior, 'forgone_outcome_value_usd': None},
        'ordinary_control': 'Identical stipulated protocol resources/costs; no measured AI versus human labor advantage.',
        'offer_model': 'Conditional accepted-delivery arithmetic; failure/default risk and actual counterparty participation are not established.',
        'cash_schedule': 'All remaining acquisition-episode cash costs before any receipt; no borrowing or conditional receivable funds.',
        'native_account_executed': False, 'actual_offer_sent': False,
        'authority_granted': False, 'commercial_profit_qualified': False,
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    args = parser.parse_args()
    document = json.loads(args.input.read_text(), parse_constant=lambda value: (_ for _ in ()).throw(ValueError('NONFINITE_JSON:' + value)))
    print(json.dumps(compare(document), indent=2, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
