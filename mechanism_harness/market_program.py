"""Executable private-information menus and independent integer verification.

No solver, model call, financial authority, or assumed truthful runtime report.
Valuations in the public type distribution are scenarios, not observed demand.
"""
from __future__ import annotations

from fractions import Fraction
from commercial.ledger import canonical, digest, strict_json

SCHEMA = 'omega/private-market/v3'
PROGRAM = 'omega/allocation-payment-program/v3'


def integer(x, low=0, high=10**9):
    if type(x) is not int or not low <= x <= high:
        raise ValueError('EXACT_BOUNDED_INTEGER_REQUIRED')
    return x


def exact(x, fields, name):
    if type(x) is not dict or set(x) != set(fields):
        raise ValueError('EXACT_' + name + '_FIELDS_REQUIRED')


def text(x):
    if type(x) is not str or not 0 < len(x) <= 160 or not x.strip():
        raise ValueError('NONEMPTY_IDENTIFIER_REQUIRED')
    return x


def validate(m):
    exact(m, {'schema', 'id', 'basis', 'outcomes', 'types', 'payment_bps',
              'participation_margin', 'limits', 'cost_basis'}, 'MARKET')
    if m['schema'] != SCHEMA or m['basis'] != 'PUBLIC_SYNTHETIC_TYPE_DISTRIBUTION':
        raise ValueError('EXPLICIT_PUBLIC_SCENARIO_BASIS_REQUIRED')
    text(m['id']); text(m['cost_basis'])
    integer(m['payment_bps'],0,9999); integer(m['participation_margin'],1,1000)
    exact(m['limits'], {'max_variables','max_rows','max_nodes','max_rounds'}, 'LIMITS')
    for v in m['limits'].values():integer(v,1,10**7)
    if type(m['outcomes']) is not list or not m['outcomes']:
        raise ValueError('OUTCOME_SET_REQUIRED')
    if type(m['types']) is not list or not m['types']:
        raise ValueError('PUBLIC_TYPE_SET_REQUIRED')
    outcomes=m['outcomes']; types=m['types'];n=len(types);k=len(outcomes)
    if n*(k+2) > m['limits']['max_variables']:
        raise ValueError('REGISTERED_VARIABLE_BOUND_EXCEEDED')
    for o in outcomes:
        exact(o,{'id','services','cost_cents'},'OUTCOME');text(o['id']);integer(o['cost_cents'])
        if type(o['services']) is not list or o['services']!=sorted(set(o['services'])):
            raise ValueError('SORTED_UNIQUE_SERVICE_IDENTITIES_REQUIRED')
        for s in o['services']:text(s)
    if outcomes[0] != {'id':'outside','services':[],'cost_cents':0}:
        raise ValueError('COSTLESS_NONENTRY_REQUIRED')
    if len({o['id'] for o in outcomes})!=k or any(not o['services'] for o in outcomes[1:]):
        raise ValueError('DISTINCT_PRODUCTIVE_OUTCOMES_REQUIRED')
    type_ids=[]
    for t in types:
        exact(t,{'id','values','budget_cents','outside_utility','weight'},'TYPE')
        text(t['id']);type_ids.append(t['id'])
        if type(t['values']) is not list or len(t['values'])!=k or t['values'][0]!=0:
            raise ValueError('EXACT_OUTCOME_VALUES_REQUIRED')
        for v in t['values']:integer(v)
        integer(t['budget_cents']);integer(t['outside_utility']);integer(t['weight'],1,10**6)
    if len(set(type_ids))!=n:raise ValueError('UNIQUE_TYPE_IDENTITIES_REQUIRED')
    return m


def fee(price, bps):
    return (price*bps+9999)//10000


def net_values(m, t):
    return [0]+[v-t['outside_utility'] for v in t['values'][1:]]


def null_program(m):
    validate(m)
    return {'schema':PROGRAM,'market_sha256':digest(m),
            'rules':[{'type_id':t['id'],'outcome_id':'outside','price_cents':0} for t in m['types']]}


def parse_program(m,p):
    validate(m);exact(p,{'schema','market_sha256','rules'},'PROGRAM')
    if p['schema']!=PROGRAM or p['market_sha256']!=digest(m):
        raise ValueError('SOURCE_BOUND_MARKET_PROGRAM_REQUIRED')
    if type(p['rules']) is not list or len(p['rules'])!=len(m['types']):
        raise ValueError('EXACT_RULE_DENOMINATOR_REQUIRED')
    out={o['id']:j for j,o in enumerate(m['outcomes'])};rules=[]
    for t,r in zip(m['types'],p['rules']):
        exact(r,{'type_id','outcome_id','price_cents'},'RULE')
        if r['type_id']!=t['id'] or r['outcome_id'] not in out:
            raise ValueError('RULE_IDENTITY_CHANGED')
        integer(r['price_cents']);rules.append((out[r['outcome_id']],r['price_cents']))
    return rules


