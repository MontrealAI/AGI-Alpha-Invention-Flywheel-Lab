"""Transparent ordinary models for one declared laboratory protocol."""
from __future__ import annotations
import math
from statistics import median
import numpy as np
from scipy.optimize import lsq_linear
from .measurement import window_capacity

CUTOFF=100
ENDPOINTS=(500,1000)
METHODS=('adjusted_peer','peer','persistence','recent_linear','sqrt_linear','curve_ridge')
PRIMARY='adjusted_peer'
SCREEN_THRESHOLD=0.8

def prefix_features(m):
    missing=[c for c in range(1,101) if c not in m.cycles]
    if len(missing)>5 or 10 not in m.cycles or 100 not in m.cycles:
        raise ValueError('At least95/100 valid cycles and exact cycles10/100 required')
    ref=window_capacity(m,1,10)
    curve={c:e['capacity_ah']/ref for c,e in m.cycles.items() if 1<=c<=CUTOFF}
    last=window_capacity(m,91,100)/ref
    xs=np.array([c for c in range(51,101) if c in curve],dtype=float)
    ys=np.array([curve[int(c)] for c in xs])
    slope=float(np.polyfit(xs,ys,1)[0])
    vectors=[]
    for c in (10,100):
        points=np.array(m.cycles[c]['curve'],dtype=float)
        # Only interpolate within measured voltage support, never extrapolate.
        if points[:,0].min()>3.2 or points[:,0].max()<4.1:
            vectors=[];break
        order=np.argsort(points[:,0],kind='stable')
        v,q=points[order,0],points[order,1]/ref
        uv,ix=np.unique(v,return_index=True)
        vectors.append(np.interp(np.linspace(3.2,4.1,64),uv,q[ix]))
    variance=float(np.var(vectors[1]-vectors[0])) if len(vectors)==2 else None
    features=[last,curve[50]-curve[10] if 50 in curve else float(np.mean(ys))-curve[10],slope*100,
              math.log10(max(variance,1e-12)) if variance is not None else None]
    return dict(reference_capacity_ah=ref,last_retention=last,curve=curve,features=features,
                missing_prefix_cycles=missing,voltage_variance=variance)

def fit_bank(training):
    peers={x['group']:{'features':x['prefix']['features'],'last_retention':x['prefix']['last_retention'],
                      'targets':x['targets'],'source_cell':x['cell']} for x in training if x.get('targets')}
    usable=[x for x in training if all(str(t) in x.get('targets',{}) for t in ENDPOINTS) and all(v is not None for v in x['prefix']['features'])]
    ridge=None
    if len(usable)>=5:
        X=np.array([x['prefix']['features'] for x in usable],float)
        means=X.mean(axis=0);scales=np.maximum(X.std(axis=0),1e-8)
        Z=(X-means)/scales;Z=np.c_[np.ones(len(Z)),Z]
        Y=np.array([[x['targets'][str(t)] for t in ENDPOINTS] for x in usable])
        penalty=np.diag([0]+[10.0]*(Z.shape[1]-1))
        coef=np.linalg.solve(Z.T@Z+penalty,Z.T@Y)
        ridge=dict(means=means.tolist(),scales=scales.tolist(),coef=coef.tolist(),alpha=10.0,n=len(usable))
    return dict(peers=peers,ridge=ridge,training_cells=[x['cell'] for x in training],widths={})

def predict(prefix,group,bank,method):
    if group not in bank['peers']:
        raise ValueError('Unsupported model group: continue testing')
    peer=bank['peers'][group]
    if abs(prefix['last_retention']-peer['last_retention'])>0.10:
        raise ValueError('Early retention shifted >10 percentage points from training peer')
    curve=prefix['curve'];ns=np.array(sorted(curve),float);ys=np.array([curve[int(c)] for c in ns])
    out={}
    for t in ENDPOINTS:
        if method in {'adjusted_peer','peer'} and str(t) not in peer['targets']:continue
        if method=='adjusted_peer':p=prefix['last_retention']+peer['targets'][str(t)]-peer['last_retention']
        elif method=='peer':p=peer['targets'][str(t)]
        elif method=='persistence':p=prefix['last_retention']
        elif method=='recent_linear':
            mask=ns>=51
            p=float(np.polyval(np.polyfit(ns[mask],ys[mask],1),t))
        elif method=='sqrt_linear':
            X=np.c_[np.ones(len(ns)),-np.sqrt(ns),-ns]
            fit=lsq_linear(X,ys,bounds=([-np.inf,0,0],[np.inf,np.inf,np.inf]),tol=1e-12,max_iter=1000)
            if not fit.success:raise ValueError('Constrained regression did not converge')
            p=float(np.array([1,-math.sqrt(t),-t])@fit.x)
        elif method=='curve_ridge':
            if bank['ridge'] is None or any(x is None for x in prefix['features']):raise ValueError('Curve feature unavailable')
            r=bank['ridge'];z=(np.array(prefix['features'])-r['means'])/r['scales']
            p=float(np.r_[1,z]@np.array(r['coef'])[:,ENDPOINTS.index(t)])
        else:raise ValueError('Unknown method')
        if not math.isfinite(p):raise ValueError('Nonfinite forecast')
        out[str(t)]=p
    if not out:raise ValueError('No supported endpoint targets')
    return out

def interval_decision(predictions,widths):
    out={}
    for t,p in predictions.items():
        if t not in widths:
            out[t]={'prediction':p,'decision':'CONTINUE_TESTING','reason':'No calibration interval'};continue
        w=widths[t];low=p-w;high=p+w
        decision='SCREEN_PASS' if low>=SCREEN_THRESHOLD else ('SCREEN_FAIL' if high<SCREEN_THRESHOLD else 'CONTINUE_TESTING')
        out[t]={'prediction':p,'lower':low,'upper':high,'decision':decision}
    return out
