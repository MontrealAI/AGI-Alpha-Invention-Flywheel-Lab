"""Exploratory unchanged CUQI3 comparison; not an extra confirmatory arm."""
from pathlib import Path
import os,sys,json,hashlib,time,traceback
ROOT=Path(__file__).resolve().parent;SOURCE=ROOT/'cuqi3';sys.path.insert(0,str(SOURCE))
import numpy as np
import scipy
import scipy.io
from main import main

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(level):
 inp=ROOT/'inputs'/f'limited-{level}';out=ROOT/'outputs'/f'cuqi3-{level}';out.mkdir(parents=True,exist_ok=True)
 p=ROOT/'receipts'/f'cuqi3-{level}.json';t=time.perf_counter();c=time.process_time()
 result={'level':level,'observations':'limited','arm':'CUQI3','qualification':'exploratory stronger conventional control, no retuning','source_commit':'c3a9465a3aeb5c2ced6c72aa357afa584fa9b9e7','source_sha256':{f.name:sha(f) for f in SOURCE.glob('*.py')},'input_sha256':{f.name:sha(f) for f in inp.glob('*.mat')},'status':'STARTED'};p.write_text(json.dumps(result,indent=2))
 try:
  os.chdir(SOURCE);sys.argv=['main.py',str(inp),str(out),str(level)];main()
  a=scipy.io.loadmat(out/'1.mat')['reconstruction'];assert a.shape==(256,256) and np.isfinite(a).all() and set(np.unique(a))<=set([0,1,2])
  result.update(status='COMPLETE',output_sha256=sha(out/'1.mat'),array_sha256=hashlib.sha256(a.tobytes()).hexdigest())
 except Exception as e:result.update(status='FAILED',error=repr(e),traceback=traceback.format_exc());raise
 finally:
  result.update(wall_seconds=time.perf_counter()-t,cpu_seconds=time.process_time()-c);p.write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
if __name__=='__main__':run(int(sys.argv[1]))
