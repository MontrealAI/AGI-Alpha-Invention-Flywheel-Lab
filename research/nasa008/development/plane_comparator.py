"""Simplest conventional comparator for flat-dominated primary endpoint.

Zero fitted-plane prediction contains no pore identification. Its score can reveal
that the chosen field MAE cannot establish the intended feature obligation.
"""
from pathlib import Path
import json,time,hashlib
import numpy as np
root=Path(__file__).resolve().parent;start=time.process_time()
s=np.load(root/'profile_at_ct_spacing.npz',allow_pickle=False);ref=s['reference'];valid=s['valid']
records=[]
for name,mask in [('all_reference_valid',valid),('v1_max_overlap',np.load(root/'ordinary_registered_max.npz',allow_pickle=False)['overlap']),('refined_max_overlap',np.load(root/'refined_max.npz',allow_pickle=False)['overlap'])]:
 values=ref[mask];r=-values
 strata=[]
 for lo,hi in [(-np.inf,-.1),(-.1,-.03),(-.03,-.01),(-.01,np.inf)]:
  use=(values>=lo)&(values<hi)
  strata.append({'reference_interval_mm':[str(lo),str(hi)],'n':int(use.sum()),'mae_mm':float(np.mean(abs(r[use])))if use.any()else None})
 records.append({'scope':name,'n':len(values),'coverage':float(mask.sum()/valid.sum()),'mae_mm':float(np.mean(abs(r))),'depth_strata':strata})
record={'scope':'EXPOSED_DEVELOPMENT_STRONG_SIMPLE_COMPARATOR','method':'Predict height0 everywhere relative to the supplied fitted plane; no pore identification','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'results':records,'cpu_seconds':time.process_time()-start,'decision':'Whole-field MAE alone cannot qualify consequential pore support if a featureless plane wins; keep the original endpoint and report the limitation, no retroactive success threshold.'}
(root/'PLANE_COMPARATOR.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
