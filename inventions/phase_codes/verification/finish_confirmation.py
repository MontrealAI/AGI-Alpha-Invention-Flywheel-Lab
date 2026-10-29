"""Independent frozen-candidate implementation probe; never normalizes recovery output."""
import argparse,hashlib,json,math,pathlib,sys,time,resource,itertools,importlib.util
import numpy as np
import process_core as P

def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def local(state,n,q,matrix):
 out={};mask=1<<(n-1-q)
 for w,a in state.items():
  b=int(bool(w&mask))
  for t in (0,1):
   v=matrix[t,b]*a
   if v!=0:
    z=(w&~mask)|(t*mask);out[z]=out.get(z,0)+v
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repo','--lab-root',dest='repo',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
 out=pathlib.Path(a.output);out.mkdir(exist_ok=False,parents=True);repo=pathlib.Path(a.repo);here=pathlib.Path(__file__).parent
 start=time.monotonic();cpu=time.process_time()
 freeze=json.loads((repo/'campaign/cycle-004/CANDIDATE_FREEZE.json').read_text());vf=json.loads((here/'VERIFIER_FREEZE.json').read_text())
 for name,digest in freeze['source_sha256'].items():
  if sha(repo/name)!=digest:raise ValueError('BUILDER_FROZEN_SOURCE_CHANGED:'+name)
 for name,digest in vf['files'].items():
  if sha(here/name)!=digest:raise ValueError('VERIFIER_FROZEN_SOURCE_CHANGED:'+name)
 candidate=repo/freeze['candidate'];raw=json.loads(candidate.read_text());runtime=load('SUT_runtime',repo/'inventions/phase_codes/runtime.py');encoder=load('SUT_encoder',repo/'inventions/phase_codes/encoder.py')
 m=runtime.Instrument(candidate,freeze['candidate_sha256']);n=raw['n']
 I=np.eye(2,dtype=complex);X=np.array([[0,1],[1,0]],complex);Y=np.array([[0,-1j],[1j,0]],complex);Z=np.diag([1,-1]).astype(complex)
 angle=math.pi/7;axis=(X+2*Y+3*Z)/math.sqrt(14);rotation=math.cos(angle/2)*I-1j*math.sin(angle/2)*axis
 cases=[('no_fault',None,[I])]
 for q in range(n):
  cases.extend([(f'{name}_q{q}',q,[matrix]) for name,matrix in [('X',X),('Y',Y),('Z',Z),('coherent_pi_over7',rotation)]])
  for gamma in (0,1/5,2/3,1):
   cases.append((f'amplitude_damping_q{q}_gamma{gamma}',q,[np.diag([1,math.sqrt(1-gamma)]).astype(complex),np.array([[0,math.sqrt(gamma)],[0,0]],complex)]))
 reports=[]
 for before in (False,True):
  for label,q,kraus in cases:
   losses=[];prob=[]
   def channel(v):
    state=m.encode(v)
    if not before:state=m.phase(state)
    branches=[dict(state)] if q is None else [local(state,n,q,k) for k in kraus]
    if before:branches=[m.phase(s) for s in branches]
    r=m.recover(branches);losses.append(r['unrecovered_probability']);prob.append(r['input_probability']);return r['logical_density']
   r=P.analyze(channel);r.update(label=label,before_gate=before,maximum_unrecovered_probability=max(losses),maximum_input_probability_error=max(abs(x-1) for x in prob))
   r['passed']=r['passed'] and r['maximum_input_probability_error']<=P.TOL and r['maximum_unrecovered_probability']<=P.TOL
   reports.append(r)
 (out/'PROCESS_CASES.json').write_text(json.dumps(reports,indent=2)+'\n')
 # Negative controls are never candidate repairs or additional success requirements.
 negatives={}
 def lossy(v):
  state=local(m.phase(m.encode(v)),n,0,X)
  coeff=np.array([sum(np.conjugate(x)*state.get(w,0) for w,x in b.items()) for b in m.basis]);return np.outer(coeff,coeff.conj())
 negatives['Vdagger_without_recovery_single_X']=P.analyze(lossy)
 negatives['uncoded_input_ignoring_logical']=P.analyze(lambda v:m.recover([{0:1+0j}])['logical_density'])
 negatives['basis_preserving_dephasing']=P.analyze(lambda v:np.diag(np.abs(P.U@v)**2))
 negatives['wrong_relative_phase']=P.analyze(lambda v:np.outer(v,v.conj()))
 negatives['lossy_hidden_postselection']=P.analyze(lambda v:(lambda w:np.outer(w,w.conj())/np.vdot(w,w))((np.diag([1,1,1,.1])@P.U)@v))
 two=[];v=np.ones(4,complex)/2;target=P.U@v
 for q,r in itertools.combinations(range(n),2):
  state=local(local(m.phase(m.encode(v)),n,q,X),n,r,X);rec=m.recover([state]);density=rec['logical_density']
  two.append(dict(qubits=[q,r],logical_fidelity=float(np.vdot(target,density@target).real),trace=float(np.trace(density).real),unrecovered_probability=rec['unrecovered_probability']))
 negatives['outside_contract_two_X_errors']={'scope':'Exploratory boundary probe, not a guaranteed-correctable channel','cases':two,'minimum_logical_fidelity':min(t['logical_fidelity'] for t in two)}
 (out/'NEGATIVE_CONTROLS.json').write_text(json.dumps(negatives,indent=2)+'\n')
 # Independently compare actual circuit amplitudes and explicitly erase helpers.
 numeric=repo/'inventions/phase_codes/artifacts/controlled_s15_numeric.json';num=json.loads(numeric.read_text())
 if sha(numeric)!=raw['source_numeric_sha256']:raise ValueError('NUMERIC_LINK_CHANGED')
 alphas=[np.array([1,0,0,0],complex),np.array([0,0,0,1],complex),np.array([1,1j,-2+3j,math.sqrt(7)],complex),np.array([1,0,0,1j],complex)]
 encoderreports=[]
 from fractions import Fraction
 for idx,alpha in enumerate(alphas):
  alpha/=np.linalg.norm(alpha);r,support=encoder.simulate_native(candidate,alpha);actual={};bad=0.;physicalnorm=0.
  for (logical,word),amp in support.items():
   measured=sum(((word&mask).bit_count()%2)<<j for j,mask in enumerate(num['color_masks']))
   helper=logical^measured
   key=(helper,word);actual[key]=actual.get(key,0)+amp;physicalnorm+=abs(amp)**2
   if helper:bad+=abs(amp)**2
  expected={}
  for j,c in enumerate(raw['codewords']):
   for word,p in c['probabilities'].items():expected[(0,int(word,2))]=alpha[j]*math.sqrt(float(Fraction(p)))
  err=math.sqrt(sum(abs(actual.get(w,0)-expected.get(w,0))**2 for w in actual.keys()|expected.keys()))
  r.update(independent_probe_index=idx,independent_full_state_L2_error=err,independent_helper_failure_probability=bad,independent_physical_state_norm=physicalnorm)
  r['independent_passed']=bool(err<=1e-10 and bad<=1e-10 and abs(physicalnorm-1)<=1e-10)
  encoderreports.append(r)
 (out/'ENCODER_CASES.json').write_text(json.dumps(encoderreports,indent=2)+'\n')
 summary={'status':'PASS' if all(r['passed'] for r in reports) and all(r['independent_passed'] for r in encoderreports) and all(not negatives[k]['passed'] for k in negatives if k!='outside_contract_two_X_errors') else 'FAIL','candidate_sha256':freeze['candidate_sha256'],'process_cases':len(reports),'normalized_probes_per_process_case':19,'before_and_after_gate':True,'process_failures':[{'label':r['label'],'before_gate':r['before_gate']} for r in reports if not r['passed']],'worst_process_matrix_error':max(r['normalized_Choi_matrix_error'] for r in reports),'worst_entanglement_infidelity':max(abs(1-r['entanglement_fidelity']) for r in reports),'native_encoder_probes':len(encoderreports),'worst_encoder_L2_error':max(r['independent_full_state_L2_error'] for r in encoderreports),'minimum_outside_contract_two_X_fidelity':min(t['logical_fidelity'] for t in two),'negative_controls_all_rejected':all(not negatives[k]['passed'] for k in negatives if k!='outside_contract_two_X_errors'),'cpu_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'scope':'Procedurally independent probes on shared host. Exact algebra and finite ideal implementation checks only. Not physical noisy encoding/recovery, circuit threshold, global novelty, overall cost or commercial validation.','helper_initialization':'Two helper wires initially carry arbitrary coherent logical input; they are zero after erase. They are not initially clean ancillas.','frozen_builder_source_sha256':freeze['source_sha256'],'frozen_verifier_source_sha256':vf['files'],'confirmation_driver_sha256':sha(__file__),'outputs':{p.name:sha(p) for p in out.iterdir() if p.is_file()}}
 (out/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary));return summary['status']=='PASS'
if __name__=='__main__':raise SystemExit(0 if main() else 1)
