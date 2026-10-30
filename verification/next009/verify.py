import argparse, hashlib, itertools, json, random, secrets, subprocess, sys, time
from fractions import Fraction
from pathlib import Path

SCOPE = 'model-based-water-observation-plan'

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def read(path):
    raw=path.read_bytes()
    def pairs(values):
        result={}
        for k,v in values:
            if k in result: raise ValueError('DUPLICATE_JSON_KEY:'+k)
            result[k]=v
        return result
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('NONFINITE_JSON')))
    canonical(value)
    return value,raw

def exact(value):
    if type(value) is float: return Fraction(str(value))
    if type(value) not in (str,int,Fraction): raise ValueError('EXACT_NUMBER_REQUIRED')
    return Fraction(value)

def corpus_values(corpus):
    if corpus.get('schema')!='agi-alpha/measurement-corpus009/v1': raise ValueError('CORPUS_SCHEMA')
    if corpus.get('units')!='source_contribution_percentage_points': raise ValueError('CORPUS_UNITS')
    if corpus.get('numeric_semantics')!='canonical-json-finite-binary64-decimal-rational-v1': raise ValueError('CORPUS_NUMERIC_SEMANTICS')
    nodes,sources,times=corpus['nodes'],corpus['sources'],corpus['times_seconds']
    for name,values in [('nodes',nodes),('sources',sources)]:
        if type(values) is not list or not values or len(set(values))!=len(values) or any(type(v) is not str or not v for v in values): raise ValueError('UNIQUE_IDENTITIES_REQUIRED:'+name)
    if len(nodes)>48 or len(sources)>48: raise ValueError('VERIFIER_FINITE_CAP')
    if type(times) is not list or not times or any(type(t) is not int or t<0 for t in times) or times!=sorted(set(times)): raise ValueError('TIMESTAMPS')
    if len(times)>128: raise ValueError('VERIFIER_TIME_CAP')
    signal=corpus['signal']
    if type(signal) is not list or len(signal)!=len(sources): raise ValueError('SOURCE_DIMENSION')
    if any(type(rows) is not list or len(rows)!=len(times) for rows in signal): raise ValueError('TIME_DIMENSION')
    if any(type(row) is not list or len(row)!=len(nodes) for rows in signal for row in rows): raise ValueError('SENSOR_DIMENSION')
    result=[[[exact(v) for v in row] for row in rows] for rows in signal]
    if any(v<0 or v>100 for rows in result for row in rows for v in row): raise ValueError('TRACE_PERCENT_RANGE')
    return result

def interval(pair_differences,noise,calibrated):
    lower=max(pair_differences)-2*noise
    upper=min(pair_differences)+2*noise
    if calibrated:
        lower=max(lower,-2*noise)
        upper=min(upper,2*noise)
    return lower,upper

def pair_channels(data,noise):
    pairs=[]
    for a,b in itertools.combinations(range(len(data)),2):
        calibrated,uncalibrated=[],[]
        for sensor in range(len(data[0][0])):
            differences=[data[a][t][sensor]-data[b][t][sensor] for t in range(len(data[0]))]
            lo,hi=interval(differences,noise,True)
            ulo,uhi=interval(differences,noise,False)
            calibrated.append(lo>hi)
            uncalibrated.append(ulo>uhi)
        pairs.append({'a':a,'b':b,'calibrated':calibrated,'uncalibrated':uncalibrated})
    return pairs

def viable(selected,pairs,outages,kind='calibrated'):
    for pair in pairs:
        if sum(pair[kind][sensor] for sensor in selected)<=outages: return False
    return True

def exact_minimum(pairs,count,outages):
    examined=0
    masks=[sum(1<<p for p,pair in enumerate(pairs) if pair['calibrated'][sensor]) for sensor in range(count)]
    full=(1<<len(pairs))-1
    def covers(selected):
        layers=[0]*(outages+1)
        for sensor in selected:
            mask=masks[sensor]
            for level in range(outages,0,-1): layers[level]|=layers[level-1]&mask
            layers[0]|=mask
        return layers[-1]==full
    for size in range(outages+1,count+1):
        for selected in itertools.combinations(range(count),size):
            examined+=1
            if examined>5000000: return {'size':None,'first':None,'examined_subsets':examined-1,'status':'UNKNOWN_ENUMERATION_CAP'}
            if covers(selected): return {'size':size,'first':selected,'examined_subsets':examined,'status':'EXACT_FIRST_FEASIBLE_CARDINALITY'}
    return {'size':None,'first':None,'examined_subsets':examined,'status':'INFEASIBLE_ALL_SUBSETS'}

