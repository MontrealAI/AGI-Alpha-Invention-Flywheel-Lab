"""V4 single-checkout carts: bounded data programs, set-union production.

The runtime uses dynamic programming. The independent checker enumerates every
subset of the normalized public menu. Repeated identical purchases cannot add
services and have nonnegative prices, so never improve utility. No shell/network.
"""
from __future__ import annotations
from fractions import Fraction
from itertools import combinations
from commercial.ledger import digest
from . import market_program as old

PROGRAM='omega/cart-allocation-payment/v4'
SCHEMA=old.SCHEMA
fee=old.fee
integer=old.integer
net_values=old.net_values


def validate(m):
    old.validate(m)
    # Explicit computational bound for this finite checker, not market capacity.
    if len(m['outcomes'])>16:raise ValueError('FINITE_CART_CHECKER_OUTCOME_BOUND')
    sets=[frozenset(o['services']) for o in m['outcomes']]
    if len(set(sets))!=len(sets):raise ValueError('UNIQUE_SERVICE_SET_OUTCOMES_REQUIRED')
    available=set(sets)
    for a in sets:
        for b in sets:
            if a|b not in available:raise ValueError('MISSING_PRODUCTIVE_UNION')
    return m


def union_table(m):
    validate(m)
    sets=[frozenset(o['services']) for o in m['outcomes']]
    return [[sets.index(a|b) for b in sets] for a in sets]


def parse_program(m,p):
    validate(m)
    if p.get('schema')==old.PROGRAM:return old.parse_program(m,p)
    old.exact(p,{'schema','market_sha256','rules','menu'},'CART_PROGRAM')
    if p['schema']!=PROGRAM or p['market_sha256']!=digest(m):
        raise ValueError('SOURCE_BOUND_MARKET_PROGRAM_REQUIRED')
    legacy={'schema':old.PROGRAM,'market_sha256':p['market_sha256'],'rules':p['rules']}
    rules=old.parse_program(m,legacy)
    _entries(m,p)
    return rules


def _entries(m,p):
    ids={o['id']:i for i,o in enumerate(m['outcomes'])}
    entries=p.get('menu',p['rules'])
    if type(entries) is not list:raise ValueError('PUBLIC_MENU_REQUIRED')
    # Only minimum price per outcome matters for nonnegative-price set union.
    best={}
    for e in entries:
        fields={'outcome_id','price_cents'} if 'menu' in p else {'type_id','outcome_id','price_cents'}
        old.exact(e,fields,'MENU_ENTRY');integer(e['price_cents'])
        if e['outcome_id'] not in ids:raise ValueError('UNKNOWN_PRODUCTIVE_OUTCOME')
        j=ids[e['outcome_id']];price=e['price_cents']
        if j==0:
            if price:raise ValueError('COSTLESS_NONENTRY_REQUIRED')
            continue
        best[j]=min(best.get(j,price),price)
    return sorted(best.items())


def _private(m,t):
    old.exact(t,{'values','budget_cents','outside_utility'},'PRIVATE_TYPE')
    if type(t['values']) is not list or len(t['values'])!=len(m['outcomes']) or t['values'][0]!=0:
        raise ValueError('BUYER_OUTCOME_VALUES_REQUIRED')
    for x in t['values']:integer(x)
    integer(t['budget_cents']);integer(t['outside_utility'])


def cheapest_carts(m,p):
    """Runtime DP: each public offer used at most once; union delivered once."""
    parse_program(m,p);table=union_table(m);states={0:(0,())}
    for j,price in _entries(m,p):
        for out,(cost,basket) in list(states.items()):
            target=table[out][j];candidate=(cost+price,basket+(m['outcomes'][j]['id'],))
            if target not in states or (candidate[0],len(candidate[1]),candidate[1]) < (states[target][0],len(states[target][1]),states[target][1]):
                states[target]=candidate
    return states


