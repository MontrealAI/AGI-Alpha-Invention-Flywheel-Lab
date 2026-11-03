"""Whole-package competition and causal action intents atop the existing Omega model.

This is a finite, authored receding-horizon policy comparison, not a new ledger,
market calibration, Nash equilibrium, or global enterprise optimum. Native money
and durable execution belong to primary_operator; these functions move no money.
"""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import hashlib
from fractions import Fraction
from itertools import combinations, product
from commercial.ledger import digest
from omega import strategy

MODES = ('nonentry', 'simple', 'no_research', 'ordinary_reuse', 'staged', 'joint')
PUBLIC_FIELDS = {'quarter', 'available_cents', 'built_products', 'content_available',
                 'research_signal', 'founder_minutes_available','observed_delivery_outcome'}
REACH = Fraction(1, 2)
ACQUISITION_CENTS = 1500
RIVAL_PRICES = (19900, 29900, 49900)
RIVAL_COST_CENTS = 8000
RIVAL_ENTRY_CENTS = 500
COMPLEMENT_CENTS = 15000
FOUNDER_MINUTES = 450
WEBINAR_MINUTES = 330
RIVAL_BUDGET_CENTS = 100000


def registration():
    return {'schema': 'omega-competitive/v1', 'currency': 'USD', 'unit': 'integer cents',
            'base_model': 'omega.strategy.make_game:16 authored worlds; four quarters',
            'own_prices_cents': strategy.PRICES, 'modes': list(MODES),
            'acquisition_cents_per_three_prospect_attempt': ACQUISITION_CENTS,
            'common_reach_probability': str(REACH), 'reach_independent_of_world': True,
            'rival_prices_cents': list(RIVAL_PRICES), 'rival_fulfillment_cents': RIVAL_COST_CENTS,
            'rival_entry_cents': RIVAL_ENTRY_CENTS, 'rival_may_withdraw': True,
            'training_download_webinar_complement_cents': COMPLEMENT_CENTS,
            'ordinary_outcome_counted_once': True, 'quarterly_founder_minutes': FOUNDER_MINUTES,
            'cost_envelopes': {'autonomous_machine_bill_cents': {'low':10000,'central':100000,'high':1000000},
                               'human_control_packaging_hours': {'low':20,'central':80,'high':160}},
            'autonomous_information_cost_cents':100, 'webinar_minutes':WEBINAR_MINUTES,
            'webinar_noncash_opportunity_cents':110000, 'group_processing_cents':832,
            'eventbrite_basis':'US absorbed fee envelope:3.7%+$1.79ticket +2.9%order; actual Canadian contract unresolved',
            'rival_current_budget_cents':RIVAL_BUDGET_CENTS,
            'evaluation': 'All16worlds x reached/not_reached x six matched modes x three autonomous plus three human control envelopes',
            'development': 'Generic choice, shared-budget, refusal, funding and information-boundary unit cases',
            'freshness': 'Prospective exposed authored evaluation; not hidden empirical holdout',
            'reach_evaluation_scope':'Two persistent annual stress paths, all reached or all unreached, weighted1/2; not all16 independent quarterly Bernoulli paths',
            'weighted_result_scope':'Weighted authored scenario result, not calibrated forecast or policy-expected optimum',
            'expanded_confirmation':'Registered after initial extreme-path inspection: all16 quarterly reach paths with weight1/16, crossed with all16 original worlds, unchanged policies and cost profiles',
            'decision_information': 'Current native available cash, owned products/content, previously paid research signal and completed native delivery outcome only',
            'limits': ['Forecasts do not fund actions', 'No actual customer, rival, calibration or demand',
                       'Best tested receding-horizon policy, not globally optimal dynamic game',
                       'Content and equivalent ordinary reuse receive identical permissions and costs',
                       'Only paid signal and completed delivery outcome update public beliefs; purchase/decline likelihood is not modeled',
                       'Research buys modeled information, not autonomous invention of a new capability',
                       'Buyer payoff after refund assumes adoption effort is lost; outside payoff is a modeled counterfactual, not observed delivery',
                       'Actual development/model/host costs, taxes and rights remain unresolved']}


