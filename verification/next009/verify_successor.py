import argparse,gzip,hashlib,importlib.util,itertools,json,random,secrets,subprocess,sys,time
from fractions import Fraction
from pathlib import Path
import numpy as np
import scipy
from scipy.optimize import Bounds,LinearConstraint,milp

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(path):
    raw=path.read_bytes();value=json.loads(raw,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('NONFINITE_JSON')));canonical(value);return value,raw
def q(value):return Fraction(str(value))

def case_seed(replay_seed):
    if replay_seed is None:return secrets.token_hex(32),'FRESH_AFTER_PUBLIC_SOURCE_FREEZE'
    if len(replay_seed)!=64 or any(c not in '0123456789abcdef' for c in replay_seed):raise ValueError('REPLAY_SEED_REQUIRES_64_LOWERCASE_HEX_CHARACTERS')
    return replay_seed,'EXPOSED_REPRODUCTION_NO_NEW_CONFIRMATION'

def validated_corpus(corpus):
    if corpus.get('schema')!='agi-alpha/measurement-corpus009/v1' or corpus.get('numeric_semantics')!='canonical-json-finite-binary64-decimal-rational-v1':raise ValueError('CORPUS_SCHEMA_OR_ARITHMETIC')
    if corpus.get('network')!='Net2' or corpus.get('units')!='source_contribution_percentage_points':raise ValueError('PRESPECIFIED_NET2_COHORT')
    if corpus['nodes']!=corpus['sources'] or corpus['times_seconds']!=list(range(0,86400,3600)):raise ValueError('ALL_SOURCE_OR_TIME_COHORT')
    n=len(corpus['nodes'])
    if not 2<=n<=48 or len(set(corpus['nodes']))!=n:raise ValueError('FINITE_COHORT_BOUND')
    if len(corpus['signal'])!=n or any(len(x)!=24 or any(len(t)!=n for t in x) for x in corpus['signal']):raise ValueError('SHAPE')
    data=[[[q(v) for v in row] for row in source] for source in corpus['signal']]
    if any(v<0 or v>100 for source in data for row in source for v in row):raise ValueError('TRACE_RANGE')
    return data

def verify_source_binding(corpus,raw_corpus_path,network_path,simulation_receipt_path,freeze):
    raw_corpus,raw_bytes=read(raw_corpus_path);network_bytes=network_path.read_bytes();simulation,simulation_bytes=read(simulation_receipt_path)
    if raw_corpus.get('upstream_commit')!='11eec7d5bf0a9367ffe04d75707918f0c0a890a1':raise ValueError('UPSTREAM_SOURCE_IDENTITY')
    if raw_corpus.get('simulator_sha256')!=freeze['files']['inventions/measurement009/inputs/libepanet22.so']:raise ValueError('FROZEN_SIMULATOR_IDENTITY')
    if sha(network_bytes)!=raw_corpus.get('network_sha256'):raise ValueError('NETWORK_BYTES_IDENTITY')
    junctions=[];section=None
    for raw_line in network_bytes.decode('utf-8-sig').splitlines():
        line=raw_line.split(';',1)[0].strip()
        if not line:continue
        if line.startswith('['):section=line.upper();continue
        if section=='[JUNCTIONS]':junctions.append(line.split()[0])
    if not junctions or junctions!=corpus['nodes'] or junctions!=corpus['sources']:raise ValueError('FULL_ACQUIRED_JUNCTION_COHORT')
    if simulation.get('corpus_sha256')!=sha(canonical(raw_corpus)) or simulation.get('warnings')!=[]:raise ValueError('SIMULATION_RECEIPT_IDENTITY_OR_WARNINGS')
    if simulation.get('source_cases')!=len(junctions) or simulation.get('sensors')!=len(junctions) or simulation.get('times')!=24:raise ValueError('SIMULATION_RECEIPT_COHORT')
    return {'network_sha256':sha(network_bytes),'network_git_blob_sha1':hashlib.sha1(b'blob '+str(len(network_bytes)).encode()+b'\0'+network_bytes).hexdigest(),'raw_corpus_sha256':sha(raw_bytes),'simulation_receipt_sha256':sha(simulation_bytes),'simulator_sha256':raw_corpus['simulator_sha256'],'upstream_commit':raw_corpus['upstream_commit'],'all_acquired_junctions':junctions,'scope':'Independent source-identity and complete-cohort checks against supplied acquired network bytes and source-pinned simulation receipt; no outside certification or physical validation.'}

