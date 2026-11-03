"""General finite allocation/payment synthesis with verified constraint learning.

Output is a new executable mechanism table, not a selected fixed-price template.
HiGHS supplies numerical mixed-integer optimization. Exact integer verification
is a separate code path. Solver bounds are never mislabeled formal proofs.
"""
from __future__ import annotations
import copy
from fractions import Fraction
import math
import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix
from commercial.ledger import digest
from . import market_program as v

MEMORY='omega/incentive-counterexamples/v3'


def all_pairs(m):
    return [(a['id'],b['id']) for a in m['types'] for b in m['types'] if a is not b]


def inherited_pairs(m,memory):
    if memory is None:return set()
    if (type(memory) is not dict or set(memory)!={'schema','outcome_ids','type_ids','pairs','parents'}
            or memory['schema']!=MEMORY or type(memory['pairs']) is not list or type(memory['parents']) is not list):
        raise ValueError('VALIDATED_CONSTRAINT_MEMORY_REQUIRED')
    if (memory['outcome_ids']!=[o['id'] for o in m['outcomes']]
            or memory['type_ids']!=[t['id'] for t in m['types']]):
        return set()  # incompatible knowledge is ignored, not silently reinterpreted
    valid=set(all_pairs(m));pairs=set()
    for pair in memory['pairs']:
        if type(pair) is not list or len(pair)!=2 or tuple(pair) not in valid:
            raise ValueError('INVALID_INHERITED_DEVIATION')
        pairs.add(tuple(pair))
    if len(pairs)!=len(memory['pairs']):raise ValueError('DUPLICATE_INHERITED_CONSTRAINT')
    if any(type(x) is not str or len(x)!=64 for x in memory['parents']):
        raise ValueError('SOURCE_IDENTIFIED_MEMORY_REQUIRED')
    return pairs


def solve_relaxation(m,pairs, restriction=None):
    n=len(m['types']);k=len(m['outcomes']);base_width=n*(k+2)
    goods=sorted({s for o in m['outcomes'] for s in o['services']})
    width=base_width+(len(goods) if restriction=='separate' else 0)
    pi=lambda t:n*k+t
    fi=lambda t:n*(k+1)+t
    rows=[];cols=[];data=[];lo=[];hi=[]
    def constraint(coeff, lower=-np.inf, upper=np.inf):
        row=len(lo)
        for column,value in coeff.items():
            if value:rows.append(row);cols.append(column);data.append(float(value))
        lo.append(lower);hi.append(upper)
    for t,typ in enumerate(m['types']):
        constraint({t*k+j:1 for j in range(k)},1,1)
        constraint({pi(t):1,t*k:typ['budget_cents']},upper=typ['budget_cents'])
        vals=v.net_values(m,typ)
        constraint({**{t*k+j:vals[j]-m['participation_margin'] for j in range(1,k)},pi(t):-1},0)
        constraint({fi(t):10000,pi(t):-m['payment_bps']},0,9999)
        constraint({**{t*k+j:-o['cost_cents'] for j,o in enumerate(m['outcomes'])},pi(t):1,fi(t):-1},0)
    ids={t['id']:j for j,t in enumerate(m['types'])}
    for a,b in sorted(pairs):
        t=ids[a];s=ids[b];vals=v.net_values(m,m['types'][t])
        for outcome in range(k):
            coeff={pi(t):-1,pi(s):1}
            for j in range(k):
                adjusted=vals[j]-(m['participation_margin'] if j==outcome else 0)
                coeff[t*k+j]=adjusted;coeff[s*k+j]=-adjusted
            constraint(coeff,0)
    if restriction=='separate':
        cap=max(t['budget_cents'] for t in m['types'])
        big=cap*(len(goods)+1)
        for t in range(n):
            for j,o in enumerate(m['outcomes']):
                coeff={pi(t):1,**{base_width+goods.index(s):-1 for s in o['services']}}
                constraint({**coeff,t*k+j:big},upper=big)
                constraint({**coeff,t*k+j:-big},lower=-big)
    if len(lo)>m['limits']['max_rows']:raise ValueError('REGISTERED_ROW_BOUND_EXCEEDED')
    objective=np.zeros(width);lower=np.zeros(width);upper=np.ones(width)
    for t,typ in enumerate(m['types']):
        weight=typ['weight']
        for j,o in enumerate(m['outcomes']):objective[t*k+j]=weight*o['cost_cents']
        objective[pi(t)]=-weight;objective[fi(t)]=weight
        upper[pi(t)]=typ['budget_cents'];upper[fi(t)]=v.fee(typ['budget_cents'],m['payment_bps'])
    if restriction=='separate':upper[base_width:]=max(t['budget_cents'] for t in m['types'])
    if restriction=='bundle':
        for t in range(n):
            for j,o in enumerate(m['outcomes']):
                if j and set(o['services'])!=set(goods):upper[t*k+j]=0
    matrix=coo_matrix((data,(rows,cols)),shape=(len(lo),width)).tocsc()
    start=time.process_time_ns()
    result=milp(objective,integrality=np.ones(width),bounds=Bounds(lower,upper),
                constraints=LinearConstraint(matrix,np.array(lo),np.array(hi)),
                options={'node_limit':m['limits']['max_nodes'],'mip_rel_gap':0.0})
    elapsed=time.process_time_ns()-start
    log={'solver_status':int(result.status),'solver_message':str(result.message),'rows':len(lo),'variables':width,
         'nonzero_coefficients':len(data),'solver_cpu_ns':elapsed,
         'node_count':None if getattr(result,'mip_node_count',None) is None else int(result.mip_node_count),
         'reported_relative_gap':None if getattr(result,'mip_gap',None) is None else float(result.mip_gap),
         'reported_minimization_bound':None if getattr(result,'mip_dual_bound',None) is None else float(result.mip_dual_bound)}
    if not result.success:return None,log
    if any(not math.isfinite(x) or abs(x-round(x))>1e-5 for x in result.x):
        log['solver_status']='NONINTEGER_SOLUTION';return None,log
    ints=[int(round(x)) for x in result.x];rules=[]
    for t,typ in enumerate(m['types']):
        mask=ints[t*k:t*k+k]
        if sum(mask)!=1 or any(x not in (0,1) for x in mask):return None,log
        outcome=mask.index(1)
        if ints[fi(t)]!=v.fee(ints[pi(t)],m['payment_bps']):return None,log
        rules.append({'type_id':typ['id'],'outcome_id':m['outcomes'][outcome]['id'],'price_cents':ints[pi(t)]})
    return {'schema':v.PROGRAM,'market_sha256':digest(m),'rules':rules},log


