"""Cross-binary first-goal regression and actual returned-witness uniqueness.
No circuit benchmark shots; no speed comparison. Run before the frozen diagnostic.
"""
import os,sys,json,argparse,subprocess,math,hashlib,resource
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
if hasattr(os,'sched_getaffinity'):os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
p=argparse.ArgumentParser();p.add_argument('--pristine-extension-dir');p.add_argument('--modified-extension-dir');p.add_argument('--helper-dir',required=True);p.add_argument('--deps',required=True);p.add_argument('--worker',choices=['pristine','modified']);p.add_argument('--extension-dir');a=p.parse_args()
fixtures=[
 ('classes','error(0.1) D0\nerror(0.08) D0 L0\nerror(0.05) D0 L1',[[0],[]],200000),
 ('same_class','error(0.1) D0\nerror(0.08) D0 D1\nerror(0.07) D1\nerror(0.05) D0 L0',[[0],[1],[0,1],[]],200000),
 ('merged_ids','error(0.1) D0 D1 ^ D1 L0\nerror(0.2) D0 L0\nerror(0) D3 L2\nerror(0.05) D0 L1',[[0],[],[3]],200000),
 ('cap_before','error(0.1) D0\nerror(0.08) D0 L0',[[0]],1),
 ('cap_after','error(0.4) D0\nerror(0.05) D0 D1\nerror(0.1) D1',[[0]],3)]
if a.worker:
 ext=Path(a.extension_dir).resolve();sys.path[:0]=[str(ext),str(Path(a.helper_dir).resolve()),str(Path(a.deps).resolve())]
 import numpy as np,stim,tesseract_decoder as td
 module=Path(td.__file__).resolve();assert module in {f.resolve() for f in ext.glob('tesseract_decoder*.so')}
 rows=[]
 for name,text,syndromes,cap in fixtures:
  dem=stim.DetectorErrorModel(text)
  for detectors in syndromes:
   cfg=td.tesseract.TesseractConfig(dem,no_revisit_dets=False,pqlimit=cap,det_beam=5,beam_climbing=False)
   dec=cfg.compile_decoder();s=np.zeros(dec.num_detectors,dtype=bool);s[detectors]=True
   errors=list(dec.decode_to_errors(s,0,5));bad=bool(dec.low_confidence_flag)
   legacy={'errors':sorted(errors),'cost':float(dec.cost_from_errors(errors)),'observables':list(dec.get_observables_from_errors(errors)),'low_confidence':bad}
   row={'case':name,'detectors':detectors,'legacy':legacy}
   if a.worker=='modified':
    result=dec.decode_to_error_candidates(s,0,5,1)
    row['list_found']=bool(result.candidates)
    if result.candidates:
     c=result.candidates[0];row['first']={'errors':sorted(c.errors),'cost':float(c.cost),'observables':[i in set(c.observables) for i in range(dec.num_observables)],'low_confidence':bool(dec.low_confidence_flag)}
    else:row['first']=None
   rows.append(row)
 duplicate_check=None
 if a.worker=='modified':
  # Duplicate DEM representations aggregate EXACTLY ONCE; same detector but
  # distinct logical effect remains a distinct candidate. Inspect real output.
  dem=stim.DetectorErrorModel('error(0.1) D0\nerror(0.2) D0\nerror(0.05) D0 L0')
  dec=td.tesseract.TesseractConfig(dem,no_revisit_dets=False).compile_decoder()
  r=dec.decode_to_error_candidates(np.array([True]),0,5,64)
  keys=[tuple(sorted(c.errors)) for c in r.candidates]
  assert len(keys)==len(set(keys))==2
  assert sorted(tuple(c.observables) for c in r.candidates)==[(),(0,)]
  assert sorted(round(c.cost,12) for c in r.candidates)==sorted([round(math.log(.74/.26),12),round(math.log(.95/.05),12)])
  assert r.raw_goals==len(keys)+r.duplicate_goals
  # The ordered blocked-error search may not generate duplicate goal paths.
  # This checks returned witnesses, not a false claim of hitting that branch.
  duplicate_check={'actual_returned_witnesses':len(keys),'unique_witnesses':len(set(keys)),'raw_goals':r.raw_goals,'duplicate_goals':r.duplicate_goals,'merged_probability':0.26,'duplicate_goal_branch_covered':r.duplicate_goals>0}
 print(json.dumps({'module':str(module),'sha256':hashlib.sha256(module.read_bytes()).hexdigest(),'rows':rows,'duplicate_witness_check':duplicate_check}));sys.exit(0)
assert a.pristine_extension_dir and a.modified_extension_dir
outputs={}
for name,path in [('pristine',a.pristine_extension_dir),('modified',a.modified_extension_dir)]:
 cmd=[sys.executable,__file__,'--worker',name,'--extension-dir',path,'--helper-dir',a.helper_dir,'--deps',a.deps]
 result=subprocess.run(cmd,capture_output=True,text=True,timeout=45)
 if result.returncode:raise RuntimeError(f'{name} test failed: {result.stderr}\n{result.stdout}')
 outputs[name]=json.loads(result.stdout.strip().splitlines()[-1])
assert len(outputs['pristine']['rows'])==len(outputs['modified']['rows'])
for pristine,modified in zip(outputs['pristine']['rows'],outputs['modified']['rows']):
 assert (pristine['case'],pristine['detectors'])==(modified['case'],modified['detectors'])
 old=pristine['legacy'];new=modified['legacy'];assert old==new,(pristine,modified)
 assert modified['list_found']==(not old['low_confidence']),(pristine,modified)
 if modified['first'] is not None:
  first=modified['first'];assert first['errors']==old['errors'] and first['observables']==old['observables'] and first['low_confidence']==old['low_confidence']
  assert math.isclose(first['cost'],old['cost'],rel_tol=1e-12,abs_tol=1e-12)
print(json.dumps({'status':'PASS','cross_build_cases':len(outputs['pristine']['rows']),'pristine_sha256':outputs['pristine']['sha256'],'modified_sha256':outputs['modified']['sha256'],'duplicate_witness_check':outputs['modified']['duplicate_witness_check'],'limitations':['No performance measurement','Duplicate-goal branch coverage reported honestly; uniqueness checked on actual output']}))
