"""Versioned, source-gated portfolio growth projection using native money semantics.

Aggregate growth settlements below are projected scenario events, not provider
receipts. Executed service qualifications and the protected pilot remain separate.
The existing ProtectedExchange snapshot is the sole earned-funds definition.
"""
from __future__ import annotations
import argparse
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import sqlite3
import statistics
import time
from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import memory_engine
from experiments.commerce006 import engine

ROOT = Path(__file__).resolve().parents[1]
MICRO = 1_000_000


def money(value):
    if type(value) not in {int, float} or not math.isfinite(value) or value < 0 or value > 1e15:
        raise ValueError('FINITE_NONNEGATIVE_USD_REQUIRED')
    return int(round(value * MICRO))


def default_policy():
    return {'schema': 'agi-alpha/portfolio-growth011-policy/v1', 'scope': 'SIMULATED',
            'horizon_months': 120, 'target_trailing_year_revenue': money(1_000_000_000),
            'seed_capital': money(5000), 'working_capital': money(100), 'setup_cost': money(500),
            'maintenance_monthly': money(25), 'initial_capacity_per_category': 40,
            'capacity_unit_cost': money(5), 'lead_cost': money(2), 'bootstrap_acquisition_limit': money(400),
            'onboarding_cost': money(1), 'bid_cost': money(.25), 'payment_rate': .029,
            'payment_fixed': money(.30), 'tax_rate': .20, 'reinvest_fraction': .65,
            'capacity_fraction': .20, 'price_multipliers': [round(.2 + .05 * i, 2) for i in range(27)],
            'acquisition_valuation_horizon_months': 3,
            'pricing_boundary_rule': 'If optimum is a boundary, extend to0.05H or4H before evaluation. NoBid is always feasible.',
            'seeds': list(range(3110001, 3110101)), 'controls': ['earned_reinvestment', 'hold_capacity'],
            'seed_allocation': '100 fixed seeds assigned round-robin to3scenarios; each seed is matched across both controls. Equal scenario weights are explicit reporting conventions.',
            'scenarios': [
                {'id': 'favorable', 'weight': 1 / 3, 'reachable_customers_per_category': 2_000_000,
                 'lead_activation': .55, 'jobs_per_customer_month': 2., 'churn': .012,
                 'approval_probability': .97, 'customer_attention': money(2),
                 'quality_acceptance': .995, 'rework_fraction': .02, 'collect_fraction': .995,
                 'settlement_months': 1, 'provider_tail_months': 2, 'supplier_outage_probability': .01,
                 'supplier_cost_multiplier': 1., 'rival_response_months': 6, 'rival_capacity_share': .35,
                 'rival_cost_fraction': .25, 'customer_self_service_effort_fraction': .45},
                {'id': 'central', 'weight': 1 / 3, 'reachable_customers_per_category': 250_000,
                 'lead_activation': .30, 'jobs_per_customer_month': 1., 'churn': .04,
                 'approval_probability': .85, 'customer_attention': money(8),
                 'quality_acceptance': .98, 'rework_fraction': .08, 'collect_fraction': .97,
                 'settlement_months': 2, 'provider_tail_months': 3, 'supplier_outage_probability': .06,
                 'supplier_cost_multiplier': 1.3, 'rival_response_months': 3, 'rival_capacity_share': .65,
                 'rival_cost_fraction': .20, 'customer_self_service_effort_fraction': .30},
                {'id': 'adverse', 'weight': 1 / 3, 'reachable_customers_per_category': 25_000,
                 'lead_activation': .12, 'jobs_per_customer_month': .5, 'churn': .10,
                 'approval_probability': .60, 'customer_attention': money(25),
                 'quality_acceptance': .90, 'rework_fraction': .30, 'collect_fraction': .85,
                 'settlement_months': 4, 'provider_tail_months': None, 'supplier_outage_probability': .20,
                 'supplier_cost_multiplier': 2., 'rival_response_months': 1, 'rival_capacity_share': .95,
                 'rival_cost_fraction': .15, 'customer_self_service_effort_fraction': .15}],
            'uncertainty': 'All demand, retention, quality at scale, prices, provider terms and resource envelopes are explicit scenarios, not calibrated observations. Equal weights are reporting conventions, not estimated probabilities.',
            'source_qualification_scope': 'Only source-bound executed subset participates; all25 are screened. Scaled simulated jobs are not individually produced or independently accepted artifacts.',
            'optimality_scope': 'Best tested finite-price policy against a bounded responding rival and public population prior. No private buyer reservation values enter seller selection; no Nash or global optimum claim.'}