def shift_interval(differences,eps,drift):
    residual=2*(eps+drift)
    lower=max([ -2*eps, max(differences)-residual])
    upper=min([ 2*eps, min(differences)+residual])
    return lower,upper

def relations(data,eps,drift):
    rows=[]
    for a,b in itertools.combinations(range(len(data)),2):
        separated=[]
        for sensor in range(len(data[0][0])):
            lo,hi=shift_interval([data[a][t][sensor]-data[b][t][sensor] for t in range(len(data[0]))],eps,drift)
            separated.append(lo>hi)
        rows.append({'a':a,'b':b,'separated':separated})
    return rows

def check_plan(selected,pairs,sources,erasures):
    checks=[];failed=[]
    for pair in pairs:
        separable=[s for s in selected if pair['separated'][s]]
        if len(separable)<=erasures:failed.append({'sources':[sources[pair['a']],sources[pair['b']]],'a':pair['a'],'b':pair['b'],'separating_selected_indices':separable})
    for n in range(erasures+1):
        for removed in itertools.combinations(selected,n):
            kept=[s for s in selected if s not in removed]
            unresolved=sum(not any(pair['separated'][s] for s in kept) for pair in pairs)
            checks.append({'erased_indices':list(removed),'unresolved_pair_count':unresolved})
    return {'failed_pair_count':len(failed),'failed_pairs':failed,'outages':checks,'accepted':not failed and all(c['unresolved_pair_count']==0 for c in checks)}

def conventional(pairs,count,required):
    matrix=np.array([p['separated'] for p in pairs],dtype=float)
    if np.any(matrix.sum(axis=1)<required):return {'status':'PROVED_INFEASIBLE_BY_PAIR','selected':[],'objective':None}
    fit=milp(c=np.ones(count),integrality=np.ones(count),bounds=Bounds(np.zeros(count),np.ones(count)),constraints=LinearConstraint(matrix,np.full(len(pairs),required),np.full(len(pairs),np.inf)),options={'time_limit':20,'mip_rel_gap':0.0})
    selected=np.flatnonzero(fit.x>.5).tolist() if fit.x is not None else []
    feasible=bool(selected) and all(sum(p['separated'][s] for s in selected)>=required for p in pairs)
    return {'status':'SOLVER_REPORTED_OPTIMAL_CHECKED_FEASIBLE' if fit.status==0 and feasible else 'FEASIBLE_OPTIMUM_UNKNOWN' if feasible else 'UNKNOWN','selected':selected,'objective':len(selected) if feasible else None,'solver_status':int(fit.status),'reported_dual_bound':float(fit.mip_dual_bound) if getattr(fit,'mip_dual_bound',None) is not None else None,'reported_gap':float(fit.mip_gap) if getattr(fit,'mip_gap',None) is not None else None,'scope':'Independent exact input relation construction and returned-cover check; shared SciPy/HiGHS optimizer, no separate exact integer optimality certificate.'}

def split_error(combined,eps,drift):
    noise=max(-eps,min(eps,combined));delta=combined-noise
    if abs(noise)>eps or abs(delta)>drift:raise AssertionError('WITNESS_ERROR_SPLIT')
    return noise,delta

