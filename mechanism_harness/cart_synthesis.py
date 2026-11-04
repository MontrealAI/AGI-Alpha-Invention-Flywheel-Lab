"""Finite V4 menu construction with checker-derived compositional constraints.

Closure is economically lossless in the declared single-checkout semantics:
adding a union offer at the cheapest feasible cart price delivers the same union
once with the same fee. This claim does not apply to per-component checkout fees,
separate counterparties, quantity consumption, or cross-buyer coalitions.
"""
from __future__ import annotations
import math
import time
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix
from commercial.ledger import digest
from . import cart_program as v

MEMORY='omega/cart-constraint-memory/v4'


def all_pairs(m):
    table=v.union_table(m)
    return [(m['outcomes'][a]['id'],m['outcomes'][b]['id'])
            for a in range(1,len(table)) for b in range(a+1,len(table))
            if table[a][b] not in (a,b)]


def inherited_pairs(m,memory):
    if memory is None:return set()
    v.old.exact(memory,{'schema','outcome_ids','service_sets','pairs','parents'},'MEMORY')
    if memory['schema']!=MEMORY:raise ValueError('VALIDATED_CONSTRAINT_MEMORY_REQUIRED')
    if memory['outcome_ids']!=[o['id'] for o in m['outcomes']] or memory['service_sets']!=[o['services'] for o in m['outcomes']]:return set()
    if type(memory['pairs']) is not list or type(memory['parents']) is not list:raise ValueError('VALIDATED_CONSTRAINT_MEMORY_REQUIRED')
    valid=set(all_pairs(m));pairs=set()
    for pair in memory['pairs']:
        if type(pair) is not list or len(pair)!=2 or tuple(pair) not in valid:raise ValueError('INVALID_INHERITED_DEVIATION')
        pairs.add(tuple(pair))
    if len(pairs)!=len(memory['pairs']):raise ValueError('DUPLICATE_INHERITED_CONSTRAINT')
    if any(type(x) is not str or len(x)!=64 for x in memory['parents']):raise ValueError('SOURCE_IDENTIFIED_MEMORY_REQUIRED')
    return pairs


