"""Finite prospective forecast construction; no trade, API key, or paid service."""
import argparse, datetime as dt, hashlib, json, time, urllib.request
from pathlib import Path
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import eye, csr_matrix, hstack, vstack
MEMBERS = ['chronos2_cov','timesfm3_cov','t0_gamma_cov','tirex2_cov','timestral_cov','lgbm_prod']
SERIES = [f'{z}_{k}' for z in ['BE','NL','FR','DE','DK1','DK2'] for k in ['wind','load']]

def finite(x, n=96):
    return isinstance(x,list) and len(x)==n and all(isinstance(v,(int,float)) and np.isfinite(v) for v in x)

def fit(X,y):
    n,k=X.shape; penalty=.02*np.mean(abs(y)); I=eye(n); Z=csr_matrix((n,k))
    A=vstack([hstack([csr_matrix(X),-I,Z]),hstack([-csr_matrix(X),-I,Z]),
      hstack([eye(k),csr_matrix((k,n)),-eye(k)]),hstack([-eye(k),csr_matrix((k,n)),-eye(k)])]).tocsr()
    b=np.r_[y,-y,np.ones(k)/k,-np.ones(k)/k]
    c=np.r_[np.zeros(k),np.ones(n)/n,np.ones(k)*penalty]
    sol=linprog(c,A_ub=A,b_ub=b,A_eq=csr_matrix(np.r_[np.ones(k),np.zeros(n+k)][None,:]),b_eq=[1.],bounds=(0,None),method='highs')
    if not sol.success: raise RuntimeError(sol.message)
    w=sol.x[:k]; objective=np.mean(abs(X@w-y))+penalty*sum(abs(w-1/k))
    if min(w)<-1e-8 or abs(sum(w)-1)>1e-8 or abs(objective-sol.fun)>1e-5: raise ValueError('LP certificate mismatch')
    return w, {'objective':float(objective),'solver_objective':float(sol.fun),'training_points':n,'penalty':float(penalty)}

