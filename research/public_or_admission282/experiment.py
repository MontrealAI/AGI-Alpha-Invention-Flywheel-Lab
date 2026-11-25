"""Public benchmark research only. No competition entry, model calls or financial actions."""
import argparse, hashlib, json, os, platform, time
from collections import defaultdict, deque, Counter
from pathlib import Path
import numpy as np
import scipy
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix

def reachable(start, edges):
    adj=defaultdict(list)
    for a,b in edges: adj[a].append(b)
    seen={start}; todo=deque([start])
    while todo:
        for b in adj[todo.popleft()]:
            if b not in seen: seen.add(b); todo.append(b)
    return seen

def solve(d, reduced):
    nodes=d['network']['nodes']; arcs=d['network']['arcs']; cs=d['commodities']['commodity_list']
    assert len(nodes)==len(set(nodes))==d['network']['num_nodes']
    assert len(arcs)==len({a['arc_id'] for a in arcs})==d['network']['num_arcs']
    assert len(cs)==len({k['commodity_id'] for k in cs})==d['commodities']['num_commodities']
    assert all(a['cost']>=0 and a['capacity']>=0 and a['from_node'] in nodes and a['to_node'] in nodes for a in arcs)
    assert all(k['demand']>0 and k['artificial_arc_cost']>=0 and k['origin']!=k['destination'] and k['origin'] in nodes and k['destination'] in nodes for k in cs)
    index={n:i for i,n in enumerate(nodes)}; n=len(nodes); m=len(arcs); K=len(cs)
    rows=[]; cols=[]; vals=[]; costs=[]; variables=[]
    lo=np.zeros(K*n+m); hi=np.zeros(K*n+m)
    lo[K*n:]=-np.inf; hi[K*n:]=[a['capacity'] for a in arcs]
    def add(row,col,val):
        rows.append(row); cols.append(col); vals.append(val)
    for i,k in enumerate(cs):
        o,t,q=k['origin'],k['destination'],k['demand']
        lo[i*n+index[o]]=hi[i*n+index[o]]=1
        lo[i*n+index[t]]=hi[i*n+index[t]]=-1
        eligible=[j for j,a in enumerate(arcs) if a['capacity']>=q]
        forward=reachable(o,[(arcs[j]['from_node'],arcs[j]['to_node']) for j in eligible])
        backward=reachable(t,[(arcs[j]['to_node'],arcs[j]['from_node']) for j in eligible])
        allowed=[j for j in eligible if arcs[j]['from_node'] in forward and arcs[j]['to_node'] in backward] if reduced else range(m)
        for j in allowed:
            a=arcs[j]; col=len(costs); costs.append(q*a['cost']); variables.append((i,j))
            add(i*n+index[a['from_node']],col,1)
            add(i*n+index[a['to_node']],col,-1)
            add(K*n+j,col,q)
        col=len(costs); costs.append(q*k['artificial_arc_cost']); variables.append((i,-1))
        add(i*n+index[o],col,1); add(i*n+index[t],col,-1)
    A=coo_matrix((vals,(rows,cols)),shape=(len(lo),len(costs))).tocsc()
    result=milp(np.asarray(costs,dtype=float),integrality=np.ones(len(costs)),bounds=Bounds(0,1),constraints=LinearConstraint(A,lo,hi),options={'time_limit':45.0,'mip_rel_gap':0.0,'threads':1})
    if result.x is None:
        return {'status':int(result.status),'message':str(result.message),'variables':len(costs),'solution':None}
    assert np.max(np.abs(result.x-np.round(result.x)))<1e-5
    chosen=defaultdict(list)
    for (i,j),v in zip(variables,result.x):
        if v>0.5: chosen[i].append(j)
    records=[]; objective=0
    for i,k in enumerate(cs):
        if -1 in chosen[i]:
            records.append({'commodity_id':k['commodity_id'],'rejected':True,'path_arcs':[]})
            objective+=k['demand']*k['artificial_arc_cost']; continue
        adj=defaultdict(list)
        for j in chosen[i]: adj[arcs[j]['from_node']].append(j)
        o,t=k['origin'],k['destination']; parent={o:None}; todo=deque([o])
        while todo and t not in parent:
            for j in adj[todo.popleft()]:
                v=arcs[j]['to_node']
                if v not in parent: parent[v]=j; todo.append(v)
        assert t in parent
        path=[]; v=t
        while v!=o:
            j=parent[v]; path.append(j); v=arcs[j]['from_node']
        path.reverse()
        records.append({'commodity_id':k['commodity_id'],'rejected':False,'path_arcs':[{'arc_id':arcs[j]['arc_id'],'from':arcs[j]['from_node'],'to':arcs[j]['to_node']} for j in path]})
        objective+=k['demand']*sum(arcs[j]['cost'] for j in path)
    if result.status==0: assert abs(objective-result.fun)<1e-4
    return {'status':int(result.status),'message':str(result.message),'variables':len(costs),'solver_objective':float(result.fun),'gap':float(result.mip_gap) if result.mip_gap is not None else None,'bound':float(result.mip_dual_bound) if result.mip_dual_bound is not None else None,'solution':{'objective_value':objective,'commodities':records}}