def solve_relaxation(m,pairs,restriction=None):
    n=len(m['types']);k=len(m['outcomes']);goods=sorted({s for o in m['outcomes'] for s in o['services']})
    # x: allocation, p: actual payment, f: fee, q: public prices, y: affordable.
    pi=lambda t:n*k+t
    fi=lambda t:n*(k+1)+t
    qi=lambda j:n*(k+2)+j
    yi=lambda t,j:n*(k+2)+k+t*k+j
    base=n*(2*k+2)+k; width=base+(len(goods) if restriction=='separate' else 0)
    if width>m['limits']['max_variables']:raise ValueError('REGISTERED_VARIABLE_BOUND_EXCEEDED')
    cap=max(t['budget_cents'] for t in m['types'])+1
    pricecap=cap*max(1,len(goods))
    if pricecap>10**9:raise ValueError('FINITE_CART_PRICE_REPRESENTATION_BOUND')
    largest=max(max(t['values'])+t['outside_utility'] for t in m['types'])
    big=2*largest+3*pricecap+2*m['participation_margin']
    rows=[];cols=[];data=[];lo=[];hi=[]
    def constraint(coeff,lower=-np.inf,upper=np.inf):
        row=len(lo)
        for col,val in coeff.items():
            if val:rows.append(row);cols.append(col);data.append(float(val))
        lo.append(lower);hi.append(upper)
    for t,typ in enumerate(m['types']):
        vals=v.net_values(m,typ);margin=m['participation_margin']
        constraint({t*k+j:1 for j in range(k)},1,1)
        constraint({pi(t):1,t*k:typ['budget_cents']},upper=typ['budget_cents'])
        constraint({**{t*k+j:vals[j]-margin for j in range(1,k)},pi(t):-1},0)
        constraint({fi(t):10000,pi(t):-m['payment_bps']},0,9999)
        constraint({**{t*k+j:-o['cost_cents'] for j,o in enumerate(m['outcomes'])},pi(t):1,fi(t):-1},0)
        for j in range(1,k):
            # Allocation pays exactly the public price of the assigned outcome.
            constraint({pi(t):1,qi(j):-1,t*k+j:pricecap},upper=pricecap)
            constraint({pi(t):1,qi(j):-1,t*k+j:-pricecap},lower=-pricecap)
            constraint({qi(j):1,yi(t,j):pricecap},upper=typ['budget_cents']+pricecap)
            constraint({qi(j):1,yi(t,j):pricecap},lower=typ['budget_cents']+1)
            # Demand a strict surplus gap only against affordable alternatives.
            coeff={t*k+i:vals[i] for i in range(k)}
            coeff[t*k+j]+=margin
            coeff.update({pi(t):-1,qi(j):1,yi(t,j):-big})
            constraint(coeff,lower=vals[j]+margin-big)
    ids={o['id']:j for j,o in enumerate(m['outcomes'])};table=v.union_table(m)
    for a,b in sorted(pairs):
        i,j=ids[a],ids[b];u=table[i][j]
        constraint({qi(u):1,qi(i):-1,qi(j):-1},upper=0)
    if restriction=='separate':
        for j,o in enumerate(m['outcomes'][1:],1):
            constraint({qi(j):1,**{base+goods.index(s):-1 for s in o['services']}},0,0)
    if len(lo)>m['limits']['max_rows']:raise ValueError('REGISTERED_ROW_BOUND_EXCEEDED')
    objective=np.zeros(width);lower=np.zeros(width);upper=np.ones(width)
    for t,typ in enumerate(m['types']):
        for j,o in enumerate(m['outcomes']):objective[t*k+j]=typ['weight']*o['cost_cents']
        objective[pi(t)]=-typ['weight'];objective[fi(t)]=typ['weight']
        upper[pi(t)]=typ['budget_cents'];upper[fi(t)]=v.fee(typ['budget_cents'],m['payment_bps'])
    upper[qi(0)]=0
    for j in range(1,k):upper[qi(j)]=pricecap
    if restriction=='separate':upper[base:]=cap
    if restriction=='bundle':
        for j,o in enumerate(m['outcomes'][1:],1):
            if set(o['services'])!=set(goods):lower[qi(j)]=upper[qi(j)]=pricecap
    matrix=coo_matrix((data,(rows,cols)),shape=(len(lo),width)).tocsc()
    started=time.process_time_ns()
    result=milp(objective,integrality=np.ones(width),bounds=Bounds(lower,upper),
                constraints=LinearConstraint(matrix,np.array(lo),np.array(hi)),
                options={'node_limit':m['limits']['max_nodes'],'mip_rel_gap':0.0})
    log={'solver_status':int(result.status),'solver_message':str(result.message),'rows':len(lo),'variables':width,
         'nonzero_coefficients':len(data),'solver_cpu_ns':time.process_time_ns()-started,
         'node_count':None if getattr(result,'mip_node_count',None) is None else int(result.mip_node_count),
         'reported_relative_gap':None if getattr(result,'mip_gap',None) is None else float(result.mip_gap)}
    if not result.success:return None,log
    if any(not math.isfinite(x) or abs(x-round(x))>1e-5 for x in result.x):
        log['solver_status']='NONINTEGER_SOLUTION';return None,log
    ints=[int(round(x)) for x in result.x];rules=[]
    for t,typ in enumerate(m['types']):
        mask=ints[t*k:t*k+k]
        if sum(mask)!=1 or any(x not in (0,1) for x in mask):return None,log
        j=mask.index(1)
        if ints[fi(t)]!=v.fee(ints[pi(t)],m['payment_bps']):return None,log
        rules.append({'type_id':typ['id'],'outcome_id':m['outcomes'][j]['id'],'price_cents':ints[pi(t)]})
    menu=[{'outcome_id':o['id'],'price_cents':ints[qi(j)]} for j,o in enumerate(m['outcomes']) if j]
    return {'schema':v.PROGRAM,'market_sha256':digest(m),'rules':rules,'menu':menu},log


