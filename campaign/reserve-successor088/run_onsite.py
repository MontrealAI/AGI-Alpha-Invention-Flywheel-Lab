import itertools,json,time,hashlib
from pathlib import Path
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
import run_zone as zone
ROOT=Path(__file__).resolve().parent
COST=(1200,1000,1100,900,3000,3000,3000)
def cuts(records,demand):
    c=set()
    for rec in records:
        for mask in range(1,8):
            row=tuple(int(any(mask>>j&1 and rec[i][j] for j in range(3))) for i in range(7))
            c.add((row,sum(demand[j] for j in range(3) if mask>>j&1)))
    return sorted(c)
def assign(rec,cap,demand):
    tasks=[j for j,n in enumerate(demand) for _ in range(n)]
    def go(k,remain):
        if k==len(tasks):return []
        for i in range(7):
            if remain[i] and rec[i][tasks[k]]:
                c=list(remain);c[i]-=1;rest=go(k+1,c)
                if rest is not None:return [(i,tasks[k])]+rest
        return None
    return go(0,cap)
def solve(records,demand):
    start=time.process_time();cc=cuts(records,demand);total=sum(demand)
    # Lower bound each coordinate from singleton-support cuts; exhaustive over
    # remaining domain, with certified pruning by nonnegative objective.
    lower=[max([b for r,b in cc if r[i] and sum(r)==1]+[0]) for i in range(7)]
    best=None;count=0
    for x in itertools.product(*(range(k,total+1) for k in lower)):
        count+=1;v=sum(a*b for a,b in zip(COST,x))
        if best and v>=best[0]:continue
        if all(sum(a*b for a,b in zip(r,x))>=b for r,b in cc):best=(v,x)
    m=milp(np.array(COST,dtype=float),integrality=np.ones(7),bounds=Bounds(np.zeros(7),np.full(7,total)),constraints=LinearConstraint(np.array([r for r,b in cc]),np.array([b for r,b in cc]),np.full(len(cc),np.inf)),options={'mip_rel_gap':0.0})
    assert m.success and best is not None
    mx=tuple(int(round(x)) for x in m.x);mc=sum(a*b for a,b in zip(COST,mx));assert mc==best[0]
    for rec in records:
        assert assign(rec,best[1],demand) is not None
        assert assign(rec,mx,demand) is not None
    return {'cost':best[0],'capacities':best[1],'conventional_cost':mc,'conventional_capacities':mx,'all_scenarios_accepted':len(records),'enumerated_candidates':count,'coordinate_lower_bounds':lower,'total_comparison_cpu_s':time.process_time()-start}
def main():
    start=time.process_time();out=[];edges,source=zone.base.read()
    for deadline in (5,10,15):
        remote,failures=zone.compile_roads(edges,deadline)
        # Every onsite route is the explicit empty path from a zone to itself.
        records=[rec+[[i==j for j in range(3)] for i in range(3)] for rec in remote]
        a=solve(records,(1,1,1));b=solve(records,(2,1,1));ordinary=solve(json.loads(json.dumps(records)),(2,1,1))
        assert b['cost']==ordinary['cost']
        out.append({'deadline':deadline,'parent':a,'successor':b,'ordinary_equal_content_successor':ordinary,'incremental_slot_cost':b['cost']-a['cost'],'supplied_by_100k_seed_on_slot_cost_only':b['cost']<=100000,'causally_enabled_by_parent_vs_ordinary':False,'seller_margin_vs_identical_conventional_outside_option':0})
    result={'schema':'reserve088-onsite-v1','source_sha256':source,'protocol_sha256':hashlib.sha256((ROOT/'ONSITE_PROTOCOL.md').read_bytes()).hexdigest(),'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'cases':out,'process_cpu_s':time.process_time()-start,'full_cost_profit':None,'native_transactions':0,'claim':'Known prepositioning removes the modeled access-cut dependency; strong conventional provision ties. No commercial or novel-successor advantage demonstrated.'}
    (ROOT/'ONSITE_RESULT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