def exhaustive_carts(m,p):
    """Independent oracle: enumerate subsets and rebuild unions from strings."""
    parse_program(m,p);entries=_entries(m,p);outcomes=m['outcomes']
    lookup={tuple(o['services']):i for i,o in enumerate(outcomes)};rows=[]
    for size in range(len(entries)+1):
        for chosen in combinations(entries,size):
            services=tuple(sorted({s for j,_ in chosen for s in outcomes[j]['services']}))
            rows.append((lookup[services],sum(price for _,price in chosen),
                         tuple(outcomes[j]['id'] for j,_ in chosen)))
    return rows


def _select(m,t,rows):
    _private(m,t);options=[]
    for out,price,basket in rows:
        if price>t['budget_cents']:continue
        utility=0 if out==0 else t['values'][out]-t['outside_utility']-price
        contribution=price-fee(price,m['payment_bps'])-m['outcomes'][out]['cost_cents']
        options.append((utility,contribution,out,price,basket))
    maximum=max(x[0] for x in options)
    selected=min((x for x in options if x[0]==maximum),key=lambda x:(x[2]!=0,x[1],x[3],m['outcomes'][x[2]]['id'],len(x[4]),x[4]))
    u,c,o,p,b=selected
    return {'outcome_id':m['outcomes'][o]['id'],'price_cents':p,'utility_cents':u,
            'seller_contribution_cents':c,'declined':o==0,'basket':list(b),
            'services':list(m['outcomes'][o]['services'])}


def buyer_choose(m,p,private_type):
    states=cheapest_carts(m,p)
    return _select(m,private_type,[(j,c,b) for j,(c,b) in states.items()])


def verify(m,p,*,require_all=True):
    """Check actual feasible carts, not hypothetical truthful reporting."""
    rules=parse_program(m,p);carts=exhaustive_carts(m,p);errors=[];violations=[];checks=0;profit=0;surpluses=[]
    for i,(t,(own,price)) in enumerate(zip(m['types'],rules)):
        private={k:t[k] for k in ('values','budget_cents','outside_utility')}
        choice=_select(m,private,carts)
        actual=(choice['outcome_id'],choice['price_cents'])
        expected=(m['outcomes'][own]['id'],price)
        if expected!=actual:
            violations.append({'true_type':t['id'],'report_type':'cart','basket':choice['basket'],
                               'assigned_outcome':expected[0],'assigned_price_cents':price,
                               'chosen_outcome':actual[0],'chosen_price_cents':actual[1],
                               'gain_cents':choice['utility_cents']-(net_values(m,t)[own]-price)})
        if price>t['budget_cents']:errors.append(('budget',i))
        if own==0 and price:errors.append(('unserved_payment',i))
        if net_values(m,t)[own]-price<(m['participation_margin'] if own else 0):errors.append(('participation',i))
        if choice['seller_contribution_cents']<0:errors.append(('negative_order_contribution',i))
        # All affordable subsets are visited independently of the DP runtime.
        checks+=sum(price<=t['budget_cents'] for _,price,_ in carts)
        profit+=t['weight']*choice['seller_contribution_cents'];surpluses.append(choice['utility_cents'])
    return {'accepted':not errors and (not violations or not require_all),'errors':errors,'violations':violations,
            'deviation_checks':checks,'minimum_buyer_surplus':min(surpluses),
            'expected_contribution_cents':str(Fraction(profit,sum(t['weight'] for t in m['types']))),
            'program_sha256':digest(p),'market_sha256':digest(m),
            'scope':'Finite nonnegative-price single-checkout set-union carts, budgets, outside options; no cross-buyer coalition or empirical-demand claim.'}


def null_program(m):
    p=old.null_program(validate(m));p['schema']=PROGRAM;p['menu']=[];return p


def menu_economics(m,entries):
    p=null_program(m);p['menu']=entries;rows=[];total=0
    for t in m['types']:
        x=buyer_choose(m,p,{k:t[k] for k in ('values','budget_cents','outside_utility')})
        rows.append({'type_id':t['id'],**x,'contribution_cents':x['seller_contribution_cents']})
        total+=t['weight']*x['seller_contribution_cents']
    return {'expected_contribution_cents':str(Fraction(total,sum(t['weight'] for t in m['types']))),'choices':rows}


def oracle_choose(m,p,private_type):
    """Independent exhaustive choice used by settlement replay and audits."""
    return _select(m,private_type,exhaustive_carts(m,p))