def outage_checks(selected,pairs,sources,outages):
    result=[]
    for count in range(outages+1):
        for removed in itertools.combinations(selected,count):
            kept=tuple(s for s in selected if s not in removed)
            ambiguous=[[sources[p['a']],sources[p['b']]] for p in pairs if not any(p['calibrated'][s] for s in kept)]
            result.append({'erased_indices':list(removed),'remaining_indices':list(kept),'ambiguous_pairs':ambiguous,'passed':not ambiguous})
    return result

def ambiguity_witness(data,pair,noise,nodes,sources):
    a,b=pair['a'],pair['b']
    sensors=[]
    for sensor,node in enumerate(nodes):
        differences=[data[a][t][sensor]-data[b][t][sensor] for t in range(len(data[0]))]
        lo,hi=interval(differences,noise,False)
        if lo>hi: raise ValueError('PAIR_IS_NOT_AMBIGUOUS')
        shift=(lo+hi)/2
        residual=[d-shift for d in differences]
        noise_a=[-r/2 for r in residual]
        noise_b=[r/2 for r in residual]
        observed_a=[data[a][t][sensor]+noise_a[t] for t in range(len(data[0]))]
        observed_b=[data[b][t][sensor]+shift+noise_b[t] for t in range(len(data[0]))]
        if observed_a!=observed_b or any(abs(v)>noise for v in noise_a+noise_b): raise AssertionError('WITNESS_INVALID')
        sensors.append({'sensor':node,'offset_a':'0','offset_b':str(shift),'error_a':[str(v) for v in noise_a],'error_b':[str(v) for v in noise_b],'identical_observations':[str(v) for v in observed_a]})
    return {'sources':[sources[a],sources[b]],'all_sensor_count':len(nodes),'all_timestamps':len(data[0]),'witness':sensors,'checked_equal':True,'scope':'Exact indistinguishability under arbitrary unknown constant sensor offset, the simulated numeric corpus and bounded reading noise.'}

def compatible_source(data,source,observed,reference,selected,noise):
    for sensor in selected:
        differences=[observed[sensor][t]-reference[sensor]-data[source][t][sensor] for t in range(len(data[0]))]
        lower=max([-noise]+[-noise-v for v in differences])
        upper=min([noise]+[noise-v for v in differences])
        if lower>upper: return False
    return True

def protected_cases(data,nodes,sources,selected,noise,outages,per_source,seed):
    rng=random.Random(seed)
    rows=[]
    for source in range(len(sources)):
        for repetition in range(per_source):
            erased_count=repetition%(outages+1)
            removed=sorted(rng.sample(list(selected),erased_count))
            kept=[s for s in selected if s not in removed]
            reference,observed,offsets={}, {}, {}
            for sensor in kept:
                offset=Fraction(rng.randint(-100000,100000),37)
                ref_error=noise*(Fraction((-1)**(repetition+sensor)) if repetition<2 else Fraction(rng.randint(-100,100),100))
                reference[sensor]=offset+ref_error
                offsets[sensor]=offset
                observed[sensor]=[]
                for t in range(len(data[0])):
                    error=noise*(Fraction((-1)**(repetition+sensor+t)) if repetition<2 else Fraction(rng.randint(-100,100),100))
                    observed[sensor].append(data[source][t][sensor]+offset+error)
            compatible=[sources[h] for h in range(len(sources)) if compatible_source(data,h,observed,reference,kept,noise)]
            rows.append({'case':len(rows),'true_source':sources[source],'erased':[nodes[s] for s in removed],'offsets':{nodes[s]:str(v) for s,v in offsets.items()},'reference':{nodes[s]:str(v) for s,v in reference.items()},'observations':{nodes[s]:[str(x) for x in values] for s,values in observed.items()},'compatible':compatible,'passed':compatible==[sources[source]]})
    return rows

