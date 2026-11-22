"""Source-hashed ordinary repair of an independently verified XY grid defect.

No threshold search, new data, hidden test, physical-error bound or invention.
The original frozen package is read-only and is hash-checked before/after.
"""
import os,sys
sys.dont_write_bytecode=True
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
from pathlib import Path
import argparse,datetime,hashlib,json,math,time,resource
import numpy as np
from scipy import ndimage
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OLD_MANIFEST='60a275fcf18a4a01e44fed5ac12c6260052125bdc214eaa64f4818ee549b9033'
PROTOCOL='26e92db9b0f5b2195c3844db384b15921b7eaac9031dd8ebee6035771490c61c'
S=.0074;T=.0258478
STRATA=[(-np.inf,-.1),(-.1,-.03),(-.03,-.01),(-.01,np.inf)]


def sha(path):
 with Path(path).open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def write(path,record):
 with Path(path).open('x')as out:json.dump(record,out,indent=2,allow_nan=False);out.write('\n')


def metrics(pred,reference,overlap,valid):
 assert overlap.shape==reference.shape and np.all(~overlap|valid)
 residual=pred[overlap]-reference[overlap]
 mean=lambda a:math.fsum(map(float,a))/len(a)if len(a)else None
 strata=[]
 for lo,hi in STRATA:
  original=valid&(reference>=lo)&(reference<hi);use=original&overlap
  r=pred[use]-reference[use]
  strata.append({'interval_mm':[str(lo),str(hi)],'reference_n':int(original.sum()),'overlap_n':int(use.sum()),'coverage':float(use.sum()/original.sum())if original.any()else None,'mae_mm':mean(abs(r)),'zero_plane_mae_mm':mean(abs(reference[use]))})
 return {'reference_n':int(valid.sum()),'overlap_n':int(overlap.sum()),'coverage':float(overlap.sum()/valid.sum()),'mae_mm':mean(abs(residual)),'bias_mm':mean(residual),'zero_plane_mae_mm_same_overlap':mean(abs(reference[overlap])),'strata':strata}


def delta_masks(old,new,universe):
 return {'universe_n':int(universe.sum()),'old_n':int((old&universe).sum()),'new_n':int((new&universe).sum()),'intersection_n':int((old&new&universe).sum()),'old_only_n':int((old&~new&universe).sum()),'new_only_n':int((new&~old&universe).sum()),'neither_n':int((~old&~new&universe).sum())}