def validate_policy(p):
    if not isinstance(p, dict) or set(p) != set(default_policy()) or p['scope'] != 'SIMULATED':
        raise ValueError('EXPLICIT_VERSIONED_POLICY_REQUIRED')
    if type(p['horizon_months']) is not int or not 1 <= p['horizon_months'] <= 240:
        raise ValueError('BOUNDED_HORIZON_REQUIRED')
    if not isinstance(p['seeds'], list) or len(p['seeds']) < 3 or len(set(p['seeds'])) != len(p['seeds']) or any(type(s) is not int or s < 0 for s in p['seeds']):
        raise ValueError('FIXED_UNIQUE_SEEDS_REQUIRED')
    for k in ['seed_capital', 'working_capital', 'setup_cost', 'maintenance_monthly', 'capacity_unit_cost', 'lead_cost', 'bootstrap_acquisition_limit', 'onboarding_cost', 'bid_cost', 'payment_fixed', 'target_trailing_year_revenue']:
        if type(p[k]) is not int or not 0 <= p[k] <= 10**21:
            raise ValueError('INTEGER_MICROUSD_REQUIRED')
    for k in ['payment_rate', 'tax_rate', 'reinvest_fraction', 'capacity_fraction']:
        if type(p[k]) not in {int, float} or not math.isfinite(p[k]) or not 0 <= p[k] <= 1:
            raise ValueError('POLICY_PROBABILITY_REQUIRED')
    if p['capacity_fraction'] + p['reinvest_fraction'] > 1:
        raise ValueError('ALLOCATION_CANNOT_EXCEED_EARNINGS')
    if not isinstance(p['price_multipliers'], list) or not p['price_multipliers'] or any(type(v) not in {int, float} or not math.isfinite(v) or v <= 0 for v in p['price_multipliers']):
        raise ValueError('POSITIVE_FINITE_PRICE_GRID_REQUIRED')
    if len(p['scenarios']) != 3 or abs(sum(s['weight'] for s in p['scenarios']) - 1) > 1e-9:
        raise ValueError('THREE_EXPLICIT_SCENARIO_WEIGHTS_REQUIRED')
    for s in p['scenarios']:
        if s['provider_tail_months'] is not None and (type(s['provider_tail_months']) is not int or s['provider_tail_months'] < 1):
            raise ValueError('EXPLICIT_PROVIDER_TAIL_REQUIRED')
        for k in ['lead_activation', 'churn', 'approval_probability', 'quality_acceptance', 'rework_fraction', 'collect_fraction', 'supplier_outage_probability', 'rival_capacity_share', 'rival_cost_fraction', 'customer_self_service_effort_fraction']:
            if type(s[k]) not in {int, float} or not math.isfinite(s[k]) or not 0 <= s[k] <= 1:
                raise ValueError('SCENARIO_PROBABILITY_REQUIRED')
    return p


def keyed_rng(seed, month, category, channel):
    return random.Random(int(hashlib.sha256(canonical([seed, month, category, channel])).hexdigest()[:16], 16))


def count_draw(n, probability, rng):
    if n <= 0:
        return 0
    if not 0 <= probability <= 1:
        raise ValueError('COUNT_PROBABILITY_REQUIRED')
    if probability in (0, 1):
        return n if probability else 0
    if n < 40:
        return sum(rng.random() < probability for _ in range(n))
    return max(0, min(n, int(round(n * probability + rng.gauss(0, math.sqrt(n * probability * (1 - probability)))))))


def logistic(x):
    return 1 / (1 + math.exp(-max(-60., min(60., x))))


def price_choice(service, scenario, policy, public):
    allowed = {'reputation', 'rival_reputation', 'rival_price_fraction', 'repeat_customer_share'}
    if not isinstance(public, dict) or set(public) != allowed:
        raise ValueError('SELLER_PUBLIC_INFORMATION_SCHEMA')
    h = int(service['human_repeat_cost'] * public['repeat_customer_share'] + service['human_first_cost'] * (1 - public['repeat_customer_share']))
    value = 3 * h
    own_quality, rival_quality = public['reputation'], public['rival_reputation']
    rival_cost = int(h * scenario['rival_cost_fraction'])
    rival_price = max(rival_cost, int(h * public['rival_price_fraction']))
    outside = max(.95 * value - h, rival_quality * value - rival_price,
                  .9 * value - int(h * scenario['customer_self_service_effort_fraction']))
    effort = scenario['customer_attention'] * (1 - public['repeat_customer_share'])
    multipliers = sorted(set(policy['price_multipliers'] + [.05, .10, 2., 3., 4., .95, 1.]))
    curve = []
    for factor in multipliers:
        price = int(h * factor)
        utility = own_quality * value - price - effort + .12 * h
        own_vs_outside = logistic((utility - outside) / max(1., .22 * h))
        win = scenario['approval_probability'] * (own_vs_outside * scenario['rival_capacity_share'] +
                logistic((utility - max(0, .95 * value - h)) / max(1., .22 * h)) * (1 - scenario['rival_capacity_share']))
        cost = service['agent_cost'] * scenario['supplier_cost_multiplier'] * (1 + scenario['rework_fraction'])
        first = policy['onboarding_cost'] * (1 - public['repeat_customer_share'])
        net = win * (scenario['quality_acceptance'] * scenario['collect_fraction'] * price * (1 - policy['payment_rate']) - cost - first - policy['payment_fixed']) - policy['bid_cost']
        curve.append({'factor': factor, 'price': price, 'first_price': int(service['human_first_cost'] * factor),
                      'repeat_price': int(service['human_repeat_cost'] * factor), 'win_probability': win, 'expected_complete_contribution_per_quote': net})
    best = max(curve, key=lambda x: (x['expected_complete_contribution_per_quote'], x['price']))
    if best['expected_complete_contribution_per_quote'] <= 0:
        best = {'factor': None, 'price': 0, 'first_price': 0, 'repeat_price': 0, 'win_probability': 0., 'expected_complete_contribution_per_quote': 0.}
    return {'selected': best, 'curve': curve,
            'deviation_residual': max(0., max(x['expected_complete_contribution_per_quote'] for x in curve) - best['expected_complete_contribution_per_quote']),
            'boundary_at_extended_limit': best['factor'] in {.05, 4.},
            'scope': policy['optimality_scope']}


