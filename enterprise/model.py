"""Bounded service enterprise using the existing protected exchange and action tape."""
from __future__ import annotations
import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import time
from commercial.ledger import TapeExchange, audit, canonical, digest, load_jobs, read_bound
from enterprise.pricing import optimize_price, optimize_bundle, utilities, probabilities

MICRO = 1_000_000

def money(value):
    return int(round(value * MICRO))


def draw(seed, cycle, buyer, channel):
    raw = hashlib.sha256(canonical(['enterprise011', seed, cycle, buyer, channel])).digest()
    return int.from_bytes(raw[:8], 'big') / 2**64


def default_policy():
    return {'schema': 'agi-alpha/enterprise011-policy/v1', 'scope': 'SIMULATED', 'currency': 'simulated-microUSD', 'nominal_price_vintage': '2026-10-30', 'exchange_rate': {'currency': 'USD', 'rate': 1, 'basis': 'single-currency experiment; no FX transaction'}, 'rounding': 'nearest microUSD for authored USD envelopes; integer ledger',
        'cycles': 24, 'capacity_per_cycle': 4, 'service_capacity_per_cycle': 2, 'customer_pool': 8, 'opening': money(5000), 'working': money(100), 'setup_cost': money(350), 'cost_multiplier': 1., 'payment_bps': 290, 'payment_fixed': money(.30), 'profit_tax_bps': 2000, 'sales_tax_bps': 0,
        'costs_usd': {'research_development_prequalification': 350, 'inference_tools_production': 1, 'independent_verification_corrections': .5, 'compute_storage_infrastructure': .25, 'delivery_support_obligation': .5, 'maintenance_failure_retry': .75, 'quote_acquisition': .5, 'autonomous_onboarding_once': .5, 'external_onboarding_fee': 0, 'bundle_coordination_once': 3},
        'cost_ranges_usd': {'setup': [200, 1500], 'per_attempt': [2, 8], 'autonomous_onboarding_once': [.01, 5], 'quote_acquisition': [.5, 8]},
        'cost_evidence': 'CONSERVATIVE_AUTHORED_ENVELOPES_NOT_MODEL_BILLS. Actual fixed deterministic service production and independent checking execute. No paid frontier-model inference is called. Setup includes all discovery, authored construction, rejected fixtures, initial prequalification and integration; per-attempt includes production/replay, verification, corrections, failed/unpaid work, storage, delivery, support, maintenance; acquisition charged on every exposed bid including losses. CPU runtime is not human task time. No human-review hour is inserted. Resource billing unavailable.',
        'human_services': {'reconciliation': {'loaded_hourly_usd': 34.75, 'stages_hours': {'research': .05, 'preparation_onboarding': .1, 'production': .2, 'verification': .1, 'correction': .05, 'ordering_support': .15}, 'tool_external_usd': 2}, 'kpi_variance': {'loaded_hourly_usd': 60, 'stages_hours': {'research': .05, 'preparation_onboarding': .1, 'production': .2, 'verification': .1, 'correction': .05, 'ordering_support': .15}, 'tool_external_usd': 2}, 'evidence_matrix': {'loaded_hourly_usd': 55, 'stages_hours': {'research': .05, 'preparation_onboarding': .1, 'production': .35, 'verification': .1, 'correction': .05, 'ordering_support': .15}, 'tool_external_usd': 2}},
        'human_evidence': 'Authored corresponding complete-service workload scenarios, not measured human times or observed selling prices. Loaded hourly values are bounded scenario proxies; ranges 0.5x–2x remain sensitivity inputs. No program runtime is converted into human effort. First-order complete work is0.65h for12-invoice reconciliation and10-metric variance,0.80h for8-requirement source matrix; preparation charged once/customer; repeats deduct0.10h onboarding. These small-fixture time hypotheses avoid applying multi-hour workloads to tiny delivered artifacts. Competent complete human delivery includes verification, correction, support and tools.',
        'thresholds': {'minimum_customers': 3, 'minimum_paid_jobs': 12, 'minimum_repeat_customers': 2, 'minimum_earned_funded_cycles': 2, 'minimum_region_success_fraction': .75},
        'qualification_regimes': ['ordinary', 'differentiation'], 'regime_weights': {'ordinary': .35, 'price_war': .30, 'differentiation': .20, 'correlated_shock': .15}, 'choice_models': ['logit', 'utility'], 'competitor_models': ['responsive', 'lagged'],
        'arms': [{'id': 'fixed_original', 'strategic_pricing': False, 'autonomous_onboarding': False}, {'id': 'fixed_autonomous', 'strategic_pricing': False, 'autonomous_onboarding': True}, {'id': 'strategic_original', 'strategic_pricing': True, 'autonomous_onboarding': False}, {'id': 'strategic_autonomous', 'strategic_pricing': True, 'autonomous_onboarding': True}],
        'bundle_enabled': True, 'dynamic_allocation': True, 'bundle_discount': .05,
        'regimes': {
            'ordinary': {'arrival_probability': .94, 'qualification_probability': .95, 'retention_probability': .94, 'reacquisition_probability': .25, 'collection_probability': .98, 'refund_probability': .02, 'supplier_multiplier': 1., 'supplier_outage_probability': .01, 'trust': .95, 'rival_trust': .95, 'urgency_value_hour': .5, 'our_hours': 2, 'rival_hours': 24, 'settlement_delay_days': 2, 'rival_cost_multiplier': 1.2, 'self_complete_cost_ratio': .85, 'temperature_ratio': .12, 'quote_cost_usd': .5, 'customer_friction_autonomous_usd': .5, 'customer_friction_original_usd': 2, 'demand_value_multiplier': 1.},
            'price_war': {'arrival_probability': .92, 'qualification_probability': .95, 'retention_probability': .85, 'reacquisition_probability': .25, 'collection_probability': .97, 'refund_probability': .03, 'supplier_multiplier': 1.3, 'supplier_outage_probability': .03, 'trust': .95, 'rival_trust': .97, 'urgency_value_hour': .05, 'our_hours': 2, 'rival_hours': 3, 'settlement_delay_days': 3, 'rival_cost_multiplier': .65, 'self_complete_cost_ratio': .45, 'temperature_ratio': .08, 'quote_cost_usd': .5, 'customer_friction_autonomous_usd': .5, 'customer_friction_original_usd': 2, 'demand_value_multiplier': 1.},
            'differentiation': {'arrival_probability': .96, 'qualification_probability': .97, 'retention_probability': .96, 'reacquisition_probability': .25, 'collection_probability': .99, 'refund_probability': .01, 'supplier_multiplier': 1.1, 'supplier_outage_probability': .01, 'trust': .97, 'rival_trust': .95, 'urgency_value_hour': 1., 'our_hours': 2, 'rival_hours': 24, 'settlement_delay_days': 2, 'rival_cost_multiplier': 1.4, 'self_complete_cost_ratio': .95, 'temperature_ratio': .1, 'quote_cost_usd': .5, 'customer_friction_autonomous_usd': .5, 'customer_friction_original_usd': 2, 'demand_value_multiplier': 1.},
            'correlated_shock': {'arrival_probability': .45, 'qualification_probability': .8, 'retention_probability': .5, 'reacquisition_probability': .15, 'collection_probability': .8, 'refund_probability': .18, 'supplier_multiplier': 2.5, 'supplier_outage_probability': .25, 'trust': .82, 'rival_trust': .9, 'urgency_value_hour': .05, 'our_hours': 8, 'rival_hours': 8, 'settlement_delay_days': 20, 'rival_cost_multiplier': .8, 'self_complete_cost_ratio': .5, 'temperature_ratio': .1, 'quote_cost_usd': .5, 'customer_friction_autonomous_usd': 12, 'customer_friction_original_usd': 25, 'demand_value_multiplier': .6}},
        'assumptions': ['All demand, budgets, arrival, switching, urgency, retention, competitor quality, rate limits, taxes and provider protection are disclosed conditional scenarios, not observed market estimates.', 'Churn persists with active=False; bounded independent channel reacquisition may restore a churned customer after an actual settled simulated order, with no repeated provider onboarding.', 'Buyer private value/budget and deterministic draws are not passed to seller pricing; seller uses public segment priors and its own transactional history only.', 'Turnaround2h/24h/48h are explicitly authored SLA waiting times, never labor hours. Ordinary segment values 2h complete delivery versus competent 24h rival and 48h human; same scoped outcome and obligations. Price war removes most latency differentiation. Trust ranges overlap; actual checker evidence is required for our deliveries.', 'Native principal-plus-fee tail reserves remain restricted throughout horizon; seed capital may back reserves. Earned delivery funding and seed-independent reserve replacement are separate metrics.', 'Tax is a conditional 20% positive-profit provision paid in the simulation; sales-tax collection/remittance assumed zero for nonjurisdictional synthetic workload. No tax compliance or actual transaction is asserted.', 'Bundles are optional grouped three-service orders with total willingness-to-pay and component identities; a bundle replaces its component sale opportunities, never adds duplicate revenue. Context reuse reduces one-time provider onboarding across services but does not grant data access.']}