def ambiguity_witness(data,failure,selected,eps,drift,nodes,sources):
    a,b=failure['a'],failure['b'];removed=failure['separating_selected_indices'];kept=[s for s in selected if s not in removed];details=[]
    for sensor in kept:
        diff=[data[a][t][sensor]-data[b][t][sensor] for t in range(len(data[0]))]
        lo,hi=shift_interval(diff,eps,drift)
        if lo>hi:raise AssertionError('WITNESS_SENSOR_SEPARATES')
        refdiff=(lo+hi)/2;offset_a=-refdiff/2;offset_b=refdiff/2;errref_a=refdiff/2;errref_b=-refdiff/2
        obs_a=[];obs_b=[];noise_a=[];noise_b=[];drift_a=[];drift_b=[]
        for t,d in enumerate(diff):
            ca=-(d-refdiff)/2;cb=(d-refdiff)/2;na,da=split_error(ca,eps,drift);nb,db=split_error(cb,eps,drift)
            obs_a.append(data[a][t][sensor]+offset_a+na+da);obs_b.append(data[b][t][sensor]+offset_b+nb+db)
            noise_a.append(na);noise_b.append(nb);drift_a.append(da);drift_b.append(db)
        if obs_a!=obs_b or offset_a+errref_a!=0 or offset_b+errref_b!=0:raise AssertionError('WITNESS_OBSERVATION_DIFFERENCE')
        details.append({'sensor':nodes[sensor],'offset_a':str(offset_a),'offset_b':str(offset_b),'reference_error_a':str(errref_a),'reference_error_b':str(errref_b),'identical_reference':'0','identical_trace':[str(v) for v in obs_a],'sample_noise_a':[str(v) for v in noise_a],'sample_noise_b':[str(v) for v in noise_b],'sample_drift_a':[str(v) for v in drift_a],'sample_drift_b':[str(v) for v in drift_b]})
    return {'sources':[sources[a],sources[b]],'drift_bound_pp':str(drift),'erased':[nodes[s] for s in removed],'remaining_sensor_count':len(kept),'witness':details,'exact_identical_raw_observations':True}

def compatible(data,h,obs,selected,eps,drift):
    for sensor in selected:
        reference=q(obs['reference'][sensor]);diff=[q(v)-reference-data[h][t][sensor] for t,v in enumerate(obs['trace'][sensor])]
        lower=max([-eps]+[-eps-drift-d for d in diff]);upper=min([eps]+[eps+drift-d for d in diff])
        if lower>upper:return False
    return True

def worlds(data,eps,drift,per_source,seed):
    rng=random.Random(seed+':'+str(drift));count=len(data[0][0]);rows=[]
    for source in range(len(data)):
        for rep in range(per_source):
            reference={};trace={};order=list(range(count));rng.shuffle(order)
            for sensor in range(count):
                offset=Fraction(rng.randint(-99999,99999),37)
                er=eps*(Fraction((-1)**(rep+sensor)) if rep<2 else Fraction(rng.randint(-100,100),100))
                reference[sensor]=str(offset+er);values=[]
                for t in range(len(data[0])):
                    e=eps*(Fraction((-1)**(rep+sensor+t)) if rep<2 else Fraction(rng.randint(-100,100),100))
                    d=drift*(Fraction((-1)**(rep+sensor+t)) if rep<2 else Fraction(rng.randint(-100,100),100))
                    values.append(str(data[source][t][sensor]+offset+e+d))
                trace[sensor]=values
            rows.append({'case':len(rows),'source':source,'reference':reference,'trace':trace,'outage_count':rep%2,'erasure_order':order})
    return rows

def select_world(world,selected,eps,drift,data,nodes):
    erased=[s for s in world['erasure_order'] if s in selected][:world['outage_count']]
    kept=[s for s in selected if s not in erased]
    obs={'reference':{s:world['reference'][s] for s in kept},'trace':{s:world['trace'][s] for s in kept}}
    choices=[h for h in range(len(data)) if compatible(data,h,obs,kept,eps,drift)]
    presented={'reference':{nodes[s]:obs['reference'][s] for s in kept},'trace':{nodes[s]:obs['trace'][s] for s in kept},'outages':[nodes[s] for s in erased],'known_zero_valid':True,'drift_bound_qualified':True,'drift_bound_pp':str(drift)}
    return presented,choices