def evaluate(corpus_path,plan_path,protocol_path,output,confirm=False,expected=None,candidate_path=None,development_seed=None):
    started,cpu=time.monotonic(),time.process_time()
    corpus,corpus_raw=read(corpus_path);plan,plan_raw=read(plan_path);protocol,protocol_raw=read(protocol_path)
    source_raw=Path(__file__).read_bytes()
    binding={'artifact_sha256':sha(plan_raw),'verifier_source_sha256':sha(source_raw),'protocol_sha256':sha(protocol_raw),'corpus_raw_sha256':sha(corpus_raw),'corpus_canonical_sha256':sha(canonical(corpus))}
    runtime_driver=Path(__file__).with_name('runtime_driver.py')
    run_cases=confirm or development_seed is not None
    if run_cases and candidate_path is None: raise ValueError('ACTUAL_CANDIDATE_RUNTIME_REQUIRED')
    if confirm and development_seed is not None: raise ValueError('EXPOSED_SEED_CANNOT_BE_CONFIRMATION')
    if candidate_path is not None:
        candidate_raw=candidate_path.read_bytes();driver_raw=runtime_driver.read_bytes()
        binding.update({'candidate_source_sha256':sha(candidate_raw),'runtime_driver_sha256':sha(driver_raw)})
    if confirm:
        if candidate_path is None: raise ValueError('ACTUAL_CANDIDATE_RUNTIME_REQUIRED')
        if expected is None or any(expected.get(k)!=v for k,v in binding.items()): raise ValueError('EXTERNAL_FREEZE_MISMATCH')
    if protocol.get('scope')!=SCOPE: raise ValueError('PROTOCOL_SCOPE')
    if plan.get('schema')!='agi-alpha/observation-plan009/v1': raise ValueError('PLAN_SCHEMA')
    if plan.get('corpus_sha256')!=binding['corpus_canonical_sha256'] or plan.get('network_sha256')!=corpus.get('network_sha256'): raise ValueError('PLAN_CORPUS_BINDING')
    if plan.get('numeric_semantics')!=corpus.get('numeric_semantics'): raise ValueError('PLAN_NUMERIC_SEMANTICS')
    if plan.get('operator')!='known-zero-reference': raise ValueError('REFERENCE_OPERATOR_REQUIRED')
    required_ast={'op':'subtract','left':{'op':'read','sensor':'$sensor','time':'$time'},'right':{'op':'zero_reference','sensor':'$sensor'}}
    if plan.get('generated_expression',{}).get('ast')!=required_ast: raise ValueError('EXECUTABLE_REFERENCE_EXPRESSION_REQUIRED')
    nuisance='arbitrary-per-sensor-offset-constant-across-reference-and-trace'
    if plan.get('nuisance')!=nuisance: raise ValueError('NUISANCE_MODEL')
    noise=exact(protocol['noise_bound_pp']);outages=protocol['max_sensor_erasures']
    if noise<=0 or type(outages) is not int or outages<0 or outages>2: raise ValueError('PROTOCOL_BOUNDS')
    if exact(plan.get('noise_bound_pp'))!=noise or plan.get('max_sensor_erasures')!=outages: raise ValueError('PLAN_REQUIREMENT_MISMATCH')
    data=corpus_values(corpus);nodes,sources=corpus['nodes'],corpus['sources']
    sensors=plan.get('sensors')
    if type(sensors) is not list or len(set(sensors))!=len(sensors) or any(s not in nodes for s in sensors): raise ValueError('SENSOR_PLAN')
    selected=tuple(nodes.index(s) for s in sensors)
    channels=pair_channels(data,noise)
    control=exact_minimum(channels,len(nodes),outages)
    checks=outage_checks(selected,channels,sources,outages)
    unresolved=[p for p in channels if not any(p['uncalibrated'])]
    witness=ambiguity_witness(data,unresolved[0],noise,nodes,sources) if unresolved else None
    output.mkdir(parents=True,exist_ok=False)
    if witness: (output/'UNCALIBRATED_WITNESS.json').write_bytes(canonical(witness))
    case_rows=[]
    runtime=None
    if run_cases:
        seed=secrets.token_hex(32) if confirm else development_seed
        commitment=sha(seed.encode())
        (output/'SEED_COMMITMENT.json').write_bytes(canonical({'seed_sha256':commitment,'scope':'Verifier-generated after external freeze, withheld from builder during execution.' if confirm else 'Explicit exposed development seed; no protected confirmation.'}))
        case_rows=protected_cases(data,nodes,sources,selected,noise,outages,protocol['protected_cases']['cases_per_source'],seed)
        (output/('EXPOSED_CONFIRMATION_CASES.json' if confirm else 'DEVELOPMENT_CASES.json')).write_bytes(canonical({'seed':seed,'seed_sha256':commitment,'cases':case_rows}))
        inputs={'corpus':corpus,'plan':plan,'cases':[{'case':case['case'],'observations':{'trace':case['observations'],'reference':case['reference'],'outages':case['erased'],'known_zero_valid':True,'offset_constant':True}} for case in case_rows]}
        runtime_input=output/'RUNTIME_OBSERVATIONS_WITHOUT_TRUTH.json'
        runtime_input.write_bytes(canonical(inputs))
        runtime_output=output/'RUNTIME_OUTPUTS.json'
        with (output/'runtime.stdout.log').open('xb') as stdout,(output/'runtime.stderr.log').open('xb') as stderr:
            completed=subprocess.run([sys.executable,str(runtime_driver),'--candidate',str(candidate_path),'--input',str(runtime_input),'--output',str(runtime_output),'--expected-candidate-sha256',binding['candidate_source_sha256']],stdout=stdout,stderr=stderr,timeout=30)
        actual=read(runtime_output)[0]['results'] if runtime_output.exists() else []
        by_id={row['case']:row for row in actual}
        runtime_cases=[]
        for case in case_rows:
            result=by_id.get(case['case'],{}).get('result',{})
            runtime_cases.append({'case':case['case'],'passed':result.get('status')=='UNIQUE' and result.get('sources')==[case['true_source']]})
        runtime={'exit_code':completed.returncode,'case_count':len(runtime_cases),'passed':sum(x['passed'] for x in runtime_cases),'failed_case_ids':[x['case'] for x in runtime_cases if not x['passed']],'input_sha256':sha(runtime_input.read_bytes()),'output_sha256':sha(runtime_output.read_bytes()) if runtime_output.exists() else None,'scope':'Candidate diagnosis invoked in a separate process with observations only; verifier truth labels are withheld from its input.'}
    accepted=bool(witness) and control['size'] is not None and len(selected)==control['size'] and all(x['passed'] for x in checks) and all(x['passed'] for x in case_rows) and (not run_cases or (runtime['exit_code']==0 and runtime['passed']==len(case_rows)))
    report={'schema':'agi-alpha/next009-delivery-acceptance/v1','scope':SCOPE,'accepted':accepted,**binding,'network_sha256':corpus['network_sha256'],'corpus_dimensions':[len(sources),len(corpus['times_seconds']),len(nodes)],'all_pairs_denominator':len(channels),'all_selected_sensor_outage_checks':checks,'uncalibrated_all_sensor_ambiguous_pairs':[[sources[p['a']],sources[p['b']]] for p in unresolved],'candidate_sensors':sensors,'candidate_size':len(selected),'exhaustive_conventional_control':{**control,'first_sensors':[nodes[s] for s in control['first']] if control['first'] is not None else None},'protected_cases_executed':len(case_rows),'protected_cases_passed':sum(x['passed'] for x in case_rows),'actual_candidate_runtime':runtime,'exposure':'FRESH_PROCEDURALLY_PROTECTED_FINITE_CASES_NOW_EXPOSED' if confirm else 'EXPOSED_DEVELOPMENT','decision_scope':'Finite numerical-model measurement-plan certificate; calibrated exact baseline tie is not discovery or novelty superiority. No field deployment or empirical commercial acceptance.','shared_infrastructure':'Python, model corpus, host and originating assistant model; procedural separation only.','claim_alpha_spent':0,'wall_seconds':time.monotonic()-started,'process_cpu_seconds':time.process_time()-cpu}
    report['cases_executed']=len(case_rows)
    report['cases_passed']=sum(x['passed'] for x in case_rows)
    report['protected_cases_executed']=len(case_rows) if confirm else 0
    report['protected_cases_passed']=sum(x['passed'] for x in case_rows) if confirm else 0
    report['development_cases_executed']=0 if confirm else len(case_rows)
    for path,raw in [(corpus_path,corpus_raw),(plan_path,plan_raw),(protocol_path,protocol_raw),(Path(__file__),source_raw)]:
        if path.read_bytes()!=raw: raise ValueError('FROZEN_BYTES_CHANGED_DURING_VERIFICATION')
    if candidate_path is not None and (candidate_path.read_bytes()!=candidate_raw or runtime_driver.read_bytes()!=driver_raw): raise ValueError('FROZEN_RUNTIME_CHANGED')
    (output/'ACCEPTANCE.json').write_bytes(canonical(report))
    print(json.dumps({k:report[k] for k in ['accepted','exposure','all_pairs_denominator','candidate_size','protected_cases_executed','protected_cases_passed','process_cpu_seconds']}))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--corpus',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);p.add_argument('--protocol',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--confirm',action='store_true');p.add_argument('--freeze',type=Path);p.add_argument('--expected-freeze-sha256');p.add_argument('--candidate',type=Path);p.add_argument('--development-seed');a=p.parse_args()
    frozen=None
    if a.freeze:
        frozen,freeze_raw=read(a.freeze)
        if a.confirm and (not a.expected_freeze_sha256 or sha(freeze_raw)!=a.expected_freeze_sha256): raise ValueError('EXTERNAL_FREEZE_IDENTITY_REQUIRED')
    report=evaluate(a.corpus,a.plan,a.protocol,a.output,a.confirm,frozen,a.candidate,a.development_seed)
    raise SystemExit(0 if report['accepted'] else 1)
