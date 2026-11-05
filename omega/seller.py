"""Voluntary offer sensitivity and a fresh, cost-only native seller research arm.

No paid product is admitted: the native service fixture is NOT a download,
webinar, founder session, or water certification. Preferences never mint revenue.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from adaptive_enterprise.instruments import SOURCE_PATHS as SERVICE_SOURCE_PATHS, prepare_services
from commercial.ledger import canonical, digest, strict_json
from experiments.commerce006 import PINS as NATIVE_SOURCE_PINS
from connected_enterprise.finance import JournalAccount, SOURCE_PATHS, audit_journal
from connected_enterprise.scale import trailing_profit

MICRO = 1_000_000
END_HOUR = 365 * 24
OPENING = 100_000 * MICRO
OFFERS = {
    'no_purchase': {'price_usd': 0, 'outside_option': True},
    'ordinary_provider': {'price_usd': 500, 'outside_option': True,
                          'price_basis': 'authored sensitivity only, not a quote'},
    'self_service_incumbent': {'price_usd': 0, 'outside_option': True},
    'open_core': {'price_usd': 0, 'license': 'unresolved; open-source intent only'},
    'self_hosted': {'price_usd': 299},
    'group_webinar': {'price_usd': 99, 'seats_per_session': 500},
    'founder_private': {'price_usd': 20_000, 'founder_minutes': 30},
}
# Deliberately authored hypothetical utilities, NOT observations of customer demand.
BASELINE_VALUES = {'no_purchase': 0, 'ordinary_provider': 450,
                   'self_service_incumbent': 400, 'open_core': 300,
                   'self_hosted': 500, 'group_webinar': 150, 'founder_private': 1000}
OPTIMISTIC_VALUES = {**BASELINE_VALUES, 'self_hosted': 800}


def voluntary_choice(values, *, friction=None, unavailable=()):
    """Choose maximal modeled net utility; no-purchase wins ties at zero.

    Each option has explicit willingness-to-pay and optional time/setup friction
    in USD equivalents. Missing options/negative or noninteger inputs fail closed.
    """
    friction = {name: 0 for name in OFFERS} if friction is None else friction
    if set(values) != set(OFFERS) or set(friction) != set(OFFERS):
        raise ValueError('ALL_OUTSIDE_OPTIONS_AND_OFFER_VALUES_REQUIRED')
    if any(type(x) is not int or x < 0 for x in [*values.values(), *friction.values()]):
        raise ValueError('NONNEGATIVE_INTEGER_PREFERENCE_INPUTS_REQUIRED')
    if values['no_purchase'] != 0 or friction['no_purchase'] != 0:
        raise ValueError('FREE_VOLUNTARY_NO_PURCHASE_REQUIRED')
    if any(x not in OFFERS or x == 'no_purchase' for x in unavailable):
        raise ValueError('VALID_AVAILABILITY_WITH_NO_PURCHASE_REQUIRED')
    utilities = {name: values[name] - offer['price_usd'] - friction[name]
                 for name, offer in OFFERS.items() if name not in unavailable}
    winner = max(utilities, key=utilities.get)
    return {'choice': winner, 'utility_usd_equivalent': utilities[winner],
            'utilities': utilities, 'consent': False,
            'scope': 'HYPOTHETICAL_PREFERENCE_NOT_ORDER_OR_REVENUE'}


def webinar_sessions(seats):
    if type(seats) is not int or seats < 0:
        raise ValueError('NONNEGATIVE_INTEGER_SEATS_REQUIRED')
    return (seats + 499) // 500


def cost_schedule():
    """Declared experimental budget, not estimates validated by actual invoices."""
    rows = [
        ('research_and_construction', 0, 8_000),
        ('failed_research_attempts', 0, 3_000),
        ('engineering_labor_paid', 0, 6_000),
        ('independent_verification', 24, 2_000),
        ('acquisition_experiment', 48, 1_000),
    ]
    for month in range(12):
        hour = month * 30 * 24 + 72
        rows.extend([(f'maintenance_{month}', hour, 200),
                     (f'support_readiness_{month}', hour, 100),
                     (f'compute_tools_{month}', hour, 100)])
    return [{'id': name, 'hour': hour, 'microUSD': dollars * MICRO,
             'basis': 'AUTHORED_SENSITIVITY_NOT_ACTUAL_BILL'}
            for name, hour, dollars in sorted(rows, key=lambda r: (r[1], r[0]))]


def declared_registration():
    """Exact current authored policy, reconstructed independently on replay."""
    return {
        'schema': 'omega/seller-research-registration/v1',
        'scope': 'FRESH_INDEPENDENT_SIMULATION_NOT_LIVE_COMMERCE',
        'capital_role': 'USD100k reference comparison, not chosen global optimum',
        'opening_microUSD': OPENING, 'financing': 'authored opening equity; no loans or topups',
        'currency': 'USD authored modeling convention pending commercial confirmation',
        'operating_start_hour': 0, 'operating_end_hour_exclusive': END_HOUR,
        'offers': OFFERS, 'native_sales_enabled': False,
        'acceptance_gap': 'No native qualified download, webinar, or private-session delivery adapter.',
        'license_gate': 'Open-source intent; license and redistribution rights unresolved.',
        'cash_cost_schedule': cost_schedule(),
        'noncash_founder_opportunity_cost': {'hours': 20, 'usd_per_hour': 2000,
            'microUSD': 40_000 * MICRO, 'basis': 'authored sensitivity, not cash expenditure'},
        'refunds_microUSD': 0, 'refund_basis': 'No offers sold or collected in this arm',
        'actual_taxes_microUSD': None, 'actual_host_model_billing_microUSD': None,
        'actual_complete_cost_profit_microUSD': None,
        'claim_limits': ['No customers, guaranteed demand, autonomous discovery, or achieved profit.',
                         'Service fixtures validate accounting only; not product acceptance.',
                         'No global capital optimum or investor commitments established.'],
        'seller_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def run(output, *, root=None):
    """Create exactly one independently funded USD100k reference research account.

    An existing destination is refused, never reset, reseeded, or resumed. The
    registered full-year experiment has zero admitted seller orders. All cash
    expenses are posted to JournalAccount; no alternative cash ledger is used.
    """
    root = Path(root or Path(__file__).resolve().parents[1]).resolve()
    output = Path(output).absolute()
    output.mkdir(parents=True, exist_ok=False)
    source = output / 'source'
    for name in sorted(set(SOURCE_PATHS) | set(SERVICE_SOURCE_PATHS) | set(NATIVE_SOURCE_PINS)):
        destination = source / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, destination)
    schedule = cost_schedule()
    registration = declared_registration()
    (output / 'registration.json').write_bytes(canonical(registration) + b'\n')
    manifest = prepare_services(source, 'accounting-fixture', jobs_per_service=32)
    (output / 'manifest.json').write_bytes(canonical(manifest) + b'\n')
    with JournalAccount(source, manifest, output / 'account.sqlite', opening=OPENING,
                        working=0, contract='omega-research:' + digest(registration)) as account:
        by_day = {}
        for row in schedule:
            by_day.setdefault(row['hour'] // 24, []).append(row)
        observed_days = 0
        for day in range(365):
            for row in by_day.get(day, []):
                account.cost(row['id'], row['microUSD'], row['hour'])
            observed_days += 1
        # Zero-cost endpoint observation records clock coverage without minting cash.
        account.cost('registered-year-end-observation', 0, END_HOUR - 1)
        record = account.export()
        if observed_days != END_HOUR // 24:
            raise ValueError('REGISTERED_OPERATING_DAYS_INCOMPLETE')
        result = derive_report(registration, record, source=source, manifest=manifest)
        (output / 'native-public-export.json').write_bytes(canonical(record) + b'\n')
        (output / 'result.json').write_bytes(canonical(result) + b'\n')
    return result


def derive_report(registration, record, *, source, manifest):
    """Validate policy and native evidence, then derive EVERY reported claim."""
    if registration['seller_source_sha256'] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise ValueError('SELLER_POLICY_SOURCE_CHANGED')
    if canonical(registration) != canonical(declared_registration()):
        raise ValueError('SELLER_REGISTRATION_CHANGED')
    if record['ledger']['config']['contract'] != 'omega-research:' + digest(registration):
        raise ValueError('NATIVE_REGISTRATION_BINDING_CHANGED')
    expected = [(r['id'], r['microUSD'], r['hour']) for r in registration['cash_cost_schedule']]
    expected.append(('registered-year-end-observation', 0, END_HOUR - 1))
    actions = record['ledger']['actions']
    actual = [(a['args']['id'], a['args']['amount'], a['day']) for a in actions if a['op'] == 'cost']
    if actual != expected or len(actual) != len(actions):
        raise ValueError('REGISTERED_COST_ONLY_OPERATIONS_CHANGED')
    if record['ledger']['config']['opening'] != OPENING or record['ledger']['config']['working'] != 0:
        raise ValueError('REGISTERED_OPENING_CAPITAL_CHANGED')
    audit = audit_journal(record, root=source, manifest=manifest)
    annual = trailing_profit(record['ledger'], operating_end_hour=END_HOUR, operating_complete=True)
    summary = record['ledger']['summary']
    if summary['cash'] != OPENING - summary['expensePaid'] or summary['collections'] != 0:
        raise ValueError('COST_ONLY_NATIVE_CONSERVATION_FAILED')
    if summary['expenses'] != sum(row['microUSD'] for row in registration['cash_cost_schedule']):
        raise ValueError('ITEMIZED_NATIVE_EXPENSE_RECONCILIATION_FAILED')
    return {
        'schema': 'omega/seller-research-result/v1', 'scope': registration['scope'],
        'registration_sha256': digest(registration), 'native_audit': audit,
        'native_summary_microUSD': summary, 'native_trailing_profit': annual,
        'completed_operating_days': END_HOUR // 24,
        'native_product_sales': 0, 'native_product_revenue_microUSD': 0,
        'actual_complete_cost_profit_microUSD': None,
        'complete_cost_status': 'UNKNOWN: actual costs, taxes, and product acceptance unresolved',
        'modeled_profit_after_founder_opportunity_before_unknown_taxes_microUSD':
            summary['profit'] - registration['noncash_founder_opportunity_cost']['microUSD'],
        'tax_sensitivity': {'basis': 'illustrative only, no tax advice or accrued tax',
                           'rates_bps': [0, 2000, 4000],
                           'taxable_profit_assumed_microUSD': max(0, summary['profit']),
                           'tax_amounts_microUSD': [max(0, summary['profit']) * r // 10000
                                                   for r in [0, 2000, 4000]]},
        'preference_scenarios': {
            'free_incumbent_baseline': voluntary_choice(BASELINE_VALUES),
            'optimistic_hypothetical_opt_in': voluntary_choice(OPTIMISTIC_VALUES),
            'all_decline': voluntary_choice({name: 0 for name in OFFERS})},
        'limits': registration['claim_limits'],
    }


def replay_audit(output):
    """Independently replay the public native export and registered cost policy."""
    output = Path(output)
    registration = strict_json((output / 'registration.json').read_bytes())
    manifest = strict_json((output / 'manifest.json').read_bytes())
    record = strict_json((output / 'native-public-export.json').read_bytes())
    result = strict_json((output / 'result.json').read_bytes())
    expected_report = derive_report(registration, record, source=output / 'source', manifest=manifest)
    if canonical(result) != canonical(expected_report):
        raise ValueError('SELLER_REPORTED_RESULT_CHANGED')
    audit = expected_report['native_audit']
    return {'accepted': audit['accepted'], 'registration_sha256': digest(registration),
            'native_actions_sha256': record['ledger']['actions_sha256']}


def run_seller(root, output):
    """Integration API: public report and native export, never private authority."""
    report = run(output, root=root)
    return {'report': report,
            'native_export': json.loads((Path(output) / 'native-public-export.json').read_text()),
            'replay_audit': replay_audit(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='new private simulation state directory')
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps({'result': str(Path(args.output) / 'result.json'),
                      'native_audit_accepted': result['native_audit']['accepted'],
                      'native_modeled_profit_microUSD': result['native_summary_microUSD']['profit'],
                      'actual_complete_cost_profit_microUSD': None}, indent=2))


if __name__ == '__main__':
    main()
