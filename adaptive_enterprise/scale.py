"""Paired policy experiments in an explicitly conditional aggregate projection.

Forecast accounting is not financial authority: only adaptive_enterprise.account
owns and reserves the native small-cohort operating ledger.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math
import random
from enterprise.scale import default_config as legacy_config

CONTROLLERS = ('fixed_shares', 'ordinary_adaptive', 'adaptive')
SCOPE = 'CONDITIONAL_ADAPTIVE_SCALE_PROJECTION'


def default_config():
    c = legacy_config()
    c.update(schema='agi-alpha/adaptive012-scale/v1', scope=SCOPE,
        discount_rate_monthly=.01, channel_entry_cost_cents=500_000,
        channel_contacts_per_month=120, channel_entry_delay_months=1,
        capacity_delay_months=1, retention_entry_cost_cents=500_000,
        retention_monthly_cost_cents=20_000, retention_churn_reduction=.25,
        supplier_diversity_entry_cost_cents=1_500_000,
        supplier_diversity_monthly_cost_cents=50_000,
        instrument_entry_cost_cents=1_000_000, instrument_monthly_cost_cents=25_000,
        instrument_attempt_cost_reduction=.15, new_service_entry_cost_cents=750_000,
        new_service_adoption_probability=.25, planning_rounds_per_month=8,
        forecast_downside_penalty=.20, prudential_buffer_months=2., planner_round_cost_cents=25)
    c['assumptions'] += ' Adaptive012 compares controllers under matched initial cash, reachable opportunities and keyed monthly demand/supplier/payment shocks. All action effects, prices, churn and channel conversion are authored hypotheses. Costed channel entry and infrastructure provisioning have explicit delays. Lifetime value uses churn plus a positive monthly discount rate, not a short fixed acquisition horizon. No projected cash funds current spending. Instruments and new services here are projected cost/offer effects, not proof that a new real service or invention executed.'
    return c


def validate_config(c):
    template = default_config()
    if not isinstance(c, dict) or set(c) != set(template) or c.get('scope') != SCOPE or c.get('schema') != template['schema'] or c.get('money_unit') != 'cents' or c.get('currency') != 'USD':
        raise ValueError('EXACT_ADAPTIVE_SCALE_SCOPE_SCHEMA_REQUIRED')
    for key, value in template.items():
        if type(value) is int and (type(c[key]) is not int or c[key] < 0):
            raise ValueError('NONNEGATIVE_INTEGER_SCALE_VALUE:' + key)
        if type(value) is float:
            x = c[key]
            if type(x) not in (int, float) or not math.isfinite(x) or x < 0:
                raise ValueError('FINITE_SCALE_VALUE:' + key)
            if (any(word in key for word in ('probability', 'fraction', 'reduction')) or key == 'annual_price_compression') and x > 1:
                raise ValueError('SCALE_PROBABILITY_RANGE:' + key)
    if not 1 <= c['months'] <= 600 or c['discount_rate_monthly'] <= 0 or not 1 <= c['planning_rounds_per_month'] <= 128:
        raise ValueError('FINITE_EVALUATION_AND_PLANNING_BUDGET_REQUIRED')
    if c['initial_customers'] > c['reachable_market_customers'] or c['capacity_block_jobs'] < 1 or c['capacity_block_cost_cents'] < 1 or c['channel_entry_cost_cents'] < 1:
        raise ValueError('CONSISTENT_FINITE_SCALE_INPUT_REQUIRED')
    targets = c['targets_annual_collected_cents']
    if not isinstance(targets, list) or not targets or len(targets) > 100 or any(type(x) is not int or x <= 0 for x in targets) or len(set(targets)) != len(targets):
        raise ValueError('POSITIVE_UNIQUE_REVENUE_MILESTONES_REQUIRED')
    for key in ('payment_fee_bps', 'reserve_bps', 'sales_tax_bps'):
        if c[key] > 10000:
            raise ValueError('BASIS_POINTS_REQUIRED')
    return c


def _rng(seed, month, event):
    key = hashlib.sha256(json.dumps([seed, month, event], separators=(',', ':')).encode()).digest()
    return random.Random(int.from_bytes(key[:16], 'big'))


def _trials(seed, month, event, n, p):
    if n <= 0 or p <= 0:
        return 0
    if p >= 1:
        return n
    rng = _rng(seed, month, event)
    if n <= 200:
        return sum(rng.random() < p for _ in range(n))
    return max(0, min(n, round(rng.gauss(n*p, math.sqrt(n*p*(1-p))))))


def _levels(maximum):
    if maximum <= 0:
        return [0]
    values = {0, 1, maximum}
    step = 2
    while step < maximum:
        values.add(step); step *= 2
    return sorted(values)


def _controller_actions(c, state, controller, month):
    active, cash, capacity = state['active'], state['cash'], state['capacity']
    restricted = state['restricted']
    buffer = c['liquidity_floor_cents']
    # This is a revisable prudential policy for uncommitted future work, not a hard liability.
    if controller != 'fixed_shares':
        predicted_products = c['base_products_per_customer']*c['utilization_probability'] + state['additional_expected_products'] + c['extra_products_per_customer']*min(1.,month*c['cross_sell_monthly_probability'])
        fee_per_product = state['price']*c['payment_fee_bps']/10000+c['payment_fixed_cents']
        future_month_cost = c['fixed_monthly_cost_cents']+active*c['support_per_customer_cents']+active*predicted_products*(state['unit_cost']+fee_per_product)
        future_month_cost += c['retention_monthly_cost_cents'] if state['retention'] else 0
        future_month_cost += c['supplier_diversity_monthly_cost_cents'] if state['supplier_diversity'] else 0
        future_month_cost += c['instrument_monthly_cost_cents'] if state['instrument'] else 0
        pending_customers = sum(x['customers'] for x in state['pipeline'])
        pending_buffer = pending_customers*(c['onboarding_per_customer_cents']+c['prudential_buffer_months']*(c['support_per_customer_cents']+predicted_products*(state['unit_cost']+fee_per_product)))
        buffer += math.ceil(c['prudential_buffer_months']*future_month_cost+pending_buffer)
    available = max(0, cash - restricted - buffer)
    ready_channels = 1 + sum(x['count'] for x in state['channels'] if x['ready'] <= month)
    future_channels = 1 + sum(x['count'] for x in state['channels'])
    active_capacity = capacity + sum(x['jobs'] for x in state['pending_capacity'])
    price = state['price']
    cost = state['unit_cost']
    net_per_product = max(0., price * c['technical_acceptance_probability'] * c['collection_probability'] * (1-c['refund_probability']) * (1-c['payment_fee_bps']/10000) - cost)
    churn = c['monthly_churn_probability'] * (1-c['retention_churn_reduction'] if state['retention'] else 1)
    lifetime = 1 / (churn + c['discount_rate_monthly'])
    products = c['base_products_per_customer'] * c['utilization_probability'] + state['additional_expected_products'] + c['extra_products_per_customer']*min(1.,month*c['cross_sell_monthly_probability'])
    customer_value = max(0., (products * net_per_product - c['support_per_customer_cents']) * lifetime - c['onboarding_per_customer_cents'])
    conversion = state['estimated_conversion']
    contact_cost = c['exposure_cost_cents'] + c['qualification_cost_cents']
    market_left = max(0, c['reachable_market_customers'] - state['exposed'] - c['initial_customers'])
    if controller == 'fixed_shares':
        contacts = min(market_left, c['maximum_monthly_contacts'], int(c['base_monthly_contacts'] * (1+c['contact_growth_monthly']*month) + active*c['referral_contacts_per_customer']), int(available*c['acquisition_budget_fraction']) // max(1, contact_cost))
        cap_budget = int(available*c['capacity_budget_fraction'])
        blocks = min(max(0, math.ceil((state['previous_desired']-active_capacity)/c['capacity_block_jobs'])), cap_budget//c['capacity_block_cost_cents'])
        return {'kind': 'fixed_share_control', 'contacts': contacts, 'channel_entries': 0, 'capacity_blocks': blocks,
                'cost': contacts*contact_cost + blocks*c['capacity_block_cost_cents'], 'predicted_net_cash': round(contacts*conversion*customer_value - contacts*contact_cost - blocks*c['capacity_block_cost_cents']), 'value_basis': 'Historical fixed acquisition/capacity shares and backlog rule retained as a control only.'}
    candidates = [{'kind': 'retain_cash', 'cost': 0, 'predicted_net_cash': 0, 'contacts': 0, 'channel_entries': 0, 'capacity_blocks': 0}]
    supplier_limit = c['supplier_capacity_jobs'] * (2 if state['supplier_diversity'] else 1)
    expected_existing = active * products
    pending = sum(x['customers'] for x in state['pipeline'])
    for channel_entries in _levels(available//c['channel_entry_cost_cents']):
        entry_cost = channel_entries*c['channel_entry_cost_cents']
        remaining = available-entry_cost
        if remaining < 0:
            continue
        future_contact_capacity = (future_channels+channel_entries)*c['channel_contacts_per_month']
        contact_capacity = min(market_left, max(0,ready_channels*c['channel_contacts_per_month']-state.get('contacts_bought',0)))
        forecast_customers = min(market_left, future_contact_capacity*conversion)
        wanted = min(supplier_limit, expected_existing + (pending + forecast_customers)*products)
        max_blocks = min(max(0, math.ceil((wanted-active_capacity)/c['capacity_block_jobs'])), remaining//c['capacity_block_cost_cents'])
        for blocks in _levels(max_blocks):
            block_cost = blocks*c['capacity_block_cost_cents']
            future_spare = max(0., min(supplier_limit, active_capacity+blocks*c['capacity_block_jobs']) - expected_existing - pending*products)
            possible_contacts = math.floor(future_spare/max(.01, products*conversion)) if conversion else 0
            working_cash_per_lead = conversion*(c['onboarding_per_customer_cents']+c['prudential_buffer_months']*(c['support_per_customer_cents']+products*(cost+price*c['payment_fee_bps']/10000+c['payment_fixed_cents'])))
            contacts = min(contact_capacity, possible_contacts, math.floor((remaining-block_cost)/max(1, contact_cost+working_cash_per_lead)))
            acq_cost = contacts*contact_cost
            capacity_recovered = min(max(0., expected_existing-active_capacity), blocks*c['capacity_block_jobs'])
            benefit = contacts*conversion*customer_value + capacity_recovered*net_per_product*lifetime
            if channel_entries:
                customer_slots = max(0., future_spare/max(.01,products)-contacts*conversion)
                old_monthly_arrivals = max(.001,future_channels*c['channel_contacts_per_month']*conversion)
                new_monthly_arrivals = max(.001,(future_channels+channel_entries)*c['channel_contacts_per_month']*conversion)
                old_fill_delay = customer_slots/old_monthly_arrivals
                new_fill_delay = c['channel_entry_delay_months']+customer_slots/new_monthly_arrivals
                speed_value = max(0.,(1+c['discount_rate_monthly'])**(-new_fill_delay)-(1+c['discount_rate_monthly'])**(-old_fill_delay))
                # Only accelerated occupancy of paid capacity has incremental value; idle channels do not create value.
                benefit += customer_slots*max(0.,customer_value-contact_cost/max(.001,conversion))*speed_value
            score = benefit - entry_cost - block_cost - acq_cost
            score -= c['forecast_downside_penalty']*(entry_cost+block_cost+acq_cost)
            candidates.append({'kind': 'growth_bundle', 'contacts': contacts, 'channel_entries': channel_entries,
                'capacity_blocks': blocks, 'cost': entry_cost+block_cost+acq_cost,
                'predicted_net_cash': round(score), 'expected_activated_customers': contacts*conversion,
                'value_basis': 'Discounted recurring contribution with observed conversion, churn and physical capacity; acquisition, onboarding and infrastructure all costed.'})
    if controller in {'adaptive', 'ordinary_adaptive'}:
        if active and not state['retention']:
            price_retention = c['retention_entry_cost_cents']
            benefit = active*customer_value*c['monthly_churn_probability']*c['retention_churn_reduction']*lifetime-c['retention_monthly_cost_cents']*lifetime
            candidates.append({'kind': 'retention', 'cost': price_retention, 'predicted_net_cash': round(benefit-price_retention)})
        if active and not state['supplier_diversity']:
            fee = c['supplier_diversity_entry_cost_cents']
            avoided_loss = active*products*net_per_product*(c['supplier_outage_probability']-c['supplier_outage_probability']**2)*lifetime
            added_capacity = max(0., min(expected_existing, c['supplier_capacity_jobs']*2)-c['supplier_capacity_jobs'])*net_per_product*lifetime
            value = avoided_loss+added_capacity-c['supplier_diversity_monthly_cost_cents']*lifetime-fee
            candidates.append({'kind': 'supplier_diversity', 'cost': fee, 'predicted_net_cash': round(value)})
        if active and not state['instrument']:
            fee = c['instrument_entry_cost_cents']
            value = active*products*cost*c['instrument_attempt_cost_reduction']*lifetime-c['instrument_monthly_cost_cents']*lifetime-fee
            candidates.append({'kind': 'instrument', 'cost': fee, 'predicted_net_cash': round(value)})
        fee = c['new_service_entry_cost_cents']*(state['new_services']+1)
        expected_products = active*c['new_service_adoption_probability']/(state['new_services']+1)
        spare = max(0., active_capacity-expected_existing)
        value = min(expected_products, spare)*net_per_product*lifetime-fee
        candidates.append({'kind': 'new_service', 'cost': fee, 'predicted_net_cash': round(value), 'expected_new_products_per_customer': c['new_service_adoption_probability']/(state['new_services']+1)})
    feasible = [x for x in candidates if x['cost'] <= available and x['predicted_net_cash'] > 0]
    if not feasible:
        return candidates[0]
    if controller == 'ordinary_adaptive':
        return max(feasible, key=lambda x: (x['predicted_net_cash']/max(1,x['cost']), x['predicted_net_cash'], -x['cost']))
    return max(feasible, key=lambda x: (x['predicted_net_cash'], -x['cost']))


def simulate_scale(config, seed, controller='adaptive'):
    validate_config(config)
    if type(seed) is not int or seed < 0 or controller not in CONTROLLERS:
        raise ValueError('DECLARED_SCALE_CONTROLLER_AND_SEED_REQUIRED')
    c = copy.deepcopy(config)
    cash = c['opening_cash_cents']
    setup = c['setup_cost_cents'] + c['initial_customers']*c['onboarding_per_customer_cents']
    if setup > cash:
        return {'scope': SCOPE, 'controller': controller, 'seed': seed, 'cash_survival': False, 'terminal_reason': 'INITIAL_SETUP_UNFUNDED', 'monthly': [], 'milestones': {str(t): None for t in c['targets_annual_collected_cents']}, 'cumulative_collected_revenue_cents': 0, 'cumulative_profit_cents': 0, 'ending_cash_cents': cash, 'peak_additional_capital_needed_cents': setup-cash, 'binding_constraints': ['setup_cash']}
    cash -= setup
    expenses = setup
    active = c['initial_customers']
    capacity = c['initial_capacity_jobs']
    channels, capacity_queue, pipeline, receivables, reserves = [], [], [], [], []
    monthly, history = [], []
    cumulative_collected = recognized = 0
    exposed = ever_acquired = 0
    retention = diversity = instrument = False
    new_services = 0
    added_products = 0.
    estimated_conversion = c['qualification_probability']*c['choice_probability']*c['activation_probability']
    conversion_trials, conversion_wins = 20., estimated_conversion*20
    binding, milestones = set(), {str(t): None for t in c['targets_annual_collected_cents']}
    peak_need = 0
    unpaid_obligations = 0
    survived = True
    previous_desired = 0
    terminal_reason = 'HORIZON_COMPLETED'
    for month in range(1, c['months']+1):
        paid_now = sum(x['amount'] for x in receivables if x['due'] <= month)
        receivables = [x for x in receivables if x['due'] > month]
        cash += paid_now; cumulative_collected += paid_now
        history.append(paid_now)
        tax_passthrough = paid_now*c['sales_tax_bps']//10000
        if paid_now:
            reserves.append({'release': month+c['reserve_months'], 'amount': paid_now*c['reserve_bps']//10000})
        reserves = [x for x in reserves if x['release'] > month]
        restricted = sum(x['amount'] for x in reserves)
        capacity += sum(x['jobs'] for x in capacity_queue if x['ready'] <= month)
        capacity_queue = [x for x in capacity_queue if x['ready'] > month]
        shock = month == c['shock_month']
        churn = min(1., c['monthly_churn_probability']*(1-c['retention_churn_reduction'] if retention else 1)+(.15 if shock else 0))
        lost = _trials(seed, month, 'customer-churn', active, churn)
        active -= lost
        ready_leads = sum(x['customers'] for x in pipeline if x['due'] <= month)
        pipeline = [x for x in pipeline if x['due'] > month]
        onboarded = min(ready_leads, max(0, cash-restricted-c['liquidity_floor_cents'])//max(1, c['onboarding_per_customer_cents']))
        onboard_cost = onboarded*c['onboarding_per_customer_cents']
        cash -= onboard_cost; expenses += onboard_cost
        active += onboarded; ever_acquired += onboarded
        fixed = c['fixed_monthly_cost_cents']+active*c['support_per_customer_cents']
        fixed += c['retention_monthly_cost_cents'] if retention else 0
        fixed += c['supplier_diversity_monthly_cost_cents'] if diversity else 0
        fixed += c['instrument_monthly_cost_cents'] if instrument else 0
        if fixed > cash-restricted:
            peak_need = max(peak_need, fixed-max(0,cash-restricted))
            unpaid_obligations = fixed
            binding.add('operating_cash'); survived = False; terminal_reason = 'OPERATING_CASH_FAILURE'; break
        cash -= fixed; expenses += fixed
        price = max(1, round(c['price_per_work_product_cents']*((1-c['annual_price_compression'])**((month-1)/12))))
        unit_cost = math.ceil(c['attempt_cost_cents']*c['supplier_cost_multiplier']*(1-c['instrument_attempt_cost_reduction'] if instrument else 1)*(2 if shock else 1))
        action_traces = []
        contacts = 0
        planning_paid = rounds_used = 0
        # This bound is an explicit per-month planning compute budget, not a service/revenue ceiling.
        for planning_round in range(c['planning_rounds_per_month'] if controller != 'fixed_shares' else 1):
            if cash-restricted-c['liquidity_floor_cents'] < c['planner_round_cost_cents']:
                break
            cash -= c['planner_round_cost_cents']; expenses += c['planner_round_cost_cents']
            planning_paid += c['planner_round_cost_cents']; rounds_used += 1
            state = {'active': active, 'cash': cash, 'restricted': restricted, 'capacity': capacity, 'pending_capacity': capacity_queue,
                'channels': channels, 'retention': retention, 'supplier_diversity': diversity, 'instrument': instrument,
                'new_services': new_services, 'additional_expected_products': added_products,
                'pipeline': pipeline+[{'customers':round(contacts*estimated_conversion)}], 'price': price, 'unit_cost': unit_cost, 'contacts_bought':contacts,
                'estimated_conversion': estimated_conversion, 'exposed': exposed+contacts, 'previous_desired': previous_desired}
            decision = _controller_actions(c, state, controller, month)
            if decision['kind'] == 'retain_cash' or decision['cost'] <= 0:
                break
            if cash-restricted-c['liquidity_floor_cents'] < decision['cost']:
                raise AssertionError('FORECAST_SPEND_EXCEEDS_CURRENT_CASH')
            before_cash = cash
            cash -= decision['cost']; expenses += decision['cost']
            if decision['kind'] in {'growth_bundle','fixed_share_control'}:
                entries, blocks = decision['channel_entries'], decision['capacity_blocks']
                contacts += decision['contacts']
                if entries:
                    channels.append({'count': entries, 'ready': month+max(1,c['channel_entry_delay_months'])})
                if blocks:
                    capacity_queue.append({'jobs': blocks*c['capacity_block_jobs'], 'ready': month+max(1,c['capacity_delay_months'])})
            elif decision['kind'] == 'retention':
                retention = True
            elif decision['kind'] == 'supplier_diversity':
                diversity = True
            elif decision['kind'] == 'instrument':
                instrument = True
            elif decision['kind'] == 'new_service':
                new_services += 1; added_products += decision['expected_new_products_per_customer']
            action_traces.append({**decision, 'planning_round': planning_round, 'cash_before': before_cash, 'cash_after': cash,
                'execution_scope': 'Actual state transition in this projection only; no native money or real service-execution authority.'})
            # Further rounds may invest, but already purchased monthly channel exposures cannot be bought twice.
        exposed += contacts
        shock_conversion = .5 if shock else 1.
        qualified = _trials(seed, month, 'qualification', contacts, c['qualification_probability'])
        chosen = _trials(seed, month, 'buyer-choice', qualified, c['choice_probability']*shock_conversion)
        activated = _trials(seed, month, 'activation', chosen, c['activation_probability'])
        if activated:
            pipeline.append({'due':month+max(1,c['sales_cycle_months']), 'customers':activated})
        if contacts:
            conversion_trials += contacts; conversion_wins += activated
            estimated_conversion = conversion_wins/conversion_trials
        potential = active*c['base_products_per_customer']
        potential += _trials(seed, month, 'cross-sell-adoption', active*max(1,new_services), min(1.,added_products/max(1,new_services))) if new_services else 0
        desired = _trials(seed, month, 'utilization', potential, c['utilization_probability']*(.6 if shock else 1))
        desired += _trials(seed, month, 'legacy-extra-products', active*c['extra_products_per_customer'], min(1.,month*c['cross_sell_monthly_probability']))
        previous_desired = desired
        primary_out = _rng(seed,month,'primary-supplier').random() < c['supplier_outage_probability']
        fallback_out = _rng(seed,month,'fallback-supplier').random() < c['supplier_outage_probability']
        supplier_capacity = (0 if primary_out else c['supplier_capacity_jobs']) + (c['supplier_capacity_jobs'] if diversity and not fallback_out else 0)
        if supplier_capacity < desired:
            binding.add('supplier_capacity_or_outage')
        available = max(0,cash-restricted-c['liquidity_floor_cents'])
        worst_payment_fee_per_attempt = (price*c['payment_fee_bps']+9999)//10000+c['payment_fixed_cents']
        attempts = min(desired,capacity,supplier_capacity,available//max(1,unit_cost+worst_payment_fee_per_attempt))
        if attempts < desired:
            binding.add('capacity_or_delivery_cash')
            peak_need = max(peak_need,(desired-attempts)*unit_cost)
        delivery_cost = attempts*unit_cost
        cash -= delivery_cost; expenses += delivery_cost
        accepted = _trials(seed,month,'technical-quality',attempts,c['technical_acceptance_probability']*(.9 if shock else 1))
        paid = _trials(seed,month,'collections',accepted,c['collection_probability']*(.8 if shock else 1))
        refunded = _trials(seed,month,'refunds',paid,min(1.,c['refund_probability']*(3 if shock else 1)))
        net_revenue = (paid-refunded)*price
        fee = paid*c['payment_fixed_cents'] + paid*price*c['payment_fee_bps']//10000
        if fee > cash-restricted:
            peak_need=max(peak_need,fee-max(0,cash-restricted)); unpaid_obligations=fee; survived=False; terminal_reason='PAYMENT_FEE_CASH_FAILURE'; break
        cash -= fee; expenses += fee
        recognized += net_revenue
        if net_revenue:
            receivables.append({'amount':net_revenue,'due':month+max(1,c['settlement_months'])})
        trailing=sum(history[-12:])
        for target in c['targets_annual_collected_cents']:
            if milestones[str(target)] is None and month>=12 and trailing>=target:
                milestones[str(target)]=month
        if cash != c['opening_cash_cents']+cumulative_collected-expenses or cash<restricted:
            raise AssertionError('FORECAST_CASH_CONSERVATION')
        monthly.append({'month':month,'active_customers':active,'new_onboarded_customers':onboarded,'churned_customers':lost,
            'contacts':contacts,'activated_future_customers':activated,'exposed_unique_opportunities':exposed,
            'capacity_jobs':capacity,'channels_ready':1+sum(x['count'] for x in channels if x['ready']<=month),
            'supplier_diversity':diversity,'instrument':instrument,'retention':retention,'new_service_entries':new_services,
            'desired_work_products':desired,'attempted_projection_work_products':attempts,'accepted_projection_work_products':accepted,
            'collected_projection_work_products':paid-refunded,'cumulative_cost_cents':expenses,
            'cumulative_recognized_revenue_cents':recognized,'cumulative_collected_revenue_cents':cumulative_collected,
            'cumulative_profit_cents':recognized-expenses,'collected_revenue_cents':paid_now,
            'trailing_12_collected_revenue_cents':trailing,'annualized_collected_run_rate_cents':paid_now*12,
            'cash_cents':cash,'restricted_cash_cents':restricted,'available_cash_cents':cash-restricted,
            'tax_collected_and_remitted_cents':tax_passthrough,'estimated_conversion':estimated_conversion,
            'action_traces':action_traces,'planning_rounds_used':rounds_used,'planning_cost_cents':planning_paid,
            'planning_budget_exhausted':rounds_used==c['planning_rounds_per_month'] and controller!='fixed_shares'})
    return {'scope':SCOPE,'controller':controller,'seed':seed,'cash_survival':survived,'terminal_reason':terminal_reason,
        'monthly':monthly,'milestones':milestones,'cumulative_collected_revenue_cents':cumulative_collected,
        'cumulative_profit_cents':recognized-expenses-unpaid_obligations,'ending_cash_cents':cash,
        'cumulative_cost_cents':expenses+unpaid_obligations,'cumulative_expenses_paid_cents':expenses,
        'terminal_unpaid_obligations_cents':unpaid_obligations,
        'terminal_receivables_cents':sum(x['amount'] for x in receivables),'peak_additional_capital_needed_cents':peak_need,
        'binding_constraints':sorted(binding),'source_scope':'Conditional aggregate forecast; native Account remains the sole small-cohort financial authority.',
        'predictions_scope':'Discounted customer-value estimates guide current costed actions; future hypothetical receipts never pay present costs.',
        'matching_scope':'Same starting cash/parameters and keyed monthly demand, quality, payment and supplier shocks. Different customer counts lead to count-conditional aggregate binomial outcomes.',
        'control_action_scope': 'Adaptive and ordinary adaptive share all paid actions, physical channel/capacity delays, public observations and planning-round budget. Ordinary ranks public predicted value per upfront cost; adaptive ranks predicted joint net value. Fixed shares intentionally preserves a restricted historical policy control.',
        'small_cohort_anchor':c['small_cohort_anchor'],'assumptions':c['assumptions'],
        'investment_prediction_comparison': 'Each action trace reports discounted future net-cash prediction and immediate realized projection spend. Long-run prediction is not equated with same-month receipts; the complete native operating loop separately compares scoped predicted and settled outcomes.',
        'prudential_buffer_policy': {'months': c['prudential_buffer_months'], 'scope': 'Revisable policy for future uncommitted delivery, onboarding and support. Hard current fees and restricted obligations are separately protected. Fixed-share control retains its historical floor-only policy.'}}


def _quantile(values,q):
    return sorted(values)[max(0,min(len(values)-1,math.ceil(q*len(values))-1))] if values else None


def evaluate_scale(config,seeds):
    validate_config(config)
    if not isinstance(seeds,list) or not seeds or len(seeds)>128 or any(type(s)is not int or s<0 for s in seeds) or len(set(seeds))!=len(seeds):
        raise ValueError('FIXED_UNIQUE_PROJECTION_SEEDS_REQUIRED')
    controllers={}
    for controller in CONTROLLERS:
        runs=[simulate_scale(config,s,controller) for s in seeds]
        milestones={}
        for target in config['targets_annual_collected_cents']:
            times=[r['milestones'][str(target)] for r in runs]
            censored=[t if t is not None else config['months']+1 for t in times]
            quantiles={}
            for label,q in [('p10',.1),('p50',.5),('p90',.9)]:
                t=_quantile(censored,q); quantiles[label]=t if t<=config['months'] else None
            milestones[str(target)]={'reached':sum(t is not None for t in times),'not_reached':sum(t is None for t in times),
                'probability_within_horizon':sum(t is not None for t in times)/len(times),'times_months_with_censoring':times,
                'unconditional_censored_quantiles_months':quantiles,'basis':'Trailing 12 collected revenue, never annualized run rate. None includes nonreach and early cash failure.'}
        controllers[controller]={'trajectories':runs,'milestones':milestones,
            'cash_survival_fraction':sum(r['cash_survival'] for r in runs)/len(runs),
            'profit_cents':[r['cumulative_profit_cents'] for r in runs],
            'peak_additional_capital_needed_cents':max(r['peak_additional_capital_needed_cents'] for r in runs),
            'binding_constraints':sorted(set().union(*(set(r['binding_constraints']) for r in runs)))}
    comparisons=[]
    for index,seed in enumerate(seeds):
        baseline=controllers['fixed_shares']['trajectories'][index]
        adaptive=controllers['adaptive']['trajectories'][index]
        ordinary=controllers['ordinary_adaptive']['trajectories'][index]
        comparisons.append({'seed':seed,'adaptive_minus_fixed_collected_cents':adaptive['cumulative_collected_revenue_cents']-baseline['cumulative_collected_revenue_cents'],
            'adaptive_minus_fixed_profit_cents':adaptive['cumulative_profit_cents']-baseline['cumulative_profit_cents'],
            'adaptive_minus_ordinary_profit_cents':adaptive['cumulative_profit_cents']-ordinary['cumulative_profit_cents'],
            'adaptive_cash_survival':adaptive['cash_survival'],'fixed_cash_survival':baseline['cash_survival']})
    return {'schema':'agi-alpha/adaptive012-scale-comparison/v1','scope':SCOPE,'currency':'USD','money_unit':'cents',
        'horizon_months':config['months'],'config':config,'seeds':seeds,'controllers':controllers,'paired_comparisons':comparisons,
        'conclusion':'Policy comparisons under disclosed hypotheses. Nonreach by a controller is not impossibility for all controllers. Positive projected revenue is not audited actual service receipts.',
        'capital_needs_basis':'Largest encountered unfunded desired delivery or operating cash gap; no outside cash injected and not a solved minimum-capital theorem.'}
