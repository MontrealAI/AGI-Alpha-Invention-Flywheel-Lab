"""Exact finite, time-causal seller policy experiment. All money is integer US cents.

This is an authored 16-world decision problem, NOT empirical demand, equilibrium,
real-world optimality or evidence of buyer consent. Accounting/native fulfillment
are deliberately separate: execute returns a prospective replay plan, not sales.
"""
from __future__ import annotations
from dataclasses import dataclass, field, replace
from fractions import Fraction
from functools import lru_cache
from itertools import combinations

PRODUCTS = ('self_hosted', 'group_webinar', 'founder_private')
PRICES = dict(zip(PRODUCTS, (29900, 9900, 2000000)))
FEES = dict(zip(PRODUCTS, (897, 317, 58030)))
REGIMES = ('commodity', 'software_convenience', 'training', 'rare_founder_access')
OUTSIDE = ('no_purchase', 'self_service_incumbent', 'open_core', 'ordinary_provider')

def subsets(xs):
    return tuple(tuple(c) for n in range(len(xs)+1) for c in combinations(xs, n))

@dataclass(frozen=True)
class World:
    id: str
    regime: str
    signal: str
    adverse: bool
    prior: Fraction

@dataclass(frozen=True)
class Costs:
    packaging_hours: int = 80
    loaded_labor_cents_per_hour: int = 9340
    ai_build_bill_cents: int = 0  # Unknown; explicit zero-assumption, not measured.
    research_cents: int = 14010  # Authored 1.5 research hours at labor proxy.
    outreach_cents: int = 2335  # Authored 0.25 outreach hours at labor proxy.
    webinar_platform_cents: int = 23700  # Three months at $79 starting platform anchor.
    webinar_unknown_base_cents: int = 0
    webinar_facilitation_cents: int = 51370  # Authored 330 total minutes at labor proxy.
    founder_opportunity_cents_per_hour: int = 20000  # Authored, NOT sale-price derived.
    founder_total_minutes: int = 105  # Authored 15 review +45 prep +30 call +15 admin.
    exception_minutes_per_order: int = 0  # Stress: 12, not an observed exception rate.
    dispute_minutes_per_refund: int = 0  # Stress: 20, not every refund is a dispute.
    native_order_cents: tuple[int, int, int] = (100, 25, 100)
    processing_cents: tuple[int, int, int] = (897, 317, 58030)
    def build(self, product):
        share = dict(zip(PRODUCTS, (40, 25, 35)))[product]
        return ((self.packaging_hours*self.loaded_labor_cents_per_hour + self.ai_build_bill_cents)*share+50)//100
    native_funding_collateral_cents: int = 20
    founder_slots_per_quarter: int = 1
    webinar_seats_per_session: int = 500
    def opportunity(self, product, adverse=False):
        minutes = (self.founder_total_minutes if product == 'founder_private' else 0)
        minutes += self.exception_minutes_per_order
        if adverse: minutes += self.dispute_minutes_per_refund
        return (self.founder_opportunity_cents_per_hour*minutes+30)//60
    def order(self, product):
        i = PRODUCTS.index(product)
        return self.native_order_cents[i] + self.processing_cents[i]

@dataclass(frozen=True)
class Game:
    costs: Costs
    worlds: tuple[World, ...]
    capital_cents: int = 10000000
    quarters: int = 4
    founder_value_cents: int = 2250000
    prospects_per_quarter: int = 3
    def __post_init__(self):
        scalar_inputs = (self.capital_cents,self.quarters,self.founder_value_cents,self.prospects_per_quarter)
        cost_inputs = tuple(getattr(self.costs,k) for k in self.costs.__dataclass_fields__ if not isinstance(getattr(self.costs,k),tuple))
        if any(type(x) is not int for x in (*scalar_inputs,*cost_inputs,*self.costs.native_order_cents,*self.costs.processing_cents)):
            raise ValueError('Integer cent/hour/capacity inputs required; no floats')
        if len(self.costs.native_order_cents) != 3 or len(self.costs.processing_cents) != 3:
            raise ValueError('Exactly three per-product costs required')
        if any(not isinstance(w.prior,Fraction) or w.prior <= 0 for w in self.worlds):
            raise ValueError('Positive exact Fraction world priors required')
        if not 1 <= self.quarters <= 4 or self.prospects_per_quarter != 3:
            raise ValueError('Declared finite model requires 1..4 quarters and three prospects')
        if self.capital_cents < 0 or any(getattr(self.costs, k) < 0 for k in self.costs.__dataclass_fields__ if isinstance(getattr(self.costs,k), int)):
            raise ValueError('Costs and capital must be nonnegative integer cents')
        if any(x < 0 for x in (*self.costs.native_order_cents,*self.costs.processing_cents)):
            raise ValueError('Negative per-order costs')
        if len({w.id for w in self.worlds}) != len(self.worlds) or sum(w.prior for w in self.worlds) != 1:
            raise ValueError('World IDs must be unique and priors sum to one')

