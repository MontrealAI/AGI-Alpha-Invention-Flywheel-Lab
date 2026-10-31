"""Freeze, operate, resume, independently audit and package one enterprise path."""
from __future__ import annotations
import argparse
import copy
import gzip
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor
from adaptive_enterprise.runner import source_paths as inherited_paths
from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from enterprise.runner import RunLock
from .engine import default_config

ROOT=Path(__file__).resolve().parents[1]

def source_paths(root):
    names=set(inherited_paths(root))
    for folder,pattern in [('connected_enterprise','*.py'),('tests','test_connected*.py'),('tests','test_native*.py'),('tests','test_transition*.py'),('campaign/connected-014','*'),('campaign/completion-015','*'),('examples/native_capital020','*.json'),('docs/native-capital020','*.md'),('historical/successor022','*'),('historical/cas-parent7d','*'),('historical/operator022','*'),('examples/connected022','*.json'),('docs/successor022','*.md')]:
        names.update(p.relative_to(root).as_posix() for p in (root/folder).glob(pattern) if p.is_file())
    names.update(p for p in ['run_connected014.py','scripts/qualify_connected014.py','scripts/render_connected014_report.py','scripts/release_connected014.py','verification/scan_adaptive_cancellation_history.py','evidence/cancellation-retirement/HISTORICAL_SCAN.json','evidence/cancellation-retirement/COUNTEREXAMPLE.before.json','docs/connected014/OPERATOR.md','AGENTS.md','README.md','.github/workflows/connected014.yml','.github/workflows/connected014-release.yml'] if (root/p).is_file())
    names.update(p for p in ['tests/__init__.py','tests/connected_legacy_fixture.py','tests/test_publication_composition.py'] if (root/p).is_file())
    names.update(p for p in ['campaign/successor-022/qualify.py','campaign/successor-022/QUALIFICATION_PROTOCOL.json','campaign/successor-022/CONTINUATION_PROTOCOL.json'] if (root/p).is_file())
    names.update(p.relative_to(root).as_posix() for p in (root/'campaign/successor-022/proofs').glob('*.py'))
    names.update(p for p in ['campaign/successor-022/proofs/maturity_successor_protocol.json','campaign/successor-022/proofs/ADAPTATION.json'] if (root/p).is_file())
    names.update(p.relative_to(root).as_posix() for p in (root/'campaign/connected-registrations').glob('*.json') if p.is_file())
    names.update(p for p in ['campaign/overnight-022/OPERATOR_INPUT.json','scripts/measure_overnight022.py','scripts/run_regression_shard.py'] if (root/p).is_file())
    names.update(p for p in ['docs/completion015/'+name for name in ['PAPER.pdf','PAPER.tex','index.html','REPORT.md','PUBLICATION.json','PDF_QA.json']] if (root/p).is_file())
    names.update(p for p in ['docs/completion024.md','scripts/operate_completion024.py'] if (root/p).is_file())
    names.update(p for p in ['docs/completion023/OPERATOR.md','scripts/export_recovered023.py','campaign/completion-023/PLAN.json'] if (root/p).is_file())
    return sorted(name for name in names if (root/name).is_file())

