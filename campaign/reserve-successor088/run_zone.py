"""Separate corrected-zone study; never modifies original outcomes."""
import copy,hashlib,itertools,json,time
from pathlib import Path
import numpy as np
from scipy.optimize import linprog
import run as base
ROOT=Path(__file__).resolve().parent
base.DEPOTS=(1,4,11,20);base.DEST=(2,5,7)

def load_instrument(path,expected):
    v=json.loads(path.read_text())
    if v['identity']!=expected or base.digest(v['content'])!=v['content_sha256']:
        raise ValueError('instrument identity or content mismatch')
    return v['content']

def compile_roads(edges,deadline):
    records=[]
    failures=[-1]+[i for i,(a,b,w) in enumerate(edges) if a>=39 and b>=39]
    for failed in failures:
        rec=[]
        for source in base.DEPOTS:
            item=[]
            for target,(dist,path) in zip(base.DEST,base.routes(edges,failed,source)):
                if dist<=deadline:
                    total=0.;at=source
                    for ix in path:
                        assert ix!=failed
                        a,b,w=edges[ix];assert a==at and (a>=39 or a==source)
                        total+=w;at=b
                    assert at==target and abs(total-dist)<1e-8 and total<=deadline
                item.append(dist<=deadline)
            rec.append(item)
        records.append(rec)
    return records,failures

def economics(records,parent):
    coalitions=[]
    for mask in range(1,8):
        demand=tuple(int(mask>>j&1) for j in range(3))
        cost=base.exact(base.constraints(records,demand),sum(demand))[0]
        coalitions.append((mask,cost[0] if cost else None))
    standalone=[c for m,c in coalitions if m in (1,2,4)]
    out={'coalition_costs':coalitions,'standalone_costs':standalone,'allocation_cases':[]}
    if parent['cost'] is None or any(x is None for x in standalone):return out
    for overhead in (0,500):
        A=[];b=[]
        for mask,cost in coalitions:
            if cost is not None:
                A.append([int(mask>>j&1) for j in range(3)]);b.append(cost)
        sol=linprog(np.zeros(3),A_ub=np.array(A),b_ub=np.array(b),A_eq=np.ones((1,3)),b_eq=[parent['cost']+overhead],bounds=[(0,None)]*3,method='highs')
        payments=[float(x) for x in sol.x] if sol.success else None
        if payments:
            assert abs(sum(payments)-parent['cost']-overhead)<1e-6
            for mask,cost in coalitions:
                if cost is not None:assert sum(payments[j] for j in range(3) if mask>>j&1)<=cost+1e-6
        out['allocation_cases'].append({'extra_overhead':overhead,'coalition_stable':bool(sol.success),'payments':payments})
    out['max_overhead_vs_standalone']=sum(standalone)-parent['cost']
    out['max_overhead_vs_equal_joint_competitor']=0
    return out

def main():
    start=time.perf_counter();cpu=time.process_time();edges,source=base.read();cases=[]
    for deadline in (5,10,15):
        c=time.process_time();records,failures=compile_roads(edges,deadline);compiled=time.process_time()-c
        identity={'source':source,'deadline':deadline,'depots':list(base.DEPOTS),'destinations':list(base.DEST),'failures':failures,'first_through':39,'units':'minutes'}
        p=ROOT/f'zone-instrument-{deadline}.json'
        p.write_text(json.dumps({'identity':identity,'content':records,'content_sha256':base.digest(records)},separators=(',',':'))+'\n')
        loaded=load_instrument(p,identity)
        altered=copy.deepcopy(identity);altered['destinations'][0]=3
        try:load_instrument(p,altered)
        except ValueError:pass
        else:raise AssertionError('stale identity accepted')
        # Validate mutation rejection in a separate file; preserve primary instrument.
        v=json.loads(p.read_text());v['content'][0][0][0]=not v['content'][0][0][0]
        tamper=ROOT/'tamper-test.json';tamper.write_text(json.dumps(v))
        try:load_instrument(tamper,identity)
        except ValueError:pass
        else:raise AssertionError('forged content accepted')
        parent=base.optimize(loaded,(1,1,1));successor=base.optimize(loaded,(2,1,1))
        ordinary=base.optimize(json.loads(json.dumps(loaded)),(2,1,1))
        c=time.process_time();cold,cf=compile_roads(edges,deadline);cold_cpu=time.process_time()-c
        assert cf==failures and cold==loaded
        fresh=base.optimize(cold,(2,1,1))
        assert successor['cost']==ordinary['cost']==fresh['cost']
        cases.append({'deadline':deadline,'scenario_count':len(failures),'compiled_cpu_s':compiled,'cold_compiled_cpu_s':cold_cpu,'parent':parent,'successor':successor,'ordinary_reuse':ordinary,'cold':fresh,'economics':economics(loaded,parent),'stale_and_tampered_cache_rejected':True})
    result={'schema':'reserve088-zone-v1','source_sha256':source,'protocol_sha256':hashlib.sha256((ROOT/'ZONE_PROTOCOL.md').read_bytes()).hexdigest(),'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'base_runner_sha256':hashlib.sha256((ROOT/'run.py').read_bytes()).hexdigest(),'cases':cases,'process_cpu_s':time.process_time()-cpu,'wall_s':time.perf_counter()-start,'native_profit':None,'real_transactions':0,'commercial_superiority':False,'successor_enabling_vs_strong_ordinary_reuse':False,'unknown_costs':'All non-slot lifecycle costs; no full-cost profit claim'}
    (ROOT/'ZONE_RESULT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