def verify(d,s):
    """Check actual witness without using compiled matrices or solver state."""
    arcs={a['arc_id']:a for a in d['network']['arcs']}
    cs={k['commodity_id']:k for k in d['commodities']['commodity_list']}
    assert Counter(x['commodity_id'] for x in s['commodities'])==Counter(cs.keys())
    used=Counter(); total=0
    for rec in s['commodities']:
        k=cs[rec['commodity_id']]; q=k['demand']; path=rec['path_arcs']
        assert type(rec['rejected']) is bool
        if rec['rejected']:
            assert not path; total+=q*k['artificial_arc_cost']; continue
        assert path
        v=k['origin']; seen={v}
        for p in path:
            a=arcs[p['arc_id']]
            assert p['from']==a['from_node']==v and p['to']==a['to_node']
            v=p['to']; assert v not in seen; seen.add(v)
            used[p['arc_id']]+=q; total+=q*a['cost']
        assert v==k['destination']
    assert all(q<=arcs[j]['capacity'] for j,q in used.items())
    assert total==s['objective_value']
    return total

def main():
    p=argparse.ArgumentParser(); p.add_argument('inputs',type=Path); p.add_argument('output',type=Path)
    a=p.parse_args(); a.output.mkdir(exist_ok=False)
    names=['tiny_instance.json']+[f'large_instance_{i}.json' for i in range(1,6)]
    receipt={'scope':'public benchmark engineering only','python':platform.python_version(),'scipy':scipy.__version__,'numpy':np.__version__,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'dataset_revision':'805df12577ba64fae37a472dd5ce24393b7df5e0','rows':[],'actual_billing':None}
    for name in names:
        for mode in ['full','reduced']:
            start=time.perf_counter(); cpu=time.process_time()
            row={'instance':name,'arm':mode,'valid':False}
            try:
                raw=(a.inputs/name).read_bytes(); row['input_sha256']=hashlib.sha256(raw).hexdigest(); d=json.loads(raw)
                row.update(solve(d,mode=='reduced')); s=row.pop('solution')
                if s is not None:
                    row['verified_objective']=verify(d,s); row['valid']=True
                    path=a.output/(name+'.'+mode+'.solution.json'); path.write_text(json.dumps(s,sort_keys=True))
                    row['solution_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            except Exception as e: row['error']=type(e).__name__+': '+str(e)
            row['wall_s']=time.perf_counter()-start; row['cpu_s']=time.process_time()-cpu
            receipt['rows'].append(row)
            (a.output/'RESULT.json').write_text(json.dumps(receipt,indent=2,allow_nan=False))
    pairs=list(zip(receipt['rows'][::2],receipt['rows'][1::2]))
    receipt['accepted']=all(x['valid'] and x['wall_s']<=60 for x in receipt['rows']) and all(y['variables']<=x['variables'] and not(x['status']==y['status']==0 and x['verified_objective']!=y['verified_objective']) for x,y in pairs)
    receipt['advantage']=receipt['accepted'] and all(y['verified_objective']<=x['verified_objective'] for x,y in pairs) and all(y['wall_s']<x['wall_s'] for x,y in pairs[1:])
    (a.output/'RESULT.json').write_text(json.dumps(receipt,indent=2,allow_nan=False))
    print(json.dumps(receipt,indent=2,allow_nan=False))
    return 0 if receipt['accepted'] else 1
if __name__=='__main__': raise SystemExit(main())
