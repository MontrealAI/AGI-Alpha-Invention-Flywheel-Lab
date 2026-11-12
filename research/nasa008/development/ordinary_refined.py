"""Conventional subvoxel isosurface + normalized feature rigid registration.

This strengthens ordinary baseline, preserves v1 and keeps its primary endpoint.
No new feature admission, calibration, protected confirmation or invention claim.
"""
from pathlib import Path
import json,time,resource,hashlib
import numpy as np
from scipy import ndimage,optimize,signal
from ordinary_baseline import ROOT,SPACING,otsu,plane_fit,downsample_profile
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def extract(ct,threshold,side):
 solid=ct>threshold
 present=np.any(solid,axis=1)
 labels,n=ndimage.label(present);areas=np.bincount(labels.ravel());areas[0]=0
 valid=ndimage.binary_erosion(labels==areas.argmax(),iterations=3)
 if side=='min':idx=np.argmax(solid,axis=1)
 else:idx=solid.shape[1]-1-np.argmax(solid[:,::-1,:],axis=1)
 del solid
 yy,xx=np.indices(idx.shape)
 inside=ct[yy,idx,xx].astype(np.float64)
 outside_idx=np.maximum(idx-1,0)if side=='min'else np.minimum(idx+1,ct.shape[1]-1)
 outside=ct[yy,outside_idx,xx].astype(np.float64)
 fraction=(inside-threshold)/np.maximum(inside-outside,1)
 surface=idx-fraction if side=='min'else idx+fraction
 depth,coef,history=plane_fit(surface,valid)
 if side=='max':depth=-depth
 return depth,valid,coef,history


