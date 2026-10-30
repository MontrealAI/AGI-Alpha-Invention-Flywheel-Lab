"""Bounded strategic simulated repeat market for actually executed service artifacts."""
from __future__ import annotations
import copy
import hashlib
import json
import math
from pathlib import Path
import random
import tempfile
import time
from .ledger import TapeExchange, amount, audit, canonical, digest, load_jobs, strict_json

ROOT = Path(__file__).resolve().parents[1]
MICRO = 1_000_000


def usd(value):
    return int(round(value * MICRO))


def default_policy():
    return {
        'schema': 'agi-alpha/commercial010-policy/v1', 'scope': 'SIMULATED',
        'currency': 'simulated-microUSD', 'cycles': 8, 'jobs_per_cycle': 2,
        'opening': usd(5000), 'working': usd(100),
        'human_benchmark': usd(139), 'human_onboarding_component': usd(17.375),
        'human_stages_hours_first': {'onboarding': .5, 'research': .25, 'production': 2., 'verification': .5, 'correction': .25, 'acquisition_ordering': .25, 'support': .25},
        'human_repeat_hours': 3.5, 'human_loaded_hourly_usd': 34.75, 'human_benchmark_interval': [usd(17.375), usd(278)],
        'human_benchmark_basis': 'BLS May2025 bookkeeping wage24.36/hour times Dec2025 private total-compensation46.15/wage32.36; rounded loaded34.75/hour. Four-hour source-matched manual-work scenario=139USD; sensitivity0.5–8hours; exact task time unobserved, no invented overhead or double loading. Human tools/acquisition/support above this conservative floor remain an explicit comparability limit',
        'adaptive_price_candidates': [{'id': 'first10500-repeat12000', 'first_bps': 10500, 'repeat_bps': 12000}],
        'initial_discount_bps': 500, 'price_multipliers_bps': [9000, 9500, 9800, 10000, 10500, 12000, 15000],
        'setup_cost_interval': [usd(200), usd(2500)], 'setup_cost': usd(500),
        'per_job_cost_interval': [usd(5), usd(30)], 'per_job_cost': usd(15),
        'cost_basis': 'CONDITIONAL_RESOURCE_ENVELOPES_NOT_ACTUAL_TOKEN_RECEIPTS; setup includes all campaign development, failed search, integration, acquisition-design and maintenance; per cohort job includes agent inference, tools, compute, storage, production, verification, repairs, failures, delivery and post-delivery obligations; host usage and bills are unavailable',
        'acquisition_new': usd(4), 'acquisition_repeat': usd(1), 'support_per_sale': usd(3),
        'agent_onboarding_original': 0, 'agent_onboarding_autonomous': usd(1),
        'agent_onboarding_autonomous_interval': [usd(.01), usd(2)],
        'external_onboarding_fee': 0,
        'onboarding_basis': 'Original agent onboarding is already included in the15USD production/acquisition envelope; the separate0 line does not assert no cost. Corrected CSV workflow adds an explicit1USD agent/tool/compute intake scenario once, bracket0.01–2USD; actual inference receipts unavailable. Historical25USD was BUYER attention, not our staff or agent invoice. Original vs corrected customer friction is a conditional workflow hypothesis, bracket0–50, not measured. Externalfee0 assumes no paid onboarding provider; payment fees remain separate. First consented accepted service only, persists after refund.',
        'arms': [{'id': 'fixed_original', 'strategic_pricing': False, 'corrected_onboarding': False},
                 {'id': 'fixed_autonomous_onboarding', 'strategic_pricing': False, 'corrected_onboarding': True},
                 {'id': 'strategic_original', 'strategic_pricing': True, 'corrected_onboarding': False},
                 {'id': 'strategic_autonomous_onboarding', 'strategic_pricing': True, 'corrected_onboarding': True}],
        'payment_bps': 290, 'payment_fixed': usd(.30), 'tax_bps': 2000,
        'exploration_seeds': [1, 2], 'confirmation_seeds': list(range(23001001, 23001007)),
        'sensitivity_seeds': [201, 202, 203],
        'sensitivity_cases': [{'id': 'cost_low', 'setup': usd(200), 'per_job': usd(5), 'human': usd(139)},
                              {'id': 'cost_region_edge', 'setup': usd(700), 'per_job': usd(20), 'human': usd(139)},
                              {'id': 'cost_high', 'setup': usd(1000), 'per_job': usd(30), 'human': usd(139)},
                              {'id': 'full_upper_cost', 'setup': usd(2500), 'per_job': usd(30), 'human': usd(139)},
                              {'id': 'human_half_hour', 'setup': usd(500), 'per_job': usd(15), 'human': usd(17.375)},
                              {'id': 'human_two_hours', 'setup': usd(500), 'per_job': usd(15), 'human': usd(69.5)},
                              {'id': 'human_eight_hours', 'setup': usd(500), 'per_job': usd(15), 'human': usd(278)}],
        'minimum_earned_cycles': 2, 'minimum_paid_jobs': 6,
        'minimum_repeat_buyers': 1, 'minimum_region_success_fraction': .75,
        'selection_rule': 'Maximize exploration expected complete-cost profit across equally weighted qualification worlds and fixed common seeds, subject to cash survival and zero payable breaches. Compare NoBid preserving setup-only cash. No win-rate/GO/all-world-perfect-success condition and no private buyer values are given to the selector. Finite-grid conditional optimum, not Nash or observed optimal pricing.',
        'terminal_obligations': 'Native exchange retains full settled principal plus $0.20 per released order throughout the horizon; working capital is restricted; no tail expiry or extra liquidity is invented',
        'strategic_scope': 'Finite heterogeneous repeated buyers; rival grid profit-maximization on noisy values, trust and capacity; supplier bounded scarcity response. Bounded heuristics, not Nash equilibrium. No actual demand data.',
        'worlds': [
            {'id': 'qualified_differentiation', 'qualification_region': True, 'value_low': 900, 'value_high': 1800, 'trust': .99, 'rival_trust': .79, 'arrival': .98, 'rival_cost': 35, 'supplier_multiplier': 1., 'settlement_delay': 1, 'revision_probability': .05, 'dispute_probability': .01, 'switching': 5, 'original_switching': 25, 'delivery_premium': 25, 'self_service_cost': 30, 'self_service_trust': .85},
            {'id': 'moderate_differentiation', 'qualification_region': True, 'value_low': 750, 'value_high': 1650, 'trust': .98, 'rival_trust': .80, 'arrival': .95, 'rival_cost': 45, 'supplier_multiplier': 1.1, 'settlement_delay': 2, 'revision_probability': .10, 'dispute_probability': .02, 'switching': 10, 'original_switching': 20, 'delivery_premium': 15, 'self_service_cost': 30, 'self_service_trust': .85},
            {'id': 'delayed_high_assurance', 'qualification_region': True, 'value_low': 1000, 'value_high': 1850, 'trust': .985, 'rival_trust': .82, 'arrival': .95, 'rival_cost': 40, 'supplier_multiplier': 1.2, 'settlement_delay': 5, 'revision_probability': .12, 'dispute_probability': .02, 'switching': 5, 'original_switching': 30, 'delivery_premium': 10, 'self_service_cost': 30, 'self_service_trust': .85},
            {'id': 'original_onboarding_barrier', 'qualification_region': False, 'value_low': 900, 'value_high': 1800, 'trust': .99, 'rival_trust': .79, 'arrival': .98, 'rival_cost': 35, 'supplier_multiplier': 1., 'settlement_delay': 1, 'revision_probability': .05, 'dispute_probability': .01, 'switching': 25, 'original_switching': 25, 'delivery_premium': 0, 'self_service_cost': 30, 'self_service_trust': .85},
            {'id': 'commodity_ai_parity', 'qualification_region': False, 'value_low': 400, 'value_high': 900, 'trust': .97, 'rival_trust': .99, 'arrival': .95, 'rival_cost': 20, 'supplier_multiplier': 1., 'settlement_delay': 1, 'revision_probability': .05, 'dispute_probability': .02, 'switching': 0, 'original_switching': 0, 'delivery_premium': 25, 'self_service_cost': 5, 'self_service_trust': .99},
            {'id': 'zero_demand', 'qualification_region': False, 'value_low': 0, 'value_high': 50, 'trust': .99, 'rival_trust': .90, 'arrival': .10, 'rival_cost': 35, 'supplier_multiplier': 1., 'settlement_delay': 1, 'revision_probability': .05, 'dispute_probability': .01, 'switching': 0, 'original_switching': 0, 'delivery_premium': 0, 'self_service_cost': 5, 'self_service_trust': .99},
            {'id': 'correlated_adverse', 'qualification_region': False, 'value_low': 400, 'value_high': 900, 'trust': .72, 'rival_trust': .96, 'arrival': .55, 'rival_cost': 20, 'supplier_multiplier': 2.5, 'settlement_delay': 18, 'revision_probability': .45, 'dispute_probability': .25, 'switching': 0, 'original_switching': 0, 'delivery_premium': 0, 'self_service_cost': 5, 'self_service_trust': .99},
        ]}