def verify(m,p,*,require_all=True):
    """Check every type/report using exact integers, independently of synthesis.

    Different assigned outcomes require the configured strictly positive gap;
    identical outcomes may tie only at identical prices. This is deliberately
    stronger than ordinary weak IC and may forgo boundary revenue.
    """
    rules=parse_program(m,p);errors=[];violations=[];surpluses=[];profit=0;checks=0
    margin=m['participation_margin'];outcomes=m['outcomes']
    for t,(own,price) in enumerate(rules):
        typ=m['types'][t];values=net_values(m,typ);utility=values[own]-price
        if price>typ['budget_cents']:errors.append(('budget',t))
        if own==0 and price!=0:errors.append(('unserved_payment',t))
        if utility < (margin if own else 0):errors.append(('participation',t))
        contribution=price-fee(price,m['payment_bps'])-outcomes[own]['cost_cents']
        if contribution<0:errors.append(('negative_order_contribution',t))
        profit+=typ['weight']*contribution
        surpluses.append(utility)
        for r,(other,q) in enumerate(rules):
            if r==t:continue
            checks+=1
            required=margin if own!=other else 0
            gap=utility-(values[other]-q)
            if gap<required:
                violations.append({'true_type':typ['id'],'report_type':m['types'][r]['id'],
                                   'gain_cents':-gap,'required_gap':required,'actual_gap':gap})
    accepted=not errors and (not violations or not require_all)
    denom=sum(t['weight'] for t in m['types'])
    return {'accepted':accepted,'errors':errors,'violations':violations,
            'deviation_checks':checks,'minimum_buyer_surplus':min(surpluses),
            'expected_contribution_cents':str(Fraction(profit,denom)),
            'program_sha256':digest(p),'market_sha256':digest(m),
            'scope':'Exact finite-type deterministic unilateral-incentive/participation check; not empirical demand, collusion resistance, or universal truthfulness.'}


def buyer_choose(m,p,private_type):
    """Voluntary runtime choice. This function is separate from the constructor.

    Unknown valuations are permitted. No hidden value is passed back to pricing.
    A buyer indifferent to nonentry declines; other ties harm seller revenue.
    """
    rules=parse_program(m,p)
    exact(private_type,{'values','budget_cents','outside_utility'},'PRIVATE_TYPE')
    v=private_type['values']
    if type(v) is not list or len(v)!=len(m['outcomes']) or v[0]!=0:
        raise ValueError('BUYER_OUTCOME_VALUES_REQUIRED')
    for x in v:integer(x)
    integer(private_type['budget_cents']);integer(private_type['outside_utility'])
    candidates=[(0,0,0,0,'outside')]
    seen=set()
    for outcome,price in rules:
        if (outcome,price) in seen or price>private_type['budget_cents']:continue
        seen.add((outcome,price))
        utility=0 if outcome==0 else v[outcome]-private_type['outside_utility']-price
        profit=price-fee(price,m['payment_bps'])-m['outcomes'][outcome]['cost_cents']
        candidates.append((utility,profit,outcome,price,m['outcomes'][outcome]['id']))
    best=max(x[0] for x in candidates)
    selected=min((x for x in candidates if x[0]==best),key=lambda x:(x[2]!=0,x[1],x[3],x[4]))
    return {'outcome_id':selected[4],'price_cents':selected[3],'utility_cents':selected[0],
            'seller_contribution_cents':selected[1],'declined':selected[2]==0}


def menu_economics(m,entries):
    """Evaluate ordinary public menus under the SAME pessimistic buyer choice."""
    validate(m)
    for e in entries:
        exact(e,{'outcome_id','price_cents'},'MENU_ENTRY');integer(e['price_cents'])
        if e['outcome_id'] not in {o['id'] for o in m['outcomes']}:raise ValueError('UNKNOWN_OUTCOME')
    # A menu need not be direct revelation or incentivize a type label.
    rows=[];total=0;weight=sum(t['weight'] for t in m['types'])
    for t in m['types']:
        candidates=[(0,0,'outside',0)]
        for entry in entries:
            o=next(x for x in m['outcomes'] if x['id']==entry['outcome_id']);j=m['outcomes'].index(o);p=entry['price_cents']
            if p>t['budget_cents']:continue
            u=(t['values'][j]-t['outside_utility'] if j else 0)-p
            net=p-fee(p,m['payment_bps'])-o['cost_cents']
            candidates.append((u,net,o['id'],p))
        maximum=max(x[0] for x in candidates)
        u,net,out,p=min((x for x in candidates if x[0]==maximum),key=lambda x:(x[2]!='outside',x[1],x[3],x[2]))
        total+=t['weight']*net
        rows.append({'type_id':t['id'],'outcome_id':out,'price_cents':p,'utility_cents':u,'contribution_cents':net})
    return {'expected_contribution_cents':str(Fraction(total,weight)),'choices':rows}
