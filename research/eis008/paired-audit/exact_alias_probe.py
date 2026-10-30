import argparse,datetime,hashlib,json,resource,time
from pathlib import Path
import numpy as np
from scipy.io import loadmat

ROOT=Path(__file__).resolve().parent
EXPECTED_PROTOCOL='f823d05d40e14ee039bd4c738cb9ded02cc05a8251e61609608888b255236faa'
EXPECTED_DATA='8f02b75054e3cf8e337a3c196f8b330ea740b698902bd38639e9536583af855b'
def canonical(a):
 b=np.array(a,dtype='<f8',order='C',copy=True);b[b==0]=0.;return b
def group_view(x,y):
 x=canonical(x);groups={};digests=[]
 for j,a in enumerate(x):
  h=hashlib.sha256(a.tobytes(order='C')).hexdigest();digests.append(h);groups.setdefault(h,[]).append(j)
 duplicates=[];conflicting=[]
 for h,ids in groups.items():
  if len(ids)<2:continue
  if any(not np.array_equal(x[ids[0]],x[k]) for k in ids[1:]):raise ValueError('SHA_COLLISION_NOT_EXACT_VALUE_GROUP')
  z=y[ids,:,0]+1j*y[ids,:,1];same=all(np.array_equal(y[ids[0]],y[k]) for k in ids[1:]);diameter=0.
  for j in range(0,len(ids),32):diameter=max(diameter,float(np.max(np.abs(z[j:j+32,None,:]-z[None,:,:]))))
  record={'input_sha256':h,'record_ids_zero_based':ids,'full_label_vectors_exactly_equal':same,'maximum_complex_label_component_diameter_released_units':diameter,'physical_noise_or_materiality_threshold':None,'physical_system_identity_equal_established':False}
  duplicates.append(record)
  if not same:conflicting.append(dict(record,full_labels=y[ids].tolist()))
 return {'records':len(x),'unique_input_groups':len(groups),'duplicate_groups':len(duplicates),'duplicate_pairs':sum(len(v)*(len(v)-1)//2 for v in groups.values() if len(v)>1),'conflicting_label_groups':len(conflicting),'recorded_alias_witness_established':bool(conflicting),'physical_underidentification_established':False,'material_spectral_difference_established':False,'source_record_digests':digests,'all_duplicate_groups':duplicates,'conflicting_groups_with_full_labels':conflicting}
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args();begin=time.monotonic();out=Path(args.output).resolve()
 if out.exists():raise FileExistsError('Refusing overwrite '+str(out))
 out.mkdir(parents=True)
 protocol=(ROOT/'PROTOCOL.json').read_bytes()
 if hashlib.sha256(protocol).hexdigest()!=EXPECTED_PROTOCOL:raise ValueError('FROZEN_PROTOCOL_CHANGED')
 data=(ROOT/'dataset4_final_split82_index.mat').read_bytes()
 if hashlib.sha256(data).hexdigest()!=EXPECTED_DATA:raise ValueError('FROZEN_COHORT_CHANGED')
 d=loadmat(ROOT/'dataset4_final_split82_index.mat',verify_compressed_data_integrity=True);x=d['X'];y=d['Y1'];index=d['final_split82_index'].ravel()
 if x.shape!=(828,10,180) or y.shape!=(828,38,2) or not np.isfinite(x).all() or not np.isfinite(y).all():raise ValueError('COMPLETE_FINITE_FROZEN_RECORDS_REQUIRED')
 if not np.array_equal(np.sort(index),np.arange(828)):raise ValueError('SOURCE_INDEX_NOT_ZERO_BASED_PERMUTATION')
 views={'published9x100':np.transpose(x[:,:9,80:180],(0,2,1)),'all10x180':x}
 results={name:group_view(a,y) for name,a in views.items()}
 summary={name:{k:v for k,v in a.items() if k not in {'source_record_digests','all_duplicate_groups','conflicting_groups_with_full_labels'}} for name,a in results.items()}
 report={'executed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'protocol_sha256':EXPECTED_PROTOCOL,'data_sha256':EXPECTED_DATA,'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'cohort_records':828,'all_records_retained':True,'source_split_index_retained_but_not_used_for_selection':True,'canonical_signed_zero_only':True,'rounding_or_near_input_equivalence_used':False,'results':summary,'physical_timing_alignment':'UNKNOWN: source X/Y row pairing is asserted and indexed in released code; mapping to original acquisition clocks not independently reconstructed','repeatability_noise_bounds':'UNKNOWN: stack/cell positions are different systems, not repeat measurements; no fit residual used as calibration','new_measurement_means_admitted':False,'all_data_development':True,'confirmation_alpha_spent':0,'decision':'No automatic scientific or commercial admission; inspect exact recorded results with source identity/timing confounders','wall_seconds':time.monotonic()-begin,'cpu_seconds':resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
 (out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n');(out/'EXACT_GROUPS.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
