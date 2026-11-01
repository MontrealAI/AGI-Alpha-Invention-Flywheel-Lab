"""Small exact/interface checks for the built modified extension. Not a benchmark."""
import os,sys,argparse,json,math,resource
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
if hasattr(os,'sched_getaffinity'):os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
p=argparse.ArgumentParser();p.add_argument('--extension-dir',required=True)
p.add_argument('--helper-dir',required=True);p.add_argument('--deps',required=True);a=p.parse_args()
ext=Path(a.extension_dir).resolve()
sys.path[:0]=[str(ext),str(Path(a.helper_dir).resolve()),str(Path(a.deps).resolve())]
import numpy as np,stim,tesseract_decoder as td
from diagnostic_common import mask
assert Path(td.__file__).resolve() in {x.resolve() for x in ext.glob('tesseract_decoder*.so')}
checks=[]
def create(text,cap=200000):
 dem=stim.DetectorErrorModel(text)
 return dem,td.tesseract.TesseractConfig(dem,no_revisit_dets=False,pqlimit=cap).compile_decoder()
def verify(dem,decoder,result,target):
 # Parse every original error instruction, including zero-probability IDs.
 columns=[]
 for instruction in dem.flattened():
  if instruction.type!='error':continue
  h=l=0
  for t in instruction.targets_copy():
   if t.is_relative_detector_id():h^=1<<t.val
   elif t.is_logical_observable_id():l^=1<<t.val
  columns.append((h,l))
 seen=set()
 for c in result.candidates:
  key=tuple(sorted(c.errors));assert key not in seen;seen.add(key)
  h=l=0
  for i in c.errors:h^=columns[i][0];l^=columns[i][1]
  assert h==target and l==mask(c.observables)
  assert math.isclose(c.cost,decoder.cost_from_errors(c.errors),rel_tol=1e-12,abs_tol=1e-12)
 assert result.raw_goals==len(result.candidates)+result.duplicate_goals
 assert result.max_arena<=result.pushed
 assert result.truncated

dem,d=create('error(0.1) D0\nerror(0.08) D0 L0\nerror(0.05) D0 L1')
s=np.array([True]);old=list(d.decode_to_errors(s,0,5));one=d.decode_to_error_candidates(s,0,5,1)
assert sorted(one.candidates[0].errors)==sorted(old)
r=d.decode_to_error_candidates(s,0,5,64);verify(dem,d,r,1)
assert len(r.candidates)==3 and len({tuple(c.observables) for c in r.candidates})==3
assert (r.pushed,r.popped,r.expanded,r.max_queue,r.max_arena)==(4,4,1,3,3)
checks.append('three classes, work counts and first-goal regression')
dem,d=create('error(0.1) D0\nerror(0.08) D0 D1\nerror(0.07) D1\nerror(0.05) D0 L0')
r=d.decode_to_error_candidates(np.array([True,False]),0,5,64);verify(dem,d,r,1)
assert sum(not c.observables for c in r.candidates)>=2
checks.append('distinct same-class configurations retained')
dem,d=create('error(0.1) D0 D1 ^ D1 L0\nerror(0.2) D0 L0\nerror(0) D3 L2\nerror(0.05) D0 L1')
r=d.decode_to_error_candidates(np.array([True,False,False,False]),0,5,64);verify(dem,d,r,1)
assert len(r.candidates)==2
for c in r.candidates:
 expected=math.log(.74/.26) if c.observables==[0] else math.log(.95/.05)
 assert math.isclose(c.cost,expected,rel_tol=1e-12)
checks.append('merged original IDs, zero probability and correlated separator')
dem,d=create('error(0.4) D0\nerror(0.05) D0 D1\nerror(0.1) D1',3)
r=d.decode_to_error_candidates(np.array([True,False]),0,5,64);verify(dem,d,r,1)
assert len(r.candidates)==1 and r.stop_reason=='push_limit' and r.pushed==4
assert not d.low_confidence_flag
checks.append('valid goal retained after push cap')
dem,d=create('error(0.1) D0\ndetector D1')
r=d.decode_to_error_candidates(np.array([False,False]),0,5,64);verify(dem,d,r,0)
assert len(r.candidates)==1 and not r.candidates[0].errors
r=d.decode_to_error_candidates(np.array([False,True]),0,5,64)
assert not r.candidates and d.low_confidence_flag and r.stop_reason=='initial_infinite_cost'
checks.append('empty and impossible syndromes')
print(json.dumps({'status':'PASS','checks':checks,'extension':str(Path(td.__file__).resolve())}))