def guarded_growth_budget(native_state, monthly, pending_invoices, scenario, policy):
    if not monthly:
        return {'spendable_earned': 0, 'buffer': 0, 'public_collected_margin': 0}
    observed = monthly[-3:]
    collected_margin = sum(x['collections'] - x['operating_complete_cost'] for x in observed) // len(observed)
    operating = max(x['operating_complete_cost'] for x in observed)
    # Invoice face values and historical expenses are observable. This forecast
    # never reads future collections/default draws or buyer reservation values.
    pending_face = sum(q['invoice'] for q in pending_invoices)
    fee_tax_support_buffer = int(pending_face * (policy['payment_rate'] + policy['tax_rate'] + .05))
    buffer = operating * max(2, 2 * scenario['settlement_months']) + fee_tax_support_buffer
    spendable = max(0, min(native_state['unrestrictedEarned'], native_state['available']) - buffer) if collected_margin > 0 else 0
    return {'spendable_earned': spendable, 'buffer': buffer, 'public_collected_margin': collected_margin}


class NativeProjection:
    """Aggregate scenario journal, with money semantics delegated to native code."""
    def __init__(self, policy, scenario=None, retain_events=True):
        self.policy = policy
        self.retain_events = retain_events
        if scenario is not None and scenario not in policy['scenarios']:
            raise ValueError('FROZEN_SCENARIO_AUTHORITY_REQUIRED')
        self.provider_tail_months = scenario['provider_tail_months'] if scenario is not None else None
        self.ex = memory_engine(engine(), key=b'P' * 32, contract='commercial011-projection',
                                validate=lambda x: None, check=lambda t, a: {'accepted': True, 'decisive': True},
                                opening=policy['seed_capital'], working=policy['working_capital'])
        self.events, self.seen, self.exposures = [], set(), []
        self.authorized_invoices = self.provisioned_invoices = self.settled_invoices = 0
        self.native('cost', 'setup', policy['setup_cost'], month=-1)

    def state(self):
        return self.ex.snapshot()

    def native(self, op, ident, amount, *, month, **extra):
        if ident in self.seen or type(amount) is not int or amount < 0:
            raise ValueError('DUPLICATE_OR_INVALID_PROJECTION_EVENT')
        if op in {'invoice', 'default', 'settlement'} and amount <= 0:
            raise ValueError('POSITIVE_INVOICE_AUTHORITY_AMOUNT_REQUIRED')
        if op in {'default', 'settlement'} and amount > self.authorized_invoices - self.provisioned_invoices - self.settled_invoices:
            raise ValueError('UNBACKED_OR_EXCESS_INVOICE_COLLECTION_OR_PROVISION')
        before = self.state() if self.retain_events else None
        if op == 'cost':
            self.ex.cost(ident, amount)
        elif op == 'invoice':
            self.ex._entry(ident, 'revenue', amount)
            self.authorized_invoices += amount
        elif op == 'default':
            self.ex._entry(ident, 'contra_revenue', amount)
            self.provisioned_invoices += amount
        elif op == 'settlement':
            self.ex._entry(ident, 'collections', amount)
            self.settled_invoices += amount
            self.ex.db.execute('INSERT INTO trades(id,buyer,price,rail,task,task_hash,contract,deadline,state) VALUES(?,?,?,?,?,?,?,?,?)',
                               (ident, 'projected-batch', str(amount), 'nonrecourse-simulated', '{}', digest({}), self.ex.contract, month, 'released'))
            self.exposures.append((ident, month))
        elif op == 'earned_work':
            self.ex.reserve_investment(ident, amount, extra['expected_net'], intent_hash=extra['artifact_sha256'])
            self.ex.finish_investment(ident, amount, extra['artifact_sha256'])
        else:
            raise ValueError('PROJECTION_OPERATION_REQUIRED')
        after = self.state() if self.retain_events else None
        if self.retain_events:
            self.events.append({'id': ident, 'op': op, 'month': month, 'amount': amount, 'extra': extra, 'before': before, 'after': after})
        self.seen.add(ident)
        if after is not None:
            self.conservation(after)
        return after

    def expire(self, month, tail):
        if tail != self.provider_tail_months:
            raise ValueError('UNQUALIFIED_PROVIDER_TAIL_POLICY')
        if tail is None:
            return
        for ident, created in self.exposures:
            if month - created == tail:
                if 'expire-' + ident in self.seen:
                    raise ValueError('DUPLICATE_TAIL_EXPIRY')
                before = self.state() if self.retain_events else None
                self.ex.db.execute("UPDATE trades SET state='projected-contract-tail-expired' WHERE id=?", (ident,))
                if self.retain_events:
                    self.events.append({'id': 'expire-' + ident, 'op': 'contract_tail_expiry', 'month': month,
                                        'amount': 0, 'extra': {'trade': ident, 'provider_tail_months': tail}, 'before': before, 'after': self.state()})
                self.seen.add('expire-' + ident)

    def compact(self):
        totals = {}
        for row in self.ex.db.execute('SELECT kind,amount FROM journal'):
            totals[row['kind']] = totals.get(row['kind'], 0) + int(row['amount'])
        before = self.state() if self.retain_events else None
        self.ex.db.execute('DELETE FROM journal')
        for kind, total in sorted(totals.items()):
            self.ex._entry('lossless-event-projection', kind, total)
        self.ex.db.execute("DELETE FROM trades WHERE state='projected-contract-tail-expired'")
        if self.retain_events and before != self.state():
            raise ValueError('NATIVE_JOURNAL_COMPACTION_CHANGED_MONEY')

    def conservation(self, s):
        if s['cash'] != self.policy['seed_capital'] + s['collections'] + s['recoveryIncome'] - s['expensePaid']:
            raise ValueError('NATIVE_CASH_CONSERVATION')
        if s['profit'] != s['revenue'] + s['recoveryIncome'] - s['expenses'] or s['unrestrictedEarned'] > s['available'] or s['unrestrictedEarned'] < 0:
            raise ValueError('NATIVE_EARNED_OR_PROFIT_CONSERVATION')

    def close(self):
        self.ex.close()


