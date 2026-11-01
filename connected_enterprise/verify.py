"""Independent financial and operating checks for connected014 evidence.

This checker consumes exported records, source bytes and admitted artifacts. It
does not accept a producer's commercial verdict as evidence of useful delivery.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from adaptive_enterprise.instruments import execute_offer
from commercial.ledger import canonical, digest

EXECUTING_VERIFIER_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _integer(value, label, *, positive=False):
    if type(value) is not int or value < (1 if positive else 0):
        raise ValueError(label + '_INTEGER_REQUIRED')
    return value


def _private_draw(seed, identity, stage):
    from commercial.ledger import canonical
    return int.from_bytes(hashlib.sha256(canonical(['connected014', seed, identity, stage])).digest()[:8], 'big') / 2**64


def _expected_competitive_price(legacy, rival, config, previous):
    denominator = 10000 - config['payment_bps']
    if denominator == 0:
        return legacy
    resources = sum(config[key] for key in ['production_cost', 'supplier_unit_cost', 'support_cost',
                                           'onboarding_cost', 'qualification_cost', 'exposure_cost'])
    numerator = (resources + config['payment_fixed'] + 1_000_000) * 10000
    floor = (numerator + denominator - 1) // denominator
    count, wins = len(previous), sum(row['chosen'] for row in previous)
    responsive = count > 0 and wins < count and wins * 5 < 2 * count
    target = min(legacy, rival - 250_000) if responsive else legacy
    if target < floor:
        return legacy if floor > legacy else floor
    return target


def _unique(rows, key, label):
    if not isinstance(rows, list) or any(not isinstance(row, dict) or key not in row for row in rows):
        raise ValueError(label + '_RECORDS_REQUIRED')
    result = {row[key]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError(label + '_DUPLICATE_ID')
    return result


def check_events(events):
    indexed = _unique(events, 'id', 'OPERATING_EVENT')
    previous = -1
    for row in events:
        moment = _integer(row.get('time'), 'EVENT_TIME')
        if moment < previous or not isinstance(row.get('kind'), str) or not row['kind']:
            raise ValueError('EVENT_TIME_REGRESSION_OR_KIND_MISSING')
        previous = moment
    return indexed


def check_budgets(buyers, orders):
    indexed = _unique(buyers, 'id', 'BUYER')
    settled = {}
    pending = {}
    for order in orders:
        customer = order['customer_id']
        if customer not in indexed:
            raise ValueError('ORDER_CUSTOMER_NOT_IN_BUDGET_AUDIT')
        if order['outcome'] == 'SETTLED':
            settled[customer] = settled.get(customer, 0) + order['price']
        elif order['outcome'] == 'PENDING':
            pending.setdefault(customer, {})[order['id']] = order['price']
    for customer, row in indexed.items():
        initial = _integer(row.get('initial_budget'), 'INITIAL_BUYER_BUDGET')
        remaining = _integer(row.get('remaining_budget'), 'REMAINING_BUYER_BUDGET')
        outside = _integer(row.get('outside_spend', 0), 'BUYER_OUTSIDE_SPEND')
        spent = _integer(row.get('our_settled_spend'), 'BUYER_SETTLED_SPEND')
        commitments = row.get('pending_commitments')
        if not isinstance(commitments, dict) or any(type(v) is not int or v < 0 for v in commitments.values()):
            raise ValueError('BUYER_PENDING_COMMITMENTS_REQUIRED')
        if spent != settled.get(customer, 0) or commitments != pending.get(customer, {}):
            raise ValueError('BUYER_CROSS_SERVICE_COMMITMENT_OR_SPEND_MISMATCH')
        if initial + _integer(row.get('external_income_total',0),'EXTERNAL_BUYER_INCOME') != remaining + spent + outside + sum(commitments.values()):
            raise ValueError('BUYER_BUDGET_CONSERVATION_FAILURE')
    receipt={'buyers_checked': len(indexed), 'buyer_initial_budget': sum(row['initial_budget'] for row in buyers)}
    if any('external_income_total' in row for row in buyers):
        receipt['external_buyer_income_microUSD']=sum(row['external_income_total'] for row in buyers)
    return receipt


def _check_buyer_origins(config, seed, buyers):
    from commercial.ledger import canonical
    indexed = _unique(buyers, 'id', 'BUYER')
    expected_ids = {f'SIM-customer-{i:03d}' for i in range(config['customer_pool'])}
    if set(indexed) != expected_ids:
        raise ValueError('FROZEN_FINITE_BUYER_POPULATION_CHANGED')
    from .complete_offer_market import compile_market
    market=compile_market(config['complete_offer_policy']) if 'complete_offer_policy' in config else None
    for ident, buyer in indexed.items():
        key = canonical(['connected014', seed, ident, 'budget'])
        uniform = int.from_bytes(hashlib.sha256(key).digest()[:8], 'big') / 2**64
        expected = int((180 + 400 * uniform) * 1_000_000 * config['buyer_budget_multiplier_bps'] / 10000)
        if 'complete_offer_policy' in config:
            expected=market.profile(ident)['atoms'][market.atom(ident,seed)]['budget_microUSD']
        if buyer['initial_budget'] != expected:
            raise ValueError('FROZEN_INITIAL_BUYER_BUDGET_CHANGED')


def _check_market_decisions(result, tape):
    from .buyer_income import income_index,received_by
    incomes=income_index(result)
    if 'complete_offer_policy' in result['config']:
        from .complete_offer_audit import audit_market
        return audit_market(result,tape)
    cfg, seed = result['config'], result['seed']
    buyers = {row['id']: row for row in result['buyers']}
    offers = [row for row in result['decisions'] if row.get('kind') == 'offer']
    choices = [row for row in result['decisions'] if row.get('kind') in {'offer', 'outside_choice'}]
    orders = {(row['customer_id'], row['qualified_time']): row for row in result['orders']}
    if len(orders) != len(result['orders']):
        raise ValueError('MULTIPLE_ORDERS_FOR_ONE_CUSTOMER_NEED')
    refunds = {row['args']['id']: row['day'] for row in tape['actions']
               if row['op'] == 'event' and row['args']['action'] == 'refund'}
    outside = {}
    checked = set()
    history = []
    current_time, rival_capacity = None, 0
    rival_cash = 500_000_000
    for decision in choices:
        moment, customer, service = decision['time'], decision['customer_id'], decision['service_id']
        if customer not in buyers or service not in cfg['human_comparator']:
            raise ValueError('OFFER_OUTSIDE_FROZEN_BUYER_AND_SERVICE_POPULATION')
        if _private_draw(seed, [moment // 24, customer], 'need') >= cfg['arrival_bps'] / 10000:
            raise ValueError('OFFER_WITHOUT_CURRENT_SIMULATED_CUSTOMER_NEED')
        if moment != current_time:
            current_time, rival_capacity = moment, 2
        if (customer, moment) in checked:
            raise ValueError('CUSTOMER_EXPOSED_TO_DUPLICATE_SERVICE_BUDGET_DECISION')
        checked.add((customer, moment))
        human = cfg['human_comparator'][service]
        anchor = int((human['hours'] * human['loaded_usd_hour'] + 2) * 1_000_000)
        previous = [row for row in history if row['service_id'] == service and row['time'] < moment][-12:]
        winrate = sum(row['chosen'] for row in previous) / len(previous) if previous else .5
        ratio = .88 if winrate < .4 else .98 if winrate > .8 else .93
        price = max(5_000_000, int(anchor * ratio))
        rival_bps = cfg['price_pressure_bps']
        for update_day in range(7, moment // 24 + 1, 7):
            update = update_day * 24
            if update >= moment:
                break
            visible = [row for row in offers if row['time'] <= update - 24][-20:]
            if visible:
                won = sum(row['buyer_choice'] == 'rival' for row in visible) / len(visible)
                rival_bps = max(5000, min(10500, rival_bps + (200 if won > .6 else -200)))
        if decision['public_rival_price'] != int(anchor * rival_bps / 10000):
            raise ValueError('RIVAL_RESPONSE_READS_UNAVAILABLE_FUTURE_HISTORY')
        if result['arm'] == 'competitive_growth':
            price = _expected_competitive_price(price, int(anchor * rival_bps / 10000), cfg, previous)
        if 'strategic_policy' in cfg and decision['kind']=='offer':
            from .strategic_commerce import selected_delivery
            wrapper=result.get('joint_actions',{}).get(decision.get('joint_allocation_sha256'))
            if wrapper is None:raise ValueError('STRATEGIC_PRICE_RECEIPT_REQUIRED')
            price=selected_delivery(wrapper['allocation'],decision.get('joint_option_id'))['price']
        if decision['human_price'] != anchor or (decision['kind'] == 'offer' and decision['price'] != price) or (decision['kind'] == 'outside_choice' and decision['price'] is not None):
            raise ValueError('PRICE_POLICY_USES_UNREGISTERED_INFORMATION_OR_HUMAN_ANCHOR')
        committed = sum(row['price'] for row in result['orders'] if row['customer_id'] == customer
                        and row['qualified_time'] < moment and (row['id'] not in refunds or refunds[row['id']] > moment))
        available = buyers[customer]['initial_budget'] + received_by(incomes,customer,moment) - outside.get(customer, 0) - committed
        value = int(anchor * (1.1 + _private_draw(seed, customer, 'value')) * cfg['value_bps'] / 10000)
        rival_price = decision['public_rival_price']
        options = [('decline', 0)]
        if available >= anchor:
            options.append(('human', value - anchor))
        if decision['kind'] == 'offer' and available >= price:
            options.append(('us', value - price))
        if rival_capacity > 0 and rival_cash > 1_000_000 and available >= rival_price:
            options.append(('rival', value - rival_price))
        choice = max(options, key=lambda item: (item[1], _private_draw(seed, [moment // 24, customer, item[0]], 'buyer-indifference')))[0]
        if decision['buyer_choice'] != choice or decision['chosen'] is not (choice == 'us'):
            raise ValueError('VOLUNTARY_BUYER_CHOICE_DOES_NOT_RECOMPUTE')
        if choice == 'us':
            order = orders.get((customer, moment))
            if order is None or order['price'] != price or order['offer']['service_id'] != service:
                raise ValueError('VOLUNTARY_CHOICE_NOT_BOUND_TO_QUALIFIED_NATIVE_ORDER')
        else:
            if (customer, moment) in orders:
                raise ValueError('DECLINED_OFFER_BECAME_NATIVE_ORDER')
            amount = anchor if choice == 'human' else rival_price if choice == 'rival' else 0
            if decision.get('outside_spend', 0) != amount:
                raise ValueError('COMPETING_PROVIDER_BUDGET_SPEND_CHANGED')
            outside[customer] = outside.get(customer, 0) + amount
            if choice == 'rival':
                rival_capacity -= 1
                rival_cash += amount - 1_000_000
        if decision['kind'] == 'offer':
            history.append(decision)
    if set(orders) - checked:
        raise ValueError('NATIVE_ORDER_WITHOUT_VOLUNTARY_BUYER_DECISION')
    if any(buyer['outside_spend'] != outside.get(ident, 0) for ident, buyer in buyers.items()):
        raise ValueError('OUTSIDE_BUYER_SPENDING_DOES_NOT_RECONCILE')
    return {'voluntary_buyer_decisions_recomputed': len(choices), 'enterprise_offers_recomputed': len(offers),
            'unavailable_offer_outside_choices_recomputed': len(choices) - len(offers)}


def _check_customer_lifecycle(result):
    cfg, seed = result['config'], result['seed']
    if set(result['channels']['exposures_by_day']) != {str(day) for day in range(cfg['horizon_days'])}:
        raise ValueError('CHANNEL_EXPOSURE_DAYS_DIFFER_FROM_FROZEN_HORIZON')
    buyers = {row['id']: row for row in result['buyers']}
    owned = set(sorted(buyers)[:4])
    state = {ident: {'known': ident in owned, 'active': True, 'onboarded': False,
                     'purchases': 0, 'retention_decision_count': 0, 'pending': None,
                     'service_index': int(ident.rsplit('-', 1)[1]) % 3,
                     'last_exposure': None, 'next_need_time': 0} for ident in buyers}
    orders = {row['id']: row for row in result['orders']}
    pending_reactivations = {}
    outside = {}
    for decision in result['decisions']:
        if decision.get('outside_spend') or ('complete_offer_policy' in cfg and decision.get('buyer_choice') in {'human','rival','self_service'}):
            outside.setdefault(decision['time'], []).append(decision)
    responses = 0
    outreach_units = {};candidate_ids={};public_buyers={}
    def operating_snapshot(moment):
        if moment in outreach_units:
            return
        day = moment // 24
        if moment % 24 or not 0 <= day < cfg['horizon_days']:
            raise ValueError('OPERATING_DECISION_OUTSIDE_REGISTERED_CALENDAR')
        channel_day = result['channels']['exposures_by_day'][str(day)]
        exposed = {row['customer_id'] for row in channel_day['exposures']}
        candidates = [ident for ident, buyer in state.items() if buyer['known'] and buyer['active']
                      and buyer['pending'] is None and buyer['next_need_time'] <= moment
                      and (ident in owned or buyer['onboarded'] or ident in exposed)]
        candidate_ids[moment]=sorted(candidates,key=lambda ident:(state[ident]['next_need_time'],ident));public_buyers[moment]=copy.deepcopy(state)
        outreach_units[moment] = channel_day['attempted_slots'] + sum(ident not in exposed for ident in candidates)
    for event in result['events']:
        kind, moment = event['kind'], event['time']
        if kind in {'INVESTMENT', 'QUALIFIED_ORDER', 'BUSINESS_DECISION'}:
            operating_snapshot(moment)
        if kind == 'EXPOSURE':
            buyer = state[event['customer_id']]
            buyer['known'] = True
            buyer['last_exposure'] = moment
            if not buyer['active']:
                pending_reactivations[event['id'] + '-reactivation'] = event
        elif kind == 'REACTIVATION_RESPONSE':
            exposure = pending_reactivations.pop(event['id'], None)
            if exposure is None or exposure['customer_id'] != event['customer_id'] or exposure['time'] != moment or exposure['source_plan_id'] != event['source_plan_id']:
                raise ValueError('REACTIVATION_WITHOUT_PAID_EXPOSURE_OF_CHURNED_BUYER')
            expected = _private_draw(seed, [moment // 24, event['customer_id']], 'paid-reactivation-response') < .35
            if event.get('response_probability_bps') != 3500 or event.get('responded') is not expected:
                raise ValueError('VOLUNTARY_REACTIVATION_RESPONSE_DOES_NOT_RECOMPUTE')
            state[event['customer_id']]['active'] = expected
            responses += 1
        elif kind == 'QUALIFIED_ORDER':
            order = orders[event['order_id']]
            customer = order['customer_id']
            buyer = state[customer]
            if not buyer['active'] or not buyer['known'] or buyer['pending'] is not None or buyer['next_need_time'] > moment:
                raise ValueError('QUALIFIED_ORDER_OUTSIDE_ACTIVE_CUSTOMER_LIFECYCLE')
            if customer not in owned and not buyer['onboarded'] and buyer['last_exposure'] != moment:
                raise ValueError('UNONBOARDED_PAID_PROSPECT_RECEIVED_FREE_FOLLOWUP')
            service = ('reconciliation', 'kpi_variance', 'evidence_matrix')[buyer['service_index'] % 3]
            if 'complete_offer_policy' in cfg:
                from .complete_offer_market import request_profile
                allowed=request_profile(cfg['complete_offer_policy'],customer)['services']
                if order['job_id'] not in cfg['complete_offer_policy']['requested_jobs'][customer]:raise ValueError('UNREQUESTED_CUSTOMER_JOB')
                if order['offer']['service_id'] not in allowed:raise ValueError('UNREQUESTED_COMPLETE_OUTCOME')
                if cfg['complete_offer_policy']['selection']=='restricted' and order['offer']['service_id']!=service:raise ValueError('RESTRICTED_SCOPE_CHANGED')
            elif order['offer']['service_id'] != service:
                raise ValueError('CUSTOMER_SERVICE_NEED_CHANGED_WITHOUT_DELIVERY')
            buyer['onboarded'], buyer['pending'] = True, order['id']
        elif kind in {'COLLECTION', 'REFUND'}:
            order = orders[event['order_id']]
            buyer = state[order['customer_id']]
            if buyer['pending'] != order['id']:
                raise ValueError('COLLECTION_OR_REFUND_WITHOUT_PENDING_CUSTOMER_ORDER')
            buyer['pending'] = None
            buyer['next_need_time'] = moment + 7 * 24
            if kind == 'COLLECTION':
                count = buyer['retention_decision_count']
                buyer['active'] = _private_draw(seed, [order['customer_id'], count], 'retention') < cfg['retention_bps'] / 10000
                buyer['retention_decision_count'] += 1
                buyer['purchases'] += 1
                buyer['service_index'] += 1
        elif kind == 'BUSINESS_DECISION':
            for decision in outside.get(moment, []):
                state[decision['customer_id']]['next_need_time'] = moment + 7 * 24
    if pending_reactivations:
        raise ValueError('UNRESOLVED_PAID_REACTIVATION_RESPONSE')
    if set(outreach_units) != {day * 24 for day in range(cfg['horizon_days'])}:
        raise ValueError('COMPLETE_OPERATING_CALENDAR_NOT_EXECUTED')
    for customer, expected in state.items():
        for key in ['known', 'active', 'onboarded', 'purchases', 'retention_decision_count', 'service_index', 'next_need_time']:
            if buyers[customer].get(key) != expected[key]:
                raise ValueError('DERIVED_CUSTOMER_LIFECYCLE_CHANGED:' + key)
    return {'customer_lifecycles_recomputed': len(state), 'paid_reactivation_responses_recomputed': responses,
            'daily_outreach_units_recomputed': outreach_units,**({'daily_candidate_ids_recomputed':candidate_ids,'daily_public_buyers':public_buyers} if 'strategic_policy' in cfg else {})}


def _check_cost_semantics(result, tape, lifecycle, *, startup_evaluation_required=False):
    cfg = result['config']
    expected = {}
    def add(ident, amount, moment, category):
        if amount:
            expected[ident] = {'amount': amount, 'time': moment, 'category': category}
    add('complete-development-setup', cfg['setup_cost'], 0, 'development_integration_qualification_and_failed_search')
    if 'startup_acquisition_policy' in cfg and startup_evaluation_required:
        add('startup-acquisition-evaluation',cfg['startup_acquisition_policy']['planning_cost_microUSD'],0,'prepaid_startup_acquisition_evaluation')
    for day in range(cfg['horizon_days']):
        moment = day * 24
        add('maintenance-' + str(day), cfg['maintenance_daily'], moment, 'maintenance')
        if 'public_budget_gate' in cfg:
            add('public-budget-gate-'+str(day),cfg['public_budget_gate']['daily_cost_microUSD'],moment,'public_affordability_preflight')
        if 'refusal_recourse_policy' in cfg:
            policy=cfg['refusal_recourse_policy'];selective=policy['schema']=='connected-selective-refusal-recourse/v2'
            if selective:add('recourse-evaluation-'+str(day),policy['daily_evaluation_cost'],moment,'selective_recourse_public_evaluation')
            wrapper=next(w for w in result['joint_actions'].values() if w['time']==moment)
            if not selective or wrapper['selective_recourse_decision']['purchase']:add('recourse-planning-'+str(day),policy['daily_planning_cost'],moment,'prepaid_finite_refusal_recourse')
        units = lifecycle['daily_outreach_units_recomputed'][moment]
        add('outreach-' + str(day), cfg['exposure_cost'] * units, moment, 'outreach_including_failed_and_unused_slots')
        attempts = sum(row.get('kind') == 'offer' and row['time'] == moment for row in result['decisions'])
        if 'strategic_policy' in cfg:
            wrapper=next(w for w in result['joint_actions'].values() if w['time']==moment)
            attempts=len(wrapper['allocation']['deliveries'])
        add('qualification-' + str(day), cfg['qualification_cost'] * attempts, moment, 'qualification_including_lost_offers')
    for row in result['orders']:
        add(row['id'] + '-resources', row.get('resource_cost',row['complete_cost']), row['qualified_time'], 'production_contract')
        if 'terms' in row:add(row['id']+'-prospective-charges',row['fee']+row['premium'],row['qualified_time'],'prospective_contract_charges')
    for row in result['investments']:
        category = 'acquisition_contract' if row['kind'] == 'acquisition' else 'capacity_contract'
        if row['kind'] == 'capacity' and row['cost'] != cfg['capacity_price']*row.get('capacity_units',1):
            raise ValueError('CAPACITY_COST_DIFFERS_FROM_DECLARED_SUPPLIER_CONTRACT')
        add(row['id'], row['cost'], row['purchased_time'], category)
    tax_paid = 0
    for native in tape['actions']:
        if native['op'] == 'event' and native['args']['action'] in {'release', 'refund'}:
            taxable = max(0, native['after']['profit'] + tax_paid)
            tax = max(0, taxable * cfg['profit_tax_bps'] // 10000 - tax_paid)
            add('tax-' + native['args']['id'], tax, native['day'], 'tax_provision')
            tax_paid += tax
    actual = {row['id']: {key: row[key] for key in ['amount', 'time', 'category']} for row in result['costs']}
    if actual != expected:
        raise ValueError('COMPLETE_COSTS_DIFFER_FROM_FROZEN_OPERATING_SEMANTICS')
    journal = result['owned_account']['connected_journal']['entries']
    committed = {}
    for entry in journal:
        request = entry['request']
        if request['operation'] == 'spend':
            committed[request['id']] = (request['amount'], request['day'])
        elif request['operation'] == 'execute' and request['op'] == 'cost':
            committed[request['args']['id']] = (request['args']['amount'], request['day'])
        elif request['operation']=='execute' and request['op']=='offer' and 'terms_id' in request['args']:
            order=next(o for o in result['orders'] if o['id']==request['args']['id'])
            if order['fee']+order['premium']:committed[order['id']+'-prospective-charges']=(order['fee']+order['premium'],request['day'])
    if committed != {ident: (row['amount'], row['time']) for ident, row in expected.items()}:
        raise ValueError('ALL_NATIVE_COSTS_MUST_HAVE_OPERATING_RESOURCE_CONTRACT')
    return {'complete_operating_cost_contracts_recomputed': len(expected), 'tax_provision_recomputed_microUSD': tax_paid}


def _check_commercial_result(result):
    settled = [row for row in result['orders'] if row['outcome'] == 'SETTLED']
    customers = {row['customer_id'] for row in settled}
    repeats = sum(sum(row['customer_id'] == customer for row in settled) > 1 for customer in customers)
    earned = [row for row in settled if row['funding_receipt']['funding'] == 'EARNED' and row['price'] > row['complete_cost']]
    summary = result['summary']
    covered = summary['cash'] >= summary['custodyReserve'] + summary['tailReserve'] + summary['workingCapital']
    expected = {'accepted_jobs': sum(row['acceptance_time'] is not None for row in result['orders']),
                'paid_jobs': len(settled), 'customers': len(customers), 'repeat_customers': repeats,
                'profitable_earned_continuations': len(earned),
                'conditional_simulated_commercial_success': len(settled) >= 12 and len(customers) >= 3 and repeats >= 2
                    and len(earned) >= 2 and summary['profit'] > 0 and summary['unrestrictedEarned'] > 0
                    and summary['payables'] == 0 and not summary['investmentStopped'] and covered,
                'actual_collections': 0, 'actual_customers': 0, 'actual_profit': None}
    if any(result.get(key) != value for key, value in expected.items()):
        raise ValueError('COMMERCIAL_COUNTERS_OR_SUCCESS_FLAG_DO_NOT_RECOMPUTE')
    expansion = []
    for investment in result['investments']:
        field = 'acquisition_source_plan_id' if investment['kind'] == 'acquisition' else 'capacity_source_plan_id'
        used = [row for row in settled if (row.get(field)==investment['plan_id'] if investment['kind']=='acquisition' else investment['plan_id'] in row.get('capacity_source_plan_ids',[row.get(field)]))]
        expansion.append({'plan_id': investment['plan_id'], 'kind': investment['kind'], 'cost': investment['cost'],
                          'funding': investment['funding_receipt']['funding'], 'later_settled_order_ids': [row['id'] for row in used],
                          'scoped_collections': sum(row['price'] for row in used)})
    if result.get('productive_expansion') != expansion:
        raise ValueError('PRODUCTIVE_EXPANSION_ATTRIBUTION_DOES_NOT_RECOMPUTE')
    return {'commercial_counters_recomputed': expected, 'obligations_covered': covered,
            'productive_expansion_receipts_recomputed': len(expansion)}


def check_source(root, source):
    if not isinstance(source, dict) or not isinstance(source.get('files'), dict) or not source['files']:
        raise ValueError('SOURCE_FILES_REQUIRED')
    if source.get('sha256') != digest(source['files']):
        raise ValueError('SOURCE_MAP_DIGEST_CHANGED')
    root = Path(root).resolve()
    for name, expected in source['files'].items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('SOURCE_PATH_ESCAPE')
        path = root / relative
        if path.is_symlink() or any(p.is_symlink() for p in path.parents):
            raise ValueError('SOURCE_SYMLINK_REFUSED')
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('CONNECTED_EXECUTING_SOURCE_CHANGED:' + name)
    return {'source_files_checked': len(source['files']), 'source_sha256': source['sha256']}


def check_channels(channels, investments, buyers, *, contracts=None, seed=None):
    if not isinstance(channels, dict) or channels.get('schema') != 'agi-alpha/connected014-channel-book/v1':
        raise ValueError('SOURCE_BOUND_CHANNEL_BOOK_REQUIRED')
    instances = channels.get('instances')
    receipts = channels.get('purchase_receipts')
    daily = channels.get('exposures_by_day')
    if not isinstance(instances, dict) or not isinstance(receipts, dict) or not isinstance(daily, dict) or set(instances) != set(receipts):
        raise ValueError('CHANNEL_INSTANCE_PURCHASE_BINDING_REQUIRED')
    if contracts is None or type(seed) is not int or seed < 0:
        raise ValueError('FROZEN_CHANNEL_CONTRACTS_AND_SEED_REQUIRED')
    investor = {row['plan_id']: row for row in investments}
    if contracts is not None or seed is not None:
        from connected_enterprise.channels import validate_contracts
        contracts = validate_contracts(contracts)
        if channels.get('binding_sha256') != digest({'seed': seed, 'contracts': contracts}):
            raise ValueError('CHANNEL_FROZEN_CONTRACT_OR_SEED_BINDING_CHANGED')
    population = sorted(row['id'] for row in buyers)
    all_exposures = []
    seen_exposures = set()
    activation = {}
    for event in channels.get('events', []):
        if event.get('kind') == 'CHANNEL_ACTIVATED':
            activation.setdefault(event['source_plan_id'], event['day'])
    for ident, row in instances.items():
        purchase = receipts[ident]
        terms = row['terms']
        if purchase['terms'] != terms or (contracts is not None and contracts.get(row['contract_id']) != terms):
            raise ValueError('CHANNEL_PURCHASE_TERMS_CHANGED_FROM_FINANCED_CONTRACT')
        if ident != row.get('source_plan_id') or ident not in investor or investor[ident]['kind'] != 'acquisition':
            raise ValueError('CHANNEL_WITHOUT_NATIVE_PRODUCTIVE_PURCHASE')
        if purchase['invoice_microUSD'] != terms['price_microUSD'] + terms['support_microUSD'] or investor[ident]['cost'] != purchase['invoice_microUSD']:
            raise ValueError('CHANNEL_COMPLETE_CONTRACT_INVOICE_MISMATCH')
        if row['activation_day'] != row['purchased_day'] + terms['lead_days'] or row['expiry_day'] != row['activation_day'] + terms['duration_days']:
            raise ValueError('CHANNEL_CONTRACT_LEAD_OR_DURATION_CHANGED')
        if 'contract_id' in investor[ident] and investor[ident]['contract_id']!=row['contract_id']:raise ValueError('NATIVE_CHANNEL_CONTRACT_ID_CHANGED')
        if investor[ident]['purchased_time'] != row['purchased_day'] * 24 or investor[ident]['activation_time'] != row['activation_day'] * 24 or investor[ident]['expiry_time'] != row['expiry_day'] * 24:
            raise ValueError('CHANNEL_AND_OPERATING_CLOCK_MISMATCH')
        if row.get('failure_credit_due_microUSD', 0) and purchase.get('failure_credit_collected_microUSD', 0):
            raise ValueError('CHANNEL_CREDIT_REQUIRES_SEPARATE_NATIVE_COLLECTION')
    for day_text, record in sorted(daily.items(), key=lambda item: int(item[0])):
        day = int(day_text)
        rows = record['exposures']
        if record.get('population_sha256') != digest(population):
            raise ValueError('CHANNEL_AUDIENCE_CHANGED')
        if len({row['customer_id'] for row in rows}) != len(rows):
            raise ValueError('OVERLAPPING_CHANNELS_DOUBLE_COUNT_CUSTOMER_DAY')
        attempted = _integer(record.get('attempted_slots'), 'ATTEMPTED_CHANNEL_SLOTS')
        unused = _integer(record.get('unused_slots'), 'UNUSED_CHANNEL_SLOTS')
        if record.get('realized_exposures') != len(rows) or attempted != unused + len(rows):
            raise ValueError('CHANNEL_SLOTS_ARE_NOT_CONSERVED')
        expected_attempts = sum(instance['terms']['slots_per_day'] for ident, instance in instances.items()
                                if ident in activation and activation[ident] <= day < instance['expiry_day'])
        if attempted != expected_attempts:
            raise ValueError('CHANNEL_FINITE_DAILY_CAPACITY_MISMATCH')
        for exposure in rows:
            plan = exposure['source_plan_id']
            instance = instances.get(plan)
            if instance is None or plan not in activation or day < activation[plan] or day >= instance['expiry_day']:
                raise ValueError('EXPOSURE_BEFORE_ACTIVATION_OR_AFTER_EXPIRY')
            if exposure['contract_id'] != instance['contract_id'] or exposure['customer_id'] not in population[instance['terms']['owned_audience_count']:]:
                raise ValueError('EXPOSURE_OUTSIDE_PAID_FINITE_AUDIENCE')
            if exposure['exposure_id'] in seen_exposures:
                raise ValueError('DUPLICATE_EXPOSURE_ID')
            seen_exposures.add(exposure['exposure_id'])
            all_exposures.append({**exposure, 'day': day})
    indexed = {}
    for exposure in all_exposures:
        indexed.setdefault(exposure['customer_id'], []).append(exposure)
    for customer, rows in indexed.items():
        prior_day = None
        for count, row in enumerate(rows):
            terms = instances[row['source_plan_id']]['terms']
            if count >= terms['max_contacts_per_customer'] or (prior_day is not None and row['day'] - prior_day < terms['contact_cooldown_days']):
                raise ValueError('CHANNEL_CONTACT_FATIGUE_OR_COOLDOWN_VIOLATION')
            prior_day = row['day']
        expected = [{'day': row['day'], 'exposure_id': row['exposure_id'], 'source_plan_id': row['source_plan_id']} for row in rows]
        if channels.get('contacts', {}).get(customer) != expected:
            raise ValueError('CHANNEL_CONTACT_HISTORY_DOES_NOT_RECONCILE')
    if set(channels.get('contacts', {})) != set(indexed):
        raise ValueError('CHANNEL_CONTACT_IDENTITIES_DO_NOT_RECONCILE')
    for ident, instance in instances.items():
        if instance['realized_exposures'] != sum(row['source_plan_id'] == ident for row in all_exposures):
            raise ValueError('CHANNEL_REALIZED_REACH_DOES_NOT_RECONCILE')
    from connected_enterprise.channels import audit_channel_history
    replay = audit_channel_history(channels, contracts, seed, buyers)
    if activation != replay['activation_by_plan']:
        raise ValueError('SEEDED_CHANNEL_HISTORY_MISMATCH')
    return {'paid_channel_contracts_checked': len(instances), 'paid_exposures_checked': len(all_exposures)}


def _check_contract_clock(ident, offered, actions, operating, qualified, config, *, refund_due=None):
    deadline = qualified + _integer(config.get('payment_deadline_hours'), 'PAYMENT_DEADLINE_HOURS', positive=True)
    if _integer(offered['args'].get('deadline'), 'NATIVE_OFFER_DEADLINE') != deadline:
        raise ValueError('NATIVE_OFFER_DEADLINE_DIFFERS_FROM_FROZEN_CONTRACT')
    if refund_due is not None:
        native_time = _integer(actions.get('refund', {}).get('day'), 'NATIVE_REFUND_TIME')
        event_time = _integer(operating.get((ident, 'REFUND'), {}).get('time'), 'OPERATING_REFUND_TIME')
        if native_time != refund_due or event_time != refund_due:
            raise ValueError('REFUND_TIME_DIFFERS_FROM_FROZEN_CONTRACT')


def _check_order_terms(result, row, offered, tape, operating):
    expected=None;policy=result['config'].get('prospective_policy')
    if policy:
        if 'monetary_policy' in result['config']:
            from commercial.terms_exact_v2 import prospective_terms
        else:
            from commercial.terms import prospective_terms
        cfg = result['config']; qualified = row['qualified_time']
        collection = qualified + cfg['production_hours'] + cfg['acceptance_hours'] + cfg['clearing_hours']
        boundary = max(collection, qualified + cfg['payment_deadline_hours']) + policy['protection_hours']
        expected = prospective_terms(row['id'], row['price'], boundary, collection,
                                     residual=policy['residual_microUSD'], premium=policy['premium_microUSD'], fee=row['fee'],
                                     coverage_limit=policy['coverage_limit_microUSD'], deductible=policy['deductible_microUSD'],
                                     exclusions=policy['exclusions'], payout_delay_hours=policy['payout_delay_hours'],
                                     jurisdiction=policy['jurisdiction'], counterparty_obligations=policy['counterparty_obligations'])
    if expected is None:
        if any(k in row for k in ['terms', 'terms_id', 'terms_sha256', 'resource_cost', 'premium', 'maturity_time']) or 'terms_id' in offered['args']:
            raise ValueError('LEGACY_OR_PREPARED_ORDER_TERMS_CANNOT_CHANGE_RETROACTIVELY')
        return 0
    registered = [e for e in tape['actions'] if e['op'] == 'register_terms' and e['args']['id'] == row.get('terms_id')]
    if (row.get('terms') != expected or row.get('terms_sha256') != digest(expected)
            or row.get('terms_id') != 'terms-' + row['id'] or offered['args'].get('terms_id') != row['terms_id']
            or len(registered) != 1 or registered[0]['args']['terms'] != expected
            or registered[0]['seq'] >= offered['seq'] or registered[0]['day'] != row['qualified_time']
            or row.get('premium') != expected['premium_microUSD']):
        raise ValueError('OPERATING_PROSPECTIVE_TERMS_NOT_AUTHORIZED_BEFORE_COMMITMENT')
    if row['outcome'] == 'SETTLED':
        maturity = [e for e in tape['actions'] if e['op'] == 'mature' and e['args']['id'] == row['id']]
        due = expected['maturity_day'] + 1
        if len(maturity) != 1 or maturity[0]['day'] != due or row.get('maturity_time') != due or operating.get((row['id'], 'PROTECTION_MATURITY'), {}).get('time') != due:
            raise ValueError('PROSPECTIVE_MATURITY_MISSING_DUPLICATED_OR_WRONG_CLOCK')
        if maturity[0]['before']['profit'] != maturity[0]['after']['profit'] or maturity[0]['before']['cash'] != maturity[0]['after']['cash']:
            raise ValueError('MATURITY_MUST_NOT_CREATE_INCOME_OR_CASH')
    return expected['premium_microUSD']


def audit(root, manifest, result):
    if not isinstance(result, dict) or result.get('schema') != 'agi-alpha/connected014-result/v1' or result.get('scope') != 'CONDITIONAL_SIMULATION':
        raise ValueError('CONNECTED_SIMULATED_WORLD_REQUIRED')
    if result.get('complete') is not True:
        raise ValueError('FULL_OPERATING_AUDIT_REQUIRES_COMPLETED_TRACE')
    from adaptive_enterprise.instruments import SOURCE_PATHS as SERVICE_SOURCES
    from connected_enterprise.finance import SOURCE_PATHS as FINANCE_SOURCES
    required = set(SERVICE_SOURCES) | set(FINANCE_SOURCES) | {
        'connected_enterprise/engine.py', 'connected_enterprise/channels.py',
        'connected_enterprise/verify.py', 'connected_enterprise/scale.py', 'connected_enterprise/pricing.py'}
    if 'buyer_income_policy' in result['config'] or 'public_budget_gate' in result['config']:
        required.add('connected_enterprise/buyer_income.py')
    if 'public_budget_gate' in result['config']:
        required.add('connected_enterprise/public_budget_gate051.py')
    if not required <= set(result.get('source', {}).get('files', {})):
        raise ValueError('COMPLETE_EXECUTING_SOURCE_BINDING_REQUIRED')
    source_receipt = check_source(root, result['source'])
    check_events(result['events'])
    from connected_enterprise.finance import audit_journal
    account = audit_journal(result['owned_account'], root=root, manifest=manifest)
    if manifest.get('native_engine','legacy-permanent-v1')!=(('exact-prospective-v2' if 'prospective_policy' in result['config'] else 'exact-permanent-v2') if 'monetary_policy' in result['config'] else ('prospective-v1' if 'prospective_policy' in result['config'] else 'legacy-permanent-v1')):raise ValueError('FRESH_POLICY_NATIVE_ENGINE_REGISTRATION_MISMATCH')
    from .capital_lifecycle import capital_metrics
    if result.get('capital_metrics')!=capital_metrics(result):raise ValueError('NATIVE_CAPITAL_OBSERVATIONS_CHANGED')
    tape = result['owned_account']['ledger']
    if result['config'].get('native_time_unit') != 'hour' or tape['config']['contract'] != 'connected014/' + digest({
            'config': result['config'], 'seed': result['seed'], 'arm': result['arm'],
            'source': result['source'], 'manifest': manifest}):
        raise ValueError('FROZEN_SOURCE_CONFIG_SEED_ARM_ACCOUNT_BINDING_CHANGED')
    if result['summary'] != account['summary']:
        raise ValueError('OPERATING_SUMMARY_DIFFERS_FROM_NATIVE_ACCOUNT')
    native_orders = {row['id']: row for row in account['orders']}
    offers, native_events = {}, {}
    for row in tape['actions']:
        if row['op'] == 'offer':
            offers[row['args']['id']] = row
        elif row['op'] == 'event':
            native_events.setdefault(row['args']['id'], {})[row['args']['action']] = row
    operating = {}
    for event in result['events']:
        if event.get('order_id') is not None:
            key = (event['order_id'], event['kind'])
            if key in operating:
                raise ValueError('DUPLICATED_ORDER_LIFECYCLE_EVENT')
            operating[key] = event
    orders = _unique(result['orders'], 'id', 'ORDER')
    if set(orders) != set(native_orders):
        raise ValueError('OPERATING_AND_NATIVE_ORDER_IDENTITIES_DIFFER')
    jobs = {job['id']: job for job in manifest['jobs']}
    resource_receipts = {entry['receipt']['id']: entry['receipt']
                         for entry in result['owned_account']['connected_journal']['entries']
                         if entry['request']['operation'] == 'spend'}
    resource_requests = {entry['receipt']['id']: entry['request']
                         for entry in result['owned_account']['connected_journal']['entries']
                         if entry['request']['operation'] == 'spend'}
    # Validate causal public decisions before resolving method plans from recourse rounds.
    lifecycle_receipt = _check_customer_lifecycle(result)
    from .strategic_audit import audit_decisions
    strategic_receipt = audit_decisions(root, manifest, result, lifecycle_receipt)
    market_receipt = _check_market_decisions(result, tape)
    verified_allocations = dict(result.get('joint_actions', {}))
    for wrapper in result.get('joint_actions', {}).values():
        for round_record in wrapper.get('refusal_recourse', {}).get('rounds', []):
            allocation = round_record['allocation']
            verified_allocations[digest(allocation)] = {'allocation': allocation}
    used = set()
    onboarding_seen = set()
    collections, accepted = 0, 0
    for ident, row in orders.items():
        price = _integer(row.get('price'), 'ORDER_PRICE', positive=True)
        _integer(row.get('complete_cost'), 'ORDER_COMPLETE_COST')
        funding = row.get('production_funding_receipt', row.get('funding_receipt'))
        if not isinstance(funding, dict) or resource_receipts.get(funding.get('id')) != funding:
            raise ValueError('PRODUCTION_FUNDING_RECEIPT_NOT_SOURCE_BOUND_TO_NATIVE_ACCOUNT')
        resource = resource_requests[funding['id']]
        if funding['id'] != ident + '-resources' or resource['kind'] != 'production_contract' or resource['work'].get('job_id') != row['job_id'] or resource['work'].get('offer') != row['offer'] or resource['expected_net'] != price - row['complete_cost']:
            raise ValueError('PRODUCTION_RESOURCE_CONTRACT_DOES_NOT_BIND_THIS_ORDER')
        if funding['day'] > row['production_time']:
            raise ValueError('PRODUCTION_BEFORE_RESOURCE_CONTRACT_FINANCED')
        cfg = result['config']
        fee = (price * cfg['payment_bps'] + 9999) // 10000 + cfg['payment_fixed']
        onboard = 0 if row['customer_id'] in onboarding_seen else cfg['onboarding_cost']
        onboarding_seen.add(row['customer_id'])
        units=row['offer']['capacity_units'] if 'complete_offer_policy' in cfg else 1
        if 'complete_offer_policy' in cfg and row.get('capacity_units')!=units:raise ValueError('COMPLETE_SCOPE_CAPACITY_UNITS_CHANGED')
        production = units*(cfg['production_cost'] + cfg['supplier_unit_cost'])
        premium=_check_order_terms(result,row,offers[ident],tape,operating)
        expected_cost = production + units*cfg['support_cost'] + fee + onboard + premium
        if row.get('method_plan'):expected_cost+=row['method_plan']['cost']
        contract=cfg.get('mechanism_policy',{}).get('cost_contract')
        if contract is not None and row.get('method_plan'):
            if contract['production_envelope_microUSD']!=cfg['production_cost'] or resource['work'].get('production_envelope_microUSD')!=cfg['production_cost'] or row['method_plan'].get('cost_contract')!=contract:raise ValueError('COMMON_PRODUCTION_COST_NOT_SOURCE_BOUND')
        if row.get('fee') != fee or row.get('onboarding') != onboard or row.get('production_cost') != production or row.get('support_cost') != units*cfg['support_cost'] or row['complete_cost'] != expected_cost or funding['amount'] != (expected_cost-fee-premium if 'terms' in row else expected_cost) or row.get('resource_cost',expected_cost-fee-premium) != expected_cost-fee-premium:
            raise ValueError('COMPLETE_PRODUCTION_FEES_SUPPORT_ONBOARDING_COST_MISMATCH')
        native = native_orders[ident]
        offered = offers[ident]
        actions = native_events.get(ident, {})
        if offered['args']['price'] != price or offered['args']['job_id'] != row['job_id'] or int(native['price']) != price:
            raise ValueError('ORDER_NATIVE_PRICE_OR_JOB_MISMATCH')
        qualified = _integer(row.get('qualified_time'), 'QUALIFIED_TIME')
        produced = _integer(row.get('production_time'), 'PRODUCTION_TIME')
        _check_contract_clock(ident, offered, actions, operating, qualified, cfg)
        acceptance = row.get('acceptance_time')
        if produced < qualified or (acceptance is not None and _integer(acceptance, 'ACCEPTANCE_TIME') < produced):
            raise ValueError('QUALIFICATION_PRODUCTION_ACCEPTANCE_ORDER')
        if 'consent' not in actions or 'fund' not in actions:
            raise ValueError('VOLUNTARY_FUNDED_ORDER_REQUIRED')
        if actions['consent']['day'] != qualified or actions['fund']['day'] != qualified:
            raise ValueError('NATIVE_CONSENT_PRODUCTION_ACCEPTANCE_TIME_MISMATCH')
        if qualified < offered['day'] or actions['consent']['seq'] > actions['fund']['seq']:
            raise ValueError('NATIVE_LIFECYCLE_CAUSAL_ORDER')
        if offered['day'] != qualified or produced != qualified + result['config']['production_hours']:
            raise ValueError('QUALIFIED_PRODUCTION_CONTRACT_TIMING_CHANGED')
        for kind, moment in [('QUALIFIED_ORDER', qualified), ('PRODUCTION', produced)]:
            if operating.get((ident, kind), {}).get('time') != moment:
                raise ValueError('ORDER_LIFECYCLE_EVENT_MISSING_OR_CHANGED:' + kind)
        job = jobs.get(row['job_id'])
        if job is None or row.get('work_keys') != job['work_keys'] or used.intersection(job['work_keys']):
            raise ValueError('DUPLICATED_OR_UNBOUND_DELIVERY_WORK')
        used.update(job['work_keys'])
        if 'mechanism_policy' in cfg:
            from .mechanism_choice import audit_order
            memory=row.get('method_plan',{}).get('memory')
            if memory is not None:
                positions={(e.get('order_id'),e['kind']):i for i,e in enumerate(result['events']) if e.get('order_id') is not None}
                prior=[o for o in orders.values() if o['production_time']<=row['qualified_time'] and positions.get((o['id'],'PRODUCTION'),len(result['events']))<positions.get((row['id'],'QUALIFIED_ORDER'),-1) and o.get('method_execution',{}).get('mode')=='critic_retain' and o.get('method_execution',{}).get('memory')==memory]
                if not prior:raise ValueError('RETAINED_CONTEXT_HAS_NO_PRIOR_OPERATING_ACQUISITION')
            audit_order(root,manifest,row,result['owned_account'],cfg['mechanism_policy'],verified_allocations)
        elif 'method_plan' in row:raise ValueError('UNAUTHORIZED_METHOD_POLICY')
        if row.get('method_plan',{}).get('mode')=='csv_backend':
            from .csv_backend029 import execute_service
            fresh=execute_service(root,manifest,row['offer'],row['job_id'],'conventional',row['method_plan']['backend'])
        else:fresh = execute_offer(root, manifest, row['offer'], row['job_id'],context=row.get('method_execution',{}).get('context'))
        recorded = row.get('service_receipt')
        if not isinstance(recorded, dict):
            raise ValueError('EXECUTED_SERVICE_RECEIPT_REQUIRED')
        if row['outcome'] == 'QUALITY_REJECTED':
            if fresh.get('accepted') is not False or recorded.get('accepted') is not False or 'prepare' in actions or acceptance is not None:
                raise ValueError('QUALITY_REJECTION_MUST_PRESERVE_FAILED_ACCEPTANCE')
            if native['state'] != 'refunded' or 'refund' not in actions or row.get('collection_time') is not None:
                raise ValueError('REJECTED_DELIVERY_MUST_REFUND_FUNDED_CUSTOMER')
            _check_contract_clock(ident, offered, actions, operating, qualified, cfg,
                                  refund_due=produced + _integer(cfg.get('acceptance_hours'), 'ACCEPTANCE_HOURS', positive=True))
            continue
        if fresh.get('accepted') is not True or acceptance is None or 'prepare' not in actions:
            raise ValueError('INDEPENDENT_USEFUL_OUTPUT_NOT_ACCEPTED')
        if actions['prepare']['day'] != acceptance or actions['fund']['seq'] > actions['prepare']['seq']:
            raise ValueError('NATIVE_ACCEPTANCE_TIME_OR_SEQUENCE_MISMATCH')
        if acceptance != produced + result['config']['acceptance_hours'] or operating.get((ident, 'ACCEPTANCE'), {}).get('time') != acceptance:
            raise ValueError('INDEPENDENT_ACCEPTANCE_LIFECYCLE_EVENT_MISMATCH')
        for field in ['accepted', 'artifact_sha256', 'actual_execution_artifact_sha256', 'native_delivered_artifact_sha256', 'useful_outcome_sha256', 'outcome_scope', 'work_keys', 'artifact']:
            if recorded.get(field) != fresh.get(field):
                raise ValueError('DELIVERY_RECEIPT_RECOMPUTATION_MISMATCH:' + field)
        if row['offer'].get('scope') != 'complete_outcome' or fresh.get('outcome_scope') != 'complete_outcome':
            raise ValueError('INCOMPLETE_OUTCOME_CANNOT_QUALIFY_COMPLETE_COMMERCE')
        default = _private_draw(result['seed'], [row['customer_id'], qualified, row['offer']['service_id']], 'nonpayment') < cfg['nonpayment_bps'] / 10000
        due = qualified + cfg['payment_deadline_hours'] if default else acceptance + cfg['clearing_hours']
        if row['outcome'] == 'SETTLED':
            collection = _integer(row.get('collection_time'), 'COLLECTION_TIME')
            if native['state'] != 'released' or 'release' not in actions or actions['release']['day'] != collection or collection < acceptance:
                raise ValueError('COLLECTION_WITHOUT_PRIOR_ACCEPTANCE_AND_NATIVE_RELEASE')
            if operating.get((ident, 'COLLECTION'), {}).get('time') != collection or collection != acceptance + cfg['clearing_hours']:
                raise ValueError('COLLECTION_EVENT_OR_CLEARING_CONTRACT_MISMATCH')
            collections += price
        elif row['outcome'] == 'REFUNDED':
            if native['state'] != 'refunded' or 'refund' not in actions or row.get('collection_time') is not None:
                raise ValueError('REFUND_MUST_PRESERVE_NATIVE_OBLIGATION')
            _check_contract_clock(ident, offered, actions, operating, qualified, cfg, refund_due=due)
        elif row['outcome'] == 'PENDING':
            if native['state'] != 'verified' or row.get('collection_time') is not None:
                raise ValueError('PENDING_ORDER_CANNOT_BE_COLLECTION')
        else:
            raise ValueError('SUPPORTED_NATIVE_ORDER_OUTCOME_REQUIRED')
        if result.get('complete') and row['outcome'] == 'PENDING':
            raise ValueError('COMPLETED_RUN_HAS_UNRESOLVED_ORDER')
        if row.get('clearing_due_time') != due or (result.get('complete') and row['outcome'] != ('REFUNDED' if default else 'SETTLED')):
            raise ValueError('FROZEN_PAYMENT_SHOCK_OR_CASH_TIMING_CHANGED')
        accepted += 1
    if collections != result['summary']['collections']:
        raise ValueError('OPERATING_COLLECTIONS_DIFFER_FROM_NATIVE_RECEIPTS')
    costs = _unique(result['costs'], 'id', 'COST')
    expense = sum(_integer(row.get('amount'), 'COMPLETE_COST') for row in costs.values())
    if expense != result['summary']['expenses']:
        raise ValueError('FULL_ENTERPRISE_COSTS_DO_NOT_RECONCILE')
    budget_receipt = check_budgets(result['buyers'], list(orders.values()))
    _check_buyer_origins(result['config'], result['seed'], result['buyers'])
    from .buyer_income import audit_income
    income_receipt=audit_income(result)
    cost_semantics = _check_cost_semantics(result, tape, lifecycle_receipt,startup_evaluation_required=strategic_receipt.get('startup_evaluation_required',False))
    commercial_receipt = _check_commercial_result(result)
    investment_receipt = _check_investments(result, tape, orders)
    channel_receipt = check_channels(result['channels'], result['investments'], result['buyers'],
                                     contracts=result['config']['channels'], seed=result['seed'])
    receipt = {'schema': 'agi-alpha/connected014-independent-audit/v1', 'accepted': True,
            'scope': 'NATIVE_FINANCIAL_AND_OPERATING_SEMANTICS',
            'independence': 'Separate checking code in the same agent session and host; not independent institutions or live counterparties.',
            'native_actions_sha256': tape['actions_sha256'], 'orders_reexecuted': accepted,
            'verifier_source_sha256': EXECUTING_VERIFIER_SHA256,
            'verifier_matches_world_source_snapshot': result['source']['files'].get('connected_enterprise/verify.py') == EXECUTING_VERIFIER_SHA256,
            'collections_microUSD': collections, 'complete_costs_microUSD': expense,
            **source_receipt, **budget_receipt, **income_receipt, **investment_receipt, **channel_receipt, **market_receipt,
            **{k:v for k,v in lifecycle_receipt.items() if k!='daily_public_buyers'}, **cost_semantics, **commercial_receipt, **strategic_receipt}
    return json.loads(canonical(receipt))


def _check_investments(result, tape, orders):
    investments = _unique(result['investments'], 'plan_id', 'PRODUCTIVE_INVESTMENT')
    reservations = {row['args']['id']: row for row in tape['actions'] if row['op'] == 'reserve'}
    finished = {row['args']['id']: row for row in tape['actions'] if row['op'] == 'finish'}
    resource_receipts = {entry['receipt']['plan_id']: entry['receipt']
                         for entry in result['owned_account']['connected_journal']['entries']
                         if entry['request']['operation'] == 'spend' and entry['receipt'].get('plan_id')}
    resource_requests = {entry['receipt']['plan_id']: entry['request']
                         for entry in result['owned_account']['connected_journal']['entries']
                         if entry['request']['operation'] == 'spend' and entry['receipt'].get('plan_id')}
    from .startup_acquisition048 import reference as startup_reference
    for entry in result['owned_account']['connected_journal']['entries']:
        if entry['request']['operation']=='spend' and entry['request'].get('work',{}).get('startup_contract') is not None:
            key=startup_reference(entry['receipt'])
            resource_receipts[key]=entry['receipt'];resource_requests[key]=entry['request']
    linked = 0
    exposure_keys = {(customer, row['source_plan_id'], row['day'] * 24)
                     for customer, rows in result['channels']['contacts'].items() for row in rows}
    owned = set(sorted(row['id'] for row in result['buyers'])[:4])
    capacity_use = {}
    qualified_daily = {}
    for ident, row in investments.items():
        moment = _integer(row.get('purchased_time'), 'INVESTMENT_PURCHASE_TIME')
        activation = _integer(row.get('activation_time'), 'INVESTMENT_ACTIVATION_TIME')
        expiry = row.get('expiry_time')
        cost = _integer(row.get('cost'), 'INVESTMENT_COST', positive=True)
        if activation < moment or (expiry is not None and _integer(expiry, 'INVESTMENT_EXPIRY') <= activation):
            raise ValueError('INVESTMENT_ACTIVATION_EXPIRY_CAUSAL_ORDER')
        reserve, finish = reservations.get(ident), finished.get(ident)
        funding=row.get('funding_receipt',{})
        if funding.get('funding')=='SEED':
            request=resource_requests.get(ident,{})
            startup=request.get('work',{}).get('startup_contract')
            native=tape['actions'][funding['native_event_sequence']]
            if 'startup_acquisition_policy' not in result['config'] or row['kind']!='acquisition' or moment!=0 or not isinstance(startup,dict) or startup.get('schema')!='connected-startup-acquisition/v1' or startup.get('time')!=0 or request.get('allow_seed') is not True or funding.get('plan_id') is not None or ident!=startup_reference(funding) or native['op']!='cost' or native['day']!=0 or native['args']['amount']!=cost or native['before']['available']<cost or native['before'].get('investmentStopped'):
                raise ValueError('SEED_ACQUISITION_REQUIRES_EXACT_NATIVE_STARTUP_CONTRACT')
        else:
            if reserve is None or finish is None or reserve['day'] > moment or finish['day'] > activation or finish['args']['amount'] != cost:
                raise ValueError('PRODUCTIVE_CAPABILITY_NOT_NATIVE_EARNED_FUNDED')
            if reserve['before']['unrestrictedEarned'] < cost:
                raise ValueError('FUTURE_COLLECTIONS_OR_RESTRICTED_FUNDS_FINANCE_INVESTMENT')
            if funding.get('funding') != 'EARNED':
                raise ValueError('PRODUCTIVE_INVESTMENT_EARNED_FUNDING_RECEIPT_REQUIRED')
        if row['funding_receipt'] != resource_receipts.get(ident):
            raise ValueError('PRODUCTIVE_INVESTMENT_RECEIPT_NOT_NATIVE_SOURCE_BOUND')
        request = resource_requests[ident]
        if request['expected_net'] <= 0 or request['expected_net'] != row.get('predicted_net'):
            raise ValueError('PRODUCTIVE_INVESTMENT_FORECAST_NOT_SOURCE_BOUND')
        if row['kind'] == 'acquisition' and request['work'].get('terms') != row.get('contract_receipt', {}).get('terms'):
            raise ValueError('ACQUISITION_CONTRACT_TERMS_DIFFER_FROM_FINANCED_WORK')
        if row['kind']=='acquisition' and 'channel_menu_policy' in result['config']:
            contract_id=row.get('contract_id');terms=result['config']['channels'].get(contract_id)
            if contract_id not in result['config']['channel_menu_policy']['contract_ids'] or request['work'].get('contract_id')!=contract_id or row.get('contract_receipt',{}).get('contract_id')!=contract_id or terms!=request['work'].get('terms') or request.get('kind')!='acquisition_contract' or request.get('id')!=row['id'] or request.get('amount')!=cost or request.get('day')!=moment or cost!=terms['price_microUSD']+terms['support_microUSD']:
                raise ValueError('MENU_CHANNEL_NOT_BOUND_TO_NATIVE_INVOICE')
        if row['kind'] == 'capacity':
            work, cfg = request.get('work'), result['config']
            if not isinstance(work, dict):
                raise ValueError('CAPACITY_FINANCED_TIMING_TERMS_REQUIRED')
            lead = _integer(work.get('lead_hours'), 'CAPACITY_FINANCED_LEAD', positive=True)
            duration = _integer(work.get('duration_hours'), 'CAPACITY_FINANCED_DURATION', positive=True)
            units = _integer(work.get('units_per_day'), 'CAPACITY_FINANCED_UNITS', positive=True)
            if (lead != _integer(cfg.get('capacity_lead_hours'), 'FROZEN_CAPACITY_LEAD', positive=True)
                    or duration != _integer(cfg.get('capacity_duration_hours'), 'FROZEN_CAPACITY_DURATION', positive=True)
                    or units != row.get('capacity_units',1)
                    or ('capacity_menu' not in cfg.get('strategic_allocation_policy',{}) and units!=1)
                    or ('capacity_menu' in cfg.get('strategic_allocation_policy',{}) and units>cfg['strategic_allocation_policy']['capacity_menu']['max_quantity'])):
                raise ValueError('CAPACITY_TERMS_DIFFER_FROM_FROZEN_SUPPLIER_CONTRACT')
            if (request.get('id') != row.get('id') or request.get('kind') != 'capacity_contract'
                    or _integer(request.get('amount'), 'CAPACITY_FINANCED_COST', positive=True) != cost
                    or _integer(request.get('day'), 'CAPACITY_FINANCED_PURCHASE_TIME') != moment
                    or _integer(row['funding_receipt'].get('day'), 'CAPACITY_RECEIPT_PURCHASE_TIME') != moment
                    or _integer(reserve['day'], 'CAPACITY_NATIVE_RESERVE_TIME') != moment
                    or _integer(finish['day'], 'CAPACITY_NATIVE_INVOICE_TIME') != moment):
                raise ValueError('CAPACITY_PURCHASE_NOT_BOUND_TO_NATIVE_INVOICE')
            if activation != moment + lead or _integer(expiry, 'CAPACITY_EXPIRY', positive=True) != activation + duration:
                raise ValueError('CAPACITY_LIFETIME_DIFFERS_FROM_FINANCED_CONTRACT')
    for order in orders.values():
        day = order['qualified_time'] // 24
        units=order.get('capacity_units',1)
        if 'complete_offer_policy' in result['config']:
            cfg=result['config'];previous=qualified_daily.get(day,0)
            available=[i for i in result['investments'] if i['kind']=='capacity' and i['activation_time']<=order['qualified_time'] and order['production_time']<i['expiry_time']]
            available=[i for i in available for _ in range(i.get('capacity_units',1))]
            expected=[available[index-cfg['initial_slots']]['plan_id'] for index in range(previous,previous+units) if index>=cfg['initial_slots'] and index-cfg['initial_slots']<len(available)]
            if len(expected)!=max(0,previous+units-cfg['initial_slots'])-max(0,previous-cfg['initial_slots']) or order.get('capacity_source_plan_ids')!=expected or order.get('capacity_source_plan_id')!=(expected[0] if expected else None):raise ValueError('ALL_PACKET_CAPACITY_UNITS_REQUIRE_CURRENT_AUTHORITY')
        qualified_daily[day] = qualified_daily.get(day, 0) + units
        acquisition = order.get('acquisition_source_plan_id')
        if acquisition is None and order['customer_id'] not in owned:
            raise ValueError('NONOWNED_CUSTOMER_WITHOUT_PAID_ACCESS')
        if acquisition is not None and (order['customer_id'], acquisition, order.get('exposure_time')) not in exposure_keys:
            raise ValueError('ACQUIRED_ORDER_WITHOUT_ACTUAL_PRIOR_EXPOSURE')
        references=[('acquisition_source_plan_id',order.get('acquisition_source_plan_id'))]+[('capacity_source_plan_id',ident) for ident in order.get('capacity_source_plan_ids',[order.get('capacity_source_plan_id')])]
        for field,ident in references:
            if ident is None:
                continue
            if ident not in investments:
                raise ValueError('DELIVERY_USES_UNPURCHASED_CAPABILITY')
            investment = investments[ident]
            used_at = order.get('exposure_time', order.get('acquisition_time')) if field.startswith('acquisition') else order['production_time']
            _integer(used_at, 'CAPABILITY_USE_TIME')
            if used_at < investment['activation_time'] or (investment.get('expiry_time') is not None and used_at >= investment['expiry_time']):
                raise ValueError('DELIVERY_USES_UNACTIVATED_OR_EXPIRED_CAPABILITY')
            if field.startswith('acquisition') and used_at > order['qualified_time']:
                raise ValueError('QUALIFIED_ORDER_BEFORE_PAID_EXPOSURE')
            if field.startswith('capacity'):
                key = (ident, day)
                capacity_use[key] = capacity_use.get(key, 0) + 1
                if capacity_use[key] > investment.get('capacity_units',1):
                    raise ValueError('PAID_CAPACITY_UNIT_REUSED_WITHIN_DAY')
            if order['outcome'] == 'SETTLED':
                linked += 1
    cfg = result['config']
    for day, count in qualified_daily.items():
        moment = day * 24
        active = sum(row.get('capacity_units',1) for row in investments.values() if row['kind'] == 'capacity' and row['activation_time'] <= moment < row['expiry_time'])
        capacity = min(cfg['maximum_slots'], cfg['initial_slots'] + active)
        if cfg['supplier_outage_start_day'] <= day < cfg['supplier_outage_start_day'] + cfg['supplier_outage_days']:
            capacity = 0
        if count > capacity:
            raise ValueError('FINITE_SUPPLIER_THROUGHPUT_EXCEEDED')
    return {'productive_investments_checked': len(investments), 'settled_capability_uses_checked': linked}
