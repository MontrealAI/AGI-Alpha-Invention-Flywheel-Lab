"""One prospectively registered local construction run; no economic booking."""
import hashlib,json,platform,random,time
from pathlib import Path
import numpy as np
from codec import (binary,binary_eval,hamming_masks,rs,lrc,rank,decoder,failures,apply,minimum_repairs)
ROOT=Path(__file__).resolve().parent

def rackify(p):return [p[:5],p[5:10],p[10:]]

def search():
    rng=random.Random(20261103); all_starts=[];best=None
    for start in range(24):
        masks=hamming_masks() if start==0 else [rng.randrange(1,256) for _ in range(6)]
        p=list(range(14));rng.shuffle(p);racks=rackify(p)
        score,bad,helpers,dist=binary_eval(masks,racks)
        for step in range(400):
            q=masks[:];v=p[:]
            if rng.random()<.35:
                i,j=rng.sample(range(14),2);v[i],v[j]=v[j],v[i]
            else:
                j=rng.randrange(6)
                if rng.random()<.2:q[j]=rng.randrange(1,256)
                else:q[j]^=1<<rng.randrange(8)
            new=binary_eval(q,rackify(v))
            # Fixed annealing only among same or improving feasibility levels.
            temperature=30*(1-step/400)
            accept=new[0]<=score or (new[1]==bad and rng.random()<np.exp(-(new[0]-score)/max(.01,temperature)))
            if accept:masks,p=q,v;score,bad,helpers,dist=new
            record=(score,tuple(masks),tuple(p),bad,tuple(helpers),dist)
            if best is None or record[:3]<best[:3]:best=record
        all_starts.append({'start':start,'final_bad':bad,'final_score':score,'final_helpers':helpers,'distance':dist})
    return best,all_starts

def placement(g, seed=20261103):
    rng=random.Random(seed); p=list(range(14));best=None;trials=0
    # Equal prospective 9600 placement proposals. Conventional formulas may seed known valid layout.
    candidates=[[0,1,4,8,12,2,5,6,9,13,3,7,10,11]]
    for _ in range(9599):
        q=p[:];rng.shuffle(q);candidates.append(q)
    for p in candidates:
        r=rackify(p);deficits=[8-rank([g[i] for i in range(14) if i not in rack]) for rack in r]
        item=(sum(deficits),tuple(p));trials+=1
        if best is None or item<best:best=item
    return rackify(list(best[1])),trials,best[0]

def benchmark(name,g,racks):
    t=time.perf_counter();f=failures(racks);plans=[decoder(g,x) for x in f]
    rejected=[list(x) for x,p in zip(f,plans) if p is None]
    helper,hpaths=minimum_repairs(g)
    byte_cases=0;byte_failures=0;h=hashlib.sha256();enc=rec=0.
    for seed in range(43001,43021):
        rng=np.random.default_rng(seed)
        for size in (1,17,1024):
            data=rng.integers(0,256,(8,size),dtype=np.uint8)
            a=time.perf_counter();stored=apply(g,data);enc+=time.perf_counter()-a
            for p in plans:
                if p is None:continue
                chosen,inv=p;a=time.perf_counter();restored=apply(inv,stored[chosen]);rec+=time.perf_counter()-a
                byte_cases+=1;byte_failures+=int(not np.array_equal(data,restored));h.update(restored.tobytes())
    fresh=[]
    for seed in range(92001,92021):
        p=list(range(14));random.Random(seed).shuffle(p);r=rackify(p)
        fresh.append({'seed':seed,'rack_ranks':[rank([g[i] for i in range(14) if i not in lost]) for lost in r]})
    # Successor: each worker computes a coded block's GF(2) matvec, then decode output blocks.
    successor={'scope':'different computational use; not autonomous discovery or commercial delivery','tested':False}
    if all(x in (0,1) for row in g for x in row) and not rejected:
        count=0;bad=0
        for seed in range(71001,71011):
            rng=np.random.default_rng(seed);blocks=rng.integers(0,2,(8,16,128),dtype=np.uint8);vec=rng.integers(0,2,128,dtype=np.uint8)
            original=(blocks.astype(np.uint32)@vec.astype(np.uint32)%2).astype(np.uint8)
            coded=apply(g,blocks.reshape(8,-1)).reshape(14,16,128)
            outputs=(coded.astype(np.uint32)@vec.astype(np.uint32)%2).astype(np.uint8)
            for chosen,inv in plans:
                got=apply(inv,outputs[chosen]);count+=1;bad+=int(not np.array_equal(got,original))
        successor.update(tested=True,cases=count,failures=bad,ordinary_direct_output_identical=True)
    return {'name':name,'generator':g,'racks':racks,'failures_registered':len(f),'rank_rejections':rejected,'single_repair_minimum_helpers':helper,'helper_witnesses':hpaths,'byte_cases':byte_cases,'byte_failures':byte_failures,'recovered_output_sha256':h.hexdigest(),'encode_seconds':enc,'recovery_seconds':rec,'total_seconds':time.perf_counter()-t,'fresh_placement':fresh,'successor':successor}

def main():
    started=time.time();tick=time.perf_counter();best,starts=search();search_s=time.perf_counter()-tick
    score,masks,p,bad,helpers,dist=best
    methods=[('synthesized_xor',binary(masks),rackify(list(p))),('reed_solomon',rs(),None),('conventional_lrc',lrc(),None),('extended_hamming',binary(hamming_masks()),None)]
    results=[];places=[]
    for name,g,r in methods:
        print('METHOD',name,flush=True)
        if r is None:
            t=time.perf_counter();r,n,deficit=placement(g);places.append({'name':name,'trials':n,'deficit':deficit,'seconds':time.perf_counter()-t})
        out=benchmark(name,g,r);results.append(out);print(name,'rank_rejections',len(out['rank_rejections']),'helpers',out['single_repair_minimum_helpers'],'bytes',out['byte_cases'],out['byte_failures'],flush=True)
    result={'schema':'superalpha083-v1','started_epoch':started,'elapsed_seconds':time.time()-started,'preregistered_commit':'3c1c57d5352e949513673d9b0f041e9933f60fe2','preregistration_sha256':hashlib.sha256((ROOT/'PREREGISTRATION.md').read_bytes()).hexdigest(),'python':platform.python_version(),'numpy':np.__version__,'candidate_masks':list(masks),'candidate_distance':dist,'candidate_contract_bad':bad,'candidate_search_seconds':search_s,'search_starts':starts,'placement_runs':places,'methods':results,'economics':{'actual_customers':0,'actual_revenue_usd':0,'native_account_opened':False,'native_profit_measured':False,'reference_capital_usd':100000,'profit_target_usd':3000000000,'target_window_days':365,'complete_cost_known':False,'economic_admission':'NOT_ESTABLISHED','frontier_model_api_calls':0,'real_spending':False},'claims':{'implemented_codec':all(m['byte_failures']==0 and not m['rank_rejections'] for m in results),'new_recovery_capability':False,'strongest_complete_alternative_beaten':False,'super_alpha_identified':False}}
    result['source_sha256']={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (ROOT/'codec.py',ROOT/'run.py')}
    (ROOT/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
    print('RESULT',ROOT/'RESULT.json',result['elapsed_seconds'],flush=True)
if __name__=='__main__':main()
