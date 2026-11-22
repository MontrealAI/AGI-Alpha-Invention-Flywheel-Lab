"""Post-original, prospectively disclosed stronger conventional controls."""
import hashlib,json,time
from itertools import combinations
from pathlib import Path
import numpy as np
from codec import inv,mul,systematic,rank,rref,inverse,apply,minimum_repairs
from run import benchmark,placement
ROOT=Path(__file__).resolve().parent

def unscaled():
    return systematic([[inv(i^(8+j)) for i in range(8)] for j in range(4)]+[[int(i<4) for i in range(8)],[int(i>=4) for i in range(8)]])

def uniform():
    c=[[inv(i^(8+j)) for i in range(8)] for j in range(5)]
    l0=[c[4][i] if i<6 else 0 for i in range(8)]
    l1=[]
    for i in range(8):
        x=c[4][i] if i>=6 else 0
        for j in range(4):x^=c[j][i]
        l1.append(x)
    return systematic(c[:4]+[l0,l1])

def pairlocal():
    return systematic([[int(i//2==j) for i in range(8)] for j in range(4)]+[[inv(i^(8+j)) for i in range(8)] for j in range(2)])

def plan(g,target,helpers):
    rows=[g[i] for i in helpers];_,piv=rref(rows)
    if len(piv)!=len(rows):raise ValueError('dependent minimum helpers')
    v=inverse([[r[p] for p in piv] for r in rows])
    weights=[]
    for j in range(len(rows)):
        x=0
        for i,p in enumerate(piv):x^=mul(g[target][p],v[i][j])
        weights.append(x)
    check=apply([weights],np.array(rows,dtype=np.uint8))[0].tolist()
    if check!=g[target]:raise ValueError('repair identity')
    return weights

def timed_repairs(m):
    g=m['generator'];plans=[]
    for i,h in enumerate(m['helper_witnesses']):plans.append(plan(g,i,h))
    count=bad=reads=0;sec=0.
    for seed in range(43001,43021):
        rng=np.random.default_rng(seed)
        for size in (1,17,1024):
            d=rng.integers(0,256,(8,size),dtype=np.uint8);coded=apply(g,d)
            for i,(helpers,w) in enumerate(zip(m['helper_witnesses'],plans)):
                t=time.perf_counter();y=apply([w],coded[helpers])[0];sec+=time.perf_counter()-t
                count+=1;bad+=int(not np.array_equal(y,coded[i]));reads+=len(helpers)*size
    return {'repair_cases':count,'failures':bad,'helper_bytes_read':reads,'seconds':sec,'weights':plans,'scope':'full-shard linear read metric, no network, partial repair or subpacketization benchmark'}

def main():
    original=json.loads((ROOT/'RESULT.json').read_text());out=[];new=[];timer=time.perf_counter()
    for name,g in [('unscaled_lrc',unscaled()),('uniform_cauchy_lrc',uniform()),('pair_local_lrc',pairlocal())]:
        print('SUPPLEMENT',name,flush=True);r,n,bad=placement(g);m=benchmark(name,g,r);new.append(m)
        print(name,m['single_repair_minimum_helpers'],len(m['rank_rejections']),flush=True)
    for m in original['methods']+new:
        g=m['generator'];profile={}
        for k in range(1,7):
            failed=0;total=0
            for lost in combinations(range(14),k):
                total+=1;failed+=int(rank([g[i] for i in range(14) if i not in lost])<8)
            profile[str(k)]={'tested':total,'unrecoverable':failed}
        rep=timed_repairs(m)
        out.append({'name':m['name'],'reliability_profile':profile,'minimum_read_repairs':rep})
        print('PROFILE',m['name'],profile,flush=True)
    result={'original_result_sha256':hashlib.sha256((ROOT/'RESULT.json').read_bytes()).hexdigest(),'supplement_registered_after_original':True,'new_controls':new,'comparisons':out,'elapsed_seconds':time.perf_counter()-timer,'source_sha256':hashlib.sha256((ROOT/'supplement.py').read_bytes()).hexdigest(),'new_activity_admitted':False,'super_alpha_identified':False}
    (ROOT/'SUPPLEMENT_RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
