from __future__ import annotations
import copy
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from . import client, source

DAYS = ('GD01', 'GD02', 'GD03')
ROUNDS = (1, 2, 3, 4, 5, 6)
WORKER_FILES = ('__init__.py', 'ordinary.py', 'retained.py', 'wave.py', 'RETAINED.json')


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def _exclusive(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(data); handle.flush(); os.fsync(handle.fileno())


def _load_public(source_root):
    result = {}
    for day in DAYS:
        customer_path = source.source_path(source_root, source.GROCERY_PUBLIC + '/' + day + '_customers.csv')
        with customer_path.open(newline='') as handle:
            rows = list(csv.DictReader(handle))
        customers = {int(row['customer_id']): {key: float(value) if key in ('x', 'y') else int(value) for key, value in row.items()} for row in rows}
        matrix_path = source.source_path(source_root, source.GROCERY_PUBLIC + '/' + day + '_duration_matrix.csv')
        with matrix_path.open(newline='') as handle:
            duration = [[int(value) for value in row] for row in csv.reader(handle)]
        result[day] = {'customers': customers, 'duration': duration}
    return result


def _load_confirmations(source_root):
    path = source.source_path(source_root, source.GROCERY_PRIVATE)
    with path.open(newline='') as handle:
        raw = list(csv.DictReader(handle))
    rows = []
    for row in raw:
        result = {key: value if key in ('service_day_id', 'order_id') else int(float(value)) if key in ('window_start', 'window_end') else int(value) for key, value in row.items()}
        result['tw_start'] = result.pop('window_start'); result['tw_end'] = result.pop('window_end')
        rows.append(result)
    return rows


def visible_window(public, confirmations, epoch):
    if type(epoch) is not int or not 0 <= epoch < 18:
        raise ValueError('OPERATIONAL075_REGISTERED_PERIOD_REQUIRED')
    day, current = DAYS[epoch // 6], ROUNDS[epoch % 6]
    orders = [copy.deepcopy(row) for row in confirmations if row['service_day_id'] == day and row['dispatch_round'] <= current]
    ready = {row['ready_time'] for row in orders if row['dispatch_round'] == current}
    if len(ready) != 1:
        raise ValueError('OPERATIONAL075_SOURCE_ROUND_DEPARTURE_REQUIRED')
    return {'service_day_id': day, 'dispatch_round': current, 'ready_time': next(iter(ready)), 'orders': orders, 'customers': copy.deepcopy(public[day]['customers']), 'duration': copy.deepcopy(public[day]['duration']), 'capacity': 1000, 'total_rounds': 6, 'epoch': epoch, 'information_mode': 'rolling_batch_v1'}


_WORKER = '''
import contextlib,importlib,json,os,pathlib,sys,time
code_root=pathlib.Path(__file__).parent/'code'
allowed_roots=[code_root.resolve(),pathlib.Path(sys.base_prefix).resolve(),pathlib.Path(sys.exec_prefix).resolve(),pathlib.Path('/usr/lib'),pathlib.Path('/usr/local/lib'),pathlib.Path('/lib')]
def permitted_path(value):
 if isinstance(value,int):return value in (0,1,2)
 target=pathlib.Path(os.fspath(value)).absolute().resolve()
 return target==pathlib.Path('/dev/null') or any(target==p or p in target.parents for p in allowed_roots)
def audit(event,args):
 if event=='open':
  mode=args[1] or '';flags=args[2] or 0
  if not permitted_path(args[0]) or any(c in mode for c in 'wax+') or flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):raise PermissionError('POLICY_FILE_ACCESS_OUTSIDE_PUBLIC_CODE_AND_RUNTIME_REFUSED')
 elif event in ('os.listdir','os.scandir') and not permitted_path(args[0]):raise PermissionError('POLICY_DIRECTORY_ACCESS_REFUSED')
 elif event in ('subprocess.Popen','os.system','os.exec','os.posix_spawn','socket.connect','socket.connect_ex','socket.bind','socket.getaddrinfo'):raise PermissionError('POLICY_EXTERNAL_EFFECT_REFUSED')
sys.addaudithook(audit)
sys.path.insert(0,str(code_root))
module=importlib.import_module(sys.argv[1]);request=json.loads(sys.stdin.read());window=request['window'];window['customers']={int(k):v for k,v in window['customers'].items()}
start=time.process_time()
with contextlib.redirect_stdout(sys.stderr): result=module.decide(window,request['state'])
if not isinstance(result,(list,tuple)) or len(result)!=2:raise ValueError('decide must return submission and state')
submission,state=result
raw=json.dumps(submission,sort_keys=True,separators=(',',':'),allow_nan=False)
print(json.dumps({'submission_raw':raw,'state':state,'policy_cpu_seconds':time.process_time()-start},sort_keys=True,allow_nan=False))
'''


def _worker_identity():
    return {'mode': 'separate-process-python-audit-restricted-file-access', 'uid': os.geteuid(), 'gid': os.getegid(), 'os_user_separation': False, 'scope': 'Reviewed policies and audited Python file operations; not a sandbox against malicious native code.'}


def worker_bundle(package=None):
    package=Path(__file__).parent if package is None else Path(package)
    payload={}
    for name in WORKER_FILES:
        path=package/name
        if path.exists():
            if not path.is_file() or any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('OPERATIONAL075_REGULAR_WORKER_FILE_REQUIRED')
            payload[name]=path.read_bytes()
        elif name=='__init__.py':payload[name]=b''
    if 'ordinary.py' not in payload or 'wave.py' not in payload or 'RETAINED.json' not in payload:raise ValueError('OPERATIONAL075_REQUIRED_WORKER_BUNDLE_MISSING')
    return payload


def worker_payload_hashes(payload=None):
    payload=worker_bundle() if payload is None else payload
    return {name:hashlib.sha256(data).hexdigest() for name,data in sorted(payload.items())}


def run_policy(policy_module, window, state, *, expected_payload_hashes=None):
    if policy_module not in ('operational075.ordinary', 'operational075.retained'):
        raise ValueError('OPERATIONAL075_DECLARED_POLICY_REQUIRED')
    payload=worker_bundle();payload_hashes=worker_payload_hashes(payload)
    if expected_payload_hashes is not None and payload_hashes!=expected_payload_hashes:raise ValueError('OPERATIONAL075_WORKER_PAYLOAD_CHANGED')
    if policy_module.split('.')[-1]+'.py' not in payload:raise ValueError('OPERATIONAL075_POLICY_SOURCE_MISSING')
    with tempfile.TemporaryDirectory(prefix='operational075-public-worker-') as folder:
        folder = Path(folder); os.chmod(folder, 0o755)
        code = folder / 'code/operational075'; code.mkdir(parents=True)
        os.chmod(folder/'code',0o755); os.chmod(code,0o755)
        for name,data in sorted(payload.items()):
            target=code/name;target.write_bytes(data);os.chmod(target,0o644)
        worker=folder/'worker.py';worker.write_text(_WORKER);os.chmod(worker,0o644)
        identity=_worker_identity()
        before=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.perf_counter()
        process=subprocess.run([sys.executable,'-I','-B',str(worker),policy_module],input=encoded({'window':window,'state':state}),stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=folder,env={'PATH':'/usr/local/bin:/usr/bin:/bin','PYTHONHASHSEED':'0','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
        after=resource.getrusage(resource.RUSAGE_CHILDREN)
        measured={'wall_seconds':time.perf_counter()-start,'child_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'worker_identity':identity,'returncode':process.returncode,'stderr_sha256':hashlib.sha256(process.stderr).hexdigest(),'worker_payload_hashes':payload_hashes,'worker_guard_sha256':hashlib.sha256(_WORKER.encode()).hexdigest()}
        if process.returncode!=0:
            raise ValueError('OPERATIONAL075_POLICY_PROCESS_FAILED:'+process.stderr.decode('utf-8',errors='replace')[-1200:])
        if len(process.stdout)>16_000_000:
            raise ValueError('OPERATIONAL075_FINITE_EXPERIMENT_PAYLOAD_EXCEEDED')
        result=json.loads(process.stdout)
        raw=result['submission_raw'].encode('utf-8');json.loads(raw)
        return raw,result['state'],dict(measured,policy_cpu_seconds=result['policy_cpu_seconds'])


def lock_submission(output, epoch, raw, window, state, resources, previous):
    if not isinstance(raw, bytes): raise ValueError('OPERATIONAL075_ORIGINAL_SUBMISSION_BYTES_REQUIRED')
    json.loads(raw)
    folder=Path(output)/'periods'/f'{epoch:02d}'
    _exclusive(folder/'SUBMISSION.json',raw)
    _exclusive(folder/'STATE.json',encoded(state))
    receipt={'schema':'operational075/locked-submission/v1','epoch':epoch,'service_day_id':window['service_day_id'],'dispatch_round':window['dispatch_round'],'window_sha256':digest(window),'visible_order_count':len(window['orders']),'submission_sha256':hashlib.sha256(raw).hexdigest(),'submission_bytes':len(raw),'state_sha256':digest(state),'previous_receipt_sha256':previous,'resources':resources,'intermediate_validation_returned':False,'intermediate_score_returned':False}
    _exclusive(folder/'RECEIPT.json',encoded(receipt))
    return receipt


def check_locked_receipt(receipt, epoch, raw, window, state, previous, payload_hashes):
    if receipt.get('schema')!='operational075/locked-submission/v1' or type(receipt.get('epoch')) is not int or receipt['epoch']!=epoch or receipt['service_day_id']!=window['service_day_id'] or type(receipt.get('dispatch_round')) is not int or receipt['dispatch_round']!=window['dispatch_round'] or receipt['window_sha256']!=digest(window) or receipt['submission_sha256']!=hashlib.sha256(raw).hexdigest() or type(receipt.get('submission_bytes')) is not int or receipt['submission_bytes']!=len(raw) or receipt['state_sha256']!=digest(state) or receipt['previous_receipt_sha256']!=previous or receipt['intermediate_validation_returned'] is not False or receipt['intermediate_score_returned'] is not False:raise ValueError('OPERATIONAL075_LOCKED_HISTORY_CHANGED')
    resources=receipt['resources']
    if resources['worker_payload_hashes']!=payload_hashes or resources['worker_guard_sha256']!=hashlib.sha256(_WORKER.encode()).hexdigest() or resources['returncode']!=0:raise ValueError('OPERATIONAL075_LOCKED_WORKER_PAYLOAD_CHANGED')
    for key in ('wall_seconds','child_cpu_seconds','policy_cpu_seconds'):
        value=resources[key]
        if type(value) not in (int,float) or not math.isfinite(value) or value<0:raise ValueError('OPERATIONAL075_INVALID_RESOURCE_MEASUREMENT')
    return receipt


def run_episode(source_root, policy_module, output, initial_state=None):
    source_root=Path(source_root).absolute();output=Path(output).absolute()
    if output==source_root or source_root in output.parents or output.is_symlink():raise ValueError('OPERATIONAL075_SEPARATE_PRIVATE_OUTPUT_REQUIRED')
    source_receipt=source.verify_source(source_root);os.chmod(source_root,0o700)
    public=_load_public(source_root);confirmations=_load_confirmations(source_root)
    output.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(output,0o700)
    package=Path(__file__).parent
    code_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(package.glob('*.py'))}
    payload_hashes=worker_payload_hashes()
    host={'schema':'operational075/rolling-host/v1','source_manifest_sha256':source_receipt['source_manifest_sha256'],'upstream_commit':source_receipt['upstream_commit'],'policy_module':policy_module,'code_hashes':code_hashes,'worker_payload_hashes':payload_hashes,'initial_state_sha256':digest(initial_state),'periods':18,'feedback':'No validity, dispatched-order or cost feedback before all eighteen raw submissions are locked.','worker_identity':_worker_identity()}
    host_path=output/'HOST.json'
    if host_path.exists():
        if json.loads(host_path.read_text())!=host:raise ValueError('OPERATIONAL075_SOURCE_OR_POLICY_CHANGED_ON_RESUME')
    else:_exclusive(host_path,encoded(host))
    state=copy.deepcopy(initial_state);previous=None;receipts=[];paths=[]
    for epoch in range(18):
        if {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(package.glob('*.py'))}!=code_hashes:raise ValueError('OPERATIONAL075_POLICY_SOURCE_CHANGED_DURING_EPISODE')
        if worker_payload_hashes()!=payload_hashes:raise ValueError('OPERATIONAL075_WORKER_PAYLOAD_CHANGED_DURING_EPISODE')
        window=visible_window(public,confirmations,epoch);folder=output/'periods'/f'{epoch:02d}'
        if (folder/'RECEIPT.json').exists():
            receipt=json.loads((folder/'RECEIPT.json').read_text());raw=(folder/'SUBMISSION.json').read_bytes();state=json.loads((folder/'STATE.json').read_text())
            check_locked_receipt(receipt,epoch,raw,window,state,previous,payload_hashes)
        else:
            if folder.exists():raise ValueError('OPERATIONAL075_INTERRUPTED_PERIOD_PRESERVED_NO_RETRY')
            folder.mkdir(parents=True,mode=0o700)
            _exclusive(folder/'STARTED.json',encoded({'epoch':epoch,'window_sha256':digest(window),'prior_state_sha256':digest(state),'previous_receipt_sha256':previous}))
            try:raw,new_state,resources=run_policy(policy_module,window,state,expected_payload_hashes=payload_hashes)
            except Exception as error:
                _exclusive(folder/'ERROR.json',encoded({'error_type':type(error).__name__,'error':str(error)[:1500]}));raise
            receipt=lock_submission(output,epoch,raw,window,new_state,resources,previous);state=new_state
        previous=digest(receipt);receipts.append(receipt);paths.append(folder/'SUBMISSION.json')
    if (output/'LOCKS.json').exists():
        if json.loads((output/'LOCKS.json').read_text())!=receipts:raise ValueError('OPERATIONAL075_LOCK_MANIFEST_CHANGED')
    else:_exclusive(output/'LOCKS.json',encoded(receipts))
    transcript=output/'TRANSCRIPT.json'
    result_path=output/'CLIENT_RESULT.json'
    if result_path.exists():
        result=json.loads(result_path.read_text())
        if result.get('locked_receipts_sha256')!=digest(receipts) or result.get('transcript_sha256')!=(hashlib.sha256(transcript.read_bytes()).hexdigest() if transcript.exists() else None):raise ValueError('OPERATIONAL075_FINAL_RESULT_CHANGED')
        return result
    accepted=client.finalize_grocery(source_root,paths,transcript)
    result={'schema':'operational075/final-rolling-result/v1','policy_module':policy_module,'locked_submissions':18,'locked_receipts_sha256':digest(receipts),'transcript_sha256':hashlib.sha256(transcript.read_bytes()).hexdigest() if transcript.exists() else None,'upstream_client':accepted,'worker_identity':host['worker_identity'],'resources':{'wall_seconds':sum(r['resources']['wall_seconds'] for r in receipts),'child_cpu_seconds':sum(r['resources']['child_cpu_seconds'] for r in receipts)},'scope':'Actual computational submissions accepted or rejected by original public task client; no physical delivery or commercial sale.'}
    _exclusive(result_path,encoded(result))
    return result


def audit_episode(source_root, output):
    source_root=Path(source_root).absolute();output=Path(output).absolute()
    source_receipt=source.verify_source(source_root)
    public=_load_public(source_root);confirmations=_load_confirmations(source_root)
    def read(path):
        if not path.is_file() or any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('OPERATIONAL075_REGULAR_AUDIT_RECORD_REQUIRED')
        return path.read_bytes()
    host=json.loads(read(output/'HOST.json'))
    code_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob('*.py'))}
    payload_hashes=worker_payload_hashes()
    if host['code_hashes']!=code_hashes or host['worker_payload_hashes']!=payload_hashes or host['source_manifest_sha256']!=source_receipt['source_manifest_sha256'] or host['upstream_commit']!=source_receipt['upstream_commit'] or host['periods']!=18:raise ValueError('OPERATIONAL075_AUDIT_SOURCE_CHANGED')
    previous=None;receipts=[];paths=[]
    for epoch in range(18):
        folder=output/'periods'/f'{epoch:02d}';path=folder/'SUBMISSION.json';raw=read(path);state=json.loads(read(folder/'STATE.json'));receipt=json.loads(read(folder/'RECEIPT.json'));window=visible_window(public,confirmations,epoch)
        check_locked_receipt(receipt,epoch,raw,window,state,previous,payload_hashes)
        previous=digest(receipt);receipts.append(receipt);paths.append(path)
    if json.loads(read(output/'LOCKS.json'))!=receipts:raise ValueError('OPERATIONAL075_AUDIT_LOCK_MANIFEST_CHANGED')
    result=json.loads(read(output/'CLIENT_RESULT.json'))
    with tempfile.TemporaryDirectory(prefix='operational075-independent-final-') as folder:
        transcript=Path(folder)/'TRANSCRIPT.json';replayed=client.finalize_grocery(source_root,paths,transcript)
        transcript_hash=hashlib.sha256(transcript.read_bytes()).hexdigest() if transcript.exists() else None
        if transcript.exists() and read(output/'TRANSCRIPT.json')!=transcript.read_bytes():raise ValueError('OPERATIONAL075_AUDIT_TRANSCRIPT_CHANGED')
    if result['upstream_client']!=replayed or result['locked_receipts_sha256']!=digest(receipts) or result['transcript_sha256']!=transcript_hash or result['locked_submissions']!=18 or result['policy_module']!=host['policy_module']:raise ValueError('OPERATIONAL075_AUDIT_CLIENT_CLAIM_CHANGED')
    return {'schema':'operational075/rolling-replay/v1','accepted':True,'computational_delivery_accepted':replayed['accepted'],'original_submissions_replayed':18,'source_manifest_sha256':source_receipt['source_manifest_sha256'],'locked_receipts_sha256':digest(receipts),'transcript_sha256':transcript_hash,'original_client':replayed,'scope':'Independent original-client and immutable-submission replay; no policy rerun or intermediate feedback.'}
