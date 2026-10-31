"""Independent PyBaMM adapter; no hardware/API access or upstream controller code.

Known models and constraints are reused. A successful simulation is not a battery
safety certification, measured lifetime improvement, or commercial demand proof.
"""
import hashlib
import json
import os
import time
from pathlib import Path
from functools import lru_cache
import importlib.metadata
os.environ['PYBAMM_DISABLE_TELEMETRY'] = 'true'
import numpy as np
import pybamm

SCHEMA='battery-physics-service/v1'
POLICY_KINDS=('cccv','anode','feedback','staged','envelope')

@lru_cache(maxsize=1)
def dependency_identity():
    package=Path(pybamm.__file__).resolve().parent
    pybamm_files={p.relative_to(package).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in package.rglob('*.py')}
    return {'versions':{name:importlib.metadata.version(name) for name in ('pybamm','numpy','scipy','casadi','pybammsolvers')},'pybamm_python_source_sha256':digest(pybamm_files),'solver':'IDAKLUSolver','rtol':1e-6,'atol':1e-6,'physics_adapter_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}

def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def validate_request(r):
    required={'schema','parameter_set','temperature_K','initial_soc','target_soc','maximum_seconds','maximum_current_A','maximum_voltage_V','maximum_temperature_K','minimum_anode_potential_V'}
    if set(r)!=required or r['schema']!=SCHEMA or r['parameter_set'] not in {'Ai2020','Chen2020'}:raise ValueError('QUALIFIED_MODEL_REQUEST_REQUIRED')
    for k in required-{'schema','parameter_set'}:
        if type(r[k]) not in (int,float) or not np.isfinite(r[k]):raise ValueError('FINITE_REQUEST_REQUIRED')
    if not 273.15<=r['temperature_K']<r['maximum_temperature_K']<=333.15 or not 0<r['initial_soc']<r['target_soc']<=.95:raise ValueError('ADMITTED_CONDITIONS_REQUIRED')
    if not 0<r['maximum_seconds']<=7200 or not 0<r['maximum_current_A']<=20 or not 3.9<=r['maximum_voltage_V']<=4.2:raise ValueError('ADMITTED_CONTROL_CONSTRAINTS_REQUIRED')
    if not 0<=r['minimum_anode_potential_V']<=.1:raise ValueError('ADMITTED_ANODE_MARGIN_REQUIRED')
    return r

def validate_policy(p):
    kind=p.get('kind')
    allowed={'cccv':{'kind','current_A'},'anode':{'kind','current_A'},'feedback':{'kind','thermal_gain'},'staged':{'kind','currents_A','soc_breakpoints'},'envelope':{'kind','temperatures_K','soc_grid','current_grid_A','safety_factor','parameter_set','training_digest'}}
    if kind not in POLICY_KINDS or set(p)!=allowed[kind]:raise ValueError('EXACT_ADMITTED_POLICY_REQUIRED')
    if kind in {'cccv','anode','feedback'}:
        x=p.get('current_A',p.get('thermal_gain'))
        if type(x) not in (int,float) or not np.isfinite(x) or not 0<x<=100:raise ValueError('POSITIVE_FINITE_CONTROL_REQUIRED')
    elif kind=='staged':
        if not isinstance(p['currents_A'],list) or not 1<=len(p['currents_A'])<=8 or len(p['soc_breakpoints'])!=len(p['currents_A'])-1 or p['soc_breakpoints']!=sorted(set(p['soc_breakpoints'])):raise ValueError('FINITE_STAGED_CONTROL_REQUIRED')
        if any(type(x) not in (int,float) or not np.isfinite(x) or not 0<x<=20 for x in p['currents_A']) or any(not 0<x<1 for x in p['soc_breakpoints']):raise ValueError('BOUNDED_STAGED_CONTROL_REQUIRED')
    else:
        if p['parameter_set'] not in {'Ai2020','Chen2020'} or not isinstance(p['training_digest'],str) or len(p['training_digest'])!=64:raise ValueError('BOUND_TRAINING_APPLICABILITY_REQUIRED')
        ts,ss,grid=p['temperatures_K'],p['soc_grid'],p['current_grid_A']
        if not 2<=len(ts)<=8 or not 2<=len(ss)<=64 or ts!=sorted(set(ts)) or ss!=sorted(set(ss)) or len(grid)!=len(ts):raise ValueError('FINITE_MONOTONE_ENVELOPE_REQUIRED')
        if any(len(row)!=len(ss) for row in grid):raise ValueError('ALIGNED_ENVELOPE_REQUIRED')
        for x in ts+ss+[p['safety_factor']]+[x for row in grid for x in row]:
            if type(x) not in (int,float) or not np.isfinite(x):raise ValueError('FINITE_ENVELOPE_REQUIRED')
        if not 0<p['safety_factor']<=1 or any(not 0<=x<=20 for row in grid for x in row):raise ValueError('BOUNDED_ENVELOPE_REQUIRED')
    return p

def useful_digest(out):
    return digest({k:v for k,v in out.items() if k!='resources'})

def evaluate(r, policy):
    validate_request(r)
    validate_policy(policy)
    if policy['kind']=='envelope' and (policy['parameter_set']!=r['parameter_set'] or not policy['temperatures_K'][0]<=r['temperature_K']<=policy['temperatures_K'][-1] or not policy['soc_grid'][0]<=r['initial_soc']<r['target_soc']<=policy['soc_grid'][-1]):raise ValueError('OUTSIDE_ACQUIRED_INSTRUMENT_APPLICABILITY')
    started=time.monotonic();cpu=time.process_time()
    params=pybamm.ParameterValues(r['parameter_set'])
    params.update({'Initial temperature [K]':r['temperature_K'],'Ambient temperature [K]':r['temperature_K'],'Current function [A]':-r['maximum_current_A']})
    capacity=float(params['Nominal cell capacity [A.h]']);charge=(r['target_soc']-r['initial_soc'])*capacity
    model=pybamm.lithium_ion.DFN(options={'thermal':'lumped'})
    model.variables['Anode potential [V]']=model.variables['Negative electrode surface potential difference at separator interface [V]']
    done=pybamm.step.CustomTermination('Requested charge attained',lambda v:charge+v['Discharge capacity [A.h]'])
    thermal=pybamm.step.CustomTermination('Request temperature limit',lambda v:r['maximum_temperature_K']-v['Volume-averaged cell temperature [K]'])
    if policy['kind']=='cccv':
        current=min(r['maximum_current_A'],float(policy['current_A']))
        steps=[pybamm.step.current(-current,duration=r['maximum_seconds'],termination=[done,thermal,str(r['maximum_voltage_V'])+'V']),
               pybamm.step.voltage(r['maximum_voltage_V'],duration=r['maximum_seconds'],termination=[done,thermal])]
    elif policy['kind']=='staged':
        if any(not r['initial_soc']<x<r['target_soc'] for x in policy['soc_breakpoints']):raise ValueError('STAGES_OUTSIDE_REQUEST')
        steps=[]
        for target,current in zip(policy['soc_breakpoints']+[r['target_soc']],policy['currents_A']):
            threshold=(target-r['initial_soc'])*capacity
            stage_done=pybamm.step.CustomTermination('Stage charge '+str(target),lambda v,q=threshold:q+v['Discharge capacity [A.h]'])
            steps.append(pybamm.step.current(-min(r['maximum_current_A'],current),duration=r['maximum_seconds'],termination=[stage_done,thermal,str(r['maximum_voltage_V'])+'V']))
        steps.append(pybamm.step.voltage(r['maximum_voltage_V'],duration=r['maximum_seconds'],termination=[done,thermal]))
    elif policy['kind']=='anode':
        cut=pybamm.step.CustomTermination('Anode margin',lambda v:v['Anode potential [V]']-r['minimum_anode_potential_V'])
        hold=lambda v:v['Anode potential [V]']-r['minimum_anode_potential_V']
        steps=[pybamm.step.current(-min(r['maximum_current_A'],float(policy['current_A'])),duration=r['maximum_seconds'],termination=[done,thermal,cut,str(r['maximum_voltage_V'])+'V']),
               pybamm.step.CustomStepImplicit(hold,duration=r['maximum_seconds'],termination=[done,thermal,str(r['maximum_voltage_V'])+'V'],direction='charge'),
               pybamm.step.voltage(r['maximum_voltage_V'],duration=r['maximum_seconds'],termination=[done,thermal])]
    else:
        # Temperature and passed charge are dynamic/observable states; voltage
        # protection is the same explicit CC-to-CV transition as the comparator.
        def controlled(v):
            if policy['kind']=='envelope':
                soc=r['initial_soc']-v['Discharge capacity [A.h]']/capacity
                temp=pybamm.Scalar(r['temperature_K'])
                soc=pybamm.minimum(policy['soc_grid'][-1],pybamm.maximum(policy['soc_grid'][0],soc))
                temp=pybamm.minimum(policy['temperatures_K'][-1],pybamm.maximum(policy['temperatures_K'][0],temp))
                ceiling=pybamm.Interpolant((np.array(policy['temperatures_K']),np.array(policy['soc_grid'])),np.array(policy['current_grid_A']),[temp,soc],interpolator='linear')*policy['safety_factor']
                ceiling=pybamm.minimum(r['maximum_current_A'],ceiling)
            else:
                troom=pybamm.maximum(0,r['maximum_temperature_K']-v['Volume-averaged cell temperature [K]'])
                ceiling=pybamm.minimum(r['maximum_current_A'],float(policy['thermal_gain'])*troom)
            return -ceiling
        steps=[pybamm.step.CustomStepExplicit(controlled,duration=r['maximum_seconds'],termination=[done,thermal,str(r['maximum_voltage_V'])+'V'],direction='charge'),
               pybamm.step.voltage(r['maximum_voltage_V'],duration=r['maximum_seconds'],termination=[done,thermal])]
    sim=pybamm.Simulation(model,parameter_values=params,experiment=pybamm.Experiment(steps,period='5 seconds'),solver=pybamm.IDAKLUSolver(rtol=1e-6,atol=1e-6))
    solution=sim.solve(initial_soc=r['initial_soc'])
    trace={k:np.asarray(solution[name].entries,dtype=float).reshape(-1).tolist() for k,name in {'seconds':'Time [s]','current_A':'Current [A]','voltage_V':'Voltage [V]','temperature_K':'Volume-averaged cell temperature [K]','discharge_Ah':'Discharge capacity [A.h]','anode_potential_V':'Anode potential [V]'}.items()}
    result={'dependency_identity':dependency_identity(),'schema':SCHEMA,'request_sha256':digest(r),'policy':policy,'parameter_set':r['parameter_set'],'nominal_capacity_Ah':capacity,'pybamm_version':pybamm.__version__,'trace':trace,'trace_sha256':digest(trace),'termination':str(solution.termination),'scope':'PHYSICS_MODEL_SIMULATION_NOT_HARDWARE_OR_LIFETIME_PROOF','resources':{'process_cpu_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-started,'billing':'HOST_MODEL_ENGINEERING_BILLING_UNKNOWN'}}
    return result

def check_trace(r,out):
    validate_request(r)
    if out['request_sha256']!=digest(r) or out['trace_sha256']!=digest(out['trace']):raise ValueError('SOURCE_DATA_BINDING_FAILED')
    if out.get('dependency_identity')!=dependency_identity():raise ValueError('DEPENDENCY_SOURCE_IDENTITY_CHANGED')
    if out.get('pybamm_version')!=pybamm.__version__ or out.get('parameter_set')!=r['parameter_set']:raise ValueError('PHYSICS_DEPENDENCY_OR_MODEL_CHANGED')
    validate_policy(out['policy'])
    t=out['trace'];n=len(t['seconds'])
    if n<2 or any(len(v)!=n or any(not np.isfinite(x) for x in v) for v in t.values()):raise ValueError('FINITE_ALIGNED_TRACE_REQUIRED')
    if abs(t['seconds'][0])>1e-6 or abs(t['discharge_Ah'][0])>1e-6:raise ValueError('ZERO_ORIGIN_REQUIRED')
    if any(b<a for a,b in zip(t['seconds'],t['seconds'][1:])):raise ValueError('MONOTONE_TIME_REQUIRED')
    expected_capacity=float(pybamm.ParameterValues(r['parameter_set'])['Nominal cell capacity [A.h]'])
    if out['nominal_capacity_Ah']!=expected_capacity:raise ValueError('PARAMETER_CAPACITY_CHANGED')
    charge=(r['target_soc']-r['initial_soc'])*expected_capacity
    attained=[i for i,q in enumerate(t['discharge_Ah']) if -q>=charge-1e-5]
    first=attained[0] if attained else n-1
    end=n-1
    failures=[]
    if attained and t['seconds'][-1]>t['seconds'][first]+1e-3:failures.append('POST_TARGET_EXECUTION')
    if not attained:failures.append('TARGET_CHARGE_NOT_ATTAINED')
    if t['seconds'][end]>r['maximum_seconds']+1e-5:failures.append('FULL_CHARGE_TIME_EXCEEDED')
    if max(t['voltage_V'][:end+1])>r['maximum_voltage_V']+1e-4:failures.append('VOLTAGE_EXCEEDED')
    if max(t['temperature_K'][:end+1])>r['maximum_temperature_K']+1e-4:failures.append('TEMPERATURE_EXCEEDED')
    if max(abs(x) for x in t['current_A'][:end+1])>r['maximum_current_A']+1e-4:failures.append('CURRENT_EXCEEDED')
    if min(t['anode_potential_V'][:end+1])<r['minimum_anode_potential_V']-1e-4:failures.append('MODELED_ANODE_MARGIN_VIOLATED')
    return {'accepted':not failures,'failures':failures,'charge_seconds':t['seconds'][end],'charged_Ah':-t['discharge_Ah'][end],'simulated_input_energy_Wh':float(np.trapezoid(-np.array(t['current_A'])*np.array(t['voltage_V']),np.array(t['seconds']))/3600),'minimum_anode_potential_V':min(t['anode_potential_V'][:end+1]),'max_voltage_V':max(t['voltage_V'][:end+1]),'max_temperature_K':max(t['temperature_K'][:end+1]),'scope':'SAMPLED_PHYSICS_TRACE_CHECK_NOT_INDEPENDENT_PHYSICAL_VALIDATION'}


def independent_check(r,out):
    """Independent same-model execution, not independent physical validation.

    Callers must fund this work. Successful result caches require exact input,
    useful artifact, implementation and dependency identities; not producer trust.
    """
    checked=check_trace(r,out)
    replay=evaluate(r,out['policy'])
    reproduced=check_trace(r,replay)
    if checked!=reproduced:
        for k in ('charge_seconds','charged_Ah','minimum_anode_potential_V','max_voltage_V','max_temperature_K','simulated_input_energy_Wh'):
            if not np.isclose(checked[k],reproduced[k],rtol=1e-6,atol=1e-6):raise ValueError('INDEPENDENT_PHYSICS_REPLAY_CHANGED')
        if checked['accepted']!=reproduced['accepted'] or checked['failures']!=reproduced['failures']:raise ValueError('INDEPENDENT_VERDICT_CHANGED')
    for k in out['trace']:
        if len(out['trace'][k])!=len(replay['trace'][k]) or not np.allclose(out['trace'][k],replay['trace'][k],rtol=1e-6,atol=1e-6):raise ValueError('INDEPENDENT_TRACE_CHANGED')
    return {**checked,'useful_digest':useful_digest(out),'independent_replay':True,'verification_resources':replay['resources']}
