"""Event-time operating controller over the qualified service/native-money path.

All prices, arrivals and unmetered costs are conditional assumptions. This module
changes operating policy, not the deterministic service acceptance contracts.
"""
from __future__ import annotations
import copy
import hashlib
import heapq
import math
from pathlib import Path
import tempfile
import time
from commercial.ledger import canonical, digest, load_jobs, audit
from enterprise.model import default_policy, money, seller_observation
from enterprise.pricing import probabilities, utilities
from enterprise.services import execute_job

SCHEMA = 'agi-alpha/growth012-world/v1'
CONTROLLERS = ('baseline', 'simple', 'joint')


def default_config():
    p = default_policy()
    return {'schema': 'agi-alpha/growth012-config/v1', 'scope': 'SIMULATED',
            'currency': 'simulated-microUSD', 'time_unit': 'hours',
            'horizon_hours': 90 * 24, 'opening': p['opening'], 'working': p['working'],
            'setup_cost': p['setup_cost'], 'policy': p, 'market_regime': 'ordinary',
            'choice_model': 'logit', 'human_ai_complete_cost_ratio': .60, 'human_ai_delivery_hours': 12, 'customer_pool': 48, 'contacts_per_day': 24,
            'initial_capacity': 1, 'maximum_capacity': 8, 'capacity_block_cost': money(12),
            'production_hours': 2, 'sales_cycle_hours': 6, 'settlement_hours': 48,
            'repeat_interval_hours': 14 * 24, 'retention_probability': .94,
            'rival_update_hours': 7 * 24, 'daily_overhead': money(.25),
            'liquidity_floor': money(100), 'allocation_cap': money(100_000),
            'baseline_acquisition_fraction': .16, 'baseline_capacity_fraction': .25,
            'risk_accepted_workload_quantile_z': 1.645,
            'intervention_setup_cost': 0, 'intervention_daily_cost': 0,
            'finite_liability_hours': None, 'arrangement_cost': money(5),
            'finite_contract_fee_bps': 50, 'finite_contract_customer_friction_usd': 2.,
            'targets_collected_microUSD': [money(500), money(1000), money(1_000_000), money(10_000_000), money(100_000_000), money(1_000_000_000), money(10_000_000_000)],
            'assumptions': 'Authored finite buyer demand, private budgets, delayed rivals and cash-contract hypotheses. Exact service tools/checkers are reused unchanged. No market calibration or real revenue. A distinct competent human-plus-AI complete service is assumed to cost60percent of equivalent human complete cost with12hour delivery; this includes customer effort rather than comparing a software subscription to a service. Native permanent principal-plus-fee tail remains in all first-comparison arms. Exact workload stock is an experimental qualification boundary, never an economic law. No external funds are added.'}


def validate_config(c):
    if not isinstance(c, dict) or set(c) != set(default_config()):
        raise ValueError('EXACT_GROWTH012_CONFIG_REQUIRED')
    for k in ('schema', 'scope', 'currency', 'time_unit'):
        if c[k] != default_config()[k]:
            raise ValueError('GROWTH012_SCOPE_UNIT_REQUIRED')
    for k, v in default_config().items():
        if type(v) is int and (type(c[k]) is not int or c[k] < 0):
            raise ValueError('NONNEGATIVE_INTEGER_GROWTH_INPUT:' + k)
        if type(v) is float and (type(c[k]) not in (int, float) or not math.isfinite(c[k]) or c[k] < 0):
            raise ValueError('FINITE_GROWTH_INPUT:' + k)
    if not 1 <= c['horizon_hours'] <= 24 * 3650 or not 1 <= c['customer_pool'] <= 10000 or not 1 <= c['initial_capacity'] <= c['maximum_capacity'] <= 1000 or c['production_hours'] <= 0 or c['repeat_interval_hours'] <= 0 or c['rival_update_hours'] <= 0 or c['contacts_per_day'] > 10000:
        raise ValueError('FINITE_THROUGHPUT_AND_MARKET_REQUIRED')
    if c['market_regime'] not in c['policy']['regimes'] or c['choice_model'] not in ('logit', 'utility'):
        raise ValueError('DECLARED_MARKET_FAMILY_REQUIRED')
    for k in ('retention_probability', 'baseline_acquisition_fraction', 'baseline_capacity_fraction'):
        if c[k] > 1:
            raise ValueError('PROBABILITY_OR_FRACTION_RANGE:' + k)
    if c['finite_liability_hours'] is not None and (type(c['finite_liability_hours']) is not int or c['finite_liability_hours'] < 1):
        raise ValueError('POSITIVE_FINITE_LIABILITY_HOURS_REQUIRED')
    if c['finite_contract_fee_bps'] > 10000 or not c['targets_collected_microUSD'] or any(type(x) is not int or x <= 0 for x in c['targets_collected_microUSD']) or len(set(c['targets_collected_microUSD'])) != len(c['targets_collected_microUSD']):
        raise ValueError('DECLARED_POSITIVE_TARGETS_REQUIRED')
    from enterprise.model import validate_policy
    validate_policy(c['policy'])
    return c


