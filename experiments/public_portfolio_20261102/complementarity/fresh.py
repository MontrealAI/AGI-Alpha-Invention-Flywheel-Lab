import math
import time

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix


def solve_fresh(case):
    n=len(case["demand_kw"])
    dt=case["dt_h"]
    hot=case["sink_c"]+case["approach_c"]+273.15
    cops=np.array([case["carnot_fraction"]*hot/(hot-(v-case["approach_c"]+273.15)) for v in case["source_c"]])
    if any(not math.isfinite(v) or v<=1 for v in cops):
        raise ValueError("COP")
    objective=np.zeros(5*n)
    objective[:n]=np.array(case["electricity_usd_kwh"])*dt/cops
    objective[n:2*n]=np.array(case["electricity_usd_kwh"])*dt
    objective[2*n:4*n]=1e-10*dt
    aeq=lil_matrix((2*n,5*n))
    beq=np.zeros(2*n)
    for t in range(n):
        aeq[t,t],aeq[t,n+t],aeq[t,2*n+t],aeq[t,3*n+t]=1,1,-1,1
        beq[t]=case["demand_kw"][t]
        aeq[n+t,4*n+t]=1
        if t:
            aeq[n+t,4*n+t-1]=-case["hourly_retention"]**dt
        aeq[n+t,2*n+t]=-dt*case["charge_efficiency"]
        aeq[n+t,3*n+t]=dt/case["discharge_efficiency"]
    aub=lil_matrix((n,5*n))
    for t in range(n):
        aub[t,t],aub[t,n+t]=1/cops[t],1
    bounds=[(0,min(case["hp_heat_limit_kw"],case["source_kw"][t]/(1-1/cops[t]))) for t in range(n)]
    bounds += [(0,case["grid_limit_kw"])]*n
    bounds += [(0,case["store_power_kw"])]*(2*n)
    bounds += [(0,case["store_kwh"])]*n
    bounds[-1]=(0,0)
    started,cpu=time.perf_counter(),time.process_time()
    answer=linprog(objective,A_ub=aub.tocsr(),b_ub=[case["grid_limit_kw"]]*n,A_eq=aeq.tocsr(),b_eq=beq,bounds=bounds,method="highs-ds")
    out={"schema":"thermal-result/v1","case":case["name"],"feasible":bool(answer.success),"solver_status":int(answer.status),"solver_message":answer.message,"method":"separate-fresh-thermal-output-formulation/highs-ds","use_heat_pump":True,"use_storage":True,"cpu_seconds":time.process_time()-cpu,"wall_seconds":time.perf_counter()-started}
    if answer.success:
        x=answer.x
        p=x[:n]/cops
        out.update({"hp_electric_kw":p.tolist(),"boiler_electric_kw":x[n:2*n].tolist(),"charge_kw":x[2*n:3*n].tolist(),"discharge_kw":x[3*n:4*n].tolist(),"soc_kwh":[0.0]+x[4*n:].tolist(),"electric_kwh":float(sum(p+x[n:2*n])*dt),"electricity_cost_usd":float(np.dot(p+x[n:2*n],case["electricity_usd_kwh"])*dt),"source_heat_kwh":float(np.dot(cops-1,p)*dt)})
    return out
