"""Explicit pending research contracts on the existing native account.

Registration admits a request only. No useful artifact or successful outcome is
asserted before prepaid execution and independent physics verification.
"""
import copy
import hashlib
import threading
import time
import resource
from pathlib import Path
from commercial.ledger import canonical,digest,amount

SCHEMA='agi-alpha/pending-battery-research/v1'
KIND='PENDING_RESEARCH_CONTRACT'
STAGES=('discovery','construction','criticism','repair','production','verification','report','support')
DEPENDENCIES=('battery_service/__init__.py','battery_service/physics.py','battery_service/construct.py','requirements-battery040.txt','connected_enterprise/research_service.py')
CACHE={}
LOCK=threading.RLock()


def sources(root):
    root=Path(root).resolve();executing=Path(__file__).resolve().parents[1]
    from battery_service import physics,construct
    for module,name in ((physics,'battery_service/physics.py'),(construct,'battery_service/construct.py')):
        if Path(module.__file__).resolve()!=(executing/name).resolve() or (root/name).read_bytes()!=Path(module.__file__).read_bytes():raise ValueError('RESEARCH_IMPORTED_SOURCE_MISMATCH')
    files={}
    for name in DEPENDENCIES:
        p=root/name
        if not p.is_file() or any(x.is_symlink() for x in (p,*p.parents)) or p.read_bytes()!=(executing/name).read_bytes():raise ValueError('RESEARCH_EXECUTING_SOURCE_MISMATCH')
        files[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    return files


def dependencies():
    from battery_service.physics import dependency_identity
    return dependency_identity()


def validate_contract(job):
    from battery_service.physics import validate_request,POLICY_KINDS
    fields={'id','kind','request','allowed_policy_kinds','cost_envelope_microUSD','max_attempts','scope','construction'}
    if not isinstance(job,dict) or set(job)!=fields or job['kind']!=KIND or not isinstance(job['id'],str) or not job['id'] or len(job['id'])>100:raise ValueError('EXACT_PENDING_RESEARCH_CONTRACT_REQUIRED')
    validate_request(job['request'])
    if job['scope']!='SIMULATED_PROTOCOL_EVALUATION_REPORT_NOT_PHYSICAL_SAFETY':raise ValueError('EXPLICIT_RESEARCH_SERVICE_SCOPE_REQUIRED')
    kinds=job['allowed_policy_kinds']
    if not isinstance(kinds,list) or not kinds or len(kinds)!=len(set(kinds)) or any(x not in POLICY_KINDS for x in kinds):raise ValueError('EXPLICIT_POLICY_SCOPE_REQUIRED')
    costs=job['cost_envelope_microUSD']
    if not isinstance(costs,dict) or set(costs)!=set(STAGES):raise ValueError('COMPLETE_RESEARCH_COST_ENVELOPE_REQUIRED')
    for v in costs.values():amount(v)
    amount(sum(costs.values()),positive=True)
    if costs['production']<=0 or costs['verification']<=0:raise ValueError('PAID_PRODUCTION_AND_VERIFICATION_REQUIRED')
    if type(job['max_attempts']) is not int or job['max_attempts']<1:raise ValueError('FINITE_POSITIVE_ATTEMPT_COUNT_REQUIRED')
    construction=job['construction']
    if not isinstance(construction,dict) or construction.get('mode') not in {'provided_policy_evaluation','known_envelope'}:raise ValueError('EXPLICIT_CONSTRUCTION_MODE_REQUIRED')
    if construction['mode']=='provided_policy_evaluation':
        if set(construction)!={'mode'}:raise ValueError('EXACT_EVALUATION_ONLY_MODE_REQUIRED')
    else:
        if set(construction)!={'mode','training_requests','oracle_current_A','safety_factor'}:raise ValueError('EXACT_PAID_CONSTRUCTION_CONTRACT_REQUIRED')
        requests=construction['training_requests']
        if not isinstance(requests,list) or not 2<=len(requests)<=8 or costs['construction']<=0:raise ValueError('PAID_FINITE_TRAINING_REQUIRED')
        for request in requests:validate_request(request)
        for key in ('oracle_current_A','safety_factor'):
            if type(construction[key]) not in (int,float) or not 0<construction[key]<= (20 if key=='oracle_current_A' else 1):raise ValueError('FINITE_CONSTRUCTION_PARAMETER_REQUIRED')
    return copy.deepcopy(job)


def manifest(root,jobs,*,native_engine='exact-permanent-v2'):
    result={'schema':SCHEMA,'account_namespace':'adaptive012','native_engine':native_engine,'source_hashes':sources(root),'dependency_versions':dependencies(),'jobs':copy.deepcopy(jobs)}
    load_jobs(root,result)
    return result


def load_jobs(root,m):
    if not isinstance(m,dict) or set(m)!={'schema','account_namespace','native_engine','source_hashes','dependency_versions','jobs'} or m['schema']!=SCHEMA or m['account_namespace']!='adaptive012':raise ValueError('EXACT_PENDING_RESEARCH_MANIFEST_REQUIRED')
    if m['native_engine'] not in {'exact-permanent-v2','exact-prospective-v2'} or m['source_hashes']!=sources(root) or m['dependency_versions']!=dependencies():raise ValueError('RESEARCH_SOURCE_OR_DEPENDENCIES_CHANGED')
    if not isinstance(m['jobs'],list) or not m['jobs']:raise ValueError('PREREGISTERED_RESEARCH_REQUESTS_REQUIRED')
    jobs={};work=set()
    for raw in m['jobs']:
        job=validate_contract(raw);key=digest(job['request'])
        if job['id'] in jobs or key in work:raise ValueError('UNIQUE_RESEARCH_WORK_NOT_RENAMED_RESULT_REQUIRED')
        work.add(key);jobs[job['id']]={'job':job,'contract_sha256':digest(job)}
    return jobs


def task(job):
    return {'scope':'PENDING_BATTERY_RESEARCH','job_id':job['id'],'request_sha256':digest(job['request']),'contract_sha256':digest(job)}


def work(job,attempt,source_sha256):
    if type(attempt) is not int or not 0<=attempt<job['max_attempts']:raise ValueError('PREREGISTERED_ATTEMPT_REQUIRED')
    return {'schema':SCHEMA,'job_id':job['id'],'contract_sha256':digest(job),'attempt':attempt,'source_sha256':source_sha256}


def verify_payment(root,job,entry,actions):
    from .finance import source_identity,_seed_id
    source=source_identity(root);request=entry.get('request',{});receipt=entry.get('receipt',{})
    if entry.get('status')!='COMPLETE' or request.get('operation')!='spend' or receipt.get('source_sha256')!=source['sha256']:raise ValueError('COMPLETE_RESEARCH_PREPAYMENT_REQUIRED')
    w=request.get('work',{});expected=work(job,w.get('attempt'),source['sha256']);ident='battery:'+job['id']+':'+str(w['attempt'])
    total=sum(job['cost_envelope_microUSD'].values())
    if w!=expected or request.get('id')!=ident or request.get('kind')!='battery-research' or request.get('amount')!=total or receipt.get('work_sha256')!=digest(w) or receipt.get('amount')!=total:raise ValueError('RESEARCH_PAYMENT_CONTRACT_CHANGED')
    seq=receipt.get('native_event_sequence')
    if type(seq)is not int or not 0<=seq<len(actions) or receipt.get('native_actions_sha256')!=digest(actions[:seq+1]):raise ValueError('RESEARCH_PAYMENT_MUST_PRECEDE_DELIVERY')
    event=actions[seq]
    if entry.get('funding')=='SEED' and request.get('allow_seed') is True:
        args={'id':_seed_id(request,source['sha256']),'amount':total}
        if event['op']!='cost' or event['args']!=args:raise ValueError('RESEARCH_SEED_PREPAYMENT_CHANGED')
    elif entry.get('funding')=='EARNED':
        plan=entry.get('plan',{});obligation=entry.get('obligation_receipt')
        if not plan or not obligation or plan['selected_options'][0]['execution'].get('work_sha256')!=digest(w):raise ValueError('RESEARCH_EARNED_CONTRACT_CHANGED')
        args={'id':plan['plan_id'],'amount':total,'artifact_sha256':digest({'work_artifact_sha256':digest(w),'obligation_receipt_sha256':digest(obligation)})}
        if event['op']!='finish' or event['args']!=args:raise ValueError('RESEARCH_EARNED_PREPAYMENT_CHANGED')
    else:raise ValueError('RESEARCH_NATIVE_FUNDING_REQUIRED')
    return digest(entry)


def assert_unused(job,payload,actions):
    for event in actions:
        previous=event['args'].get('research_payload') if event['op']=='event' else None
        if previous and (previous['payment']['receipt']['native_event_sequence']==payload['payment']['receipt']['native_event_sequence'] or previous['payment']['request']['work']['job_id']==job['id']):
            raise ValueError('RESEARCH_PAYMENT_OR_JOB_ALREADY_DELIVERED')


def check(root,m,job,payload,actions):
    from battery_service.physics import independent_check,useful_digest,validate_policy
    registered=load_jobs(root,m)
    if job.get('id') not in registered or registered[job['id']]['job']!=job:raise ValueError('RESEARCH_JOB_NOT_REGISTERED')
    if not isinstance(payload,dict) or set(payload)!={'result','payment','construction'}:raise ValueError('ACTUAL_RESEARCH_RESULT_AND_PREPAYMENT_REQUIRED')
    payment=verify_payment(root,job,payload['payment'],actions)
    result=payload['result'];validate_policy(result['policy'])
    if result['policy']['kind'] not in job['allowed_policy_kinds']:raise ValueError('RESEARCH_POLICY_OUTSIDE_CONTRACT')
    key=digest({'contract':job,'construction':payload['construction'],'request':job['request'],'artifact':result,'source':m['source_hashes'],'dependencies':m['dependency_versions']})
    if key not in CACHE:
        if job['construction']['mode']=='known_envelope':
            from battery_service.construct import construct
            c=job['construction'];built=construct(c['training_requests'],oracle_current_A=c['oracle_current_A'],safety_factor=c['safety_factor'])
            if deterministic(built)!=deterministic(payload['construction']) or result['policy']!=built['policy']:raise ValueError('PAID_CONSTRUCTION_NOT_REPRODUCED')
        elif payload['construction'] is not None:raise ValueError('EVALUATION_CANNOT_CLAIM_CONSTRUCTION')
        checked=independent_check(job['request'],result)
        if job['construction']['mode']=='known_envelope':checked['construction_verification_resources']=built['resources']
        if not checked['accepted']:raise ValueError('RESEARCH_PHYSICS_ACCEPTANCE_FAILED')
        CACHE[key]=checked
    checked=copy.deepcopy(CACHE[key])
    if checked['useful_digest']!=useful_digest(result):raise ValueError('RESEARCH_USEFUL_OUTPUT_CHANGED')
    return {'accepted':True,'decisive':True,'scope':'SIMULATED_BATTERY_RESEARCH','authority':digest({'contract':digest(job),'useful':checked['useful_digest'],'payment':payment}), 'verification':checked}


def deterministic(value):
    if isinstance(value,dict):return {k:deterministic(v) for k,v in value.items() if k!='resources'}
    if isinstance(value,list):return [deterministic(v) for v in value]
    return value


def run_paid(root,account,job_id,policy=None,*,attempt=0,day=0,allow_seed=False,expected_net=0):
    from commercial.persistence import atomic_bytes
    from .finance import JournalAccount
    if type(account)is not JournalAccount:raise ValueError('CANONICAL_JOURNAL_ACCOUNT_REQUIRED')
    if not isinstance(job_id,str) or not job_id or len(job_id)>100 or type(attempt)is not int or attempt<0:raise ValueError('EXPLICIT_RESEARCH_ATTEMPT_ID_REQUIRED')
    with LOCK:
        wall=time.monotonic();cpu=time.process_time();children=resource.getrusage(resource.RUSAGE_CHILDREN)
        before=children.ru_utime+children.ru_stime
        result=None;failure=None
        try:
            result=_run_paid(root,account,job_id,policy,attempt=attempt,day=day,allow_seed=allow_seed,expected_net=expected_net)
            return result
        except BaseException as exc:
            failure=exc
            raise
        finally:
            children=resource.getrusage(resource.RUSAGE_CHILDREN)
            receipt={'schema':'battery-research-invocation-resources/v1','job_id':job_id,'attempt':attempt,
                'status':'FAILED' if failure is not None else 'COMPLETED',
                'process_cpu_seconds':time.process_time()-cpu,
                'waited_child_cpu_seconds':children.ru_utime+children.ru_stime-before,
                'wall_seconds':time.monotonic()-wall,
                'scope':'Actual whole invocation through receipt construction, including source/payment/audit overhead. Excludes this receipt write and unawaited children. Cached component timings are historical verification provenance, not additional current work.',
                'billing':'Authored native envelope is not measured host/model/engineering billing.'}
            if result is not None:result['invocation_resources']=receipt
            if failure is not None:setattr(failure,'research_resources',receipt)
            # Separate non-authoritative operational receipt, never money/state.
            if hasattr(account,'path'):
                path=Path(account.path).with_name(Path(account.path).name+'.research-resources-'+digest([job_id,attempt,receipt])+'.json')
                try:
                    atomic_bytes(path,canonical(receipt)+b'\n')
                except Exception as write_error:
                    receipt['non_authoritative_receipt_write_error']=type(write_error).__name__
                    # Return/raise original execution outcome; native money is unchanged.


def _run_paid(root,account,job_id,policy=None,*,attempt=0,day=0,allow_seed=False,expected_net=0):
    """One paid evaluation; no automatic retries or uncharged search/comparators."""
    from .finance import JournalAccount,source_identity
    from battery_service.physics import evaluate
    if type(account)is not JournalAccount:raise ValueError('CANONICAL_JOURNAL_ACCOUNT_REQUIRED')
    job=load_jobs(root,account.manifest)[job_id]['job'];source=source_identity(root)
    w=work(job,attempt,source['sha256']);ident='battery:'+job_id+':'+str(attempt)
    entries=account.export()['connected_journal']['entries']
    if any(e['request'].get('id')==ident for e in entries):raise ValueError('RESEARCH_ATTEMPT_ALREADY_PAID_OR_FAILED')
    receipt=account.spend(ident,'battery-research',sum(job['cost_envelope_microUSD'].values()),day,w,expected_net,allow_seed=allow_seed)
    if receipt is None:raise ValueError('RESEARCH_NATIVE_FUNDS_INSUFFICIENT')
    entry=next(e for e in account.export()['connected_journal']['entries'] if e['request'].get('id')==ident)
    verify_payment(root,job,entry,account.export()['ledger']['actions'])
    # Failure leaves the paid native cost intact; the attempt cannot be reused.
    construction=None
    if job['construction']['mode']=='known_envelope':
        if policy is not None:raise ValueError('CONSTRUCTOR_POLICY_CANNOT_BE_PRECOMPUTED')
        from battery_service.construct import construct
        c=job['construction'];construction=construct(c['training_requests'],oracle_current_A=c['oracle_current_A'],safety_factor=c['safety_factor'])
        policy=construction['policy']
    result=evaluate(job['request'],policy)
    payload={'result':result,'payment':entry,'construction':construction}
    checked=check(root,account.manifest,job,payload,account.export()['ledger']['actions'])
    return {'payload':payload,'acceptance':checked,'cost_basis':'Declared simulated complete-attempt envelope; actual CPU/wall measured, host/model/engineering billing unknown.'}
