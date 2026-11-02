"""Established HiGHS mixed-integer dispatch with participant outside options."""
from __future__ import annotations
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix
from .verify import digest, validate_request


class Infeasible(ValueError):
    pass


def solve(request,mode='pooled'):
    validate_request(request)
    if mode not in {'pooled','conventional','individual'}: raise ValueError('UNKNOWN_CONTROL')
    if mode=='individual':
        options=[]
        for device in request['devices']:
            trial=dict(request,devices=[device])
            try:
                artifact=solve(trial)
                options.append((sum(artifact['payments_microUSD'].values()),artifact,device['id']))
            except Infeasible: pass
        if not options: raise Infeasible('NO_INDIVIDUAL_MEETS_PRECOMMITTED_CONTRACT')
        _,artifact,chosen=min(options,key=lambda row:(row[0],row[2]))
        artifact['input_sha256']=digest(request)
        for device in request['devices']:
            if device['id']!=chosen:
                artifact['dispatch_wh'][device['id']]=list(device['baseline_wh'])
                artifact['payments_microUSD'][device['id']]=0
        return artifact
    devices=request['devices'];n=len(devices);slots=len(request['target_wh']);events=[t for t,v in enumerate(request['target_wh']) if v]
    e=len(events);nx=n*slots;nr=n*e;size=nx+nr+n
    objective=np.zeros(size);upper=np.zeros(size);lower=np.zeros(size)
    row_indices=[];column_indices=[];coefficients=[];lb=[];ub=[]
    def add(values,low,high):
        row=len(lb)
        for index,value in values.items():
            if value:row_indices.append(row);column_indices.append(index);coefficients.append(value)
        lb.append(low);ub.append(high)
    for i,device in enumerate(devices):
        for t in range(slots):upper[i*slots+t]=device['power_wh'][t] if device['available'][t] else 0
        add({i*slots+t:1 for t in range(slots)},device['required_wh'],device['required_wh'])
        yi=nx+nr+i;upper[yi]=1;objective[yi]=request['participant_margin_microUSD']
        for j,t in enumerate(events):
            ri=nx+i*e+j;upper[ri]=device['baseline_wh'][t];objective[ri]=device['disutility_microUSD_per_wh']
            add({i*slots+t:1,ri:1},device['baseline_wh'][t],device['baseline_wh'][t])
            add({ri:1,yi:-device['baseline_wh'][t]},-np.inf,0)
    for j,t in enumerate(events):
        required=(request['target_wh'][t]*1_000_000+999_999-request['derating_ppm'])//(1_000_000-request['derating_ppm'])
        add({nx+i*e+j:1 for i in range(n)},required,np.inf)
    add({i:float(c) for i,c in enumerate(objective) if c},-np.inf,request['buyer_budget_microUSD'])
    result=milp(objective,integrality=np.ones(size),bounds=Bounds(lower,upper),constraints=LinearConstraint(coo_matrix((coefficients,(row_indices,column_indices)),shape=(len(lb),size)).tocsc(),np.array(lb),np.array(ub)),options={'time_limit':10,'mip_rel_gap':0})
    if not result.success:raise Infeasible('PRECOMMITTED_CONTRACT_INFEASIBLE:'+str(result.status))
    values=np.rint(result.x).astype(np.int64)
    dispatch={d['id']:[int(v) for v in values[i*slots:(i+1)*slots]] for i,d in enumerate(devices)}
    payments={}
    reductions=[0]*slots
    for device in devices:
        removed=0
        for t in events:
            reduction=device['baseline_wh'][t]-dispatch[device['id']][t]
            reductions[t]+=reduction;removed+=reduction
        payments[device['id']]=int(removed*device['disutility_microUSD_per_wh']+(request['participant_margin_microUSD'] if removed else 0))
    return {'schema':'flexibility063/dispatch/v1','request_id':request['id'],'input_sha256':digest(request),'dispatch_wh':dispatch,'payments_microUSD':payments,
            'delivered_wh':[r*(1_000_000-request['derating_ppm'])//1_000_000 for r in reductions]}
