"""Independent integer replay of a precommitted synthetic flexibility contract."""
from __future__ import annotations
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def validate_request(request):
    required={'schema','id','scope','slot_minutes','target_wh','derating_ppm','buyer_budget_microUSD','participant_margin_microUSD','devices'}
    if not isinstance(request,dict) or set(request)!=required or request['schema']!='flexibility063/request/v1' or request['scope']!='SYNTHETIC_FLEXIBILITY_PROFILE':
        raise ValueError('EXACT_SYNTHETIC_REQUEST_REQUIRED')
    def integer(value,minimum=0):
        if type(value) is not int or value<minimum: raise ValueError('NONNEGATIVE_INTEGER_REQUIRED')
        if value>2**50: raise ValueError('EXACT_SOLVER_NUMERIC_RANGE_EXCEEDED')
        return value
    if not isinstance(request['id'],str) or not 1<=len(request['id'])<=160: raise ValueError('REQUEST_ID_REQUIRED')
    integer(request['slot_minutes'],1)
    integer(request['derating_ppm'])
    if request['derating_ppm']>=1_000_000: raise ValueError('DERATING_BELOW_ONE_REQUIRED')
    integer(request['buyer_budget_microUSD'])
    integer(request['participant_margin_microUSD'],1)
    targets=request['target_wh']
    if not isinstance(targets,list) or not 1<=len(targets)<=96 or not any(targets): raise ValueError('FINITE_EVENT_TARGET_REQUIRED')
    for value in targets: integer(value)
    devices=request['devices']
    if not isinstance(devices,list) or not 1<=len(devices)<=1000: raise ValueError('FINITE_DEVICE_PROBE_REQUIRED')
    ids=set()
    for device in devices:
        if not isinstance(device,dict) or set(device)!={'id','power_wh','baseline_wh','required_wh','disutility_microUSD_per_wh','available'}: raise ValueError('EXACT_DEVICE_REQUIRED')
        ident=device['id']
        if not isinstance(ident,str) or not 1<=len(ident)<=160 or ident in ids: raise ValueError('UNIQUE_DEVICE_ID_REQUIRED')
        ids.add(ident)
        for key in ('power_wh','baseline_wh','available'):
            if not isinstance(device[key],list) or len(device[key])!=len(targets): raise ValueError('MATCHED_DEVICE_SLOTS_REQUIRED')
        for t,(cap,baseline,available) in enumerate(zip(device['power_wh'],device['baseline_wh'],device['available'])):
            integer(cap);integer(baseline)
            if type(available) is not bool or baseline>cap or baseline and not available: raise ValueError('BASELINE_CAPACITY_REQUIRED')
        integer(device['required_wh'])
        integer(device['disutility_microUSD_per_wh'])
        if sum(device['baseline_wh'])!=device['required_wh']: raise ValueError('BASELINE_ENERGY_REQUIRED')
    if sum(sum(d['baseline_wh']) for d in devices)>2**50 or sum(sum(d['baseline_wh'][t]*d['disutility_microUSD_per_wh'] for t,v in enumerate(targets) if v)+request['participant_margin_microUSD'] for d in devices)>2**50:
        raise ValueError('EXACT_SOLVER_AGGREGATE_RANGE_EXCEEDED')
    return request


def verify(request,artifact):
    errors=[];delivered=[];costs={};total_payments=0
    try:
        validate_request(request)
        keys={'schema','request_id','input_sha256','dispatch_wh','payments_microUSD','delivered_wh'}
        if not isinstance(artifact,dict) or set(artifact)!=keys or artifact['schema']!='flexibility063/dispatch/v1': raise ValueError('EXACT_DISPATCH_REQUIRED')
        if artifact['request_id']!=request['id'] or artifact['input_sha256']!=digest(request): errors.append('INPUT_BINDING')
        ids={d['id'] for d in request['devices']}
        dispatch=artifact['dispatch_wh'];payments=artifact['payments_microUSD'];n=len(request['target_wh'])
        if not isinstance(dispatch,dict) or set(dispatch)!=ids or not isinstance(payments,dict) or set(payments)!=ids: raise ValueError('EXACT_DEVICE_PARTITION_REQUIRED')
        reductions=[0]*n
        for device in request['devices']:
            ident=device['id'];row=dispatch[ident];payment=payments[ident]
            if not isinstance(row,list) or len(row)!=n or any(type(v) is not int or v<0 for v in row): raise ValueError('INTEGER_DISPATCH_REQUIRED')
            if type(payment) is not int or payment<0: raise ValueError('INTEGER_PAYMENT_REQUIRED')
            if sum(row)!=device['required_wh']: errors.append('DEVICE_ENERGY:'+ident)
            removed=0
            for t,value in enumerate(row):
                if value>device['power_wh'][t] or value and not device['available'][t]: errors.append('DEVICE_CAPACITY:'+ident)
                if request['target_wh'][t]:
                    reduction=device['baseline_wh'][t]-value
                    if reduction<0: errors.append('EVENT_REBOUND:'+ident)
                    reductions[t]+=reduction
                    removed+=reduction
            cost=removed*device['disutility_microUSD_per_wh']
            costs[ident]=cost
            expected=cost+request['participant_margin_microUSD'] if removed>0 else 0
            if payment!=expected: errors.append('PARTICIPANT_OUTSIDE_OPTION:'+ident)
            total_payments+=payment
        delivered=[r*(1_000_000-request['derating_ppm'])//1_000_000 for r in reductions]
        if artifact['delivered_wh']!=delivered or any(type(v) is not int for v in artifact['delivered_wh']): errors.append('DELIVERED_REPLAY')
        if any(d<t for d,t in zip(delivered,request['target_wh'])): errors.append('CONTRACT_SHORTFALL')
        if total_payments>request['buyer_budget_microUSD']: errors.append('BUYER_BUDGET')
    except (ValueError,TypeError,KeyError,OverflowError) as exc:
        errors.append(str(exc))
    try: artifact_hash=digest(artifact)
    except (TypeError,ValueError): artifact_hash=None
    try: input_hash=digest(request)
    except (TypeError,ValueError): input_hash=None
    return {'accepted':not errors,'errors':sorted(set(errors)),'input_sha256':input_hash,'artifact_sha256':artifact_hash,
            'delivered_wh':delivered,'participant_cost_microUSD':costs,'participant_payments_microUSD':total_payments,
            'scope':'SYNTHETIC_COMPUTATION_ONLY','independence':'Separate integer replay; same host and agent family; no external certification'}