def validate_policy(policy):
    if not isinstance(policy, dict) or policy.get('schema') != 'agi-alpha/enterprise011-policy/v1' or policy.get('scope') != 'SIMULATED' or policy.get('currency') != 'simulated-microUSD':
        raise ValueError('ENTERPRISE_POLICY_SCOPE_REQUIRED')
    template = default_policy()
    if set(policy) != set(template):
        raise ValueError('EXACT_ENTERPRISE_POLICY_SCHEMA_REQUIRED')
    if not isinstance(policy['rounding'], str) or not isinstance(policy['nominal_price_vintage'], str) or policy['exchange_rate'] != template['exchange_rate']:
        raise ValueError('DECLARED_USD_UNITS_VINTAGE_AND_ROUNDING_REQUIRED')
    for key in ['cycles', 'capacity_per_cycle', 'service_capacity_per_cycle', 'customer_pool']:
        if type(policy.get(key)) is not int or not 1 <= policy[key] <= 1000:
            raise ValueError('BOUNDED_POSITIVE_OPERATING_LIMIT_REQUIRED')
    for key in ['opening', 'working', 'setup_cost', 'payment_fixed']:
        if type(policy.get(key)) is not int or not 0 <= policy[key] <= 10**12:
            raise ValueError('MICROUSD_INTEGER_REQUIRED')
    for key in ['payment_bps', 'profit_tax_bps', 'sales_tax_bps']:
        if type(policy.get(key)) is not int or not 0 <= policy[key] <= 10000:
            raise ValueError('BASIS_POINTS_REQUIRED')
    for key in ['bundle_enabled', 'dynamic_allocation']:
        if type(policy.get(key)) is not bool:
            raise ValueError('EXPLICIT_POLICY_BOOLEAN_REQUIRED')
    if type(policy.get('cost_multiplier')) not in {int, float} or not math.isfinite(policy['cost_multiplier']) or policy['cost_multiplier'] <= 0:
        raise ValueError('POSITIVE_COST_MULTIPLIER_REQUIRED')
    if type(policy['bundle_discount']) not in {int, float} or not math.isfinite(policy['bundle_discount']) or not 0 <= policy['bundle_discount'] <= .5:
        raise ValueError('BOUNDED_BUNDLE_DISCOUNT_REQUIRED')
    required_regimes = set(default_policy()['regimes'])
    if not isinstance(policy.get('regimes'), dict) or set(policy['regimes']) != required_regimes:
        raise ValueError('FOUR_DECLARED_REGIMES_REQUIRED')
    if policy['choice_models'] != template['choice_models'] or policy['competitor_models'] != template['competitor_models'] or policy['qualification_regimes'] != template['qualification_regimes']:
        raise ValueError('DECLARED_SUPPORTED_CHOICE_COMPETITOR_AND_REGION_MODELS_REQUIRED')
    if policy['arms'] != template['arms']:
        raise ValueError('DECLARED_MATCHED_FOUR_CONTROL_ARMS_REQUIRED')
    for name, regime in policy['regimes'].items():
        if not isinstance(regime, dict) or set(regime) != set(template['regimes'][name]):
            raise ValueError('EXACT_STRATEGIC_REGIME_SCHEMA_REQUIRED')
        for k, v in regime.items():
            if type(v) not in {int, float} or not math.isfinite(v) or v < 0 or k.endswith('probability') and v > 1:
                raise ValueError('FINITE_REGIME_VALUE_REQUIRED')
        if regime['temperature_ratio'] <= 0 or regime['supplier_multiplier'] <= 0 or any(regime[k] > 1 for k in ['trust', 'rival_trust']) or type(regime['settlement_delay_days']) is not int or regime['settlement_delay_days'] > 29:
            raise ValueError('INVALID_TRUST_OR_SETTLEMENT_RANGE')
    if not isinstance(policy['costs_usd'], dict) or set(policy['costs_usd']) != set(template['costs_usd']):
        raise ValueError('ALL_ENTERPRISE_COST_CATEGORIES_REQUIRED')
    if not isinstance(policy['human_services'], dict) or set(policy['human_services']) != set(template['human_services']):
        raise ValueError('ALL_EXECUTED_SERVICES_REQUIRE_HUMAN_COMPARATORS')
    if not isinstance(policy['thresholds'], dict) or set(policy['thresholds']) != set(template['thresholds']) or any(type(v) not in {int, float} or not math.isfinite(v) or v <= 0 for v in policy['thresholds'].values()) or policy['thresholds']['minimum_region_success_fraction'] > 1:
        raise ValueError('POSITIVE_PREDECLARED_THRESHOLDS_REQUIRED')
    if not isinstance(policy['regime_weights'], dict) or set(policy['regime_weights']) != required_regimes or any(type(v) not in {int, float} or not math.isfinite(v) or v < 0 for v in policy['regime_weights'].values()) or abs(sum(policy['regime_weights'].values()) - 1) > 1e-9:
        raise ValueError('NORMALIZED_DECLARED_REGIME_WEIGHTS_REQUIRED')
    for service in policy['human_services'].values():
        if not isinstance(service, dict) or set(service) != {'stages_hours', 'loaded_hourly_usd', 'tool_external_usd'}:
            raise ValueError('EXACT_HUMAN_SERVICE_SCHEMA_REQUIRED')
        if not isinstance(service['stages_hours'], dict) or set(service['stages_hours']) != set(template['human_services']['reconciliation']['stages_hours']) or any(type(v) not in {int, float} or not math.isfinite(v) or v < 0 for v in service['stages_hours'].values()):
            raise ValueError('COMPLETE_HUMAN_STAGE_MODEL_REQUIRED')
        if type(service['loaded_hourly_usd']) not in {int, float} or not math.isfinite(service['loaded_hourly_usd']) or service['loaded_hourly_usd'] <= 0 or type(service['tool_external_usd']) not in {int, float} or not math.isfinite(service['tool_external_usd']) or service['tool_external_usd'] < 0 or sum(service['stages_hours'].values()) <= service['stages_hours']['preparation_onboarding']:
            raise ValueError('FINITE_POSITIVE_HUMAN_COST_AND_REPEAT_WORK_REQUIRED')
    if not isinstance(policy['cost_ranges_usd'], dict) or set(policy['cost_ranges_usd']) != set(template['cost_ranges_usd']):
        raise ValueError('EXACT_COST_RANGE_SCHEMA_REQUIRED')
    for bounds in policy['cost_ranges_usd'].values():
        if not isinstance(bounds, list) or len(bounds) != 2 or any(type(v) not in {int, float} or not math.isfinite(v) or v < 0 for v in bounds) or bounds[0] > bounds[1]:
            raise ValueError('ORDERED_FINITE_COST_RANGE_REQUIRED')
    if any(type(v) not in {int, float} or not math.isfinite(v) or v < 0 for v in policy['costs_usd'].values()):
        raise ValueError('FULL_COST_SCHEMA_REQUIRED')
    return policy


