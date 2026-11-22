"""Independent saved-array arithmetic check; does not import builder functions.

Same author/host/libraries: procedural self-check, not organizational certification.
"""
from pathlib import Path
import hashlib,json,math,time,resource
import numpy as np
root=Path(__file__).resolve().parent;start=time.process_time();out=[]
refsource=np.load(root/'profile_at_ct_spacing.npz',allow_pickle=False);ref=refsource['reference'];rv=refsource['valid']
for label,resultname,prefix in [('v1','ORDINARY_RESULT.json','ordinary_registered_'),('refined','REFINED_RESULT.json','refined_')]:
 report=json.loads((root/resultname).read_text())
 assert report['protocol_sha256']==hashlib.sha256((root/'PROTOCOL.json').read_bytes()).hexdigest()
 for record in report['results']:
  arr=np.load(root/(prefix+record['side']+'.npz'),allow_pickle=False)
  values=arr['aligned'];mask=arr['overlap']
  assert mask.shape==ref.shape and values.shape==ref.shape and mask.dtype==bool
  assert not np.any(mask & ~rv)
  assert np.isfinite(values[mask]).all()and np.isfinite(ref[mask]).all()
  residual=values[mask]-ref[mask]
  recomputed=math.fsum(map(float,abs(residual)))/len(residual)
  coverage=int(mask.sum())/int(rv.sum())
  assert math.isclose(recomputed,record['mae_mm'],rel_tol=1e-13,abs_tol=1e-15)
  assert math.isclose(coverage,record['coverage'],rel_tol=1e-15)
  out.append({'version':label,'side':record['side'],'points':len(residual),'mae_mm_independent_fsum':recomputed,'coverage':coverage,'receipt_matched':True})
receipt={'scope':'SELF_CHECK_SAVED_ARRAY_ARITHMETIC_ONLY','records':out,'cpu_seconds':time.process_time()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'limitations':'No independent data, physical error model, protected confirmation or builder-free re-extraction.'}
(root/'ARRAY_CHECK.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