def identity(root):
    root=Path(root).resolve();files={}
    for name in source_paths(root):
        p=root/name
        if p.is_symlink() or any(q.is_symlink() for q in p.parents):raise ValueError('SOURCE_SYMLINK_REFUSED')
        files[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    return {'files':files,'sha256':digest(files)}

def source002_protocol(smoke=False):
    return {'schema':'agi-alpha/connected014-protocol/v1','edition':'development-smoke' if smoke else 'connected014-confirmation-002','scope':'CONDITIONAL_SIMULATION',
        'central_seeds':[14001] if smoke else [2610301601,2610301602,2610301603,2610301604],
        'adverse_seeds':[] if smoke else [2610301701,2610301702],'channel_control_seeds':[],
        'development_excluded':[14001,14002,14003,14004,14005,14006,2610301401,2610301402,2610301403,2610301404,2610301501,2610301502],'cases':['central'] if smoke else ['central','weak_channel','price_pressure','delayed_and_expensive'],
        'arms':['baseline','growth'] if smoke else ['growth','competitive_growth'],'candidate_arm':'growth' if smoke else 'competitive_growth','control_arm':'baseline' if smoke else 'growth','pricing_extension_setup_microUSD':5000000,'pricing_extension_per_quote_microUSD':50000,'case_design':'Central4pairedseeds; three separatelydeclared adversecases2pairedseeds. Retainedgrowthcontrol andcostedpublicpricingoption haveequalcapital/actionsasidefromthepriceextension. Common exogenous customer/day/service payment and need identities; endogenous activity and artifact assignment may differ.',
        'risk':{'central_minimum_commercial_fraction':.75,'central_minimum_cash_survival_fraction':1.,'growth_minimum_positive_paired_fraction':.75,'central_maximum_loss_microUSD':750_000_000,'hard_native_and_semantic_integrity':True},
        'completion':{'minimum_collected_deliveries':12,'minimum_paying_customers':3,'minimum_profitable_earned_continuations':2,'positive_complete_cost_profit':True,'positive_available_earnings':True,'minimum_repeat_customers':2,'obligations_covered':True},
        'comparison':'Equalstartingcapital,services,completequality,privatebuyer/marketassumptionsandcontractswithinpair. Non-smoke comparesretainedgrowthwiththecostedpublicpriceextension. Smokecomparesownedbaselinewithgrowth. Equalpriceutilitytiesusestablekeyedneutralindifference. Thisestimatescommercialoptionvalue,NOTgeneralalgorithmicoptimality.',
        'selection':'Ordinary observed-contribution heuristic, frozen before confirmation; no hidden buyer values, future shocks or evaluator case labels in seller policy. Decline/retaincash allowed. No developmentcontroller tournament.',
        'clock':'Integerhours/native dayfield; production2hours, acceptance1hour, clearing48hours baseline. Expiry/reinvestment eventcausal; tailobligations retained. Calendar epoch2026-11-01T00Z.',
        'resource_billing':'Actual deterministic executors/checkers, no paidmodelcalls. Modeled completecost envelopes; host/modelbilling unavailable. Sensitivities do not turn assumptions into calibration.',
        'recovery':'Live-state event intent persisted before mutations; signed command WAL/native CAS recovers exact commitments. Reopen requires retained local simulation key. Public copies support audit/reproduction, not takeover.',
        'inference':'Finite authored worlds, not calibrated real success probabilities. Historical economic results never relabeled. Native record aggregation is exact accounting, not validated forward-demand aggregation.',
        'service_cohort_seed':14013026 if smoke else 14023026,'workers':4}

def protocol(smoke=False):
    if smoke:
        return source002_protocol(True)
    registration=json.loads((ROOT/'campaign/completion-015/PREREGISTRATION.json').read_text())
    return registration['protocol']

def config_for(case,smoke=False):
    cfg=default_config()
    if smoke:cfg['horizon_days']=21;cfg['customer_pool']=12
    if case=='weak_channel':
        for c in cfg['channels'].values():c['realization_bps']=1000;c['overlap_bps']=8500;c['activation_reliability_bps']=7000
        cfg['retention_bps']=7500
    elif case=='price_pressure':cfg['price_pressure_bps']=5500;cfg['value_bps']=7000;cfg['arrival_bps']=4500
    elif case=='delayed_and_expensive':
        cfg['clearing_hours']=168;cfg['nonpayment_bps']=1200;cfg['production_cost']*=3;cfg['supplier_outage_start_day']=18;cfg['supplier_outage_days']=10
        for c in cfg['channels'].values():c['price_microUSD']*=10;c['lead_days']*=3
        cfg['setup_cost']=500_000_000
    elif case!='central':raise ValueError('REGISTERED_CASE_REQUIRED')
    return cfg

def task_config(f,task):
    cfg=copy.deepcopy(f['configs'][task['case']])
    if task['arm']=='competitive_growth':
        cfg['setup_cost']+=f['protocol']['pricing_extension_setup_microUSD']
        cfg['qualification_cost']+=f['protocol']['pricing_extension_per_quote_microUSD']
    return cfg

def tasks(p):
    result=[]
    for seed in p['central_seeds']:
        for arm in p['arms']:result.append({'seed':seed,'case':'central','arm':arm})
    for seed in p['adverse_seeds']:
        for case in p['cases'][1:]:
            for arm in p['arms']:result.append({'seed':seed,'case':case,'arm':arm})
    for seed in p['channel_control_seeds']:result.append({'seed':seed,'case':'central','arm':'channel'})
    for row in result:row['id']=f"{row['seed']}-{row['case']}-{row['arm']}"
    return result

def write(path,value):atomic_bytes(Path(path),canonical(value)+b'\n')

def freeze(output,smoke=False,registration=None):
    if registration is not None:
        from .registration import validate
        registration=validate(registration)
        if smoke:raise ValueError('SMOKE_AND_CUSTOM_REGISTRATION_ARE_DISTINCT')
    output=Path(output).resolve()
    if output.exists() or any(p.is_symlink() for p in [output,*output.parents]):raise FileExistsError('NEW_NORMALIZED_OUTPUT_REQUIRED')
    output.mkdir(parents=True);source=identity(ROOT)
    for name in source['files']:
        target=output/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    if identity(output/'source')!=source:raise ValueError('FROZEN_COPY_CHANGED')
    registration_path=None
    if registration is not None:
        from .registration import registered_protocol
        registration_path='campaign/connected-registrations/'+digest(registration)+'.json'
        write(output/'source'/registration_path,registration)
        source=identity(output/'source')
        p=registered_protocol(registration,protocol(False));configs=registration['configs']
    else:p=protocol(smoke);configs={case:config_for(case,smoke) for case in p['cases']}
    if not smoke and registration is None:
        registration=json.loads((ROOT/'campaign/completion-015/PREREGISTRATION.json').read_text())
        if registration['protocol']!=p or registration['configs']!={case:config_for(case) for case in p['cases']}:raise ValueError('PUBLIC_PREREGISTRATION_DOES_NOT_MATCH')
    f={'schema':'agi-alpha/connected014-freeze/v1','source':source,'protocol':p,'configs':configs,'registered_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'git_commit':None}
    if registration_path is not None:f['registration_path']=registration_path
    try:f['git_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
    except (OSError,subprocess.CalledProcessError):pass
    f['sha256']=digest(f);write(output/'FROZEN.json',f);return output

def read_freeze(output):
    output=Path(output).resolve();f=strict_json((output/'FROZEN.json').read_bytes());expected=f.pop('sha256')
    if digest(f)!=expected or identity(output/'source')!=f['source']:raise ValueError('FROZEN_SOURCE_OR_CONFIGURATION_CHANGED')
    if 'registration_path' in f:
        from .registration import validate,registered_protocol
        name=f['registration_path']
        if not isinstance(name,str) or not name.startswith('campaign/connected-registrations/') or Path(name).name!=name.removeprefix('campaign/connected-registrations/'):
            raise ValueError('SOURCE_BOUND_REGISTRATION_PATH_REQUIRED')
        if name not in f['source']['files']:raise ValueError('SOURCE_BOUND_REGISTRATION_REQUIRED')
        registered=validate(strict_json((output/'source'/name).read_bytes()))
        if name!='campaign/connected-registrations/'+digest(registered)+'.json':raise ValueError('REGISTRATION_CONTENT_ADDRESS_CHANGED')
        expected_protocol=registered_protocol(registered,protocol(False));configs=registered['configs']
    else:
        smoke=f['protocol'].get('edition')=='development-smoke';expected_protocol=protocol(smoke)
        configs={case:config_for(case,smoke) for case in expected_protocol['cases']}
    if f['protocol']!=expected_protocol or f['configs']!=configs:raise ValueError('FROZEN_REGISTRATION_NOT_REDERIVED_FROM_SOURCE')
    f['sha256']=expected;return f

def _task(payload):
    root,manifest,output,f,task,max_events=payload
    from .engine import run_world
    from .verify import audit
    from .scale import analyze
    cfg=task_config(f,task);directory=Path(output)/'worlds'/task['id'];start=time.process_time()
    result=run_world(root,manifest,cfg,task['seed'],task['arm'],directory,source=f['source'],stop_after_events=max_events);result['case']=task['case']
    if not result['complete']:
        write(directory/'RESULT.json',result)
        return {'task':task,'complete':False,'result_sha256':digest(result),'cpu_seconds':time.process_time()-start,'processed_events':result['processed_events']}
    receipt=audit(root,manifest,result);growth=analyze(result)
    write(directory/'RESULT.json',result);write(directory/'AUDIT.json',receipt);write(directory/'GROWTH.json',growth)
    return {'task':task,'complete':True,'result':brief(result),'result_sha256':digest(result),'audit':receipt,'growth':growth,'cpu_seconds':time.process_time()-start}

def brief(r):
    return {k:r[k] for k in ['seed','case','arm','summary','complete','accepted_jobs','paid_jobs','customers','repeat_customers','profitable_earned_continuations','conditional_simulated_commercial_success','productive_expansion','processed_events']}

def _summary(f,items,results):
    from .scale import compare,frontier
    central=[r for r in results if r['case']=='central' and r['arm']==f['protocol']['candidate_arm']];risk=f['protocol']['risk'];success=sum(r['conditional_simulated_commercial_success'] for r in central)
    covered=lambda r:r['summary']['payables']==0 and not r['summary']['investmentStopped'] and r['summary']['cash']>=sum(r['summary'][x] for x in ['tailReserve','custodyReserve','workingCapital'])
    fraction=success/len(central);survival=sum(covered(r) for r in central)/len(central)
    growth_evidence=any(x['later_settled_order_ids'] for r in central for x in r['productive_expansion'])
    paired=compare(results,baseline=f['protocol']['control_arm'],candidate=f['protocol']['candidate_arm']);central_pairs=[p for p in paired['pairs'] if p['identity'][1]=='central'];positive_growth=sum(p['collected_delivery_delta']>0 and p['profit_delta_microUSD']>0 for p in central_pairs);growth_fraction=positive_growth/len(central_pairs) if central_pairs else 0
    growth_success=growth_evidence and growth_fraction>=risk['growth_minimum_positive_paired_fraction'] and sum(p['profit_delta_microUSD'] for p in central_pairs)>0
    return {'schema':'agi-alpha/connected014-report/v1','scope':'CONDITIONAL_SIMULATION','source_sha256':f['source']['sha256'],'frozen_sha256':f['sha256'],'worlds':len(results),'all_independent_audits_passed':all(i['audit'].get('accepted',False) for i in items),
        'outcomes':{'operating_implementation':'EXECUTED_WITH_INDEPENDENT_FINANCIAL_AND_OPERATING_SEMANTIC_AUDIT' if all(i['audit'].get('accepted',False) for i in items) else 'NOT_QUALIFIED','commercial_result':'CONDITIONAL_SUCCESS' if fraction>=risk['central_minimum_commercial_fraction'] and survival>=risk['central_minimum_cash_survival_fraction'] and min(r['summary']['profit'] for r in central)>=-risk['central_maximum_loss_microUSD'] else 'NOT_ESTABLISHED_IN_REGISTERED_REGION','growth_result':'CONDITIONAL_INCREASE_IN_PROFITABLE_DELIVERY' if growth_success else 'CAPABILITY_USE_WITHOUT_QUALIFIED_MATCHED_GROWTH' if growth_evidence else 'NOT_ESTABLISHED','billion_native_scale':'NOT_ESTABLISHED'},
        'central':{'runs':len(central),'commercial_successes':success,'fraction':fraction,'cash_survival_fraction':survival,'minimum_profit':min(r['summary']['profit'] for r in central),'maximum_profit':max(r['summary']['profit'] for r in central),'minimum_paid_jobs':min(r['paid_jobs'] for r in central),'maximum_paid_jobs':max(r['paid_jobs'] for r in central)},
        'growth_criterion':{'positive_delivery_and_profit_pairs':positive_growth,'central_pairs':len(central_pairs),'fraction':growth_fraction,'minimum_registered_fraction':risk['growth_minimum_positive_paired_fraction']},'representative':brief(central[0]),'comparisons':paired,'frontier':frontier(results),'protocol':f['protocol'],'worlds_index':[{k:i[k] for k in ['task','result_sha256','cpu_seconds']} for i in items],
        'next_action':'Use matched realized incremental contribution to retain/renew channels and capacity; close finite artifact/audience/working-capital constraints with a new costed qualified capability before claiming a native scale bridge. Historical aggregate billion projections remain separate hypotheses.',
        'actual_commerce':{'customers':0,'collections':0,'profit':None},'limits':default_config()['limits']}

def worker(output,max_events=None):
    if max_events is not None and (type(max_events) is not int or max_events<1):raise ValueError('POSITIVE_EVENT_STEP_REQUIRED')
    output=Path(output).resolve();f=read_freeze(output);root=output/'source'
    from adaptive_enterprise.instruments import prepare_services
    with RunLock(output):
        manifest_path=output/'SERVICES.json'
        if manifest_path.exists():manifest=json.loads(manifest_path.read_text())
        else:manifest=prepare_services(root,'service-inputs',cohort_seed=f['protocol']['service_cohort_seed']);write(manifest_path,manifest)
        payloads=[(str(root),manifest,str(output),f,t,max_events) for t in tasks(f['protocol'])];items=[]
        with ProcessPoolExecutor(max_workers=min(f['protocol']['workers'],len(payloads)),mp_context=multiprocessing.get_context('spawn')) as pool:
            for item in pool.map(_task,payloads):
                items.append(item);write(output/'PROGRESS.json',{'completed':sum(i['complete'] for i in items),'visited':len(items),'total':len(payloads),'last_task':item['task']['id'],'complete':all(i['complete'] for i in items) and len(items)==len(payloads)})
        if not all(i['complete'] for i in items):
            return {'schema':'agi-alpha/connected014-paused/v1','complete':False,'source_sha256':f['source']['sha256'],'worlds':items,'next_action':'operate or resume the same output and retained private account authority; no reseeding'}
        results=[json.loads((output/'worlds'/i['task']['id']/'RESULT.json').read_text()) for i in items]
        report=_summary(f,items,results);write(output/'REPORT.json',report);write(output/'COMPLETE.json',{'source_sha256':f['source']['sha256'],'report_sha256':digest(report),'worlds':len(items)});return report

def comparison(output,control=None,candidate=None):
    output=Path(output).resolve();f=read_freeze(output)
    control=control or f['protocol']['control_arm'];candidate=candidate or f['protocol']['candidate_arm']
    if control==candidate or control not in f['protocol']['arms'] or candidate not in f['protocol']['arms']:
        raise ValueError('DISTINCT_REGISTERED_COMPARISON_ARMS_REQUIRED')
    checked=audit_output(output)
    if not checked['accepted']:raise ValueError('ACCEPTED_NATIVE_AND_OPERATING_AUDIT_REQUIRED')
    from .scale import compare
    results=[json.loads((output/'worlds'/task['id']/'RESULT.json').read_text()) for task in tasks(f['protocol']) if task['arm'] in {control,candidate}]
    result=compare(results,baseline=control,candidate=candidate)
    result.update(source_sha256=f['source']['sha256'],frozen_sha256=f['sha256'],audit=checked,
                  evidence_role=f['protocol'].get('evidence_role','reproduction'),funding_authority=False)
    return result

def audit_output(output):
    output=Path(output).resolve();f=read_freeze(output);manifest=json.loads((output/'SERVICES.json').read_text());receipts=[];items=[];results=[]
    from .verify import audit
    from .scale import analyze
    from adaptive_enterprise.runner import _validate_manifest_origin
    cohort=_validate_manifest_origin({'protocol':{'service_cohort_seed':f['protocol']['service_cohort_seed']}},manifest,output/'source')
    stored=json.loads((output/'REPORT.json').read_text());indices=stored.get('worlds_index',[])
    expected_tasks=tasks(f['protocol'])
    if len(indices)!=len(expected_tasks):raise ValueError('REGISTERED_WORLD_INDEX_REQUIRED')
    for task,index in zip(expected_tasks,indices):
        directory=output/'worlds'/task['id'];result=json.loads((directory/'RESULT.json').read_text())
        if any(result[k]!=task[k] for k in ['seed','case','arm']) or result['config']!=task_config(f,task) or result['source']!=f['source'] or not result['complete']:raise ValueError('WORLD_CONFIGURATION_OR_TASK_CHANGED')
        if index['task']!=task or index['result_sha256']!=digest(result) or type(index['cpu_seconds']) not in {int,float} or index['cpu_seconds']<0:raise ValueError('WORLD_RESULT_INDEX_BINDING_CHANGED')
        from .transition_evidence import output_scope
        with output_scope(directory):checked=audit(output/'source',manifest,result)
        growth=analyze(result)
        if json.loads((directory/'GROWTH.json').read_text())!=growth:raise ValueError('GROWTH_REPORT_NOT_REDERIVED_FROM_NATIVE_RECORDS')
        if json.loads((directory/'AUDIT.json').read_text())!=checked:raise ValueError('WORLD_AUDIT_RECEIPT_CHANGED')
        receipts.append(checked);results.append(result);items.append({'task':task,'result':brief(result),'result_sha256':digest(result),'audit':checked,'growth':growth,'cpu_seconds':index['cpu_seconds']})
    expected_report=_summary(f,items,results)
    if stored!=expected_report:raise ValueError('TOP_LEVEL_COMMERCIAL_REPORT_CHANGED')
    complete={'source_sha256':f['source']['sha256'],'report_sha256':digest(expected_report),'worlds':len(items)}
    if json.loads((output/'COMPLETE.json').read_text())!=complete:raise ValueError('COMPLETION_RECEIPT_CHANGED')
    receipt={'schema':'agi-alpha/connected014-package-audit/v1','source_sha256':f['source']['sha256'],'worlds':len(receipts),'accepted':all(r['accepted'] for r in receipts),'scope':'NATIVE_FINANCE_AND_OPERATING_SEMANTICS_WITH_ARTIFACT_REEXECUTION_AND_REPORT_REDERIVATION','service_cohort':cohort,'simulation_keys_required':False,'resource_cpu_metadata':'Command resource observations retained, not independently reproduced timing measurements'};write(output/'PACKAGE_AUDIT.json',receipt);return receipt

def package(output,archive):
    output=Path(output).resolve();archive=Path(archive).resolve();read_freeze(output)
    checked=audit_output(output)
    if not checked['accepted']:raise ValueError('ACCEPTED_COMPLETE_PACKAGE_AUDIT_REQUIRED')
    if archive.exists() or output in archive.parents:raise ValueError('NEW_ARCHIVE_OUTSIDE_OUTPUT_REQUIRED')
    recovery={}
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(output.rglob('*')):
            if not p.is_file() or p.is_symlink() or p.name.endswith('.adaptive-simulation-key') or p.suffix in {'.sqlite','-wal','-shm'} or '__pycache__' in p.parts or p.name in {'WORKER.lock','RUN.lock'}:continue
            if '.sqlite' in p.name:continue
            relative=p.relative_to(output)
            if 'account.sqlite.rejected-operating-intents' in relative.parts:
                if p.suffix!='.json':raise ValueError('DECLARED_PUBLIC_RECOVERY_EVIDENCE_REQUIRED')
                name='/'.join('public-rejected-operating-intents' if part=='account.sqlite.rejected-operating-intents' else part for part in relative.parts)
                raw=p.read_bytes();recovery[name]={'original_path':relative.as_posix(),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
                z.writestr(name,raw)
            elif any('.sqlite' in part for part in relative.parts):
                continue
            else:z.write(p,relative.as_posix())
        if recovery:z.writestr('PUBLIC_RECOVERY_INDEX.json',json.dumps({'schema':'agi-alpha/keyfree-rejected-intent-transport/v1','scope':'Original key-free rejected-intent evidence preserved byte-for-byte; no account database or signing key.','files':recovery},sort_keys=True,indent=2)+'\n')
    return {'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'scope':'KEY_FREE_AUDIT_AND_FRESH_REPRODUCTION_NOT_ACCOUNT_TAKEOVER'}

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    for name in ['run','resume','operate','audit','scoreboard','comparison','_worker']:
        s=sub.add_parser(name);s.add_argument('--output',required=True)
        if name=='run':s.add_argument('--smoke',action='store_true')
        if name in {'operate','_worker'}:s.add_argument('--max-events',type=int)
        if name=='comparison':s.add_argument('--control');s.add_argument('--candidate');s.add_argument('--config')
    s=sub.add_parser('register');s.add_argument('--config',required=True);s.add_argument('--output',required=True)
    s.add_argument('--seed',type=int);s.add_argument('--arm',default='growth',choices=['baseline','channel','growth','competitive_growth']);s.add_argument('--cohort-seed',type=int)
    s=sub.add_parser('package');s.add_argument('--output',required=True);s.add_argument('--archive',required=True)
    s=sub.add_parser('_capital');s.add_argument('--output',required=True);s.add_argument('--action',required=True,choices=['register','operate','audit','scoreboard','comparison']);s.add_argument('--max-events',type=int)
    s=sub.add_parser('upgrade');s.add_argument('--output',required=True);s.add_argument('--historical-source',required=True);s.add_argument('--manifest',required=True);s.add_argument('--policy',required=True);s.add_argument('--expected-checkpoint',required=True);s.add_argument('--id',required=True);s.add_argument('--transition-format',choices=['v1','v2-cas'],default='v1')
    s=sub.add_parser('recover-checkpoint');s.add_argument('--output',required=True);s.add_argument('--historical-source',required=True);s.add_argument('--manifest',required=True);s.add_argument('--expected-checkpoint',required=True);s.add_argument('--id',required=True)
    s=sub.add_parser('recover-transition-evidence');s.add_argument('--output',required=True);s.add_argument('--historical-source',required=True);s.add_argument('--manifest',required=True);s.add_argument('--expected-checkpoint',required=True);s.add_argument('--id',required=True)
    s=sub.add_parser('_connected');s.add_argument('--output',required=True);s.add_argument('--action',required=True,choices=['operate','audit','scoreboard','upgrade']);s.add_argument('--max-events',type=int)
    args=p.parse_args();raw_output=Path(args.output).expanduser()
    if any(q.is_symlink() for q in [raw_output,*raw_output.parents]):raise ValueError('OUTPUT_SYMLINK_REFUSED')
    output=raw_output.resolve()
    from . import capital,operations
    if args.command=='recover-transition-evidence':
        from .upgrades import recover_transition_evidence
        result=recover_transition_evidence(args.historical_source,strict_json(Path(args.manifest).read_bytes()),output,expected_checkpoint=args.expected_checkpoint,ident=args.id)
        print(json.dumps(result,sort_keys=True));return 0
    if args.command=='recover-checkpoint':
        from .recovery import recover_checkpoint
        result=recover_checkpoint(args.historical_source,args.manifest,output,expected_checkpoint=args.expected_checkpoint,ident=args.id)
        print(json.dumps(result,sort_keys=True));return 0
    if args.command=='upgrade':
        d=operations.prepare_upgrade(ROOT,args.historical_source,args.manifest,output,policy=strict_json(Path(args.policy).read_bytes()),expected_checkpoint_sha256=args.expected_checkpoint,ident=args.id,transition_format=args.transition_format)
        return subprocess.call([sys.executable,'-m','connected_enterprise','_connected','--action','upgrade','--output',str(output)],cwd=output/d['source_dir'])
    if args.command=='_connected':
        if args.action=='operate':
            r=operations.operate(output,max_events=args.max_events);result={'complete':r['complete'],'summary':r['summary'],'processed_events':r['processed_events']}
        elif args.action=='upgrade':result=operations.upgrade(output)
        elif args.action=='audit':result=operations.audit(output)
        else:result=operations.scoreboard(output)
        print(json.dumps(result,sort_keys=True));return 0
    configuration=None
    if args.command=='register' or args.command=='comparison' and args.config is not None:
        config_path=Path(args.config).expanduser()
        if any(q.is_symlink() for q in [config_path,*config_path.parents]):raise ValueError('REGISTRATION_SYMLINK_REFUSED')
        configuration=strict_json(config_path.read_bytes())
    if (args.command=='register' and configuration.get('schema')!='agi-alpha/connected014-registration/v1'
            or args.command=='comparison' and args.config is not None):
        if args.command=='register' and configuration.get('schema')=='agi-alpha/connected014-config/v1':
            d=operations.register(ROOT,configuration,output,seed=args.seed,arm=args.arm,cohort_seed=args.cohort_seed)
            print(json.dumps({'schema':d['schema'],'registration_sha256':d['sha256'],'source_sha256':d['source']['sha256']},sort_keys=True));return 0
        capital.freeze(ROOT,configuration,output,comparison=args.command=='comparison')
        action='comparison' if args.command=='comparison' else 'register'
        return subprocess.call([sys.executable,'-m','connected_enterprise','_capital','--action',action,'--output',str(output)],cwd=output/'source')
    if args.command=='_capital':
        if args.action=='register':
            registered=capital.register(output);result={'schema':registered['schema'],'registration_sha256':registered['sha256'],'opportunities':len(registered['opportunities'])}
        elif args.action=='operate':
            from .engine import run_native_capital
            operated=run_native_capital(output,max_events=args.max_events)
            result={'complete':operated['complete'],'summary':operated['summary'],'processed_events':operated['state']['processed_events'],'source_sha256':operated['source_sha256']}
        elif args.action=='comparison':result=capital.comparison(output)
        else:
            checked=capital.audit_output(output)
            write(output/'CAPITAL_AUDIT.json',checked)
            result=({'accepted':checked['accepted'],'arms':{k:v['scoreboard'] for k,v in checked['arms'].items()}} if 'arms' in checked
                    else checked['scoreboard'] if args.action=='scoreboard' else {'accepted':checked['accepted'],'scoreboard':checked['scoreboard']})
        print(json.dumps(result,sort_keys=True));return 0
    if args.command in {'operate','resume','audit','scoreboard'} and operations.is_connected(output):
        d,_=operations.read_operator(output);action='operate' if args.command=='resume' else args.command
        command=[sys.executable,'-m','connected_enterprise','_connected','--action',action,'--output',str(output)]
        if args.command=='operate' and args.max_events is not None:command.extend(['--max-events',str(args.max_events)])
        return subprocess.call(command,cwd=output/d['source_dir'])
    if args.command in {'operate','scoreboard','resume','audit'} and capital.is_capital(output):
        capital.read_freeze(output)
        action='operate' if args.command=='resume' else args.command
        command=[sys.executable,'-m','connected_enterprise','_capital','--action',action,'--output',str(output)]
        if args.command=='operate' and args.max_events is not None:command.extend(['--max-events',str(args.max_events)])
        return subprocess.call(command,cwd=output/'source')
    if args.command=='register':
        config_path=Path(args.config).expanduser()
        if any(p.is_symlink() for p in [config_path,*config_path.parents]):raise ValueError('REGISTRATION_SYMLINK_REFUSED')
        freeze(output,registration=strict_json(config_path.read_bytes()))
        frozen=read_freeze(output)
        print(json.dumps({'registered':True,'source_sha256':frozen['source']['sha256'],'frozen_sha256':frozen['sha256'],'tasks':tasks(frozen['protocol']),'accounts_created':False},sort_keys=True));return 0
    if args.command=='scoreboard':
        frozen=read_freeze(output)
        if 'connected_enterprise/scoreboard.py' not in frozen['source']['files']:raise ValueError('FROZEN_SCOREBOARD_IMPLEMENTATION_UNAVAILABLE')
        code='from connected_enterprise.scoreboard import scoreboard; import sys,json; print(json.dumps(scoreboard(sys.argv[1]),sort_keys=True))'
        return subprocess.call([sys.executable,'-c',code,str(output)],cwd=output/'source')
    if args.command=='comparison':
        read_freeze(output)
        code='from connected_enterprise.runner import comparison; import sys,json; print(json.dumps(comparison(sys.argv[1],sys.argv[2] or None,sys.argv[3] or None),sort_keys=True))'
        return subprocess.call([sys.executable,'-c',code,str(output),args.control or '',args.candidate or ''],cwd=output/'source')
    if args.command=='run':freeze(output,args.smoke)
    if args.command in {'run','resume','operate','audit'}:
        frozen=read_freeze(output);command='_worker' if args.command!='audit' else '_audit'
        if command=='_audit':
            code='from connected_enterprise.runner import audit_output; import sys,json; print(json.dumps(audit_output(sys.argv[1]),sort_keys=True))'
            return subprocess.call([sys.executable,'-c',code,str(output)],cwd=output/'source')
        operation=[sys.executable,'-m','connected_enterprise','_worker','--output',str(output)]
        if args.command=='operate' and args.max_events is not None:
            if args.max_events<1:raise ValueError('POSITIVE_EVENT_STEP_REQUIRED')
            operation.extend(['--max-events',str(args.max_events)])
        return subprocess.call(operation,cwd=output/'source')
    if args.command=='_worker':print(json.dumps(worker(output,args.max_events),sort_keys=True));return 0
    if args.command=='package':print(json.dumps(package(output,args.archive),sort_keys=True));return 0
    return 1

if __name__=='__main__':raise SystemExit(main())
