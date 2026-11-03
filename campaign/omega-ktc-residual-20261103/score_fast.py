"""Independent implementation of the KTC SSIM formula using Gaussian separability.

The official 2-D kernel is c * outer(k,k). The common c cancels from every
normalized local moment. scipy.ndimage.convolve1d uses the same zero extension
as scipy.signal.convolve2d(mode='same') for the odd 321-point symmetric kernel.
This changes evaluation cost, not its windows, constants, images or formula.
Unmodified original score receipts independently check equivalence.
"""
from pathlib import Path
import sys,json,hashlib,time
import numpy as np
from scipy.io import loadmat
from scipy.ndimage import convolve1d
ROOT=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def normalized_filter(a):
 w=np.arange(-160,161);k=np.exp(-0.5*w*w/80**2)
 return convolve1d(convolve1d(np.asarray(a,dtype=float),k,axis=0,mode='constant',cval=0.),k,axis=1,mode='constant',cval=0.)
def binary_ssim(t,r):
 correction=normalized_filter(np.ones(t.shape))
 mt=normalized_filter(t)/correction;mr=normalized_filter(r)/correction
 vt=normalized_filter(t*t)/correction-mt*mt;vr=normalized_filter(r*r)/correction-mr*mr
 cov=normalized_filter(t*r)/correction-mt*mr
 return float(np.mean(((2*mt*mr+1e-4)*(2*cov+9e-4))/((mt*mt+mr*mr+1e-4)*(vt+vr+9e-4))))
def score_arrays(t,r):
 if t.shape!=(256,256):raise ValueError('ground truth shape')
 if r.shape!=(256,256):return 0.
 return .5*sum(binary_ssim((abs(t-i)<.1).astype(float),(abs(r-i)<.1).astype(float)) for i in [1,2])
def run(level,kind):
 tpath=ROOT/'data'/'EvaluationData'/'GroundTruths'/f'level_{level}'/'1_true.mat';opath=ROOT/'outputs'/f'{kind}-{level}'/'1.mat'
 t=loadmat(tpath)['truth'];r=loadmat(opath)['reconstruction'];tm=time.perf_counter();cpu=time.process_time()
 out={'level':level,'phantom':'A=data1','observations':'limited' if kind=='cuqi3' else kind,'arm':'CUQI3' if kind=='cuqi3' else 'organizer','truth_sha256':sha(tpath),'output_sha256':sha(opath),'scorer_sha256':sha(Path(__file__)),'official_score':score_arrays(t,r),'metric_source':'Independent separable implementation of exact published KTC SSIM formula; compare original_score_validation.json',
 'class_metrics':{str(i):{'intersection_over_union':float(np.logical_and(t==i,r==i).sum()/np.logical_or(t==i,r==i).sum()) if np.logical_or(t==i,r==i).any() else 1.,'truth_pixels':int((t==i).sum()),'predicted_pixels':int((r==i).sum()),'signed_area_error_pixels':int((r==i).sum()-(t==i).sum())} for i in (1,2)},'wall_seconds':time.perf_counter()-tm,'cpu_seconds':time.process_time()-cpu}
 p=ROOT/'scores_fast';p.mkdir(exist_ok=True);(p/f'{kind}-{level}.json').write_text(json.dumps(out,indent=2));print(json.dumps(out),flush=True)
if __name__=='__main__':run(int(sys.argv[1]),sys.argv[2])
