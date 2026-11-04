"""Finite registered engineering-model evaluation; contains authored truth generator.
Constructor interface.py is passed observations only. Shared process/files are not
security-isolated hidden truth. No physical-validation or population claim.
"""
import argparse, hashlib, json, time
from pathlib import Path
import numpy as np
from interface import reflectors,calibrate,extend_phase,focus,reconstruct,relative


def unitary(rng,n):
    z=rng.normal(size=(n,n))+1j*rng.normal(size=(n,n))
    q,r=np.linalg.qr(z)
    return q @ np.diag(np.diag(r)/abs(np.diag(r)))


def plant(rng,n,condition):
    return unitary(rng,n)@np.diag(np.geomspace(.9,.9/condition,n))@unitary(rng,n)


def noise(rng,a,amount):
    e=rng.normal(size=a.shape)+1j*rng.normal(size=a.shape)
    return a+amount*np.linalg.norm(a)*e/np.linalg.norm(e)


def aligned(a,b):
    return min(relative(a,b),relative(-a,b))


def main(out):
    out=Path(out)
    if out.exists(): raise ValueError('refuse overwrite')
    out.mkdir(parents=True)
    start=time.perf_counter()
    results=[]
    for seed in (20261102,20261103,20261104):
      rng=np.random.default_rng(seed)
      for n in (4,8,16):
       rs=reflectors(n)
       for cond in (1,3,10):
        t=plant(rng,n,cond)
        obj=rng.normal(size=n)+1j*rng.normal(size=n)
        cs=[t.T@r@t for r in rs]
        for kind,levels in [('noise',(0,1e-6,1e-4,1e-2)),('drift',(1e-6,1e-3,.05))]:
         for level in levels:
          record=dict(seed=seed,n=n,condition=cond,challenge=kind,level=level)
          if kind=='noise':
           obs=[noise(rng,c,level) for c in cs]
          else:
           shifted=[t,noise(rng,t,level),noise(rng,t,level)]
           obs=[v.T@r@v for v,r in zip(shifted,rs)]
          try:
           k1=calibrate(obs[0],obs[1],rs[0],rs[1])
           k1bytes=k1.operator.tobytes()
           record['frozen_k1_sha256']=hashlib.sha256(k1bytes).hexdigest()
           record['k1_min_target_efficiency']=min(float(abs((t@focus(k1,i))[i])**2/np.linalg.norm(t[i])**2) for i in range(n))
           record['uncalibrated_min_target_efficiency']=min(float(abs(t[i,i])**2/np.linalg.norm(t[i])**2) for i in range(n))
           k2=extend_phase(k1,obs[2],rs[2])
           assert k1.operator.tobytes()==k1bytes
           recovered=reconstruct(k2,t.T@obj)
           record['k2_relative_error']=aligned(recovered,obj)
           fresh=extend_phase(calibrate(obs[0],obs[1],rs[0],rs[1]),obs[2],rs[2])
           record['fresh_reuse_operator_gap']=relative(fresh.operator,k2.operator)
           record['direct_distal_error']=relative(np.linalg.solve(t.T,t.T@obj),obj)
           record['residual']=k2.residual
           record['status']='returned'
          except (ValueError,np.linalg.LinAlgError) as e:
           record['status']='abstain';record['reason']=str(e)
          results.append(record)
    exact=[r for r in results if r['challenge']=='noise' and r['level']==0]
    summary={'scope':'authored reciprocal linear optics model; no physical measurement',
      'cases':len(results),'exact_cases':len(exact),
      'exact_passes':sum(r['status']=='returned' and r['k1_min_target_efficiency']>=1-1e-8 and r['k2_relative_error']<=1e-7 for r in exact),
      'elapsed_seconds':time.perf_counter()-start,
      'constructor_sha256':hashlib.sha256(Path(__file__).with_name('interface.py').read_bytes()).hexdigest(),
      'prereg_sha256':hashlib.sha256(Path(__file__).with_name('PREREG.md').read_bytes()).hexdigest(),
      'probe_columns':{'k1':'2n','k2_incremental':'n','complete_lifecycle':'3n','fresh_k2':'3n','ordinary_equal_content_reuse':'3n'},
      'new_cash_spend_usd':0,'actual_included_resource_billing':'unknown','physical_costs':'unpriced; no commercial qualification'}
    (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();main(a.out)