def validate_policy(policy):
    template = default_policy()
    if not isinstance(policy, dict) or set(policy) != set(template):
        raise ValueError('FROZEN_POLICY_SCHEMA')
    if policy['schema'] != template['schema'] or policy['scope'] != 'SIMULATED' or policy['currency'] != template['currency']:
        raise ValueError('UNSUPPORTED_SCOPE_OR_CURRENCY')
    monetary = ['opening', 'working', 'human_benchmark', 'setup_cost', 'per_job_cost', 'acquisition_new', 'acquisition_repeat', 'support_per_sale', 'payment_fixed', 'human_onboarding_component', 'agent_onboarding_original', 'agent_onboarding_autonomous', 'external_onboarding_fee']
    for key in monetary:
        amount(policy[key])
    amount(policy['human_benchmark'], positive=True)
    for key in ['cycles', 'jobs_per_cycle', 'minimum_earned_cycles', 'minimum_paid_jobs', 'minimum_repeat_buyers']:
        if type(policy[key]) is not int or not 1 <= policy[key] <= 1000:
            raise ValueError('POSITIVE_BOUNDED_POLICY_INTEGER')
    for key in ['initial_discount_bps', 'payment_bps', 'tax_bps']:
        if type(policy[key]) is not int or not 0 <= policy[key] <= 10000:
            raise ValueError('BASIS_POINT_POLICY_REQUIRED')
    if 10000 - policy['initial_discount_bps'] not in policy['price_multipliers_bps']:
        raise ValueError('INITIAL_DISCOUNT_MUST_BE_TESTED')
    if policy['initial_discount_bps'] > 1000:
        raise ValueError('PREMIUM_SMALL_DISCOUNT_REQUIRED')
    multipliers = policy['price_multipliers_bps']
    if not isinstance(multipliers, list) or not multipliers or any(type(x) is not int or not 9000 <= x <= 15000 for x in multipliers):
        raise ValueError('PREMIUM_PRICE_GRID_REQUIRED')
    adaptive = policy['adaptive_price_candidates']
    if not isinstance(adaptive, list) or any(not isinstance(c, dict) or set(c) != {'id', 'first_bps', 'repeat_bps'} or not isinstance(c['id'], str) or any(type(c[k]) is not int or c[k] not in multipliers for k in ['first_bps', 'repeat_bps']) for c in adaptive):
        raise ValueError('FROZEN_ADAPTIVE_PRICE_CANDIDATES_REQUIRED')
    stages = policy['human_stages_hours_first']
    if not isinstance(stages, dict) or not stages or any(type(v) not in {int, float} or not math.isfinite(v) or v < 0 for v in stages.values()) or type(policy['human_repeat_hours']) not in {int, float} or policy['human_repeat_hours'] <= 0 or type(policy['human_loaded_hourly_usd']) not in {int, float} or not math.isfinite(policy['human_loaded_hourly_usd']) or policy['human_loaded_hourly_usd'] <= 0:
        raise ValueError('FULL_HUMAN_LABOR_STAGES_REQUIRED')
    for key in ['setup_cost_interval', 'per_job_cost_interval', 'human_benchmark_interval', 'agent_onboarding_autonomous_interval']:
        values = policy[key]
        if not isinstance(values, list) or len(values) != 2:
            raise ValueError('COST_INTERVAL_REQUIRED')
        for value in values:
            amount(value)
        if values[0] > values[1]:
            raise ValueError('ORDERED_INTERVAL_REQUIRED')
    if not policy['setup_cost_interval'][0] <= policy['setup_cost'] <= policy['setup_cost_interval'][1] or not policy['per_job_cost_interval'][0] <= policy['per_job_cost'] <= policy['per_job_cost_interval'][1]:
        raise ValueError('COST_OUTSIDE_DECLARED_INTERVAL')
    for key in ['exploration_seeds', 'confirmation_seeds', 'sensitivity_seeds']:
        values = policy[key]
        if not isinstance(values, list) or not values or len(set(values)) != len(values) or any(type(v) is not int or v < 0 for v in values):
            raise ValueError('FIXED_UNIQUE_SEEDS_REQUIRED')
    if set(policy['exploration_seeds']) & set(policy['confirmation_seeds']) or set(policy['sensitivity_seeds']) & (set(policy['exploration_seeds']) | set(policy['confirmation_seeds'])):
        raise ValueError('EXPLORATION_CONFIRMATION_OVERLAP')
    first_hours = sum(policy['human_stages_hours_first'].values())
    onboarding_hours = policy['human_stages_hours_first'].get('onboarding', 0)
    if abs(usd(first_hours * policy['human_loaded_hourly_usd']) - policy['human_benchmark']) > 1 or abs(usd(onboarding_hours * policy['human_loaded_hourly_usd']) - policy['human_onboarding_component']) > 1 or abs(first_hours - onboarding_hours - policy['human_repeat_hours']) > 1e-9:
        raise ValueError('HUMAN_ONBOARDING_MUST_BE_INCLUDED_ONCE')
    arms = policy['arms']
    if not isinstance(arms, list) or len(arms) != 4 or any(not isinstance(a, dict) or set(a) != {'id', 'strategic_pricing', 'corrected_onboarding'} or type(a['strategic_pricing']) is not bool or type(a['corrected_onboarding']) is not bool for a in arms) or {(a['strategic_pricing'], a['corrected_onboarding']) for a in arms} != {(False, False), (False, True), (True, False), (True, True)}:
        raise ValueError('MATCHED_FOUR_ARM_FACTORIAL_REQUIRED')
    cases = policy['sensitivity_cases']
    if not isinstance(cases, list) or not cases or any(not isinstance(c, dict) or set(c) != {'id', 'setup', 'per_job', 'human'} for c in cases) or len({c['id'] for c in cases}) != len(cases):
        raise ValueError('FIXED_COST_SENSITIVITY_CASES_REQUIRED')
    for c in cases:
        for key in ['setup', 'per_job', 'human']:
            amount(c[key], positive=True)
    for key in ['minimum_region_success_fraction']:
        if type(policy[key]) not in {int, float} or not math.isfinite(policy[key]) or not 0 < policy[key] <= 1:
            raise ValueError('BOUNDED_SUCCESS_THRESHOLD_REQUIRED')
    worlds = policy['worlds']
    if not isinstance(worlds, list) or not worlds or any(not isinstance(w, dict) for w in worlds) or len({w.get('id') for w in worlds}) != len(worlds) or not any(w.get('qualification_region') is True for w in worlds):
        raise ValueError('UNIQUE_WORLD_SCHEMA')
    fields = set(template['worlds'][0])
    for world in worlds:
        if not isinstance(world, dict) or set(world) != fields or type(world['qualification_region']) is not bool:
            raise ValueError('EXPLICIT_WORLD_SCHEMA')
        for key in fields - {'id', 'qualification_region'}:
            value = world[key]
            if type(value) not in {int, float} or not math.isfinite(value) or value < 0:
                raise ValueError('FINITE_NONNEGATIVE_WORLD_VALUE')
        for key in ['trust', 'rival_trust', 'arrival', 'revision_probability', 'dispute_probability', 'self_service_trust']:
            if not 0 <= world[key] <= 1:
                raise ValueError('PROBABILITY_RANGE')
        if world['value_low'] > world['value_high'] or type(world['settlement_delay']) is not int or not 0 <= world['settlement_delay'] <= 25:
            raise ValueError('WORLD_RANGE_OR_TIMING')
    return policy