def human_anchor(policy, service, onboarded):
    record = policy['human_services'][service]
    hours = sum(record['stages_hours'].values()) - (record['stages_hours']['preparation_onboarding'] if onboarded else 0)
    return hours * record['loaded_hourly_usd'] + record['tool_external_usd']


def seller_observation(policy, regime, service, history, *, autonomous=True):
    onboarded = bool(history['onboarded'])
    costs = policy['costs_usd']
    return {'anchor_usd': human_anchor(policy, service, onboarded), 'autonomous_cost_usd': sum(costs[x] for x in ['inference_tools_production', 'independent_verification_corrections', 'compute_storage_infrastructure', 'delivery_support_obligation', 'maintenance_failure_retry']) * regime['supplier_multiplier'] * policy['cost_multiplier'], 'onboarding_cost_usd': 0 if onboarded else costs['autonomous_onboarding_once'] * policy['cost_multiplier'], 'friction_usd': 0 if onboarded else regime['customer_friction_autonomous_usd' if autonomous else 'customer_friction_original_usd'], 'trust': history['trust'], 'rival_trust': regime['rival_trust'], 'urgency_value_hour': regime['urgency_value_hour'], 'repeat_probability': regime['retention_probability'], 'payment_fraction': policy['payment_bps'] / 10000, 'payment_fixed_usd': policy['payment_fixed'] / MICRO}


