"""Replay ten independent paid-reach accounts and publish only aggregate evidence."""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commercial.ledger import digest, strict_json
from mechanism_harness import cart_campaign, reach_native, reach_policy


MONEY = {
    'collections': 'collections', 'recognized_revenue': 'revenue',
    'incurred_expenses_including_tax': 'expenses', 'cash_expenses_paid': 'expensePaid',
    'profit_after_modeled_tax': 'profit', 'recovery_income': 'recoveryIncome',
    'cash': 'cash', 'available_cash': 'available', 'available_earned_cash': 'unrestrictedEarned',
    'payables': 'payables', 'tail_reserve': 'tailReserve', 'working_capital': 'workingCapital',
    'custody_restricted': 'custodyRestricted', 'custody_reserve': 'custodyReserve',
    'reserved_investment': 'reservedInvestment',
}
INPUTS = ('CONTRACT.json', 'SOURCE.json', 'MANIFEST.json', 'STUDY.json', 'PLAN.json',
          'ORDERS.json', 'CHANNEL.json', 'NATIVE_EXPORT.json', 'REPORT.json')


def require(test, code):
    if not test:
        raise ValueError(code)


def checked_file(path):
    require(path.is_file() and not path.is_symlink() and path.absolute() == path.resolve(),
            'REGULAR_PILOT_FILE_REQUIRED')
    return path


def identity(path):
    return {name: sha256(checked_file(path / name).read_bytes()).hexdigest() for name in INPUTS}


def expense_breakdown(entries):
    """Every business charge must enter exactly once, even when paid with earned funds."""
    by_kind = Counter()
    for entry in entries:
        req = entry['request']
        if req['operation'] == 'spend':
            by_kind[req['kind']] += req['amount']
        elif req['op'] == 'cost':
            args = req['args']
            if args['id'].startswith('reach-fee-'):
                key = 'payment_fees'
            elif args['id'] == 'reach-maintenance':
                key = 'maintenance'
            elif args['id'] == 'reach-modeled-tax':
                key = 'modeled_tax'
            elif args['amount'] == 0:
                continue
            else:
                raise ValueError('UNCLASSIFIED_REACH_EXPENSE')
            by_kind[key] += args['amount']
    return dict(sorted(by_kind.items()))


def economic_prefix(orders, entries, actions, day):
    """Compare actual choices/work, all business requests and before/after balances.

    A reserve intent binds the separately initialized account's signed state.
    Finish binds its obligation receipt. The independent native audit checks
    both bindings before this cross-account projection. The full work payload,
    any funding source and every other native argument remain in the comparison.
    """
    rows = [r for r in orders if r['day'] < day]
    schedule = [(d, i) for d in range(day) for i in reach_policy.warm(d)]
    require([(r['day'], r['ordinal']) for r in rows] == schedule and all(r['source'] == 'warm' for r in rows),
            'MISSING_OR_REORDERED_WARM_HISTORY')
    requests = [{'request': e['request'], 'funding': e.get('funding')}
                for e in entries if e['request']['day'] < day]
    projected = []
    for a in actions:
        if a['day'] >= day:
            continue
        args = dict(a['args'])
        if a['op'] == 'reserve':
            del args['intent_sha256']
        elif a['op'] == 'finish':
            del args['artifact_sha256']
        projected.append({**a, 'args': args})
    first_collection = next((a['seq'] for a in projected
                             if a['after']['collections'] > a['before']['collections']), None)
    return {
        'before_day': day, 'contacts': len(rows), 'native_actions': len(projected),
        'first_collected_native_sequence': first_collection,
        'settled_baskets': sum(r['status'] == 'SETTLED' for r in rows),
        'collections_microUSD': sum(r['collections_microUSD'] for r in rows),
        'orders_sha256': digest(rows), 'requests_and_funding_sha256': digest(requests),
        'economic_actions_sha256': digest(projected),
    }


