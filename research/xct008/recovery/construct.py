"""Ordinary direct and preconditioned-PDHG full120 feasibility construction.

Recovery edition. No angle search, dual-optimality or novelty claim.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import argparse,hashlib,json,pathlib,resource,time
import numpy as np
import scipy.sparse as sp
from scipy.io import loadmat
from exact_feasibility import BITS,SCALE,scaled,exact_rows,exact_dot,lower_float,check

ROOT=pathlib.Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,obj):p.write_text(json.dumps(obj,indent=2)+'\n')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=pathlib.Path,required=True);args=parser.parse_args()
    start=time.monotonic();resource.setrlimit(resource.RLIMIT_CPU,(700,705));resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30));resource.setrlimit(resource.RLIMIT_FSIZE,(64<<20,64<<20))
    out=args.output;out.mkdir(exist_ok=False)
    protocol=json.loads((ROOT/'PROTOCOL.json').read_text());model=ROOT/'model'
    for name,digest in protocol['frozen_files'].items():
        if sha(ROOT/name)!=digest:raise ValueError('changed frozen input: '+name)
    dump(out/'FREEZE.json',{'source_sha256':sha(pathlib.Path(__file__)),'helper_sha256':sha(ROOT/'exact_feasibility.py'),'protocol_sha256':sha(ROOT/'PROTOCOL.json'),'frozen_files':protocol['frozen_files'],'edition':protocol['edition']})
    d=loadmat(ROOT/'data/Data82.mat');A=d['A'].tocsr();AT=A.T.tocsr();y=d['m'].reshape(-1,order='F')
    reference=np.load(model/'reference.npy',allow_pickle=False);eps=np.tile(np.load(model/'eps.npy',allow_pickle=False),120);c=np.load(model/'objective.npy',allow_pickle=False)
    if A.shape!=(9840,6724) or A.nnz!=970344 or np.min(A.data)<0:raise ValueError('unexpected matrix')
    for name,array in [('reference',reference),('eps_full',eps),('objective',c)]:np.save(out/f'{name}.npy',array,allow_pickle=False)
    refcheck,refrows=check(A,y,eps,reference,c);dump(out/'REFERENCE_CHECK.json',refcheck)
    if not refcheck['feasible']:raise ValueError('reconstructed reference is not exact-model feasible')
    result={'edition':protocol['edition'],'scope':'EXPOSED_DEVELOPMENT_NEW_RECOVERY_EDITION','control':{},'pdhg':{},'status':'RUNNING'}
    direction=(c!=0).astype(float);direction_rows=exact_rows(A,direction)
    def direct(sign):
        cap=[]
        for v,rr,dd,e in zip(y,refrows,direction_rows,eps):
            if dd>0:cap.append(lower_float(scaled(e)+sign*(scaled(v)-rr),dd))
        if sign<0:cap.append(float(np.min(reference[c!=0])))
        step=max(0,min(cap))*.999999
        x=reference+sign*step*direction
        info,_=check(A,y,eps,x,c);info['step']=step
        np.save(out/f'direct_{"lo" if sign<0 else "hi"}.npy',x,allow_pickle=False)
        return info
    for sign,label in [(-1,'lo'),(1,'hi')]:result['control'][label]=direct(sign);dump(out/'RESULTS.json',result)
    result['control']['gap_float_lower']=lower_float(int(result['control']['hi']['roi_numerator'])-int(result['control']['lo']['roi_numerator']),SCALE)
    reference_roi=float(c@reference)
    K=sp.vstack([A,sp.csr_matrix((100*c).reshape(1,-1))],format='csr');KT=K.T.tocsr()
    tau=.9/np.maximum(np.asarray(abs(K).sum(axis=0)).ravel(),1e-12)
    sigma=.9/np.maximum(np.asarray(abs(K).sum(axis=1)).ravel(),1e-12)
    raymargin=np.min(eps-np.abs(A@reference-y));tighten=min(1e-7,float(raymargin)/10)
    for sign,label in [(-1,'lo'),(1,'hi')]:
        target=reference_roi+sign*.003
        lower=np.r_[y-eps+tighten,100*target];upper=np.r_[y+eps-tighten,100*target]
        x=reference.copy();bar=x.copy();dual=np.zeros(K.shape[0]);trace=[];t=time.monotonic();ct=time.process_time()
        for iteration in range(1,32001):
            dual+=sigma*(K@bar)
            dual-=sigma*np.clip(dual/sigma,lower,upper)
            new=np.maximum(0,(x-tau*(KT@dual)+tau*reference)/(1+tau))
            bar=2*new-x;x=new
            if iteration%100==0:
                violation=float(np.max(np.abs(A@x-y)-eps));error=float(abs(c@x-target))
                if iteration%1000==0:trace.append({'iteration':iteration,'max_ray_excess':violation,'roi_target_error':error,'cpu_seconds':time.process_time()-ct})
                if violation<=-tighten/2 and error<=1e-8:break
                if time.process_time()-ct>240:break
        np.save(out/f'pdhg_{label}.npy',x,allow_pickle=False)
        info,_=check(A,y,eps,x,c)
        info.update(target=target,iterations=iteration,trace=trace,wall_seconds=time.monotonic()-t,cpu_seconds=time.process_time()-ct,tighten=tighten)
        result['pdhg'][label]=info;dump(out/f'PDHG_{label}.json',info);dump(out/'RESULTS.json',result)
    gap=int(result['pdhg']['hi']['roi_numerator'])-int(result['pdhg']['lo']['roi_numerator'])
    both=all(result['pdhg'][label]['feasible'] for label in ['lo','hi'])
    result['pdhg']['gap_float_lower']=lower_float(gap,SCALE)
    result['pdhg']['exact_gap_exceeds_1_over_200']=bool(gap*200>SCALE)
    result['status']='FULL120_PAIR_OBSTRUCTION' if both and gap*200>SCALE else 'UNKNOWN_NO_ACCEPTED_OBSTRUCTION'
    result['resources']={'cpu_seconds':time.process_time(),'wall_seconds':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    result['limits']=['New reconstructed calibration bytes; not exact historical source replay.','Full120 and1200-view reference exposed; not protected confirmation.','Both routes are ordinary methods available equally; no novelty or technical advantage established.','Closed binary64 model only; no physical feasibility, industrial feature or commercial claim.']
    dump(out/'RESULTS.json',result);print(json.dumps(result))
if __name__=='__main__':main()
