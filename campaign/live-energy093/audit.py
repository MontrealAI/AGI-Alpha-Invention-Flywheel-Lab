"""Independent offline LP, retained-input and publication-integrity checks.
Usage: python audit.py [--forecast path/forecast.json --inputs path/fit_inputs.json]
No downloads or external writes. Prints JSON evidence; failures raise exceptions.
"""
import argparse, hashlib, importlib.util, json
from pathlib import Path
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import csr_matrix, eye, hstack, vstack

def alternate_lp(X,y):
    # Independent formulation: free residual split into positive/negative errors;
    # deviations from uniform split into positive/negative weight deviations.
    n,k=X.shape; z=csr_matrix
    A=vstack([hstack([z(X),-eye(n),eye(n),z((n,2*k))]),
              hstack([eye(k),z((k,2*n)),-eye(k),eye(k)]),
              z(np.r_[np.ones(k),np.zeros(2*n+2*k)][None,:])]).tocsr()
    b=np.r_[y,np.full(k,1/k),1.]
    lam=.02*np.mean(np.abs(y)); c=np.r_[np.zeros(k),np.full(2*n,1/n),np.full(2*k,lam)]
    res=linprog(c,A_eq=A,b_eq=b,bounds=(0,None),method='highs')
    assert res.success,res.message
    return res.x[:k],res.fun

def load_runner():
    spec=importlib.util.spec_from_file_location('runner_under_test',Path(__file__).with_name('run.py'))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def unit_tests(mod):
    rng=np.random.default_rng(903); records=[]
    cases=[(rng.normal(size=(35,6)),rng.normal(size=35)),
           (np.ones((9,6)),np.ones(9)),
           (np.zeros((7,6)),np.zeros(7)),
           (rng.normal(size=(31,6))*2000,rng.normal(size=31)*2000)]
    for X,y in cases:
        w,cert=mod.fit(X,y); wa,opt=alternate_lp(X,y)
        obj=np.mean(np.abs(X@w-y))+.02*np.mean(np.abs(y))*np.abs(w-1/X.shape[1]).sum()
        assert abs(w.sum()-1)<1e-8 and w.min()>=-1e-8
        assert np.isclose(obj,opt,rtol=1e-8,atol=1e-7),(obj,opt)
        assert np.isclose(obj,cert['objective'])
        # Ordinary equal-information recomputation must reproduce current engine.
        w2,c2=mod.fit(X.copy(),y.copy())
        assert np.allclose(w,w2,rtol=0,atol=1e-10)
        records.append({'n':len(y),'objective':obj,'alternate_objective':opt,'ordinary_refit_max_weight_delta':float(abs(w-w2).max())})
    assert not mod.finite([1.]*95) and not mod.finite([1.]*100)
    assert not mod.finite([float('nan')]*96)
    assert not mod.finite([None]*96)
    assert mod.finite([1.]*96)
    return records

def audit_artifacts(mod,forecast,inputs):
    f=json.loads(forecast.read_text()); used=json.loads(inputs.read_text()); records={}
    assert f['issue_date']=='2026-11-04' and f['delivery_date']=='2026-11-05'
    assert f['n']==96 and f['t0']=='2026-11-04T23:00:00Z'
    assert f['protocol_sha256']==hashlib.sha256(Path(__file__).with_name('PROTOCOL.md').read_bytes()).hexdigest()
    assert set(f['series'])==set(mod.SERIES)
    for key,s in f['series'].items():
        if s['status']!='available':
            records[key]={'status':'unavailable'};continue
        X=np.asarray(used[key]['X']);y=np.asarray(used[key]['y']);F=np.asarray(used[key]['future_members']);w=np.asarray(s['weights']);p=s['predictions']
        assert X.shape==(96*len(s['complete_days']),6) and y.shape==(len(X),) and F.shape==(96,6)
        assert len(s['complete_days'])>=7
        assert all('2026-10-20'<=d<='2026-11-02' for d in s['complete_days'])
        assert not set(s['complete_days'])&set(s['excluded_days'])
        assert np.isfinite(X).all() and np.isfinite(y).all() and np.isfinite(F).all()
        assert w.min()>=-1e-8 and abs(w.sum()-1)<1e-8
        _,opt=alternate_lp(X,y);obj=np.abs(X@w-y).mean()+.02*np.abs(y).mean()*np.abs(w-1/6).sum()
        assert np.isclose(obj,opt,rtol=1e-8,atol=1e-6),(key,obj,opt)
        assert np.isclose(obj,s['fit_certificate']['objective'])
        mae=np.abs(X-y[:,None]).mean(axis=0);best=min(range(6),key=lambda i:(mae[i],mod.MEMBERS[i]))
        assert s['selected_incumbent']==mod.MEMBERS[best]
        assert np.allclose(p['candidate'],F@w)
        assert np.allclose(p['equal_mean'],F.mean(axis=1))
        assert np.allclose(p['equal_median'],np.median(F,axis=1))
        assert np.allclose(p['selected_incumbent'],F[:,best])
        for i,m in enumerate(mod.MEMBERS):assert np.allclose(p[m],F[:,i])
        w2,_=mod.fit(X.copy(),y.copy())
        assert np.allclose(w,w2,rtol=0,atol=1e-10)
        records[key]={'status':'pass','objective':obj,'independent_optimum':opt,'ordinary_refit_max_weight_delta':float(abs(w-w2).max()),'ordinary_refit_max_prediction_delta':float(abs(F@w-F@w2).max()),'training_days':len(s['complete_days'])}
    return records

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--forecast',type=Path);ap.add_argument('--inputs',type=Path);a=ap.parse_args()
    m=load_runner(); result={'unit_tests':unit_tests(m),'caveats':['Equality is an ordinary identical-information refit control, not evidence of invention.','Historical mutable snapshots cannot establish historical publication-time availability.','A selected incumbent from six members is not the best model across the full public field.']}
    if a.forecast or a.inputs:
        assert a.forecast and a.inputs;result['artifacts']=audit_artifacts(m,a.forecast,a.inputs)
    print(json.dumps(result,indent=2))