def synthesize(m,*,memory=None,mode='counterexample', restriction=None):
    v.validate(m)
    if restriction not in (None,'separate','bundle'):raise ValueError('DECLARED_COMPARATOR_RESTRICTION')
    if mode not in ('counterexample','full'):raise ValueError('DECLARED_CONSTRUCTOR_REQUIRED')
    started=time.process_time_ns();warm=inherited_pairs(m,memory)
    pairs=set(all_pairs(m)) if mode=='full' else warm
    history=[];checks=0;program=None;certificate=None;status='UNRESOLVED'
    for iteration in range(m['limits']['max_rounds']):
        program,log=solve_relaxation(m,pairs,restriction)
        log['iteration']=iteration;log['active_pairs']=len(pairs)
        if program is None:
            history.append(log);break
        certificate=v.verify(m,program)
        checks+=certificate['deviation_checks']
        log['candidate_sha256']=digest(program)
        log['verified_incentive_failures']=len(certificate['violations'])
        log['integer_semantic_errors']=certificate['errors']
        log['expected_contribution_cents']=certificate['expected_contribution_cents']
        history.append(log)
        if certificate['errors']:break
        if certificate['accepted']:
            status='VERIFIED_FINITE_MECHANISM';break
        new={(e['true_type'],e['report_type']) for e in certificate['violations']}
        if new<=pairs:raise ValueError('SOLVER_VIOLATES_ALREADY_ADMITTED_EXACT_CONSTRAINT')
        pairs|=new
    if status!='VERIFIED_FINITE_MECHANISM':program=None
    record={'schema':'omega/mechanism-construction/v3','market_sha256':digest(m),'mode':mode,
            'restriction':restriction,'memory_sha256':None if memory is None else digest(memory),'initial_pairs':len(warm),
            'status':status,'program':program,'verification':certificate,'history':history,
            'total_rows_built':sum(r['rows'] for r in history),'total_nonzeros_built':sum(r['nonzero_coefficients'] for r in history),
            'deviation_checks':checks,'construction_cpu_ns':time.process_time_ns()-started,
            'active_pairs':list(map(list,sorted(pairs))),
            'optimality_scope':'Numerical solver-reported optimum in the declared strict-incentive deterministic integer model; independent exact feasibility, not a formal global optimum proof.'}
    return record


def retain(m,record,previous=None):
    if record['status']!='VERIFIED_FINITE_MECHANISM' or record['market_sha256']!=digest(m):
        raise ValueError('NO_MEMORY_FROM_UNVERIFIED_CONSTRUCTION')
    actual=v.verify(m,record['program'])
    if not actual['accepted'] or actual!=record['verification']:raise ValueError('UNVERIFIED_MEMORY_SOURCE')
    # Compress binding constraints to a reusable graph. This is a search hint,
    # never a proof: every fresh output still faces every possible deviation.
    # Equal-outcome price relations need only a bidirectional spanning chain
    # as a hint; changed outcomes are detected by the independent verifier.
    rules=v.parse_program(m,record['program']);groups={};pairs=set()
    for j,(outcome,price) in enumerate(rules):
        groups.setdefault(outcome,[]).append(m['types'][j]['id'])
    for ids in groups.values():
        for a,b in zip(sorted(ids),sorted(ids)[1:]):pairs|={(a,b),(b,a)}
    for t,(own,p) in enumerate(rules):
        vals=v.net_values(m,m['types'][t]);u=vals[own]-p
        for r,(other,q) in enumerate(rules):
            if own!=other and u-(vals[other]-q)==m['participation_margin']:
                pairs.add((m['types'][t]['id'],m['types'][r]['id']))
    parents=[] if previous is None else list(previous['parents'])
    parents.append(digest({'market':digest(m),'program':record['program'],'active_pairs':record['active_pairs']}))
    return {'schema':MEMORY,'outcome_ids':[o['id'] for o in m['outcomes']],
            'type_ids':[t['id'] for t in m['types']],'pairs':list(map(list,sorted(pairs))),
            'parents':parents}