def composition_violations(m,p):
    prices={e['outcome_id']:e['price_cents'] for e in p['menu']};ids={o['id']:j for j,o in enumerate(m['outcomes'])};table=v.union_table(m)
    return [(a,b) for a,b in all_pairs(m) if prices[m['outcomes'][table[ids[a]][ids[b]]]['id']]>prices[a]+prices[b]]


def synthesize(m,*,memory=None,mode='counterexample',restriction=None):
    v.validate(m)
    if mode not in ('counterexample','full'):raise ValueError('DECLARED_CONSTRUCTOR_REQUIRED')
    if restriction not in (None,'separate','bundle'):raise ValueError('DECLARED_COMPARATOR_RESTRICTION')
    started=time.process_time_ns();warm=inherited_pairs(m,memory);pairs=set(all_pairs(m)) if mode=='full' else warm
    history=[];checks=0;program=None;certificate=None;status='UNRESOLVED'
    for iteration in range(m['limits']['max_rounds']):
        program,log=solve_relaxation(m,pairs,restriction);log.update(iteration=iteration,active_pairs=len(pairs))
        if program is None:history.append(log);break
        certificate=v.verify(m,program);checks+=certificate['deviation_checks']
        bad=composition_violations(m,program)
        log.update(candidate_sha256=digest(program),verified_incentive_failures=len(certificate['violations']),
                   composition_failures=[list(x) for x in bad],integer_semantic_errors=certificate['errors'],
                   expected_contribution_cents=certificate['expected_contribution_cents'])
        history.append(log)
        if certificate['accepted'] and not bad:status='VERIFIED_FINITE_MECHANISM';break
        if certificate['errors']:break
        if not bad or set(bad)<=pairs:raise ValueError('SOLVER_VIOLATES_ALREADY_ADMITTED_EXACT_CONSTRAINT')
        pairs|=set(bad)
    if status!='VERIFIED_FINITE_MECHANISM':program=None
    return {'schema':'omega/cart-construction/v4','market_sha256':digest(m),'mode':mode,'restriction':restriction,
            'memory_sha256':None if memory is None else digest(memory),'initial_pairs':len(warm),
            'status':status,'program':program,'verification':certificate,'history':history,
            'total_rows_built':sum(x['rows'] for x in history),
            'total_nonzeros_built':sum(x['nonzero_coefficients'] for x in history),
            'deviation_checks':checks,'construction_cpu_ns':time.process_time_ns()-started,
            'active_pairs':list(map(list,sorted(pairs))),
            'optimality_scope':'Numerical finite public-menu MILP with strict affordable-choice gaps and single-checkout union production; exact feasible-cart verification, not global game-theoretic proof.'}


def retain(m,record,previous=None):
    if record['status']!='VERIFIED_FINITE_MECHANISM' or record['market_sha256']!=digest(m):raise ValueError('NO_MEMORY_FROM_UNVERIFIED_CONSTRUCTION')
    actual=v.verify(m,record['program'])
    if not actual['accepted'] or actual!=record['verification'] or composition_violations(m,record['program']):raise ValueError('UNVERIFIED_MEMORY_SOURCE')
    inherited_pairs(m,previous)
    parents=[] if previous is None else list(previous['parents'])
    parents.append(digest({'market':digest(m),'program':record['program'],'active_pairs':record['active_pairs']}))
    return {'schema':MEMORY,'outcome_ids':[o['id'] for o in m['outcomes']],
            'service_sets':[o['services'] for o in m['outcomes']],
            'pairs':record['active_pairs'],'parents':parents}
