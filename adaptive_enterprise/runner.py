"""Freeze and qualify the adaptive enterprise without rewriting enterprise011."""
import argparse
import copy
import gzip
import hashlib
import json
import multiprocessing
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor
from enterprise.runner import RunLock, canonical, digest, write_json

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'agi-alpha/adaptive012-run/v1'
MAX_WORKERS = 4


def protocol(smoke=False):
    return {'schema':'agi-alpha/adaptive012-protocol/v1','scope':'CONDITIONAL_SIMULATION',
        'edition':'engineering-smoke' if smoke else 'adaptive012-confirmation-002',
        'seeds':[12001] if smoke else list(range(2610301301,2610301305)),
        'exposed_development_seeds':[12001,12002]+list(range(2610301201,2610301205)), 'service_cohort_seed':12013026 if not smoke else 0,
        'worlds':['recurring_complete_service'] if smoke else ['recurring_complete_service','unseen_responsive_rival','demand_shift','competent_imitation','supplier_interruption','delayed_payments','premium_need_mix','joint_adverse'],
        'central_region':['recurring_complete_service','unseen_responsive_rival','demand_shift','competent_imitation','supplier_interruption','delayed_payments','premium_need_mix'],
        'primary_arms':['full_adaptive'] if smoke else ['full_adaptive','strategic_011_public_priors','strong_fixed','ordinary_adaptive'],
        'ablation_arms':[] if smoke else ['no_memory','no_opponent','no_diagnosis','no_instrument','no_capital_adaptation'],
        'ablation_worlds':['demand_shift','competent_imitation'],'ablation_seed_count':2,
        'sensitivity_cases':[] if smoke else ['setup350','setup1500','production3','production8','payment_deadline14','working500'],
        'sensitivity_seed_count':2,
        'economic_criteria':{'minimum_customers':3,'minimum_settled_jobs':12,'minimum_repeat_customers':2,'minimum_profitable_earned_continuations':2,'positive_complete_cost_profit':True,'positive_available_earned':True,'known_obligations_accounted':True,'all_cycles_required':False,'inventory_completion_required':False},
        'risk_choice':{'minimum_central_flywheel_fraction':.75,'minimum_central_cash_survival_fraction':.90,'central_cvar20_lower_bound_microUSD':-750_000_000},
        'hard_requirements':['Native money conservation','Owned state-bound authorized reservations','No protected-fund spending','Actual independent artifact acceptance','No hidden buyer/rival/seed/world information to policy','No future receipts financing current commitments'],
        'scale_seeds':[12001] if smoke else list(range(2610302301,2610302309)),
        'scale_sensitivities':[] if smoke else ['channel_cost2','channel_delay3','conversion_half','demand_half','buffer0','buffer4'],
        'execution_workers':MAX_WORKERS,
        'scheduling':'At most four spawned independent account workers; atomic per-world checkpoints; deterministic registered task/index/report order. Full audit uses the same bound. Financial-only audit omits operating replay and reports that narrower scope explicitly.',
        'weights':'Equal finite-design weights, not calibrated real-market probabilities. Risk tolerances are explicit policies, not laws.',
        'comparison':'Matched source/tools, information interface, initial capital, budgets and keyed private shocks. Online learning permitted under frozen code. Old011publishedverdicts preserved; strategic011public-prior adapter is separately identified.',
        'claims':'Commercial success, competitive adaptation, invention and productive expansion are independent verdicts. Scale is a conditional projection, never native earned cash.',
        'recovery':'Completed-world atomic checkpoints. Interrupted worlds recompute unchanged seeds; local live Account recovery separately tested with retained simulation-only key. Public packages omit private keys.'}


def source_paths(root):
    # Frozen workers must carry every source-bound service dependency, including
    # optional admitted services outside the historical adaptive directories.
    from .instruments import SOURCE_PATHS
    required=set(SOURCE_PATHS)|{'connected_enterprise/__init__.py'}
    if any(not (root/name).is_file() for name in required):
        raise ValueError('ADAPTIVE_INSTRUMENT_SOURCE_DEPENDENCY_MISSING')
    result=[root/name for name in sorted(required)]
    for directory in ['adaptive_enterprise','commercial','enterprise','vendor/alpha_claim','portfolio_scale','portfolio25']:
        result += [p for p in (root/directory).glob('*') if p.is_file() and p.suffix in {'.py','.json','.md'}]
    result += [root/p for p in ['vendor/__init__.py','experiments/__init__.py','experiments/commerce006.py','requirements-commercial010.txt','flywheel/__init__.py','flywheel/strategy.py','flywheel/evidence_executor.py','flywheel/retention.py','flywheel/archive_v2.py','scripts/reassemble_enterprise011.py']]
    result += list((root/'campaign/adaptive-012').glob('*'))
    result += list((root/'tests').glob('test_adaptive*.py'))
    result += [root/'historical/adaptive012-prior-policy/ARCHIVE_V2_SOURCE.json',root/'historical/adaptive012-prior-policy/flywheel/archive_v2.py']
    return sorted({p.relative_to(root).as_posix() for p in result if p.is_file()})