def keyed_draw(seed, cycle, buyer, channel):
    if type(seed) is not int or type(cycle) is not int or not isinstance(channel, str):
        raise ValueError('KEYED_DRAW_SCHEMA')
    raw = hashlib.sha256(canonical([seed, cycle, str(buyer), channel])).digest()
    return int.from_bytes(raw[:8], 'big') / 2**64


def onboarding_quote(arm, world, buyer_state, policy):
    if type(arm.get('corrected_onboarding')) is not bool or type(buyer_state.get('onboarded')) is not bool:
        raise ValueError('EXPLICIT_ONBOARDING_STATE_REQUIRED')
    new = not buyer_state['onboarded']
    return {'agent_expense': (policy['agent_onboarding_autonomous'] if arm['corrected_onboarding'] else policy['agent_onboarding_original']) if new else 0,
            'customer_friction_usd': (world['switching'] if arm['corrected_onboarding'] else world['original_switching']) if new else 0.,
            'external_fee': policy['external_onboarding_fee'] if new else 0,
            'timing': 'Incurred once on first consented, technically accepted service; state persists after refund; no charge on repeat.'}


def public_seller_observation(world, buyers, snapshot):
    return {'population_value_interval_assumption': [world['value_low'], world['value_high']],
            'buyer_public_history': [{'id': b['id'], 'purchases': b['purchases'], 'onboarded': b['onboarded'], 'trust': b['trust']} for b in buyers],
            'seller_cash': snapshot['cash'], 'seller_unrestricted_earned': snapshot['unrestrictedEarned'],
            'supplier_terms_multiplier': world['supplier_multiplier'],
            'information_limit': 'No private realized values, budgets, future arrival/revision/dispute draws or reservation prices.'}


def select_contribution_candidate(evaluations, policy):
    if not isinstance(evaluations, list) or not evaluations:
        raise ValueError('CANDIDATE_PAYOFF_CURVE_REQUIRED')
    feasible = []
    for item in evaluations:
        for key in ['expected_complete_profit', 'expected_available_cash', 'cash_survival_fraction', 'win_probability']:
            v = item.get(key)
            if type(v) not in {int, float} or not math.isfinite(v):
                raise ValueError('FINITE_CANDIDATE_PAYOFF_REQUIRED')
        candidate = item.get('price_multiplier_bps')
        allowed = policy['price_multipliers_bps'] + [c['id'] for c in policy['adaptive_price_candidates']]
        if candidate not in allowed or type(item.get('payable_breach_runs')) is not int or item['payable_breach_runs'] < 0 or not 0 <= item['cash_survival_fraction'] <= 1 or not 0 <= item['win_probability'] <= 1:
            raise ValueError('FROZEN_FEASIBLE_CANDIDATE_REQUIRED')
        if item['cash_survival_fraction'] == 1. and item['payable_breach_runs'] == 0 and item['expected_available_cash'] >= 0:
            feasible.append(item)
    no_bid = {'price_multiplier_bps': None, 'expected_complete_profit': -policy['setup_cost'],
              'expected_available_cash': policy['opening'] - policy['setup_cost'] - policy['working'],
              'cash_survival_fraction': float(policy['opening'] >= policy['setup_cost'] + policy['working']), 'win_probability': 0., 'payable_breach_runs': 0,
              'scope': 'NoBid preserves cash; already incurred full campaign qualification/setup remains charged.'}
    if no_bid['cash_survival_fraction'] == 1.:
        feasible.append(no_bid)
    if not feasible:
        raise ValueError('NO_LIQUIDITY_FEASIBLE_POLICY')
    selected = max(feasible, key=lambda x: (x['expected_complete_profit'], x['expected_available_cash']))
    return {'selected_multiplier_bps': selected['price_multiplier_bps'], 'selected_payoff': selected,
            'candidate_curve': evaluations + [no_bid],
            'seller_grid_profitable_deviation_residual': max(x['expected_complete_profit'] for x in feasible) - selected['expected_complete_profit'],
            'information': 'Only frozen exploration distributions; no confirmation outcome or individual private reservation value.',
            'solution_scope': 'Conditional finite-grid expected-contribution optimum with cash constraints; not Nash equilibrium or a global continuous-price optimum.'}