def run(args):
    root=args.root.resolve();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False);started,cpu=time.monotonic(),time.process_time()
    freeze,freeze_raw=read(args.freeze)
    if sha(freeze_raw)!=args.expected_freeze_sha256:raise ValueError('EXTERNAL_SUCCESSOR_FREEZE_REQUIRED')
    for name,expected in freeze['files'].items():
        if sha((root/name).read_bytes())!=expected:raise ValueError('FROZEN_SOURCE_CHANGED:'+name)
    numeric_path=Path(__file__).with_name('numeric_edition_checker.py')
    numeric_spec=importlib.util.spec_from_file_location('independent_numeric_edition_checker',numeric_path);numeric_checker=importlib.util.module_from_spec(numeric_spec);numeric_spec.loader.exec_module(numeric_checker)
    numeric_check=numeric_checker.check(args.raw_corpus,args.corpus,args.numeric_receipt)
    (output/'NUMERIC_EDITION_CHECK.json').write_bytes(canonical(numeric_check))
    corpus,corpus_raw=read(args.corpus);protocol,protocol_raw=read(args.protocol);data=validated_corpus(corpus);nodes,sources=corpus['nodes'],corpus['sources']
    if sha(protocol_raw)!=freeze['files']['verification/next009/successor_protocol.json']:raise ValueError('FROZEN_VERIFIER_PROTOCOL_REQUIRED')
    if protocol['drift_grid_pp']!=['0','1','5','10','25'] or protocol['max_sensor_erasures']!=1 or protocol['noise_bound_pp']!='1':raise ValueError('PRESPECIFIED_OBLIGATION_CHANGED')
    if protocol['arms']!=['retained','equal-content-ordinary-reuse','reset-full-toolbox'] or protocol['protected_cases_per_source_per_drift']!=4:raise ValueError('COMPLETE_ARMS_AND_CASES_REQUIRED')
    source_binding=verify_source_binding(corpus,args.raw_corpus,args.network,args.simulation_receipt,freeze)
    identity_inputs={str(path):path.read_bytes() for path in [args.raw_corpus,args.numeric_receipt,args.network,args.simulation_receipt]}
    old,old_raw=read(args.plans/'old_zero_drift_plan.json')
    if old['corpus_sha256']!=sha(canonical(corpus)):raise ValueError('OLD_PLAN_CORPUS_BINDING')
    old_selected=[nodes.index(s) for s in old['sensors']]
    eps=q(protocol['noise_bound_pp']);seed,generation_mode=case_seed(args.replay_seed);fresh=generation_mode=='FRESH_AFTER_PUBLIC_SOURCE_FREEZE';(output/'SEED_COMMITMENT.json').write_bytes(canonical({'seed_sha256':sha(seed.encode()),'fresh_after_source_freeze':fresh,'mode':generation_mode}))
    batches=[];expected_runtime={};rows=[];truth_records=[];plan_raws={}
    for d in protocol['drift_grid_pp']:
        drift=q(d);pairs=relations(data,eps,drift);base=check_plan(old_selected,pairs,sources,1);control=conventional(pairs,len(nodes),2);world=worlds(data,eps,drift,protocol['protected_cases_per_source_per_drift'],seed)
        if base['failed_pairs']:
            witness=ambiguity_witness(data,base['failed_pairs'][0],old_selected,eps,drift,nodes,sources)
            (output/('old-plan-drift-'+d+'-witness.json')).write_bytes(canonical(witness))
        level={'drift_bound_pp':d,'pairs':len(pairs),'old_plan':base,'conventional_control':control,'arms':[]}
        for arm in protocol['arms']:
            name='drift_'+d+'_'+arm;plan,raw=read(args.plans/(name+'.json'));plan_raws[name]=raw
            if plan.get('schema')!='agi-alpha/drift-observation-plan009/v1' or plan.get('operator')!='bounded-reference-drift' or plan.get('network')!='Net2':raise ValueError('PLAN_SCHEMA_OR_OPERATOR')
            if plan['corpus_sha256']!=sha(canonical(corpus)) or q(plan['noise_bound_pp'])!=eps or q(plan['drift_bound_pp'])!=drift or plan['max_sensor_erasures']!=1:raise ValueError('PLAN_OBLIGATION_MISMATCH')
            program=plan['generated_program'];composition=program['interval_composition']
            required_ast={'op':'subtract','left':{'op':'read','sensor':'$sensor','time':'$time'},'right':{'op':'zero_reference','sensor':'$sensor'}}
            if program.get('parent_expression')!=required_ast or q(composition['reference_pair_error_bound'])!=2*eps or q(composition['sample_pair_error_bound'])!=2*(eps+drift) or composition.get('shared_reference_required') is not True:raise ValueError('GENERATED_INTERVAL_PROGRAM_MISMATCH')
            selected=[nodes.index(s) for s in plan['sensors']]
            if len(set(selected))!=len(selected):raise ValueError('DUPLICATE_SENSOR')
            checked=check_plan(selected,pairs,sources,1);case_inputs=[];truth=[]
            for w in world:
                observations,choices=select_world(w,selected,eps,drift,data,nodes)
                case_inputs.append({'case':w['case'],'observations':observations});truth.append({'case':w['case'],'true_source':sources[w['source']],'independent_compatible':[sources[x] for x in choices],'independent_passed':choices==[w['source']]})
            expected_runtime[name]=truth;batches.append({'name':name,'plan':plan,'cases':case_inputs});truth_records.append({'name':name,'truth':truth})
            level['arms'].append({'arm':arm,'name':name,'plan_sha256':sha(raw),'selected_sensors':plan['sensors'],'exact_check':checked,'independent_cases':len(truth),'independent_cases_passed':sum(x['independent_passed'] for x in truth),'same_cardinality_as_conventional':control['objective'] is not None and len(selected)==control['objective']})
        rows.append(level)
    (output/'EXPOSED_CASE_TRUTHS.json').write_bytes(canonical({'seed':seed,'seed_sha256':sha(seed.encode()),'batches':truth_records}))
    input_path=output/'RUNTIME_OBSERVATIONS_WITHOUT_TRUTH.json.gz';input_path.write_bytes(gzip.compress(canonical({'corpus':corpus,'batches':batches}),mtime=0));runtime_out=output/'RUNTIME_OUTPUTS.json'
    source=root/'research/next009/successor.py';driver=root/'verification/next009/successor_runtime_driver.py'
    with (output/'runtime.stdout.log').open('xb') as stdout,(output/'runtime.stderr.log').open('xb') as stderr:
        completed=subprocess.run([sys.executable,str(driver),'--root',str(root),'--source',str(source),'--input',str(input_path),'--output',str(runtime_out),'--expected-source-sha256',sha(source.read_bytes())],stdout=stdout,stderr=stderr,timeout=180)
    runtime=read(runtime_out)[0] if runtime_out.exists() else {};actual=runtime.get('batches',[]);actual_by_name={b['name']:{x['case']:x for x in b['results']} for b in actual}
    runtime_identity_passed=runtime.get('source_sha256')==freeze['files']['research/next009/successor.py']
    for level in rows:
        for arm in level['arms']:
            name=arm['name'];passed=0;failures=[]
            for truth in expected_runtime[name]:
                result=actual_by_name.get(name,{}).get(truth['case'],{}).get('result',{})
                correct=result.get('status')=='UNIQUE' and result.get('sources')==[truth['true_source']]
                if correct:passed+=1
                else:failures.append(truth['case'])
            arm['actual_runtime']={'passed':passed,'cases':len(expected_runtime[name]),'failed_case_ids':failures}
            arm['accepted']=completed.returncode==0 and runtime_identity_passed and arm['exact_check']['accepted'] and arm['independent_cases_passed']==arm['independent_cases'] and passed==len(expected_runtime[name])
        level['causal_successor_benefit']=q(level['drift_bound_pp'])>0 and level['old_plan']['failed_pair_count']>0 and all(a['accepted'] for a in level['arms'])
    for name,expected in freeze['files'].items():
        if sha((root/name).read_bytes())!=expected:raise ValueError('SOURCE_CHANGED_DURING_VERIFICATION:'+name)
    if args.corpus.read_bytes()!=corpus_raw or args.protocol.read_bytes()!=protocol_raw or (args.plans/'old_zero_drift_plan.json').read_bytes()!=old_raw:raise ValueError('INPUT_CHANGED_DURING_VERIFICATION')
    for name,raw in plan_raws.items():
        if (args.plans/(name+'.json')).read_bytes()!=raw:raise ValueError('PLAN_CHANGED_DURING_VERIFICATION')
    for name,raw in identity_inputs.items():
        if Path(name).read_bytes()!=raw:raise ValueError('SOURCE_IDENTITY_INPUT_CHANGED_DURING_VERIFICATION')
    report={'schema':'agi-alpha/next009-independent-successor-acceptance/v1','freeze_sha256':sha(freeze_raw),'corpus_raw_sha256':sha(corpus_raw),'corpus_canonical_sha256':sha(canonical(corpus)),'network_sha256':corpus['network_sha256'],'source_count':len(sources),'pair_count':len(sources)*(len(sources)-1)//2,'all_drift_levels':rows,'any_verified_model_successor_benefit':any(x['causal_successor_benefit'] for x in rows),'candidate_runtime_exit_code':completed.returncode,'conventional_solver_version':scipy.__version__,'qualified_earned_funding':0,'earned_funded_successor':False,'after_cost_discovery_advantage':'NOT_ESTABLISHED','exposure':'Fresh Net2 transfer after policy freeze; perturbation cases now exposed; finite engineering scope only.','procedural_independence':'No candidate arithmetic imported by checker; actual candidate is executed as a separate tested process. Same host, originating models, source simulator and SciPy/HiGHS libraries are disclosed.','claim_alpha_spent':0,'wall_seconds':time.monotonic()-started,'process_cpu_seconds':time.process_time()-cpu}
    report['schema']='agi-alpha/next009-independent-successor-acceptance/v2'
    report['numeric_edition_verification']=numeric_check
    report['source_binding']=source_binding
    report['candidate_runtime_source_identity_passed']=runtime_identity_passed
    report['numeric_edition_scope']='Prospectively defined uniform rounded finite numerical edition; original raw-model qualification remains unchanged.'
    report['case_generation_mode']=generation_mode
    report['exposure']='Fresh Net2 transfer after policy freeze; perturbation cases now exposed; finite engineering scope only.' if fresh else 'EXPOSED_REPRODUCTION_NO_NEW_CONFIRMATION: supplied already exposed seed, unchanged engineering checks; no new protected cases or new statistical evidence.'
    report['new_protected_latent_worlds']=len(sources)*protocol['protected_cases_per_source_per_drift']*len(protocol['drift_grid_pp']) if fresh else 0
    (output/'ACCEPTANCE.json').write_bytes(canonical(report));print(json.dumps({'sources':len(sources),'pairs':report['pair_count'],'benefit_drift_levels':[x['drift_bound_pp'] for x in rows if x['causal_successor_benefit']],'runtime_exit':completed.returncode}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--corpus',type=Path,required=True);p.add_argument('--raw-corpus',type=Path,required=True);p.add_argument('--numeric-receipt',type=Path,required=True);p.add_argument('--network',type=Path,required=True);p.add_argument('--simulation-receipt',type=Path,required=True);p.add_argument('--plans',type=Path,required=True);p.add_argument('--protocol',type=Path,required=True);p.add_argument('--freeze',type=Path,required=True);p.add_argument('--expected-freeze-sha256',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--replay-seed',help='Already exposed 64-character lowercase hexadecimal seed; labels output as reproduction, never new protected confirmation.');run(p.parse_args())