def make_game(*, cost_scenario='low', operation='autonomous', **kwargs):
    if operation not in ('autonomous', 'human_control') or cost_scenario not in ('low','central','high'):
        raise ValueError('REGISTERED_OPERATION_AND_COST_ENVELOPE_REQUIRED')
    if 'costs' in kwargs:
        raise ValueError('USE_EXPLICIT_GAME_FOR_NONREGISTERED_COST_SENSITIVITY')
    costs = strategy.Costs(packaging_hours={'low':20,'central':80,'high':160}[cost_scenario],
                           processing_cents=(897,832,58030))
    if operation == 'autonomous':
        costs = replace(costs, packaging_hours=0, loaded_labor_cents_per_hour=0,
                        ai_build_bill_cents={'low':10000,'central':100000,'high':1000000}[cost_scenario],
                        research_cents=100, webinar_facilitation_cents=0)
    return strategy.make_game(costs=costs, **kwargs)


def _subsets(items):
    items = tuple(items)
    return [tuple(c) for n in range(1, len(items)+1) for c in combinations(items, n)]


def _public(value, game):
    if type(value) is not dict or set(value) != PUBLIC_FIELDS:
        raise ValueError('PUBLIC_HISTORY_AND_NATIVE_STATE_ONLY')
    for key in ('quarter', 'available_cents', 'founder_minutes_available'):
        if type(value[key]) is not int or value[key] < 0:
            raise ValueError('NONNEGATIVE_PUBLIC_INTEGER_REQUIRED')
    if value['quarter'] > game.quarters or type(value['content_available']) is not bool:
        raise ValueError('DECLARED_PUBLIC_CAPABILITY_STATE_REQUIRED')
    if value['observed_delivery_outcome'] not in (None,'accepted','rejected_refunded'):
        raise ValueError('COMPLETED_NATIVE_DELIVERY_OBSERVATION_REQUIRED')
    if value['research_signal'] not in (None, 'positive', 'negative'):
        raise ValueError('OBSERVED_RESEARCH_SIGNAL_REQUIRED')
    if type(value['built_products']) is not list or len(set(value['built_products'])) != len(value['built_products']) or any(p not in strategy.PRODUCTS for p in value['built_products']):
        raise ValueError('UNIQUE_PUBLIC_BUILT_PRODUCTS_REQUIRED')
    return deepcopy(value)


def _support(game, signal, outcome=None):
    worlds = tuple(w for w in game.worlds if (signal is None or w.signal == signal) and
                   (outcome is None or w.adverse == (outcome=='rejected_refunded')))
    total = sum((w.prior for w in worlds), Fraction())
    if total <= 0:
        raise ValueError('PUBLIC_SIGNAL_HAS_NO_REGISTERED_SUPPORT')
    return [(w, w.prior/total) for w in worlds]


def environment_signal(world_id, game=None):
    game = game or make_game()
    return next(w.signal for w in game.worlds if w.id == world_id)