def price_quote(policy, candidate, onboarded):
    if type(onboarded) is not bool:
        raise ValueError('EXPLICIT_PUBLIC_ONBOARDING_STATE_REQUIRED')
    if candidate is None:
        return 0
    if type(candidate) is int:
        if candidate not in policy['price_multipliers_bps']:
            raise ValueError('UNFROZEN_PRICE_CANDIDATE')
        bps = candidate
    else:
        matches = [c for c in policy['adaptive_price_candidates'] if c['id'] == candidate]
        if len(matches) != 1:
            raise ValueError('UNFROZEN_PRICE_CANDIDATE')
        bps = matches[0]['repeat_bps' if onboarded else 'first_bps']
    human = policy['human_benchmark'] - (policy['human_onboarding_component'] if onboarded else 0)
    return max(0, human) * bps // 10000


def execute_work_batch(root, jobs, selected, commitment_sequence, funding, corrected_onboarding=False):
    from commercial.service import deliver, digest as file_digest
    from commercial.service_verifier import audit_delivery
    receipts = []
    with tempfile.TemporaryDirectory(prefix='commercial010-executed-delivery-') as tmp:
        for ident in selected:
            job = jobs[ident]['job']
            from .ledger import read_bound
            order = read_bound(root, job['input'], job['input_sha256'])
            if corrected_onboarding:
                from commercial.onboarding import prepare_order
                exports = Path(root) / 'campaign/commercial-010/onboarding/executed-001' / ident / 'synthetic-exports'
                prepared = prepare_order(exports / 'contract.json', exports / 'invoices.csv', exports / 'payments.csv')
                if canonical(prepared) != canonical(order):
                    raise ValueError('AUTONOMOUS_ONBOARDING_CHANGED_ORDER')
                order = prepared
            target = Path(tmp) / ident
            wall, cpu = time.monotonic(), time.process_time()
            actual = deliver(order, target)
            receipt = audit_delivery(order, actual)
            if receipt['accepted'] is not True or file_digest(target / 'reconciliation.json') != job['artifact_sha256']:
                raise ValueError('POST_COMMITMENT_ACTUAL_PRODUCTION_FAILED')
            receipts.append({'job_id': ident, 'input_sha256': job['input_sha256'],
                             'produced_artifact_sha256': file_digest(target / 'reconciliation.json'),
                             'exceptions_csv_sha256': file_digest(target / 'exceptions.csv'),
                             'fresh_checker_receipt': receipt, 'funding_scope': funding,
                             'native_commitment_sequence': commitment_sequence, 'autonomous_csv_onboarding_executed': corrected_onboarding,
                             'production_cpu_seconds': time.process_time() - cpu,
                             'production_wall_seconds': time.monotonic() - wall,
                             'execution': 'Actual deterministic service deliver() executed after funding decision; same qualified input, not fresh independent scientific confirmation. Temporary production copies removed; identical source-bound deliverable is retained in cohort.'})
    return receipts


def _outside(value, human_price):
    return max(0., .97 * value - human_price)


def competitor_response(values, own_price, own_trust, rival_trust, rival_cost, human_price, delivery_premium=0, self_service_cost=0, self_service_trust=0, own_onboarding=0, rival_switching=0):
    options = []
    for quality in [.90, .95, .99]:
        unit_cost = rival_cost * (1 + (quality - .90) * 5)
        for price in [human_price * fraction for fraction in [.10, .20, .35, .50, .65, .80, .95, 1.05, 1.20]] + [unit_cost * 1.05]:
            choices = sum(quality * rival_trust * v - price - rival_switching + delivery_premium > max(own_trust * .99 * v - own_price - own_onboarding + delivery_premium, _outside(v, human_price), .99 * self_service_trust * v - self_service_cost + delivery_premium, 0) for v in values)
            payoff = (price - unit_cost) * choices
            options.append((payoff, price, quality, choices, unit_cost))
    best = max(options, key=lambda x: (x[0], x[1]))
    return {'price': best[1], 'quality': best[2], 'expected_payoff': best[0], 'estimated_customers': best[3],
            'cost_per_job': best[4], 'grid_best_response_residual': max(x[0] for x in options) - best[0],
            'scope': 'Noisy-value finite-grid response includes own, human, DIY and abstention utilities with public onboarding/switching assumptions. Private budgets and exact values remain uncertain; zero modeled-grid residual is not a Nash equilibrium certificate'}


