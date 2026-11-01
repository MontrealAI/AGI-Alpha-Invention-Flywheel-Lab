"""Registered fixed-model official-default validity check; not accuracy benchmark."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
if hasattr(os,'sched_getaffinity'):os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
import sys,time,json,glob,subprocess,resource
import numpy as np,stim,tesseract_decoder as td
from kernel import mask,bits

def make():
 c=stim.Circuit.from_file(glob.glob('upstream/testdata/bivariatebicyclecodes/r=6,d=6,p=0.002,*_Z,*72*')[0])
 first=td.tesseract.TesseractConfig(c.detector_error_model(decompose_errors=False)).compile_decoder()
 return c,first.config.dem

def syndrome(m,h):
 s=0
 for i in bits(m):s^=h[i]
 return s

if len(sys.argv)>1 and sys.argv[1]=='worker':
 start=time.perf_counter();c,dem=make();cfg=td.tesseract.TesseractConfig(dem);d=cfg.compile_decoder();h=[mask(e.symptom.detectors) for e in d.errors]
 s=np.zeros(c.num_detectors,dtype=bool);s[list(map(int,sys.argv[2].split(',')))]=True
 prep=time.perf_counter()-start;t=time.perf_counter();ids=d.decode_to_errors(s);elapsed=time.perf_counter()-t
 print(json.dumps({'valid':syndrome(mask(ids),h)==mask(s.nonzero()[0]),'decode_seconds':elapsed,'prep_seconds':prep,'low_confidence':bool(d.low_confidence_flag),'errors_count':len(ids),'cost':d.cost_from_errors(ids),'maxrss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'actual_config':{'orders':len(d.config.det_orders),'pqlimit':d.config.pqlimit,'beam':d.config.det_beam,'beam_climbing':d.config.beam_climbing,'merge_errors':d.config.merge_errors}}));sys.exit(0)
start=time.perf_counter();c,dem=make();d=td.tesseract.TesseractConfig(dem,det_beam=10,pqlimit=10000,beam_climbing=True).compile_decoder();h=[mask(e.symptom.detectors) for e in d.errors];sampler=c.compile_detector_sampler(seed=2026110102)
selected=[];first_invalid=None
for i in range(32):
 s=sampler.sample(1)[0];target=mask(s.nonzero()[0]);t=time.perf_counter();valid=0
 for order in range(4):valid+=syndrome(mask(d.decode_to_errors(s,order,10)),h)==target
 entry={'shot':i,'detector_indices':s.nonzero()[0].tolist(),'capped_valid_searches':valid,'capped_decode_seconds':time.perf_counter()-t}
 if i in (0,1,2):selected.append(entry)
 if valid==0 and first_invalid is None:
  first_invalid=i
  if i not in (0,1,2):selected.append(entry)
 if i>=2 and first_invalid is not None:break
results=[]
for entry in selected:
 t=time.perf_counter()
 try:
  p=subprocess.run([sys.executable,__file__,'worker',','.join(map(str,entry['detector_indices']))],capture_output=True,text=True,timeout=45,env=os.environ)
  if p.returncode:entry['official']={'status':'error','returncode':p.returncode,'stderr':p.stderr[-1000:]}
  else:entry['official']={'status':'complete',**json.loads(p.stdout.strip().splitlines()[-1])}
 except subprocess.TimeoutExpired:entry['official']={'status':'timeout','wall_limit_seconds':45}
 entry['official_process_seconds']=time.perf_counter()-t;results.append(entry)
 out={'purpose':'validity-only sanity, not accuracy or cost-matched benchmark','selection':'fixed shots0,1,2 plus first all-invalid capped shot among first32, no truth labels accessed','seed':2026110102,'sample_batch':1,'first_invalid_shot':first_invalid,'worker_timeout_seconds':45,'total_seconds':time.perf_counter()-start,'shots':results}
 open('research/default_sanity.json','w').write(json.dumps(out,indent=2));print(json.dumps(entry),flush=True)
