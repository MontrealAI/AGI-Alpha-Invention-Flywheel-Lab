"""Finite development/confirmation runner with immutable protocol identities."""
from __future__ import annotations
import argparse, hashlib, json, math, os, time, subprocess, sys, tempfile, shutil
from pathlib import Path
import numpy as np
from science import produce, construct_process, response, actions, DESIGNS, EXPANDED_GRAPHS
from reference import observer, evaluate, truth_rates, measure_exact, process_exact

BASE=Path(__file__).resolve().parent
ARMS=('initial','retained','ordinary','equal_content')

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise ValueError('REFUSE_OVERWRITE:'+str(path))
    path.write_text(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n')
def load(path):return json.loads(Path(path).read_text())
def sources():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(BASE.glob('*.py'))}

def observation_only_run(observe, *, arm, retained, noise_bound, budget):
    # The worker gets only the construction files and an observation IPC stream.
    # This is same-host process separation, not a sandbox against malicious code.
    with tempfile.TemporaryDirectory(prefix='outlearn-observation-worker-') as tmp:
        tmp=Path(tmp)
        for name in ('science.py','worker.py'):shutil.copy2(BASE/name,tmp/name)
        child=subprocess.Popen([sys.executable,'-u',str(tmp/'worker.py')],cwd=tmp,
                               stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                               text=True,env={'PATH':os.defpath,'OPENBLAS_NUM_THREADS':'1'})
        transcript=[]
        def send(v):child.stdin.write(json.dumps(v)+'\n');child.stdin.flush()
        send({'arm':arm,'retained':retained,'noise_bound':noise_bound,'budget':budget})
        result=None;query_count=0
        try:
            for line in child.stdout:
                msg=json.loads(line);typ=msg['type']
                if typ=='query':
                    query_count+=1
                    if query_count>budget:raise ValueError('QUERY_BUDGET')
                    reply={'observation':list(map(float,observe(msg['time_s'],msg['fraction_b'])))}
                    transcript.append({'request':msg,'response':reply});send(reply)
                elif typ=='frozen_k1':
                    if digest(msg['artifact'])!=msg['sha256']:raise ValueError('K1_HASH')
                    transcript.append({'frozen_k1':msg['sha256']});send({'construct_k2_from':msg['sha256']})
                elif typ=='result':result=msg
                else:raise ValueError('IPC_MESSAGE')
            child.stdin.close();err=child.stderr.read();rc=child.wait()
            if rc or result is None:raise RuntimeError(f'WORKER_FAILED:{rc}:{err}')
            if result['reference_module_loaded']:raise ValueError('REFERENCE_LEAK')
            if result['k1']['queries']!=query_count:raise ValueError('QUERY_COUNT')
            result['ipc_sha256']=digest(transcript);return result
        finally:
            if child.poll() is None:child.kill();child.wait()