def keyed_draw(seed, tick, buyer, kind):
    return int.from_bytes(hashlib.sha256(canonical(['growth012', seed, tick, buyer, kind])).digest()[:8], 'big') / 2**64


def _utilities6(value, ours, rival, public, regime):
    base = utilities(value,ours,rival,public,regime)
    hybrid = .99*.97*value - public['anchor_usd']*regime['human_ai_complete_cost_ratio'] - regime['human_ai_delivery_hours']*public['urgency_value_hour']
    return base[:3] + [hybrid] + base[3:]


def _expected_choice6(ours,rival,public,regime,model):
    total = [0.]*6
    for factor in [1.3,1.7,2.1,2.5,2.9,3.3,3.7]:
        row = probabilities(_utilities6(public['anchor_usd']*factor,ours,rival,public,regime),model,max(.01,public['anchor_usd']*regime['temperature_ratio']))
        total = [a+b/7 for a,b in zip(total,row)]
    return total


def _rival_response(ours,public,regime,model):
    cost = public['autonomous_cost_usd']*regime['rival_cost_multiplier']
    prices = [cost*1.03]+[public['anchor_usd']*i/10 for i in range(2,21,2)]
    gain,price = max(((_expected_choice6(ours,price,public,regime,model)[1]*(price-cost),price) for price in prices),key=lambda x:(x[0],x[1]))
    return {'price':price if gain>0 else public['anchor_usd']*10,'expected_profit':max(0.,gain),'cost':cost,'response':'delayed_public_six_alternative_finite_best_response'}


def _quote(public, regime, model, rival_price):
    anchor = public['anchor_usd']
    candidates = [anchor * (.2 + i * .05) for i in range(37)]
    curve = []
    for price in candidates:
        win = _expected_choice6(price, rival_price, public, regime, model)[0]
        exposure = regime['arrival_probability'] * regime['qualification_probability'] * (1-regime['supplier_outage_probability'])
        net = price * (regime['collection_probability'] * (1 - regime['refund_probability']) - public['payment_fraction']) - public['payment_fixed_usd'] - public['autonomous_cost_usd'] - public['onboarding_cost_usd']
        curve.append({'price': price, 'conditional_win_probability': win,
                      'incremental_collected_contribution': exposure * win * net - regime['quote_cost_usd'],
                      'contribution_per_won_order': net})
    best = max(curve, key=lambda x: (x['incremental_collected_contribution'], -x['price']))
    return {**best, 'rival_price': rival_price, 'human_anchor_usd': anchor,
            'no_bid': best['incremental_collected_contribution'] <= 0,
            'search_scope': 'Best tested premium/human-anchor finite price menu versus current observed rival quote; future/private draws absent.'}


