"""Construct a NEW exposed-development model edition, not recover lost bytes."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import hashlib,json,pathlib,resource,time
import numpy as np
from scipy.io import loadmat
from scipy.optimize import least_squares

ROOT=pathlib.Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    start=time.monotonic();resource.setrlimit(resource.RLIMIT_CPU,(45,50));resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30))
    out=ROOT/'model'
    out.mkdir(exist_ok=False)
    data=ROOT/'data/Data82.mat';gt=ROOT/'data/GroundTruthReconstruction.mat'
    assert sha(data)=='03a35c57ae52026f980ffcf540a4243a02f198b3fcdd8dff72cb251f70b067cc'
    assert sha(gt)=='88cc17c0b9706a9cf88f615e490d0254e59e89ee88740d293d06c16a1d6005bd'
    d=loadmat(data);A=d['A'].tocsr();y=d['m'].reshape(-1,order='F')
    assert A.shape==(9840,6724) and A.nnz==970344 and np.min(A.data)>=0
    fbp=loadmat(gt)['FBP1200']
    assert fbp.shape==(2296,2296) and fbp.dtype==np.uint16
    raw=fbp.astype(float).reshape(82,28,82,28).mean((1,3)).ravel(order='F')/65535
    def residual(p):return A@np.maximum(p[0]*raw+p[1],0)-y
    fit=least_squares(residual,[.1,0],bounds=([0,-np.inf],[np.inf,np.inf]),ftol=1e-12,xtol=1e-12,gtol=1e-12,max_nfev=200)
    reference=np.maximum(fit.x[0]*raw+fit.x[1],0)
    r=A@reference-y
    eps=1.05*np.max(np.abs(r.reshape(82,120,order='F')),axis=1)+1e-6
    c=np.zeros((82,82));c[38:44,38:44]=1/36;c=c.ravel(order='F')
    for name,array in [('reference',reference),('eps',eps),('objective',c)]:np.save(out/f'{name}.npy',array,allow_pickle=False)
    info={'edition':'XCT008_RECOVERY_MODEL_R1_NEW_BYTES','scope':'EXPOSED_DEVELOPMENT_NOT_PROTECTED','affine_parameters':fit.x.tolist(),'affine_fit':{'method':'scipy.optimize.least_squares; x0=[.1,0]; clipped affine nonnegative reference','success':bool(fit.success),'nfev':int(fit.nfev),'message':str(fit.message),'bounds':{'scale_min':0,'offset':'unbounded'},'tolerances':1e-12},'matrix_shape':list(A.shape),'matrix_nnz':int(A.nnz),'data_sha256':sha(data),'groundtruth_sha256':sha(gt),'source_sha256':sha(pathlib.Path(__file__)),'reference_roi_float':float(c@reference),'relative_residual_l2':float(np.linalg.norm(r)/np.linalg.norm(y)),'max_abs_residual':float(np.max(np.abs(r))),'eps_rule':'1.05*max(abs((A@reference-y).reshape(82,120,order=F)),axis=1)+1e-6','roi':{'rows':[38,44],'cols':[38,44],'order':'F','coefficient_float':float(1/36)},'arrays':{name:sha(out/f'{name}.npy') for name in ['reference','eps','objective']},'resources':{'cpu_seconds':time.process_time(),'wall_seconds':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},'limitations':['Lost prior calibration bytes cannot be recovered from their hash; this is a declared reconstructed edition.','All120 source views and full1200-view reference exposed; empirical model discrepancy has no independent physical coverage.','The reference is feasible by construction. No physical/material/industrial/customer claim.']}
    (out/'CALIBRATION.json').write_text(json.dumps(info,indent=2)+'\n');print(json.dumps(info))
if __name__=='__main__':main()