def development(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    protocol={'schema':'outlearn-process/development/v1','stage':'EXPOSED_DEVELOPMENT','seed_start':923000,
              'worlds_per_family':3,'families':['series','parallel','combined','reversible'],
              'noise_bound':.001,'budget':8,'sources':sources(),
              'purpose':'construct a reusable experiment initializer from observed fits, not from ground-truth rates'}
    write(out/'PROTOCOL.json',protocol);rows=[];models=[]
    for j,kind in enumerate(protocol['families']):
        for i in range(3):
            seed=923000+j*100+i;observe,receipts=observer(seed,kind,.001)
            k1=produce(observe,arm='initial',retained={'prefix':[]},noise_bound=.001,budget=8)
            k2=construct_process(k1)
            verdict=evaluate(seed,kind,k1,k2,DESIGNS)
            rows.append({'seed':seed,'family':kind,'k1':k1,'k2':k2,'verdict':verdict})
            models.extend(m['rates'] for m in k1['models'])
    # Compile an intervention recipe from the fitted model archive. No truth_rates
    # calls or evaluation outcomes influence this mathematical selection.
    if not models:raise ValueError('NO_SUPPORTED_DEVELOPMENT_MODELS')
    information=[np.eye(4)*1e-6 for _ in models];prefix=[];search=[]
    for chosen in range(2):
        scores=[]
        for action in actions():
            if action in ((.25,0.),(2.,0.)) or list(action) in prefix:continue
            total=0.;matrices=[]
            for r,F in zip(models,information):
                r=np.array(r);base=response(r,*action);jac=[]
                for k in range(4):
                    pert=r.copy();pert[k]+=1e-4
                    jac.append((response(pert,*action)-base)/1e-4)
                J=np.array(jac).T;F2=F+J.T@J
                matrices.append(F2);total+=np.linalg.slogdet(F2)[1]
            scores.append((total/len(models),-action[0],-action[1],action,matrices))
        winner=max(scores,key=lambda x:x[:3]);prefix.append(list(winner[3]));information=winner[4]
        search.append({'selected':list(winner[3]),'mean_log_determinant':winner[0],
                       'candidates_tested':len(scores)})
    retained={'schema':'outlearn-process/retained/v1','prefix':prefix,'edge_grammar':[list(g) for g in EXPANDED_GRAPHS],
              'method':'greedy expected log-determinant on fitted K1 model archive; known experimental-design method',
              'origin':'data-derived experiment program; developer-authored grammar and learner',
              'model_archive_hash':digest(models),'models_used':len(models),'selection_trace':search,
              'development_hash':digest(rows),'parameter_domain':[0.,3.],
              'validity':'normalized time-invariant first-order concentrations; trusted time/concentration standards'}
    write(out/'DEVELOPMENT.json',rows);write(out/'RETAINED.json',retained)
    return retained

def freeze(out,retained):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    cases=[]
    for j,kind in enumerate(('series','parallel','combined','reversible','nonlinear','gain','noisy','limited')):
        for i in range(8):
            cases.append({'id':f'{kind}-{i:02d}','seed':924000+j*100+i,'family':kind,
                          'noise_bound':.06 if kind=='noisy' else .001,'budget':3 if kind=='limited' else 8})
    p={'schema':'outlearn-process/confirmation/v1','evidence_role':'FRESH_SYNTHETIC_MECHANISMS_NOT_MEASURED_CHEMISTRY',
       'source_hashes':sources(),'retained_hash':digest(retained),'cases':cases,'arms':list(ARMS),
       'primary_metric':'assay count per independently accepted K2, with acceptance/false-candidate outcomes also shown',
       'material_effect':'at least one assay less per accepted K2 than ordinary, with no lower K2 acceptance and no more false candidates',
       'criteria':{'max_fresh_concentration_error':.025,'min_product_yield':.40,'max_score_regret':.02},
       'call_budget_includes_failures':True,'first_use_includes_development':True,
       'role_separation':'same-author independent ODE; worker process receives no rates, case labels or seeds; not external blinding or a malicious-code sandbox',
       'model_calls_in_runtime':0,'reselection':False,'stopping':'execute every predeclared case exactly once per arm; record recoverable engineering exceptions',
       'business_gate':'only independently accepted computational artifacts may be sold as simulated engineering artifacts; no physical release claims'}
    write(out/'PROTOCOL.json',p);write(out/'RETAINED.json',retained);return digest(p)

def check_freeze(out):
    p=load(Path(out)/'PROTOCOL.json');ret=load(Path(out)/'RETAINED.json')
    if p['source_hashes']!=sources() or p['retained_hash']!=digest(ret):raise ValueError('FROZEN_SOURCE_CHANGED')
    return p,ret

def confirm(out,case_ids=None):
    out=Path(out);p,ret=check_freeze(out);started=time.monotonic()
    for case in p['cases']:
        if case_ids is not None and case['id'] not in case_ids:continue
        target=out/'cases'/f"{case['id']}.json"
        if target.exists():continue
        rows=[]
        for arm in p['arms']:
            observe,receipts=observer(case['seed'],case['family'],case['noise_bound'])
            work=observation_only_run(observe,arm=arm,retained=ret,noise_bound=case['noise_bound'],budget=case['budget'])
            k1=work['k1'];k1_hash=work['k1_sha256'];k2=work['k2']
            result=evaluate(case['seed'],case['family'],k1,k2,DESIGNS)
            rows.append({'arm':arm,'k1':k1,'k1_sha256':k1_hash,'k2':k2,'verdict':result,
                         'observation_receipts':receipts,'protocol_sha256':digest(p),'ipc_sha256':work['ipc_sha256'],'reference_module_loaded':work['reference_module_loaded']})
        write(target,{'case':case,'rows':rows})
        print(case['id'],[(r['arm'],r['k1']['queries'],r['verdict']['k2_design_acceptance']) for r in rows],flush=True)
    return {'wall_seconds':time.monotonic()-started}

def summarize(out):
    out=Path(out);p,ret=check_freeze(out);records=[]
    for c in p['cases']:
        path=out/'cases'/f"{c['id']}.json"
        if not path.exists():raise ValueError('INCOMPLETE:'+c['id'])
        records.append(load(path))
    summaries={};by_family={}
    for arm in p['arms']:
        rows=[next(r for r in x['rows'] if r['arm']==arm) for x in records]
        accepted=sum(r['verdict']['k2_design_acceptance'] for r in rows)
        queries=sum(r['k1']['queries'] for r in rows)
        summaries[arm]={'cases':len(rows),'k1_accepted':sum(r['verdict']['k1_predictive_acceptance'] for r in rows),
                        'k2_accepted':accepted,'false_candidates':sum(r['verdict']['false_deployment'] for r in rows),
                        'abstentions':sum(r['verdict']['abstained'] for r in rows),'queries_including_failures':queries,
                        'queries_per_accepted_k2':queries/accepted if accepted else None,
                        'model_family_expansions':sum(r['k1']['expansions'] for r in rows),
                        'producer_cpu_seconds':sum(r['k1']['cpu_seconds'] for r in rows)}
        by_family[arm]={}
        for kind in sorted({x['case']['family'] for x in records}):
            part=[next(r for r in x['rows'] if r['arm']==arm) for x in records if x['case']['family']==kind]
            by_family[arm][kind]={'n':len(part),'accepted':sum(r['verdict']['k2_design_acceptance'] for r in part),
                                  'false_candidates':sum(r['verdict']['false_deployment'] for r in part),
                                  'queries':sum(r['k1']['queries'] for r in part)}
    pairs=[]
    for x in records:
        a=next(r for r in x['rows'] if r['arm']=='retained');b=next(r for r in x['rows'] if r['arm']=='ordinary')
        pairs.append((int(a['verdict']['k2_design_acceptance'])-int(b['verdict']['k2_design_acceptance']),a['k1']['queries']-b['k1']['queries']))
    delta=np.array(pairs);rng=np.random.default_rng(924999)
    boot=delta[rng.integers(0,len(delta),size=(4000,len(delta)))].mean(axis=1)
    a=summaries['retained'];b=summaries['ordinary']
    advantage=(a['k2_accepted']>=b['k2_accepted'] and a['false_candidates']<=b['false_candidates'] and
               a['queries_per_accepted_k2'] is not None and b['queries_per_accepted_k2']-a['queries_per_accepted_k2']>=1)
    result={'protocol_sha256':digest(p),'retained':ret,'summary':summaries,'by_family':by_family,
            'paired_effect':{'acceptance_difference':float(delta[:,0].mean()),'query_difference':float(delta[:,1].mean()),
                            'paired_bootstrap_95_percent':np.quantile(boot,[.025,.975],axis=0).tolist(),
                            'uncertainty_scope':'empirical resampling of this authored balanced set, not population chemistry'},
            'discovery_method_advantage':advantage,'real_assays':0,'real_customers':0,
            'retained_program_executed':True,'unrestricted_model_generated_discovery':False,
            'source_hashes':p['source_hashes']}
    write(out/'RESULTS.json',result);return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['development','freeze','confirm','summarize']);ap.add_argument('--out',required=True);ap.add_argument('--retained');ap.add_argument('--cases',nargs='*');a=ap.parse_args()
    if a.command=='development':r=development(a.out)
    elif a.command=='freeze':r=freeze(a.out,load(a.retained))
    elif a.command=='confirm':r=confirm(a.out,a.cases)
    else:r=summarize(a.out)
    print(json.dumps(r,indent=2))