def run_world(root, manifest, policy, seed, regime, choice_model='logit', arm=None, output=None, *, competitor_model='responsive', persist=False):
    validate_policy(policy)
    if type(seed) is not int or seed < 0 or regime not in policy['regimes'] or choice_model not in policy['choice_models'] or competitor_model not in policy['competitor_models']:
        raise ValueError('DECLARED_WORLD_INPUT_REQUIRED')
    arm = copy.deepcopy(policy['arms'][-1] if arm is None else arm)
    if arm not in policy['arms']:
        raise ValueError('DECLARED_CONTROL_ARM_REQUIRED')
    world = copy.deepcopy(policy['regimes'][regime])
    world['quote_cost_usd'] = policy['costs_usd']['quote_acquisition'] * policy['cost_multiplier']
    jobs = load_jobs(root, manifest)
    if len(jobs) < policy['cycles'] * policy['capacity_per_cycle']:
        raise ValueError('INSUFFICIENT_UNIQUE_ACCEPTED_ARTIFACTS')
    by_service = {}
    for key, entry in sorted(jobs.items()):
        by_service.setdefault(entry['job']['service_id'], []).append(key)
    if set(by_service) != set(policy['human_services']):
        raise ValueError('EXACT_ADMITTED_SERVICE_SET_REQUIRED')
    output = Path(output) if output is not None else None
    if persist and output is None:
        raise ValueError('DURABLE_REPRESENTATIVE_OUTPUT_REQUIRED')
    if output is not None:
        output.mkdir(parents=True, exist_ok=False)
    temp = tempfile.TemporaryDirectory(prefix='enterprise011-world-')
    destination = output if output is not None else Path(temp.name)
    contract = 'enterprise011/' + digest({'policy': policy, 'manifest': manifest, 'seed': seed, 'regime': regime, 'choice': choice_model, 'arm': arm, 'competitor': competitor_model})
    exchange = TapeExchange(destination / 'exchange.sqlite', root=root, manifest=manifest, opening=policy['opening'], working=policy['working'], contract=contract, durable=persist)
    histories = {f'SIM-buyer-{i}': {'id': f'SIM-buyer-{i}', 'purchases': 0, 'onboarded': False, 'trust': world['trust'], 'services': [], 'last_purchase_cycle': None, 'active': True, 'reacquisitions': 0} for i in range(policy['customer_pool'])}
    private = {buyer: {'value_factor': 1.3 + 2.4 * draw(seed, -1, buyer, 'reservation'), 'budget_usd': 500 + 1500 * draw(seed, -1, buyer, 'budget')} for buyer in histories}
    cycles, consumed, prices, exceptions = [], set(), {}, []
    cost_receipts, counts = [], {'reachable': policy['customer_pool'], 'arrivals': 0, 'qualified': 0, 'exposed': 0, 'activated': 0, 'accepted': 0, 'settled': 0, 'refunded': 0, 'defaulted': 0, 'churn_events': 0, 'bundles_offered': 0, 'bundles_settled': 0, 'reacquisition_opportunities': 0, 'reacquired_customers': 0}
    setup = int(round(policy['setup_cost'] * policy['cost_multiplier']))
    previous_taxable, cumulative_tax = 0, 0
    stop = None
    start_wall, start_cpu = time.monotonic(), time.process_time()
    def charge(ident, amount, day, category):
        exchange.execute('cost', {'id': ident, 'amount': amount}, day)
        cost_receipts.append({'event': ident, 'category': category, 'amount': amount, 'currency': policy['currency'], 'evidence': 'AUTHORED_CONDITIONAL_ENVELOPE'})
    try:
        charge('enterprise-setup', setup, 0, 'complete_shared_setup_all_attempts')
        for cycle in range(policy['cycles']):
            day = cycle * 30 + 1
            before = exchange.ex.snapshot()
            available = [j for ids in by_service.values() for j in ids if j not in consumed]
            public_quotes = {}
            for service in by_service:
                baseline = {'onboarded': cycle > 0, 'trust': world['trust']}
                public = seller_observation(policy, world, service, baseline, autonomous=arm['autonomous_onboarding'])
                cache = digest([public, world, choice_model, arm['strategic_pricing'], competitor_model])
                if cache not in prices:
                    prices[cache] = optimize_price(public, world, choice_model, strategic=arm['strategic_pricing'], lagged=competitor_model == 'lagged')
                public_quotes[service] = prices[cache]
            positive_services = {service for service, quote in public_quotes.items() if quote['price'] is not None and quote['expected_immediate_contribution_per_opportunity'] > 0}
            if not positive_services:
                stop = 'NO_BID_NONPOSITIVE_EXPECTED_INCREMENTAL_RETURN_BEFORE_COMMITMENT'
                break
            available = [j for j in available if jobs[j]['job']['service_id'] in positive_services]
            if policy['dynamic_allocation']:
                available.sort(key=lambda j: (-public_quotes[jobs[j]['job']['service_id']]['expected_immediate_contribution_per_opportunity'], j))
            else:
                available.sort(key=lambda j: (int(jobs[j]['job'].get('ordinal', 0)), j))
            selected, service_slots = [], {}
            remaining_cycles = policy['cycles'] - cycle - 1
            required = []
            for service in by_service:
                remaining = [j for j in available if jobs[j]['job']['service_id'] == service]
                required.extend(remaining[:max(0, len(remaining) - remaining_cycles * policy['service_capacity_per_cycle'])])
            for job_id in required + available:
                service = jobs[job_id]['job']['service_id']
                if job_id not in selected and service_slots.get(service, 0) < policy['service_capacity_per_cycle']:
                    selected.append(job_id)
                    service_slots[service] = service_slots.get(service, 0) + 1
                    if len(selected) == policy['capacity_per_cycle']:
                        break
            bundle_intent = policy['bundle_enabled'] and cycle % 3 == 2 and len(by_service) <= policy['capacity_per_cycle']
            if bundle_intent:
                first_per_service = [next((j for j in available if jobs[j]['job']['service_id'] == service), None) for service in sorted(by_service)]
                grouped = first_per_service + [j for j in required if j not in first_per_service]
                if all(first_per_service) and len(grouped) <= policy['capacity_per_cycle']:
                    selected = grouped + [j for j in selected + available if j not in grouped][:policy['capacity_per_cycle'] - len(grouped)]
                else:
                    bundle_intent = False
            if not selected:
                stop = 'ARTIFACT_CAPACITY_BOUNDARY'
                break
            base_attempt = money(sum(policy['costs_usd'][k] for k in ['inference_tools_production', 'independent_verification_corrections', 'compute_storage_infrastructure', 'delivery_support_obligation', 'maintenance_failure_retry']) * world['supplier_multiplier'] * policy['cost_multiplier'])
            acquisition_each = money(policy['costs_usd']['quote_acquisition'] * policy['cost_multiplier'])
            bundle = bundle_intent and len({jobs[j]['job']['service_id'] for j in selected[:3]}) == 3
            bundle_plan, group_publics, group_quotes = None, [], []
            if bundle:
                group_buyer = f'SIM-buyer-{(cycle * 2) % policy["customer_pool"]}'
                group_history = histories[group_buyer]
                group_publics, group_quotes = [], []
                for grouped_slot, grouped_job in enumerate(selected[:3]):
                    grouped_service = jobs[grouped_job]['job']['service_id']
                    grouped_context = dict(group_history, onboarded=True) if grouped_slot > 0 else group_history
                    grouped_public = seller_observation(policy, world, grouped_service, grouped_context, autonomous=arm['autonomous_onboarding'])
                    grouped_key = digest([grouped_public, world, choice_model, arm['strategic_pricing'], competitor_model])
                    if grouped_key not in prices:
                        prices[grouped_key] = optimize_price(grouped_public, world, choice_model, strategic=arm['strategic_pricing'], lagged=competitor_model == 'lagged')
                    group_publics.append(grouped_public)
                    group_quotes.append(prices[grouped_key])
                bundle_plan = optimize_bundle(group_publics, group_quotes, world, choice_model, strategic=arm['strategic_pricing'], coordination_cost_usd=policy['costs_usd']['bundle_coordination_once'] * policy['cost_multiplier'])
                if bundle_plan['total_price'] is None or bundle_plan['expected_immediate_contribution_per_opportunity'] <= 0:
                    bundle = False
            base_budget = len(selected) * (base_attempt + acquisition_each) + (money(policy['costs_usd']['bundle_coordination_once'] * policy['cost_multiplier']) if bundle else 0)
            forecast_quotes = []
            for slot, job_id in enumerate(selected):
                if bundle and slot < 3:
                    forecast_quotes.append(group_quotes[slot])
                    continue
                forecast_buyer = histories[f'SIM-buyer-{(cycle * 2 + slot) % policy["customer_pool"]}']
                forecast_service = jobs[job_id]['job']['service_id']
                forecast_public = seller_observation(policy, world, forecast_service, forecast_buyer, autonomous=arm['autonomous_onboarding'])
                forecast_key = digest([forecast_public, world, choice_model, arm['strategic_pricing'], competitor_model])
                if forecast_key not in prices:
                    prices[forecast_key] = optimize_price(forecast_public, world, choice_model, strategic=arm['strategic_pricing'], lagged=competitor_model == 'lagged')
                forecast_quotes.append(prices[forecast_key])
            forecast = (bundle_plan['expected_immediate_contribution_per_opportunity'] + sum(q['expected_immediate_contribution_per_opportunity'] for q in forecast_quotes[3:])) if bundle else sum(q['expected_immediate_contribution_per_opportunity'] for q in forecast_quotes)
            if forecast <= 0:
                stop = 'NO_BID_NONPOSITIVE_COMPLETE_BATCH_FORECAST_BEFORE_COMMITMENT'
                break
            funded = before['unrestrictedEarned'] >= base_budget and before['profit'] > 0 and forecast > 0
            if before['available'] < base_budget:
                stop = 'LIQUIDITY_BEFORE_DELIVERY_COMMITMENT'
                break
            funding = 'PRIOR_UNRESTRICTED_SIMULATED_EARNINGS' if funded else 'SEED_OR_REMAINING_LIQUIDITY'
            if funded:
                exchange.execute('reserve', {'id': f'cycle-capacity-{cycle}', 'amount': base_budget, 'expected_net_value': max(1, money(forecast)), 'intent_sha256': digest({'cycle': cycle, 'jobs': selected, 'public_quotes': public_quotes, 'forecast_quotes': forecast_quotes, 'bundle_plan': bundle_plan})}, day)
            else:
                charge(f'cycle-attempts-{cycle}', base_budget, day, 'production_verification_corrections_acquisition_support_all_slots')
            consumed.update(selected)
            outage = draw(seed, cycle, 'supplier', 'outage') < world['supplier_outage_probability']
            work = []
            for job_id in selected:
                if outage:
                    work.append({'job_id': job_id, 'funding': funding, 'commitment_sequence': len(exchange.actions)-1, 'receipt': {'accepted': False, 'reexecuted': False, 'reason': 'SUPPLIER_OUTAGE_UNAVAILABLE_CAPACITY', 'cost_scope': 'Committed capacity/acquisition outage loss charged conservatively; no unavailable production counted.'}})
                    continue
                from enterprise.services import execute_job
                receipt = execute_job(root, jobs[job_id]['job'])
                if receipt.get('accepted') is not True:
                    raise ValueError('POST_FUNDING_ACTUAL_SERVICE_EXECUTION_FAILED')
                work.append({'job_id': job_id, 'funding': funding, 'commitment_sequence': len(exchange.actions) - 1, 'receipt': receipt})
            if funded:
                exchange.execute('finish', {'id': f'cycle-capacity-{cycle}', 'amount': base_budget, 'artifact_sha256': digest([{'job_id': x['job_id'], 'artifact_sha256': x['receipt'].get('artifact_sha256'), 'accepted': x['receipt'].get('accepted')} for x in work])}, day)
                cost_receipts.append({'event': f'cycle-capacity-{cycle}', 'category': 'earned_funded_attempts_acquisition_support', 'amount': base_budget, 'currency': policy['currency'], 'evidence': 'AUTHORED_CONDITIONAL_ENVELOPE'})
            lifecycle = {}
            for customer_id, state in histories.items():
                was_active = state['active']
                churned = state['purchases'] > 0 and was_active and draw(seed, cycle, customer_id, 'retention') > world['retention_probability']
                if churned:
                    state['active'] = False
                    counts['churn_events'] += 1
                reacquisition = not state['active'] and draw(seed, cycle, customer_id, 'reacquisition') < world['reacquisition_probability']
                counts['reacquisition_opportunities'] += int(reacquisition)
                lifecycle[customer_id] = {'eligible': state['active'] or reacquisition, 'active_before': state['active'], 'churned': churned, 'reacquisition': reacquisition}
            decisions, settlement_queue = [], []
            # A grouped bundle consumes the same component slots and revenue replaces individual opportunities.
            bundle_pick, bundle_allowed = None, False
            if bundle:
                counts['bundles_offered'] += 1
                if bundle_plan['total_price'] is not None:
                    rows = [utilities(p['anchor_usd'] * private[group_buyer]['value_factor'] * world['demand_value_multiplier'], q['price'] * bundle_plan['factor'], q['rival']['price'], p, world) for p, q in zip(group_publics, group_quotes)]
                    combined = [sum(row[i] for row in rows) for i in range(5)]
                    combined[0] += sum(p['friction_usd'] for p in group_publics[1:])
                    chances = probabilities(combined, choice_model, sum(p['anchor_usd'] for p in group_publics) * world['temperature_ratio'])
                    toss, cumulative = draw(seed, cycle, group_buyer, 'bundle-choice'), 0.
                    bundle_pick = 4
                    for option, probability in enumerate(chances):
                        cumulative += probability
                        if toss < cumulative:
                            bundle_pick = option
                            break
                    bundle_allowed = bundle_pick == 0 and combined[0] >= 0 and private[group_buyer]['budget_usd'] >= bundle_plan['total_price']
            for slot, job_id in enumerate(selected):
                buyer_id = f'SIM-buyer-{(cycle * 2 + (0 if bundle and slot < 3 else slot)) % policy["customer_pool"]}'
                history = histories[buyer_id]
                hidden = private[buyer_id]
                service = jobs[job_id]['job']['service_id']
                prior_purchases = history['purchases']
                arrived = draw(seed, cycle, buyer_id, 'arrival') < world['arrival_probability']
                qualifies = draw(seed, cycle, buyer_id, 'qualification') < world['qualification_probability']
                lifecycle_state = lifecycle[buyer_id]
                counts['arrivals'] += int(arrived)
                counts['qualified'] += int(arrived and qualifies)
                public = group_publics[slot] if bundle and slot < 3 else seller_observation(policy, world, service, history, autonomous=arm['autonomous_onboarding'])
                key = digest([public, world, choice_model, arm['strategic_pricing'], competitor_model])
                if key not in prices:
                    prices[key] = optimize_price(public, world, choice_model, strategic=arm['strategic_pricing'], lagged=competitor_model == 'lagged')
                quote = group_quotes[slot] if bundle and slot < 3 else prices[key]
                exposed = arrived and qualifies and lifecycle_state['eligible'] and quote['price'] is not None and not outage
                counts['exposed'] += int(exposed)
                price_usd = (quote['price'] or 0) * (bundle_plan.get('factor', 1.) if bundle and slot < 3 else 1)
                price = money(price_usd)
                latent_value = public['anchor_usd'] * hidden['value_factor'] * world['demand_value_multiplier']
                utilities_ = utilities(latent_value, price_usd, quote['rival']['price'], public, world)
                chances = probabilities(utilities_, choice_model, max(.01, public['anchor_usd'] * world['temperature_ratio']))
                pick, cumulative = 4, 0.
                toss = draw(seed, cycle, buyer_id, 'choice-' + service)
                for option, probability in enumerate(chances):
                    cumulative += probability
                    if toss < cumulative:
                        pick = option
                        break
                if bundle and slot < 3:
                    pick = bundle_pick if bundle_pick is not None else 4
                    chooses = exposed and bundle_allowed
                else:
                    chooses = exposed and pick == 0 and hidden['budget_usd'] >= price_usd and utilities_[0] >= 0
                decision = {'job_id': job_id, 'service_id': service, 'buyer': buyer_id, 'arrived': arrived, 'qualified': qualifies, 'customer_lifecycle': dict(lifecycle_state), 'exposed': exposed, 'participates': chooses, 'prior_purchases': prior_purchases, 'bundle_id': f'bundle-{cycle}' if bundle and slot < 3 else None, 'price': price, 'human_complete_cost_anchor': money(public['anchor_usd']), 'seller_public_observation': public, 'price_policy': {'price': quote['price'], 'win_probability': quote['win_probability'], 'expected_immediate_contribution_per_opportunity': quote['expected_immediate_contribution_per_opportunity'], 'rival': quote['rival']}, 'outside_choice': ['our_service', 'rival_ai', 'human_service', 'self_service', 'postpone_or_no_purchase'][pick], 'outcome': 'NO_ORDER' if not chooses else 'PREPARED'}
                if chooses:
                    ident = f'SIM-order-{cycle}-{slot}'
                    wallet = ident + '-wallet'
                    exchange.execute('wallet', {'buyer': wallet, 'amount': price}, day)
                    exchange.execute('offer', {'id': ident, 'buyer': wallet, 'price': price, 'job_id': job_id, 'deadline': day + 14}, day)
                    for action in ['consent', 'fund', 'prepare']:
                        exchange.execute('event', {'id': ident, 'event_id': ident + '-' + action, 'action': action}, day)
                    counts['activated'] += 1
                    counts['accepted'] += 1
                    if not history['onboarded']:
                        onboarding = money((policy['costs_usd']['autonomous_onboarding_once'] + policy['costs_usd']['external_onboarding_fee']) * policy['cost_multiplier'])
                        charge(buyer_id + '-onboarding-once', onboarding, day, 'provider_autonomous_onboarding_once')
                        history['onboarded'] = True
                    fee = (price * policy['payment_bps'] + 9999) // 10000 + policy['payment_fixed']
                    charge(ident + '-payment-fee', fee, day, 'collection_payment_fee')
                    collect = draw(seed, cycle, buyer_id, 'collection') < world['collection_probability']
                    disputed = draw(seed, cycle, buyer_id, 'refund') < world['refund_probability']
                    late = world['settlement_delay_days'] > 14 or world['our_hours'] > 24
                    settlement_queue.append({'order_id': ident, 'job_id': job_id, 'buyer_id': buyer_id, 'price_usd': price_usd, 'decision': decision, 'collect': collect, 'disputed': disputed or late})
                decisions.append(decision)
            settled_this = 0
            for event in settlement_queue:
                decision, history = event['decision'], histories[event['buyer_id']]
                refund = event['disputed'] or not event['collect']
                action = 'refund' if refund else 'release'
                exchange.execute('event', {'id': event['order_id'], 'event_id': event['order_id'] + '-' + action, 'action': action}, day + world['settlement_delay_days'])
                if refund:
                    counts['refunded'] += int(event['disputed'])
                    counts['defaulted'] += int(not event['collect'])
                    history['trust'] = max(.5, history['trust'] - .025)
                    decision['outcome'] = 'SIMULATED_REFUND_OR_DEFAULT'
                else:
                    if not history['active']:
                        history['reacquisitions'] += 1
                        counts['reacquired_customers'] += 1
                    history['active'] = True
                    history['purchases'] += 1
                    history['last_purchase_cycle'] = cycle
                    if decision['service_id'] not in history['services']:
                        history['services'].append(decision['service_id'])
                    private[event['buyer_id']]['budget_usd'] -= event['price_usd']
                    history['trust'] = min(.99, history['trust'] + .002)
                    counts['settled'] += 1
                    settled_this += 1
                    decision['outcome'] = 'SIMULATED_SETTLED'
            if bundle and all(d['outcome'] == 'SIMULATED_SETTLED' for d in decisions[:3]):
                counts['bundles_settled'] += 1
            taxable = max(0, exchange.ex.snapshot()['profit'] + cumulative_tax)
            provision = max(0, taxable - previous_taxable) * policy['profit_tax_bps'] // 10000
            if provision:
                charge(f'conditional-profit-tax-{cycle}', provision, day + 29, 'conditional_positive_profit_tax_provision')
            cumulative_tax += provision
            previous_taxable = max(previous_taxable, taxable)
            after = exchange.ex.snapshot()
            cycles.append({'cycle': cycle, 'funding': funding, 'base_budget': base_budget, 'forecast_expected_incremental_usd': forecast, 'forecast_quotes': forecast_quotes, 'forecast_scope': 'Public CRM context and segment arrival/qualification/supplier probabilities; unconditional attempt and acquisition each selected slot, conditional payment/onboarding, joint bundle coordination. Retention/budget shocks may deviate; no private realized value is used.', 'service_ids': sorted({jobs[j]['job']['service_id'] for j in selected}), 'jobs': selected, 'outage': outage, 'bundle': bundle, 'bundle_plan': bundle_plan, 'decisions': decisions, 'post_commitment_actual_work': work, 'settled_jobs': settled_this, 'before': before, 'after': after})
        tape = exchange.export()
    finally:
        exchange.close()
        temp.cleanup()
    verified = audit(tape, root=root, manifest=manifest, expected_actions_sha256=tape['actions_sha256'])
    summary = verified['summary']
    thresholds = policy['thresholds']
    customers = sum(h['purchases'] > 0 for h in histories.values())
    repeats = sum(h['purchases'] > 1 for h in histories.values())
    earned_cycles = sum(c['funding'] == 'PRIOR_UNRESTRICTED_SIMULATED_EARNINGS' and c['settled_jobs'] > 0 and c['after']['profit'] > c['before']['profit'] for c in cycles)
    survives = summary['payables'] == 0 and not summary['investmentStopped'] and summary['cash'] >= summary['tailReserve'] + summary['workingCapital'] + summary['custodyReserve']
    success = len(cycles) == policy['cycles'] and customers >= thresholds['minimum_customers'] and counts['settled'] >= thresholds['minimum_paid_jobs'] and repeats >= thresholds['minimum_repeat_customers'] and earned_cycles >= thresholds['minimum_earned_funded_cycles'] and summary['profit'] > 0 and summary['unrestrictedEarned'] > 0 and survives
    result = {'schema': 'agi-alpha/enterprise011-world/v1', 'scope': 'SIMULATED', 'regime': regime, 'choice_model': choice_model, 'competitor_model': competitor_model, 'seed': seed, 'arm': arm, 'policy_sha256': digest(policy), 'manifest_sha256': digest(manifest), 'thresholds': thresholds, 'conditional_simulated_go': success, 'cash_survival': survives, 'stop': stop, 'paid_jobs': counts['settled'], 'accepted_jobs': counts['accepted'], 'customers': customers, 'repeat_buyers': repeats, 'earned_funded_cycles': earned_cycles, 'services_settled': sorted({d['service_id'] for c in cycles for d in c['decisions'] if d['outcome'] == 'SIMULATED_SETTLED'}), 'counts': counts, 'cycles': cycles, 'buyers_public_final_history': list(histories.values()), 'cost_receipts': cost_receipts, 'ledger': tape, 'summary': summary, 'available_earned_surplus': summary['unrestrictedEarned'], 'reinvested_earned': sum(int(i['actual']) for i in verified['investments'] if i['state'] == 'complete'), 'earned_funding_scope': 'Native prior-earned reserve finances base production, acquisition, support and bundle coordination tranche; later provider onboarding, collection fees and tax costs are separately paid and included in cycle/total profit. Seed may still back principal-tail and working reserves.', 'seed_still_supporting_reserves': summary['equityProtectionBacking'], 'strict_seed_independent_earned_control': summary['strictEarnedControl'], 'sales_tax_collected_for_remittance': 0, 'actual_customers': 0, 'actual_collections': 0, 'actual_profit': None, 'service_execution': 'ACTUAL_DETERMINISTIC_PRODUCTION_AND_INDEPENDENT_CHECKING', 'provider_model_inference': 'NOT_CALLED_IN_THIS_SERVICE_EXECUTION', 'invention_compounding': 'NOT_ESTABLISHED', 'blue_sky_enablement': 'NOT_ESTABLISHED', 'cost_evidence': policy['cost_evidence'], 'production_cpu_seconds': time.process_time() - start_cpu, 'production_wall_seconds': time.monotonic() - start_wall, 'price_searches': [{'public_input_sha256': k, 'result': v} for k, v in prices.items()], 'exceptions': exceptions}
    if output is not None:
        (output / 'RESULT.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return result


def aggregate(results):
    if not results:
        raise ValueError('NONEMPTY_SCENARIO_COHORT_REQUIRED')
    profits = [r['summary']['profit'] for r in results]
    n, passed = len(results), sum(r['conditional_simulated_go'] for r in results)
    z, fraction = 1.959963984540054, passed / n
    center = (fraction + z*z/(2*n)) / (1+z*z/n)
    half = z * math.sqrt(fraction*(1-fraction)/n + z*z/(4*n*n)) / (1+z*z/n)
    return {'runs': n, 'go_runs': passed, 'go_fraction': fraction, 'engineering_wilson95_interval': [max(0., center-half), min(1., center+half)], 'mean_complete_profit': sum(profits)/n, 'profit_range': [min(profits), max(profits)], 'cash_survival_fraction': sum(r['cash_survival'] for r in results)/n, 'mean_paid_jobs': sum(r['paid_jobs'] for r in results)/n, 'mean_customers': sum(r['customers'] for r in results)/n, 'mean_repeat_buyers': sum(r['repeat_buyers'] for r in results)/n, 'mean_earned_funded_cycles': sum(r['earned_funded_cycles'] for r in results)/n, 'mean_available_earned': sum(r['summary']['unrestrictedEarned'] for r in results)/n, 'scope': 'Finite prespecified conditional scenario trajectories. Wilson interval describes seeded simulator success only, not empirical real-market probability or independent uncertainty in authored assumptions.'}
