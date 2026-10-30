"""Conditional monthly scale projections, separate from audited service execution."""
from __future__ import annotations
import copy
import hashlib
import json
import math
import random

SCOPE = 'CONDITIONAL_SCALE_PROJECTION'


def default_config():
    return {
        'schema': 'agi-alpha/enterprise011-scale/v1', 'scope': SCOPE,
        'currency': 'USD', 'money_unit': 'cents', 'months': 120,
        'targets_annual_collected_cents': [100_000_000_000, 1_000_000_000_000, 10_000_000_000_000, 100_000_000_000_000],
        'opening_cash_cents': 25_000_000, 'setup_cost_cents': 1_000_000,
        'liquidity_floor_cents': 1_000_000, 'fixed_monthly_cost_cents': 300_000,
        'initial_customers': 20, 'reachable_market_customers': 2_000_000,
        'initial_capacity_jobs': 200, 'capacity_block_jobs': 100,
        'capacity_block_cost_cents': 500_000, 'supplier_capacity_jobs': 2_000_000,
        'price_per_work_product_cents': 40_000, 'attempt_cost_cents': 4_000,
        'support_per_customer_cents': 300, 'onboarding_per_customer_cents': 2_000,
        'exposure_cost_cents': 300, 'qualification_cost_cents': 200,
        'base_monthly_contacts': 120, 'referral_contacts_per_customer': .15,
        'maximum_monthly_contacts': 100_000, 'contact_growth_monthly': .01,
        'qualification_probability': .7, 'choice_probability': .25,
        'activation_probability': .9, 'sales_cycle_months': 1,
        'base_products_per_customer': 2, 'extra_products_per_customer': 2,
        'cross_sell_monthly_probability': .025, 'utilization_probability': .75,
        'monthly_churn_probability': .025, 'technical_acceptance_probability': .98,
        'collection_probability': .98, 'refund_probability': .02,
        'settlement_months': 1, 'reserve_months': 3, 'reserve_bps': 1000,
        'payment_fee_bps': 290, 'payment_fixed_cents': 30, 'sales_tax_bps': 0,
        'acquisition_budget_fraction': .16, 'capacity_budget_fraction': .25,
        'supplier_outage_probability': .03, 'supplier_cost_multiplier': 1.,
        'annual_price_compression': .015, 'shock_month': 36,
        'small_cohort_anchor': None,
        'assumptions': 'Authored conditional operating hypotheses, not calibrated market forecasts. Nominal USD cents, integer rounding at each charge, no currency conversion or inflation forecast. Zero sales tax is a disclosed scenario assumption, not a tax eligibility determination; a configured tax is collected and remitted immediately outside revenue. Only permitted synthetic digital outcomes; no geographic expansion or regulatory permission assumed. Aggregate binomial draws use exact trials up to 200 and bounded normal approximation above 200. Bundle components are counted as delivered work products once; no extra bundle revenue is added. Initial cash is an explicit hypothetical scale allocation, separate from any small-cohort earned funds.',
    }


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_config(config):
    template = default_config()
    if not isinstance(config, dict) or set(config) != set(template):
        raise ValueError('EXACT_SCALE_CONFIG_REQUIRED')
    for name in ('schema', 'scope', 'currency', 'money_unit'):
        if config[name] != template[name]:
            raise ValueError('SCALE_SCHEMA_SCOPE_UNIT')
    integer_keys = [k for k, v in template.items() if type(v) is int]
    for key in integer_keys:
        if type(config[key]) is not int or config[key] < 0:
            raise ValueError('NONNEGATIVE_INTEGER_SCALE_INPUT:' + key)
    if not 1 <= config['months'] <= 600 or config['initial_customers'] > config['reachable_market_customers']:
        raise ValueError('BOUNDED_HORIZON_AND_MARKET_REQUIRED')
    if config['capacity_block_jobs'] < 1 or config['capacity_block_cost_cents'] < 1:
        raise ValueError('POSITIVE_CAPACITY_BLOCK_REQUIRED')
    if config['base_products_per_customer'] < 1 or config['price_per_work_product_cents'] < 1:
        raise ValueError('POSITIVE_WORK_UNIT_AND_PRICE')
    for key, default in template.items():
        if type(default) is float:
            value = config[key]
            if not _finite(value) or value < 0:
                raise ValueError('FINITE_NONNEGATIVE_SCALE_INPUT:' + key)
            if ('probability' in key or 'fraction' in key or key == 'annual_price_compression') and value > 1:
                raise ValueError('SCALE_PROBABILITY_RANGE:' + key)
    if config['supplier_cost_multiplier'] <= 0:
        raise ValueError('POSITIVE_SUPPLIER_COST')
    for key in ('reserve_bps', 'payment_fee_bps', 'sales_tax_bps'):
        if config[key] > 10_000:
            raise ValueError('BASIS_POINTS_REQUIRED')
    targets = config['targets_annual_collected_cents']
    if not isinstance(targets, list) or not targets or len(targets) > 100 or any(type(x) is not int or x <= 0 for x in targets) or len(set(targets)) != len(targets):
        raise ValueError('UNIQUE_POSITIVE_MILESTONES_REQUIRED')
    if not isinstance(config['assumptions'], str) or not config['assumptions']:
        raise ValueError('DISCLOSED_SCALE_ASSUMPTIONS_REQUIRED')
    anchor = config['small_cohort_anchor']
    if anchor is not None and (not isinstance(anchor, dict) or anchor.get('scope') not in ('SIMULATED', 'SIMULATED_COMMERCIAL', 'CONDITIONAL_SIMULATED')):
        raise ValueError('EXPLICIT_SIMULATED_ANCHOR_REQUIRED')
    if config['sales_cycle_months'] > 24 or config['settlement_months'] > 24 or config['reserve_months'] > 60:
        raise ValueError('BOUNDED_SCALE_TIMING_REQUIRED')
    return config