def make_game(*, capital_cents=10000000, cost_scenario='central', founder_value_cents=2250000,
              costs=None, quarters=4):
    """Priors/personas are authored, declared before optimization, not fitted results."""
    costs = costs or Costs(packaging_hours={'low':20,'central':80,'high':160}[cost_scenario])
    priors = (Fraction(1,2),Fraction(1,4),Fraction(1,5),Fraction(1,20))
    worlds = []
    for regime, prior in zip(REGIMES, priors):
        positive = Fraction(3,4) if regime in ('training','rare_founder_access') else Fraction(1,4)
        for signal, sp in (('positive',positive),('negative',1-positive)):
            for adverse, ap in ((False,Fraction(3,4)),(True,Fraction(1,4))):
                worlds.append(World(f'{regime}:{signal}:{"adverse" if adverse else "normal"}',regime,signal,adverse,prior*sp*ap))
    return Game(costs,tuple(worlds),capital_cents,quarters,founder_value_cents)

def buyer_choice(game, world, prospect, offers):
    """Full-outcome alternatives with explicit effort, budgets and access premium.

    Every alternative can deliver the SAME ordinary outcome. Access premium is
    independent incremental utility, not pretending paid products alone work.
    Commodity adverse worlds also contain the deliberate all-decline stress.
    """
    outcome = 60000
    efforts = {'no_purchase':0,'self_service_incumbent':10000,'ordinary_provider':0,
               'self_hosted':4000,'group_webinar':12000,'founder_private':0}
    if world.regime == 'software_convenience':
        efforts['self_service_incumbent'] = 48000
    elif world.regime == 'training':
        efforts['self_service_incumbent'] = 52000
        efforts['self_hosted'] = 45000
        efforts['group_webinar'] = 1000
    # A useful free core has the same ordinary capability and setup burden as
    # the competent free incumbent. Rights are hypothetical in this simulation.
    efforts['open_core'] = efforts['self_service_incumbent']
    budget = 50000
    premium = 0
    if world.regime == 'rare_founder_access' and prospect == 0:
        budget = 2500000
        premium = game.founder_value_cents-outcome
    prices = {'no_purchase':0,'self_service_incumbent':0,'open_core':0,'ordinary_provider':50000,**PRICES}
    values = {p:(0 if p == 'no_purchase' else outcome) for p in prices}
    values['founder_private'] += premium
    if world.regime == 'commodity' and world.adverse:
        values = {p:0 for p in prices}  # Explicit zero-demand stress, including free alternatives.
    utilities = {p:values[p]-prices[p]-efforts[p] for p in (*OUTSIDE,*offers) if prices[p] <= budget}
    choice = max(utilities, key=utilities.get)  # no_purchase wins zero ties.
    return {'choice':choice, 'budget_cents':budget, 'utilities_cents':utilities,
            'ordinary_outcome_value_cents':outcome, 'founder_access_premium_cents':premium,
            'same_ordinary_outcome_available_from_outside_options':True}

@dataclass(frozen=True)
class Action:
    kind: str
    build: tuple[str,...] = ()
    offers: tuple[str,...] = ()
    def as_dict(self): return {'kind':self.kind,'build':list(self.build),'offers':list(self.offers)}

@dataclass
class Node:
    action: Action
    children: dict = field(default_factory=dict)
    value: Fraction = Fraction(0)
    # Belief support is used only by solver/audit, never to choose an execution action.
    support: tuple[str,...] = ()

@dataclass
class Policy:
    mode: str
    root: Node
    expected_profit_cents: Fraction
    worst_profit_cents: int
    finite_model_optimality_gap_cents: Fraction | None
    states_evaluated: int
    scope: str = 'Exhaustive optimum only in the declared finite authored decision model'


