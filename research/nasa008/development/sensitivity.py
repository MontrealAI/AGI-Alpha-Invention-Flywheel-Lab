"""Declared ordinary threshold/registration sensitivity, not measurement uncertainty.

Five thresholds are ordinary alternatives, never five fresh confirmation attempts.
All outputs and source cases are exposed development. No threshold is accepted as
physical truth and all failed/missing points stay in each coverage denominator.
"""
import json,time,resource,hashlib
import numpy as np
from scipy import ndimage
from ordinary_refined import extract,ROOT,SPACING
start=time.process_time();wall=time.monotonic()
ct=np.load(ROOT/'ct.npy',mmap_mode='r');source=np.load(ROOT/'profile_at_ct_spacing.npz');ref=source['reference'];valid=source['valid']
best=json.loads((ROOT/'REFINED_RESULT.json').read_text())['results'][1]['best']
theta,dy,dx=best['parameters'];flip=best['flip']
y,x=np.indices(ref.shape,dtype=float);ry,rx=np.mean(np.argwhere(valid),axis=0);sy=y-ry;sx=x-rx


def evaluate(depth,support,extra_y=0,extra_x=0,extra_angle=0):
 cy,cx=np.mean(np.argwhere(support),axis=0);a=np.deg2rad(theta+extra_angle);c=np.cos(a);s=np.sin(a)
 co=np.array([c*sy-s*flip*sx+cy+dy+extra_y,s*sy+c*flip*sx+cx+dx+extra_x])
 aligned=ndimage.map_coordinates(np.nan_to_num(depth),co,order=1,mode='constant',cval=0)
 sv=ndimage.map_coordinates(support.astype(float),co,order=1,mode='constant',cval=0)>.999
 overlap=valid&sv;r=aligned[overlap]-ref[overlap]
 strata=[]
 for lo,hi in [(-np.inf,-.1),(-.1,-.03),(-.03,-.01),(-.01,np.inf)]:
  use=overlap&(ref>=lo)&(ref<hi);e=aligned[use]-ref[use]
  strata.append({'reference_interval_mm':[str(lo),str(hi)],'n':int(use.sum()),'mae_mm':float(np.mean(abs(e)))if len(e)else None})
 return {'mae_mm':float(np.mean(abs(r))),'bias_mm':float(np.mean(r)),'coverage':float(overlap.sum()/valid.sum()),'n':int(overlap.sum()),'depth_strata':strata}

records=[];registration=[]
for threshold in (84,88,92,96,100):
 depth,support,coef,history=extract(ct,threshold,'max')
 metrics=evaluate(depth,support)
 records.append({'threshold':threshold,'metrics':metrics,'plane':coef.tolist()})
 print(json.dumps({'threshold':threshold,'mae_mm':metrics['mae_mm'],'deep_mae_mm':metrics['depth_strata'][0]['mae_mm']}),flush=True)
 if threshold==92:
  for e_y,e_x,e_a in [(0,0,0),(-1,0,0),(1,0,0),(0,-1,0),(0,1,0),(0,0,-.1),(0,0,.1)]:
   registration.append({'perturbation_ct_pixels_degrees':[e_y,e_x,e_a],'metrics':evaluate(depth,support,e_y,e_x,e_a)})
profile=np.load(ROOT/'profile.npy',mmap_mode='r')
# Streaming quantization check keeps memory bounded and includes every finite pixel.
finite_n=0;noninteger_n=0;max_deviation=0;zero_n=0
for block in profile:
 v=block[np.isfinite(block)];q=v/.01;d=abs(q-np.rint(q));finite_n+=len(v);noninteger_n+=int((d>1e-10).sum());max_deviation=max(max_deviation,float(d.max())if len(d) else 0);zero_n+=int((v==0).sum())
receipt={'scope':'DEVELOPMENT_SENSITIVITY_NOT_A_CALIBRATED_ERROR_BOUND','unchanged_primary':'all-valid-overlap mean absolute depth deviation','fixed_registration_from':'REFINED_RESULT.json max-side; no threshold-specific re-registration','threshold_grid':records,'registration_perturbations':registration,'registration_perturbation_interpretation':'Chosen +/-1CTpixel and +/-0.1degree scenarios only, not measured confidence bounds','profile_quantization':{'finite_n':finite_n,'zero_n':zero_n,'fraction_zero':zero_n/finite_n,'step_test_mm':.01,'nonmultiples_over_tolerance':noninteger_n,'max_grid_deviation':max_deviation,'caution':'Exact step membership does not identify rounding convention or total measurement error.'},'cpu_seconds':time.process_time()-start,'wall_seconds':time.monotonic()-wall,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
(ROOT/'SENSITIVITY_RESULT.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items()if k not in ('threshold_grid','registration_perturbations')}),flush=True)