def summarize_contacts(orders, channel):
    """One basket per contact; several components or visits can belong to one buyer."""
    exposures = {(int(day), e['customer_id']) for day, group in channel['exposures_by_day'].items()
                 for e in group['exposures']}
    organic = {(r['day'], r['buyer']) for r in orders if r['source'] == 'organic'}
    paid = {(r['day'], r['buyer']) for r in orders if r['source'] == 'paid'}
    require(exposures == paid | (exposures & organic) and not (organic & paid),
            'CHANNEL_EXPOSURE_CONTACT_MISMATCH')
    settled = [r for r in orders if r['status'] == 'SETTLED']
    attempted = [r for r in orders if r['status'] in ('SETTLED', 'REFUNDED')]
    qualified = [r for r in orders if r['private'] is not None and r['status'] != 'UNQUALIFIED']
    settlement_counts = Counter(r['buyer'] for r in settled)
    raw_slots = sum(i['potential_slots'] for i in channel['instances'].values())
    attempted_slots = sum(x['attempted_slots'] for x in channel['exposures_by_day'].values())
    unused_slots = sum(x['unused_slots'] for x in channel['exposures_by_day'].values())
    require(attempted_slots == len(exposures) + unused_slots and raw_slots >= attempted_slots,
            'CHANNEL_SLOT_COUNTS_CHANGED')
    used = Counter(c['service'] for r in attempted for c in r['components'])
    service_capacity = {
        s: {'used_units': used[s], 'unused_annual_units': reach_policy.ANNUAL_UNITS - used[s]}
        for s in ('kpi_variance', 'reconciliation')
    }
    require(set(used) <= set(service_capacity) and
            all(r['unused_annual_units'] >= 0 for r in service_capacity.values()),
            'INVALID_SERVICE_CAPACITY')
    statuses = Counter(r['status'] for r in orders)
    allowed_statuses = ('SETTLED', 'REFUNDED', 'DECLINED', 'UNQUALIFIED', 'CAPACITY', 'UNSUPPORTED', 'ILLIQUID', 'NONENTRY')
    require(set(statuses) <= set(allowed_statuses), 'UNCLASSIFIED_CONTACT_OUTCOME')
    fresh = [r for r in orders if r['source'] != 'warm']
    fresh_settled = [r for r in settled if r['source'] != 'warm']
    return {
        'post_warm_contacts': len(fresh), 'post_warm_settled_baskets': len(fresh_settled),
        'post_warm_collections_microUSD': sum(r['collections_microUSD'] for r in fresh_settled),
        'deduplicated_contacts': len(orders), 'unique_contacted_buyers': len({r['buyer'] for r in orders}),
        'qualified_contacts': len(qualified), 'unique_qualified_buyers': len({r['buyer'] for r in qualified}),
        'status_counts': {s: statuses[s] for s in allowed_statuses},
        'source_contact_counts': dict(sorted(Counter(r['source'] for r in orders).items())),
        'settled_baskets': len(settled), 'unique_settled_buyers': len(settlement_counts),
        'repeat_settled_buyers': sum(n > 1 for n in settlement_counts.values()),
        'settlements_after_first': sum(n - 1 for n in settlement_counts.values()),
        'settled_product_units': sum(len(r['components']) for r in settled),
        'refunded_baskets': len(attempted) - len(settled),
        'refunded_buyer_principal_microUSD': sum(sum(c['price_cents'] for c in r['components']) * reach_native.CENT
                                                 for r in attempted if r['status'] == 'REFUNDED'),
        'paid_exposures': len(exposures), 'unique_paid_exposed_buyers': len({b for _, b in exposures}),
        'same_day_organic_paid_overlaps': len(exposures & organic),
        'paid_routed_contacts_to_organic_roster': sum(r['source'] == 'paid' and not r['paid_exclusive'] for r in orders),
        'paid_exclusive_settled_baskets': sum(r['source'] == 'paid' and r['paid_exclusive'] for r in settled),
        'channel_potential_slots': raw_slots, 'channel_attempted_slots': attempted_slots,
        'channel_unfilled_attempted_slots': unused_slots, 'channel_unattempted_slots': raw_slots - attempted_slots,
        'service_capacity': service_capacity,
    }


def tranche(decision, channel, orders):
    policy = decision['policy']
    purchase = decision['purchase']
    result = {
        'day': decision['day'], 'action': policy['action'],
        'available_before_microUSD': decision['prefix']['available_microUSD'],
        'earned_before_microUSD': decision['prefix']['earned_microUSD'],
        'invoice_microUSD': 0,
    }
    # Decision evidence is public aggregate data. Keep the projection explicit
    # so adding a future policy field cannot disclose a private account record.
    for field in ('reason', 'expected_net_microUSD', 'attributed_pretax_microUSD'):
        if field in policy:
            result[field] = policy[field]
    observed = policy['observed']
    result['decision_observations'] = {key: observed[key] for key in (
        'warm_settled', 'warm_contribution_microUSD', 'first_invoice_microUSD',
        'first_exclusive_settled', 'first_exclusive_collections_microUSD', 'first_paid_variable_costs_microUSD')}
    if purchase is None:
        require(decision['funding'] is None, 'FUNDED_TRANCHE_MISSING_PURCHASE')
        return result
    plan_id = purchase['source_plan_id']
    instance = channel['instances'][plan_id]
    paid = [r for r in orders if r['source'] == 'paid' and r['source_plan_id'] == plan_id]
    exclusive = [r for r in paid if r['paid_exclusive'] and r['status'] == 'SETTLED']
    net = sum(r['collections_microUSD'] for r in exclusive) - purchase['invoice_microUSD']
    net -= sum(r['quote_microUSD'] + r['production_microUSD'] + r['fee_microUSD'] for r in paid)
    result.update(
        invoice_microUSD=purchase['invoice_microUSD'], funding=decision['funding']['funding'],
        paid_native_sequence=decision['funding']['native_event_sequence'],
        activation_due_day=purchase['activation_day'], expiry_day=purchase['expiry_day'],
        supplier_final_state=instance['state'], activation_attempts=instance['activation_attempts'],
        failure_credit_due_microUSD=instance['failure_credit_due_microUSD'],
        realized_exposures=instance['realized_exposures'], routed_contacts=len(paid),
        exclusive_settled_baskets=len(exclusive), observed_attributable_pretax_microUSD=net,
    )
    return result


