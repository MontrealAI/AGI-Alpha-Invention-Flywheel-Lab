"""Prospective completion of preregistered stale/wrong-reflector controls.
Not executed until source registered; never changes main evaluation or acceptance.
"""
import json
import numpy as np
from interface import calibrate,extend_phase,reflectors,reconstruct,focus,relative
from run import plant,aligned

def run():
 rows=[]
 for seed in (20261102,20261103,20261104):
  rng=np.random.default_rng(seed);n=8;rs=reflectors(n)
  t=plant(rng,n,3); obj=rng.normal(size=n)+1j*rng.normal(size=n)
  cs=[t.T@r@t for r in rs]
  k1=calibrate(cs[0],cs[1],rs[0],rs[1]); k2=extend_phase(k1,cs[2],rs[2])
  changed=plant(rng,n,3)
  stale_error=aligned(reconstruct(k2,changed.T@obj),obj)
  stale_focus=min(float(abs((changed@focus(k1,i))[i])**2/np.linalg.norm(changed[i])**2) for i in range(n))
  fresh_cs=[changed.T@r@changed for r in rs]
  fresh=extend_phase(calibrate(fresh_cs[0],fresh_cs[1],rs[0],rs[1]),fresh_cs[2],rs[2])
  # Fixed preregistered calibration-misspecification challenge. True reflectors
  # 1.21 times assumed reflectors remain passive but yield effective T_hat=1.1T.
  actual_rs=[1.21*r for r in rs]
  badcs=[t.T@r@t for r in actual_rs]
  wrong=extend_phase(calibrate(badcs[0],badcs[1],rs[0],rs[1]),badcs[2],rs[2])
  rows.append(dict(seed=seed,stale_field_error=stale_error,stale_min_target_efficiency=stale_focus,
    recalibrated_field_error=aligned(reconstruct(fresh,changed.T@obj),obj),
    wrong_reflector_field_error=aligned(reconstruct(wrong,t.T@obj),obj),
    wrong_reflector_residual=wrong.residual,
    max_actual_reflector_norm=max(float(np.linalg.norm(r,2)) for r in actual_rs)))
 return {'scope':'authored negative controls; no deployment validation','cases':rows}
if __name__=='__main__': print(json.dumps(run(),indent=2))
