"""Exact read-only conditional frontier; no financial state or selling authority."""
from __future__ import annotations
import argparse
from collections import defaultdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path

PROTOCOL_PATH = Path(__file__).with_name('ECONOMIC_PROTOCOL.json')
TARGET = 3_000_000_000_000_000
FACTS = ('qualified_artifact_acceptance', 'reachable_accepted_contracts_365_bound',
         'execution_capacity_contracts_365_bound', 'current_available_cash_microUSD',
         'dated_reachable_contracts_by_day', 'dated_execution_capacity_contracts_by_day')
COSTS = ('resource_expense_microUSD', 'acquisition_expense_microUSD',
         'support_expense_microUSD', 'correction_expense_microUSD')


def _int(value, minimum=0):
    if type(value) is not int or value < minimum: raise ValueError('EXACT_NONNEGATIVE_INTEGER_REQUIRED')
    return value


def _fraction(value):
    if not isinstance(value, dict) or set(value) != {'numerator', 'denominator'}:
        raise ValueError('EXACT_FRACTION_REQUIRED')
    fraction = Fraction(_int(value['numerator']), _int(value['denominator'], 1))
    if fraction > 1: raise ValueError('UNIT_INTERVAL_FRACTION_REQUIRED')
    return fraction


def _ratio(value):
    value = Fraction(value)
    return {'numerator': value.numerator, 'denominator': value.denominator}


