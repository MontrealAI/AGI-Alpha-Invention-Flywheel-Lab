"""Document complete fixed affine maps from original frozen centers/parameters.
No candidate reexecution or source/case mutation; units CT-index per physical mm.
"""
from pathlib import Path
import hashlib,json,time
import numpy as np
root=Path(__file__).resolve().parent;old=root.parent/'energy_recovery';start=time.process_time()
ref=np.load(old/'profile_at_ct_spacing.npz',allow_pickle=False);ry,rx=np.mean(np.argwhere(ref['valid']),axis=0)
report=json.loads((old/'REFINED_RESULT.json').read_text());spacing=np.array([(3259-1)*.0074/(933-1),(3195-1)*.0074/(915-1)])
rows=[]
for side in ('min','max'):
 data=np.load(old/('refined_'+side+'.npz'),allow_pickle=False);center=np.mean(np.argwhere(data['valid']),axis=0)
 row=next(x for x in report['results']if x['side']==side);theta,dy,dx=row['best']['parameters'];flip=row['best']['flip'];a=np.deg2rad(theta);c=np.cos(a);s=np.sin(a);R=np.array([[c,-s*flip],[s,c*flip]])
 A=R@np.diag(1/spacing);b=center+np.array([dy,dx])-R@np.array([ry,rx])
 rows.append({'side':side,'original_reference_valid_center_indices':[ry,rx],'original_CT_support_center_indices':center.tolist(),'old_actual_reference_spacing_mm':spacing.tolist(),'old_frozen_parameters':row['best'],'A_CT_indices_per_mm':A.tolist(),'b_CT_indices':b.tolist(),'formula':'CT_index=A@[target_y_mm,target_x_mm]+b; no repaired-validity recentering'})
with(root/'AFFINE_MAPS.json').open('x')as f:json.dump({'scope':'DOCUMENTARY_DERIVATION_FROM_FROZEN_CONSTANTS','rows':rows,'cpu_seconds':time.process_time()-start,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},f,indent=2);f.write('\n')