def fetch(date,folder):
    path=folder/(date+'.json'); meta=folder/(date+'.meta.json')
    if not path.exists():
        url=f'https://energybench.foretec.co/data/days/{date}.json'
        with urllib.request.urlopen(url,timeout=90) as response:
            raw=response.read(); headers={k:response.headers.get(k) for k in ['Last-Modified','ETag','Content-Length']}
        path.write_bytes(raw); meta.write_text(json.dumps({'url':url,'fetched_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'headers':headers,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},indent=2)+'\n')
    raw=path.read_bytes(); info=json.loads(meta.read_text())
    if hashlib.sha256(raw).hexdigest()!=info['sha256']: raise ValueError('Snapshot changed')
    d=json.loads(raw)
    if d['issue_date']!=date or d['n'] not in (92,96,100): raise ValueError('Unexpected issue or horizon')
    return d,info

def construct(folder,out,successor_from=None):
    wall=time.monotonic(); cpu=time.process_time(); folder.mkdir(parents=True,exist_ok=True)
    issue='2026-11-06' if successor_from else '2026-11-04'
    delivery='2026-11-07' if successor_from else '2026-11-05'
    dates=[(dt.date(2026,10,20)+dt.timedelta(days=i)).isoformat() for i in range(16 if successor_from else 14)]
    prior=json.loads(successor_from.read_text()) if successor_from else None
    prior_inputs=json.loads(successor_from.with_name('fit_inputs.json').read_text()) if successor_from else None
    if prior and (prior['issue_date']!='2026-11-04' or prior['members']!=MEMBERS): raise ValueError('Unexpected parent instrument')
    docs={}; manifest=[]
    for date in (dates[-2:] if prior else dates)+[issue]:
        docs[date],meta=fetch(date,folder); manifest.append(meta)
    future=docs[issue]
    if future['n']!=96: raise ValueError('Future horizon must be 96')
    if dt.datetime.now(dt.timezone.utc)>=dt.datetime.fromisoformat(future['t0'].replace('Z','+00:00')): raise ValueError('Delivery already started; cannot preregister')
    result={'issue_date':issue,'delivery_date':delivery,'t0':future['t0'],'n':96,'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'protocol_sha256':hashlib.sha256(Path(__file__).with_name('PROTOCOL.md').read_bytes()).hexdigest(),'members':MEMBERS,'status':'prospective, post-gate, unscored','series':{},'sources':manifest}
    if successor_from:
        result['parent_forecast_sha256']=hashlib.sha256(successor_from.read_bytes()).hexdigest()
        result['parent_fit_inputs_sha256']=hashlib.sha256(successor_from.with_name('fit_inputs.json').read_bytes()).hexdigest()
        result['update_scope']='Frozen original fit rows plus only newly completed issueNov3 and issueNov4; no old-label revisions'
    used={}
    for key in SERIES:
        fs=future['series'][key]
        if fs.get('actual') is not None and any(v is not None for v in fs['actual']): raise ValueError('Future outcome exposure')
        selected=list(prior['series'][key]['complete_days']) if prior else []
        missing=list(prior['series'][key]['excluded_days']) if prior else []
        for date in (dates[-2:] if prior else dates):
            s=docs[date]['series'].get(key,{})
            if finite(s.get('actual')) and all(finite(s.get('models',{}).get(m,{}).get('p')) for m in MEMBERS): selected.append(date)
            else: missing.append(date)
        if len(selected)<7 or not all(finite(fs['models'].get(m,{}).get('p')) for m in MEMBERS):
            result['series'][key]={'status':'unavailable','complete_days':selected,'excluded_days':missing};continue
        newdays=[d for d in selected if d in docs]
        chunks=[np.array([docs[d]['series'][key]['models'][m]['p'] for m in MEMBERS]).T for d in newdays]
        labels=[docs[d]['series'][key]['actual'] for d in newdays]
        if prior:
            if key not in prior_inputs: raise ValueError('Parent fit inputs unavailable; cannot manufacture historical fit')
            chunks.insert(0,np.array(prior_inputs[key]['X'])); labels.insert(0,prior_inputs[key]['y'])
        X=np.concatenate(chunks); y=np.concatenate(labels)
        w,cert=fit(X,y); F=np.array([fs['models'][m]['p'] for m in MEMBERS]).T
        mae=np.mean(abs(X-y[:,None]),axis=0); best=min(range(len(MEMBERS)),key=lambda i:(mae[i],MEMBERS[i]))
        predictions={m:v['p'] for m,v in fs['models'].items() if finite(v.get('p'))}
        predictions.update(candidate=(F@w).tolist(),equal_mean=F.mean(axis=1).tolist(),equal_median=np.median(F,axis=1).tolist(),selected_incumbent=F[:,best].tolist())
        if prior and prior['series'][key]['status']=='available':
            predictions['frozen_parent']=(F@np.array(prior['series'][key]['weights'])).tolist()
            ordinary,_=fit(X.copy(),y.copy())
            predictions['equal_information_ordinary_refit']=(F@ordinary).tolist()
            if not np.allclose(ordinary,w,rtol=0,atol=1e-10): raise ValueError('Ordinary refit unexpectedly differs')
        result['series'][key]={'status':'available','weights':w.tolist(),'fit_certificate':cert,'training_member_mae':dict(zip(MEMBERS,mae.tolist())),'selected_incumbent':MEMBERS[best],'complete_days':selected,'excluded_days':missing,'predictions':predictions,'missing_published_models':[m for m,v in fs['models'].items() if not finite(v.get('p'))]}
        used[key]={'X':X.tolist(),'y':y.tolist(),'future_members':F.tolist()}
    result['measured_costs']={'elapsed_seconds':time.monotonic()-wall,'process_cpu_seconds':time.process_time()-cpu,'source_bytes':sum(m['bytes'] for m in manifest),'cash_spent':0,'complete_economic_cost':'unknown; underlying forecast production, support and qualification not valued'}
    out.mkdir(parents=True,exist_ok=True)
    (out/'forecast.json').write_text(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n')
    (out/'fit_inputs.json').write_text(json.dumps(used,separators=(',',':'),allow_nan=False)+'\n')
    print(json.dumps({'series':{k:v['status'] for k,v in result['series'].items()},'costs':result['measured_costs']},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshots',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--successor-from',type=Path);a=p.parse_args();construct(a.snapshots,a.out,a.successor_from)
