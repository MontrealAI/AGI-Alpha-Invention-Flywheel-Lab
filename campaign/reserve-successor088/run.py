"""Known robust reserve optimization; no account or commerce effects."""
import hashlib, heapq, itertools, json, math, time
from pathlib import Path
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
ROOT=Path(__file__).resolve().parent
DEPOTS=(117,233,309,397)
DEST=(87,165,253)
COST=(1200,1000,1100,900)

def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def read():
    raw=(ROOT/'Anaheim_net.tntp').read_bytes()
    edges=[]
    for line in raw.decode().splitlines():
        a=line.split()
        if a and a[0].isdigit():
            edges.append((int(a[0]),int(a[1]),float(a[4])))
    assert len(edges)==914 and max(max(e[:2]) for e in edges)==416
    assert len({e[:2] for e in edges})==len(edges)
    return edges, hashlib.sha256(raw).hexdigest()

def routes(edges,failed,source):
    adj={i:[] for i in range(1,417)}
    for i,(a,b,w) in enumerate(edges):
        if i!=failed: adj[a].append((b,w,i))
    d={source:0.}; p={}; q=[(0.,source)]
    while q:
        val,a=heapq.heappop(q)
        if val!=d[a]: continue
        if a<39 and a!=source: continue
        for b,w,i in adj[a]:
            nxt=val+w
            if nxt<d.get(b,math.inf):
                d[b]=nxt;p[b]=(a,i);heapq.heappush(q,(nxt,b))
    out=[]
    for target in DEST:
        path=[]; at=target
        if at in d:
            while at!=source:
                a,i=p[at];path.append(i);at=a
            path.reverse()
        out.append((d.get(target,math.inf),path))
    return out

def compile_reach(edges,deadline):
    start=time.process_time(); records=[]
    for failed in range(-1,len(edges)):
        rec=[]
        for source in DEPOTS:
            item=[]
            for target,(dist,path) in zip(DEST,routes(edges,failed,source)):
                # Separate path arithmetic check never trusts the distance label.
                if dist<=deadline:
                    at=source; total=0.
                    for ix in path:
                        assert ix!=failed
                        a,b,w=edges[ix];assert a==at
                        assert a>=39 or a==source
                        total+=w;at=b
                    assert at==target and abs(total-dist)<1e-8 and total<=deadline
                    item.append(True)
                else: item.append(False)
            rec.append(item)
        records.append(rec)
    return records,time.process_time()-start

def constraints(records,demand):
    # Hall: every subset's demand <= capacity of its union of neighboring depots.
    cuts=set()
    for rec in records:
        for mask in range(1,1<<len(demand)):
            rhs=sum(demand[j] for j in range(len(demand)) if mask>>j&1)
            bits=tuple(int(any(rec[i][j] and mask>>j&1 for j in range(len(demand)))) for i in range(4))
            cuts.add((bits,rhs))
    return sorted(cuts)

def exact(cuts,total):
    best=None; checked=0
    for x in itertools.product(range(total+1),repeat=4):
        checked+=1
        if all(sum(a*b for a,b in zip(row,x))>=rhs for row,rhs in cuts):
            val=sum(a*b for a,b in zip(COST,x))
            if best is None or (val,x)<best: best=(val,x)
    return best,checked

def conventional(cuts,total):
    a=np.array([r for r,b in cuts],dtype=float)
    b=np.array([b for r,b in cuts],dtype=float)
    res=milp(np.array(COST,dtype=float),integrality=np.ones(4),bounds=Bounds(np.zeros(4),np.full(4,total)),constraints=LinearConstraint(a,b,np.full(len(b),np.inf)),options={'mip_rel_gap':0.0})
    if res.status==2:return None
    assert res.success, res.message
    x=tuple(int(round(v)) for v in res.x)
    assert all(sum(q*v for q,v in zip(r,x))>=b for r,b in cuts)
    return sum(q*v for q,v in zip(COST,x)),x

def dispatch(rec,capacity,demand):
    # Independent finite assignment checker, not Hall inequalities or MILP.
    tasks=[j for j,n in enumerate(demand) for _ in range(n)]
    def solve(k,cap):
        if k==len(tasks):return []
        j=tasks[k]
        for i in range(4):
            if cap[i] and rec[i][j]:
                nxt=list(cap);nxt[i]-=1
                tail=solve(k+1,nxt)
                if tail is not None:return [(i,j)]+tail
        return None
    return solve(0,capacity)