def choose_bundle(game, world, prospect, offers, rival_price=None, *, already_spent_cents=0,
                  complement_cents=COMPLEMENT_CENTS, allowed_bundles=None):
    if type(already_spent_cents) is not int or already_spent_cents < 0 or type(complement_cents) is not int or complement_cents < 0:
        raise ValueError('NONNEGATIVE_BUYER_COST_REQUIRED')
    if len(set(offers)) != len(offers) or any(p not in strategy.PRODUCTS for p in offers):
        raise ValueError('DECLARED_UNIQUE_COMPLETE_PRODUCTS_REQUIRED')
    old = strategy.buyer_choice(game, world, prospect, strategy.PRODUCTS)
    budget = old['budget_cents']
    if already_spent_cents > budget:
        raise ValueError('BUYER_BUDGET_CANNOT_INCREASE')
    remaining = budget-already_spent_cents
    zero = world.regime == 'commodity' and world.adverse
    outcome = 0 if zero else old['ordinary_outcome_value_cents']
    premium = 0 if zero else old['founder_access_premium_cents']
    effort = {}
    for p in strategy.PRODUCTS:
        if p in old['utilities_cents']:
            effort[p] = outcome+(premium if p == 'founder_private' else 0)-strategy.PRICES[p]-old['utilities_cents'][p]
        else:
            effort[p] = 0 if p == 'founder_private' else 4000
    options = [{'id': 'no_purchase', 'provider': 'decline', 'products': [], 'price_cents': 0, 'utility_cents': 0}]
    outside_prices = {'self_service_incumbent': 0, 'open_core': 0, 'ordinary_provider': 50000}
    for name, price in outside_prices.items():
        if price <= remaining:
            options.append({'id': name, 'provider': 'outside', 'products': [], 'price_cents': price,
                            'utility_cents': old['utilities_cents'].get(name, -10**30)})
    if rival_price is not None:
        if type(rival_price) is not int or rival_price not in RIVAL_PRICES:
            raise ValueError('REGISTERED_RIVAL_PRICE_REQUIRED')
        if rival_price <= remaining:
            options.append({'id': 'rival_download', 'provider': 'rival', 'products': ['self_hosted'],
                            'price_cents': rival_price, 'utility_cents': outcome-rival_price-effort['self_hosted']})
    for bundle in _subsets(offers):
        if allowed_bundles is not None and tuple(bundle) not in allowed_bundles:
            continue
        price = sum(strategy.PRICES[p] for p in bundle)
        if price > remaining:
            continue
        complement = complement_cents if not zero and world.regime == 'training' and {'self_hosted', 'group_webinar'} <= set(bundle) else 0
        value = outcome+(premium if 'founder_private' in bundle else 0)+complement
        options.append({'id': 'us:'+'+'.join(bundle), 'provider': 'us', 'products': list(bundle),
                        'price_cents': price, 'utility_cents': value-price-min(effort[p] for p in bundle),
                        'buyer_value_before_price_cents': value, 'adoption_effort_cents': min(effort[p] for p in bundle)})
    rank = {'decline': 0, 'outside': 1, 'rival': 2, 'us': 3}
    chosen = min(options, key=lambda o: (-o['utility_cents'], rank[o['provider']], o['id']))
    return {**chosen, 'budget_cents': budget, 'spent_before_cents': already_spent_cents,
            'remaining_before_cents': remaining, 'alternatives': options,
            'joint_choice': True, 'synthetic_consent': chosen['provider'] == 'us',
            'ordinary_outcome_counted_once': True,
            'best_outside_promised_net_cents':max(o['utility_cents'] for o in options if o['provider']!='us')}


def buyer_payoff(choice,status):
    if choice['provider']!='us':
        return {'our_realized_outcome_value_cents':0,'our_retained_fee_cents':0,'our_realized_buyer_net_cents':0,
                'outside_chosen_promised_net_cents':choice['utility_cents'],'our_incremental_buyer_net_cents':None,
                'payoff_basis':'Outside choice is modeled, not an executed outside-provider delivery'}
    effort=choice['adoption_effort_cents']
    accepted=status=='accepted'
    value=choice['buyer_value_before_price_cents'] if accepted else 0
    fee=choice['price_cents'] if accepted else 0
    net=value-effort-fee
    return {'our_realized_outcome_value_cents':value,'our_retained_fee_cents':fee,
            'our_buyer_value_before_fee_after_effort_cents':value-effort,
            'our_realized_buyer_net_cents':net,'outside_chosen_promised_net_cents':None,
            'our_incremental_buyer_net_cents':net-choice['best_outside_promised_net_cents'],
            'payoff_basis':'Authored realized delivery; refund loses adoption effort; best outside comparator is promised modeled net, not observed counterfactual'}


