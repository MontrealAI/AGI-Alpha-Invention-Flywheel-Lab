"""Separately written ODE plant and evaluator, never imported by producer."""
from __future__ import annotations
import numpy as np
from scipy.integrate import solve_ivp


def truth_rates(seed,kind):
    rng=np.random.default_rng(seed)
    a=float(rng.uniform(.18,1.2));b=float(rng.uniform(.025,.22));c=float(rng.uniform(.025,.20));d=float(rng.uniform(.03,.30))
    if kind=='series':return [a,b,0.,0.]
    if kind=='parallel':return [a,0.,c,0.]
    if kind in ('combined','nonlinear','gain','noisy','limited'):return [a,b,c,0.]
    if kind=='reversible':return [a,b,c,d]
    raise ValueError('KIND')


def derivative(r,kind):
    def rhs(t,y):
        ab=r[0]*y[0]*(1+1.5*y[0] if kind=='nonlinear' else 1)
        bc=r[1]*y[1];ac=r[2]*y[0];ba=r[3]*y[1]
        return [-ab-ac+ba,ab-bc-ba,ac+bc]
    return rhs


def measure_exact(r,kind,t,fraction_b=0.):
    sol=solve_ivp(derivative(r,kind),(0.,float(t)),[1-fraction_b,fraction_b,0.],
                  method='DOP853',rtol=2e-11,atol=2e-13)
    if not sol.success:raise RuntimeError('REFERENCE_ODE_FAILED')
    return sol.y[:,-1]


def observer(seed,kind,noise_bound):
    r=truth_rates(seed,kind);receipts=[]
    def measure(t,q):
        key=int(round(t*1000))+int(q*1000000)+seed
        err=np.random.default_rng(key).uniform(-noise_bound,noise_bound,3)
        y=measure_exact(r,kind,t,q)
        if kind=='gain':y=y*1.12+np.array([.01,.02,.03])
        y+=err
        receipts.append({'time_s':t,'fraction_b':q,'observation':y.tolist()})
        return y
    return measure,receipts


def process_exact(r,kind,design):
    t,tau,f=design
    first=measure_exact(r,kind,t)
    extracted=f*first[1];feed=first.copy();feed[1]*=1-f
    rhs=derivative(r,kind)
    def flow(t,y):return np.asarray(rhs(t,y))+(feed-y)/tau
    # Long integration plus an independently checked stationary residual.
    final=solve_ivp(flow,(0.,max(500.,tau*150)),feed,method='LSODA',rtol=1e-10,atol=1e-12)
    out=final.y[:,-1]
    if not final.success or max(abs(flow(0,out)))>1e-8:raise ValueError('CSTR_STATIONARITY')
    y=extracted+out[1];score=y-.02*(t+tau)-.10*f
    return float(y),float(score)


def evaluate(seed,kind,k1,k2,menu):
    r=truth_rates(seed,kind)
    truth=[]
    for d in menu:
        y,s=process_exact(r,kind,d)
        if y>=.40:truth.append((s,d,y))
    best=max(truth,default=None)
    actual=None;design_ok=False;error=None
    if k2['design'] is not None:
        y,s=process_exact(r,kind,k2['design']);actual={'yield':y,'score':s}
        gap=best[0]-s if best else None
        design_ok=best is not None and y>=.40-1e-9 and gap<=.02
        actual['score_regret']=gap
    model_ok=False
    if k1['models']:
        errors=[]
        for t,q in ((.37,.17),(1.3,.63),(3.7,.82),(6.1,.28)):
            exact=measure_exact(r,kind,t,q)
            for m in k1['models']:
                # Deliberately integrate the proposed program; do not call its closed form.
                pred=measure_exact(m['rates'],'combined',t,q)
                errors.append(float(max(abs(pred-exact))))
        error=max(errors);model_ok=error<=.025
    # Gain-corrupted evidence cannot substantiate a scientifically accepted model.
    if kind=='gain':model_ok=False
    safe_abstention=k2['design'] is None
    return {'k1_predictive_acceptance':model_ok,'maximum_fresh_concentration_error':error,
            'k2_design_acceptance':bool(design_ok and model_ok),'actual_design':actual,
            'reference_feasible':best is not None,'reference_best_score':None if best is None else best[0],
            'abstained':safe_abstention,'false_deployment':bool(k2['design'] is not None and not (design_ok and model_ok))}
