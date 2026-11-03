from __future__ import annotations
import argparse, hashlib, json, sys, time
from pathlib import Path
import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import expm
import verify_science as base

HERE=Path(__file__).resolve().parent


def generator(n):
    a=np.zeros((6,6));a[:3,3:]=np.eye(3)
    a[3,0]=3*n*n;a[3,4]=2*n;a[4,3]=-2*n;a[5,2]=-n*n
    return a


def independent_timing(n,duration,initial,target,fractions):
    g=generator(n);f=expm(g*duration);rows=[]
    for fraction in fractions:
        h=expm(g*duration*(1-fraction));a=np.column_stack([f[:,3:],h[:,3:]])
        if np.linalg.cond(a)>1e10:
            continue
        burns=np.linalg.solve(a,target-f@initial).reshape(2,3)
        residual=float(np.linalg.norm(f@initial+a@burns.ravel()-target))
        fuel=float(sum(np.linalg.norm(b) for b in burns))
        rows.append((fuel,fraction,residual))
    return sorted(rows)


def run(nonce):
    protocol=json.loads((HERE/'TIMING_VERIFICATION_PROTOCOL.json').read_text())
    if hashlib.sha256(nonce.encode()).hexdigest()!=protocol['hidden_nonce_commitment_sha256']:
        raise ValueError('nonce commitment mismatch')
    m=base.module('arrangement','timing_extension');checks=base.Checks()
    rng=np.random.default_rng(int.from_bytes(hashlib.sha256(nonce.encode()).digest()[:8],'big'))
    rows=[]
    fractions=protocol['fresh_population']['second_impulse_fractions']
    for case in range(24):
        n=float(rng.uniform(.0009,.0012));duration=float(rng.uniform(6000,9000))
        initial=np.r_[rng.uniform(-200,200,3),np.zeros(3)];target=np.array([500+5*case,30.,10.,0.,0.,0.])
        result=m.solve_timed_transfer(n,duration,initial,target,fractions)
        truth=independent_timing(n,duration,initial,target,fractions)
        best=truth[0];expected_accepted=best[0]<=5 and best[2]<=1e-7
        fuel_error=abs(result['fuel_mps']-best[0]);state=initial.copy();g=generator(n)
        for burn,interval in zip(result['burns_mps'],[duration*result['second_fraction'],duration*(1-result['second_fraction'])]):
            state[3:]+=np.asarray(burn)
            if interval:
                state=solve_ivp(lambda t,s:g@s,[0,interval],state,rtol=1e-11,atol=1e-11).y[:,-1]
        ode_error=float(np.linalg.norm(state-target))
        passed=fuel_error<1e-7 and bool(result['accepted'])==bool(expected_accepted) and ode_error<1e-5
        rows.append({'case':case,'accepted':bool(result['accepted']),'independent_accepted':bool(expected_accepted),
                     'fuel_mps':result['fuel_mps'],'fuel_difference_from_independent_finite_specialist':fuel_error,
                     'ode_endpoint_error':ode_error,'passed':bool(passed)})
    checks.add('fresh_finite_timing_matches_strong_independent_specialist',all(r['passed'] for r in rows),cases=24)
    checks.add('all_acceptances_preserve_unchanged_fuel_and_endpoint_contract',all(not r['accepted'] or (r['fuel_mps']<=5 and r['ode_endpoint_error']<1e-5) for r in rows))
    for label,fractions_bad in [('zero',[0.]),('after_mission',[1.1]),('nonfinite',[float('nan')])]:
        checks.reject(label+'_timing_refused',lambda fractions_bad=fractions_bad:m.solve_timed_transfer(.001,7200.,np.zeros(6),np.array([500.,0,0,0,0,0]),fractions_bad))
    return {'schema':'public-portfolio-independent-timing-followup-result/v1','checker_sha256':base.digest(__file__),
            'protocol_sha256':base.digest(HERE/'TIMING_VERIFICATION_PROTOCOL.json'),
            'constructor_source_sha256':base.digest(base.BASE/'arrangement/timing_extension.py'),
            'nonce_commitment_sha256':protocol['hidden_nonce_commitment_sha256'],
            'records':rows,'checks':checks.rows,'accepted_count':sum(r['accepted'] for r in rows),
            'refused_count':sum(not r['accepted'] for r in rows),'passed':all(r['passed'] for r in checks.rows),
            'scope':'Post-constructor-report prospectively registered independent fresh follow-up; finite classical timing tie, no physical/continuous/market claim'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--nonce',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    output=Path(args.output)
    if output.exists():
        raise ValueError('refuse overwrite of independent follow-up')
    started=time.time();result=run(args.nonce);result['wall_seconds']=time.time()-started
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'passed':result['passed'],'accepted':result['accepted_count'],'refused':result['refused_count']}))
    raise SystemExit(0 if result['passed'] else 1)