def audit_projection(policy, events, expected, scenario=None):
    book = NativeProjection(policy, scenario)
    try:
        if not events or events[0] != book.events[0]:
            raise ValueError('PROJECTION_SETUP_IDENTITY')
        for event in events[1:]:
            if event['id'] in book.seen:
                raise ValueError('DUPLICATE_PROJECTION_EVENT')
            if event['before'] != book.state():
                raise ValueError('PROJECTION_EVENT_STATE_OR_ORDER')
            if event['op'] == 'contract_tail_expiry':
                ident = event['extra']['trade']
                if event['id'] != 'expire-' + ident:
                    raise ValueError('CANONICAL_TAIL_EXPIRY_ID_REQUIRED')
                prior = next((m for i, m in book.exposures if i == ident), None)
                if book.provider_tail_months is None or event['extra']['provider_tail_months'] != book.provider_tail_months or prior is None or event['month'] - prior != book.provider_tail_months:
                    raise ValueError('UNQUALIFIED_TAIL_RELEASE')
                book.ex.db.execute("UPDATE trades SET state='projected-contract-tail-expired' WHERE id=?", (ident,))
                book.seen.add(event['id'])
            else:
                book.native(event['op'], event['id'], event['amount'], month=event['month'], **event['extra'])
            if event['after'] != book.state():
                raise ValueError('PROJECTION_DERIVED_STATE_CHANGED')
            book.compact()
        if book.state() != expected:
            raise ValueError('PROJECTION_SUMMARY_CHANGED')
        return {'accepted': True, 'scope': 'NATIVE_ACCOUNTED_AGGREGATE_PROJECTION_NOT_PROVIDER_RECEIPTS', 'events': len(events)}
    finally:
        book.close()


