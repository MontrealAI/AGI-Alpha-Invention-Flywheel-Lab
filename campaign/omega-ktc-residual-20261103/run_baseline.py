"""Execute unchanged KTC v3 organizer code; held-out selection frozen in PROTOCOL.md."""
from pathlib import Path
import os,sys,json,hashlib,shutil,time,traceback
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'source'/'Codes_Python'
sys.path.insert(0,str(SOURCE))
import numpy as np
import scipy
import scipy.io
from main import main

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(level,kind):
    inputdir=ROOT/'inputs'/f'{kind}-{level}'
    outputdir=ROOT/'outputs'/f'{kind}-{level}'
    inputdir.mkdir(parents=True,exist_ok=True);outputdir.mkdir(parents=True,exist_ok=True)
    src=ROOT/'data'/('EvaluationData_full' if kind=='full' else 'EvaluationData')/'evaluation_datasets'/f'level{level}'
    for name in ('data1.mat','ref.mat'):shutil.copyfile(src/name,inputdir/name)
    receipt=ROOT/'receipts'/f'{kind}-{level}.json';receipt.parent.mkdir(exist_ok=True)
    data={'schema':'omega/ktc-residual/v1','level':level,'phantom':'A=data1','observations':kind,'category_argument':1 if kind=='full' else level,
          'input_sha256':{name:sha(inputdir/name) for name in ('data1.mat','ref.mat')},
          'source_sha256':{p.name:sha(p) for p in SOURCE.glob('*.py')},
          'versions':{'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__},
          'protocol_sha256':sha(ROOT/'PROTOCOL.md'),'status':'STARTED'}
    receipt.write_text(json.dumps(data,indent=2)); t=time.perf_counter();c=time.process_time()
    try:
        os.chdir(SOURCE);main(str(inputdir),str(outputdir),data['category_argument'])
        a=scipy.io.loadmat(outputdir/'1.mat')['reconstruction']
        assert a.shape==(256,256) and np.isfinite(a).all() and set(np.unique(a))<=set([0,1,2])
        data.update(status='COMPLETE',output_sha256=sha(outputdir/'1.mat'),array_sha256=hashlib.sha256(a.tobytes()).hexdigest(),label_counts={str(int(i)):int((a==i).sum()) for i in np.unique(a)})
    except Exception as e:
        data.update(status='FAILED',error=type(e).__name__+': '+str(e),traceback=traceback.format_exc())
        raise
    finally:
        data.update(wall_seconds=time.perf_counter()-t,cpu_seconds=time.process_time()-c)
        receipt.write_text(json.dumps(data,indent=2));print(json.dumps(data),flush=True)
if __name__=='__main__':run(int(sys.argv[1]),sys.argv[2])