def rival_best_response(game, public, offers, build=()):
    _public(public, game)
    rows = []
    for price in (None, *RIVAL_PRICES):
        margin, seller = Fraction(), Fraction()
        action = {'kind':'operate','build':list(build),'offers':list(offers)}
        for world, weight in _support(game, public['research_signal'],public['observed_delivery_outcome']):
            row = _row(game, public, action, {'price_cents':price}, world, True)
            wins = [c for c in row['buyer_decisions'] if c['provider']=='rival']
            if len(wins)*RIVAL_COST_CENTS+(RIVAL_ENTRY_CENTS if price is not None else 0)>RIVAL_BUDGET_CENTS:
                raise ValueError('RIVAL_CURRENT_CASH_REQUIRED')
            if price is not None:
                margin += weight*REACH*len(wins)*((0 if world.adverse else price)-RIVAL_COST_CENTS)
            seller += weight*REACH*row['accepted_revenue_cents']
        rows.append({'price_cents':price,'expected_profit_cents':str(margin-(0 if price is None else RIVAL_ENTRY_CENTS)),
                     'seller_revenue_cents':str(seller)})
    chosen = min(rows,key=lambda r:(-Fraction(r['expected_profit_cents']),Fraction(r['seller_revenue_cents']),
                                    -1 if r['price_cents'] is None else r['price_cents']))
    return {'price_cents':chosen['price_cents'],'expected_profit_cents':chosen['expected_profit_cents'],
            'alternatives':rows,'information_sha256':digest({'public':public,'offers':list(offers),'build':list(build)}),
            'optimality':'Exact one-quarter response over registered rival prices and current feasible own packages; not full dynamic equilibrium'}


def _row(game, public, action, rival, world, reached):
    costs = game.costs; quarter = public['quarter']
    build = sum(costs.build(p) for p in action['build'])
    session = costs.webinar_platform_cents+costs.webinar_unknown_base_cents+costs.webinar_facilitation_cents if 'group_webinar' in action['offers'] else 0
    fixed = build+ACQUISITION_CENTS+session
    available = public['available_cents']-fixed
    if available < 0:
        raise ValueError('CURRENT_NATIVE_CASH_REQUIRED')
    minutes = WEBINAR_MINUTES if 'group_webinar' in action['offers'] else 0
    session_opportunity = (minutes*costs.founder_opportunity_cents_per_hour+30)//60 if costs.webinar_facilitation_cents == 0 else 0
    cash_cost, revenue, opportunity, residual = fixed, 0, session_opportunity, 0
    capacities = {'self_hosted': game.prospects_per_quarter, 'group_webinar': costs.webinar_seats_per_session,
                  'founder_private': costs.founder_slots_per_quarter}
    orders, choices = [], []
    if reached:
        for prospect in range(game.prospects_per_quarter):
            feasible = []
            for package in _subsets(action['offers']):
                pprice=sum(strategy.PRICES[p] for p in package); pexpense=sum(costs.order(p) for p in package)
                ptime=sum(costs.founder_total_minutes if p=='founder_private' else 0 for p in package)
                ptime += (costs.exception_minutes_per_order+costs.dispute_minutes_per_refund)*len(package)
                if all(capacities[p]>0 for p in package) and minutes+ptime<=public['founder_minutes_available'] and available>=pprice+pexpense+costs.native_funding_collateral_cents*len(package):
                    feasible.append(package)
            buyer = choose_bundle(game, world, prospect, action['offers'], rival['price_cents'], allowed_bundles=feasible)
            buyer.update(prospect=prospect, buyer_group_id=f'q{quarter}:buyer{prospect}', package_id=buyer['id'],
                         selected_package=buyer['products'], total_price_cents=buyer['price_cents'])
            if buyer['provider'] != 'us':
                buyer['status'] = 'outside'; buyer.update(buyer_payoff(buyer,'outside')); choices.append(buyer); continue
            products = buyer['products']; price = buyer['price_cents']
            expense = sum(costs.order(p) for p in products)
            time = sum(costs.founder_total_minutes if p == 'founder_private' else 0 for p in products)
            time += costs.exception_minutes_per_order*len(products)
            if world.adverse: time += costs.dispute_minutes_per_refund*len(products)
            if any(capacities[p] <= 0 for p in products) or minutes+time > public['founder_minutes_available']:
                buyer['status'] = 'capacity_hold'; choices.append(buyer); continue
            if available < price+expense+costs.native_funding_collateral_cents*len(products):
                buyer['status'] = 'liquidity_hold'; choices.append(buyer); continue
            buyer['status'] = 'accepted' if not world.adverse else 'rejected_refunded'
            buyer.update(buyer_payoff(buyer,buyer['status']))
            choices.append(buyer); minutes += time
            for p in products:
                capacities[p] -= 1
                charge = costs.order(p); earned = 0 if world.adverse else strategy.PRICES[p]
                protected = 0 if world.adverse else strategy.PRICES[p]//100
                cash_cost += charge; revenue += earned; residual += protected
                opportunity += costs.opportunity(p, world.adverse)
                available -= charge+(0 if world.adverse else costs.native_funding_collateral_cents)
                orders.append({'prospect': prospect, 'product': p, 'status': buyer['status'],
                               'price_cents': strategy.PRICES[p], 'cost_cents': charge,
                               'processing_fee_cents': costs.processing_cents[strategy.PRODUCTS.index(p)],
                               'native_cost_cents': costs.native_order_cents[strategy.PRODUCTS.index(p)],
                               'buyer_group_id': buyer['buyer_group_id'], 'package_id': buyer['package_id'], 'buyer': buyer,
                               'noncash_founder_opportunity_cents': costs.opportunity(p, world.adverse)})
    cash_profit = revenue-cash_cost
    return {'quarter': quarter, 'hour': quarter*2160, 'action': deepcopy(action),
            'opening_available_cents': public['available_cents'], 'build_cost_cents': build,
            'outreach_cost_cents': ACQUISITION_CENTS, 'session_cost_cents': session,
            'cost_cents': cash_cost, 'cash_cost_cents': cash_cost, 'accepted_revenue_cents': revenue,
            'cash_profit_cents': cash_profit, 'profit_cents': cash_profit-opportunity,
            'noncash_founder_opportunity_cents': opportunity, 'session_opportunity_cents':session_opportunity, 'new_residual_reserve_cents': residual,
            'mature_available_cents': public['available_cents']+cash_profit-residual,
            'maturity_hour': quarter*2160+721, 'orders': orders, 'buyer_decisions': choices,
            'reached': reached, 'founder_minutes': minutes, 'native_replay_required': True}