def run_world(services, policy, scenario, seed, control, *, retain=False):
    validate_policy(policy)
    if control not in policy['controls'] or not services or any(not s['technical_qualified'] for s in services):
        raise ValueError('EXECUTED_QUALIFIED_SUBSET_AND_CONTROL_REQUIRED')
    book = NativeProjection(policy, scenario, retain_events=retain)
    state = {s['id']: {'customers': 0, 'contacted': 0, 'capacity': policy['initial_capacity_per_category'], 'capacity_backlog': 0,
                      'reputation': 9 / 11, 'rival_reputation': 8 / 10, 'rival_price': .65, 'previous_win': .5,
                      'last_margin': 0} for s in services}
    # One correlated qualification observation is not16 independent market trials.
    queue, monthly, prices = [], [], []
    acquired_total = paid_jobs = simulated_accepted = earned_cycles = repeat_jobs = 0
    paid_customer_onboardings = 0
    bootstrap_spent = 0
    taxes = taxable_max = 0
    target_month = None
    capital_replacement_month = None
    peak_seed_protection = 0
    try:
        for month in range(policy['horizon_months']):
            book.expire(month, scenario['provider_tail_months'])
            due = [q for q in queue if q['due'] == month]
            collections = sum(q['collected'] for q in due)
            settled_jobs = sum(q['collected_jobs'] for q in due)
            if collections:
                book.native('settlement', 'settled-' + str(month), collections, month=month)
                book.native('cost', 'payment-fees-' + str(month), int(collections * policy['payment_rate']) + settled_jobs * policy['payment_fixed'], month=month)
            before = book.state()
            if before['payables'] or before['cash'] < before['workingCapital']:
                break
            guarded = guarded_growth_budget(before, monthly, [q for q in queue if q['due'] > month], scenario, policy) if control == 'guarded_reinvestment' else None
            growth_earned = guarded['spendable_earned'] if guarded else before['unrestrictedEarned']
            if control in {'earned_reinvestment', 'guarded_reinvestment'} and growth_earned > money(20):
                observed_backlog = sum(c['capacity_backlog'] for c in state.values())
                expansion = min(int(growth_earned * policy['capacity_fraction']), observed_backlog * policy['capacity_unit_cost'])
                if guarded:
                    expansion = min(expansion, max(0, guarded['public_collected_margin']) * 2)
                plans = []
                for ident, value in state.items():
                    units = min(value['capacity_backlog'], int(expansion * value['capacity_backlog'] / max(1, observed_backlog)) // policy['capacity_unit_cost'])
                    cost = units * policy['capacity_unit_cost']
                    expected_net = int(units * value['last_margin'] * (1 - scenario['churn']) * (1 - scenario['supplier_outage_probability'])) - cost
                    if units and expected_net > 0:
                        plans.append({'service': ident, 'units': units, 'cost': cost, 'expected_net': expected_net})
                if plans:
                    book.native('earned_work', 'capacity-' + str(month), sum(x['cost'] for x in plans), month=month,
                                expected_net=sum(x['expected_net'] for x in plans), artifact_sha256=digest({'month': month, 'kind': 'capacity', 'plans': plans}))
                    for plan in plans:
                        state[plan['service']]['capacity'] += plan['units']
            available = book.state()
            profitable_acquisition = []
            for service in services:
                current = state[service['id']]
                first = price_choice(service, scenario, policy, {'reputation': current['reputation'], 'rival_reputation': current['rival_reputation'], 'rival_price_fraction': current['rival_price'], 'repeat_customer_share': 0.})['selected']
                repeat = price_choice(service, scenario, policy, {'reputation': current['reputation'], 'rival_reputation': current['rival_reputation'], 'rival_price_fraction': current['rival_price'], 'repeat_customer_share': 1.})['selected']
                retained_months = sum((1 - scenario['churn']) ** m for m in range(1, policy['acquisition_valuation_horizon_months'] + 1))
                lifetime = first['expected_complete_contribution_per_quote'] + first['win_probability'] * scenario['jobs_per_customer_month'] * repeat['expected_complete_contribution_per_quote'] * retained_months
                expected_lead_net = scenario['lead_activation'] * lifetime - policy['lead_cost']
                if expected_lead_net > 0 and current['contacted'] < scenario['reachable_customers_per_category']:
                    profitable_acquisition.append(service['id'])
            guarded = guarded_growth_budget(available, monthly, [q for q in queue if q['due'] > month], scenario, policy) if control == 'guarded_reinvestment' else None
            growth_earned = guarded['spendable_earned'] if guarded else available['unrestrictedEarned']
            earned_marketing = int(growth_earned * policy['reinvest_fraction']) if control in {'earned_reinvestment', 'guarded_reinvestment'} and profitable_acquisition else 0
            if guarded:
                spare_capacity = sum(max(0, state[s['id']]['capacity'] - int(state[s['id']]['customers'] * scenario['jobs_per_customer_month'])) for s in services)
                earned_marketing = min(earned_marketing, spare_capacity * policy['lead_cost'] * 2)
            bootstrap = min(money(40), policy['bootstrap_acquisition_limit'] - bootstrap_spent)
            marketing = min(max(bootstrap, earned_marketing), money(250_000), available['available'] // 3) if profitable_acquisition else 0
            if marketing < 0:
                marketing = 0
            bootstrap_spent += min(bootstrap, marketing)
            remaining_cash = max(0, available['available'] - marketing - policy['maintenance_monthly'])
            batch_cost, invoice, new_customers, accepts, jobs, repeats, bids = policy['maintenance_monthly'] + marketing, 0, 0, 0, 0, 0, 0
            publicly_forecast_collection = 0
            month_categories = []
            for service in services:
                current = state[service['id']]
                effective_churn = min(1., scenario['churn'] + max(0., .95 - current['reputation']) * .1)
                churn = count_draw(current['customers'], effective_churn, keyed_rng(seed, month, service['id'], 'churn'))
                current['customers'] -= churn
                reach_left = max(0, scenario['reachable_customers_per_category'] - current['contacted'])
                leads = min(reach_left, marketing // max(1, len(profitable_acquisition)) // max(1, policy['lead_cost'])) if service['id'] in profitable_acquisition else 0
                current['contacted'] += leads
                arriving = count_draw(leads, scenario['lead_activation'], keyed_rng(seed, month, service['id'], 'arrivals'))
                repeat_opportunities = int(current['customers'] * scenario['jobs_per_customer_month'])
                opportunities = arriving + repeat_opportunities
                public = {'reputation': current['reputation'], 'rival_reputation': current['rival_reputation'],
                          'rival_price_fraction': current['rival_price'], 'repeat_customer_share': repeat_opportunities / max(1, opportunities)}
                selected = price_choice(service, scenario, policy, public)
                quote = selected['selected']
                current['last_margin'] = max(0, int((quote['expected_complete_contribution_per_quote'] + policy['bid_cost']) / max(.0001, quote['win_probability'])))
                if quote['factor'] is None:
                    month_categories.append({'service': service['id'], 'no_bid': True, 'opportunities': opportunities})
                    continue
                won_new = count_draw(arriving, quote['win_probability'], keyed_rng(seed, month, service['id'], 'private-new-choice'))
                won_repeat = count_draw(repeat_opportunities, quote['win_probability'], keyed_rng(seed, month, service['id'], 'private-repeat-choice'))
                capacity = current['capacity']
                outage = keyed_rng(seed, month, 'portfolio', 'supplier-outage').random() < scenario['supplier_outage_probability']
                if outage:
                    capacity //= 3
                wanted = min(capacity, won_new + won_repeat)
                current['capacity_backlog'] = max(0, won_new + won_repeat - capacity)
                unit_cost = max(1, int(service['agent_cost'] * scenario['supplier_cost_multiplier'] * (1 + scenario['rework_fraction'])))
                bid_cost = min(opportunities * policy['bid_cost'], remaining_cash)
                liquidity_per_job = unit_cost + policy['onboarding_cost'] + int(max(quote['first_price'], quote['repeat_price']) * policy['tax_rate'])
                affordable = max(0, (remaining_cash - bid_cost) // max(1, liquidity_per_job))
                delivered = min(wanted, affordable)
                delivered_new = min(won_new, delivered)
                delivered_repeat = min(won_repeat, delivered - delivered_new)
                publicly_forecast_collection += int((delivered_new * quote['first_price'] + delivered_repeat * quote['repeat_price']) * scenario['quality_acceptance'] * scenario['collect_fraction'])
                accepted_new = count_draw(delivered_new, scenario['quality_acceptance'], keyed_rng(seed, month, service['id'], 'projected-quality-new'))
                accepted_repeat = count_draw(delivered_repeat, scenario['quality_acceptance'], keyed_rng(seed, month, service['id'], 'projected-quality-repeat'))
                accepted = accepted_new + accepted_repeat
                collected_new = count_draw(accepted_new, scenario['collect_fraction'], keyed_rng(seed, month, service['id'], 'projected-collections-new'))
                collected_repeat = count_draw(accepted_repeat, scenario['collect_fraction'], keyed_rng(seed, month, service['id'], 'projected-collections-repeat'))
                projected_collected_jobs = collected_new + collected_repeat
                invoice_amount = accepted_new * quote['first_price'] + accepted_repeat * quote['repeat_price']
                collected_amount = collected_new * quote['first_price'] + collected_repeat * quote['repeat_price']
                cost = delivered * unit_cost + bid_cost + delivered_new * policy['onboarding_cost']
                remaining_cash -= cost
                batch_cost += cost
                invoice += invoice_amount
                accepts += accepted
                jobs += delivered
                repeats += delivered_repeat
                new_customers += delivered_new
                bids += opportunities
                current['customers'] += delivered_new
                # Public history learns from delivered quality; both competitors
                # receive the same qualification prior and can adapt on cadence.
                if delivered:
                    current['reputation'] = .9 * current['reputation'] + .1 * accepted / delivered
                if month and month % scenario['rival_response_months'] == 0:
                    current['rival_reputation'] = min(scenario['quality_acceptance'], current['rival_reputation'] + .025)
                    rival_options = [.2, .35, .5, .65, .8, 1.]
                    current['rival_price'] = max(rival_options, key=lambda f: max(0, f - scenario['rival_cost_fraction']) * logistic((quote['factor'] - f) / .2))
                queue.append({'due': month + scenario['settlement_months'], 'invoice': invoice_amount, 'collected': collected_amount,
                              'collected_jobs': projected_collected_jobs, 'defaulted': invoice_amount - collected_amount})
                prices.append(quote['price'])
                month_categories.append({'service': service['id'], 'opportunities': opportunities, 'new_arrivals': arriving,
                                         'repeat_opportunities': repeat_opportunities, 'bids': opportunities, 'won_and_produced': delivered,
                                         'simulated_accepted': accepted, 'new_customers': delivered_new, 'repeat_jobs': delivered_repeat,
                                         'price': quote['price'], 'first_price': quote['first_price'], 'repeat_price': quote['repeat_price'],
                                         'win_probability_model': quote['win_probability'], 'actual_win_fraction': delivered / max(1, opportunities),
                                         'quality_basis': service['qualification_scope'], 'capacity': capacity, 'supplier_outage': outage,
                                         'provider_onboarding_cost': delivered_new * policy['onboarding_cost'],
                                         'production_rework_support_cost': delivered * unit_cost, 'unsuccessful_and_successful_bid_cost': bid_cost,
                                         'seller_public': public, 'price_search_residual': selected['deviation_residual'], 'price_boundary': selected['boundary_at_extended_limit']})
            before_commit = book.state()
            funding = 'BOOTSTRAP_OR_REMAINING_LIQUIDITY'
            forecast_net = publicly_forecast_collection - batch_cost
            if batch_cost and forecast_net > 0 and before_commit['unrestrictedEarned'] >= batch_cost and before_commit['profit'] > 0:
                book.native('earned_work', 'operations-' + str(month), batch_cost, month=month,
                            expected_net=forecast_net, artifact_sha256=digest({'month': month, 'qualification': [s['source_sha256'] for s in services], 'public_forecast_collection': publicly_forecast_collection}))
                funding = 'PRIOR_UNRESTRICTED_SIMULATED_EARNINGS'
                earned_cycles += int(jobs > 0)
            else:
                book.native('cost', 'operations-' + str(month), batch_cost, month=month)
            if invoice:
                book.native('invoice', 'invoiced-' + str(month), invoice, month=month)
                expected_noncollection = sum(q['defaulted'] for q in queue if q['due'] == month + scenario['settlement_months'])
                if expected_noncollection:
                    book.native('default', 'bad-debt-provision-' + str(month), expected_noncollection, month=month)
            after = book.state()
            taxable = max(0, after['profit'] + taxes)
            tax = int(max(0, taxable - taxable_max) * policy['tax_rate'])
            if tax:
                book.native('cost', 'tax-' + str(month), tax, month=month)
                taxes += tax
            taxable_max = max(taxable_max, taxable)
            after = book.state()
            peak_seed_protection = max(peak_seed_protection, after['equityProtectionBacking'])
            if capital_replacement_month is None and after['unrestrictedEarned'] >= policy['seed_capital']:
                capital_replacement_month = month + 1
            acquired_total += new_customers
            paid_jobs += settled_jobs
            simulated_accepted += accepts
            repeat_jobs += repeats
            paid_customer_onboardings += new_customers
            last_collections = [r['collections'] for r in monthly[-11:]] + [collections]
            trailing_year = sum(last_collections)
            annualized = collections * 12
            if target_month is None and len(monthly) >= 11 and trailing_year >= policy['target_trailing_year_revenue']:
                target_month = month + 1
            monthly.append({'month': month + 1, 'scope': 'SIMULATED_AGGREGATE_EXTRAPOLATION', 'collections': collections,
                            'annualized_run_rate': annualized, 'realized_trailing_12month_revenue': trailing_year,
                            'cumulative_collections': after['collections'], 'profit': after['profit'], 'cash': after['cash'],
                            'unrestricted_earned': after['unrestrictedEarned'], 'seed_capital': policy['seed_capital'],
                            'receivables': sum(q['invoice'] for q in queue if q['due'] > month),
                            'defaulted_collections_this_month': sum(q['defaulted'] for q in due),
                            'funding': funding, 'guarded_capital_allocation': guarded,
                            'public_forecast_collection_before_quality_and_default_outcomes': publicly_forecast_collection,
                            'operating_complete_cost': batch_cost + tax,
                            'new_customers': new_customers, 'paid_customer_onboardings': new_customers,
                            'simulated_jobs_produced': jobs, 'simulated_accepted': accepts, 'settled_jobs': settled_jobs,
                            'repeat_jobs': repeats, 'bids': bids, 'native_summary': after, 'categories': month_categories})
            book.compact()
        final = book.state()
        book.conservation(final)
        result = {'schema': 'agi-alpha/portfolio-growth011-world/v1', 'scope': 'SIMULATED', 'scenario': scenario['id'], 'seed': seed,
                  'control': control, 'policy_sha256': digest(policy), 'services_sha256': digest(services), 'target_month': target_month,
                  'horizon_completed_months': len(monthly), 'paid_jobs': paid_jobs, 'simulated_accepted_jobs': simulated_accepted,
                  'repeat_jobs': repeat_jobs, 'new_customers': acquired_total, 'one_time_onboardings': paid_customer_onboardings,
                  'earned_funded_cycles': earned_cycles, 'summary': final, 'cash_survived': final['cash'] >= 0 and final['payables'] == 0,
                  'seed_capital': policy['seed_capital'], 'peak_seed_still_backing_protection': peak_seed_protection,
                  'capital_replacement_possible_month': capital_replacement_month,
                  'capital_metric_scope': 'No capital is actually withdrawn; possible replacement requires available earnings at least equal original seed, and does not gate commercial loop success.',
                  'annualized_run_rate': monthly[-1]['annualized_run_rate'] if monthly else 0,
                  'realized_trailing_12month_revenue': monthly[-1]['realized_trailing_12month_revenue'] if monthly else 0,
                  'cumulative_collections': final['collections'], 'complete_cost_profit': final['profit'],
                  'prices': {'minimum': min(prices) if prices else None, 'median': statistics.median(prices) if prices else None, 'maximum': max(prices) if prices else None},
                  'conditional_simulated_loop': final['profit'] > 0 and earned_cycles >= 2 and repeat_jobs > 0 and final['payables'] == 0,
                  'binding_constraints': ['reachable-market/channel saturation', 'buyer/rival and DIY outside options', 'supplier capacity/outages', 'liquidity/settlement delay', 'provider reserve duration'],
                  'native_engine_sha256': hashlib.sha256((ROOT / 'vendor/alpha_claim/protected_exchange.py').read_bytes()).hexdigest(),
                  'limits': [policy['uncertainty'], policy['source_qualification_scope'], 'Monthly settlements are aggregate projections, not fabricated native provider receipts. Native snapshot/earned/investment rules are reused; expired-tail terms are explicit successor assumptions, not PR16-equivalent assurance.']}
        if retain:
            result.update(monthly=monthly, native_projection_events=book.events)
            audit_projection(policy, book.events, final, scenario)
        return result
    finally:
        book.close()


def load_services(root, path):
    raw = Path(path).read_bytes()
    manifest = strict_json(raw)
    if manifest.get('scope') not in {'PUBLIC_SYNTHETIC_TECHNICAL_WORK_ONLY', 'SYNTHETIC_EXECUTED_SERVICES', 'EXECUTED_PUBLIC_SYNTHETIC', 'SYNTHETIC_AUTHORIZED_PUBLIC', 'SIMULATED_TECHNICAL_EXECUTION'}:
        raise ValueError('EXPLICIT_EXECUTED_SERVICE_SCOPE_REQUIRED')
    review = manifest.get('independent_review')
    if not isinstance(review, dict) or set(review) != {'path', 'sha256'}:
        raise ValueError('INDEPENDENT_SERVICE_REVIEW_REQUIRED')
    review_path = Path(review['path'])
    if review_path.is_absolute() or '..' in review_path.parts or hashlib.sha256((Path(root) / review_path).read_bytes()).hexdigest() != review['sha256']:
        raise ValueError('SERVICE_REVIEW_IDENTITY_CHANGED')
    evidence = strict_json((Path(root) / review_path).read_bytes())
    checker_path = Path(root) / 'commercial/portfolio_services_check.py'
    if hashlib.sha256(checker_path.read_bytes()).hexdigest() != evidence.get('checker_source_sha256'):
        raise ValueError('INDEPENDENT_CHECKER_IDENTITY_CHANGED')
    from commercial.portfolio_services_check import verify_services
    fresh = verify_services(Path(root), manifest)
    if fresh.get('accepted') is not True or fresh.get('payload_sha256') != evidence.get('payload_sha256'):
        raise ValueError('SERVICE_REVIEW_PAYLOAD_OR_ACCEPTANCE_CHANGED')
    result = []
    for row in manifest.get('services', manifest.get('rows', [])):
        if row.get('accepted') is not True:
            continue
        for artifact in row['artifacts'] + [row['acceptance_receipt']]:
            p = Path(artifact['path'])
            if p.is_absolute() or '..' in p.parts or (Path(root) / p).is_symlink() or hashlib.sha256((Path(root) / p).read_bytes()).hexdigest() != artifact['sha256']:
                raise ValueError('EXECUTED_SERVICE_ARTIFACT_CHANGED')
        receipt = strict_json((Path(root) / row['acceptance_receipt']['path']).read_bytes())
        if receipt.get('accepted') is not True:
            raise ValueError('SERVICE_ACCEPTANCE_AUTHORITY_REQUIRED')
        for key in ['human_first_cost_usd_interval', 'human_repeat_cost_usd_interval', 'agent_operating_cost_usd_interval']:
            interval = row[key]
            if not isinstance(interval, list) or len(interval) != 2 or interval[0] <= 0 or interval[1] < interval[0]:
                raise ValueError('EXPLICIT_SERVICE_COST_INTERVAL_REQUIRED')
        result.append({'id': row['portfolio_id'], 'technical_qualified': True,
                       'human_first_cost': money(statistics.mean(row['human_first_cost_usd_interval'])),
                       'human_repeat_cost': money(statistics.mean(row['human_repeat_cost_usd_interval'])),
                       'agent_cost': money(statistics.mean(row['agent_operating_cost_usd_interval'])),
                       'source_sha256': hashlib.sha256(canonical(row)).hexdigest(),
                       'qualification_scope': row.get('scope_limits', 'Source-bound finite technical qualification; not real-market quality or per-scaled-job verification.')})
    if not result or len({x['id'] for x in result}) != len(result):
        raise ValueError('UNIQUE_NONEMPTY_EXECUTED_SUBSET_REQUIRED')
    return result, hashlib.sha256(raw).hexdigest()


def aggregate(worlds, horizon):
    times = sorted(w['target_month'] for w in worlds if w['target_month'] is not None)
    profits = sorted(w['complete_cost_profit'] for w in worlds)
    return {'runs': len(worlds), 'conditional_loop_fraction': sum(w['conditional_simulated_loop'] for w in worlds) / len(worlds),
            'target_reached_fraction': len(times) / len(worlds), 'time_to_target_months_if_reached': {'minimum': min(times), 'median': statistics.median(times), 'maximum': max(times)} if times else None,
            'right_censored_without_target': len(worlds) - len(times), 'horizon_months': horizon,
            'profit_microUSD': {'minimum': profits[0], 'median': statistics.median(profits), 'maximum': profits[-1]},
            'cash_survival_fraction': sum(w['cash_survived'] for w in worlds) / len(worlds),
            'median_earned_funded_cycles': statistics.median(w['earned_funded_cycles'] for w in worlds),
            'median_repeat_jobs': statistics.median(w['repeat_jobs'] for w in worlds),
            'median_trailing_year_revenue': statistics.median(w['realized_trailing_12month_revenue'] for w in worlds),
            'median_annualized_run_rate': statistics.median(w['annualized_run_rate'] for w in worlds),
            'median_cumulative_revenue': statistics.median(w['cumulative_collections'] for w in worlds)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--services', type=Path, required=True)
    p.add_argument('--policy', type=Path, required=True)
    p.add_argument('--expected-policy-sha256', required=True)
    p.add_argument('--expected-services-sha256', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists() or a.output.is_symlink():
        raise FileExistsError(a.output)
    if hashlib.sha256(a.policy.read_bytes()).hexdigest() != a.expected_policy_sha256 or hashlib.sha256(a.services.read_bytes()).hexdigest() != a.expected_services_sha256:
        raise ValueError('EXTERNAL_FROZEN_INPUT_IDENTITY_REQUIRED')
    policy = validate_policy(strict_json(a.policy.read_bytes()))
    services, services_sha = load_services(ROOT, a.services)
    a.output.mkdir(parents=True)
    started, cpu = time.monotonic(), time.process_time()
    summaries, all_results = {}, []
    trace_index = []
    for scenario_index, scenario in enumerate(policy['scenarios']):
        summaries[scenario['id']] = {}
        scenario_seeds = policy['seeds'][scenario_index::len(policy['scenarios'])]
        for control in policy['controls']:
            worlds = []
            for seed in scenario_seeds:
                world = run_world(services, policy, scenario, seed, control, retain=True)
                target = a.output / 'world-journals' / scenario['id'] / control / (str(seed) + '.json.gz')
                target.parent.mkdir(parents=True, exist_ok=True)
                packed = gzip.compress(canonical(world), compresslevel=6, mtime=0)
                with target.open('xb') as f:
                    f.write(packed)
                trace_index.append({'path': str(target.relative_to(a.output)), 'sha256': hashlib.sha256(packed).hexdigest(),
                                    'uncompressed_sha256': digest(world), 'bytes': len(packed), 'scope': 'Full monthly states and every native projection event; independently rebuilt by audit_projection.'})
                if seed == scenario_seeds[0]:
                    with (a.output / (scenario['id'] + '-' + control + '-representative.json')).open('x') as f:
                        json.dump(world, f, indent=2, allow_nan=False)
                worlds.append({k: v for k, v in world.items() if k not in {'monthly', 'native_projection_events'}})
            summaries[scenario['id']][control] = aggregate(worlds, policy['horizon_months'])
            all_results.extend({k: v for k, v in world.items() if k not in {'monthly', 'native_projection_events'}} for world in worlds)
    result = {'schema': 'agi-alpha/portfolio-growth011-result/v1', 'scope': 'SIMULATED_AGGREGATE_PROJECTION',
              'policy_file_sha256': a.expected_policy_sha256, 'services_manifest_sha256': services_sha,
              'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'qualified_services': services,
              'scenarios': summaries, 'worlds': all_results, 'full_event_journals': trace_index, 'cpu_seconds': time.process_time() - cpu,
              'wall_seconds': time.monotonic() - started, 'actual_customers': 0, 'actual_collections': 0,
              'billion_objective': 'Time-based trailing12month collections target, not customer-count arithmetic; censored failures retained.',
              'scope_limits': [policy['uncertainty'], policy['source_qualification_scope'], policy['optimality_scope']]}
    with (a.output / 'RESULT.json').open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False)
    print(json.dumps({k: result[k] for k in ['scope', 'scenarios', 'cpu_seconds', 'wall_seconds']}, indent=2))


if __name__ == '__main__':
    main()
