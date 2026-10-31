"""Known system-identification adaptation: compile a bounded observable envelope.

This is a developer-authored constructor using established interpolation, not a
claim of autonomous scientific invention or superiority to ordinary reuse.
"""
import copy
import time
import numpy as np
from .physics import digest, evaluate, check_trace, validate_request, validate_policy

def construct(requests, *, oracle_current_A=4.0, safety_factor=.95):
    if not isinstance(requests,list) or not 2<=len(requests)<=8:raise ValueError('FINITE_DECLARED_TRAINING_CASES_REQUIRED')
    for r in requests:validate_request(r)
    constants=[{k:v for k,v in r.items() if k!='temperature_K'} for r in requests]
    if any(x!=constants[0] for x in constants):raise ValueError('MATCHED_TRAINING_MODEL_REQUIRED')
    temperatures=[r['temperature_K'] for r in requests]
    if temperatures!=sorted(set(temperatures)):raise ValueError('ORDERED_DISTINCT_TRAINING_TEMPERATURES_REQUIRED')
    start=time.monotonic();cpu=time.process_time();receipts=[];curves=[]
    grid=np.linspace(requests[0]['initial_soc'],requests[0]['target_soc'],17)
    for r in requests:
        out=evaluate(r,{'kind':'anode','current_A':oracle_current_A})
        checked=check_trace(r,out)
        if not checked['accepted']:raise ValueError('ORACLE_TRAINING_OUTCOME_NOT_QUALIFIED')
        trace=out['trace'];soc=r['initial_soc']-np.array(trace['discharge_Ah'])/out['nominal_capacity_Ah']
        curves.append(np.interp(grid,soc,-np.array(trace['current_A'])).tolist())
        receipts.append({'request':r,'trace_sha256':out['trace_sha256'],'check':checked,'resources':out['resources']})
    policy={'kind':'envelope','parameter_set':requests[0]['parameter_set'],'temperatures_K':temperatures,'soc_grid':grid.tolist(),'current_grid_A':curves,'safety_factor':safety_factor,'training_digest':digest([{k:v for k,v in row.items() if k!='resources'} for row in receipts])}
    validate_policy(policy)
    return {'policy':policy,'training':receipts,'resources':{'process_cpu_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start},'scope':'KNOWN_METHOD_GENERATED_OBSERVABLE_ENVELOPE_NOT_NOVEL_DISCOVERY_OR_PHYSICAL_VALIDATION','applicability':'Same parameter model and trained temperature/SOC ranges; measured passed charge and ambient temperature required. Recheck each requested outcome.'}
