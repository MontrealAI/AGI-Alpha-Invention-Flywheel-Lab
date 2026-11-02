"""Independent finite replay; run only after public preregistration receipt."""
import importlib.util, json, sys
from pathlib import Path
import numpy as np
from scipy.linalg import eig
from interface_checks import checks, relative

def run(path):
    spec=importlib.util.spec_from_file_location('candidate',path)
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
    results=[]
    for seed in (20261102,20261103,20261104):
      rng=np.random.default_rng(seed)
      for n in (4,8,16):
       for cond in (1,3,10):
        unitary=lambda:np.linalg.qr(rng.normal(size=(n,n))+1j*rng.normal(size=(n,n)))[0]
        T=unitary()@np.diag(np.geomspace(.8,.8/cond,n))@unitary()
        r0,r1,r2=m.reflectors(n); cs=[T.T@r@T for r in (r0,r1,r2)]
        k1=m.calibrate(cs[0],cs[1],r0,r1)
        ratios=[]
        for i in range(n):
            x=m.focus(k1,i)
            assert abs(np.linalg.norm(x)-1)<1e-10
            ratios.append(float(abs((T@x)[i])**2/np.linalg.norm(T[i,:])**2))
        k2=m.extend_phase(k1,cs[2],r2)
        obj=rng.normal(size=n)+1j*rng.normal(size=n)
        rec=m.reconstruct(k2,T.T@obj)
        err=min(relative(rec,obj),relative(-rec,obj))
        # Separate generalized eigenvalue implementation checks spectrum,
        # not physical validity; it does not call candidate inversion pipeline.
        ev=eig(cs[1],cs[0],right=False)
        eigerr=float(np.max(abs(np.sort_complex(ev)-np.sort_complex(np.diag(r1)/.3))))
        passed=min(ratios)>=1-1e-8 and err<=1e-7 and eigerr<1e-8
        results.append(dict(seed=seed,n=n,condition=cond,min_focus_ratio=min(ratios),phase_error=err,generalized_eigenvalue_error=eigerr,passed=bool(passed)))
    # Independent invalid-input challenges: these require rejection, not NaN output.
    rejects={}
    T=np.diag([.2,.3,.5,.7]);r0,r1,r2=m.reflectors(4);c0=T.T@r0@T;c1=T.T@r1@T;c2=T.T@r2@T
    k1=m.calibrate(c0,c1,r0,r1);k2=m.extend_phase(k1,c2,r2)
    calls={'nan_c2':lambda:m.extend_phase(k1,np.full((4,4),np.nan),r2),
           'infinite_field':lambda:m.reconstruct(k2,np.full(4,np.inf)),
           'rank_deficient':lambda:m.calibrate(np.zeros((4,4)),c1,r0,r1),
           'repeated_spectrum':lambda:m.calibrate(c0,c1,r0,r0),
           'disconnected':lambda:m.extend_phase(k1,T.T@r0@T,r0),
           'k1_only_phase':lambda:m.reconstruct(k1,np.ones(4))}
    for name,fn in calls.items():
        try:fn();rejects[name]=False
        except (ValueError,np.linalg.LinAlgError):rejects[name]=True
    return {'analytic_obligations':checks(),'noiseless_cases':results,'invalid_input_rejections':rejects,'pass':all(x['passed'] for x in results) and all(rejects.values()),'scope':'27 authored deterministic exact-model cases plus analytic and invalid-input checks; no physical or economic qualification.'}
if __name__=='__main__':
    print(json.dumps(run(sys.argv[1]),indent=2))
