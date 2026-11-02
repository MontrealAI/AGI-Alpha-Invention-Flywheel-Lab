from __future__ import annotations
import argparse
import copy
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import time

from commercial.ledger import canonical, digest, strict_json
from commercial.terms_exact_v2 import prospective_terms
from connected_enterprise.finance import JournalAccount, audit_journal
from connected_enterprise.scale import aggregate_native, trailing_profit
from portfolio071.arrangement import factorial, rival_best_response

MICRO = 1_000_000
HORIZON_DAYS = 365 * 5
EPOCH = '2026-11-02T00:00:00Z'
CAPITALS_USD = (25_000, 100_000, 1_000_000, 10_000_000, 1_000_000_000)
PRICE_MENU_USD = (3000, 4500, 6000, 9000, 13500, 18000)
COSTS_USD = {'research_and_failed_attempts': 15000, 'K1_construction': 16000,
             'independent_validation': 6000, 'data_rights_and_legal_review': 3000,
             'K2_construction_and_requalification': 14000,
             'annual_inference_compute_storage_maintenance': 2400,
             'annual_administration_insurance_security': 3600,
             'coalition_contact': 360, 'member_integration': 400,
             'independent_domain_review': 1800, 'license_support_prepaid': 1200,
             'renewal_review': 300, 'retirement_archive_and_support': 2000}


@dataclass(frozen=True)
class World:
    name: str = 'central'
    value_bps: int = 10000
    budget_bps: int = 10000
    usable_yield_bps: int = 10000
    maintenance_multiplier: int = 1
    collection_delay_days: int = 30
    default_every: int = 0
    qualification_passes: bool = True
    rival_change_months: int | None = 12
    rival_after_cost_usd: int = 3000
    rival_fixed_cost_usd: int = 10000
    supplier_available: bool = True
    rights_available: bool = True
    external_financing_requested: bool = False
    tax_bps: int = 2500
    equal_capability_rival: bool = False
    research_cost_multiplier: int = 1


def registered_worlds():
    base = World()
    return [base, replace(base, name='no_demand', value_bps=0),
            replace(base, name='low_willingness', budget_bps=500),
            replace(base, name='imitation_month1', rival_change_months=1),
            replace(base, name='imitation_month6', rival_change_months=6),
            replace(base, name='imitation_month18', rival_change_months=18),
            replace(base, name='imitation_month36', rival_change_months=36),
            replace(base, name='stable_gap', rival_change_months=None),
            replace(base, name='failed_qualification', qualification_passes=False),
            replace(base, name='lower_yield', usable_yield_bps=3500),
            replace(base, name='costly_maintenance', maintenance_multiplier=10),
            replace(base, name='collection_delay', collection_delay_days=180),
            replace(base, name='payment_default', default_every=2),
            replace(base, name='refused_financing', external_financing_requested=True),
            replace(base, name='supplier_refusal', supplier_available=False),
            replace(base, name='rights_refusal', rights_available=False),
            replace(base, name='equal_complete_codesign_rival', equal_capability_rival=True),
            replace(base, name='research_cost_times10', research_cost_multiplier=10)]


def population(world):
    groups = []
    for group in range(12):
        members = []
        for member in range(3 + int(group % 4 == 0)):
            value = (32000 + 1500 * member + 500 * (group % 3)) * world.value_bps // 10000
            members.append({'id': f'synthetic-site-{group:02d}-{member:02d}',
                            'value_usd': value, 'budget_usd': 20000 * world.budget_bps // 10000,
                            'adoption_usd': 1000, 'outside_surplus_usd': 0})
        groups.append({'id': f'synthetic-coalition-{group:02d}', 'members': members})
    return groups


def project_game(world=World(), capital_usd=100000):
    buyers = population(world)[0]['members']
    return factorial(buyers, capital_usd=capital_usd, setup_usd=18000,
                     adapter_usd=400, coordination_usd=200,
                     supplier_cost_usd=1600, supplier_hurdle_usd=200,
                     supplier_quote_usd=1800, support_usd=1200 * world.maintenance_multiplier,
                     rights_review_usd=3000, price_menu_usd=PRICE_MENU_USD,
                     qualification=(1, 1) if world.qualification_passes else (0, 1),
                     supplier_available=world.supplier_available, rights_available=world.rights_available,
                     tax_bps=world.tax_bps)


