"""Finite exact material allocation and source-carrying remnant inventory.

Known cutting-stock methods, not autonomous discovery. All current examples and
market assumptions are simulated. A valid digital trace does not prove physical
stock dimensions, provenance, custody, workmanship or real buyer consent.
"""
from functools import lru_cache
from itertools import product
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def patterns(raw, stock, budget=None):
    groups = sorted({(p['grade'], p['length_mm']) for p in raw['pieces']})
    counts = tuple(sum((p['grade'], p['length_mm']) == g for p in raw['pieces']) for g in groups)
    limits = [min(n, stock['length_mm'] // (g[1] + raw['kerf_mm'])) if g[0] == stock['grade'] else 0 for g,n in zip(groups,counts)]
    budget = [1000000] if budget is None else budget
    result=[]
    for t in product(*(range(n+1) for n in limits)):
        budget[0]-=1
        if budget[0]<0:raise RuntimeError('FINITE_SOLVER_STATE_WINDOW_EXHAUSTED: pattern enumeration')
        if any(t) and sum(c*(g[1]+raw['kerf_mm']) for c,g in zip(t,groups))<=stock['length_mm']:
            result.append(t)
    return groups, counts, tuple(result)


def solve(raw, *, max_states=1000000):
    """Exact finite-stock DP, with a per-invocation resource stop, not a market cap."""
    from .material_verify054 import validate_order
    validate_order(raw)
    if type(max_states) is not int or max_states<1:raise ValueError('POSITIVE_EXECUTION_WINDOW_REQUIRED')
    stocks = sorted(raw['stocks'], key=lambda s: s['id'])
    if not raw['pieces']:return assemble(raw,[]), {'states':0,'verdict':'EMPTY_DEMAND'}
    if not stocks:return None, {'states':0,'verdict':'NO_AVAILABLE_STOCK'}
    budget=[max_states]
    rows=[patterns(raw,s,budget) for s in stocks]
    groups,target=rows[0][:2]
    choices=[r[2] for r in rows]
    calls = 0
    @lru_cache(None)
    def visit(i, need):
        nonlocal calls
        calls += 1
        if calls > max_states:
            raise RuntimeError('FINITE_SOLVER_STATE_WINDOW_EXHAUSTED')
        if not any(need):
            return (0,0,())
        if i == len(stocks):
            return None
        # Remaining length lower bound cheaply avoids infeasible suffixes.
        for grade in {g[0] for g in groups}:
            if sum(n*(g[1]+raw['kerf_mm']) for n,g in zip(need,groups) if g[0]==grade) > sum(s['length_mm'] for s in stocks[i:] if s['grade']==grade):
                return None
        best = visit(i+1,need)
        for pat in choices[i]:
            if any(a>b for a,b in zip(pat,need)):
                continue
            tail = visit(i+1,tuple(b-a for a,b in zip(pat,need)))
            if tail is not None:
                val=(stocks[i]['cost_microUSD']+tail[0],1+tail[1],((i,pat),)+tail[2])
                if best is None or val < best:
                    best=val
        return best
    answer=visit(0,target)
    if answer is None:
        return None, {'states':calls,'verdict':'NO_FEASIBLE_FINITE_STOCK_ALLOCATION'}
    pools={g:sorted(p['id'] for p in raw['pieces'] if (p['grade'],p['length_mm'])==g) for g in groups}
    used=[]
    for i,pat in answer[2]:
        ids=[]
        for g,n in zip(groups,pat):
            ids.extend(pools[g][:n]);del pools[g][:n]
        used.append((stocks[i],sorted(ids)))
    return assemble(raw,used), {'states':calls,'verdict':'EXACT_FOR_REGISTERED_FINITE_STOCKS'}


def assemble(raw, used):
    by_piece={p['id']:p for p in raw['pieces']}
    rows=[];remnants=[]
    for stock, ids in used:
        length=sum(by_piece[p]['length_mm']+raw['kerf_mm'] for p in ids)
        leftover=stock['length_mm']-length
        rows.append({'stock_id':stock['id'],'piece_ids':sorted(ids),'used_mm':length,'remnant_mm':leftover})
        if leftover>=raw['min_remnant_mm']:
            remnants.append({'id':raw['order_id']+':'+stock['id']+':remnant','parent_stock_id':stock['id'],
                'length_mm':leftover,'grade':stock['grade'],
                'source_sha256':digest({'input_sha256':digest(raw),'stock_id':stock['id'],'piece_ids':sorted(ids),'remnant_mm':leftover}),
                'cost_microUSD':0})
    # The transfer record retains parent_stock_id; next input strips that metadata.
    return {'schema':'material054/plan/v1','order_id':raw['order_id'],'scope':raw['scope'],'input_sha256':digest(raw),
        'patterns':rows,'unused_stock_ids':sorted({s['id'] for s in raw['stocks']}-{s['id'] for s,_ in used}),
        'remnants':remnants,'material_cost_microUSD':sum(s['cost_microUSD'] for s,_ in used),
        'consumed_mm':sum(r['used_mm'] for r in rows)}


def ordinary_milp(raw):
    """Independent established set-partitioning formulation, same finite inventory.

    SciPy/HiGHS is an optional comparison tool, not a new production dependency.
    Pattern enumeration is shared transparent content, not a claimed advantage.
    """
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import csc_matrix
    stocks=sorted(raw['stocks'],key=lambda s:s['id'])
    if not stocks or not raw['pieces']:raise ValueError('NONEMPTY_COMPARATOR_INSTANCE_REQUIRED')
    budget=[1000000]
    rows=[patterns(raw,s,budget) for s in stocks]
    groups,target=rows[0][:2]
    columns=[(i,t) for i,row in enumerate(rows) for t in row[2]]
    matrix=np.zeros((len(stocks)+len(groups),len(columns)))
    for j,(i,t) in enumerate(columns):
        matrix[i,j]=1;matrix[len(stocks):,j]=t
    costs=np.array([stocks[i]['cost_microUSD'] for i,_ in columns],dtype=float)
    res=milp(costs,integrality=np.ones(len(columns)),bounds=Bounds(0,1),
        constraints=LinearConstraint(csc_matrix(matrix),np.array([0]*len(stocks)+list(target)),np.array([1]*len(stocks)+list(target))),
        options={'time_limit':60,'mip_rel_gap':0})
    if res.status!=0:
        raise RuntimeError('ORDINARY_MILP_NOT_PROVEN_OPTIMAL:'+str(res.message))
    pools={g:sorted(p['id'] for p in raw['pieces'] if (p['grade'],p['length_mm'])==g) for g in groups}
    used=[]
    for v,(i,t) in zip(res.x,columns):
        if v>0.5:
            ids=[]
            for g,n in zip(groups,t):ids.extend(pools[g][:n]);del pools[g][:n]
            used.append((stocks[i],sorted(ids)))
    return assemble(raw,used)


def stock_from_remnant(remnant):
    return {k:v for k,v in remnant.items() if k!='parent_stock_id'}


def textbook_order():
    pieces=[]
    for length,n in [(2,4),(3,2),(4,6),(5,6),(6,2),(7,2),(8,2)]:
        pieces.extend({'id':f'part-{length}-{i}','length_mm':length*1000,'grade':'authored-grade-A'} for i in range(n))
    return {'schema':'material054/order/v1','scope':'SYNTHETIC_PUBLIC_WORKLOAD','order_id':'textbook-first',
        'kerf_mm':0,'min_remnant_mm':500,'pieces':pieces,
        'stocks':[{'id':f'roll-{i:02}','length_mm':9000,'grade':'authored-grade-A','source_sha256':digest({'authored_supplier_lot':i}),'cost_microUSD':90000000} for i in range(16)]}


def successor_order(parent):
    # This demand is observed only after first delivery; first planner never sees it.
    return {'schema':'material054/order/v1','scope':'SYNTHETIC_PUBLIC_WORKLOAD','order_id':'successor-small-parts',
        'kerf_mm':0,'min_remnant_mm':500,
        'pieces':[{'id':f'next-{i}','length_mm':1000,'grade':'authored-grade-A'} for i in range(6)],
        'stocks':[stock_from_remnant(r) for r in parent['remnants']]+[
            {'id':'new-virgin','length_mm':9000,'grade':'authored-grade-A','source_sha256':digest({'authored_supplier_lot':'next'}),'cost_microUSD':90000000}]}