def run_world(*, root, manifest, policy, world, seed, multiplier, directory, persist=True, arm=None):
    validate_policy(policy)
    arm = policy['arms'][0] if arm is None else arm
    if arm not in policy['arms'] or world not in policy['worlds'] or seed not in policy['exploration_seeds'] + policy['confirmation_seeds'] + policy['sensitivity_seeds'] or multiplier is not None and multiplier not in policy['price_multipliers_bps'] + [c['id'] for c in policy['adaptive_price_candidates']]:
        raise ValueError('UNFROZEN_WORLD_SEED_OR_PRICE')
    jobs = load_jobs(root, manifest)
    eligible = sorted(jobs)
    needed = policy['cycles'] * policy['jobs_per_cycle']
    if len(eligible) < needed:
        raise ValueError('INSUFFICIENT_UNIQUE_EXECUTED_COHORT')
    eligible = eligible[:needed]
    rng = random.Random(seed)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    contract = 'commercial010/' + digest({'policy': policy, 'world': world, 'seed': seed, 'multiplier': multiplier, 'manifest': digest(manifest), 'arm': arm})
    tape = TapeExchange(directory / 'exchange.sqlite', root=root, manifest=manifest,
                        opening=policy['opening'], working=policy['working'], contract=contract)
    price = price_quote(policy, multiplier, False)
    human = policy['human_benchmark'] / MICRO
    own_price = price / MICRO
    buyers = [{'id': 'SIM-buyer-' + str(i), 'trust': world['trust'], 'purchases': 0,
               'value': world['value_low'] + (world['value_high'] - world['value_low']) * keyed_draw(seed, -1, i, 'value'), 'last': None, 'onboarded': False,
               'budget': policy['cycles'] * human * 1.5}
              for i in range(policy['jobs_per_cycle'])]
    events, cycles, stop = [], [], None
    failed_jobs = len(manifest['jobs']) - len(jobs)
    attempts = manifest.get('attempts', [])
    revised_attempts = max(0, len(attempts) - len(manifest['jobs']))
    # Rejected jobs are charged just like accepted ones. Extra failed/revised
    # attempts receive one full per-job envelope, deliberately conservative.
    cost_units = len(manifest['jobs']) + revised_attempts
    all_job_cost = policy['per_job_cost'] * cost_units
    tranche = (all_job_cost + policy['cycles'] - 1) // policy['cycles']
    previous_taxable = 0
    cumulative_tax = 0
    try:
        tape.execute('cost', {'id': 'complete-campaign-setup', 'amount': policy['setup_cost']}, 0)
        for cycle in range(policy['cycles'] if multiplier is not None else 0):
            day = cycle * 30 + 1
            selected = eligible[cycle * policy['jobs_per_cycle']:(cycle + 1) * policy['jobs_per_cycle']]
            active_buyers = buyers[:len(selected)]
            acquisition = sum(policy['acquisition_repeat'] if b['purchases'] else policy['acquisition_new'] for b in active_buyers)
            # Supplier chooses scarcity markup in response to its utilization;
            # base factor is a conditional exogenous cost state. This is a
            # bounded pricing heuristic, not an optimized supplier equilibrium.
            utilization = len(selected) / policy['jobs_per_cycle']
            supplier_factor = world['supplier_multiplier'] * (1 + .05 * utilization)
            production_cost = int(math.ceil(tranche * supplier_factor))
            base_cycle_budget = production_cost + acquisition + len(selected) * policy['support_per_sale']
            onboarding_cap = sum(onboarding_quote(arm, world, b, policy)['agent_expense'] + onboarding_quote(arm, world, b, policy)['external_fee'] for b in active_buyers)
            cycle_budget = base_cycle_budget + onboarding_cap
            before = tape.ex.snapshot()
            forecast_prices = [price_quote(policy, multiplier, b['onboarded']) for b in active_buyers]
            own_price = sum(forecast_prices) / len(forecast_prices) / MICRO
            human = sum(policy['human_benchmark'] - (policy['human_onboarding_component'] if b['onboarded'] else 0) for b in active_buyers) / len(active_buyers) / MICRO
            forecast_value = (world['value_low'] + world['value_high']) / 2
            forecast_trust = sum(b['trust'] for b in active_buyers) / len(active_buyers)
            forecast_rival = competitor_response([forecast_value] * len(active_buyers), own_price, forecast_trust, world['rival_trust'], world['rival_cost'], human, world['delivery_premium'], world['self_service_cost'], world['self_service_trust'],
                                                  sum(onboarding_quote(arm, world, b, policy)['customer_friction_usd'] for b in active_buyers) / len(active_buyers),
                                                  world['switching'] * sum(b['onboarded'] for b in active_buyers) / len(active_buyers))
            forecast_participants = 0
            forecast_offer_margins = []
            for b in active_buyers:
                b_offer = price_quote(policy, multiplier, b['onboarded'])
                b_human = (policy['human_benchmark'] - (policy['human_onboarding_component'] if b['onboarded'] else 0)) / MICRO
                own = b['trust'] * .99 * forecast_value - b_offer / MICRO - onboarding_quote(arm, world, b, policy)['customer_friction_usd'] + world['delivery_premium']
                rival_utility = world['rival_trust'] * forecast_rival['quality'] * forecast_value - forecast_rival['price'] - (world['switching'] if b['purchases'] else 0) + world['delivery_premium']
                diy = .99 * world['self_service_trust'] * forecast_value - world['self_service_cost'] + world['delivery_premium']
                forecast_chooses = own >= max(0, rival_utility, _outside(forecast_value, b_human), diy)
                forecast_participants += int(forecast_chooses)
                if forecast_chooses:
                    forecast_offer_margins.append(b_offer * (1 - policy['payment_bps'] / 10000) - policy['payment_fixed'])
            expected_sales = forecast_participants * world['arrival'] * (1 - world['dispute_probability'])
            expected_net_value = int(sum(forecast_offer_margins) * world['arrival'] * (1 - world['dispute_probability']) - cycle_budget)
            observation = public_seller_observation(world, active_buyers, before)
            funding = 'BOOTSTRAP_SEED_OR_REMAINING_LIQUIDITY'
            if before['unrestrictedEarned'] >= cycle_budget and before['profit'] > 0 and expected_net_value <= 0:
                stop = 'PRESERVE_EARNINGS_NEGATIVE_EXPECTED_MARGINAL_RETURN'
                break
            if before['unrestrictedEarned'] >= cycle_budget and before['profit'] > 0 and expected_net_value > 0:
                intent = digest({'cycle': cycle, 'jobs': selected, 'policy': digest(policy)})
                tape.execute('reserve', {'id': 'delivery-capacity-' + str(cycle), 'amount': cycle_budget,
                                        'expected_net_value': expected_net_value, 'intent_sha256': intent}, day)
                funding = 'PRIOR_UNRESTRICTED_SIMULATED_EARNINGS'
            else:
                if before['available'] < cycle_budget:
                    stop = 'LIQUIDITY_BOUNDARY_BEFORE_COMMITMENT'
                    break
                tape.execute('cost', {'id': 'cohort-production-acquisition-support-' + str(cycle), 'amount': base_cycle_budget}, day)
            work_receipts = execute_work_batch(root, jobs, selected, len(tape.actions) - 1, funding, arm['corrected_onboarding'])
            if funding == 'PRIOR_UNRESTRICTED_SIMULATED_EARNINGS':
                tape.execute('finish', {'id': 'delivery-capacity-' + str(cycle), 'amount': base_cycle_budget,
                                       'artifact_sha256': digest([jobs[x]['job'] for x in selected])}, day)
            information = [b['value'] * (.9 + .2 * keyed_draw(seed, cycle, b['id'], 'rival_information')) for b in active_buyers]
            rival = competitor_response(information, own_price, sum(b['trust'] for b in active_buyers) / len(active_buyers), world['rival_trust'], world['rival_cost'], human, world['delivery_premium'], world['self_service_cost'], world['self_service_trust'],
                                                  sum(onboarding_quote(arm, world, b, policy)['customer_friction_usd'] for b in active_buyers) / len(active_buyers),
                                                  world['switching'] * sum(b['onboarded'] for b in active_buyers) / len(active_buyers))
            accepted_count, collected_count, returns = 0, 0, 0
            decisions = []
            for j, buyer in zip(selected, active_buyers):
                ident = 'SIM-order-' + str(cycle) + '-' + j
                price = price_quote(policy, multiplier, buyer['onboarded'])
                own_price = price / MICRO
                buyer_human = (policy['human_benchmark'] - (policy['human_onboarding_component'] if buyer['onboarded'] else 0)) / MICRO
                arrival_draw = keyed_draw(seed, cycle, buyer['id'], 'arrival')
                arrival = arrival_draw < world['arrival'] * (.97 if buyer['purchases'] else 1.)
                onboarding = onboarding_quote(arm, world, buyer, policy)
                switching = onboarding['customer_friction_usd']
                own_utility = buyer['trust'] * .99 * buyer['value'] - own_price - switching + world['delivery_premium']
                rival_utility = world['rival_trust'] * rival['quality'] * buyer['value'] - rival['price'] - (world['switching'] if buyer['purchases'] else 0.) + world['delivery_premium']
                human_utility = _outside(buyer['value'], buyer_human)
                self_service_utility = .99 * world['self_service_trust'] * buyer['value'] - world['self_service_cost'] + world['delivery_premium']
                outside_utility = max(0., rival_utility, human_utility, self_service_utility)
                chooses = arrival and buyer['budget'] >= own_price and own_utility >= outside_utility and own_utility >= 0
                decision = {'job_id': j, 'buyer': buyer['id'], 'arrival': arrival, 'own_utility': own_utility,
                            'rival_utility': rival_utility, 'human_or_no_purchase_utility': human_utility,
                            'self_service_utility': self_service_utility, 'self_service_scope': 'Free code or conventional software; price/time cost and user-execution trust are conditional assumptions, not a measured inferiority claim',
                            'outside_utility': outside_utility, 'participates': chooses, 'repeat_customer': buyer['purchases'] > 0,
                            'arrival_draw': arrival_draw, 'revision_draw': keyed_draw(seed, cycle, buyer['id'], 'revision'), 'dispute_draw': keyed_draw(seed, cycle, buyer['id'], 'dispute'),
                            'onboarding': onboarding, 'human_complete_cost_anchor': int(round(buyer_human * MICRO)), 'price': price, 'conditional_fast_delivery_utility_premium_usd': world['delivery_premium'], 'onboarding_usd': switching, 'buyer_budget_before_usd': buyer['budget'], 'information': 'Realized value is latent; buyer uses its own expected utility; rival sees noisy proxy'}
                if chooses:
                    tape.execute('wallet', {'buyer': ident + '-wallet', 'amount': price}, day)
                    tape.execute('offer', {'id': ident, 'buyer': ident + '-wallet', 'price': price, 'job_id': j, 'deadline': day + 14}, day)
                    for action in ['consent', 'fund', 'prepare']:
                        tape.execute('event', {'id': ident, 'event_id': ident + '-' + action, 'action': action}, day)
                    accepted_count += 1
                    if not buyer['onboarded']:
                        if onboarding['agent_expense']:
                            tape.execute('cost', {'id': buyer['id'] + '-agent-onboarding', 'amount': onboarding['agent_expense']}, day)
                        if onboarding['external_fee']:
                            tape.execute('cost', {'id': buyer['id'] + '-external-onboarding-fee', 'amount': onboarding['external_fee']}, day)
                        buyer['onboarded'] = True
                    payment_fee = (price * policy['payment_bps'] + 9999) // 10000 + policy['payment_fixed']
                    tape.execute('cost', {'id': ident + '-payment-fee', 'amount': payment_fee}, day)
                    revised = keyed_draw(seed, cycle, buyer['id'], 'revision') < world['revision_probability']
                    if revised:
                        tape.execute('cost', {'id': ident + '-extra-revision', 'amount': policy['per_job_cost'] // 2}, day)
                    dispute = keyed_draw(seed, cycle, buyer['id'], 'dispute') < world['dispute_probability']
                    settlement_day = day + world['settlement_delay']
                    # All same-day order decisions occur before processing their
                    # settlement queue; this preserves global event time.
                    events.append({'id': ident, 'buyer': buyer, 'settlement_day': settlement_day,
                                   'dispute': dispute or settlement_day > day + 14,
                                   'revised': revised, 'decision': decision})
                decisions.append(decision)
            pending = [e for e in events if e['decision'].get('processed') is not True]
            for e in sorted(pending, key=lambda x: x['settlement_day']):
                now = e['settlement_day']
                if e['dispute']:
                    tape.execute('event', {'id': e['id'], 'event_id': e['id'] + '-refund', 'action': 'refund'}, now)
                    e['buyer']['trust'] = max(0., e['buyer']['trust'] - .1)
                    e['decision']['outcome'] = 'REFUNDED_DISPUTE_OR_DEADLINE'
                else:
                    tape.execute('event', {'id': e['id'], 'event_id': e['id'] + '-release', 'action': 'release'}, now)
                    returns += int(e['buyer']['purchases'] > 0)
                    e['buyer']['purchases'] += 1
                    e['buyer']['budget'] -= e['decision']['price'] / MICRO
                    e['buyer']['trust'] = min(.995, e['buyer']['trust'] + .003)
                    e['decision']['outcome'] = 'SIMULATED_COLLECTED'
                    collected_count += 1
                e['decision']['processed'] = True
            taxable = max(0, tape.ex.snapshot()['profit'] + cumulative_tax)
            tax = max(0, taxable - previous_taxable) * policy['tax_bps'] // 10000
            if tax:
                tape.execute('cost', {'id': 'conditional-tax-provision-' + str(cycle), 'amount': tax}, day + 25)
            cumulative_tax += tax
            previous_taxable = max(previous_taxable, taxable)
            after = tape.ex.snapshot()
            cycles.append({'cycle': cycle, 'day': day, 'jobs': selected, 'funding': funding,
                           'budget': cycle_budget, 'charged_base_budget': base_cycle_budget, 'onboarding_cap': onboarding_cap, 'seller_public_observation': observation, 'forecast_expected_net_value': expected_net_value, 'forecast_scope': 'Bounded midpoint-distribution participation forecast; no private realized buyer value or forced sale', 'actual_post_commitment_work': work_receipts, 'production_rejected_rework_allocation': production_cost,
                           'acquisition': acquisition, 'supplier_factor': supplier_factor,
                           'supplier_rule': '5% scarcity markup at full batch utilization, on exogenous world term',
                           'rival': rival, 'decisions': decisions, 'accepted': accepted_count,
                           'collected': collected_count, 'repeat_deliveries': returns, 'before': before, 'after': after})
        exported = tape.export()
    finally:
        tape.close()
    checked = audit(exported, root=root, manifest=manifest, expected_actions_sha256=exported['actions_sha256'])
    summary = checked['summary']
    paid = sum(c['collected'] for c in cycles)
    earned = sum(c['funding'] == 'PRIOR_UNRESTRICTED_SIMULATED_EARNINGS' and c['collected'] > 0 for c in cycles)
    repeats = sum(b['purchases'] > 1 for b in buyers)
    go = (len(cycles) == policy['cycles'] and paid >= policy['minimum_paid_jobs'] and
          earned >= policy['minimum_earned_cycles'] and repeats >= policy['minimum_repeat_buyers'] and
          summary['profit'] > 0 and summary['unrestrictedEarned'] > 0 and summary['payables'] == 0 and
          summary['custodyRestricted'] == 0 and not summary['investmentStopped'])
    result = {'schema': 'agi-alpha/commercial010-world/v1', 'scope': 'SIMULATED', 'world': world['id'],
              'seed': seed, 'arm': arm, 'price_multiplier_bps': multiplier, 'first_price': price_quote(policy, multiplier, False), 'repeat_price': price_quote(policy, multiplier, True), 'price': price_quote(policy, multiplier, False),
              'policy_sha256': digest(policy), 'cohort_sha256': digest(manifest), 'ledger': exported,
              'cycles': cycles, 'paid_jobs': paid, 'earned_funded_cycles': earned, 'repeat_buyers': repeats,
              'cohort_jobs': len(manifest['jobs']), 'failed_jobs': failed_jobs, 'extra_failed_attempts': revised_attempts,
              'charged_cost_units': cost_units, 'complete_cost_model': policy['cost_basis'],
              'conditional_simulated_go': go, 'stop': 'NO_BID_NEGATIVE_EXPECTED_CONTRIBUTION' if multiplier is None else stop,
              'actual_collections': 0, 'actual_profit': None,
              'terminal_obligations': policy['terminal_obligations'],
              'human_matched_accepted_cost': sum(d['human_complete_cost_anchor'] for c in cycles for d in c['decisions'] if d.get('outcome') == 'SIMULATED_COLLECTED'),
              'potential_productivity_savings_hypothetical': max(0, sum(d['human_complete_cost_anchor'] for c in cycles for d in c['decisions'] if d.get('outcome') == 'SIMULATED_COLLECTED') - summary['expenses']),
              'captured_simulated_surplus': summary['profit'],
              'customer_discount_transfer_vs_human_scenario': sum(d['human_complete_cost_anchor'] for c in cycles for d in c['decisions'] if d.get('outcome') == 'SIMULATED_COLLECTED') - summary['revenue'],
              'available_earned_surplus': summary['unrestrictedEarned'],
              'reinvested_earned': sum(int(x['actual']) for x in checked['investments'] if x['state'] == 'complete')}
    if persist:
        (directory / 'RESULT.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return result


def aggregate(results):
    if not results:
        raise ValueError('NONEMPTY_RESULT_COHORT_REQUIRED')
    profits = sorted(x['ledger']['summary']['profit'] for x in results)
    n = len(results)
    snapshots = [x['ledger']['summary'] for x in results]
    survival = [s['cash'] >= s['payables'] + s['custodyReserve'] + s['tailReserve'] + s['workingCapital'] and s['payables'] == 0 for s in snapshots]
    opportunities = sum(sum(len(c['jobs']) for c in x['cycles']) for x in results)
    return {'runs': n, 'go_runs': sum(x['conditional_simulated_go'] for x in results),
            'go_fraction': sum(x['conditional_simulated_go'] for x in results) / n,
            'expected_complete_profit': sum(profits) / n,
            'expected_available_cash': sum(s['available'] for s in snapshots) / n,
            'expected_unrestricted_earned': sum(s['unrestrictedEarned'] for s in snapshots) / n,
            'cash_survival_fraction': sum(survival) / n,
            'payable_breach_runs': sum(s['payables'] > 0 or s['investmentStopped'] for s in snapshots),
            'win_probability': sum(x['paid_jobs'] for x in results) / opportunities if opportunities else 0.,
            'mean_paid_jobs': sum(x['paid_jobs'] for x in results) / n,
            'mean_earned_funded_cycles': sum(x['earned_funded_cycles'] for x in results) / n,
            'mean_repeat_buyers': sum(x['repeat_buyers'] for x in results) / n,
            'mean_reinvested_earned': sum(x['reinvested_earned'] for x in results) / n,
            'profit_min': profits[0], 'profit_median': profits[n // 2], 'profit_max': profits[-1],
            'paid_jobs_range': [min(x['paid_jobs'] for x in results), max(x['paid_jobs'] for x in results)],
            'earned_cycles_range': [min(x['earned_funded_cycles'] for x in results), max(x['earned_funded_cycles'] for x in results)],
            'scope': 'Equally weighted finite conditional seeded model outcomes, not estimated real customer demand or observed commercial probability'}


def run_campaign(*, root, manifest_path, policy_path, output, expected_manifest_sha256, expected_policy_sha256):
    root, output = Path(root), Path(output)
    if output.exists() or output.is_symlink() or any(x.is_symlink() for x in output.absolute().parents):
        raise FileExistsError(output)
    raw_manifest, raw_policy = Path(manifest_path).read_bytes(), Path(policy_path).read_bytes()
    if hashlib.sha256(raw_manifest).hexdigest() != expected_manifest_sha256 or hashlib.sha256(raw_policy).hexdigest() != expected_policy_sha256:
        raise ValueError('EXTERNAL_FROZEN_INPUT_IDENTITY_REQUIRED')
    manifest, policy = strict_json(raw_manifest), validate_policy(strict_json(raw_policy))
    output.mkdir(parents=True)
    region = [w for w in policy['worlds'] if w['qualification_region']]
    candidates = policy['price_multipliers_bps'] + [c['id'] for c in policy['adaptive_price_candidates']]
    selections, explored_by_onboarding = {}, {}
    for corrected in [False, True]:
        arm = next(a for a in policy['arms'] if a['strategic_pricing'] and a['corrected_onboarding'] is corrected)
        evaluated = []
        for candidate in candidates:
            runs = []
            for world in region:
                for seed in policy['exploration_seeds']:
                    runs.append(run_world(root=root, manifest=manifest, policy=policy, world=world, seed=seed,
                                          multiplier=candidate, arm=arm,
                                          directory=output / 'exploration' / arm['id'] / str(candidate) / world['id'] / str(seed)))
            evaluated.append({'price_multiplier_bps': candidate, 'worlds': {w['id']: aggregate([r for r in runs if r['world'] == w['id']]) for w in region}, **aggregate(runs)})
        selections[arm['id']] = select_contribution_candidate(evaluated, policy)
        explored_by_onboarding[str(corrected)] = evaluated
    selection = {'schema': 'agi-alpha/commercial010-factorial-price-freeze/v2', 'scope': 'SIMULATED',
                 'selections': selections, 'exploration': explored_by_onboarding,
                 'policy_sha256': expected_policy_sha256, 'cohort_sha256': expected_manifest_sha256,
                 'confirmation_seeds': policy['confirmation_seeds'], 'adaptation_after_confirmation': False,
                 'objective': policy['selection_rule']}
    (output / 'PRICE_FREEZE.json').write_text(json.dumps(selection, indent=2) + '\n')
    arms, all_runs = {}, {}
    for arm in policy['arms']:
        candidate = selections[arm['id']]['selected_multiplier_bps'] if arm['strategic_pricing'] else 10000 - policy['initial_discount_bps']
        runs, worlds = [], {}
        for world in policy['worlds']:
            wruns = []
            for seed in policy['confirmation_seeds']:
                r = run_world(root=root, manifest=manifest, policy=policy, world=world, seed=seed,
                              multiplier=candidate, arm=arm,
                              directory=output / 'confirmation' / arm['id'] / world['id'] / str(seed))
                wruns.append(r)
                runs.append(r)
            worlds[world['id']] = aggregate(wruns)
        all_runs[arm['id']] = runs
        regional = [r for r in runs if any(w['id'] == r['world'] and w['qualification_region'] for w in region)]
        summary = aggregate(regional)
        qualifies = summary['expected_complete_profit'] > 0 and summary['cash_survival_fraction'] == 1. and summary['payable_breach_runs'] == 0 and summary['mean_earned_funded_cycles'] >= policy['minimum_earned_cycles'] and summary['mean_repeat_buyers'] >= policy['minimum_repeat_buyers']
        arms[arm['id']] = {'arm': arm, 'selected_price_policy': candidate,
                          'first_price': price_quote(policy, candidate, False), 'repeat_price': price_quote(policy, candidate, True),
                          'worlds': worlds, 'qualification_region': summary, 'conditional_simulated_go': qualifies}
    contrasts = {}
    for label, left, right in [('onboarding_at_fixed_price', 'fixed_autonomous_onboarding', 'fixed_original'),
                               ('strategy_at_original_onboarding', 'strategic_original', 'fixed_original'),
                               ('onboarding_at_strategic_price', 'strategic_autonomous_onboarding', 'strategic_original'),
                               ('both_vs_original', 'strategic_autonomous_onboarding', 'fixed_original')]:
        l = {(r['world'], r['seed']): r for r in all_runs[left]}
        r = {(x['world'], x['seed']): x for x in all_runs[right]}
        pairs = []
        for key in sorted(l):
            pairs.append({'world': key[0], 'seed': key[1],
                          'complete_profit_delta': l[key]['ledger']['summary']['profit'] - r[key]['ledger']['summary']['profit'],
                          'paid_jobs_delta': l[key]['paid_jobs'] - r[key]['paid_jobs'],
                          'unrestricted_earned_delta': l[key]['available_earned_surplus'] - r[key]['available_earned_surplus'],
                          'earned_reinvestment_delta': l[key]['reinvested_earned'] - r[key]['reinvested_earned']})
        contrasts[label] = {'left': left, 'right': right, 'pairs': pairs,
                            'mean_complete_profit_delta': sum(p['complete_profit_delta'] for p in pairs) / len(pairs),
                            'scope': 'Paired same cohort, latent values, arrivals, revisions, disputes, horizons and acquisition policy; endogenous purchases, trust, price and liquidity may diverge.'}
    best = arms['strategic_autonomous_onboarding']
    best_arm = next(a for a in policy['arms'] if a['id'] == 'strategic_autonomous_onboarding')
    sensitivity = {}
    cases = policy['sensitivity_cases'] + [{'id': 'friction_' + str(f), 'setup': policy['setup_cost'], 'per_job': policy['per_job_cost'], 'human': policy['human_benchmark'], 'friction': f} for f in [0, 5, 25, 50]]
    for case in cases:
        alternative = copy.deepcopy(policy)
        ratio = case['human'] / policy['human_benchmark']
        alternative.update(setup_cost=case['setup'], per_job_cost=case['per_job'], human_benchmark=case['human'],
                           human_onboarding_component=int(round(policy['human_onboarding_component'] * ratio)),
                           human_stages_hours_first={k: v * ratio for k, v in policy['human_stages_hours_first'].items()},
                           human_repeat_hours=policy['human_repeat_hours'] * ratio)
        if 'friction' in case:
            alternative['worlds'][0]['switching'] = case['friction']
        cruns = []
        for seed in policy['sensitivity_seeds']:
            cruns.append(run_world(root=root, manifest=manifest, policy=alternative, world=alternative['worlds'][0], seed=seed,
                                    multiplier=best['selected_price_policy'], arm=best_arm,
                                    directory=output / 'sensitivity' / case['id'] / str(seed)))
        sensitivity[case['id']] = {'conditions': case, **aggregate(cruns)}
    from .verdicts import verdicts
    result = {'schema': 'agi-alpha/commercial010-campaign/v2', 'scope': 'SIMULATED',
              'policy_file_sha256': expected_policy_sha256, 'cohort_file_sha256': expected_manifest_sha256,
              'arms': arms, 'paired_contrasts': contrasts, 'price_selection': selection, 'sensitivity': sensitivity,
              'worlds': best['worlds'], 'qualification_region': best['qualification_region'],
              'selected_price_multiplier_bps': best['selected_price_policy'], 'selected_price': best['first_price'],
              'conditional_simulated_go': best['conditional_simulated_go'],
              'verdicts': verdicts(simulated_go=best['conditional_simulated_go'], accepted_jobs=len(load_jobs(root, manifest)),
                                   positive_service=best['qualification_region']['expected_complete_profit'] > 0),
              'limits': ['Actual demand, willingness to pay, buyer attention friction, trust differentiation and source-exact provider bills remain unobserved.',
                         'Agent onboarding is autonomous machine work. Human comparator onboarding and all remaining stages are human labor, counted once per customer.',
                         'The four arms are new controlled conditional counterfactuals, not a rewrite of the preserved original zero-sales experiment.',
                         'Prices maximize finite-grid exploration mean complete profit with sustainable cash constraints. Win probability is endogenous; no target win-rate or perfect-win gate.',
                         'Repeated production and CSV intake execute after native funding commitments. Monetary resource envelopes and customer payments remain simulated.',
                         'No Nash equilibrium, continuous-price global optimum, observed revenue, causal invention benefit or Blue Sky enablement is claimed.']}
    (output / 'RESULT.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return result
