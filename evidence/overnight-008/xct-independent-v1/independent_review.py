import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import hashlib,json,pathlib,resource,time
import numpy as np
import scipy.io as sio,scipy.sparse as sp
from scipy.optimize import linprog

resource.setrlimit(resource.RLIMIT_CPU,(110,115))
base=pathlib.Path('/workspace/scratch/557a27c9cfaf/research_manufacturing/xct')
out=pathlib.Path(__file__).resolve().parent
record=out/'INDEPENDENT_RESULT.json'
if record.exists(): raise FileExistsError(record)
start=time.monotonic();N=82
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
frozen=json.loads((base/'run001/FREEZE.json').read_text())
assert sha(base/'probe.py')==frozen['source_sha256']
assert sha(base/'PROTOCOL.json')==frozen['protocol_sha256']
d=sio.loadmat(base.parent/'data/Data82.mat');A=d['A'].tocsr();y=d['m'].reshape(-1,order='F')
cal=json.loads((base/'run001/CALIBRATION.json').read_text())
raw=sio.loadmat(base/'GroundTruthReconstruction.mat')['FBP1200'].astype(float).reshape(N,28,N,28).mean((1,3)).ravel(order='F')/65535
reference=np.maximum(cal['affine_parameters'][0]*raw+cal['affine_parameters'][1],0)
residual=(A@reference-y).reshape(N,120,order='F')
eps=1.05*np.max(np.abs(residual),axis=1)+1e-6
c=np.zeros((N,N));c[38:44,38:44]=1/36;c=c.ravel(order='F')
def rows(views):return np.concatenate([np.arange(N*v,N*(v+1)) for v in views])
def check(x,views):
    ix=rows(views);r=A[ix]@x-y[ix];e=np.tile(eps,len(views))
    return {'roi_mean':float(c@x),'min_x':float(x.min()),'constraint_excess':float(np.max(np.abs(r)-e)),'feasible':bool(x.min()>=-1e-7 and np.max(np.abs(r)-e)<=1e-7)}
initial=[0,20,40,60,80,100]
selection=json.loads((base/'run001/SELECTION_BEFORE_REPLAY.json').read_text())
labels={'initial':initial,'selected':initial+[selection['selected_view']],'uniform':initial+[selection['uniform_view']]}
result={'scope':'INDEPENDENT_DEVELOPMENT_REVIEW_NO_PROTECTED_CASES','candidate_sha256':frozen['source_sha256'],'protocol_sha256':frozen['protocol_sha256'],'review_source_sha256':sha(pathlib.Path(__file__)),'data_sha256':sha(base.parent/'data/Data82.mat'),'matrix_shape':list(A.shape),'matrix_nnz':int(A.nnz),'ray_order_check':'m(:) and x column-major indexing follow primary dataset documentation; no transpose error established','reference_roi':float(c@reference),'endpoints':{},'full120':{},'limitations':['All120 views and full-view FBP reference exposed to original calibration; not a heldout selection test.','Reference feasibility is guaranteed by fitted empirical residual envelope, not independent physical noise calibration.','ROI mean attenuation is not a pore-size/material-quality outcome.','Shared model libraries and host; no external certification.']}
for label,views in labels.items():
    pair=[]
    for suffix in ['lo','hi']:
        x=np.load(base/f'run001/{label}_{suffix}.npy',allow_pickle=False)
        item=check(x,views);item['all120_check']=check(x,list(range(120)));pair.append(item)
    result['endpoints'][label]={'lo':pair[0],'hi':pair[1],'interval_width':pair[1]['roi_mean']-pair[0]['roi_mean']}
widths=[result['endpoints'][k]['interval_width'] for k in labels]
result['actual_feature_range_reduction']={'selected':widths[0]-widths[1],'uniform':widths[0]-widths[2],'all_three_equal_within_1e_10':max(widths)-min(widths)<1e-10,'conclusion':'Pair separation does not establish ROI uncertainty reduction; the fixed feature range did not shrink.'}
record.write_text(json.dumps(result,indent=2)+'\n')
for sign,label in [(1,'lo'),(-1,'hi')]:
    t=time.monotonic();fit=linprog(sign*c,A_ub=sp.vstack([A,-A],format='csr'),b_ub=np.r_[y+np.tile(eps,120),-y+np.tile(eps,120)],bounds=(0,None),method='highs',options={'time_limit':42,'presolve':True,'threads':1})
    result['full120'][label]={'status':int(fit.status),'message':str(fit.message),'solver_wall_seconds':time.monotonic()-t,'iterations':int(fit.nit)}
    if fit.x is not None:
        result['full120'][label]['check']=check(fit.x,list(range(120)))
        np.save(out/f'all120_{label}.npy',fit.x,allow_pickle=False)
    record.write_text(json.dumps(result,indent=2)+'\n')
result['resources']={'wall_seconds':time.monotonic()-start,'cpu_seconds':resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
record.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