def register(depth,valid,ref,refvalid):
 cy,cx=np.mean(np.argwhere(valid),axis=0);ry,rx=np.mean(np.argwhere(refvalid),axis=0)
 ys,xs=np.indices(ref.shape,dtype=float)
 feature=lambda a:ndimage.gaussian_filter(np.clip((-np.nan_to_num(a)-.015)/.10,0,1),.65)
 sf=feature(depth);tf=feature(ref)
 step=3
 # Erode support for registration only, avoiding a jagged disk edge dominating
 # the correlation; final scoring still uses all originally valid overlap.
 target_valid=ndimage.binary_erosion(refvalid,iterations=9)[::step,::step]
 sy=(ys[::step,::step]-ry);sx=(xs[::step,::step]-rx)
 target=tf[::step,::step]*target_valid
 syall=ys-ry;sxall=xs-rx
 def R(theta,flip):
  a=np.deg2rad(theta);c=np.cos(a);s=np.sin(a)
  return np.array([[c,-s*flip],[s,c*flip]])
 def sample(theta,dy,dx,flip,field=sf):
  rot=R(theta,flip)
  co=np.array([rot[0,0]*sy+rot[0,1]*sx+cy+dy,rot[1,0]*sy+rot[1,1]*sx+cx+dx])
  return ndimage.map_coordinates(field,co,order=1,mode='constant',cval=0)
 starts=[]
 for flip in (1,-1):
  coarse=[]
  for a in range(-180,180,4):
   source=sample(a,0,0,flip)*target_valid
   corr=signal.fftconvolve(target,source[::-1,::-1],mode='same')
   h,w=corr.shape;window=corr[h//2-12:h//2+13,w//2-12:w//2+13]
   iy,ix=np.unravel_index(np.argmax(window),window.shape)
   shift=np.array([iy-12,ix-12])*step
   adjust=-R(a,flip)@shift
   normalized=float(window[iy,ix]/np.sqrt(max(np.sum(target**2)*np.sum(source**2),1e-20)))
   coarse.append((normalized,a,*adjust))
  for initial in sorted(coarse,reverse=True)[:4]:
   _,a,dy,dx=initial
   def loss(v):
    pred=sample(*v,flip)*target_valid
    return 1-float(np.sum(pred*target)/np.sqrt(max(np.sum(target**2)*np.sum(pred**2),1e-20)))
   fit=optimize.minimize(loss,[a,dy,dx],method='Powell',bounds=[(a-5,a+5),(dy-10,dy+10),(dx-10,dx+10)],options={'maxiter':40,'xtol':.02,'ftol':1e-7})
   starts.append({'flip':flip,'parameters':fit.x.tolist(),'loss':float(fit.fun),'success':bool(fit.success),'nfev':int(fit.nfev)})
 best=min(starts,key=lambda v:v['loss']);theta,dy,dx=best['parameters'];rot=R(theta,best['flip'])
 co=np.array([rot[0,0]*syall+rot[0,1]*sxall+cy+dy,rot[1,0]*syall+rot[1,1]*sxall+cx+dx])
 aligned=ndimage.map_coordinates(np.nan_to_num(depth),co,order=1,mode='constant',cval=0)
 support=ndimage.map_coordinates(valid.astype(float),co,order=1,mode='constant',cval=0)>.999
 overlap=refvalid&support
 r=aligned[overlap]-ref[overlap]
 strata=[]
 for lo,hi in [(-np.inf,-.1),(-.1,-.03),(-.03,-.01),(-.01,np.inf)]:
  use=overlap&(ref>=lo)&(ref<hi);e=aligned[use]-ref[use]
  strata.append({'reference_interval_mm':[str(lo),str(hi)],'pixels':int(use.sum()),'mae_mm':float(np.mean(abs(e)))if len(e)else None,'bias_mm':float(np.mean(e))if len(e)else None})
 result={'best':best,'alternatives':starts,'overlap_pixels':int(overlap.sum()),'reference_valid_pixels':int(refvalid.sum()),'coverage':float(overlap.sum()/refvalid.sum()),'mae_mm':float(np.mean(abs(r))),'bias_mm':float(np.mean(r)),'rms_mm':float(np.sqrt(np.mean(r*r))),'abs_quantiles_mm':np.quantile(abs(r),[.5,.9,.95,.99,1]).tolist(),'depth_strata':strata,'registration_metric':'normalized clipped depression-field correlation; eroded interior support for registration only','scoring_metric':'unchanged all-valid overlap MAE','disclosure':'All data exposed DEVELOPMENT; fitted registration is not independent validation.'}
 return result,aligned,overlap


def main():
 start=time.process_time();wall=time.monotonic();ct=np.load(ROOT/'ct.npy',mmap_mode='r')
 hist=json.loads((ROOT/'INTAKE.json').read_text())['ct']['histogram'];threshold=otsu(hist)
 ref,refvalid=downsample_profile();results=[]
 fig,axs=plt.subplots(2,3,figsize=(12,8),constrained_layout=True)
 for row,side in enumerate(('min','max')):
  depth,valid,coef,history=extract(ct,threshold,side)
  score,aligned,overlap=register(depth,valid,ref,refvalid)
  score.update({'side':side,'threshold':threshold,'plane_voxels':coef.tolist(),'plane_history':history})
  results.append(score)
  np.savez_compressed(ROOT/f'refined_{side}.npz',depth=depth,valid=valid,plane=coef,aligned=aligned,overlap=overlap)
  axs[row,0].imshow(np.where(refvalid,ref,np.nan),vmin=-.3,vmax=.03);axs[row,0].set_title('Independent profilometry (mm)')
  axs[row,1].imshow(np.where(overlap,aligned,np.nan),vmin=-.3,vmax=.03);axs[row,1].set_title(f'Ordinary subvoxel {side}')
  z=axs[row,2].imshow(np.where(overlap,aligned-ref,np.nan),vmin=-.1,vmax=.1,cmap='coolwarm');axs[row,2].set_title(f'MAE {score["mae_mm"]:.5f} mm; coverage {score["coverage"]:.3f}')
  for ax in axs[row]:ax.axis('off')
  print(json.dumps({'side':side,'mae_mm':score['mae_mm'],'coverage':score['coverage'],'best':score['best']}),flush=True)
 fig.colorbar(z,ax=axs[:,2],label='height residual (mm)');fig.savefig(ROOT/'refined_comparison.png',dpi=140);plt.close(fig)
 record={'scope':'EXPOSED_DEVELOPMENT_STRONGER_ORDINARY_METHOD_NOT_INVENTION','protocol_sha256':hashlib.sha256((ROOT/'PROTOCOL.json').read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'results':results,'cpu_seconds':time.process_time()-start,'wall_seconds':time.monotonic()-wall,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'no_calibration_claim':True,'approximation':'Ray direction uses CT axis rather than fitted plane normal; lowres volume and no supplied exact labels/registration. Differences from published complete route prevent claiming full source reproduction.'}
 (ROOT/'REFINED_RESULT.json').write_text(json.dumps(record,indent=2)+'\n')
 print(json.dumps({k:v for k,v in record.items()if k!='results'}),flush=True)

if __name__=='__main__':main()
