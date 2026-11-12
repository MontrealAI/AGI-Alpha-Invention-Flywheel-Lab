"""Public-data ordinary Otsu, opaque-ray, robust-plane and rigid-registration baseline.

Owned development code. No learned/supplied segmentation invention and no physical
error guarantee. Registration optimizes on exposed measurements; its residuals are
diagnostic and must never be called protected confirmation.
"""
from pathlib import Path
import json,time,resource,hashlib
import numpy as np
from scipy import ndimage, optimize
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
SPACING=.0258478
PROFILE_SPACING=.0074


def otsu(hist):
 h=np.asarray(hist,dtype=np.float64);n=np.cumsum(h);m=np.cumsum(h*np.arange(len(h)))
 score=(m[-1]*n-m*n[-1])**2/np.maximum(n*(n[-1]-n),1)
 return int(np.argmax(score[:-1]))


def plane_fit(surface,valid):
 yy,xx=np.indices(surface.shape)
 use=valid & (yy%4==0)&(xx%4==0)
 X=np.column_stack((np.ones(use.sum()),yy[use],xx[use]));y=surface[use].astype(float)
 chosen=np.ones(len(y),bool)
 history=[]
 for k in range(6):
  coef=np.linalg.lstsq(X[chosen],y[chosen],rcond=None)[0]
  res=y-X@coef
  sigma=1.4826*np.median(abs(res-np.median(res)))
  chosen=abs(res-np.median(res))<max(2.5*sigma,1)
  history.append({'iteration':k,'kept':int(chosen.sum()),'scale_voxels':float(sigma)})
 plane=coef[0]+coef[1]*yy+coef[2]*xx
 depth=(plane-surface)*SPACING/np.sqrt(1+coef[1]**2+coef[2]**2)
 depth[~valid]=np.nan
 return depth,coef,history


def extract(ct,threshold,side='min'):
 solid=ct>threshold
 present=np.any(solid,axis=1)
 labels,n=ndimage.label(present)
 areas=np.bincount(labels.ravel());areas[0]=0
 valid=labels==areas.argmax()
 # Exclude the physical disk edge from the plane fit and scoring; valid mask
 # is retained separately so missingness is never silently filled.
 valid=ndimage.binary_erosion(valid,iterations=3)
 if side=='min':surface=np.argmax(solid,axis=1)
 else:surface=solid.shape[1]-1-np.argmax(solid[:,::-1,:],axis=1)
 del solid
 depth,coef,history=plane_fit(surface,valid)
 if side=='max':depth=-depth
 return depth,valid,coef,history


def downsample_profile():
 profile=np.load(ROOT/'profile.npy',mmap_mode='r')
 # Interpolate values and finite mask separately, retaining only original
 # support neighborhoods; do not manufacture measurements inside missing pores.
 finite=np.isfinite(profile)
 scale=PROFILE_SPACING/SPACING
 num=ndimage.zoom(np.where(finite,profile,0),scale,order=1)
 den=ndimage.zoom(finite.astype(np.float32),scale,order=1)
 valid=den>.999
 val=num/np.maximum(den,1e-20);val[~valid]=np.nan
 return val,valid


