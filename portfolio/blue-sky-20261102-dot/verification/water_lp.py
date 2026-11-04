"""Independent cyclic-stock linear program. Input is modeled hourly usable volume.
No water-quality, plant-counterfactual, or sub-hour service inference is made.
"""
import numpy as np
from scipy.optimize import linprog

def minimum_store(production,demand,allow_spill=False):
    p=np.asarray(production,dtype=float);d=np.broadcast_to(np.asarray(demand,dtype=float),p.shape)
    if p.ndim!=1 or not len(p) or not np.all(np.isfinite(p)) or not np.all(np.isfinite(d)) or np.any(p<0) or np.any(d<0):
        raise ValueError('finite nonnegative hourly volumes required')
    n=len(p);# variables S0..Sn, capacity, spill0..spill(n-1)
    cap=n+1;num=n+2+n; c=np.zeros(num);c[cap]=1
    eq=np.zeros((n,num));rhs=p-d
    for t in range(n):eq[t,t]=-1;eq[t,t+1]=1;eq[t,n+2+t]=1
    ub=np.zeros((n+2,num));br=np.zeros(n+2)
    for t in range(n+1):ub[t,t]=1;ub[t,cap]=-1
    ub[-1,0]=1;ub[-1,n]=-1 # terminal stock >= initial; no borrowing
    bounds=[(0,None)]*(n+2)+[(0,None if allow_spill else 0)]*n
    res=linprog(c,A_ub=ub,b_ub=br,A_eq=eq,b_eq=rhs,bounds=bounds,method='highs')
    if not res.success:return {'feasible':False,'solver_status':int(res.status),'message':res.message}
    x=res.x;s=x[:n+1];sp=x[n+2:]
    residual=float(np.max(np.abs(s[1:]-s[:-1]-p+d+sp)))
    return {'feasible':True,'capacity_l':float(x[cap]),'initial_l':float(s[0]),'terminal_l':float(s[-1]),'spill_l':float(sum(sp)),'max_balance_residual_l':residual,'stock_l':s.tolist(),'scope':'hourly end-of-interval stock; not continuous intrahour service or qualified water'}

# Independently prescribed structural fixtures, not empirical plant inputs.
FIXTURES={
 'no_water':([0]*24,[1]*24),
 'constant_exact':([1]*24,[1]*24),
 'daylight_only':([0]*6+[2]*12+[0]*6,[1]*24),
 'early_surplus':([4]*6+[0]*18,[1]*24),
 'insufficient':([.99]*24,[1]*24),
 'surplus_spill_sensitivity':([3]*12+[0]*12,[1]*24),
}
if __name__=='__main__':
    import json
    print(json.dumps({k:{str(s):minimum_store(p,d,s) for s in (False,True)} for k,(p,d) in FIXTURES.items()},indent=2))