def sample(field,coordinates):return ndimage.map_coordinates(field,coordinates,order=1,mode='constant',cval=0)


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--old',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
 old=a.old.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);code_root=Path(__file__).resolve().parent
 start=time.process_time();wall=time.monotonic()
 assert sha(code_root/'PROTOCOL.json')==PROTOCOL
 assert sha(old/'MANIFEST.json')==OLD_MANIFEST
 auth=json.loads((code_root/'AUTH.json').read_text());assert auth['agreed_protocol_sha256']==PROTOCOL
 manifest=json.loads((old/'MANIFEST.json').read_text());before={}
 for item in manifest['files']:
  path=old/item['path'];before[item['path']]=sha(path);assert path.stat().st_size==item['bytes']and before[item['path']]==item['sha256'],item['path']
 # Use exact frozen conventional helper; prevent bytecode writes in old package.
 sys.path.insert(0,str(old))
 from ordinary_refined import register
 native=np.load(old/'profile.npy',mmap_mode='r',allow_pickle=False)
 finite=np.isfinite(native);shape=tuple(int(np.floor((n-1)*S/T))+1 for n in native.shape)
 assert shape==(933,915)
 yy,xx=np.indices(shape,dtype=float);native_coords=np.array([yy*T/S,xx*T/S])
 # Process coordinates are explicitly defined by sample centers, not zoomfactor.
 numerator=sample(np.where(finite,native,0),native_coords)
 denominator=sample(finite.astype(np.float32),native_coords)
 valid=denominator>.999
 reference=numerator/np.maximum(denominator,1e-20);reference[~valid]=np.nan
 np.savez_compressed(out/'corrected_reference.npz',reference=reference,valid=valid,target_y_mm=np.arange(shape[0])*T,target_x_mm=np.arange(shape[1])*T)
 ramps=[];old_spacings=[]
 for axis,n in enumerate(native.shape):
  native_ramp=np.arange(n,dtype=float)*S;target=np.arange(shape[axis])*T
  repaired=sample(native_ramp,np.array([target/S]))
  error=float(np.max(abs(repaired-target)));assert error<1e-12
  old_ramp=ndimage.zoom(native_ramp,S/T,order=1)
  old_spacing=(n-1)*S/(len(old_ramp)-1);old_spacings.append(old_spacing)
  ramps.append({'axis':axis,'native_count':n,'target_count':shape[axis],'source_spacing_mm':S,'target_spacing_mm':T,'repaired_max_error_mm':error,'old_zoom_effective_spacing_mm':old_spacing,'trailing_center_span_cropped_mm':float((n-1)*S-target[-1]),'old_zoom_endpoint_drift_mm':float(old_ramp[-1]-target[-1])})
 old_refsource=np.load(old/'profile_at_ct_spacing.npz',allow_pickle=False);old_ref=old_refsource['reference'];old_valid=old_refsource['valid']
 transport_coords=np.array([yy*T/old_spacings[0],xx*T/old_spacings[1]])
 transported_old_valid=sample(old_valid.astype(float),transport_coords)>.999
 num=sample(np.nan_to_num(old_ref),transport_coords);den=sample(old_valid.astype(float),transport_coords)
 transported_old_ref=num/np.maximum(den,1e-20);transported_old_ref[~transported_old_valid]=np.nan
 np.savez_compressed(out/'transported_old_reference.npz',reference=transported_old_ref,valid=transported_old_valid,coordinates=transport_coords)
 shared_reference=valid&transported_old_valid
 rows=[];plots=[]
 old_result=json.loads((old/'REFINED_RESULT.json').read_text())
 for side in ('min','max'):
  old_row=next(row for row in old_result['results']if row['side']==side)
  data=np.load(old/('refined_'+side+'.npz'),allow_pickle=False)
  depth=data['depth'];support=data['valid'];old_pred=data['aligned'];old_overlap=data['overlap']
  old_transported_pred=sample(old_pred,transport_coords)
  old_transported_overlap=(sample(old_overlap.astype(float),transport_coords)>.999)&valid&transported_old_valid
  # Exact old fitted map in its actual source-center domain: preserve original
  # centers/parameters; evaluate old index positions at corrected physical points.
  cy,cx=np.mean(np.argwhere(support),axis=0);ry,rx=np.mean(np.argwhere(old_valid),axis=0)
  theta,dy,dx=old_row['best']['parameters'];flip=old_row['best']['flip'];angle=np.deg2rad(theta);c=np.cos(angle);s=np.sin(angle)
  sy=transport_coords[0]-ry;sx=transport_coords[1]-rx
  co=np.array([c*sy-s*flip*sx+cy+dy,s*sy+c*flip*sx+cx+dx])
  fixed_pred=sample(np.nan_to_num(depth),co);fixed_overlap=(sample(support.astype(float),co)>.999)&valid
  # Only the reference coordinate representation changes; helper and all its
  # registration settings remain those in the original frozen ordinary method.
  fit_result,new_pred,new_overlap=register(depth,support,reference,valid)
  common=old_transported_overlap&fixed_overlap&new_overlap&valid
  index_diagnostic=delta_masks(old_overlap,new_overlap,np.ones(shape,bool))
  physical_masks=delta_masks(old_transported_overlap,new_overlap,valid|transported_old_valid)
  row={'side':side,'original_frozen_result':{'mae_mm':old_row['mae_mm'],'coverage':old_row['coverage'],'overlap_n':old_row['overlap_pixels'],'transform':old_row['best']},'old_transport_metrics':metrics(old_transported_pred,reference,old_transported_overlap,valid),'fixed_old_transform_metrics':metrics(fixed_pred,reference,fixed_overlap,valid),'refit_metrics':metrics(new_pred,reference,new_overlap,valid),'refit_transform':fit_result['best'],'all_refit_search_alternatives':fit_result['alternatives'],'common_physical_grid':{'old_transported':metrics(old_transported_pred,reference,common,valid),'fixed_old_transform':metrics(fixed_pred,reference,common,valid),'refit':metrics(new_pred,reference,common,valid)},'mask_differences':{'same_index_only_not_physical':index_diagnostic,'common_physical_target_grid':physical_masks},'coordinate_only_interpretation':'Old transported and direct fixed-map differ by interpolation order; repaired reference/refit changes cannot be attributed solely to coordinate accuracy or physical measurement improvement.'}
  rows.append(row)
  np.savez_compressed(out/(side+'_fields.npz'),old_transported=old_transported_pred,old_transported_overlap=old_transported_overlap,fixed=fixed_pred,fixed_overlap=fixed_overlap,refit=new_pred,refit_overlap=new_overlap,common=common,depth=depth,support=support)
  plots.append((side,new_pred,new_overlap));write(out/(side+'_result.json'),row)
  print(json.dumps({'side':side,'refit_mae_mm':row['refit_metrics']['mae_mm'],'fixed_mae_mm':row['fixed_old_transform_metrics']['mae_mm'],'common_refit_mae_mm':row['common_physical_grid']['refit']['mae_mm'],'common_zero_mae_mm':row['common_physical_grid']['refit']['zero_plane_mae_mm_same_overlap']}),flush=True)
 # Validate all before/after source hashes: no original frozen artifact rewritten.
 after={item['path']:sha(old/item['path'])for item in manifest['files']}
 assert before==after and sha(old/'MANIFEST.json')==OLD_MANIFEST
 fig,axes=plt.subplots(2,3,figsize=(12,8),constrained_layout=True)
 for row,(side,pred,overlap)in enumerate(plots):
  axes[row,0].imshow(np.where(valid,reference,np.nan),vmin=-.3,vmax=.03);axes[row,0].set_title('Correct-center reference (mm)')
  axes[row,1].imshow(np.where(overlap,pred,np.nan),vmin=-.3,vmax=.03);axes[row,1].set_title('Ordinary refit '+side)
  im=axes[row,2].imshow(np.where(overlap,pred-reference,np.nan),vmin=-.1,vmax=.1,cmap='coolwarm');axes[row,2].set_title('Height disagreement (mm)')
  for ax in axes[row]:ax.axis('off')
 fig.colorbar(im,ax=axes[:,2]);fig.savefig(out/'corrected_comparison.png',dpi=130);plt.close(fig)
 record={'scope':'ORDINARY_COORDINATE_REPAIR_DEVELOPMENT_NOT_PHYSICAL_QUALIFICATION','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_sha256':sha(__file__),'protocol_sha256':PROTOCOL,'original_manifest_sha256':OLD_MANIFEST,'old_frozen_files_checked_unchanged':len(before),'ramps':ramps,'shape':list(shape),'reference_valid_n':int(valid.sum()),'reference_masks':{'same_index_only':delta_masks(old_valid,valid,np.ones(shape,bool)),'physical_target_grid':delta_masks(transported_old_valid,valid,np.ones(shape,bool))},'zero_plane_all_repaired_reference':metrics(np.zeros(shape),reference,valid,valid),'reference_transport_disagreement':metrics(transported_old_ref,reference,shared_reference,valid),'rows':rows,'resources':{'function_cpu_seconds':time.process_time()-start,'wall_seconds':time.monotonic()-wall,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'downloads':0,'complete_monetary_cost':None},'limits':['Relative computational origin, no calibrated absolute physical origin','No total physical error, true pore mask or internal-pore truth','Reference-assisted registration and all results exposed; no confirmation','No invention, baseline superiority, economic success or earnings claim']}
 write(out/'RESULT.json',record);print(json.dumps({'status':'COMPLETE_ORDINARY_REPAIR','resources':record['resources'],'ramp_max_errors_mm':[r['repaired_max_error_mm']for r in ramps]}),flush=True)

if __name__=='__main__':main()