def identity(root):
    files={}
    for name in source_paths(root):
        path=root/name
        if path.is_symlink():raise ValueError('SOURCE_SYMLINK_REFUSED')
        files[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    return {'files':files,'sha256':digest(files)}


def freeze(output,smoke=False):
    output=Path(output).absolute()
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):raise FileExistsError('NEW_OUTPUT_REQUIRED')
    output.mkdir(parents=True)
    source=identity(ROOT)
    for name in source['files']:
        target=output/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    if identity(output/'source')!=source:raise ValueError('EXACT_SNAPSHOT_REQUIRED')
    from .model import default_policy,world_specs
    from .scale import default_config
    frozen={'schema':SCHEMA,'source':source,'protocol':protocol(smoke),'policy':default_policy(),'world_specs':world_specs(),'scale_config':default_config(),'registered_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'git_commit':None}
    if not smoke:
        registered=json.loads((ROOT/'campaign/adaptive-012/PREREGISTRATION.json').read_text())
        if any(registered[k]!=frozen[k] for k in ['protocol','policy','world_specs','scale_config']):raise ValueError('PUBLIC_PREREGISTRATION_DOES_NOT_MATCH_SOURCE')
    try:frozen['git_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
    except (subprocess.CalledProcessError,FileNotFoundError):pass
    frozen['freeze_sha256']=digest(frozen);write_json(output/'FROZEN012.json',frozen)
    return output


def tasks(frozen):
    p=frozen['protocol'];result=[]
    for seed in p['seeds']:
        for world in p['worlds']:
            for arm in p['primary_arms']:result.append({'seed':seed,'world':world,'arm':arm,'kind':'primary','case':None})
    for seed in p['seeds'][:p['ablation_seed_count']]:
        for world in p['ablation_worlds']:
            if world in p['worlds']:
                for arm in p['ablation_arms']:result.append({'seed':seed,'world':world,'arm':arm,'kind':'ablation','case':None})
    for seed in p['seeds'][:p['sensitivity_seed_count']]:
        for case in p['sensitivity_cases']:result.append({'seed':seed,'world':'recurring_complete_service','arm':'full_adaptive','kind':'sensitivity','case':case})
    for task in result:task['id']=f"{task['seed']}-{task['world']}-{task['arm']}"+(('-'+task['case']) if task['case'] else '')
    return result


def task_policy(frozen,task):
    policy=copy.deepcopy(frozen['policy']);case=task['case']
    if case=='setup350':policy['setup_cost']=350_000_000
    elif case=='setup1500':policy['setup_cost']=1_500_000_000
    elif case=='production3':policy['base_production_cost']=3_000_000
    elif case=='production8':policy['base_production_cost']=8_000_000
    elif case=='payment_deadline14':policy['payment_deadline_days']=14
    elif case=='working500':policy['working']=500_000_000
    elif case is not None:raise ValueError('UNREGISTERED_SENSITIVITY')
    return policy


def _file(path,base):return {'path':path.relative_to(base).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}


def scale_sensitivity_config(frozen,case):
    cfg=copy.deepcopy(frozen['scale_config'])
    if case=='channel_cost2':cfg['channel_entry_cost_cents']*=2
    elif case=='channel_delay3':cfg['channel_entry_delay_months']=3
    elif case=='conversion_half':cfg['choice_probability']*=.5
    elif case=='demand_half':cfg['reachable_market_customers']//=2
    elif case=='buffer0':cfg['prudential_buffer_months']=0.
    elif case=='buffer4':cfg['prudential_buffer_months']=4.
    else:raise ValueError('UNREGISTERED_SCALE_SENSITIVITY')
    return cfg


def _read_freeze(output):
    f=json.loads((output/'FROZEN012.json').read_text());expected=f.pop('freeze_sha256')
    if digest(f)!=expected or identity(output/'source')!=f['source']:raise ValueError('FROZEN_SOURCE_OR_PROTOCOL_CHANGED')
    f['freeze_sha256']=expected;return f


def _validate_manifest_origin(frozen,manifest,root):
    from .instruments import SOURCE_PATHS,prepare_services
    from .model import stable_projection
    with tempfile.TemporaryDirectory(prefix='adaptive012-cohort-audit-') as temporary:
        regenerated_root=Path(temporary)
        for name in SOURCE_PATHS:
            target=regenerated_root/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(Path(root)/name,target)
        regenerated=prepare_services(regenerated_root,'service-inputs',cohort_seed=frozen['protocol']['service_cohort_seed'])
        if stable_projection(regenerated)!=stable_projection(manifest):raise ValueError('REGISTERED_SERVICE_COHORT_CHANGED')
        for job in regenerated['jobs']:
            for field in ['input','artifact','receipt']:
                if (Path(root)/job[field]).read_bytes()!=(regenerated_root/job[field]).read_bytes():
                    raise ValueError('REGISTERED_SERVICE_ARTIFACT_BYTES_CHANGED')
    return {'registered_jobs_rederived':len(regenerated['jobs'])}


def _validate_world(result,frozen,task,manifest,root,reexecute=False):
    from .account import audit_account
    policy=task_policy(frozen,task)
    for name,value in {'seed':task['seed'],'arm':task['arm'],'evaluator_world_id':task['world'],'policy_sha256':digest(policy),'manifest_sha256':digest(manifest)}.items():
        if result.get(name)!=value:raise ValueError('WORLD_TASK_BINDING_CHANGED:'+name)
    checked=audit_account(result['owned_account'],root=root,manifest=manifest)
    if checked['summary']!=result['summary'] or result['ledger']!=result['owned_account']['ledger'] or result['paid_jobs']!=sum(x['state']=='released' for x in checked['orders']):raise ValueError('DERIVED_WORLD_FINANCES_CHANGED')
    if reexecute:
        from .model import run_world,stable_projection
        world=next(w for w in frozen['world_specs'] if w['id']==task['world'])
        repeated=run_world(root,manifest,policy,task['seed'],world,task['arm'])
        if stable_projection(repeated)!=stable_projection(result):raise ValueError('DETERMINISTIC_OPERATING_REPLAY_CHANGED')
    return checked


def _children_cpu():
    usage=resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime+usage.ru_stime


def _report_input(result):
    return {**brief(result),'instrument_receipts':result['instrument_receipts']}


def _run_task(payload):
    root,manifest,frozen,task,path=payload
    root,path=Path(root),Path(path);result=None;cpu=time.process_time()
    if path.exists():
        try:result=json.loads(gzip.decompress(path.read_bytes()))
        except (OSError,ValueError,EOFError):shutil.move(str(path),str(path)+'.interrupted-'+str(time.time_ns()))
        if result is not None:_validate_world(result,frozen,task,manifest,root,reexecute=True)
    if result is None:
        from .model import run_world
        from commercial.persistence import atomic_bytes
        world=next(w for w in frozen['world_specs'] if w['id']==task['world'])
        result=run_world(root,manifest,task_policy(frozen,task),task['seed'],world,task['arm'])
        _validate_world(result,frozen,task,manifest,root)
        atomic_bytes(path,gzip.compress(canonical(result),mtime=0))
    return {'result':_report_input(result),'record':_file(path,path.parent.parent),'cpu_seconds':time.process_time()-cpu}


def _audit_task(payload):
    root,output,manifest,frozen,item,task,reexecute=payload
    root,output=Path(root),Path(output);path=output/item['path']
    if item['path']!='worlds/'+task['id']+'.json.gz':raise ValueError('EXACT_WORLD_PATH_REQUIRED')
    if _file(path,output)!={k:item[k] for k in ['path','sha256','bytes']}:raise ValueError('WORLD_BYTES_CHANGED')
    result=json.loads(gzip.decompress(path.read_bytes()))
    _validate_world(result,frozen,task,manifest,root,reexecute=reexecute)
    return _report_input(result)


def _parallel(function,payloads):
    if not payloads:return
    executor=ProcessPoolExecutor(max_workers=min(MAX_WORKERS,len(payloads)),mp_context=multiprocessing.get_context('spawn'))
    futures=[executor.submit(function,payload) for payload in payloads]
    try:
        for future in futures:yield future.result()
    except BaseException:
        for future in futures:future.cancel()
        for process in list((executor._processes or {}).values()):
            if process.is_alive():process.terminate()
        for process in list((executor._processes or {}).values()):process.join(timeout=5)
        raise
    finally:executor.shutdown(wait=True,cancel_futures=True)


def brief(result):
    return {k:result[k] for k in ['arm','evaluator_world_id','seed','conditional_simulated_go','accepted_jobs','paid_jobs','customers','repeat_buyers','profitable_earned_continuations','earned_funded_cycles','summary','cash_survival','stop','operated_cycles','economic_completion_requires_all_cycles','inventory_completion_required','available_earned_surplus','seed_backing_reserves','actual_customers','actual_collections','actual_profit','verdicts']}


def comparisons(results):
    primary={(t['seed'],t['world'],t['arm']):r for t,r in results if t['kind']=='primary'};out={}
    for control in ['strategic_011_public_priors','strong_fixed','ordinary_adaptive']:
        differences=[];by_world={}
        for (seed,world,arm),r in primary.items():
            if arm!='full_adaptive' or (seed,world,control) not in primary:continue
            d=r['summary']['profit']-primary[(seed,world,control)]['summary']['profit'];differences.append(d);by_world.setdefault(world,[]).append(d)
        if differences:out[control]={'pairs':len(differences),'mean_profit_delta_microUSD':sum(differences)/len(differences),'range_microUSD':[min(differences),max(differences)],'worlds':{k:{'pairs':len(v),'mean_delta_microUSD':sum(v)/len(v),'range_microUSD':[min(v),max(v)]} for k,v in by_world.items()},'scope':'Finite matched scenario effects; no empirical market or general optimality claim.'}
    return out


def assemble_report(frozen,results,manifest):
    from .model import aggregate
    p=frozen['protocol'];full=[r for t,r in results if t['kind']=='primary' and t['arm']=='full_adaptive'];central=[r for r in full if r['evaluator_world_id'] in p['central_region']]
    a=aggregate(central);risk=p['risk_choice'];go=a['go_fraction']>=risk['minimum_central_flywheel_fraction'] and a['cash_survival_fraction']>=risk['minimum_central_cash_survival_fraction'] and a['downside_cvar20']>=risk['central_cvar20_lower_bound_microUSD']
    grouped={world:aggregate([r for r in full if r['evaluator_world_id']==world]) for world in p['worlds']};paired=comparisons(results)
    rep=next((r for r in full if r['conditional_simulated_go']),full[0]);comparison=paired.get('ordinary_adaptive',{})
    adaptation='POSITIVE_TESTED_MEAN_VERSUS_ORDINARY_ADAPTIVE' if comparison.get('mean_profit_delta_microUSD',0)>0 else 'NO_MEAN_ADVANTAGE_VERSUS_ORDINARY_ADAPTIVE'
    return {'schema':SCHEMA,'source_sha256':frozen['source']['sha256'],'freeze_sha256':frozen['freeze_sha256'],'scope':'CONDITIONAL_SIMULATION','protocol':p,'central_region':a,'worlds':grouped,'comparisons':paired,'representative':brief(rep),'all_world_summaries':[{'task':t,**brief(r)} for t,r in results],
            'executed_manifest_jobs':len(manifest['jobs']),'unique_component_work_units':len({key for j in manifest['jobs'] for key in j.get('work_keys',[j['id']])}),'joint_bundle_configurations':sum(j['service_id']=='operations_bundle' for j in manifest['jobs']),'executed_service_contracts':sorted({j['service_id'] for j in manifest['jobs'] if j['accepted']}),
            'verdicts':{'conditional_simulated_commercial_flywheel':'SUCCEEDED' if go else 'NOT_ESTABLISHED','competitive_adaptation':adaptation,'invention':'EXECUTED_SOURCE_BOUND_GENERATION; NO_SUPERIORITY_CLAIM' if any(r['instrument_receipts'] for r in full) else 'NOT_EXECUTED_IN_COMMERCE','productive_expansion':'SEE_SOURCE_BOUND_INVESTMENTS_AND_MATCHED_ABLATIONS','actual_commercial_operation':'NOT_EXECUTED'},
            'conclusion':'A conditional simulated commercial flywheel succeeded under the registered adaptive conditions.' if go else 'The registered adaptive commercial region did not meet its criteria; retained individual outcomes and failures remain valid.',
            'evidence_limits':['All customer, competitor, supplier, timing, demand and cost envelopes are disclosed simulation assumptions.','Actual deterministic artifacts and independent acceptance execute; no paid frontier provider call, real receipt or real customer is claimed.','A profitable withdrawal is not itself commercial success; qualifying cases have repeated settled, profitable earned-funded work.','Scale projections do not create spendable native cash.','Risk tolerance is selected policy; accounting conservation, authorization and protection of incurred obligations remain hard.','All controls share available information, starting tools, budgets and shocks. Separate verdicts never become a global AND gate.']}


def worker(output):
    output=Path(output).absolute();frozen=_read_freeze(output)
    if ROOT!=output/'source':raise ValueError('EXECUTE_FROZEN_SNAPSHOT_REQUIRED')
    from .instruments import prepare_services
    from .model import run_world
    start=time.monotonic();cpu=time.process_time();children_cpu=_children_cpu();completed_cpu=0;manifest_path=ROOT/'service-inputs/MANIFEST.json'
    if manifest_path.exists():manifest=json.loads(manifest_path.read_text())
    else:
        if (ROOT/'service-inputs').exists():shutil.move(str(ROOT/'service-inputs'),str(ROOT/('interrupted-inputs-'+str(time.time_ns()))))
        manifest=prepare_services(ROOT,'service-inputs',cohort_seed=frozen['protocol']['service_cohort_seed'])
    _validate_manifest_origin(frozen,manifest,ROOT)
    write_json(output/'SERVICES.json',manifest);directory=output/'worlds';directory.mkdir(exist_ok=True);index=[];results=[]
    planned=tasks(frozen)
    payloads=[(str(ROOT),manifest,frozen,task,str(directory/(task['id']+'.json.gz'))) for task in planned]
    for i,(task,completed) in enumerate(zip(planned,_parallel(_run_task,payloads))):
        index.append({'task':task,**completed['record']});results.append((task,completed['result']));completed_cpu+=completed['cpu_seconds']
        write_json(output/'PROGRESS.json',{'completed':i+1,'planned':len(planned),'last':task['id'],'freeze_sha256':frozen['freeze_sha256'],'parallel_workers':min(MAX_WORKERS,len(planned)),'completed_task_cpu_seconds':completed_cpu})
        if time.monotonic()-start>1800 or time.process_time()-cpu+completed_cpu>7000:raise TimeoutError('EVALUATION_BOUNDARY_CHECKPOINT_PRESERVED')
    from .scale import evaluate_scale
    scale=evaluate_scale(frozen['scale_config'],frozen['protocol']['scale_seeds']);write_json(output/'SCALE.json',scale)
    scale_sens=[]
    for case in frozen['protocol']['scale_sensitivities']:
        cfg=scale_sensitivity_config(frozen,case)
        scale_sens.append({'case':case,'config':cfg,'result':evaluate_scale(cfg,frozen['protocol']['scale_seeds'][:2])})
    write_json(output/'SCALE_SENSITIVITIES.json',scale_sens)
    parent_cpu=time.process_time()-cpu;child_cpu=_children_cpu()-children_cpu
    report=assemble_report(frozen,results,manifest);report['resource_receipt']={'process_cpu_seconds':parent_cpu+child_cpu,'parent_cpu_seconds':parent_cpu,'children_cpu_seconds':child_cpu,'wall_seconds':time.monotonic()-start,'maximum_parallel_workers':MAX_WORKERS,'model_billing':'UNAVAILABLE; modeled envelopes disclosed','paid_model_calls':0};write_json(output/'INDEX.json',{'freeze_sha256':frozen['freeze_sha256'],'worlds':index});write_json(output/'REPORT.json',report)
    write_json(output/'COMPLETE.json',{'source_sha256':frozen['source']['sha256'],'report_sha256':hashlib.sha256((output/'REPORT.json').read_bytes()).hexdigest(),'completed_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())});print(json.dumps({'conclusion':report['conclusion'],'worlds':len(results),'report':str(output/'REPORT.json')}),flush=True)


def audit(output,reexecute=True):
    output=Path(output).absolute()
    if ROOT!=output/'source':
        command=[sys.executable,'-m','adaptive_enterprise','_audit','--output',str(output)]+([] if reexecute else ['--financial-only'])
        done=subprocess.run(command,cwd=output/'source',capture_output=True,text=True)
        if done.returncode:raise ValueError('SNAPSHOT_AUDIT_FAILED:'+done.stderr.strip().splitlines()[-1])
        return json.loads(done.stdout)
    frozen=_read_freeze(output);manifest=json.loads((output/'SERVICES.json').read_text());_validate_manifest_origin(frozen,manifest,ROOT);index=json.loads((output/'INDEX.json').read_text());expected=tasks(frozen)
    if index['freeze_sha256']!=frozen['freeze_sha256'] or [x['task'] for x in index['worlds']]!=expected:raise ValueError('EXACT_COMPLETE_COVERAGE_REQUIRED')
    start_cpu=time.process_time();child_start=_children_cpu()
    payloads=[(str(ROOT),str(output),manifest,frozen,item,task,reexecute) for item,task in zip(index['worlds'],expected)]
    results=list(zip(expected,_parallel(_audit_task,payloads)))
    actual=json.loads((output/'REPORT.json').read_text());expected_report=assemble_report(frozen,results,manifest)
    if {k:v for k,v in actual.items() if k!='resource_receipt'}!=expected_report:raise ValueError('DERIVED_REPORT_CHANGED')
    complete=json.loads((output/'COMPLETE.json').read_text())
    if complete['source_sha256']!=frozen['source']['sha256']:raise ValueError('COMPLETE_SOURCE_IDENTITY_CHANGED')
    if hashlib.sha256((output/'REPORT.json').read_bytes()).hexdigest()!=complete['report_sha256']:raise ValueError('REPORT_IDENTITY_CHANGED')
    from .scale import evaluate_scale
    if json.loads((output/'SCALE.json').read_text())!=evaluate_scale(frozen['scale_config'],frozen['protocol']['scale_seeds']):raise ValueError('SCALE_OUTPUT_CHANGED')
    expected_scale_sens=[{'case':case,'config':scale_sensitivity_config(frozen,case),'result':evaluate_scale(scale_sensitivity_config(frozen,case),frozen['protocol']['scale_seeds'][:2])} for case in frozen['protocol']['scale_sensitivities']]
    if json.loads((output/'SCALE_SENSITIVITIES.json').read_text())!=expected_scale_sens:raise ValueError('SCALE_SENSITIVITY_OUTPUT_CHANGED')
    operating=len(results) if reexecute else 0
    return {'accepted':True,'source_sha256':frozen['source']['sha256'],'native_and_operating_worlds_replayed':operating,'native_worlds_replayed':len(results),'operating_replayed':operating,'qualification_scope':'FULL_NATIVE_AND_OPERATING' if reexecute else 'NATIVE_FINANCIAL_ONLY','maximum_parallel_workers':MAX_WORKERS,'audit_cpu_seconds':time.process_time()-start_cpu+_children_cpu()-child_start,'private_signing_keys_required':False}


def package(output,archive):
    output,archive=Path(output).absolute(),Path(archive).absolute()
    if archive.exists() or output in archive.parents:raise FileExistsError('NEW_ARCHIVE_OUTSIDE_OUTPUT_REQUIRED')
    checked=audit(output)
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in sorted(output.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and not path.name.endswith('.adaptive-simulation-key') and not path.is_symlink():z.write(path,path.relative_to(output))
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:raise ValueError('ZIP_CRC_FAILURE')
        if any(n.endswith('.adaptive-simulation-key') for n in z.namelist()):raise ValueError('PRIVATE_KEY_PUBLICATION_REFUSED')
    return {'path':str(archive),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'qualification':checked}


def main():
    parser=argparse.ArgumentParser(description=__doc__);subs=parser.add_subparsers(dest='command',required=True)
    run=subs.add_parser('run');run.add_argument('--output',required=True);run.add_argument('--smoke',action='store_true')
    for name in ['resume','audit','_worker','_audit']:
        command=subs.add_parser(name);command.add_argument('--output',required=True)
        if name in {'audit','_audit'}:command.add_argument('--financial-only',action='store_true')
    p=subs.add_parser('package');p.add_argument('--output',required=True);p.add_argument('--archive',required=True)
    args=parser.parse_args();output=Path(args.output).absolute()
    if args.command=='run':
        freeze(output,args.smoke);subprocess.run([sys.executable,'-m','adaptive_enterprise','_worker','--output',str(output)],cwd=output/'source',check=True)
    elif args.command in {'resume','_worker'}:
        if ROOT!=output/'source':subprocess.run([sys.executable,'-m','adaptive_enterprise','_worker','--output',str(output)],cwd=output/'source',check=True)
        else:
            with RunLock(output):worker(output)
    elif args.command in {'audit','_audit'}:print(json.dumps(audit(output,reexecute=not args.financial_only)))
    else:print(json.dumps(package(output,args.archive)))