def _ceil(value):
    value = Fraction(value)
    return -(-value.numerator // value.denominator)


def load_protocol(path=PROTOCOL_PATH):
    protocol = json.loads(Path(path).read_text())
    if protocol['schema'] != 'operational075/economic-protocol/v1' or protocol['target_microUSD'] != TARGET or protocol['window_days'] != 365:
        raise ValueError('FROZEN_365_DAY_3B_PROTOCOL_REQUIRED')
    tax = _fraction(protocol['tax_fraction'])
    if tax == 1: raise ValueError('TAX_RATE_MUST_LEAVE_POSITIVE_NET_FRACTION')
    for value in protocol['fixed_costs_microUSD'].values(): _int(value)
    if len(protocol['scenarios']) != 3: raise ValueError('EXACT_THREE_REGISTERED_REGIONS_REQUIRED')
    for row in protocol['scenarios']:
        for key in COSTS + ('fee_microUSD', 'outside_quote_microUSD', 'buyer_budget_microUSD', 'payment_fixed_per_accepted_microUSD', 'production_days', 'collection_lag_days', 'claim_tail_days', 'producer_collateral_per_accepted_microUSD'):
            _int(row[key])
        collection = _fraction(row['collected_fraction']); _fraction(row['payment_fraction'])
        if collection.denominator > 10_000: raise ValueError('REGISTERED_FRACTION_SEARCH_ALLOWANCE_EXCEEDED')
        if row['production_days'] + row['collection_lag_days'] >= 365:
            raise ValueError('NO_FULLY_COLLECTED_ADMISSION_WINDOW')
    return protocol


def _terms(row):
    collected = _fraction(row['collected_fraction'])
    payment = _ceil(row['fee_microUSD'] * _fraction(row['payment_fraction']))
    noncollection_cost = sum(row[key] for key in COSTS) + row['payment_fixed_per_accepted_microUSD']
    return collected, payment, noncollection_cost


def profit_at_count(row, count, fixed, tax):
    count = _int(count); collected, payment, cost = _terms(row)
    paid = count * collected.numerator // collected.denominator
    revenue = paid * row['fee_microUSD']
    expenses = fixed + count * cost + paid * payment
    pretax = revenue - expenses
    tax_paid = max(pretax, 0) * tax.numerator // tax.denominator
    return {'accepted_contracts': count, 'collected_contracts': paid,
            'collected_fee_microUSD': revenue, 'complete_pretax_expense_microUSD': expenses,
            'pretax_profit_microUSD': pretax, 'tax_microUSD': tax_paid,
            'aftertax_profit_microUSD': pretax - tax_paid}


def minimum_count(row, fixed, tax, target=TARGET):
    collected, payment, cost = _terms(row)
    numerator, denominator = collected.numerator, collected.denominator
    receipt = row['fee_microUSD'] - payment
    block_gain = numerator * receipt - denominator * cost
    if block_gain <= 0: return None
    pretax_required = ((target - 1) * tax.denominator // (tax.denominator - tax.numerator)) + 1
    candidates = []
    for remainder in range(denominator):
        residual = (remainder * numerator // denominator) * receipt - remainder * cost - fixed
        blocks = max(0, _ceil(Fraction(pretax_required - residual, block_gain)))
        candidates.append(blocks * denominator + remainder)
    count = min(candidates)
    if profit_at_count(row, count, fixed, tax)['aftertax_profit_microUSD'] < target:
        raise ValueError('EXACT_TARGET_COUNT_RECONCILIATION_FAILED')
    return count


def cash_envelope(row, count, fixed, tax):
    collected, payment, cost = _terms(row)
    production, lag, tail = (row[key] for key in ('production_days', 'collection_lag_days', 'claim_tail_days'))
    admission_days = 365 - production - lag
    admissions = [(day + 1) * count // admission_days - day * count // admission_days if day < admission_days else 0 for day in range(365)]
    events = defaultdict(lambda: [0, 0, 0, 0, 0])
    events[0][0] += fixed
    for day in range(admission_days):
        before, after = day * count // admission_days, (day + 1) * count // admission_days
        quantity = after - before
        paid = after * collected.numerator // collected.denominator - before * collected.numerator // collected.denominator
        events[day][0] += quantity * cost
        events[day][2] += quantity * row['producer_collateral_per_accepted_microUSD']
        settlement = day + production + lag
        events[settlement][1] += paid * (row['fee_microUSD'] - payment)
        events[settlement + tail][3] += quantity * row['producer_collateral_per_accepted_microUSD']
    finances = profit_at_count(row, count, fixed, tax)
    events[364][4] += finances['tax_microUSD']
    paid_out = received = protected = peak = peak_day = 0
    for day, (expense, income, add, release, tax_paid) in sorted(events.items()):
        paid_out += expense; protected += add
        requirement = paid_out - received + protected
        if requirement > peak: peak, peak_day = requirement, day
        received += income; protected -= release
        paid_out += tax_paid
        requirement = paid_out - received + protected
        if requirement > peak: peak, peak_day = requirement, day
        if protected < 0: raise ValueError('COLLATERAL_RELEASE_EXCEEDS_PROTECTION')
    if received - paid_out != finances['aftertax_profit_microUSD'] or protected != 0:
        raise ValueError('DATED_CASH_PROFIT_RECONCILIATION_FAILED')
    return {'required_initial_cash_microUSD': peak, 'peak_day': peak_day,
            'required_admissions_by_day': admissions,
            'admission_schedule_sha256': hashlib.sha256(json.dumps(admissions, separators=(',', ':')).encode()).hexdigest(),
            'admission_days': admission_days, 'active_day_contract_rate': _ratio(Fraction(count, admission_days)),
            'average_365_day_contract_rate': _ratio(Fraction(count, 365)),
            'fixed_expenses_microUSD': fixed,
            'collateral_per_accepted_microUSD': row['producer_collateral_per_accepted_microUSD'],
            'collection_lag_days': lag, 'production_days': production, 'claim_tail_days': tail,
            'cash_minus_opening_after_all_tail_releases_microUSD': received - paid_out,
            'scope': 'Exact authored finite dated cash envelope; no native account or financing is created. Collateral release produces no income.'}


def _gate(facts, count, cash, buyer_choice, required_daily=None):
    missing, violations = [], []
    thresholds = {'qualified_artifact_acceptance': True,
                  'reachable_accepted_contracts_365_bound': count,
                  'execution_capacity_contracts_365_bound': count,
                  'current_available_cash_microUSD': cash,
                  'dated_reachable_contracts_by_day': 'Each day at least the dated_cash_envelope.required_admissions_by_day count',
                  'dated_execution_capacity_contracts_by_day': 'Each day at least the dated_cash_envelope.required_admissions_by_day count'}
    for key in FACTS:
        evidence = facts.get(key)
        if not isinstance(evidence, dict) or evidence.get('value') is None or evidence.get('independently_verified') is not True or not isinstance(evidence.get('evidence_ref'), str) or not evidence['evidence_ref'].strip():
            missing.append(key); continue
        value, required = evidence['value'], thresholds[key]
        if key != 'qualified_artifact_acceptance' and key != 'current_available_cash_microUSD' and evidence.get('bound_kind') != 'supported_available_quantity':
            missing.append(key + ':supported_available_quantity'); continue
        if key.startswith('dated_'):
            if not isinstance(value, list) or len(value) != 365: raise ValueError('EXACT_365_DAY_SUPPORTED_SCHEDULE_REQUIRED')
            for amount in value: _int(amount)
            if required_daily is not None and any(available < needed for available, needed in zip(value, required_daily)):
                violations.append(key)
        elif key == 'qualified_artifact_acceptance':
            if type(value) is not bool: raise ValueError('BOOLEAN_QUALIFIED_ACCEPTANCE_REQUIRED')
            if value is not True: violations.append('qualified_artifact_acceptance')
        else:
            _int(value)
            if required is not None and value < required: violations.append(key)
    if not buyer_choice: violations.append('buyer_prefers_outside_option_or_declines')
    if count is None: violations.append('no_finite_profitable_contract_volume_in_this_region')
    status = 'UNESTABLISHED' if missing else 'CONDITIONAL_REQUIREMENTS_NOT_SATISFIED' if violations else 'CONDITIONAL_REQUIREMENTS_SATISFIED'
    return {'status': status, 'required_facts': missing, 'known_constraint_violations': violations,
            'conditional_thresholds': thresholds,
            'annual_aggregate_constraints': 'Necessary only; dated demand and capacity support are separately required for this cash schedule.',
            'evidence_boundary': 'Independent-verification flags and public evidence references are supplied by the caller; this arithmetic module does not authenticate them or grant spending authority.'}


def evaluate(facts=None, protocol=None):
    facts = {} if facts is None else facts
    if not isinstance(facts, dict): raise ValueError('PUBLIC_FACTS_OBJECT_REQUIRED')
    protocol = load_protocol() if protocol is None else protocol
    fixed = sum(protocol['fixed_costs_microUSD'].values()); tax = _fraction(protocol['tax_fraction'])
    regions = []
    for row in protocol['scenarios']:
        collected, payment, cost = _terms(row)
        pretax_unit = collected * (row['fee_microUSD'] - payment) - cost
        buyer = row['fee_microUSD'] <= row['buyer_budget_microUSD'] and row['fee_microUSD'] < row['outside_quote_microUSD']
        count = minimum_count(row, fixed, tax) if buyer else None
        cash = cash_envelope(row, count, fixed, tax) if count is not None else None
        regions.append({'id': row['id'], 'assumptions': row, 'buyer_chooses_our_authored_offer': buyer,
            'conditional_region': 'POSITIVE_UNIT_MARGIN_REQUIRES_SCALE_AND_FUNDING' if buyer and count is not None else 'REFUSE_BUYER_CHOICE' if not buyer else 'NO_FINITE_PROFITABLE_VOLUME',
            'collected_fee_per_accepted_microUSD': _ratio(collected * row['fee_microUSD']),
            'resource_acquisition_support_correction_per_accepted_microUSD': {key: row[key] for key in COSTS},
            'proportional_payment_expense_per_collected_microUSD': payment,
            'pretax_unit_net_microUSD': _ratio(pretax_unit),
            'aftertax_unit_net_before_fixed_microUSD': _ratio(pretax_unit * (1 - tax) if pretax_unit > 0 else pretax_unit),
            'fixed_research_and_setup_microUSD': fixed,
            'minimum_accepted_contracts_365': count,
            'target_count_reconciliation': profit_at_count(row, count, fixed, tax) if count is not None else None,
            'dated_cash_envelope': cash,
            'planning_gate': _gate(facts, count, cash['required_initial_cash_microUSD'] if cash else None, buyer,
                                   cash['required_admissions_by_day'] if cash else None)})
    encoded = json.dumps(protocol, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return {'schema': 'operational075/economic-frontier-result/v1',
            'scope': protocol['evidence_role'], 'economic_protocol_sha256': hashlib.sha256(encoded).hexdigest(),
            'target_microUSD': TARGET, 'window_days': 365, 'source_facts': facts, 'regions': regions,
            'human_conventional_comparator': protocol['human_conventional_comparator'],
            'actual_model_and_host_billing': 'UNKNOWN', 'native_account_operated': False,
            'native_trailing_365_profit_microUSD': None, 'native_target_achieved': False,
            'actual_commercial_revenue_microUSD': 0,
            'native_target_gate': protocol['native_observer'],
            'next_decision': 'Use verified delivery and independently evidenced reach, capacity and present funding to adjudicate the stated thresholds. No current facts are replaced by simulated sales or pooled accounts.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--facts', type=Path); parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    facts = json.loads(args.facts.read_text()) if args.facts else None
    result = evaluate(facts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists(): raise ValueError('NEW_ECONOMIC_RESULT_PATH_REQUIRED')
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'output': str(args.output), 'native_target_achieved': False,
                      'regions': [{'id': row['id'], 'status': row['planning_gate']['status']} for row in result['regions']]}, sort_keys=True))


if __name__ == '__main__': main()