def run_growth(root, manifest, config, seed, controller='joint', output=None, persist=True):
    validate_config(config)
    if controller not in CONTROLLERS or type(seed) is not int or seed < 0:
        raise ValueError('DECLARED_CONTROLLER_AND_SEED_REQUIRED')
    from commercial.single_writer import SingleWriterExchange
    from enterprise.finance012 import AuditedAllocation
    started_wall, started_cpu = time.monotonic(), time.process_time()
    root, c = Path(root), copy.deepcopy(config)
    p, regime = c['policy'], copy.deepcopy(c['policy']['regimes'][c['market_regime']])
    regime['quote_cost_usd'] = p['costs_usd']['quote_acquisition'] * p['cost_multiplier']
    regime['retention_probability'] = c['retention_probability']
    regime['our_hours'] = c['production_hours']
    regime['human_ai_complete_cost_ratio'] = c['human_ai_complete_cost_ratio']
    regime['human_ai_delivery_hours'] = c['human_ai_delivery_hours']
    jobs = load_jobs(root, manifest)
    by_service = {}
    for job_id, record in sorted(jobs.items()):
        by_service.setdefault(record['job']['service_id'], []).append(job_id)
    services = sorted(by_service)
    if set(services) != set(p['human_services']):
        raise ValueError('SAME_THREE_QUALIFIED_SERVICES_REQUIRED')
    temporary = tempfile.TemporaryDirectory(prefix='growth012-')
    destination = Path(output) if output is not None else Path(temporary.name) / 'run'
    destination.mkdir(parents=True, exist_ok=False)
    contract = 'growth012/' + digest({'config': c, 'manifest': manifest, 'seed': seed, 'controller': controller})
    kwargs = dict(root=root, manifest=manifest, opening=c['opening'], working=c['working'], contract=contract, durable=persist)
    if c['finite_liability_hours'] is None:
        exchange = SingleWriterExchange(destination / 'exchange.sqlite', **kwargs)
    else:
        from enterprise.contract012 import OwnedFiniteExchange
        exchange = OwnedFiniteExchange(destination / 'exchange.sqlite', liability_ticks=c['finite_liability_hours'], time_unit='hours', arrangement_cost=c['arrangement_cost'], **kwargs)
        exchange.execute('arrange', {}, 0)
    gate = AuditedAllocation(exchange, root=root, manifest=manifest, allocation_id=contract, cap=c['allocation_cap'])
    histories = {f'SIM-buyer-{i:04d}': {'id': f'SIM-buyer-{i:04d}', 'service': services[i % len(services)], 'purchases': 0, 'onboarded': False, 'trust': regime['trust'], 'last_contact': -c['repeat_interval_hours'], 'last_purchase': None, 'next_due': 0, 'active': True} for i in range(c['customer_pool'])}
    private = {buyer: {'factor': 1.3 + 2.4 * keyed_draw(seed, -1, buyer, 'reservation'), 'budget': 500 + 1500 * keyed_draw(seed, -1, buyer, 'budget')} for buyer in histories}
    events, decisions, work, receipts, rejected = [], [], [], [], []
    queue, seq, consumed, outstanding = [], 0, set(), {}
    capacity, busy, quotes, rival_prices, last_our_price = c['initial_capacity'], 0, {}, {}, {}
    win_count, offer_count, earned_deliveries, earned_spent, acquisition_earned = 0, 0, 0, 0, 0
    counters = {'contacts': 0, 'qualified': 0, 'won': 0, 'accepted': 0, 'paid': 0, 'refunds': 0, 'capacity_blocks': 0, 'withdrawn_orders': 0}
    production_cost = money(sum(p['costs_usd'][k] for k in ['inference_tools_production', 'independent_verification_corrections', 'compute_storage_infrastructure', 'delivery_support_obligation', 'maintenance_failure_retry']) * regime['supplier_multiplier'] * p['cost_multiplier'])
    acquisition_cost = money(p['costs_usd']['quote_acquisition'] * p['cost_multiplier'])
    onboard_cost = money((p['costs_usd']['autonomous_onboarding_once'] + p['costs_usd']['external_onboarding_fee']) * p['cost_multiplier'])
    last_taxable, cumulative_tax, contacts_day, current_day, qualified_boundary = 0, 0, 0, -1, None
    pending_sales = 0
    baseline_budget = {'month':-1,'acquisition':0,'capacity':0,'spent_acquisition':0,'spent_capacity':0}
    def push(tick, kind, data=None):
        nonlocal seq
        seq += 1
        heapq.heappush(queue, (tick, seq, kind, data or {}))
    def log_event(tick, kind, **fields):
        events.append({'time': tick, 'kind': kind, **fields})
    def charge(ident, amount, tick, category, predicted=0, artifact_hash=None):
        nonlocal earned_spent
        if not amount:
            return None
        before = exchange.snapshot()
        if before['available'] < amount:
            raise ValueError('COMMITMENT_WITHOUT_AVAILABLE_CASH')
        plan = None
        if before['unrestrictedEarned'] >= amount and predicted > 0:
            plan = gate.plan(ident, amount, max(1, predicted), intent={'id': ident, 'category': category, 'time': tick, 'cost': amount})
            gate.reserve(plan, tick)
            if artifact_hash is not None:
                gate.finish(plan, amount, artifact_hash, tick)
                earned_spent += amount
        else:
            exchange.execute('cost', {'id': ident, 'amount': amount}, tick)
        receipts.append({'id': ident, 'time': tick, 'category': category, 'amount': amount, 'funding': 'PRIOR_UNRESTRICTED_EARNINGS' if plan else 'SEED_OR_REMAINING_LIQUIDITY', 'cost_evidence': p['cost_evidence']})
        return plan
    def action_record(kind, tick, cash, value, payback, downside, feasible, reason=None, cls=None, **extras):
        return {'id': kind, 'kind': kind, 'cash_required': cash, 'projected_contribution': value, 'payback_hours': payback, 'downside': downside, 'feasible': bool(feasible), 'reason': reason, 'constraint_class': cls, **extras}
    def decision(tick, selected, candidates, observation, realized):
        observation['native_actions_through'] = len(exchange.export()['actions'])
        record = {'id': f'decision-{len(decisions)}', 'time': tick, 'observation': observation,
                  'observation_sha256': digest(observation), 'feasible_actions': candidates,
                  'selected_action': selected, 'projected_contribution': next((x['projected_contribution'] for x in candidates if x['id'] == selected), 0),
                  'cash_required': next((x['cash_required'] for x in candidates if x['id'] == selected), 0),
                  'binding_constraint': [x['reason'] for x in candidates if not x['feasible']],
                  'realized_outcome': realized}
        record['action_sha256'] = digest([record['id'], selected, record['projected_contribution'], record['cash_required']])
        decisions.append(record)
        rejected.extend({'decision': record['id'], 'time': tick, **x} for x in candidates if not x['feasible'])
        return record
    for service in services:
        h = {'onboarded': False, 'trust': regime['trust']}
        public = seller_observation(p, regime, service, h)
        rival_prices[service] = max(public['autonomous_cost_usd'] * regime['rival_cost_multiplier'] * 1.1, public['anchor_usd'] * .85)
        last_our_price[service] = public['anchor_usd'] * .95
    try:
        if exchange.snapshot()['available'] < c['setup_cost']:
            raise ValueError('INITIAL_SETUP_UNFUNDED')
        charge('growth012-development-setup', c['setup_cost'], 0, 'all_development_qualification_and_failures')
        charge('growth012-intervention-setup', c['intervention_setup_cost'], 0, 'additional_contract_channel_or_retention_construction')
        for tick in range(0, c['horizon_hours'], 24):
            push(tick, 'overhead')
        push(0, 'decide')
        for tick in range(c['rival_update_hours'], c['horizon_hours'], c['rival_update_hours']):
            push(tick, 'rival')
        while queue:
            tick, _, kind, data = heapq.heappop(queue)
            if tick > c['horizon_hours']:
                continue
            if current_day != tick // 24:
                current_day, contacts_day = tick // 24, 0
            if kind == 'overhead':
                if exchange.snapshot()['available'] < c['daily_overhead'] + c['intervention_daily_cost']:
                    log_event(tick, 'PROFITABLE_WITHDRAWAL', reason='UNFUNDED_OPTIONAL_FUTURE_OPERATIONS; no existing order abandoned')
                    continue
                charge(f'overhead-{tick}', c['daily_overhead'] + c['intervention_daily_cost'], tick, 'machine_maintenance_infrastructure_and_intervention_ongoing_resources')
            elif kind == 'rival':
                for service in services:
                    public = seller_observation(p, regime, service, {'onboarded': True, 'trust': regime['trust']})
                    result = _rival_response(last_our_price[service], public, regime, c['choice_model'])
                    old = rival_prices[service]
                    rival_prices[service] = result['price']
                    log_event(tick, 'RIVAL_RESPONSE', service=service, observed_our_price=last_our_price[service], prior_price=old, price=result['price'], information='Own declared costs and previously public seller quote, no latent buyer values/future shocks')
                quotes.clear()
            elif kind == 'sale':
                pending_sales -= 1
                h, quote, oid = histories[data['buyer']], data['quote'], data['order_id']
                period = tick // c['repeat_interval_hours']
                arrived = keyed_draw(seed, period, h['id'], 'arrival') < regime['arrival_probability']
                qualified = keyed_draw(seed, period, h['id'], 'qualification') < regime['qualification_probability']
                if h['purchases'] and keyed_draw(seed, period, h['id'], 'retention') >= c['retention_probability']:
                    h['active'] = False
                eligible = h['active'] or keyed_draw(seed, period, h['id'], 'reacquisition') < regime['reacquisition_probability']
                public = data['public']
                us = _utilities6(public['anchor_usd'] * private[h['id']]['factor'] * regime['demand_value_multiplier'], quote['price'], quote['rival_price'], public, regime)
                probs = probabilities(us, c['choice_model'], max(.01, public['anchor_usd'] * regime['temperature_ratio']))
                toss, total, pick = keyed_draw(seed, period, h['id'], 'choice-' + h['service']), 0., 4
                for option, probability in enumerate(probs):
                    total += probability
                    if toss < total:
                        pick = option
                        break
                wins = arrived and qualified and eligible and pick == 0 and us[0] >= 0 and private[h['id']]['budget'] >= quote['price']
                counters['qualified'] += int(arrived and qualified)
                offer_count += 1
                win_count += int(wins)
                if not wins:
                    data['decision']['realized_outcome']['outcomes'].append({'buyer': h['id'], 'outcome': 'NO_PURCHASE', 'outside_choice': ['our_service','rival_ai','human_service','human_plus_ai_complete_service','self_service','no_purchase'][pick], 'arrived': arrived, 'qualified': qualified})
                    continue
                counters['won'] += 1
                available_ids = [j for j in by_service[h['service']] if j not in consumed]
                price = money(quote['price'])
                fee = (price * (p['payment_bps'] + (c['finite_contract_fee_bps'] if c['finite_liability_hours'] is not None else 0)) + 9999) // 10000 + p['payment_fixed']
                cost = production_cost + (0 if h['onboarded'] else onboard_cost) + fee
                before = exchange.snapshot()
                supplier_unavailable = keyed_draw(seed,tick//24,'supplier','outage') < regime['supplier_outage_probability']
                reason = 'SUPPLIER_OUTAGE' if supplier_unavailable else 'QUALIFIED_WORKLOAD_STOCK' if not available_ids else 'MEASURED_EXECUTION_CAPACITY' if busy >= capacity else 'COLLATERAL_AND_COMPLETE_DELIVERY_CASH' if before['available'] < cost + price + c['liquidity_floor'] else None
                if reason:
                    data['decision']['realized_outcome']['outcomes'].append({'buyer':h['id'],'outcome':'DECLINED_BEFORE_COMMITMENT','reason':reason})
                    counters['withdrawn_orders'] += 1
                    decision(tick, 'decline', [action_record('fulfill', tick, cost + price, money(quote['contribution_per_won_order']), c['production_hours'] + c['settlement_hours'], cost, False, reason, 'measured_resource_limit' if reason != 'COLLATERAL_AND_COMPLETE_DELIVERY_CASH' else 'real_obligation_or_authorization_boundary'), action_record('decline',tick,0,0,0,0,True)], {'snapshot': before, 'buyer_public': copy.deepcopy(h), 'current_orders': busy}, {'outcome': 'DECLINED_BEFORE_ACCEPTING_OBLIGATION'})
                    if not available_ids and qualified_boundary is None:
                        qualified_boundary = tick
                    continue
                job_id = available_ids[0]
                consumed.add(job_id)
                plan = charge(oid + '-complete-delivery', cost, tick, 'production_verification_onboarding_support_fee', money(max(.01, quote['contribution_per_won_order'])))
                exchange.execute('wallet', {'buyer': oid + '-wallet', 'amount': price}, tick)
                exchange.execute('offer', {'id': oid, 'buyer': oid + '-wallet', 'price': price, 'job_id': job_id, 'deadline': tick + c['production_hours'] + c['settlement_hours'] + 24}, tick)
                for action in ['consent','fund']:
                    exchange.execute('event', {'id': oid, 'action': action, 'event_id': oid + '-' + action}, tick)
                commitment_seq = len(exchange.export()['actions']) - 1
                busy += 1
                h['onboarded'] = True
                outstanding[oid] = {'buyer': h['id'], 'job_id': job_id, 'price': price, 'plan': plan, 'cost': cost, 'fund_time': tick, 'commitment_seq': commitment_seq, 'decision': data['decision']}
                push(tick + c['production_hours'], 'production', {'id': oid})
                log_event(tick, 'ACCEPTED_ORDER', order_id=oid, buyer=h['id'], job_id=job_id, price=price, committed_complete_cost=cost, earned_funded=bool(plan))
            elif kind == 'production':
                oid, order = data['id'], outstanding[data['id']]
                receipt = execute_job(root, jobs[order['job_id']]['job'])
                if order['plan']:
                    gate.finish(order['plan'], order['cost'], receipt['artifact_sha256'], tick)
                    earned_spent += order['cost']
                    earned_deliveries += 1
                exchange.execute('event', {'id': oid, 'action': 'prepare', 'event_id': oid + '-prepare'}, tick)
                work.append({'order_id': oid, 'job_id': order['job_id'], 'time': tick, 'commitment_action_seq': order['commitment_seq'], 'receipt': receipt, 'earned_funded': bool(order['plan'])})
                busy -= 1
                counters['accepted'] += 1
                push(tick + c['settlement_hours'], 'settlement', {'id': oid})
                log_event(tick, 'ACTUAL_SERVICE_ACCEPTED', order_id=oid, job_id=order['job_id'], artifact_sha256=receipt['artifact_sha256'])
            elif kind == 'settlement':
                oid, order = data['id'], outstanding.pop(data['id'])
                h = histories[order['buyer']]
                period = order['fund_time'] // c['repeat_interval_hours']
                collected = keyed_draw(seed, period, h['id'], 'collection') < regime['collection_probability']
                refunded = keyed_draw(seed, period, h['id'], 'refund') < regime['refund_probability']
                action = 'release' if collected and not refunded else 'refund'
                exchange.execute('event', {'id': oid, 'action': action, 'event_id': oid + '-' + action}, tick)
                if action == 'release':
                    h['purchases'] += 1
                    h['last_purchase'], h['active'], h['next_due'] = tick, True, tick + c['repeat_interval_hours']
                    private[h['id']]['budget'] -= order['price'] / 1_000_000
                    counters['paid'] += 1
                    if c['finite_liability_hours'] is not None:
                        push(tick + c['finite_liability_hours'], 'mature', {'id': oid})
                else:
                    counters['refunds'] += 1
                    h['next_due'] = tick + c['repeat_interval_hours']
                order['decision']['realized_outcome']['outcomes'].append({'buyer': h['id'], 'order_id': oid, 'outcome': 'SIMULATED_SETTLED' if action == 'release' else 'SIMULATED_REFUNDED', 'price': order['price'], 'complete_delivery_cost': order['cost'], 'collection_time': tick})
                log_event(tick, 'COLLECTION' if action == 'release' else 'REFUND', order_id=oid, amount=order['price'] if action == 'release' else 0)
                taxable = max(0, exchange.snapshot()['profit'] + cumulative_tax)
                tax = max(0, taxable - last_taxable) * p['profit_tax_bps'] // 10000
                if tax:
                    charge(oid + '-profit-tax', tax, tick, 'conditional_positive_profit_tax')
                cumulative_tax += tax
                last_taxable = max(last_taxable, taxable)
            elif kind == 'mature':
                exchange.execute('mature', {'id': data['id'], 'event_id': data['id'] + '-mature'}, tick)
                log_event(tick, 'CONTRACT_LIABILITY_EXPIRED', order_id=data['id'])
            elif kind == 'decide':
                if tick + c['sales_cycle_hours'] + c['production_hours'] + c['settlement_hours'] > c['horizon_hours']:
                    continue
                before = exchange.snapshot()
                if controller=='baseline' and baseline_budget['month'] != tick//(30*24):
                    baseline_budget.update(month=tick//(30*24), acquisition=int(before['available']*c['baseline_acquisition_fraction']), capacity=int(before['available']*c['baseline_capacity_fraction']), spent_acquisition=0,spent_capacity=0)
                eligible = [h for h in histories.values() if h['next_due'] <= tick and tick - h['last_contact'] >= c['repeat_interval_hours'] and any(j not in consumed for j in by_service[h['service']])]
                eligible.sort(key=lambda h: (-int(h['purchases'] > 0), h['id']))
                forecast_win = (win_count + 2) / (offer_count + 5)
                prospective_contacts = min(len(eligible), max(0,c['contacts_per_day'] - contacts_day))
                expected_load = forecast_win * prospective_contacts + busy + pending_sales * forecast_win
                conservative_load = expected_load + c['risk_accepted_workload_quantile_z'] * math.sqrt(max(0, prospective_contacts * forecast_win * (1-forecast_win)))
                future_margin_rows = []
                for service in services:
                    context = seller_observation(p,regime,service,{'onboarded':True,'trust':regime['trust']})
                    if c['finite_liability_hours'] is not None:
                        context['friction_usd'] += c['finite_contract_customer_friction_usd']
                        context['payment_fraction'] += c['finite_contract_fee_bps']/10000
                    key = digest([context,regime,c['choice_model'],rival_prices[service]])
                    if key not in quotes:
                        quotes[key] = _quote(context,regime,c['choice_model'],rival_prices[service])
                    future_margin_rows.append(max(0.,quotes[key]['contribution_per_won_order']))
                remaining_cycles = max(0,(c['horizon_hours']-tick)//c['repeat_interval_hours'])
                margin_per_incremental_slot = sum(future_margin_rows)/len(future_margin_rows) * sum(c['retention_probability']**i for i in range(remaining_cycles))
                capacity_value = money(min(1.,max(0.,expected_load-capacity)) * margin_per_incremental_slot) - c['capacity_block_cost']
                observation = {'snapshot': before, 'current_orders': busy, 'pending_sales': pending_sales, 'capacity': capacity, 'eligible_contacts': len(eligible), 'customer_history': [{'id':h['id'],'purchases':h['purchases'],'onboarded':h['onboarded'],'next_due':h['next_due']} for h in histories.values()], 'demand_signals': {'own_quoted': offer_count, 'own_wins': win_count, 'posterior_win_probability': forecast_win}, 'forecast_accepted_workload': expected_load, 'forecast_upper_workload': conservative_load, 'capacity_incremental_margin_basis': margin_per_incremental_slot, 'rival_public_prices': dict(rival_prices), 'source_manifest_sha256': digest(manifest)}
                candidates = [action_record('retain_cash',tick,0,0,0,0,True)]
                candidates.append(action_record('capacity',tick,c['capacity_block_cost'],capacity_value, c['production_hours'] + c['settlement_hours'],c['capacity_block_cost'], capacity < c['maximum_capacity'] and before['available'] >= c['capacity_block_cost'] + c['liquidity_floor'] and expected_load > capacity, 'NO_SUPPORTED_EXCESS_ACCEPTED_WORKLOAD' if expected_load <= capacity else 'CAPACITY_OR_ELIGIBLE_FUNDS', 'uncertain_market_assumption'))
                batches = sorted(set(min(x,len(eligible), max(0,c['contacts_per_day']-contacts_day)) for x in [1,2,4,8,16,c['contacts_per_day']]))
                for n in batches:
                    if n <= 0:
                        continue
                    subset, qrows = eligible[:n], []
                    for h in subset:
                        public = seller_observation(p,regime,h['service'],h)
                        if c['finite_liability_hours'] is not None:
                            public['friction_usd'] += c['finite_contract_customer_friction_usd']
                            public['payment_fraction'] += c['finite_contract_fee_bps']/10000
                        key = digest([public,regime,c['choice_model'],rival_prices[h['service']]])
                        if key not in quotes:
                            quotes[key] = _quote(public,regime,c['choice_model'],rival_prices[h['service']])
                        qrows.append((h,public,quotes[key]))
                    projected = money(sum(q['incremental_collected_contribution'] for _,_,q in qrows))
                    expected = n * forecast_win
                    # Quote cash is spent now; forecast collateral is a feasibility bound,
                    # not spendable future collections and not an extra accounting cost.
                    collateral = money(max(q['price'] for _,_,q in qrows)) * math.ceil(expected)
                    cashneed = n * acquisition_cost + math.ceil(expected) * (production_cost + onboard_cost) + collateral
                    room = max(0,(capacity-busy) - pending_sales*forecast_win)
                    feasible = projected > 0 and before['available'] >= cashneed + c['liquidity_floor'] and expected + c['risk_accepted_workload_quantile_z'] * math.sqrt(n*forecast_win*(1-forecast_win)) <= room
                    reason = None if feasible else 'NONPOSITIVE_MARGINAL_CONTRIBUTION' if projected <= 0 else 'CURRENT_ELIGIBLE_CASH_AND_RESERVES' if before['available'] < cashneed+c['liquidity_floor'] else 'ACCEPTED_WORKLOAD_CAPACITY'
                    if controller == 'baseline' and n * acquisition_cost + baseline_budget['spent_acquisition'] > baseline_budget['acquisition']:
                        feasible, reason = False, 'BASELINE_FIXED_ACQUISITION_SHARE'
                    candidates.append(action_record('acquire-'+str(n),tick,cashneed,projected,c['sales_cycle_hours']+c['production_hours']+c['settlement_hours'],n*acquisition_cost,feasible,reason, 'controller_defect_or_arbitrary_heuristic' if reason == 'BASELINE_FIXED_ACQUISITION_SHARE' else 'real_obligation_or_authorization_boundary' if reason == 'CURRENT_ELIGIBLE_CASH_AND_RESERVES' else 'measured_resource_limit' if reason == 'ACCEPTED_WORKLOAD_CAPACITY' else 'uncertain_market_assumption', count=n, expected_accepted_workload=expected, quoted_work=qrows))
                choices = [x for x in candidates if x['feasible'] and x['projected_contribution'] > 0]
                if controller == 'baseline' and candidates[1]['cash_required'] + baseline_budget['spent_capacity'] > baseline_budget['capacity']:
                    candidates[1]['feasible'], candidates[1]['reason'] = False, 'BASELINE_FIXED_CAPACITY_SHARE'
                    choices = [x for x in choices if x['id'] != 'capacity']
                if controller == 'simple':
                    chosen = max(choices, key=lambda x:(x['projected_contribution']/max(1,x['cash_required']),x.get('count',0)), default=candidates[0])
                else:
                    chosen = max(choices, key=lambda x:(x['projected_contribution'], -x['cash_required']), default=candidates[0])
                clean = [{k:v for k,v in x.items() if k != 'quoted_work'} for x in candidates]
                record = decision(tick,chosen['id'],clean,observation,{'outcomes':[]})
                if chosen['id'] == 'capacity':
                    charge(f'capacity-{capacity}',c['capacity_block_cost'],tick,'costed_machine_capacity',chosen['projected_contribution'],digest(['capacity',capacity+1]))
                    capacity += 1
                    baseline_budget['spent_capacity'] += c['capacity_block_cost']
                    counters['capacity_blocks'] += 1
                    record['realized_outcome']['outcomes'].append({'outcome':'CAPACITY_CONSTRUCTED','new_capacity':capacity})
                elif chosen['id'].startswith('acquire-'):
                    actual = chosen['count'] * acquisition_cost
                    record['actual_acquisition_cost'] = actual
                    baseline_budget['spent_acquisition'] += actual
                    plan = charge(record['id']+'-acquisition',actual,tick,'agent_acquisition_all_quotes_including_losses',chosen['projected_contribution'],digest([h['id'] for h,_,_ in chosen['quoted_work']]))
                    acquisition_earned += actual if plan else 0
                    for h,public,quote in chosen['quoted_work']:
                        h['last_contact'] = tick
                        contacts_day += 1
                        counters['contacts'] += 1
                        last_our_price[h['service']] = quote['price']
                        pending_sales += 1
                        push(tick+c['sales_cycle_hours'],'sale',{'buyer':h['id'],'public':public,'quote':quote,'order_id':f'SIM-order-{counters["contacts"]:05d}','decision':record})
                else:
                    record['realized_outcome']['outcomes'].append({'outcome':'CASH_RETAINED','available':before['available']})
                # A reporting-clock baseline completes its finite allocation batch at the
                # reporting event; it is not forced to choose only one purchase/month.
                # Capacity strictly rises or remaining contacts strictly fall, so
                # zero-time allocation batching cannot create an infinite loop.
                cadence = (0 if chosen['id'] != 'retain_cash' else 30*24) if controller == 'baseline' else (1 if choices else 6)
                push(tick+cadence,'decide')
        tape = exchange.export()
    finally:
        if hasattr(gate,'close'):
            gate.close()
        exchange.close()
        temporary.cleanup()
    if c['finite_liability_hours'] is None:
        native_audit = audit(tape, root=root, manifest=manifest, expected_actions_sha256=tape['actions_sha256'])
    else:
        from enterprise.contract012 import audit_contract012
        native_audit = audit_contract012(tape, root=root, manifest=manifest)
    summary = tape['summary']
    survives = summary['payables'] == 0 and summary['reservedInvestment'] == 0 and not summary['investmentStopped'] and summary['cash'] >= summary['tailReserve'] + summary['custodyReserve'] + summary['workingCapital']
    collection_events = [e for e in events if e['kind']=='COLLECTION']
    milestones = {str(target): None for target in c['targets_collected_microUSD']}
    collected_rows = []
    for action in tape['actions']:
        delta = action['after']['collections'] - action['before']['collections']
        if delta:
            collected_rows.append((action['day'], delta))
        trailing = sum(v for t,v in collected_rows if action['day']-365*24 < t <= action['day'])
        for target in c['targets_collected_microUSD']:
            if milestones[str(target)] is None and trailing >= target and action['after']['profit'] > 0 and action['after']['payables'] == 0 and not action['after']['investmentStopped']:
                milestones[str(target)] = action['day']
    metrics = {'paid_jobs':counters['paid'],'accepted_jobs':counters['accepted'],'customers':sum(h['purchases']>0 for h in histories.values()),'repeat_buyers':sum(h['purchases']>1 for h in histories.values()),'earned_funded_deliveries':earned_deliveries,'earned_reinvestment':earned_spent,'earned_funded_acquisition':acquisition_earned,'capacity':capacity,'collections_microUSD':summary['collections'],'costs_microUSD':summary['expenses'],'profit_microUSD':summary['profit'],'earned_reinvestment_share_of_collections':earned_spent/max(1,summary['collections']),'qualified_unique_work_executed':len(work),'experimental_workload_stock':len(jobs),'qualification_stock_boundary_time':qualified_boundary}
    for record in decisions:
        outcomes = record['realized_outcome'].get('outcomes',[])
        if record['selected_action'].startswith('acquire-'):
            realized = sum(o.get('price',0) if o.get('outcome')=='SIMULATED_SETTLED' else 0 for o in outcomes) - sum(o.get('complete_delivery_cost',0) for o in outcomes) - record.get('actual_acquisition_cost',0)
            record['realized_outcome']['direct_collected_contribution_before_shared_tax_and_capacity'] = realized
            record['realized_outcome']['prediction_error'] = realized-record['projected_contribution']
    earned_investments = [i for i in tape['investments'] if i['state']=='complete']
    generated_earnings = max(0, summary['profit'] + earned_spent)
    metrics.update({'net_earnings_generated_before_earned_reinvestment': generated_earnings,
                    'fraction_generated_earnings_reinvested': earned_spent/generated_earnings if generated_earnings else 0.,
                    'reinvestment_fraction_basis': 'Actual native earned-funded expenses divided by final complete-cost profit plus those reinvestment expenses; this finite-trajectory flow ratio includes repeated use and is not an instantaneous balance ratio.',
                    'mean_contract_cash_conversion_hours': c['production_hours']+c['settlement_hours'],
                    'paid_jobs_first_14_days':sum(e['time']<14*24 for e in collection_events),
                    'paid_jobs_last_14_days':sum(c['horizon_hours']-14*24<=e['time']<=c['horizon_hours'] for e in collection_events),
                    'earned_investment_count':len(earned_investments),
                    'qualified_stock_remaining':len(jobs)-len(consumed),
                    'cash_microUSD':summary['cash'], 'unrestricted_earned_microUSD':summary['unrestrictedEarned']})
    result = {'schema':SCHEMA,'scope':'SIMULATED','config':c,'seed':seed,'controller':controller,'manifest_sha256':digest(manifest),'summary':summary,'ledger':tape,'decisions':decisions,'events':events,'work_executions':work,'cost_receipts':receipts,'rejected_growth_actions':rejected,'metrics':metrics,'counts':counters,'milestones':milestones,'milestone_basis':'First passage of trailing365-day collected microUSD revenue; all unreached targets remain null. Exact finite synthetic cohort, no scale projection.','cash_survival':survives,'conditional_simulated_go':survives and summary['profit']>0 and counters['paid']>1 and earned_deliveries>0,'native_replay':native_audit,'actual_revenue':0,'invention_compounding':'NOT_ESTABLISHED','native_tail_contract':'PERMANENT_PRINCIPAL_PLUS_FEE' if c['finite_liability_hours'] is None else 'EXPLICIT_COSTED_FINITE_LIABILITY','controller_scope':'Reconstructed fixed-share/report-clock comparator, competent greedy contribution/cash policy, and joint absolute incremental contribution/workload policy share price menu, buyers, obligations and feasible option definitions. Exact historical PR19 baseline reproduced separately.','resource_receipt':{'wall_seconds':time.monotonic()-started_wall,'process_cpu_seconds':time.process_time()-started_cpu,'paid_model_calls':0},'information_boundary':'Controller receives own public CRM and transactions, observed rival prices, known costs and declared segment priors. Hidden buyer values/budgets and keyed future events are confined to simulated environment.'}
    if output is not None:
        from commercial.persistence import atomic_bytes
        atomic_bytes(destination/'RESULT.json',canonical(result)+b'\n')
    return result