def _forecast(game, public, action):
    if public['quarter'] >= game.quarters:
        return None
    build = sum(game.costs.build(p) for p in action['build'])
    fixed = build+ACQUISITION_CENTS
    if 'group_webinar' in action['offers']:
        fixed += game.costs.webinar_platform_cents+game.costs.webinar_unknown_base_cents+game.costs.webinar_facilitation_cents
        webinar_minutes = WEBINAR_MINUTES
        if public['founder_minutes_available'] < webinar_minutes: return None
    if public['available_cents'] < fixed:
        return None
    rival = rival_best_response(game, public, action['offers'], action['build'])
    expected = Fraction()
    for world, weight in _support(game, public['research_signal'],public['observed_delivery_outcome']):
        for reached, reach_weight in ((True, REACH), (False, 1-REACH)):
            row = _row(game, public, action, rival, world, reached)
            expected += weight*reach_weight*row['profit_cents']
    remaining = game.quarters-public['quarter']
    projection = (expected+build)*remaining-build
    return {'action': deepcopy(action), 'rival_response': rival,
            'expected_first_quarter_profit_cents': str(expected), 'expected_remaining_profit_cents': str(projection),
            'fixed_costs_cents': {'build': build, 'acquisition': ACQUISITION_CENTS, 'session': fixed-build-ACQUISITION_CENTS},
            'required_current_cash_cents': fixed,
            'forecast_scope': 'Static continuation projection; actual future actions replan from native cash; not spendable revenue'}


def _best(game, public, mode):
    built = tuple(p for p in strategy.PRODUCTS if p in public['built_products'])
    additions = [()] + [(p,) for p in strategy.PRODUCTS if p not in built]
    best = None
    for addition in additions:
        available = tuple(p for p in strategy.PRODUCTS if p in built or p in addition)
        for offers in _subsets(available):
            if mode == 'simple' and offers != ('self_hosted',): continue
            if mode == 'staged' and len(offers) != 1: continue
            action = {'kind': 'operate', 'build': list(addition), 'offers': list(offers)}
            result = _forecast(game, public, action)
            if result is None: continue
            value = Fraction(result['expected_remaining_profit_cents'])
            if value > 0 and (best is None or value > Fraction(best['expected_remaining_profit_cents'])):
                best = result
    return best


