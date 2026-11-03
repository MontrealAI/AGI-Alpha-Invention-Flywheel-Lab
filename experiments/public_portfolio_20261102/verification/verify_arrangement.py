from __future__ import annotations
import argparse, copy, json, math
from pathlib import Path
import numpy as np
import verify_science as base


def additional_checks(checks,rng):
    m=base.module('arrangement','orbital')
    request=base.module('arrangement','experiment').base_request()
    result=m.select_contract(request)
    if result['accepted']:
        selected=result['selected']
        checks.add('selected_contract_is_voluntary_and_prefunded',
                   all(s>=-1e-8 for s in selected['participation_surplus_usd']) and
                   all(need<=cash for need,cash in zip(selected['cash_required_usd'],request['cash_usd'])) and
                   selected['overlap_bound']<=request['max_overlap_bound'])
    else:
        checks.add('selected_contract_is_voluntary_and_prefunded',True, outcome='model_refusal')
    for label,update in [('no_demand',{'asset_loss_usd':[0.,0.]}),
                         ('no_prefunding',{'cash_usd':[0.,0.]}),
                         ('execution_default',{'execution_default':True})]:
        req=copy.deepcopy(request);req.update(update)
        checks.add(label+'_refused',not m.select_contract(req)['accepted'])
    for label,update in [('withdrawn_consent',{'consent':[True,False]}),
                         ('truthy_string_consent',{'consent':['yes','yes']}),
                         ('nonfinite_model_envelope',{'linearization_scale_m':float('nan')})]:
        req=copy.deepcopy(request);req.update(update)
        checks.reject(label+'_refused',lambda req=req:m.select_contract(req))
    from scipy.integrate import solve_ivp
    accepted=0;maximum_error=0.;failures=[]
    for case in range(12):
        n=float(rng.uniform(.0009,.0012));duration=float(rng.uniform(6500,9000))
        initial=np.concatenate([rng.uniform(-200,200,size=3),np.zeros(3)])
        target=np.array([500.,30.,10.,0.,0.,0.])
        transfer=m.servicing_transfer(n,duration,initial,target)
        if not transfer['accepted']:
            continue
        accepted+=1;state=initial.copy()
        def ode(t,s):
            x,y,z,vx,vy,vz=s
            return [vx,vy,vz,3*n*n*x+2*n*vy,-2*n*vx,-n*n*z]
        for burn in transfer['burns_mps']:
            state[3:]+=np.asarray(burn)
            state=solve_ivp(ode,[0,duration/2],state,rtol=1e-11,atol=1e-11).y[:,-1]
        error=float(np.max(abs(state-target)));maximum_error=max(maximum_error,error)
        if error>1e-5 or sum(np.linalg.norm(v) for v in transfer['burns_mps'])>5+1e-10:
            failures.append({'case':case,'endpoint_error':error})
    checks.add('different_successor_endpoint_design_independent_ode',accepted>0 and not failures,
               cases=12,accepted=accepted,max_absolute_endpoint_error=maximum_error,failures=failures,
               scope='Endpoint only; no continuous approach corridor or integrated collision probability')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--nonce',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();output=Path(args.output)
    if output.exists():
        raise ValueError('refuse overwrite of existing independent result')
    original=base.ROUTES['arrangement']
    def combined(checks,rng):
        original(checks,rng)
        additional_checks(checks,rng)
    base.ROUTES['arrangement']=combined
    result=base.run('arrangement',args.nonce)
    result['checker_chain_sha256']={'verify_science.py':base.digest(base.__file__),'verify_arrangement.py':base.digest(__file__)}
    result['amendment']='Final arrangement API adaptation adds preregistered refusal and successor endpoint cases before first arrangement outcome; earlier route checker is unchanged'
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'route':'arrangement','passed':result['passed'],'checks':len(result['checks']),'output':str(output)}))
    raise SystemExit(0 if result['passed'] else 1)
