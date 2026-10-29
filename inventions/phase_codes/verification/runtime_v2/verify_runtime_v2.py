"""Independent admission and process regression of a hash-pinned runtimev2 source."""
import argparse,copy,datetime,hashlib,importlib.util,itertools,json,math,pathlib,resource,sys,time
import numpy as np

def sha(path):return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
def mod(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m

def physical(state,n,q,k):
 out={};mask=1<<(n-1-q)
 for w,a in state.items():
  b=int(bool(w&mask))
  for t in (0,1):
   x=k[t,b]*a
   if x!=0:
    z=(w&~mask)|(t*mask);out[z]=out.get(z,0)+x
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--lab-root',required=True,type=pathlib.Path);ap.add_argument('--output',required=True,type=pathlib.Path);ap.add_argument('--runtime-sha256',required=True);a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=False)
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));resource.setrlimit(resource.RLIMIT_CPU,(600,600));start=time.monotonic();cpu=time.process_time();root=a.lab_root;here=pathlib.Path(__file__).parent
 runtime_path=root/'inventions/phase_codes/runtime_v2.py'
 if sha(runtime_path)!=a.runtime_sha256:raise ValueError('V2_SOURCE_IDENTITY_MISMATCH')
 freeze=json.loads((root/'campaign/cycle-004/CANDIDATE_FREEZE.json').read_text())
 for path,h in freeze['source_sha256'].items():
  if sha(root/path)!=h:raise ValueError('V1_SOURCE_CHANGED:'+path)
 verification=root/'inventions/phase_codes/verification'
 if not (verification/'process_core.py').exists():verification=root/'evidence/cycle-004/confirmation'
 if not (verification/'process_core.py').exists():verification=here.parent/'cycle4-quantum-verifier'
 P=mod('independent_frozen_process_core_v2',verification/'process_core.py');C=mod('independent_frozen_certify_v2',verification/'certify.py')
 v1=mod('independent_old_runtime_v2_test',root/'inventions/phase_codes/runtime.py');v2=mod('independent_new_runtime_v2_test',runtime_path)
 raw=json.loads((root/freeze['candidate']).read_text());I=np.eye(2,dtype=complex);X=np.array([[0,1],[1,0]],complex);Y=np.array([[0,-1j],[1j,0]],complex);Z=np.diag([1,-1]).astype(complex);rot=math.cos(math.pi/14)*I-1j*math.sin(math.pi/14)*(X+2*Y+3*Z)/math.sqrt(14)
 fixtures={};fixtures['original15']=copy.deepcopy(raw)
 n=raw['n'];permutation=list(range(1,n))+[0];d=copy.deepcopy(raw);d['physical_weights']=[raw['physical_weights'][j] for j in permutation]
 for row in d['codewords']:row['probabilities']={''.join(w[j] for j in permutation):p for w,p in row['probabilities'].items()}
 fixtures['cyclic_permutation']=d
 d=copy.deepcopy(raw);d['physical_weights']=[(-w)%4 for w in raw['physical_weights']];d['global_phase_exponent']=(raw['global_phase_exponent']-sum(raw['physical_weights']))%4
 for row in d['codewords']:row['probabilities']={''.join('1' if b=='0' else '0' for b in w):p for w,p in row['probabilities'].items()}
 fixtures['complemented_global_phase1']=d
 for label,duplicate in [('fixed0',False),('duplicated_coordinate',True)]:
  d=copy.deepcopy(raw);d['n']+=1;d['physical_weights']=[0]+d['physical_weights']
  for row in d['codewords']:row['probabilities']={(w[0] if duplicate else '0')+w:p for w,p in row['probabilities'].items()}
  fixtures[label]=d
 from fractions import Fraction
 d=copy.deepcopy(raw);dist=d['codewords'][0]['probabilities'];dist.pop(next(iter(dist)));total=sum(map(Fraction,dist.values()));d['codewords'][0]['probabilities']={w:str(Fraction(p)/total) for w,p in dist.items()};fixtures['normalized_moment_corruption']=d
 d=copy.deepcopy(raw);d['physical_weights']=[0]*n;fixtures['wrong_phase']=d
 d=copy.deepcopy(raw);d['codewords'][1]['probabilities']=copy.deepcopy(d['codewords'][0]['probabilities']);fixtures['overlap']=d
 d=copy.deepcopy(raw);d['n']=True;fixtures['boolean_n']=d
 d=copy.deepcopy(raw);d['physical_weights'][0]=True;fixtures['boolean_weight']=d
 paths={};fixture_reports={};fields=['n','physical_weights','global_phase_exponent','logical_order','codewords'];fp=a.output/'fixtures';fp.mkdir()
 for label,d in fixtures.items():
  path=fp/(label+'.json');path.write_text(json.dumps(d,sort_keys=True,indent=2)+'\n');paths[label]=path
  try:cert=C.certify(json.dumps({k:d[k] for k in fields}).encode());status=cert['status']
  except Exception as e:status='INPUT_REJECTED';cert={'reason':type(e).__name__+':'+str(e)}
  fixture_reports[label]={'fixture_sha256':sha(path),'broad_exact_certificate_status':status,'broad_checks':cert.get('checks'), 'broad_reason':cert.get('reason')}
 expected_yes={'original15','cyclic_permutation','complemented_global_phase1'};valid_outside={'fixed0','duplicated_coordinate'}
 for label in expected_yes|valid_outside:
  if fixture_reports[label]['broad_exact_certificate_status']!='CERTIFIED_EXACT_ALGEBRA_ONLY':raise ValueError('INDEPENDENT_FIXTURE_NOT_EXACT:'+label)
 admitted={};admission_fail=[]
 for label,path in paths.items():
  try:instance=v2.Instrument(path,sha(path));accepted=True;reason=None;admitted[label]=instance
  except Exception as e:accepted=False;reason=type(e).__name__+': '+str(e)
  fixture_reports[label].update(runtime_v2_admitted=accepted,runtime_v2_reason=reason)
  if accepted!=(label in expected_yes):admission_fail.append(label)
 original=paths['original15'];special=[]
 for label,path,expected in [('hash_mismatch',original,'0'*64)]:
  try:v2.Instrument(path,expected);refused=False;reason=None
  except Exception as e:refused=True;reason=type(e).__name__+': '+str(e)
  special.append(dict(label=label,refused=refused,reason=reason))
 dup=fp/'duplicate_json_key.json';s=original.read_text();s=s.replace('{','{"n": 15,',1);dup.write_text(s)
 try:v2.Instrument(dup,sha(dup));refused=False;reason=None
 except Exception as e:refused=True;reason=type(e).__name__+': '+str(e)
 special.append(dict(label='duplicate_json_key',refused=refused,reason=reason,sha256=sha(dup)))
 (a.output/'ADMISSION.json').write_text(json.dumps({'fixtures':fixture_reports,'special':special,'failed_expectations':admission_fail},indent=2)+'\n')
 witness=[];alpha=np.ones(4,complex)/2
 for label,q in [('fixed0',None),('duplicated_coordinate',0)]:
  m=v1.Instrument(paths[label],sha(paths[label]));state=m.phase(m.encode(alpha))
  if q is not None:state=physical(state,m.n,q,Z)
  rec=m.recover([state]);witness.append(dict(fixture=label,error='none' if q is None else 'Z_new_first_coordinate',input_probability=rec['input_probability'],raw_recovered_trace=float(np.trace(rec['logical_density']).real),reported_correctable_probability=rec['correctable_probability'],reported_unrecovered_probability=rec['unrecovered_probability']))
 (a.output/'V1_WITNESSES.json').write_text(json.dumps(witness,indent=2)+'\n')
 cases=[]
 for label in sorted(expected_yes):
  if label not in admitted:continue
  m=admitted[label];base=[('no_fault',None,[I])]
  for q in range(m.n):
   base.extend([(f'{p}_q{q}',q,[k]) for p,k in [('X',X),('Y',Y),('Z',Z)]])
   if label=='original15':base.append((f'coherent_q{q}',q,[rot]));gammas=(0,1/5,2/3,1)
   else:gammas=(1,) if q in (0,m.n//2,m.n-1) else ()
   for gamma in gammas:base.append((f'amplitude_damping_q{q}_g{gamma}',q,[np.diag([1,math.sqrt(1-gamma)]).astype(complex),np.array([[0,math.sqrt(gamma)],[0,0]],complex)]))
  for before in (False,True):
   for name,q,kraus in base:
    raw_loss=[];input_error=[];excess=[]
    def channel(v):
     state=m.encode(v)
     if not before:state=m.phase(state)
     branches=[state] if q is None else [physical(state,m.n,q,k) for k in kraus]
     if before:branches=[m.phase(s) for s in branches]
     rec=m.recover(branches);rho=rec['logical_density'];inp=sum(sum(abs(z)**2 for z in s.values()) for s in branches);input_error.append(abs(inp-1));raw_loss.append(inp-float(np.trace(rho).real));excess.append(float(np.trace(rho).real)-inp);return rho
    r=P.analyze(channel);r.update(fixture=label,label=name,before_gate=before,max_input_probability_error=float(max(input_error)),maximum_trace_excess=float(max(excess)),minimum_raw_unrecovered_probability=float(min(raw_loss)))
    r['passed']=bool(r['passed'] and max(input_error)<=P.TOL and max(excess)<=P.TOL)
    cases.append(r)
 (a.output/'PROCESS_CASES.json').write_text(json.dumps(cases,indent=2)+'\n')
 branches_reports=[]
 if 'original15' in admitted:
  m=admitted['original15'];s=m.phase(m.encode(alpha))
  for label,branches,want in [('scaled_037',[{w:math.sqrt(.37)*z for w,z in s.items()}],.37),('zero_branch',[{}],0.),('outside_two_X',[physical(physical(s,m.n,0,X),m.n,1,X)],None)]:
   rec=m.recover(branches);inp=sum(sum(abs(z)**2 for z in s.values()) for s in branches);tr=float(np.trace(rec['logical_density']).real)
   good=tr<=inp+P.TOL and (want is None or abs(tr-want)<=P.TOL) and abs(rec['input_probability']-inp)<=P.TOL
   if want is None:good=good and abs(rec['unrecovered_probability']-(inp-tr))<=P.TOL
   branches_reports.append(dict(label=label,input_probability=inp,raw_recovered_trace=tr,reported_unrecovered_probability=rec['unrecovered_probability'],expected_trace=want,passed=bool(good)))
 (a.output/'SUBNORMALIZED.json').write_text(json.dumps(branches_reports,indent=2)+'\n')
 ok=not admission_fail and all(t['refused'] for t in special) and all(r['passed'] for r in cases) and all(r['passed'] for r in branches_reports) and len(cases)==438
 report={'status':'PASS' if ok else 'FAIL','runtime_v2_sha256':a.runtime_sha256,'driver_sha256':sha(__file__),'protocol_sha256':sha(here/'PROTOCOL.json'),'frozen_process_core_sha256':sha(verification/'process_core.py'),'accepted_fixture_count':len(expected_yes),'process_cases':len(cases),'normalized_logical_probes_per_process_case':19,'process_failures':[{'fixture':r['fixture'],'label':r['label'],'before_gate':r['before_gate']} for r in cases if not r['passed']],'admission_failed_expectations':admission_fail,'special_admission_controls':special,'worst_process_matrix_error':max((r['normalized_Choi_matrix_error'] for r in cases),default=None),'maximum_trace_excess':max((r['maximum_trace_excess'] for r in cases),default=None),'v1_witnesses':witness,'subnormalized':branches_reports,'cpu_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'scope':'Exposed engineering regression, same exact candidate and process criteria; restricted runtime domain is explicit. No new statistical confirmation, global novelty, physical noisy processor, cost or business claim.','outputs':{p.name:sha(p) for p in a.output.iterdir() if p.is_file()}}
 (a.output/'SUMMARY.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));return ok
if __name__=='__main__':raise SystemExit(0 if main() else 1)