def audited_case(path, arm, scenario):
    fingerprints = identity(path)
    audit = reach_native.audit(path)
    require(audit.get('accepted') is True, 'INDEPENDENT_ACCOUNT_AUDIT_REQUIRED')

    def read(name):
        raw = checked_file(path / name).read_bytes()
        require(sha256(raw).hexdigest() == fingerprints[name], 'ACCOUNT_CHANGED_DURING_AUDIT')
        return strict_json(raw)

    report, terms = read('REPORT.json'), read('CONTRACT.json')
    require(terms['arm'] == arm and terms['scenario'] == scenario and
            terms['opening_microUSD'] == 100_000_000_000 and
            terms['clock'] == {'start_day': 0, 'end_day_exclusive': 365},
            'REGISTERED_NATIVE_ACCOUNT_REQUIRED')
    source = read('SOURCE.json')
    require(digest(source) == report['source_sha256'], 'SOURCE_IDENTITY_CHANGED')
    manifest = read('MANIFEST.json')
    # Service preparation measures actual CPU; all other manifest content must match.
    preparation_cpu = manifest['resource_receipt'].pop('process_cpu_seconds')
    study = read('STUDY.json')
    study_sha = digest(cart_campaign.logical(study))
    require(study_sha == report['study_sha256'], 'STUDY_IDENTITY_CHANGED')
    decisions = read('PLAN.json')['decisions']
    require([d['day'] for d in decisions] == list(reach_policy.DECISION_DAYS), 'REVIEW_DAYS_CHANGED')
    orders, channel = read('ORDERS.json'), read('CHANNEL.json')
    export = read('NATIVE_EXPORT.json')
    tape = export['ledger']
    entries = export['connected_journal']['entries']
    summary = tape['summary']
    require(summary == report['native_summary'], 'REPORT_ACCOUNT_MISMATCH')
    money = {k: summary[v] for k, v in MONEY.items()}
    require(all(type(v) is int for v in money.values()), 'EXACT_NATIVE_MONEY_REQUIRED')
    expenses = expense_breakdown(entries)
    tranches = [tranche(d, channel, orders) for d in decisions]
    require(sum(expenses.values()) == summary['expenses'] and
            expenses.get('modeled_tax', 0) == report['tax_microUSD'] and
            expenses.get('paid_reach', 0) == sum(t['invoice_microUSD'] for t in tranches) and
            summary['collections'] == sum(r['collections_microUSD'] for r in orders) and
            summary['cash'] == terms['opening_microUSD'] + summary['collections'] +
            summary['recoveryIncome'] - summary['expensePaid'] and
            summary['profit'] == summary['revenue'] + summary['recoveryIncome'] - summary['expenses'],
            'INCOMPLETE_ACCOUNT_RECONCILIATION')
    require(identity(path) == fingerprints, 'ACCOUNT_CHANGED_DURING_SUMMARY')
    require(audit['native_export_sha256'] == digest(export) and audit['report_sha256'] == digest(report)
            and audit['contacts'] == len(orders) and audit['financial_actions'] == len(tape['actions']),
            'RECORDED_ACCOUNT_DIFFERS_FROM_INDEPENDENT_AUDIT')
    case = {
        'native_audit_accepted': True, 'audit_receipt_sha256': digest(audit),
        'audited_native_action_count': audit['financial_actions'],
        'artifact_file_sha256': fingerprints, 'financial_microUSD': money,
        'incurred_expense_breakdown_microUSD': expenses, 'tranches': tranches,
        'reach_and_work': summarize_contacts(orders, channel),
        'measured_compute': {
            'service_preparation_process_cpu_seconds': preparation_cpu,
            'construction_cpu_ns_by_study_arm': study['study']['construction_cpu_ns'],
            'independent_verification_cpu_ns': study['study']['independent_verification_cpu_ns'],
            'retention_cpu_ns': study['study']['retention_cpu_ns'],
        },
    }
    shared = {
        'source_sha256': digest(source), 'protocol_sha256': source[reach_native.PROTOCOL],
        'matched_job_manifest_sha256_excluding_cpu_seconds': digest(manifest),
        'matched_menu_study_sha256': study_sha,
        'warm_prefix': economic_prefix(orders, entries, tape['actions'], reach_policy.DECISION_DAYS[0]),
    }
    return case, shared