def _trials(rng, count, probability):
    if count <= 0 or probability <= 0:
        return 0
    if probability >= 1:
        return count
    if count <= 200:
        return sum(rng.random() < probability for _ in range(count))
    mean = count * probability
    return min(count, max(0, int(round(rng.gauss(mean, math.sqrt(mean * (1 - probability)))))))


def _identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def simulate_scale(config, seed):
    validate_config(config)
    if type(seed) is not int or seed < 0:
        raise ValueError('NONNEGATIVE_SCALE_SEED_REQUIRED')
    c = copy.deepcopy(config)
    rng = random.Random(seed)
    cash = c['opening_cash_cents']
    setup = c['setup_cost_cents'] + c['initial_customers'] * c['onboarding_per_customer_cents']
    if cash < setup:
        return {'scope': SCOPE, 'config_sha256': _identity(c), 'seed': seed, 'cash_survival': False, 'terminal_reason': 'INITIAL_SETUP_UNFUNDED', 'months_completed': 0, 'monthly': [], 'milestones': {str(x): None for x in c['targets_annual_collected_cents']}, 'peak_additional_capital_needed_cents': setup - cash, 'initial_setup_required_cents': setup, 'cumulative_collected_revenue_cents': 0, 'cumulative_profit_cents': 0, 'ending_cash_cents': cash, 'cumulative_cost_cents': 0, 'terminal_receivables_cents': 0, 'restricted_cash_cents': 0, 'ending_unrestricted_cash_cents': cash, 'binding_constraints': ['setup_cash'], 'small_cohort_anchor': c['small_cohort_anchor'], 'cost_basis': 'Setup was not admitted or incurred because initial funding was insufficient.'}
    cash -= setup
    expenses = setup
    cohorts = [{'customers': c['initial_customers'], 'age': 0}]
    ever_acquired = c['initial_customers']
    exposed = 0
    capacity = c['initial_capacity_jobs']
    pipeline, receivables, reserves = [], [], []
    monthly, collected_history = [], []
    milestones = {str(x): None for x in c['targets_annual_collected_cents']}
    cumulative_collected = recognized = 0
    peak_need = 0
    binding, survived = set(), True
    previous_unserved = 0
    terminal_reason = 'HORIZON_COMPLETED'
    for month in range(1, c['months'] + 1):
        receipts = [x for x in receivables if x['due'] <= month]
        receivables = [x for x in receivables if x['due'] > month]
        collected = sum(x['net_revenue_cents'] for x in receipts)
        collected_tax = sum(x['tax_cents'] for x in receipts)
        cash += collected + collected_tax
        cash -= collected_tax
        cumulative_collected += collected
        for receipt in receipts:
            reserve = receipt['net_revenue_cents'] * c['reserve_bps'] // 10_000
            reserves.append({'due': month + c['reserve_months'], 'cents': reserve})
        reserves = [x for x in reserves if x['due'] > month]
        restricted = sum(x['cents'] for x in reserves)
        shock = c['shock_month'] == month
        churn = min(1., c['monthly_churn_probability'] + (.15 if shock else 0.) + (.05 if previous_unserved else 0.))
        for cohort in cohorts:
            cohort['customers'] = _trials(rng, cohort['customers'], 1 - churn)
            cohort['age'] += 1
        cohorts = [x for x in cohorts if x['customers']]
        arriving = sum(x['customers'] for x in pipeline if x['due'] <= month)
        pipeline = [x for x in pipeline if x['due'] > month]
        available = max(0, cash - restricted - c['liquidity_floor_cents'])
        affordable_arrivals = min(arriving, available // max(1, c['onboarding_per_customer_cents']))
        onboarding_cost = affordable_arrivals * c['onboarding_per_customer_cents']
        cash -= onboarding_cost
        expenses += onboarding_cost
        if affordable_arrivals < arriving:
            binding.add('onboarding_cash')
            peak_need = max(peak_need, (arriving - affordable_arrivals) * c['onboarding_per_customer_cents'])
        if affordable_arrivals:
            cohorts.append({'customers': affordable_arrivals, 'age': 0})
        active = sum(x['customers'] for x in cohorts)
        monthly_fixed = c['fixed_monthly_cost_cents'] + active * c['support_per_customer_cents']
        if cash - restricted < monthly_fixed:
            survived = False
            peak_need = max(peak_need, monthly_fixed - max(0, cash - restricted))
            binding.add('operating_cash')
            terminal_reason = 'OPERATING_CASH_FAILURE'
            break
        cash -= monthly_fixed
        expenses += monthly_fixed
        desired = 0
        for cohort in cohorts:
            extras = _trials(rng, cohort['customers'] * c['extra_products_per_customer'], min(1., cohort['age'] * c['cross_sell_monthly_probability']))
            potential = cohort['customers'] * c['base_products_per_customer'] + extras
            desired += _trials(rng, potential, c['utilization_probability'] * (.6 if shock else 1.))
        supplier_limit = 0 if rng.random() < c['supplier_outage_probability'] else c['supplier_capacity_jobs']
        if supplier_limit < desired:
            binding.add('supplier_capacity_or_outage')
        available = max(0, cash - restricted - c['liquidity_floor_cents'])
        capacity_budget = int(available * c['capacity_budget_fraction'])
        blocks_needed = max(0, (min(desired, supplier_limit) - capacity + c['capacity_block_jobs'] - 1) // c['capacity_block_jobs'])
        blocks = min(blocks_needed, capacity_budget // c['capacity_block_cost_cents'])
        capacity_cost = blocks * c['capacity_block_cost_cents']
        cash -= capacity_cost
        expenses += capacity_cost
        capacity += blocks * c['capacity_block_jobs']
        if blocks < blocks_needed:
            binding.add('capacity_investment_cash')
            peak_need = max(peak_need, (blocks_needed - blocks) * c['capacity_block_cost_cents'])
        unit_cost = int(math.ceil(c['attempt_cost_cents'] * c['supplier_cost_multiplier'] * (2 if shock else 1)))
        available = max(0, cash - restricted - c['liquidity_floor_cents'])
        attempts = min(desired, capacity, supplier_limit, available // max(1, unit_cost))
        if attempts < desired:
            binding.add('delivery_capacity')
        if unit_cost and attempts < min(desired, capacity, supplier_limit):
            binding.add('delivery_cash')
        previous_unserved = desired - attempts
        costs = attempts * unit_cost
        cash -= costs
        expenses += costs
        accepted = _trials(rng, attempts, c['technical_acceptance_probability'] * (.9 if shock else 1.))
        paid = _trials(rng, accepted, c['collection_probability'] * (.8 if shock else 1.))
        refunds = _trials(rng, paid, min(1., c['refund_probability'] * (3 if shock else 1.)))
        price = max(1, int(round(c['price_per_work_product_cents'] * ((1 - c['annual_price_compression']) ** ((month - 1) / 12)))))
        gross = paid * price
        refund_amount = refunds * price
        net = gross - refund_amount
        fees = gross * c['payment_fee_bps'] // 10_000 + paid * c['payment_fixed_cents']
        if fees > cash - restricted:
            survived = False
            peak_need = max(peak_need, fees - max(0, cash - restricted))
            binding.add('payment_fee_cash')
            terminal_reason = 'PAYMENT_FEE_CASH_FAILURE'
            break
        cash -= fees
        expenses += fees
        recognized += net
        if net:
            receivables.append({'due': month + max(1, c['settlement_months']), 'net_revenue_cents': net, 'tax_cents': net * c['sales_tax_bps'] // 10_000})
        available = max(0, cash - restricted - c['liquidity_floor_cents'])
        acquisition_budget = int(available * c['acquisition_budget_fraction'])
        headroom = max(0, c['reachable_market_customers'] - ever_acquired)
        unexposed_market = max(0, c['reachable_market_customers'] - c['initial_customers'] - exposed)
        channel_contacts = min(c['maximum_monthly_contacts'], int(c['base_monthly_contacts'] * (1 + c['contact_growth_monthly'] * month) + active * c['referral_contacts_per_customer']))
        max_contact_cost = c['exposure_cost_cents'] + c['qualification_cost_cents']
        contacts = min(unexposed_market, channel_contacts, acquisition_budget // max(1, max_contact_cost))
        qualified = _trials(rng, contacts, c['qualification_probability'])
        won = _trials(rng, qualified, c['choice_probability'] * (.5 if shock else 1.))
        activated = min(headroom, _trials(rng, won, c['activation_probability']))
        acquisition_cost = contacts * c['exposure_cost_cents'] + qualified * c['qualification_cost_cents']
        cash -= acquisition_cost
        expenses += acquisition_cost
        exposed += contacts
        ever_acquired += activated
        if activated:
            pipeline.append({'due': month + max(1, c['sales_cycle_months']), 'customers': activated})
        if contacts < channel_contacts:
            binding.add('reachable_market' if unexposed_market <= contacts else 'acquisition_cash')
        if contacts == c['maximum_monthly_contacts']:
            binding.add('channel_capacity')
        collected_history.append(collected)
        trailing = sum(collected_history[-12:])
        run_rate = collected * 12
        for target in c['targets_annual_collected_cents']:
            if milestones[str(target)] is None and len(collected_history) >= 12 and trailing >= target:
                milestones[str(target)] = month
        if cash < restricted or cash < 0:
            raise AssertionError('SCALE_RESTRICTED_CASH_CONSERVATION')
        if cash != c['opening_cash_cents'] + cumulative_collected - expenses:
            raise AssertionError('SCALE_CASH_CONSERVATION')
        monthly.append({'month': month, 'active_customers': active, 'ever_acquired_customers': ever_acquired, 'new_activated': activated, 'contacts': contacts, 'qualified': qualified, 'choice_wins': won, 'onboarded': affordable_arrivals, 'desired_work_products': desired, 'executed_projection_attempts': attempts, 'accepted_projection_work_products': accepted, 'collected_projection_jobs': paid - refunds, 'failed_or_rejected_projection_attempts': attempts - accepted, 'uncollected_projection_jobs': accepted - paid, 'refunded_projection_jobs': refunds, 'supplier_available_jobs': supplier_limit, 'capacity_jobs': capacity, 'capacity_investment_cents': capacity_cost, 'collected_revenue_cents': collected, 'trailing_12_collected_revenue_cents': trailing, 'annualized_collected_run_rate_cents': run_rate, 'cumulative_collected_revenue_cents': cumulative_collected, 'cumulative_recognized_revenue_cents': recognized, 'cumulative_cost_cents': expenses, 'cumulative_profit_cents': recognized - expenses, 'cash_cents': cash, 'restricted_cash_cents': restricted, 'available_cash_cents': cash - restricted, 'tax_collected_and_remitted_cents': collected_tax})
    return {'scope': SCOPE, 'schema': c['schema'], 'config_sha256': _identity(c), 'seed': seed, 'cash_survival': survived, 'terminal_reason': terminal_reason, 'months_completed': len(monthly), 'monthly': monthly, 'milestones': milestones, 'milestone_basis': 'First month with at least 12 completed projection months and trailing-12 net collected revenue at threshold; annualized run rate does not qualify.', 'peak_additional_capital_needed_cents': peak_need, 'capital_needs_basis': 'Largest single unfunded desired onboarding/capacity block or operating shortfall. This is a policy funding-gap diagnostic, not a solved minimum external-capital requirement; no external capital is injected.', 'cumulative_collected_revenue_cents': cumulative_collected, 'cumulative_profit_cents': recognized - expenses, 'cumulative_cost_cents': expenses, 'ending_cash_cents': cash, 'terminal_receivables_cents': sum(x['net_revenue_cents'] for x in receivables), 'restricted_cash_cents': sum(x['cents'] for x in reserves), 'ending_unrestricted_cash_cents': cash - sum(x['cents'] for x in reserves), 'binding_constraints': sorted(binding), 'small_cohort_anchor': c['small_cohort_anchor'], 'anchor_scope': 'Provenance only. Scale assumptions are separately declared and are not inferred from the small executed cohort.', 'assumptions': c['assumptions'], 'liquidity_floor_cents': c['liquidity_floor_cents'], 'liquidity_floor_basis': 'Investment, acquisition and delivery admission preserve this working buffer. Already owed fixed bills may consume the buffer; cash survival means obligations remain funded, not that the buffer never falls.', 'seed_capital_still_supports_reserves': True}


def _quantile(values, probability):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(math.ceil(probability * len(ordered))) - 1)]


def evaluate_scale(config, seeds):
    validate_config(config)
    if not isinstance(seeds, list) or not seeds or len(seeds) > 128 or any(type(x) is not int or x < 0 for x in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError('FIXED_UNIQUE_SCALE_SEEDS_REQUIRED')
    regime_changes = {
        'base': {},
        'fast': {'reachable_market_customers': config['reachable_market_customers'] * 4, 'base_monthly_contacts': config['base_monthly_contacts'] * 3, 'choice_probability': min(1., config['choice_probability'] * 1.3), 'monthly_churn_probability': config['monthly_churn_probability'] / 2},
        'slow': {'base_monthly_contacts': config['base_monthly_contacts'] // 3, 'choice_probability': config['choice_probability'] / 2, 'monthly_churn_probability': min(1., config['monthly_churn_probability'] * 1.5)},
        'shock': {'supplier_outage_probability': min(1., config['supplier_outage_probability'] * 4), 'supplier_cost_multiplier': config['supplier_cost_multiplier'] * 2, 'collection_probability': max(0., config['collection_probability'] - .12), 'annual_price_compression': max(.08, config['annual_price_compression'])},
    }
    result = {}
    for regime, changes in regime_changes.items():
        scenario = copy.deepcopy(config)
        scenario.update(changes)
        trajectories = [simulate_scale(scenario, seed) for seed in seeds]
        targets = {}
        for target in config['targets_annual_collected_cents']:
            times = [t['milestones'][str(target)] for t in trajectories]
            reached = [x for x in times if x is not None]
            censored = [x if x is not None else config['months'] + 1 for x in times]
            def censored_quantile(q):
                value = _quantile(censored, q)
                return value if value <= config['months'] else None
            targets[str(target)] = {'reached': len(reached), 'not_reached': len(times) - len(reached), 'probability_within_horizon': len(reached) / len(times), 'times_months_including_right_censoring': times, 'censored_quantiles_months': {'p10': censored_quantile(.1), 'p50': censored_quantile(.5), 'p90': censored_quantile(.9)}, 'reached_only_median_months': _quantile(reached, .5), 'censoring': 'None means not reached within the horizon; quantiles include all trajectories, not just successes.'}
        result[regime] = {'config': scenario, 'milestones': targets, 'cash_survival_probability': sum(t['cash_survival'] for t in trajectories) / len(trajectories), 'profit_cents': [t['cumulative_profit_cents'] for t in trajectories], 'peak_additional_capital_needed_cents': max(t['peak_additional_capital_needed_cents'] for t in trajectories), 'binding_constraints': sorted(set().union(*(set(t['binding_constraints']) for t in trajectories))), 'trajectories': trajectories}
    return {'scope': SCOPE, 'currency': 'USD', 'money_unit': 'cents', 'horizon_months': config['months'], 'seeds': seeds, 'regimes': result, 'verdict': 'Conditional projections only; no target is promised and no projection counts as executed service, actual demand, or audited simulated commercial receipts.', 'scenario_weights': 'Unweighted alternative hypotheses; no empirical probabilities assigned to regimes.'}