def conditional_market_frontier():
    rows = []
    for price_each in PRICE_MENU_USD:
        gross = 3 * price_each
        base_cost = (3 * COSTS_USD['member_integration'] + COSTS_USD['independent_domain_review']
                     + COSTS_USD['license_support_prepaid'] + COSTS_USD['coalition_contact'])
        for cost_multiplier in (1, 2, 5):
            for collection_bps in (10000, 8000, 5000):
                collected = Fraction(gross * collection_bps, 10000)
                payment_fee = collected * Fraction(200, 10000)
                variable = base_cost * cost_multiplier + payment_fee
                contribution = collected - variable
                net = contribution * Fraction(7500, 10000) if contribution > 0 else contribution
                fixed = 6000 + 15000 + 16000 + 6000 + 3000 + 14000 + 2000
                thresholds = {}
                for target in (1_000_000_000, 3_000_000_000):
                    needed = None
                    if contribution > 0:
                        contracts = (Fraction(target, 1) / Fraction(7500, 10000) + fixed) / contribution
                        needed = (contracts.numerator + contracts.denominator - 1) // contracts.denominator
                    thresholds[str(target)] = needed
                explicit_checks = []
                for n in (0, 1, 3, 12):
                    explicit = sum((collected - variable for _ in range(n)), Fraction(0)) - fixed
                    aggregate = n * contribution - fixed
                    explicit_checks.append({'contracts': n, 'difference_numerator': (explicit - aggregate).numerator})
                rows.append({'price_each_usd': price_each, 'members_per_contract': 3,
                    'collection_bps': collection_bps, 'variable_cost_multiplier': cost_multiplier,
                    'gross_contract_price_usd': gross,
                    'conditional_net_variable_contribution_usd': {'numerator': net.numerator, 'denominator': net.denominator},
                    'annual_fixed_and_full_setup_expensed_usd': fixed,
                    'required_annual_contracts_for_target': thresholds,
                    'small_explicit_arithmetic_checks': explicit_checks})
    return {'scope': 'CONDITIONAL_STATIONARY_BREAK_EVEN_ARITHMETIC_NOT_FINANCED_GROWTH_OR_NATIVE_REVENUE',
            'rows': rows, 'population_cap': None, 'market_reach_or_share_assumed': None,
            'actual_market_demand_evidence': None,
            'cost_coverage': 'Research for all five routes, failed work, design construction, independent review, rights, K2, retirement, ongoing compute/admin, acquisition/integration/support, payment fees and 25% scenario tax. Cost multipliers challenge variable scaling; installed physical capital excluded because the sold unit is computational design access.',
            'limits': ['Twelve coalitions are the finite execution test, not a market ceiling.',
                       'Required counts do not establish market existence, qualified demand, funded ramp, capacity, renewals, or financing.',
                       'This arithmetic contains no industrial savings inferred from a resistance-only baseline. Complete conventional co-design is an equal-capability outside option.',
                       'Small explicit checks establish arithmetic aggregation only; the 24 native histories are separately audited.',
                       'Costs and values are scenario hypotheses; model billing and real willing buyers are unmeasured.']}


def commercial_choice(group, world, day, renewal):
    changed = world.rival_change_months is not None and day >= 30 * world.rival_change_months
    rival_cost = (COSTS_USD['member_integration'] if world.equal_capability_rival
                  else (world.rival_after_cost_usd if changed else 9000))
    rival_fixed = (COSTS_USD['independent_domain_review']
                   + COSTS_USD['license_support_prepaid'] * world.maintenance_multiplier
                   + (COSTS_USD['renewal_review'] if renewal else COSTS_USD['coalition_contact'])
                   if world.equal_capability_rival else world.rival_fixed_cost_usd)
    candidates = []
    for price in PRICE_MENU_USD:
        rival = rival_best_response(group['members'], price,
            rival_price_menu_usd=(3000, 4500, 6000, 9000, 13500, 18000, 24000),
            rival_variable_usd=rival_cost, rival_fixed_usd=rival_fixed,
            rival_payment_bps=200 if world.equal_capability_rival else 0,
            own_value_bps=world.usable_yield_bps)
        members = rival['selected']['company_members']
        quote = (COSTS_USD['member_integration'] * len(members)
                 + COSTS_USD['independent_domain_review']
                 + COSTS_USD['license_support_prepaid'] * world.maintenance_multiplier
                 + (COSTS_USD['renewal_review'] if renewal else COSTS_USD['coalition_contact']))
        revenue = price * len(members)
        payment_fee = (revenue * 200 + 9999) // 10000
        complete_cost = quote + payment_fee
        profit = revenue - complete_cost
        candidate = {'price_each_usd': price, 'members': members,
                     'price_usd': revenue, 'cost_usd': complete_cost,
                     'contribution_before_tax_usd': profit, 'rival': rival,
                     'decision': 'LICENSE' if len(members) >= 2 and profit > 0 else 'REFUSE'}
        if not world.supplier_available or not world.rights_available or not world.qualification_passes:
            candidate['decision'] = 'REFUSE'
        candidates.append(candidate)
    feasible = [c for c in candidates if c['decision'] == 'LICENSE']
    selected = max(feasible, key=lambda c: (c['contribution_before_tax_usd'], -c['price_usd'])) if feasible else None
    return {'selected': selected, 'evaluated': candidates,
            'unconstrained_company_choice_regret_usd': max([c['contribution_before_tax_usd'] for c in feasible] + [0]) - (selected['contribution_before_tax_usd'] if selected else 0),
            'scope': 'Exact myopic choice in finite public-information offer menu; not an optimal five-year policy.'}


