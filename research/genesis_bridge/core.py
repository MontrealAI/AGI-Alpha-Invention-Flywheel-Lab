"""Trusted local adapters, not a sandbox for hostile code or filesystem custody."""
from __future__ import annotations
import copy, hashlib, importlib.util, json, math, os, pathlib, subprocess, sys, time
from datetime import datetime, timezone
ROOT = pathlib.Path(__file__).resolve().parents[2]
LOCK = 'campaign/genesis-execution-bridge/SOURCE_LOCK.json'
OPS = {'compile': 'editable_design', 'analyze': 'accepted_analysis', 'replay': 'accepted_replay',
       'ordinary': 'accepted_analysis', 'direct': 'accepted_analysis'}
CONTRACT = {'scope':'synthetic_resistive_rod_only','sample_threshold_ohm':0.5,
            'contact_threshold_ohm':0.25,'truth_role':'independent_frozen_fixture',
            'physical_calibration_verified':False}

def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(x): return hashlib.sha256(canonical(x)).hexdigest()
def read(path):
    def unique(pairs):
        d={}
        for k,v in pairs:
            if k in d: raise ValueError('duplicate JSON key')
            d[k]=v
        return d
    return json.loads(pathlib.Path(path).read_bytes(),object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
def save(path,x):
    with pathlib.Path(path).open('xb') as f: f.write(canonical(x)+b'\n')
def verify_sources(root=ROOT):
    lock=read(root/LOCK)
    for p,expected in lock['sha256'].items():
        if pathlib.PurePosixPath(p).is_absolute() or '..' in pathlib.PurePosixPath(p).parts:
            raise ValueError('unsafe source path')
        if hashlib.sha256((root/p).read_bytes()).hexdigest()!=expected:
            raise ValueError('source changed: '+p)
    return digest(lock)
def load_planner():
    p=ROOT/'campaign/frontier-genesis-001/genesis.py'
    spec=importlib.util.spec_from_file_location('pinned_genesis_planner',p)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def request(operation,task_id,context,inputs,wall_seconds=10,cpu_seconds=5):
    if operation not in OPS: raise ValueError('operation not allowlisted')
    return {'schema':'genesis-bridge-request/v1','operation':operation,'task_id':task_id,
            'context':context,'input':inputs,'acceptance_contract':CONTRACT,
            'source_lock_sha256':verify_sources(),'design_proof':None,
            'limits':{'wall_seconds':wall_seconds,'cpu_seconds':cpu_seconds,'memory_bytes':268435456}}

def validate_request(req):
    if set(req)!={'schema','operation','task_id','context','input','acceptance_contract','source_lock_sha256','design_proof','limits'}:
        raise ValueError('request schema')
    if req['schema']!='genesis-bridge-request/v1' or req['operation'] not in OPS: raise ValueError('operation/schema')
    if not isinstance(req['task_id'],str) or not req['task_id'] or len(req['task_id'])>100: raise ValueError('task id')
    if not isinstance(req['context'],dict) or not req['context']: raise ValueError('context missing')
    if req['acceptance_contract']!=CONTRACT: raise ValueError('checker contract changed')
    if req['source_lock_sha256']!=verify_sources(): raise ValueError('source lock mismatch')
    lim=req['limits']
    if set(lim)!={'wall_seconds','cpu_seconds','memory_bytes'}: raise ValueError('limits schema')
    for k,v in lim.items():
        if type(v) not in (int,float) or not math.isfinite(v) or v<=0: raise ValueError('invalid bound')
    if type(lim['cpu_seconds']) is not int or type(lim['memory_bytes']) is not int: raise ValueError('integer OS limits')
    if lim['wall_seconds']>60 or lim['cpu_seconds']>60 or not 16777216<=lim['memory_bytes']<=536870912:
        raise ValueError('adapter finite safety envelope')
    if len(canonical(req))>1000000: raise ValueError('request too large')
    if req['operation']=='compile':
        if not isinstance(req['input'],dict): raise ValueError('design input')
    else:
        observations=[req['input']['previous'],req['input']['current']] if req['operation']=='replay' else [req['input']]
        for obs in observations:
            if not isinstance(obs,dict): raise ValueError('observations')
            for phase in ('baseline','after'):
                if len(obs.get(phase,{}).get('records',[]))>32: raise ValueError('bounded adapter records')

def binding(req):
    return {'request_sha256':digest(req),'task_id':req['task_id'],'context_sha256':digest(req['context']),
            'input_sha256':digest(req['input']),'contract_sha256':digest(req['acceptance_contract']),
            'source_lock_sha256':req['source_lock_sha256']}

def run(req,out):
    validate_request(req)
    out=pathlib.Path(out).absolute()
    if any(p.is_symlink() for p in [out,*out.parents]):raise ValueError('symlink output ancestry unsupported')
    out.mkdir(parents=True,exist_ok=False)
    save(out/'request.json',req)
    start=datetime.now(timezone.utc).isoformat();t=time.monotonic()
    command=[sys.executable,'-I','-B',str(ROOT/'research/genesis_bridge/worker.py'),str(out/'request.json')]
    result=None;error=None;code=None;stdout='';stderr=''
    try:
        p=subprocess.run(command,capture_output=True,timeout=req['limits']['wall_seconds'],check=False,
                         env={'PATH':os.defpath,'PYTHONDONTWRITEBYTECODE':'1'})
        code=p.returncode;stdout=p.stdout.decode('utf-8',errors='replace')[-4096:];stderr=p.stderr.decode('utf-8',errors='replace')[-4096:]
        if code==0:
            result=json.loads(p.stdout);canonical(result)
        else:error='adapter exited '+str(code)
    except subprocess.TimeoutExpired as e:
        error='wall limit exceeded';stdout=(e.stdout or b'').decode('utf-8',errors='replace')[-4096:];stderr=(e.stderr or b'').decode('utf-8',errors='replace')[-4096:]
    except (ValueError,KeyError):error='invalid worker receipt'
    receipt={'binding':binding(req),'started_utc':start,'ended_utc':datetime.now(timezone.utc).isoformat(),
             'wall_seconds':time.monotonic()-t,'exit_code':code,'worker':result,'error':error,
             'diagnostics':{'stdout_tail':stdout,'stderr_tail':stderr,'maximum_chars_each':4096},
             'monetary_cost':None,'cost_coverage':'child CPU/RSS; wrapper wall. Excludes development, model billing, host dollars.',
             'status':'EXECUTED' if result is not None else 'FAIL'}
    save(out/'execution.json',receipt)
    return receipt

def validate_fixture(req,fixture):
    if req['operation']=='compile':
        if set(fixture)!={'request_sha256'} or req['input']!={'maximum_current_A':.001,'maximum_specimen_power_W':.001,'maximum_bulk_ohm':40,'current_menu_A':[.0005,.001]}:
            raise ValueError('unregistered design fixture')
        return
    cases=read(ROOT/'campaign/genesis-execution-bridge/FIXTURES.json')
    matches=[c for c in cases if c['id']==req['task_id']]
    if len(matches)!=1 or set(fixture)!={'request_sha256','truth','registration'}:
        raise ValueError('unregistered fixture task/schema')
    c=matches[0]
    from .demo import CONTEXT
    if req['context']!=CONTEXT:raise ValueError('unregistered fixture context')
    if fixture['truth']!=c['truth'] or fixture['registration']!='campaign/genesis-execution-bridge/FIXTURES.json':
        raise ValueError('frozen fixture truth/registration mismatch')
    observations=[req['input']['previous'],req['input']['current']] if req['operation']=='replay' else [req['input']]
    for obs in observations:
        # Only removal of sense observations is a registered task variant.
        restored=copy.deepcopy(obs)
        try:
            for phase in ('baseline','after'):
                if len(restored[phase]['records'])!=len(c['observation'][phase]['records']):raise ValueError('fixture records')
                for row,original in zip(restored[phase]['records'],c['observation'][phase]['records']):
                    if row.get('v4') is None:row['v4']=original['v4']
            if restored!=c['observation']:raise ValueError('unregistered fixture observations')
        except (KeyError,TypeError):raise ValueError('unregistered fixture observations')

def _accept_local(req,receipt,fixture):
    """Independent receipt+fixture binding. The executor never receives fixture truth."""
    validate_request(req)
    validate_fixture(req,fixture)
    proof=req['design_proof']
    if proof is not None:
        if req['operation']!='analyze' or proof['request']['operation']!='compile' or proof['request']['design_proof'] is not None:raise ValueError('design predecessor type')
        verdict=_accept_local(proof['request'],proof['execution'],proof['fixture'])
        if verdict['status']!='PASS':raise ValueError('design predecessor not accepted')
        design=proof['execution']['worker']['output']
        for phase in ('baseline','after'):
            if [r['current'] for r in req['input'][phase]['records']]!=design['currents_A']:raise ValueError('acquisition not bound to compiled design')
    if fixture['request_sha256']!=digest(req): raise ValueError('fixture bound to another request')
    if receipt['binding']!=binding(req): raise ValueError('receipt binding mismatch')
    if receipt['status'] not in ('FAIL','EXECUTED'):raise ValueError('unknown execution status')
    if receipt['status']=='FAIL':return {'status':'FAIL','reason':receipt['error'],'retention_allowed':False}
    if receipt['exit_code']!=0 or receipt['error'] is not None or receipt['wall_seconds']<0 or not math.isfinite(receipt['wall_seconds']):raise ValueError('execution status/elapsed mismatch')
    w=receipt['worker']
    if w['python_executable_sha256']!=hashlib.sha256(pathlib.Path(sys.executable).read_bytes()).hexdigest() or w['python_version']!=sys.version:raise ValueError('runtime mismatch')
    if w['binding']!=binding(req) or w['output_sha256']!=digest(w['output']): raise ValueError('worker/output binding')
    if w['source_lock_sha256']!=verify_sources():raise ValueError('worker source')
    cpu,rss=w['cpu_seconds'],w['max_rss_kib']
    if type(cpu) not in (int,float) or not math.isfinite(cpu) or not 0<=cpu<=req['limits']['cpu_seconds']:
        raise ValueError('CPU resource receipt')
    if type(rss) is not int or not 0<rss*1024<=req['limits']['memory_bytes']:
        raise ValueError('RSS qualification bound')
    if receipt['wall_seconds']>req['limits']['wall_seconds']+1.0:
        raise ValueError('wall receipt exceeds timeout plus one-second scheduling tolerance')
    output=w['output'];op=req['operation']
    if op=='compile':
        # Separate arithmetic acceptance, not a second call to compile_design.
        s=req['input'];currents=output.get('currents_A');eligible=[i for i in s['current_menu_A']
            if type(i) in (int,float) and math.isfinite(i) and 0<i<=s['maximum_current_A'] and i*i*s['maximum_bulk_ohm']<=s['maximum_specimen_power_W']]
        i=max(eligible)
        if currents!=[i,-i,.5*i,-.5*i,.25*i,-.25*i] or output['specification']!=s or output['physical_execution_authorized'] is not False:
            raise ValueError('design acceptance')
        status='PASS'
    else:
        if op=='replay':
            if output.get('reopened') is not True:return {'status':'ABSTAIN','reason':output['reason'],'retention_allowed':False}
            # Check same-context proof independently, not via producer replay helper.
            old,new=req['input']['previous'],req['input']['current'];restored=copy.deepcopy(new)
            added=False
            for phase in ('baseline','after'):
                if len(old[phase]['records'])!=len(new[phase]['records']):raise ValueError('replay lengths')
                for a,b,c in zip(old[phase]['records'],new[phase]['records'],restored[phase]['records']):
                    if a.get('v4') is None:
                        if b.get('v4') is None:raise ValueError('missing replay observation')
                        added=True
                        if 'v4' in a:c['v4']=None
                        else:c.pop('v4',None)
            if not added or restored!=old:raise ValueError('changed replay context')
            output=output['prediction']
        from research.genesis097.check import check_prediction
        verdict=check_prediction({'truth':fixture['truth']},output)
        status='ABSTAIN' if verdict['abstained'] else 'PASS'
    return {'status':status,'retention_allowed':status=='PASS','fixture_sha256':digest(fixture),
            'request_sha256':digest(req),'execution_sha256':digest(receipt),
            'scope':'frozen synthetic fixture; no physical or commercial certification'}

def accept(req,receipt,fixture):
    # Fresh process defeats stale/monkeypatched imported producer/checker modules.
    validate_request(req)
    t=time.monotonic()
    try:
        p=subprocess.run([sys.executable,'-I','-B',str(ROOT/'research/genesis_bridge/check_worker.py')],
            input=canonical({'request':req,'execution':receipt,'fixture':fixture}),capture_output=True,
            timeout=10,env={'PATH':os.defpath,'PYTHONDONTWRITEBYTECODE':'1'})
    except subprocess.TimeoutExpired:raise ValueError('checker wall limit exceeded')
    if p.returncode!=0:raise ValueError('checker process failed: '+str(p.returncode))
    v=json.loads(p.stdout)
    if 'error' in v:
        if v['error_type']=='AssertionError':raise AssertionError(v['error'])
        raise ValueError(v['error'])
    a=v['acceptance'];a['checker_resources']={'wall_seconds':time.monotonic()-t,'cpu_seconds':v['cpu_seconds'],
        'max_rss_kib':v['max_rss_kib'],'coverage':'fresh checker process call CPU; Linux lifetime RSS; wrapper wall'}
    return a

def execute_from_design(req,out,fixture,design_request,design_receipt,design_fixture):
    proof={'request':design_request,'execution':design_receipt,'fixture':design_fixture}
    if accept(design_request,design_receipt,design_fixture)['status']!='PASS':raise ValueError('design not accepted')
    req=copy.deepcopy(req);req['design_proof']=proof;fixture={**fixture,'request_sha256':digest(req)}
    return execute(req,out,fixture)

def execute(req,out,fixture):
    r=run(req,out)
    try:a=accept(req,r,fixture)
    except (ValueError,AssertionError,KeyError,TypeError) as e:
        a={'status':'FAIL','reason':str(e),'retention_allowed':False}
    save(pathlib.Path(out)/'acceptance.json',a)
    return r,a

def validate_canary(req,fixture):
    from .demo import CONTEXT
    canary=read(ROOT/'campaign/genesis-execution-bridge/FIXTURES.json')[0]
    if req['operation']!='analyze' or req['task_id']!=canary['id'] or req['input']!=canary['observation'] or req['context']!=CONTEXT or fixture['truth']!=canary['truth']:
        raise ValueError('fixed source-bound canary required')

def probe(req,fixture,out):
    validate_canary(req,fixture)
    r,a=execute(req,out,fixture)
    return {'kind':'local_probe','capability':'local_kelvin_kernel','request':req,'execution':r,'fixture':fixture,'acceptance':a}

def plan(observation,probes):
    verify_sources()
    # Observe bytes as evidence only. No observation field can provide code or access.
    if not isinstance(observation.get('source_url'),str) or not observation['source_url'].startswith('https://'):
        raise ValueError('observation provenance')
    if not isinstance(observation.get('response_sha256'),str) or len(observation['response_sha256'])!=64:
        raise ValueError('response hash required')
    initial=[]
    for p in probes:
        validate_canary(p['request'],p['fixture'])
        a=accept(p['request'],p['execution'],p['fixture'])
        if p.get('capability')!='local_kelvin_kernel' or p['request']['operation']!='analyze':raise ValueError('probe type')
        if a['status']=='PASS':initial.append('local_kelvin_kernel')
    scenario={'evidence_scope':'AUTHORED_SYNTHETIC','initial':sorted(set(initial)),'events':[],
       'operations':[{'id':'compile','requires':['local_kelvin_kernel'],'provides':['editable_design'],'kind':'construct','cost_cents':0},
                     {'id':'analyze','requires':['editable_design'],'provides':['accepted_analysis'],'kind':'existing','cost_cents':0}],
       'offers':[]}
    planner=load_planner();planner.validate(scenario)
    proposal=planner.find_plan(scenario,frozenset(['accepted_analysis']))
    return {'observation':copy.deepcopy(observation),'observation_sha256':digest(observation),'scenario':scenario,
            'scenario_sha256':digest(scenario),'proposal':proposal,'execution_authority':False,
            'costs':'zero search weights only, NOT monetary estimates','available_capabilities':scenario['initial']}

def retain(req,r,fixture):
    a=accept(req,r,fixture)
    if a['status']!='PASS' or req['operation'] not in ('analyze','replay'):raise ValueError('only accepted analytical method can be retained')
    return {'kind':'reusable_method','adapter':'analyze','source_lock_sha256':verify_sources(),
            'origin_request_sha256':digest(req),'origin_execution_sha256':digest(r),'origin_fixture_sha256':digest(fixture),
            'applicability':req['context'],'acceptance_contract':CONTRACT,
            'maintenance':'reprobe after any source/contract/context change','cached_answer':False}

def reuse(method,origin_req,origin_receipt,origin_fixture,new_req,out,new_fixture):
    if method!=retain(origin_req,origin_receipt,origin_fixture):raise ValueError('retained method provenance')
    if new_req['operation']!='analyze' or new_req['context']!=method['applicability']:raise ValueError('method applicability')
    original_input=origin_req['input']['current'] if origin_req['operation']=='replay' else origin_req['input']
    if digest(new_req['input'])==digest(original_input) or new_req['task_id']==origin_req['task_id']:raise ValueError('fresh instance required')
    return execute(new_req,out,new_fixture)