def decide(public, mode='joint', game=None):
    game = game or make_game(); public = _public(public, game)
    if mode not in MODES: raise ValueError('REGISTERED_POLICY_MODE_REQUIRED')
    stop = {'action': {'kind': 'stop', 'build': [], 'offers': []}, 'fixed_costs_cents': {},
            'expected_remaining_profit_cents': '0', 'required_current_cash_cents': 0, 'rival_response': None}
    best = None if mode == 'nonentry' else _best(game, public, mode)
    winner = best or stop
    if mode in ('staged', 'joint', 'ordinary_reuse') and public['research_signal'] is None and public['quarter'] < game.quarters and public['available_cents'] >= game.costs.research_cents:
        research = Fraction(-game.costs.research_cents)
        for signal in ('positive', 'negative'):
            probability = sum((weight for w,weight in _support(game,None,public['observed_delivery_outcome']) if w.signal == signal),Fraction())
            future = dict(public, research_signal=signal, available_cents=public['available_cents']-game.costs.research_cents)
            follow = _best(game, future, mode)
            research += probability*(Fraction(follow['expected_remaining_profit_cents']) if follow else 0)
        if research > Fraction(winner['expected_remaining_profit_cents']):
            winner = {'action': {'kind': 'research', 'build': [], 'offers': []},
                      'fixed_costs_cents': {'research': game.costs.research_cents},
                      'expected_remaining_profit_cents': str(research), 'required_current_cash_cents': game.costs.research_cents,
                      'rival_response': None}
    return {**winner, 'schema': 'omega-competitive-decision/v1', 'mode': mode, 'public': public,
            'public_sha256': digest(public), 'registration_sha256': digest(registration()),
            'game_sha256':digest(strategy.model_disclosure(game)),
            'native_authority': None, 'optimality': 'Best evaluated current menu and optional signal under declared static-continuation forecast'}


def realize(decision, world_id, reached, game=None):
    game = game or make_game()
    if type(reached) is not bool: raise ValueError('ENVIRONMENT_REACH_BOOLEAN_REQUIRED')
    if decision != decide(decision['public'], decision['mode'], game):
        raise ValueError('PREDECISION_POLICY_RECEIPT_CHANGED')
    world = next(w for w in game.worlds if w.id == world_id)
    public = decision['public']; action = decision['action']
    if public['research_signal'] is not None and public['research_signal']!=world.signal:
        raise ValueError('ENVIRONMENT_CONTRADICTS_OBSERVED_SIGNAL')
    if public['observed_delivery_outcome'] is not None and world.adverse!=(public['observed_delivery_outcome']=='rejected_refunded'):
        raise ValueError('ENVIRONMENT_CONTRADICTS_COMPLETED_NATIVE_DELIVERY')
    if action['kind'] != 'operate': raise ValueError('OPERATING_DECISION_REQUIRED')
    return _row(game, public, action, decision['rival_response'], world, reached)


def initial_public(game=None):
    game = game or make_game()
    return {'quarter': 0, 'available_cents': game.capital_cents, 'built_products': [],
            'content_available': False, 'research_signal': None, 'founder_minutes_available': FOUNDER_MINUTES,
            'observed_delivery_outcome':None}


