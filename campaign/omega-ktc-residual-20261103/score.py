"""Run the released KTC scoring function unchanged on frozen evaluation outputs."""
from pathlib import Path
import sys,json,hashlib,time
import numpy as np
from scipy.io import loadmat
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'source'/'Codes_Python'))
from KTCScoring import scoringFunction

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def score(level,kind):
    truthpath=ROOT/'data'/'EvaluationData'/'GroundTruths'/f'level_{level}'/'1_true.mat'
    outpath=ROOT/'outputs'/f'{kind}-{level}'/'1.mat'
    truth=loadmat(truthpath)['truth'];reco=loadmat(outpath)['reconstruction']
    t=time.perf_counter();c=time.process_time()
    result={'level':level,'phantom':'A=data1','observations':kind,'truth_sha256':sha(truthpath),'output_sha256':sha(outpath),'scorer_sha256':sha(ROOT/'source'/'Codes_Python'/'KTCScoring.py'),'official_score':float(scoringFunction(truth,reco)),
            'metric_source':'Unmodified KTC v3 KTCScoring.scoringFunction: mean per-class SSIM',
            'class_metrics':{str(i):{'intersection_over_union':float(np.logical_and(truth==i,reco==i).sum()/np.logical_or(truth==i,reco==i).sum()) if np.logical_or(truth==i,reco==i).any() else 1.,'truth_pixels':int((truth==i).sum()),'predicted_pixels':int((reco==i).sum()),'signed_area_error_pixels':int((reco==i).sum()-(truth==i).sum())} for i in (1,2)},
            'wall_seconds':time.perf_counter()-t,'cpu_seconds':time.process_time()-c}
    p=ROOT/'scores';p.mkdir(exist_ok=True);(p/f'{kind}-{level}.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
if __name__=='__main__':score(int(sys.argv[1]),sys.argv[2])