def register(depth,valid,reference,refvalid):
 # Robust geometric centres followed by a complete coarse rotation search and
 # local Euclidean registration. Preserve the alternative reflected convention.
 cy,cx=np.mean(np.argwhere(valid),axis=0)
 ry,rx=np.mean(np.argwhere(refvalid),axis=0)
 y,x=np.indices(reference.shape,dtype=np.float64)
 # Source's optical height field has 10um quantization. Window only during
 # registration; all valid finite values remain in final primary scoring.
 target=np.clip(np.nan_to_num(reference),-.5,.15)
 # Register at fourfold spacing using both height features and validity support.
 use=refvalid & (y%4==0)&(x%4==0)
 sy=(y[use]-ry);sx=(x[use]-rx);tv=target[use]
 filled=np.nan_to_num(depth)
 # A clipped negative-height field emphasizes matching surface depressions,
 # while a valid-overlap penalty prevents optimizing by dropping hard pixels.
 tvneg=np.minimum(tv,0)
 def coords(theta,dy=0,dx=0,flip=1):
  a=np.deg2rad(theta);c=np.cos(a);s=np.sin(a)
  return np.array([c*sy-s*flip*sx+cy+dy,s*sy+c*flip*sx+cx+dx])
 def objective(v,flip=1):
  co=coords(*v,flip=flip)
  pred=ndimage.map_coordinates(filled,co,order=1,mode='constant',cval=0)
  support=ndimage.map_coordinates(valid.astype(float),co,order=1,mode='constant',cval=0)>.999
  # Huber-like clipped squared residuals for registration alone.
  err=np.minimum(pred,0)-tvneg
  return float(np.mean(np.minimum(err**2,.1**2))+0.005*np.mean(~support))
 starts=[]
 for flip in (1,-1):
  vals=[(objective([float(a),0,0],flip),a)for a in range(-180,180,10)]
  for score,a in sorted(vals)[:3]:
   fit=optimize.minimize(lambda v:objective(v,flip),[float(a),0,0],method='Powell',bounds=[(a-12,a+12),(-15,15),(-15,15)],options={'maxiter':35,'xtol':.03,'ftol':1e-6})
   starts.append({'flip':flip,'parameters':fit.x.tolist(),'objective':float(fit.fun),'success':bool(fit.success),'nfev':int(fit.nfev)})
 best=min(starts,key=lambda r:r['objective']);theta,dy,dx=best['parameters'];flip=best['flip']
 syall=y-ry;sxall=x-rx;a=np.deg2rad(theta);c=np.cos(a);s=np.sin(a)
 co=np.array([c*syall-s*flip*sxall+cy+dy,s*syall+c*flip*sxall+cx+dx])
 aligned=ndimage.map_coordinates(filled,co,order=1,mode='constant',cval=0)
 support=ndimage.map_coordinates(valid.astype(float),co,order=1,mode='constant',cval=0)>.999
 overlap=refvalid & support
 residual=aligned[overlap]-reference[overlap]
 # Explicit depth strata are diagnostic, not newly admitted feature cohorts.
 strata=[]
 for lo,hi in [(-np.inf,-.1),(-.1,-.03),(-.03,-.01),(-.01,np.inf)]:
  mask=overlap&(reference>=lo)&(reference<hi)
  r=aligned[mask]-reference[mask]
  strata.append({'reference_depth_interval_mm':[str(lo),str(hi)],'n':int(len(r)),'mae_mm':float(np.mean(abs(r)))if len(r)else None})
 result={'alternatives':starts,'best':best,'overlap_pixels':int(overlap.sum()),'reference_valid_pixels':int(refvalid.sum()),'coverage':float(overlap.sum()/refvalid.sum()),'mae_mm':float(np.mean(abs(residual))),'median_abs_mm':float(np.median(abs(residual))),'bias_mm':float(np.mean(residual)),'rms_mm':float(np.sqrt(np.mean(residual**2))),'abs_quantiles_mm':np.quantile(abs(residual),[.5,.9,.95,.99,1]).tolist(),'depth_strata':strata,'reflected_convention_allowed':True,'registration_uses_exposed_reference':True}
 return result,aligned,overlap


def main():
 start=time.process_time();wall=time.monotonic()
 ct=np.load(ROOT/'ct.npy',mmap_mode='r')
 hist=json.loads((ROOT/'INTAKE.json').read_text())['ct']['histogram'];threshold=otsu(hist)
 reference,refvalid=downsample_profile()
 np.savez_compressed(ROOT/'profile_at_ct_spacing.npz',reference=reference,valid=refvalid)
 results=[]
 fig,axs=plt.subplots(2,3,figsize=(12,8),constrained_layout=True)
 for row,side in enumerate(('min','max')):
  depth,valid,coef,history=extract(ct,threshold,side)
  np.savez_compressed(ROOT/f'ordinary_depth_{side}.npz',depth=depth,valid=valid,plane=coef)
  score,aligned,overlap=register(depth,valid,reference,refvalid)
  score.update({'side':side,'threshold':threshold,'plane_coefficients_voxels':coef.tolist(),'plane_fit_history':history})
  results.append(score)
  np.savez_compressed(ROOT/f'ordinary_registered_{side}.npz',aligned=aligned,overlap=overlap,residual=np.where(overlap,aligned-reference,np.nan))
  axs[row,0].imshow(np.where(refvalid,reference,np.nan),vmin=-.3,vmax=.03);axs[row,0].set_title('Measured profilometry (mm)')
  axs[row,1].imshow(np.where(overlap,aligned,np.nan),vmin=-.3,vmax=.03);axs[row,1].set_title(f'Otsu opaque rays {side}')
  z=axs[row,2].imshow(np.where(overlap,aligned-reference,np.nan),vmin=-.1,vmax=.1,cmap='coolwarm');axs[row,2].set_title(f'MAE {score["mae_mm"]:.5f} mm; coverage {score["coverage"]:.3f}')
  for ax in axs[row]:ax.axis('off')
  print(json.dumps({'side':side,'mae_mm':score['mae_mm'],'coverage':score['coverage'],'best':score['best']}),flush=True)
 fig.colorbar(z,ax=axs[:,2],label='height residual (mm)');fig.savefig(ROOT/'ordinary_comparison.png',dpi=140);plt.close(fig)
 record={'scope':'EXPOSED_DEVELOPMENT_NOT_PHYSICAL_QUALIFICATION','protocol_sha256':hashlib.sha256((ROOT/'PROTOCOL.json').read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'results':results,'cpu_seconds':time.process_time()-start,'wall_seconds':time.monotonic()-wall,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'refusal':'No measured calibration/repeatability error, buyer obligation or internal-pore truth; no invention or success claim.'}
 (ROOT/'ORDINARY_RESULT.json').write_text(json.dumps(record,indent=2)+'\n')
 print(json.dumps({k:v for k,v in record.items()if k!='results'}),flush=True)

if __name__=='__main__':main()
