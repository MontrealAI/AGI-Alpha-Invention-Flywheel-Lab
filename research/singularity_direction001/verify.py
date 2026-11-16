"""Separate scalar primal/dual proof checker for Reality Probe 001.

Does not call scipy.optimize or trust its solver success flag. It reconstructs
the lossless DC constraints and checks primal feasibility plus a certified
no-switch and every allowed one-opening LP optimum using signed dual multipliers.
Tolerance: 2e-5 MW; this remains DC-only and retrospectively selected.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .source import SOURCE, OUTAGES, STRESS, parse_case

TOL = 2e-5


def require(cond, message):
    if not cond:
        raise ValueError(message)


def near(a,b,eps=TOL):
    return abs(a-b) <= eps


def matrices(case, unavailable):
    n = len(case['loads_mw']); g = len(case['generators']); m = g+2*n
    c = [0.0]*m
    for i in range(n): c[g+i]=1
    aeq = [[0.0]*m for _ in range(n+1)]
    beq = [0.0]*(n+1)
    aeq[0][g+n] = 1
    for i,gen in enumerate(case['generators']):
        aeq[gen['bus']+1][i] += 1
    for i,load in enumerate(case['loads_mw']):
        aeq[i+1][g+i]=1;beq[i+1]=load*STRESS['demand_multiplier']
    aub = [];bub = []
    for i,line in enumerate(case['lines']):
        if i in unavailable:continue
        f=case['base_mva']/(line['reactance']*line['tap'])
        v=[0.0]*m;v[g+n+line['from']]=f;v[g+n+line['to']]=-f
        for j in range(m):
            aeq[line['from']+1][j] -= v[j]
            aeq[line['to']+1][j] += v[j]
        bound=min(line['rating_mw_proxy']*STRESS['thermal_rating_multiplier'],f*math.pi/6)
        aub.extend([v,[-q for q in v]]);bub.extend((bound,bound))
    bounds = [(j['min_mw'],j['max_mw']) for j in case['generators']]
    bounds += [(0, l*STRESS['demand_multiplier']) for l in case['loads_mw']]
    bounds += [(None,None)]*n
    return c,aeq,beq,aub,bub,bounds


def dot(u,v):
    return sum(a*b for a,b in zip(u,v))


def check_primal(case, unavailable, witness):
    c,eq,eb,ub,bb,bounds=matrices(case,unavailable)
    x=witness['primal'];require(len(x)==len(c) and all(type(a) in (float,int) and math.isfinite(a) for a in x),'INVALID_PRIMAL_VECTOR')
    for i,(a,b) in enumerate(bounds):
        if a is not None:require(x[i]>=a-TOL,f'LOWER_VIOLATION_{i}')
        if b is not None:require(x[i]<=b+TOL,f'UPPER_VIOLATION_{i}')
    for i,(row,b) in enumerate(zip(eq,eb)):
        require(near(dot(row,x),b),f'KCL_OR_ANGLE_VIOLATION_{i}')
    for i,(row,b) in enumerate(zip(ub,bb)):
        require(dot(row,x)<=b+TOL,f'FLOW_LIMIT_VIOLATION_{i}')
    value=dot(c,x)
    require(near(value,witness['unserved_mw']),'OBJECTIVE_INCONSISTENT')
    return value


def check_dual(case, unavailable, witness):
    c,eq,eb,ub,bb,bounds=matrices(case,unavailable)
    d=witness['dual'];ye=d['equalities'];yu=d['inequalities'];yl=d['lower'];yup=d['upper']
    require(len(ye)==len(eq) and len(yu)==len(ub) and len(yl)==len(c) and len(yup)==len(c), 'DUAL_SHAPE')
    require(all(type(x) in (float,int) and math.isfinite(x) for x in ye+yu+yl+yup),'NONFINITE_DUAL')
    require(all(x<=TOL for x in yu+yup) and all(x>=-TOL for x in yl), 'DUAL_SIGN')
    for i in range(len(c)):
        if bounds[i][0] is None:require(abs(yl[i])<=TOL,'UNBOUNDED_LOWER_MULTIPLIER')
        if bounds[i][1] is None:require(abs(yup[i])<=TOL,'UNBOUNDED_UPPER_MULTIPLIER')
        stationarity=sum(ye[j]*eq[j][i] for j in range(len(eq)))
        stationarity+=sum(yu[j]*ub[j][i] for j in range(len(ub)))+yl[i]+yup[i]
        require(near(stationarity,c[i]),f'DUAL_STATIONARITY_{i}')
    lower=dot(ye,eb)+dot(yu,bb)
    for i,(a,b) in enumerate(bounds):
        if a is not None:lower+=yl[i]*a
        if b is not None:lower+=yup[i]*b
    require(lower>=-TOL,'INVALID_NEGATIVE_LOWER_BOUND')
    value=check_primal(case,unavailable,witness)
    require(lower<=value+TOL,'WEAK_DUALITY_BROKEN')
    require(near(lower,value),'PRIMAL_DUAL_GAP')
    return lower


def verify(evidence):
    require(evidence['schema']=='montreal-ai/reality-probe-001/v2','SCHEMA')
    require(evidence['stress']==STRESS,'STRESS_CHANGED')
    require(len(evidence['cases'])==len(SOURCE),'CASE_COUNT')
    require(sorted(r['case'] for r in evidence['cases'])==sorted(SOURCE),'CASE_COVERAGE')
    outcomes=[]
    for result in evidence['cases']:
        case=parse_case(result['case'])
        require(result['source']=={'path':case['source'],
            'git_blob_sha1':case['source_git_blob_sha1'],'sha256':case['source_sha256']},'SOURCE_CHANGED')
        require(result['selected_outage']==OUTAGES[result['case']],'OUTAGE_CHANGED')
        outage=result['selected_outage'];sw=result['selected_additional_switch']
        require(0<=sw<len(case['lines']) and sw!=outage,'INVALID_SWITCH')
        require(result['bus_count']==len(case['loads_mw']) and result['line_count']==len(case['lines']),'CASE_SIZE')
        require(near(result['total_stressed_demand_mw'],sum(case['loads_mw'])*STRESS['demand_multiplier']),'DEMAND_CHANGED')
        no=check_primal(case,{outage},result['baseline'])
        no_lower=check_dual(case,{outage},result['baseline'])
        after=check_primal(case,{outage,sw},result['switched'])
        check_dual(case,{outage,sw},result['switched'])
        require(near(result['modeled_gain_mw'],no-after) and no-after>0.01,'NO_PROVED_GAIN')
        rows=result['responses'];ids=[x['switch'] for x in rows]
        require(sorted(ids)==[i for i in range(len(case['lines'])) if i!=outage],
                'INCOMPLETE_SWITCH_SEARCH')
        # Each alternative must have a complete *independently checked* optimum.
        # Scalar-only rankings can be forged while retaining the selected witness.
        max_gap=0.0
        for row in rows:
            idx=row['switch']
            witness=row['witness']
            require(near(row['unserved_mw'],witness['unserved_mw']),
                    'RESPONSE_WITNESS_MISMATCH')
            optimum_lower=check_dual(case,{outage,idx},witness)
            require(near(row['unserved_mw'],optimum_lower),
                    'RESPONSE_DUAL_MISMATCH')
            max_gap=max(max_gap,abs(row['unserved_mw']-optimum_lower))
            require(optimum_lower>=after-TOL,
                    'COMPETING_SWITCH_BEATS_SELECTED')
        selected=next(x for x in rows if x['switch']==sw)
        require(near(selected['unserved_mw'],after) and
                near(selected['witness']['unserved_mw'],after),'RESPONSE_MISMATCH')
        outcomes.append({'case':case['case'],'baseline_primal_mw':round(no,8),
                         'baseline_dual_lower_mw':round(no_lower,8),
                         'new_topology_primal_mw':round(after,8),'gain_mw':round(no-after,8),
                         'certified_alternative_switches':len(rows),
                         'maximum_candidate_objective_dual_gap_mw':round(max_gap,10),
                         'ranking_certificate':'ALL_ONE_EXTRA_SWITCH_LP_OPTIMA_VERIFIED',
                         'status':'PASS_SCOPED_DC_PROOF'})
    return {'status':'PASS_SCOPED_DC_PROOF','results':outcomes,
            'not_established':'Real grid operation; AC feasibility, control authorization, innovation priority, payments, or institution-wide advantage'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args(argv)
    print(json.dumps(verify(json.loads(args.evidence.read_text())),indent=2))


if __name__=='__main__':main()