def optimize(records,demand):
    start=time.process_time();cuts=constraints(records,demand)
    a,n=exact(cuts,sum(demand)); enum_cpu=time.process_time()-start
    start=time.process_time(); b=conventional(cuts,sum(demand)); milp_cpu=time.process_time()-start
    assert (a is None)==(b is None)
    if a:assert a[0]==b[0]
    accepted=0
    if a:
        for rec in records:
            assert dispatch(rec,a[1],demand) is not None
            assert dispatch(rec,b[1],demand) is not None
            accepted+=1
    return {'demand':demand,'cost':a[0] if a else None,'capacity':a[1] if a else None,'ordinary_cost':b[0] if b else None,'ordinary_capacity':b[1] if b else None,'accepted_scenarios':accepted,'unique_cuts':len(cuts),'enumerated_candidates':n,'enum_and_constraint_cpu_s':enum_cpu,'milp_cpu_s':milp_cpu}

def tests():
    # Unreachable beneficiary, double allocation, exact boundary, invalidation.
    rec=[[True,False,False],[False]*3,[False]*3,[False]*3]
    assert dispatch(rec,(1,0,0,0),(2,0,0)) is None
    assert dispatch(rec,(2,0,0,0),(2,0,0)) is not None
    assert exact(constraints([rec],(0,1,0)),1)[0] is None
    assert exact(constraints([rec],(1,0,0)),1)[0][0]==1200
    # Exhaustive Hall vs independent assignment over all 2x3 topologies/capacities.
    checks=0
    for bits in itertools.product((False,True),repeat=6):
        rr=[list(bits[:3]),list(bits[3:]),[False]*3,[False]*3]
        cc=constraints([rr],(1,1,1))
        for u,v in itertools.product(range(4),repeat=2):
            x=(u,v,0,0)
            lhs=all(sum(a*b for a,b in zip(row,x))>=rhs for row,rhs in cc)
            assert lhs==(dispatch(rr,x,(1,1,1)) is not None);checks+=1
    return {'exhaustive_hall_assignment_checks':checks,'double_allocation_and_unreachable_rejected':True}

def main():
    start=time.perf_counter();cpu=time.process_time();edges,source=read()
    out={'schema':'reserve088-v1','source_sha256':source,'protocol_sha256':hashlib.sha256((ROOT/'PROTOCOL.md').read_bytes()).hexdigest(),'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'tests':tests(),'cases':[],'native_profit':None,'actual_revenue':0,'all_unmeasured_lifecycle_costs':'unknown, not zero'}
    for deadline in (5,10,15):
        records,comp_cpu=compile_reach(edges,deadline)
        identity={'source':source,'deadline':deadline,'depots':DEPOTS,'destinations':DEST,'failure_model':'all individual directed links plus intact','zone_through_policy':39}
        instrument={'identity':identity,'content':records}
        instrument_id=digest(instrument)
        parent=optimize(records,(1,1,1))
        successor=optimize(records,(2,1,1))
        ordinary_reuse=optimize(json.loads(json.dumps(records)),(2,1,1))
        assert successor['cost']==ordinary_reuse['cost']
        cold,cold_cpu=compile_reach(edges,deadline)
        assert cold==records
        cold_successor=optimize(cold,(2,1,1))
        assert successor['cost']==cold_successor['cost']
        singles=[optimize(records,tuple(int(i==j) for i in range(3))) for j in range(3)]
        separate=None if any(x['cost'] is None for x in singles) else sum(x['cost'] for x in singles)
        room=None if separate is None or parent['cost'] is None else separate-parent['cost']
        changed=dict(identity,deadline=deadline+1)
        assert digest(changed)!=digest(identity)
        row={'deadline_minutes':deadline,'instrument_sha256':instrument_id,'compiled_cpu_s':comp_cpu,'cold_rebuild_cpu_s':cold_cpu,'parent':parent,'successor':successor,'equal_content_ordinary_reuse':ordinary_reuse,'cold_successor':cold_successor,'separate_reserve_cost':separate,'separate_participant_costs':[x['cost'] for x in singles],'max_extra_complete_cost_vs_separate':room,'extra_value_vs_equal_joint_competitor':0 if parent['cost'] is not None else None,'successor_superiority':False,'source_or_contract_change_invalidates':True}
        out['cases'].append(row)
        # Small retained executable instrument, not inherited authority.
        (ROOT/f'instrument-{deadline}.json').write_text(json.dumps(instrument,separators=(',',':'))+'\n')
    out['process_cpu_s']=time.process_time()-cpu;out['wall_s']=time.perf_counter()-start
    (ROOT/'RESULT.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))
if __name__=='__main__':main()
