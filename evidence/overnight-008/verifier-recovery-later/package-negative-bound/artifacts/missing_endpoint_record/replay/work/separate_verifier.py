import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse,datetime,hashlib,json,math,pathlib,resource,time
from fractions import Fraction as Q
import numpy as np
import scipy
from scipy.io import loadmat
EXPECTED_PROTOCOL='7eb2d4efb7ba71bdda25695f95db2b73fcbed4943dd71cfcaa98a4d55954e58e'
BITS=2148

def sha(path):return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(pathlib.Path(path).read_text())
def fraction(value):return Q.from_float(float(value))
def write(path,value):
 with pathlib.Path(path).open('x')as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
def rational(value):return {'numerator':str(value.numerator),'denominator':str(value.denominator)}
def honor_limit(kind,ceiling):
 soft,hard=resource.getrlimit(kind);hard=ceiling if hard==resource.RLIM_INFINITY else min(hard,ceiling);soft=hard if soft==resource.RLIM_INFINITY else min(soft,hard);resource.setrlimit(kind,(soft,hard))
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--base',type=pathlib.Path,required=True);parser.add_argument('--records',type=pathlib.Path,required=True);parser.add_argument('--output',type=pathlib.Path,required=True);args=parser.parse_args();base=args.base.resolve();records=args.records.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);started=time.process_time();wall=time.monotonic()
 honor_limit(resource.RLIMIT_CPU,180);honor_limit(resource.RLIMIT_AS,2<<30)
 protocol_path=base/'PROTOCOL.json';protocol=read(protocol_path);freeze=read(records/'FREEZE.json');report=read(records/'RESULTS.json');checks={'independently_pinned_protocol':sha(protocol_path)==EXPECTED_PROTOCOL,'constructor_finished':report['status']in('FULL120_PAIR_OBSTRUCTION','UNKNOWN_NO_ACCEPTED_OBSTRUCTION'),'same_new_edition':report['edition']==protocol['edition']==freeze['edition']}
 for name,digest in protocol['frozen_files'].items():
  relative=pathlib.Path(name)
  if relative.is_absolute()or'..'in relative.parts:raise ValueError('unsafe model path')
  checks['frozen_'+name]=sha(base/relative)==digest
 checks['constructor_freeze_matches_protocol']=freeze['protocol_sha256']==EXPECTED_PROTOCOL and freeze['source_sha256']==protocol['frozen_files']['construct.py'] and freeze['helper_sha256']==protocol['frozen_files']['exact_feasibility.py'] and freeze['frozen_files']==protocol['frozen_files']
 required=['reference.npy','eps_full.npy','objective.npy','direct_lo.npy','direct_hi.npy','pdhg_lo.npy','pdhg_hi.npy','REFERENCE_CHECK.json','PDHG_lo.json','PDHG_hi.json']
 checks['all_required_records_present']=all((records/name).is_file()for name in required)
 if not all(checks.values()):write(out/'REFUSAL.json',{'checks':checks,'reason':'incomplete or changed source/model/result'});raise ValueError('incomplete or changed source/model/result')
 data=loadmat(base/'data/Data82.mat');A=data['A'].tocsr();measurements=data['m'];y=measurements.ravel(order='F');checks['full_nonnegative_canonical_matrix']=A.shape==(9840,6724)and A.nnz==970344 and measurements.shape==(82,120)and bool(np.all(np.isfinite(A.data)))and bool(np.all(A.data>=0))and bool(A.has_canonical_format)and bool(np.all(np.isfinite(y)))
 cal=read(base/'model/CALIBRATION.json');reference=np.load(base/'model/reference.npy',allow_pickle=False);eps_detector=np.load(base/'model/eps.npy',allow_pickle=False);objective=np.load(base/'model/objective.npy',allow_pickle=False);checks['model_array_shapes']=reference.shape==(6724,)and eps_detector.shape==(82,)and objective.shape==(6724,)
 fbp=loadmat(base/'data/GroundTruthReconstruction.mat')['FBP1200'];checks['raw_reference_contract']=fbp.shape==(2296,2296)and fbp.dtype==np.uint16
 raw=fbp.astype(float).reshape(82,28,82,28).mean((1,3)).ravel(order='F')/65535;scale,offset=cal['affine_parameters'];reconstructed=np.maximum(scale*raw+offset,0);eps_expected=1.05*np.max(abs((A@reconstructed-y).reshape(82,120,order='F')),axis=1)+1e-6;c=np.zeros((82,82));c[38:44,38:44]=1/36;c=c.ravel(order='F')
 checks['reference_reconstructs_from_frozen_affine_parameters']=bool(np.array_equal(reference,reconstructed));checks['detector_envelope_rule_reconstructs']=bool(np.array_equal(eps_detector,eps_expected));checks['fixed_roi_objective_exact']=bool(np.array_equal(objective,c));checks['positive_finite_detector_envelope']=bool(np.all(np.isfinite(eps_detector)))and bool(np.all(eps_detector>=0));eps=np.tile(eps_detector,120)
 checks['run_copied_model_arrays_match']=bool(np.array_equal(np.load(records/'reference.npy',allow_pickle=False),reference))and bool(np.array_equal(np.load(records/'eps_full.npy',allow_pickle=False),eps))and bool(np.array_equal(np.load(records/'objective.npy',allow_pickle=False),objective))
 if not all(checks.values()):write(out/'REFUSAL.json',{'checks':checks,'reason':'model reconstruction mismatch'});raise ValueError('model reconstruction mismatch')
 yq=[fraction(v)for v in y];eq=[fraction(v)for v in eps];nonzero=[j for j,v in enumerate(c)if v];cq={j:fraction(c[j])for j in nonzero};verified={};records_check={}
 for label in ['reference','direct_lo','direct_hi','pdhg_lo','pdhg_hi']:
  path=records/(label+'.npy');x=np.load(path,allow_pickle=False);valid_shape=x.shape==(6724,)and bool(np.all(np.isfinite(x)))
  if not valid_shape:raise ValueError('witness shape/nonfinite: '+label)
  xq=[fraction(v)for v in x];minimum=None
  for row in range(9840):
   left,right=A.indptr[row:row+2];value=sum((fraction(A.data[k])*xq[int(A.indices[k])]for k in range(left,right)),Q(0));margin=eq[row]-abs(value-yq[row]);minimum=margin if minimum is None else min(minimum,margin)
  nonnegative=bool(np.all(x>=0));feasible=nonnegative and minimum>=0;roi=sum((cq[j]*xq[j]for j in nonzero),Q(0));expected=read(records/'REFERENCE_CHECK.json')if label=='reference'else report['control'if label.startswith('direct')else'pdhg'][label.rsplit('_',1)[1]]
  matching={'feasibility_matches':expected['feasible']is feasible,'nonnegative_matches':expected['nonnegative']is nonnegative,'exact_margin_matches':minimum==Q(int(expected['exact_min_ray_margin_numerator']),1<<expected['denominator_power']),'exact_roi_matches':roi==Q(int(expected['roi_numerator']),1<<expected['denominator_power']),'all_original_inequalities_reported':expected['inequalities_checked']==19680,'margin_outward_lower':fraction(expected['min_ray_margin_float_lower'])<=minimum,'roi_outward_lower':fraction(expected['roi_float_lower'])<=roi}
  if label.startswith('pdhg'):matching['endpoint_record_matches_result']=read(records/('PDHG_'+label.rsplit('_',1)[1]+'.json'))==expected
  item={'array_sha256':sha(path),'verified_feasible':feasible,'nonnegative':nonnegative,'exact_minimum_margin':rational(minimum),'exact_roi':rational(roi),'checks':matching,'record_integrity':all(matching.values())};verified[label]={'feasible':feasible,'roi':roi};records_check[label]=item;write(out/(label+'.json'),item)
 routes={}
 for name,prefix in [('ordinary_direct','direct'),('ordinary_pdhg','pdhg')]:
  lo=verified[prefix+'_lo'];hi=verified[prefix+'_hi'];gap=hi['roi']-lo['roi'];actual=lo['feasible']and hi['feasible']and gap>Q(1,200);block=report['control'if prefix=='direct'else'pdhg'];matching={'reported_gap_lower':fraction(block['gap_float_lower'])<=gap}
  if prefix=='pdhg':matching['reported_threshold_exact']=block['exact_gap_exceeds_1_over_200']is(gap>Q(1,200))
  routes[name]={'both_witnesses_exactly_feasible':lo['feasible']and hi['feasible'],'exact_gap':rational(gap),'gap_float':float(gap),'gap_exceeds_1_over_200':gap>Q(1,200),'obstruction_verified':actual,'checks':matching}
 checks['final_status_matches_independent_result']=(report['status']=='FULL120_PAIR_OBSTRUCTION')is routes['ordinary_pdhg']['obstruction_verified'];accepted=all(checks.values())and all(x['record_integrity']for x in records_check.values())and all(all(x['checks'].values())for x in routes.values());verdict='FULL120_MODEL_OBSTRUCTION_VERIFIED'if accepted and routes['ordinary_pdhg']['obstruction_verified']else'UNKNOWN_NO_ACCEPTED_OBSTRUCTION'
 final={'schema':'agi-alpha-independent-xct-recovery-fraction008/v1','current_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'edition':protocol['edition'],'scope':'Exact original full120 inequalities of newly reconstructed binary64 mathematical model only','checks':checks,'records':records_check,'routes':routes,'artifact_integrity_verified':accepted,'verdict':verdict,'input_freeze_sha256':sha(records/'FREEZE.json'),'constructor_results_sha256':sha(records/'RESULTS.json'),'protocol_sha256':EXPECTED_PROTOCOL,'verifier_source_sha256':sha(__file__),'versions':{'numpy':np.__version__,'scipy':scipy.__version__},'timeline':'Criteria fixed by root/protocol before construction; verifier source completed after builder summary exposure. Deterministic exposed engineering review, not protected confirmation.','limits':['No candidate helper imported. Every original ray is recomputed independently with Fraction.','Calibration reconstruction uses frozen fitted parameters; optimizer/global calibration quality or physical coverage is not independently validated.','All120 measurement views and1200-view reference are exposed; no acquisition saving.','New calibration bytes, not recovery of lost historical arrays or their exact proof.','Ordinary PDHG and equal-content reuse remain existing alternatives; no method novelty or inheritance advantage established.','No physical material validity, industrial tolerance, buyer demand, profit or earned-funded successor acceptance.','Shared model family/host and numerical libraries; procedural separation, not external certification.','Alpha0; no protected or population-inference claim.'],'resources':{'cpu_seconds':time.process_time()-started,'wall_seconds':time.monotonic()-wall,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}}
 write(out/'REPORT.json',final);print(json.dumps({'artifact_integrity_verified':accepted,'verdict':verdict,'routes':routes,'resources':final['resources']}));raise SystemExit(0 if accepted else 1)
if __name__=='__main__':main()
