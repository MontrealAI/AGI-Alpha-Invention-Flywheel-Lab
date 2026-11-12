import os
for key in('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse,csv,hashlib,json,math,pathlib,resource,struct,time,zipfile
from fractions import Fraction
import numpy as np
from scipy import ndimage
from PIL import Image
EXPECTED_MANIFEST='60a275fcf18a4a01e44fed5ac12c6260052125bdc214eaa64f4818ee549b9033'
CT_SPACING=.0258478
PROFILE_SPACING=.0074
STRATA=[(-np.inf,-.1),(-.1,-.03),(-.03,-.01),(-.01,np.inf)]
def sha(path):
 h=hashlib.sha256()
 with pathlib.Path(path).open('rb')as stream:
  for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
 return h.hexdigest()
def read(path):return json.loads(pathlib.Path(path).read_text())
def write(path,x):
 with pathlib.Path(path).open('x')as stream:json.dump(x,stream,indent=2,allow_nan=False);stream.write('\n')
def mean(values):return math.fsum(map(float,values))/len(values)if len(values)else None
def close(a,b):return a is None and b is None or a is not None and b is not None and abs(float(a)-float(b))<=1e-12
def main():
 p=argparse.ArgumentParser();p.add_argument('--package',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();base=a.package.resolve();a.output.mkdir(parents=True,exist_ok=False);start=time.process_time();wall=time.monotonic();manifest=read(base/'MANIFEST.json');checks={'pinned_manifest':sha(base/'MANIFEST.json')==EXPECTED_MANIFEST}
 for item in manifest['files']:
  rel=pathlib.Path(item['path'])
  if rel.is_absolute()or'..'in rel.parts:raise ValueError('manifest path')
  checks['file_'+item['path']]=(base/rel).is_file()and(base/rel).stat().st_size==item['bytes']and sha(base/rel)==item['sha256']
 if not all(checks.values()):write(a.output/'REFUSAL.json',checks);raise ValueError('frozen package changed')
 protocol=read(base/'PROTOCOL.json');chronology=read(base/'CHRONOLOGY.json');intake=read(base/'INTAKE.json');ordinary=read(base/'ORDINARY_RESULT.json');refined=read(base/'REFINED_RESULT.json');coverage=read(base/'STRATIFIED_COVERAGE.json');plane=read(base/'PLANE_COMPARATOR.json');profile=np.load(base/'profile.npy',mmap_mode='r',allow_pickle=False);ct=np.load(base/'ct.npy',mmap_mode='r',allow_pickle=False)
 checks['native_array_contracts']=profile.shape==(3259,3195)and profile.dtype==np.float64 and ct.shape==(931,234,902)and ct.dtype==np.uint8
 with zipfile.ZipFile(base/'TTT_AM_315400_profilometry.zip')as archive:
  names=[name for name in archive.namelist()if name=='disk_profilometry_top_height_image.tif']
  if len(names)!=1:raise ValueError('height TIFF not unique')
  raw=archive.read(names[0])
 if raw[:2]!=b'II'or struct.unpack_from('<H',raw,2)[0]!=42:raise ValueError('unsupported source TIFF')
 offset=struct.unpack_from('<I',raw,4)[0];count=struct.unpack_from('<H',raw,offset)[0];tags={}
 for i in range(count):
  pos=offset+2+12*i;tag,kind,n,value=struct.unpack_from('<HHII',raw,pos)
  if kind in(3,4):
   size={3:2,4:4}[kind];payload=raw[pos+8:pos+12]if n*size<=4 else raw[value:value+n*size];tags[tag]=struct.unpack('<'+{3:'H',4:'I'}[kind]*n,payload[:n*size])
 checks['source_TIFF_contract']=tags[256]==(3195,)and tags[257]==(3259,)and tags[258]==(64,)and tags[259]==(1,)and tags[339]==(3,)and len(tags[273])==1 and tags[279]==(3259*3195*8,)
 decoded=np.frombuffer(raw,dtype='<f8',count=3259*3195,offset=tags[273][0]).reshape(3259,3195);checks['native_profile_bits_match_source_TIFF']=bool(np.array_equal(np.asarray(profile).view(np.uint64),decoded.view(np.uint64)));del decoded,raw
 finite_count=zero_count=grid_count=0;max_scaled_residual=0.
 for row in range(0,profile.shape[0],128):
  block=np.asarray(profile[row:row+128]);values=block[np.isfinite(block)];finite_count+=len(values);zero_count+=int(np.count_nonzero(values==0));grid_count+=int(np.count_nonzero(values==np.rint(values*100)/100));max_scaled_residual=max(max_scaled_residual,float(np.max(abs(values*100-np.rint(values*100))))if len(values)else 0.)
 quantization={'finite_native_values':finite_count,'zero_native_values':zero_count,'zero_fraction':zero_count/finite_count,'stored_decimal_centroid_equal_count':grid_count,'grid_mm':.01,'max_scaled_centroid_rounding_residual':max_scaled_residual,'scope':'Consistency with10um decimal-level exported quantization only; rounding rule and total physical error remain unknown.'};checks['finite_count_matches_intake']=finite_count==intake['profile']['finite_count'];checks['all_values_at_decimal_10um_centroids']=grid_count==finite_count
 with Image.open(base/'TTT_AM_315400_low_res.tif')as image:
  description=str(image.tag_v2.get(270));header_spacing=float(description.split('spacing=')[1].split('\n')[0]);checks['CT_header_spacing']=header_spacing==CT_SPACING;checks['CT_header_stack']=image.n_frames==931 and image.size==(902,234)
 s=np.load(base/'profile_at_ct_spacing.npz',allow_pickle=False);ref=s['reference'];valid=s['valid'];finite=np.isfinite(profile);factor=PROFILE_SPACING/CT_SPACING;numerator=ndimage.zoom(np.where(finite,profile,0),factor,order=1);denominator=ndimage.zoom(finite.astype(np.float32),factor,order=1);expected_valid=denominator>.999;expected_ref=numerator/np.maximum(denominator,1e-20);expected_ref[~expected_valid]=np.nan
 checks['resampled_reference_shape']=ref.shape==(933,915)and valid.shape==ref.shape;checks['saved_reference_matches_documented_resampling']=bool(np.array_equal(valid,expected_valid))and bool(np.array_equal(ref,expected_ref,equal_nan=True));checks['valid_reference_is_finite']=bool(np.all(np.isfinite(ref[valid])))and int(valid.sum())==547749
 del finite,numerator,denominator,expected_ref,expected_valid
 coordinate=[]
 for axis,native in enumerate(profile.shape):
  ramp=np.arange(native,dtype=float)*PROFILE_SPACING;resampled=ndimage.zoom(ramp,factor,order=1);nominal=(len(resampled)-1)*CT_SPACING;actual=float(resampled[-1]-resampled[0]);coordinate.append({'axis':axis,'native_count':native,'output_count':len(resampled),'nominal_output_spacing_mm':CT_SPACING,'effective_zoom_center_spacing_mm':actual/(len(resampled)-1),'far_endpoint_discrepancy_mm':actual-nominal,'direct_ramp_end_matches_native_span':abs(actual-(native-1)*PROFILE_SPACING)<1e-12})
 coord_defect=any(abs(x['far_endpoint_discrepancy_mm'])>1e-8 for x in coordinate)
 hist=intake['ct']['histogram'];checks['histogram_count']=sum(hist)==int(np.prod(ct.shape));nt=sum(hist);total=sum(i*v for i,v in enumerate(hist));left=sleft=0;best=None;best_t=None
 for t in range(255):
  left+=hist[t];sleft+=t*hist[t]
  if left and left<nt:
   score=Fraction((total*left-sleft*nt)**2,left*(nt-left))
   if best is None or score>best:best,best_t=score,t
 checks['ordinary_threshold_is_full_volume_Otsu']=all(r['threshold']==best_t for block in [ordinary,refined]for r in block['results'])
 rows=[];arrays={};strata_total=[int(np.count_nonzero(valid&(ref>=lo)&(ref<hi)))for lo,hi in STRATA]
 for version,receipt in [('v1',ordinary),('refined',refined)]:
  for side in ['min','max']:
   item=next(x for x in receipt['results']if x['side']==side);file=base/(f'ordinary_registered_{side}.npz'if version=='v1'else f'refined_{side}.npz');z=np.load(file,allow_pickle=False);pred=z['aligned'];overlap=z['overlap'];good={'mask_subset_of_reference':overlap.shape==valid.shape and bool(np.all(~overlap|valid)),'finite_predictions_on_overlap':bool(np.all(np.isfinite(pred[overlap])))}
   error=pred[overlap]-ref[overlap];mae=mean(abs(error));zero=mean(abs(ref[overlap]));good.update({'overlap_count_matches':int(overlap.sum())==item['overlap_pixels'],'coverage_matches':close(overlap.sum()/valid.sum(),item['coverage']),'MAE_matches':close(mae,item['mae_mm']),'bias_matches':close(mean(error),item['bias_mm']),'RMS_matches':close(math.sqrt(mean(error*error)),item['rms_mm'])})
   native=np.load(base/f'ordinary_depth_{side}.npz',allow_pickle=False)if version=='v1'else z;depth=native['depth'];source_valid=native['valid'];cy,cx=np.mean(np.argwhere(source_valid),axis=0);ry,rx=np.mean(np.argwhere(valid),axis=0);yy,xx=np.indices(ref.shape,dtype=float);theta,dy,dx=item['best']['parameters'];flip=item['best']['flip'];angle=np.deg2rad(theta);co=np.array([np.cos(angle)*(yy-ry)-np.sin(angle)*flip*(xx-rx)+cy+dy,np.sin(angle)*(yy-ry)+np.cos(angle)*flip*(xx-rx)+cx+dx]);rebuild=ndimage.map_coordinates(np.nan_to_num(depth),co,order=1,mode='constant',cval=0);support=ndimage.map_coordinates(source_valid.astype(float),co,order=1,mode='constant',cval=0)>.999;good['reported_rigid_transform_rebuilds_predictions']=bool(np.max(abs(rebuild-pred))<1e-12);good['overlap_rebuilds_from_source_support_only']=bool(np.array_equal(overlap,valid&support));strata=[];declared_coverage=next(x for x in coverage['rows']if x['version']==version and x['side']==side)
   for i,(lo,hi)in enumerate(STRATA):
    mask=overlap&(ref>=lo)&(ref<hi);e=pred[mask]-ref[mask];count=int(mask.sum());entry=item['depth_strata'][i];m=mean(abs(e));declared_count=entry.get('n',entry.get('pixels'));good[f'stratum{i}_counts_and_MAE']=count==declared_count and close(m,entry['mae_mm']);cov=declared_coverage['strata'][i];good[f'stratum{i}_coverage']=cov['reference_finite_pixels']==strata_total[i]and cov['overlap_pixels']==count and close(cov['coverage'],count/strata_total[i]);strata.append({'reference_interval_mm':[str(lo),str(hi)],'all_reference_pixels':strata_total[i],'overlap_pixels':count,'coverage':count/strata_total[i],'MAE_mm':m,'zero_plane_MAE_mm':mean(abs(ref[mask]))})
   record={'version':version,'side':side,'record_sha256':sha(file),'overlap':int(overlap.sum()),'coverage':overlap.sum()/valid.sum(),'MAE_mm':mae,'zero_plane_MAE_same_overlap_mm':zero,'zero_plane_wins_primary':zero<mae,'strata':strata,'checks':good};rows.append(record);arrays[(version,side)]=(pred,overlap);write(a.output/(version+'_'+side+'.json'),record)
 plane_checks={};plane_rows={r['scope']:r for r in plane['results']}
 for name,mask in [('all_reference_valid',valid),('v1_max_overlap',arrays[('v1','max')][1]),('refined_max_overlap',arrays[('refined','max')][1])]:
  r=plane_rows[name];plane_checks[name]=r['n']==int(mask.sum())and close(r['coverage'],mask.sum()/valid.sum())and close(r['mae_mm'],mean(abs(ref[mask])))
 checks['zero_plane_receipt_reproduces']=all(plane_checks.values());common={}
 for side in ['min','max']:
  x,m=arrays[('v1',side)];z,n=arrays[('refined',side)];mask=m&n;common[side]={'common_pixels':int(mask.sum()),'v1_MAE_mm':mean(abs(x[mask]-ref[mask])),'refined_MAE_mm':mean(abs(z[mask]-ref[mask])),'zero_plane_MAE_mm':mean(abs(ref[mask]))}
 all_math=all(checks.values())and all(all(r['checks'].values())for r in rows);final={'schema':'agi-alpha-independent-NASA-metric-review008/v1','scope':'Exposed frozen saved-array arithmetic/coordinate audit, no candidate import or segmentation/registration reoptimization','manifest_sha256':EXPECTED_MANIFEST,'verifier_source_sha256':sha(__file__),'checks':checks,'all_reported_math_and_reconstruction_checks_pass':all_math,'quantization':quantization,'coordinate_ramp_witnesses':coordinate,'nominal_target_spacing_inconsistent_with_zoom_center_grid':coord_defect,'rows':rows,'common_overlap_diagnostic':common,'findings':['Featureless zero plane beats all-field MAE on identical overlaps; this primary endpoint cannot establish pore identification.','Deep diagnostic stratum loses nearly half of original reference points despite high aggregate coverage.','Default endpoint-aligned zoom does not produce exactly the declared CT-spacing grid after output-count rounding; ramp witness measures only processing XY discrepancy, not height impact or physical uncertainty.','Both reference-assisted registration and version/face selection are exposed; no protected/reference-independent accuracy is established.','Exported10um level quantization and nominal voxel spacing are not calibrated error envelopes or hard accuracy bounds.'],'limits':['No true pore labels, internal geometry, unseen specimens or independent calibration/registration uncertainty.','Diagnostic depth strata and common-overlap analysis do not replace the frozen primary endpoint or create a new customer cohort.','The grid mismatch does not establish how much of observed height error it caused; candidate remains unchanged.','No method novelty, strongest-complete-baseline superiority, demand, profit, earned funds or mission success.','Procedural separate reviewer sharing numerical libraries/host/model family; alpha0 and no external certification.'],'resources':{'cpu_seconds':time.process_time()-start,'wall_seconds':time.monotonic()-wall,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}}
 write(a.output/'REPORT.json',final);print(json.dumps({'reported_math_verified':all_math,'Otsu_threshold':best_t,'coordinate_ramp':coordinate,'native_zero_fraction':quantization['zero_fraction'],'common_overlap':common,'resources':final['resources']}));raise SystemExit(0 if all_math else 1)
if __name__=='__main__':main()