def _write_new(path, value):
    path = Path(path)
    raw = canonical(value) + b'\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)
    return hashlib.sha256(raw).hexdigest()


def _calendar(hour):
    start = datetime.fromisoformat(EPOCH.replace('Z', '+00:00'))
    return (start + timedelta(hours=hour)).isoformat().replace('+00:00', 'Z')


def _spend(account, ident, amount_usd, hour, *, expected=0, earned_only=False, work=None, tax_commitment=0):
    if account.snapshot()['summary']['available'] < amount_usd * MICRO + tax_commitment:
        return None
    return account.spend(ident, 'portfolio071_registered_complete_cost', amount_usd * MICRO,
                         hour, work or {'cost_id': ident, 'units': 'USD', 'scope': 'AUTHORED_DEPLOYMENT_ESTIMATE'},
                         expected * MICRO, allow_seed=not earned_only)


def _pending_tax(pending, world):
    return sum((p['price_usd'] * MICRO * world.tax_bps + 9999) // 10000 for p in pending)


def execute_trajectory(root, manifest, output, *, capital_usd, world=World(),
                       policy='working_capital_aware', earned_only_k2=False,
                       horizon_days=HORIZON_DAYS, infer_idle_days=True):
    if policy not in {'working_capital_aware', 'stylized_prepaid_reach_capacity'}:
        raise ValueError('REGISTERED_POLICY_REQUIRED')
    if type(capital_usd) is not int or capital_usd < 0 or type(horizon_days) is not int or horizon_days < 1:
        raise ValueError('REGISTERED_CAPITAL_AND_HORIZON_REQUIRED')
    if type(infer_idle_days) is not bool:
        raise ValueError('EXPLICIT_IDLE_DAY_OBSERVATION_POLICY_REQUIRED')
    from portfolio071.service import load_contracts
    root, output = Path(root).absolute(), Path(output).absolute()
    jobs = load_contracts(root, manifest)
    by_purpose = {}
    for row in manifest['jobs']:
        request = strict_json((root / row['input']).read_bytes())
        by_purpose[request['task']] = row['id']
    if set(by_purpose) != {'heat_delivery', 'thermal_continuity'}:
        raise ValueError('TWO_DISTINCT_ACCEPTED_SCIENTIFIC_FUNCTIONS_REQUIRED')
    output.mkdir(parents=True, exist_ok=False)
    manifest_sha = _write_new(output / 'manifest.json', manifest)
    started_wall, started_cpu = time.monotonic(), time.process_time()
    identity = f'{world.name}-{capital_usd}-{policy}-{int(earned_only_k2)}'
    record = {'schema': 'portfolio071/native-economic-trajectory/v1', 'id': identity,
              'scope': 'CONDITIONAL_NATIVE_DESIGN_LICENSE_SIMULATION_NOT_PHYSICAL_DEPLOYMENT',
              'world': asdict(world), 'capital_usd': capital_usd, 'policy': policy,
              'infer_idle_days': infer_idle_days,
              'earned_only_k2': earned_only_k2, 'manifest_sha256': manifest_sha,
              'initial_finance': 'ASSUMED_RECEIVED_OPENING_EQUITY_FRESH_COUNTERFACTUAL_NOT_SECURED_FUNDS',
              'decisions': [], 'daily': [], 'cost_receipts': [], 'tax_settlements': [],
              'financing': [], 'K2_funding': None,
              'population': population(world), 'stop_reason': None,
              'actual_scientific_artifacts': len(jobs), 'modeled_licenses': 0,
              'external_revenue_usd': 0, 'installed_physical_sites': 0,
              'post_horizon_collected_licenses': 0,
              'actual_model_billing': None,
              'modeled_human_internal_hours': 18,
              'actual_human_runtime_intervention_minutes_observed': 0,
              'unmeasured_human_minutes': 'User mandate creation/oversight and historical engineering time are not instrumented; zero total-human-time claim is unsupported.'}
    pending = []
    collected_years = set()
    prepaid = {}
    prepayment_done = False
    tax_paid = 0
    operating_stop_day = None
    k1_ready = True
    k2_ready = False
    horizon_hour = horizon_days * 24
    with JournalAccount(root, manifest, output / 'account.sqlite', opening=capital_usd * MICRO,
                        working=0, contract='portfolio071-' + digest(identity)[:24]) as account:
        for cost_name in ('research_and_failed_attempts', 'K1_construction', 'independent_validation', 'data_rights_and_legal_review', 'retirement_archive_and_support'):
            amount_usd = COSTS_USD[cost_name] * (world.research_cost_multiplier if cost_name == 'research_and_failed_attempts' else 1)
            receipt = _spend(account, cost_name, amount_usd, 0)
            if receipt is None:
                record['decisions'].append({'day': 0, 'decision': 'REFUSE_UNFUNDED_RESEARCH', 'cost': cost_name})
                k1_ready = False
                operating_stop_day = 0
                record['stop_reason'] = 'INITIAL_RESEARCH_PREFUNDING_UNAVAILABLE'
                break
            record['cost_receipts'].append(receipt)
        if world.external_financing_requested:
            before = account.snapshot()
            try:
                account.execute('finance', {'id': 'uncommitted-draw', 'amount': 1_000_000 * MICRO}, 0)
            except ValueError as error:
                record['financing'].append({'decision': 'REFUSED', 'reason': str(error),
                    'requested_usd': 1_000_000, 'cash_received_usd': 0,
                    'cash_unchanged': account.snapshot() == before})
            else:
                raise AssertionError('UNSUPPORTED_FINANCING_WAS_ACCEPTED')
        event_days = {0, 180}
        event_days.update(range(0, horizon_days, 365))
        for index in range(len(record['population'])):
            event_days.update(range(15 + index * 28, horizon_days, 365))
        for day in range(horizon_days):
            if infer_idle_days and day not in event_days:
                # The sole writer has no scheduled action, collection or maturity
                # today. This is an explicitly inferred observation of the last
                # authoritative native state, not a new cash or profit update.
                unchanged = {**record['daily'][-1], 'day': day,
                             'observation': 'INFERRED_UNCHANGED_NO_NATIVE_EVENT'}
                record['daily'].append(unchanged)
                continue
            hour = day * 24
            account.advance_financial(hour)
            due, pending = [p for p in pending if p['due_day'] <= day], [p for p in pending if p['due_day'] > day]
            for obligation in sorted(due, key=lambda p: (p['due_day'], p['id'])):
                action = 'refund' if obligation['default'] else 'release'
                account.execute('event', {'id': obligation['id'], 'action': action,
                    'event_id': obligation['id'] + '-' + action}, hour)
                if not obligation['default']:
                    record['modeled_licenses'] += 1
                    collected_years.add((obligation['coalition'], obligation['year']))
                    state = account.snapshot()['summary']
                    pretax = state['profit'] + tax_paid
                    due_tax = max(0, pretax * world.tax_bps // 10000 - tax_paid)
                    if due_tax > obligation['price_usd'] * MICRO or due_tax > state['available']:
                        raise AssertionError('PRERELEASE_TAX_COMMITMENT_INSUFFICIENT')
                    if due_tax:
                        account.cost('tax-' + obligation['id'], due_tax, hour)
                        tax_paid += due_tax
                    record['tax_settlements'].append({'order_id': obligation['id'], 'hour': hour,
                        'post_horizon': False, 'gross_collection_microUSD': obligation['price_usd'] * MICRO,
                        'available_before_tax_microUSD': state['available'], 'tax_paid_microUSD': due_tax,
                        'payables_after_tax_microUSD': account.snapshot()['summary']['payables']})
                record['decisions'].append({'day': day, 'decision': 'ESCROW_CANCELLATION_REFUND' if obligation['default'] else 'COLLECTED_MODELED_LICENSE',
                                            'order_id': obligation['id'], 'price_usd': obligation['price_usd']})
            if operating_stop_day is None and day % 365 == 0:
                overhead = COSTS_USD['annual_inference_compute_storage_maintenance'] + COSTS_USD['annual_administration_insurance_security']
                receipt = _spend(account, f'overhead-year-{day // 365}', overhead, hour,
                                 tax_commitment=_pending_tax(pending, world))
                if receipt is None:
                    operating_stop_day = day
                    record['stop_reason'] = 'OVERHEAD_UNFUNDED'
                else:
                    record['cost_receipts'].append(receipt)
            if operating_stop_day is None and day == 180 and k1_ready and world.qualification_passes:
                receipt = _spend(account, 'K2-development', COSTS_USD['K2_construction_and_requalification'], hour,
                                 expected=10000, earned_only=earned_only_k2,
                                 tax_commitment=_pending_tax(pending, world),
                                 work={'accepted_scientific_job': by_purpose['thermal_continuity'],
                                       'purpose': 'Distinct thermal continuity design; accepted arithmetic, no physical qualification'})
                record['K2_funding'] = receipt
                k2_ready = receipt is not None
                if receipt is not None:
                    record['cost_receipts'].append(receipt)
                record['decisions'].append({'day': day, 'decision': 'K2_FUNDED' if k2_ready else 'K2_FUNDING_REFUSED',
                                            'funding': receipt['funding'] if receipt else None})
            if operating_stop_day is None and k1_ready:
                for index, group in enumerate(record['population']):
                    first = 15 + index * 28
                    if day < first or (day - first) % 365 != 0:
                        continue
                    year = (day - first) // 365
                    renewal = (group['id'], year - 1) in collected_years
                    ident = f'license-{index:02d}-{year}'
                    choice = commercial_choice(group, world, day, renewal)
                    selected = choice['selected']
                    if selected is None:
                        contact = COSTS_USD['renewal_review'] if renewal else COSTS_USD['coalition_contact']
                        prepaid_contact = bool(year == 0 and group['id'] in prepaid)
                        if prepaid_contact:
                            contact = 0
                        receipt = _spend(account, 'unsuccessful-contact-' + ident, contact, hour,
                                         tax_commitment=_pending_tax(pending, world))
                        if receipt is not None:
                            record['cost_receipts'].append(receipt)
                        record['decisions'].append({'day': day, 'coalition': group['id'], 'decision': 'BUYER_OR_SUPPLIER_REFUSAL',
                            'contact_paid': receipt is not None, 'prepaid_contact_applied': prepaid_contact,
                            'renewal_after_collected_prior_year': renewal, 'choice': choice})
                        continue
                    state = account.snapshot()['summary']
                    if policy == 'stylized_prepaid_reach_capacity' and not prepayment_done:
                        prepayment_done = True
                        for forecast_group in record['population']:
                            forecast = commercial_choice(forecast_group, world, day, False)['selected']
                            if forecast is None:
                                continue
                            prepay_cost = forecast['cost_usd']
                            receipt = _spend(account, 'prepaid-first-year-' + forecast_group['id'], prepay_cost, hour,
                                tax_commitment=_pending_tax(pending, world),
                                work={'coalition': forecast_group['id'], 'forecast_at_day': day,
                                      'cost_breakdown': 'Same contact, integration, review, prepaid support and payment-fee quote as per-job control; unused capacity nonrefundable.'})
                            if receipt is not None:
                                prepaid[forecast_group['id']] = prepay_cost
                                record['cost_receipts'].append(receipt)
                        state = account.snapshot()['summary']
                    prepayment = prepaid.get(group['id'], 0) if year == 0 else 0
                    existing_tax = _pending_tax(pending, world)
                    feasible_cash = [c for c in choice['evaluated'] if c['decision'] == 'LICENSE'
                        and (max(0, c['cost_usd'] - prepayment) + c['price_usd'] + 1) * MICRO
                            + (c['price_usd'] * MICRO * world.tax_bps + 9999) // 10000 + existing_tax <= state['available']]
                    choice['unconstrained_selected'] = selected
                    if feasible_cash:
                        selected = max(feasible_cash, key=lambda c: (c['contribution_before_tax_usd'], -c['price_usd']))
                        choice['selected'] = selected
                    choice['cash_feasible_candidate_count'] = len(feasible_cash)
                    choice['cash_constrained_choice_regret_usd'] = (
                        max([c['contribution_before_tax_usd'] for c in feasible_cash] + [0])
                        - (selected['contribution_before_tax_usd'] if feasible_cash else 0))
                    new_tax = (selected['price_usd'] * MICRO * world.tax_bps + 9999) // 10000
                    needed = (max(0, selected['cost_usd'] - prepayment) + selected['price_usd'] + 1) * MICRO + new_tax + existing_tax
                    if state['available'] < needed or state['investmentStopped']:
                        record['decisions'].append({'day': day, 'coalition': group['id'], 'decision': 'PROFITABLE_BUT_UNFUNDED',
                            'available_microUSD': state['available'], 'required_microUSD': needed,
                            'renewal_after_collected_prior_year': renewal,
                            'contribution_before_tax_usd': selected['contribution_before_tax_usd'], 'choice': choice})
                        continue
                    unpaid_cost = max(0, selected['cost_usd'] - prepayment)
                    receipt = _spend(account, 'delivery-and-prepaid-support-' + ident, unpaid_cost, hour,
                                     expected=selected['contribution_before_tax_usd'],
                                     tax_commitment=existing_tax + new_tax,
                                     work={'coalition': group['id'], 'selected_members': selected['members'],
                                           'scope': 'Complete modeled design license integration and prepaid support'})
                    if receipt is None and unpaid_cost:
                        raise AssertionError('AFFORDABLE_PRECOMMITTED_COST_REFUSED')
                    if receipt is not None:
                        record['cost_receipts'].append(receipt)
                    record['modeled_human_internal_hours'] += 12
                    buyer_id = group['id'] + '-year-' + str((day - first) // 365)
                    price = selected['price_usd'] * MICRO
                    due_day = day + world.collection_delay_days
                    terms = prospective_terms(ident, price, (due_day + 90) * 24, due_day * 24,
                        residual=1000 * MICRO, counterparty_obligations='Synthetic consortium members voluntarily choose a shared already-verified computational design license. No physical performance or external agreement is claimed.')
                    account.execute('wallet', {'buyer': buyer_id, 'amount': price}, hour)
                    account.execute('register_terms', {'id': ident + '-terms', 'terms': terms}, hour)
                    account.execute('offer', {'id': ident, 'buyer': buyer_id, 'price': price,
                        'job_id': by_purpose['thermal_continuity'] if k2_ready else by_purpose['heat_delivery'],
                        'deadline': (due_day + 10) * 24, 'terms_id': ident + '-terms'}, hour)
                    for action in ('consent', 'fund', 'prepare'):
                        account.execute('event', {'id': ident, 'action': action, 'event_id': ident + '-' + action}, hour)
                    pending.append({'id': ident, 'due_day': due_day, 'price_usd': selected['price_usd'],
                                    'coalition': group['id'], 'year': year,
                                    'default': bool(world.default_every and (index + day // 365 + 1) % world.default_every == 0)})
                    event_days.update((due_day, due_day + 91))
                    record['decisions'].append({'day': day, 'coalition': group['id'], 'decision': 'ACCEPTED_CONDITIONAL_LICENSE',
                        'order_id': ident, 'choice': choice, 'payment_due_day': due_day,
                        'renewal_after_collected_prior_year': renewal,
                        'prepaid_capacity_applied_usd': min(prepayment, selected['cost_usd']),
                        'new_delivery_cost_usd': unpaid_cost})
            state = account.snapshot()['summary']
            if state['payables'] > 0 or state['investmentStopped']:
                if operating_stop_day is None:
                    operating_stop_day = day
                    record['stop_reason'] = 'NATIVE_OBLIGATIONS_OR_STOP_PRECLUDE_EXPANSION'
            record['daily'].append({'day': day, 'observation': 'AUTHORITATIVE_NATIVE_EVENT_SNAPSHOT',
                'cash_microUSD': state['cash'], 'profit_microUSD': state['profit'],
                'collections_microUSD': state['collections'], 'restricted_microUSD': state['tailReserve'] + state['custodyReserve'] + state['workingCapital'],
                'payables_microUSD': state['payables'], 'available_microUSD': state['available'],
                'pending_tax_commitment_microUSD': _pending_tax(pending, world),
                'tax_commitments_covered': state['available'] >= _pending_tax(pending, world)})
        close_hour = horizon_hour - 1
        account.cost('operating-clock-close-prepaid-retirement', 0, close_hour)
        record['operating_endpoint'] = account.snapshot()['summary']
        native_at_horizon = account.export()
        native_audit_at_horizon = account.audit()
        aggregation = aggregate_native(native_at_horizon['ledger'])
        rolling = trailing_profit(native_at_horizon['ledger'], operating_end_hour=horizon_hour,
                                  operating_complete=True, aggregation=aggregation)
        record['rolling_profit'] = {**rolling, 'start_date_inclusive': _calendar(max(0, horizon_hour - 365 * 24)),
                                  'end_date_exclusive': _calendar(horizon_hour)}
        record['operating_complete'] = True
        record['observation_counts'] = {
            'authoritative_native_event_snapshots': sum(r['observation'] == 'AUTHORITATIVE_NATIVE_EVENT_SNAPSHOT' for r in record['daily']),
            'inferred_unchanged_daily_states': sum(r['observation'] == 'INFERRED_UNCHANGED_NO_NATIVE_EVENT' for r in record['daily'])}
        record['operating_stop_day'] = operating_stop_day
        record['stop_reason'] = record['stop_reason'] or 'REGISTERED_HORIZON_COMPLETE'
        record['native_account_audit'] = native_audit_at_horizon
        record['tax_paid_microUSD'] = tax_paid
        record['opening_plus_flows_reconciles'] = (
            capital_usd * MICRO + record['operating_endpoint']['collections']
            + record['operating_endpoint']['recoveryIncome'] - record['operating_endpoint']['expensePaid']
            == record['operating_endpoint']['cash'])
        record['milestone_1b'] = bool(rolling['trailing_365_day_profit_microUSD'] is not None and rolling['trailing_365_day_profit_microUSD'] >= 1_000_000_000 * MICRO)
        record['milestone_3b'] = bool(rolling['trailing_365_day_profit_microUSD'] is not None and rolling['trailing_365_day_profit_microUSD'] >= 3_000_000_000 * MICRO)
        record['external_financing_received_usd'] = 0
        record['native_export_sha256'] = _write_new(output / 'native-at-horizon.json', native_at_horizon)
        drain_days = sorted({p['due_day'] for p in pending} | {p['due_day'] + 91 for p in pending})
        for row in native_at_horizon['ledger'].get('prospective_terms', []):
            terms = strict_json(row['terms'])
            if terms['maturity_day'] >= horizon_hour:
                drain_days.append(terms['maturity_day'] // 24 + 1)
        for day in sorted(set(drain_days)):
            hour = day * 24
            if hour < horizon_hour:
                continue
            due = [p for p in pending if p['due_day'] == day]
            for obligation in due:
                action = 'refund' if obligation['default'] else 'release'
                account.execute('event', {'id': obligation['id'], 'action': action,
                    'event_id': obligation['id'] + '-' + action}, hour)
                if not obligation['default']:
                    record['post_horizon_collected_licenses'] += 1
                    state = account.snapshot()['summary']
                    pretax = state['profit'] + tax_paid
                    due_tax = max(0, pretax * world.tax_bps // 10000 - tax_paid)
                    if due_tax > obligation['price_usd'] * MICRO or due_tax > state['available']:
                        raise AssertionError('PRERELEASE_TAX_COMMITMENT_INSUFFICIENT')
                    if due_tax:
                        account.cost('tax-' + obligation['id'], due_tax, hour)
                        tax_paid += due_tax
                    record['tax_settlements'].append({'order_id': obligation['id'], 'hour': hour,
                        'post_horizon': True, 'gross_collection_microUSD': obligation['price_usd'] * MICRO,
                        'available_before_tax_microUSD': state['available'], 'tax_paid_microUSD': due_tax,
                        'payables_after_tax_microUSD': account.snapshot()['summary']['payables']})
            account.advance_financial(hour)
        record['post_horizon_drain_endpoint'] = account.snapshot()['summary']
        record['total_tax_after_drain_microUSD'] = tax_paid
        record['post_horizon_native_audit'] = account.audit()
        record['drain_export_sha256'] = _write_new(output / 'native-after-drain.json', account.export())
    record['resource_measurement'] = {'process_cpu_seconds': time.process_time() - started_cpu,
                                    'wall_seconds': time.monotonic() - started_wall,
                                    'model_api_calls': 0, 'incremental_spending_authorized_usd': 0}
    profit = record['operating_endpoint']['profit']
    record['investor_test'] = {'required_simple_annual_return_bps': 1000,
        'cumulative_company_profit_microUSD': profit, 'horizon_days': horizon_days,
        'meets_hypothetical_equity_return_hurdle': profit * 365 * 10000 >= capital_usd * MICRO * horizon_days * 1000,
        'financing_secured': False, 'founder_dilution': 'UNSPECIFIED_NO_EQUITY_TRANSACTION_MODELED',
        'note': 'Investor hurdle is a separate feasibility diagnostic, not a fictitious wage or company expense.'}
    _write_new(output / 'trajectory.json', record)
    return record


def compact(record):
    return {key: copy.deepcopy(record[key]) for key in (
        'id', 'scope', 'world', 'capital_usd', 'policy', 'earned_only_k2', 'initial_finance',
        'infer_idle_days', 'observation_counts',
        'stop_reason', 'operating_stop_day', 'operating_endpoint', 'rolling_profit', 'K2_funding',
        'actual_scientific_artifacts', 'modeled_licenses', 'external_revenue_usd', 'installed_physical_sites',
        'tax_paid_microUSD', 'opening_plus_flows_reconciles', 'milestone_1b', 'milestone_3b',
        'external_financing_received_usd', 'investor_test', 'resource_measurement', 'native_export_sha256',
        'drain_export_sha256', 'post_horizon_drain_endpoint', 'modeled_human_internal_hours',
        'actual_human_runtime_intervention_minutes_observed', 'unmeasured_human_minutes',
        'post_horizon_collected_licenses', 'total_tax_after_drain_microUSD')}


def run_campaign(root, manifest, output):
    output = Path(output).absolute()
    output.mkdir(parents=True, exist_ok=False)
    recipes = [(World(), capital, 'working_capital_aware', False) for capital in CAPITALS_USD]
    recipes += [(world, 100000, 'working_capital_aware', False) for world in registered_worlds()[1:]]
    recipes += [(World(), 100000, 'working_capital_aware', True),
                (World(), 100000, 'stylized_prepaid_reach_capacity', False)]
    records = []
    for i, (world, capital, policy, earned_only) in enumerate(recipes):
        result = execute_trajectory(root, manifest, output / f'arm-{i:02d}', capital_usd=capital,
                                    world=world, policy=policy, earned_only_k2=earned_only)
        records.append(compact(result))
    game = project_game()
    result = {'schema': 'portfolio071/economic-campaign/v1', 'registered_arms': len(recipes),
              'completed_arms': len(records), 'arms': records, 'factorial_game': game,
              'unique_scientific_artifacts': len(manifest['jobs']),
              'artifact_reuse_scope': 'The same accepted catalog is licensed across counterfactual accounts; per-arm catalog counts must not be summed as new scientific artifacts.',
              'conditional_market_frontier': conditional_market_frontier(),
              'actual_external_revenue_usd': 0, 'milestone_1b_count': sum(r['milestone_1b'] for r in records),
              'milestone_3b_count': sum(r['milestone_3b'] for r in records),
              'claims': {'code_execution': 'SUPPORTED_IF_REPLAY_PASSES',
                         'finite_game_optimality': 'CONDITIONAL_FINITE_MENU_ONLY',
                         'novel_discovery_superiority': 'NOT_ESTABLISHED_CONVENTIONAL_TIE',
                         'actual_market_demand': 'UNRESOLVED_AUTHORED_BUYERS',
                         'physical_installation': 'NOT_RUN', 'industrial_rights': 'UNRESOLVED',
                         'model_cost_calibration': 'UNRESOLVED', 'actual_commerce': 'NOT_RUN'}}
    _write_new(output / 'campaign.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description='Finite native scientific-design licensing experiment; no network or real transactions.')
    parser.add_argument('command', choices=('campaign', 'audit', 'game'))
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--record', type=Path)
    args = parser.parse_args()
    if args.command == 'game':
        result = project_game()
    else:
        if args.manifest is None:
            parser.error('--manifest is required')
        manifest = strict_json(args.manifest.read_bytes())
        if args.command == 'audit':
            if args.record is None:
                parser.error('--record is required')
            result = audit_journal(strict_json(args.record.read_bytes()), root=args.root, manifest=manifest)
        else:
            if args.output is None:
                parser.error('--output is required')
            result = run_campaign(args.root, manifest, args.output)
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