def report(*, expanded=False, include_outcomes=True):
    if type(expanded) is not bool or type(include_outcomes) is not bool:
        raise ValueError('EXPLICIT_REPORT_COVERAGE_FLAGS_REQUIRED')
    rows = []
    for operation,envelope in ((o,e) for o in ('autonomous','human_control') for e in ('low','central','high')):
        game = make_game(cost_scenario=envelope, operation=operation)
        paths = list(product((False,True),repeat=game.quarters)) if expanded else [(False,)*game.quarters,(True,)*game.quarters]
        cache={}
        def cached(public,mode):
            key=(digest(public),mode)
            if key not in cache: cache[key]=decide(public,mode,game)
            return deepcopy(cache[key])
        for mode in MODES:
            first = cached(initial_public(game), mode)
            outcomes = []
            for world in game.worlds:
                for reach_path in paths:
                    public = initial_public(game); profit = 0; actions = []; count = 0
                    buyer_net=0; incremental=0; value=0; buyer_fee=0
                    for _ in range(game.quarters+1):
                        d = cached(public, mode); actions.append(d['action'])
                        if d['action']['kind'] == 'stop': break
                        if d['action']['kind'] == 'research':
                            cost = game.costs.research_cents; profit -= cost
                            public.update(available_cents=public['available_cents']-cost, research_signal=world.signal)
                            continue
                        row = _row(game,public,d['action'],d['rival_response'],world,reach_path[public['quarter']])
                        for b in row['buyer_decisions']:
                            if b['provider']=='us' and b['status'] in ('accepted','rejected_refunded'):
                                buyer_net+=b['our_realized_buyer_net_cents']; incremental+=b['our_incremental_buyer_net_cents']
                                value+=b['our_realized_outcome_value_cents'];buyer_fee+=b['our_retained_fee_cents']
                        profit += row['profit_cents']; count += len(row['orders'])
                        if row['orders']:
                            outcomes_seen={o['status'] for o in row['orders']}
                            if len(outcomes_seen)!=1: raise ValueError('CONSTANT_ADVERSE_WORLD_CONTRADICTED')
                            public['observed_delivery_outcome']=next(iter(outcomes_seen))
                        public.update(quarter=public['quarter']+1, available_cents=row['mature_available_cents'],
                                      built_products=sorted(set(public['built_products'])|set(d['action']['build'])))
                    outcomes.append({'world_id':world.id,'reach_path':list(reach_path),'profit_cents':profit,
                                     'component_orders':count,'actions':actions,'realized_buyer_net_cents':buyer_net,
                                     'realized_buyer_outcome_value_cents':value,'retained_buyer_fees_cents':buyer_fee,
                                     'incremental_buyer_net_vs_promised_outside_cents':incremental})
            weights={w.id:w.prior/Fraction(len(paths)) for w in game.worlds}
            mean=sum((weights[o['world_id']]*o['profit_cents'] for o in outcomes),Fraction())
            buyer_mean=sum((weights[o['world_id']]*o['realized_buyer_net_cents'] for o in outcomes),Fraction())
            row={'operation':operation,'envelope':envelope,'mode':mode,'initial_action':first['action'],
                 'expected_realized_profit_cents':str(mean),'weighted_scenario_buyer_net_cents':str(buyer_mean),
                 'minimum_cents':min(o['profit_cents'] for o in outcomes),'maximum_cents':max(o['profit_cents'] for o in outcomes),
                 'trajectory_count':len(outcomes),'trajectory_sha256':digest(outcomes),
                 'positive_count':sum(o['profit_cents']>0 for o in outcomes),
                 'zero_count':sum(o['profit_cents']==0 for o in outcomes),
                 'negative_count':sum(o['profit_cents']<0 for o in outcomes),
                 'best_witness':max(outcomes,key=lambda o:o['profit_cents']),
                 'worst_witness':min(outcomes,key=lambda o:o['profit_cents'])}
            if include_outcomes: row['outcomes']=outcomes
            rows.append(row)
    root=Path(__file__).resolve().parents[1]
    source={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ('omega/competitive.py','omega/strategy.py','commercial/ledger.py')}
    return {'registration':registration(),'source_files_sha256':source,'comparisons':rows,'native_account_result':None,
            'coverage':'EXPANDED_ALL_QUARTER_REACH_PATHS' if expanded else 'ORIGINAL_TWO_EXTREME_ANNUAL_STRESS_PATHS',
            'registration_timing':'Expanded coverage registered after initial stress inspection; no economic parameter retuning' if expanded else 'Original prospectively registered extreme-path stress',
            'path_count_per_world':16 if expanded else 2,'total_trajectories':sum(r['trajectory_count'] for r in rows),
            'claim':'Executed hypothetical decisions and order intents; no native profit claimed by this report'}