def operating_step(game, world, quarter, built, cash, action):
    """Observation comes AFTER chosen action/costs. No hidden-world input to policy.

    Public cash is mature working cash: revenues less all paid costs less 1%
    residual reserve. Sequential order preflight holds FULL price plus costs;
    within-quarter proceeds are not available to fund subsequent orders.
    """
    if action.kind != 'operate' or len(set(action.build)) != len(action.build) or any(p not in PRODUCTS or p in built for p in action.build):
        raise ValueError('Invalid capability build')
    if not action.offers or len(set(action.offers)) != len(action.offers) or any(p not in (*built,*action.build) for p in action.offers):
        raise ValueError('Only available, uniquely listed products may be offered')
    costs = game.costs
    build_cost = sum(costs.build(p) for p in action.build)
    session = costs.webinar_platform_cents+costs.webinar_unknown_base_cents+costs.webinar_facilitation_cents if 'group_webinar' in action.offers else 0
    fixed = build_cost+costs.outreach_cents+session
    if cash < fixed:
        raise ValueError('UNFUNDED_FIXED_COST_ACTION')
    available = cash-fixed
    total_cost, accepted, reserved = fixed, 0, 0
    opportunity_cost = 0
    capacity = {'founder_private':costs.founder_slots_per_quarter, 'group_webinar':costs.webinar_seats_per_session, 'self_hosted':game.prospects_per_quarter}
    orders, choices, outcomes, buyer_decisions = [], [], [], []
    for prospect in range(game.prospects_per_quarter):
        decision = buyer_choice(game,world,prospect,action.offers)
        p = decision['choice']; choices.append(p)
        buyer_decisions.append({'prospect':prospect,**decision})
        if p not in PRODUCTS:
            outcomes.append('outside'); continue
        price, expense = PRICES[p], costs.order(p)
        if capacity[p] <= 0:
            outcomes.append('capacity_hold')
            orders.append({'prospect':prospect,'product':p,'status':'capacity_hold','price_cents':price,'cost_cents':0,'buyer':decision})
            continue
        if available < price+expense+costs.native_funding_collateral_cents:
            outcomes.append('liquidity_hold')
            orders.append({'prospect':prospect,'product':p,'status':'liquidity_hold','price_cents':price,'cost_cents':0,'buyer':decision})
            continue
        # Accepted cash inflow is matched by full-price reserve, so only expense
        # and fee collateral reduce availability until maturity. Refunds cancel
        # principal exposure immediately; processing expense remains paid.
        available -= expense + (0 if world.adverse else costs.native_funding_collateral_cents)
        capacity[p] -= 1
        total_cost += expense
        opportunity_cost += costs.opportunity(p,world.adverse)
        ok = not world.adverse
        if ok: accepted += price; reserved += price//100
        outcomes.append('accepted' if ok else 'rejected_refunded')
        orders.append({'prospect':prospect,'product':p,'status':outcomes[-1],
                       'price_cents':price,'cost_cents':expense,'cash_cost_cents':expense,'buyer':decision,
                       'processing_fee_cents':costs.processing_cents[PRODUCTS.index(p)],
                       'native_cost_cents':costs.native_order_cents[PRODUCTS.index(p)],
                       'founder_opportunity_cost_cents':costs.opportunity(p,world.adverse),
                       'noncash_founder_opportunity_cents':costs.opportunity(p,world.adverse),
                       'residual_reserve_cents':price//100 if ok else 0})
    cash_profit = accepted-total_cost
    profit = cash_profit-opportunity_cost
    new_cash = cash+cash_profit-reserved
    observation = (tuple(p if p in PRODUCTS else 'declined' for p in choices),tuple(outcomes))
    trace = {'quarter':quarter,'hour':quarter*90*24,'action':action.as_dict(),
             'opening_available_cents':cash,'build_cost_cents':build_cost,
             'outreach_cost_cents':costs.outreach_cents,'session_cost_cents':session,
             'cost_cents':total_cost,'cash_cost_cents':total_cost,
             'noncash_founder_opportunity_cents':opportunity_cost,
             'cash_profit_cents':cash_profit,'accepted_revenue_cents':accepted,
             'profit_cents':profit,'new_residual_reserve_cents':reserved,
             'mature_available_cents':new_cash,'maturity_hour':quarter*90*24+30*24+1,
             'observation':observation,'orders':orders,'buyer_decisions':buyer_decisions}
    return tuple(p for p in PRODUCTS if p in built or p in action.build),new_cash,profit,observation,trace


def solve(game, mode='expected'):
    if mode not in ('expected','robust','no_research','static_all','nonentry'):
        raise ValueError('Unknown policy mode')
    worlds = {w.id:w for w in game.worlds}
    calls = 0
    def aggregate(values, ids):
        if mode == 'robust': return min(values.values())
        weight = sum(worlds[i].prior for i in ids)
        return sum(worlds[i].prior*values[i] for i in ids)/weight
    @lru_cache(None)
    def dp(t, built, cash, researched, ids):
        nonlocal calls
        calls += 1
        best = Node(Action('stop'),value=Fraction(0),support=ids)
        if t == game.quarters or mode == 'nonentry': return best
        # An optional paid signal changes only public belief, not the hidden world.
        if not researched and mode in ('expected','robust') and cash >= game.costs.research_cents:
            groups = {}
            for i in ids: groups.setdefault(worlds[i].signal,[]).append(i)
            children = {s:dp(t,built,cash-game.costs.research_cents,True,tuple(group)) for s,group in groups.items()}
            vals = {i:children[worlds[i].signal].value-game.costs.research_cents for i in ids}
            value = aggregate(vals,ids)
            if value > best.value: best = Node(Action('research'),children,value,ids)
        if mode == 'static_all':
            additions = (tuple(p for p in PRODUCTS if p not in built),)
        else:
            # Capabilities are staged: build at most ONE product each quarter.
            additions = ((),)+tuple((p,) for p in PRODUCTS if p not in built)
        for addition in additions:
            available_products = tuple(p for p in PRODUCTS if p in built or p in addition)
            offers_list = (PRODUCTS,) if mode == 'static_all' else subsets(available_products)
            for offers in offers_list:
                if not offers: continue
                action = Action('operate',addition,offers)
                fixed = sum(game.costs.build(p) for p in addition)+game.costs.outreach_cents
                if 'group_webinar' in offers: fixed += game.costs.webinar_platform_cents+game.costs.webinar_unknown_base_cents+game.costs.webinar_facilitation_cents
                if cash < fixed: continue
                results = {i:operating_step(game,worlds[i],t,built,cash,action) for i in ids}
                groups = {}
                for i,r in results.items(): groups.setdefault(r[3],[]).append(i)
                children = {}
                for obs,group in groups.items():
                    b,c,_,_,_ = results[group[0]]
                    # Identical public observations must imply identical state.
                    assert all(results[i][0:2] == (b,c) for i in group)
                    children[obs] = dp(t+1,b,c,researched,tuple(group))
                vals = {i:results[i][2]+children[results[i][3]].value for i in ids}
                value = aggregate(vals,ids)
                if value > best.value: best = Node(action,children,value,ids)
        return best
    root = dp(0,(),game.capital_cents,False,tuple(worlds))
    policy = Policy(mode,root,Fraction(0),0,None,calls)
    results = {i:execute(game,policy,i)['realized_profit_cents'] for i in worlds}
    policy.expected_profit_cents = sum(worlds[i].prior*results[i] for i in worlds)
    policy.worst_profit_cents = min(results.values())
    # Controls are solved within their own explicitly restricted action classes.
    policy.finite_model_optimality_gap_cents = Fraction(0)
    return policy


def execute(game, policy, world_id):
    """Execute ONE public-history policy in a world; never inspect world to branch.

    The environment produces signals/outcomes. Policy branch selection uses only
    their returned public observations; compatible worlds share one continuation.
    """
    world = next(w for w in game.worlds if w.id == world_id)
    node, t, built, cash = policy.root,0,(),game.capital_cents
    profit, trace = 0,[]
    while node.action.kind != 'stop':
        if node.action.kind == 'research':
            expense = game.costs.research_cents
            if cash < expense: raise ValueError('UNFUNDED_RESEARCH')
            cash -= expense; profit -= expense
            trace.append({'quarter':t,'hour':t*90*24,'action':node.action.as_dict(),
                          'cost_cents':expense,'cash_cost_cents':expense,'cash_profit_cents':-expense,
                          'noncash_founder_opportunity_cents':0,'profit_cents':-expense,
                          'observation':world.signal,'mature_available_cents':cash,'orders':[]})
            node = node.children[world.signal]
        else:
            built,cash,p,obs,row = operating_step(game,world,t,built,cash,node.action)
            trace.append(row); profit += p; t += 1
            node = node.children[obs]
    trace.append({'quarter':t,'hour':min(t*90*24,365*24),'action':{'kind':'stop','build':[],'offers':[]},
                  'cost_cents':0,'cash_cost_cents':0,'cash_profit_cents':0,
                  'noncash_founder_opportunity_cents':0,'profit_cents':0,'orders':[],'mature_available_cents':cash})
    return {'world_id':world_id,'policy_mode':policy.mode,'realized_profit_cents':profit,
            'realized_cash_profit_cents':sum(r['cash_profit_cents'] for r in trace),
            'noncash_founder_opportunity_cents':sum(r['noncash_founder_opportunity_cents'] for r in trace),
            'working_available_cents':cash,'trace':trace,'endpoint_hour':365*24,
            'native_replay_required':True}


def summary(game, policy):
    return {'mode':policy.mode,'expected_profit_cents':str(policy.expected_profit_cents),
            'worst_profit_cents':policy.worst_profit_cents,
            'finite_model_optimality_gap_cents':str(policy.finite_model_optimality_gap_cents),
            'states_evaluated':policy.states_evaluated,'root_action':policy.root.action.as_dict(),
            'scope':policy.scope,'capital_cents':game.capital_cents,'world_count':len(game.worlds),
            'priors_are_authored_not_empirical':True}


def model_disclosure(game):
    """Machine-readable limitations/assumptions to accompany numerical results."""
    return {
        'money_unit':'integer USD cents',
        'profit_objective':'accepted revenue minus cash costs minus noncash founder opportunity cost',
        'horizon_quarters':game.quarters,
        'new_prospects_each_quarter':3,
        'actions':'stop; optional paid research at most once; build at most one capability per quarter; offer any nonempty subset of available products',
        'static_all_control':'build all capabilities initially and offer all, with optional nonentry or later stop',
        'information':'research yields only noisy binary signal; paid product choices/declines and fulfillment outcomes observed after operating action and costs; the specific outside alternative is never exposed to the policy; no knowledge of hidden world in continuation choice',
        'priors':{w.id:str(w.prior) for w in game.worlds},
        'open_core':'Explicit zero-price outside option with the same complete ordinary outcome and setup effort as the competent free incumbent. Paid products do not uniquely unlock the ordinary outcome. Free redistribution rights are hypothetical for simulation; actual repository licensing remains unresolved, and no real open-source license is asserted or granted.',
        'cost_parameter_values':{k:getattr(game.costs,k) for k in game.costs.__dataclass_fields__},
        'cost_assumptions':{
            'loaded_labor':'$93.40/hour BLS loaded developer proxy supplied for this experiment, not actual construction cost or supplier quote',
            'construction':'20/80/160 total packaging hours low/central/high; authored quantities, allocated 40% software/25% webinar/35% founder capability',
            'ai_bill':'Unknown; zero default is an optimistic boundary, not evidence of no bill. Required sensitivity: additional $100/$1,000 allocated build AI bill',
            'research':'Authored 1.5 labor-proxy hours',
            'outreach':'Authored 0.25 labor-proxy hours per operating quarter',
            'processing':'US Stripe anchor 2.9% plus $0.30 per order, rounded nearest cent; retained after refund',
            'webinar':'Three months at $79/month starting platform anchor per operating quarter plus unknown-base parameter and authored 330-minute preparation/presentation/admin workload at labor proxy; not a complete vendor quote. Unknown-base zero is optimistic boundary; sensitivity adds $30/$90 per quarter',
            'founder':'Opportunity rate independently parameterized, default authored $200/hour for 105 total minutes around a 30-minute conversation (15 review,45 preparation,30 conversation,15 administration); noncash economic cost, not a phantom payment',
            'workload_source':'PR193 authored envelope, not measured workload or vendor quote: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/973036c2f2059b3c82a54970dce02746f44098a0/omega/commerce.py . Low-workload sensitivity: founder30min/webinar60min. Stress:12exception minutes perorder and20dispute minutes perrefund, valued at independent founder opportunity rate; not claimed incidence rates',
            'taxes':'Applicable taxes and complete actual obligations unknown; modeled results only, not fully loaded real-world profit',
            'native_order':'Default authored sensitivity $1/$0.25/$1 for software/group/founder marginal fulfillment; actual AI/infrastructure bills unknown',
        },
        'liquidity':'All fixed cash costs preflighted; each sequential order requires price plus full order cash expense plus $0.20 native collateral; no within-quarter forecast sales spent; accepted price less 1% residual available after 30-day maturity',
        'limitations':['Authored priors and utility/budget personas, not empirical demand or buyer consent',
                       'Founder premium is independent willingness-to-pay sensitivity, not validated demand',
                       'Finite known scenarios omit acquisition uncertainty, market competition dynamics and unknown unknowns',
                       'Expected policy may lose money in realized worlds; robust policy may select nonentry',
                       'Gap zero is exact only for this finite action/scenario model, not real-world or game-theoretic global optimality'],
    }