def compare(organic, pilot):
    """Signed differences for one pair only; account balances stay separate."""
    money = {k: value - organic['financial_microUSD'][k] for k, value in pilot['financial_microUSD'].items()}
    left, right = organic['reach_and_work'], pilot['reach_and_work']
    volume = {k: right[k] - left[k] for k in (
        'deduplicated_contacts', 'unique_contacted_buyers', 'unique_qualified_buyers',
        'settled_baskets', 'unique_settled_buyers', 'settled_product_units', 'repeat_settled_buyers')}
    profits = {'organic': organic['financial_microUSD']['profit_after_modeled_tax'],
               'pilot': pilot['financial_microUSD']['profit_after_modeled_tax'], 'arithmetic_nonentry': 0}
    cost_keys = organic['incurred_expense_breakdown_microUSD'].keys() | pilot['incurred_expense_breakdown_microUSD'].keys()
    costs = {k: pilot['incurred_expense_breakdown_microUSD'].get(k, 0) -
             organic['incurred_expense_breakdown_microUSD'].get(k, 0) for k in sorted(cost_keys)}
    return {
        'pilot_minus_organic_expense_breakdown_microUSD': costs,
        'pilot_minus_organic_financial_microUSD': money, 'pilot_minus_organic_counts': volume,
        'profit_and_settled_volume_both_increased': money['profit_after_modeled_tax'] > 0 and volume['settled_baskets'] > 0,
        'highest_annual_modeled_profit_including_nonentry': [a for a, p in profits.items() if p == max(profits.values())],
    }


def summarize(root):
    require(root.is_dir() and root.absolute() == root.resolve(), 'REGULAR_ACCOUNT_ROOT_REQUIRED')
    pairs = {}
    registered = None
    for world in reach_policy.SCENARIOS:
        cases = {}
        for arm in ('organic', 'pilot'):
            case, shared = audited_case(root / world / arm, arm, world)
            if registered is None:
                registered = shared
            require(shared == registered, 'UNMATCHED_WARM_HISTORY_JOBS_MENU_OR_SOURCE')
            cases[arm] = case
        pairs[world] = {**cases, 'comparison': compare(cases['organic'], cases['pilot'])}
    require(len(pairs) == 5, 'FIVE_REGISTERED_PAIRS_REQUIRED')
    return {
        'schema': 'omega/earned-paid-reach-paired-evidence/v1', 'window_days': [0, 365],
        'end_day_exclusive': True, 'opening_microUSD_each': 100_000_000_000, 'actual_revenue_usd': 0,
        'actual_complete_lifecycle_cost_usd': None, 'comparison_program_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'shared_design_and_prefix': registered, 'pairs': pairs,
        'scope': 'Ten independent synthetic account-years. Each difference compares pilot minus organic within one environment. '
                 'Arithmetic nonentry starts no enterprise and incurs no modeled revenue or costs. No scenario weighting or annualization.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='Private account tree WORLD/ARM')
    parser.add_argument('--output', type=Path, required=True, help='New comparison JSON outside the account tree')
    args = parser.parse_args()
    destination = args.output.absolute()
    require(destination.parent.resolve() == destination.parent and destination.parent.is_dir() and
            not destination.is_relative_to(args.input.resolve()), 'OUTPUT_MUST_BE_OUTSIDE_ACCOUNTS')
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('NEW_PUBLIC_EVIDENCE_FILE_REQUIRED')
    result = summarize(args.input)
    # Publish only complete results. link() refuses an overwrite even if a second
    # process completes its audit at the same time.
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=destination.parent) as tmp:
        json.dump(result, tmp, indent=2, sort_keys=True, allow_nan=False)
        tmp.write('\n')
        tmp.flush()
        os.fsync(tmp.fileno())
        os.link(tmp.name, destination)
    print(destination)


if __name__ == '__main__':
    main()
