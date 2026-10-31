"""Export an existing completed business with recursive pinned verifier closures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
import stat
import threading
import uuid
from contextlib import contextmanager

from connected_enterprise.transition_evidence import ticket_body, record_blobs, output_scope, persist_evidence

MAX_FILES=10_000
MAX_BYTES=512*1024*1024


def read(path):
    from commercial.ledger import strict_json
    return strict_json(Path(path).read_bytes())


def write(path,value):
    Path(path).write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def copy_source(original,target,expected,manifest,budget=None):
    budget={"files":0,"bytes":0} if budget is None else budget
    expected=dict(expected)
    for job in manifest['jobs']:
        for field in ['input','artifact','receipt']:
            name=job[field];bound=job[field+'_sha256']
            if name in expected and expected[name]!=bound:raise ValueError('SOURCE_INPUT_HASH_CONFLICT')
            expected[name]=bound
    for name,bound in sorted(expected.items()):
        relative=Path(name);path=original/relative
        if relative.is_absolute() or '..' in relative.parts:raise ValueError('RELATIVE_BOUND_SOURCE_REQUIRED')
        if any(p.is_symlink() for p in [path,*path.parents]):raise ValueError('SOURCE_SYMLINK_REFUSED')
        if not path.is_file() or path.stat().st_size>MAX_BYTES:raise ValueError('BOUNDED_REGULAR_SOURCE_REQUIRED')
        if '.sqlite' in path.name or path.name.endswith(('.key','-key')):raise ValueError('PRIVATE_STATE_IN_SOURCE_REFUSED')
        if sha(path)!=bound:raise ValueError('BOUND_SOURCE_CONTENT_CHANGED')
        budget['files']+=1;budget['bytes']+=path.stat().st_size
        if budget['files']>MAX_FILES or budget['bytes']>MAX_BYTES:raise ValueError('PUBLIC_ARCHIVE_GUARD_EXCEEDED')
        dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)


def copy_history(target,record,manifest,seen=None,budget=None,processed=None):
    """One exact closure per source version; ancestry remains in original tickets."""
    seen=set() if seen is None else seen
    processed={} if processed is None else processed
    for ticket in record.get('source_transitions',{}).values():
        body=ticket_body(ticket);identity=body['from_source']['sha256']
        if identity in seen:raise ValueError('HISTORICAL_SOURCE_CYCLE_REFUSED')
        runtime=body.get('operating',{}).get('from_runtime')
        if runtime is None:raise ValueError('PINNED_HISTORICAL_RUNTIME_INVENTORY_REQUIRED')
        expected=dict(runtime['files'])
        for name,bound in body['verifier_files'].items():
            if name in expected and expected[name]!=bound:raise ValueError('HISTORICAL_VERIFIER_HASH_CONFLICT')
            expected[name]=bound
        if identity in processed and processed[identity]!=expected:
            raise ValueError('HISTORICAL_VERSION_INVENTORY_CHANGED')
        if identity not in processed:
            if len(processed)>=4:raise ValueError('BOUNDED_SOURCE_TRANSITION_ANCESTRY_REQUIRED')
            source=Path(body['historical_root'])
            destination=target/'historical-source-versions'/identity
            copy_source(source,destination,expected,manifest,budget)
            processed[identity]=expected
        copy_history(target,body['prior_record'],manifest,seen|{identity},budget,processed)


def historical_roots(record):
    result=set()
    for ticket in record.get('source_transitions',{}).values():
        body=ticket_body(ticket)
        result.add(Path(body['historical_root']))
        result.update(historical_roots(body['prior_record']))
    return result


def inventory(output):
    files={};total=0
    for path in sorted(output.rglob('*')):
        if path.is_symlink():raise ValueError('PUBLIC_SYMLINK_REFUSED')
        if not path.is_file() or '__pycache__' in path.parts:continue
        total+=path.stat().st_size
        if len(files)>=MAX_FILES or total>MAX_BYTES:raise ValueError('PUBLIC_ARCHIVE_GUARD_EXCEEDED')
        files[path.relative_to(output).as_posix()]={'bytes':path.stat().st_size,'sha256':sha(path)}
    return files,total


@contextmanager
def unavailable_sources(roots,plan):
    token=uuid.uuid4().hex;marker=('HISTORICAL_SOURCE_UNAVAILABLE_'+token+'\n').encode()
    held=[];violations=[];stop=threading.Event();watcher=None
    def intact(path,inode):
        try:return stat.S_ISREG(path.lstat().st_mode) and path.stat().st_ino==inode and path.read_bytes()==marker
        except OSError:return False
    def monitor():
        while not stop.wait(.01):
            if any(not intact(p,ino) for p,q,ino in held):violations.append('HISTORICAL_SOURCE_REAPPEARED');return
    write(plan,{'scope':'Temporarily unavailable historical SOURCE directories only; no account/key movement',
                'sources':[str(p) for p in roots],'recovery_suffix':'-offline-held-'+token})
    try:
        for path in sorted(roots,key=lambda p:(-len(p.parts),str(p))):
            if not path.is_dir() or path.is_symlink():raise ValueError('OWNED_NORMAL_HISTORICAL_SOURCE_REQUIRED')
            temporary=path.with_name(path.name+'-offline-held-'+token)
            if temporary.exists():raise FileExistsError('OFFLINE_SOURCE_TARGET_EXISTS')
            path.rename(temporary)
            try:
                with path.open('xb') as stream:stream.write(marker);stream.flush();os.fsync(stream.fileno())
                path.chmod(0o400);held.append((path,temporary,path.stat().st_ino))
            except BaseException:
                if not path.exists():temporary.rename(path)
                raise
        watcher=threading.Thread(target=monitor,daemon=True);watcher.start()
        yield
        if violations or any(not intact(p,ino) for p,q,ino in held):raise ValueError('HISTORICAL_SOURCE_REAPPEARED')
    finally:
        stop.set()
        if watcher is not None:watcher.join()
        for path,temporary,inode in reversed(held):
            if intact(path,inode):path.unlink()
            elif path.exists():path.rename(path.with_name(path.name+'-unexpected-preserved-'+token))
            temporary.rename(path)


def export(business,output,offline):
    with output_scope(business):return _export(business,output,offline)


def _export(business,output,offline):
    descriptor=read(business/'OPERATOR.json');result=read(business/'RESULT.json')
    if not result['complete']:raise ValueError('COMPLETE_REGISTERED_HORIZON_REQUIRED')
    if output.exists() or any(p.is_symlink() for p in [output,*output.parents]):raise FileExistsError('NEW_PUBLIC_OUTPUT_REQUIRED')
    output.mkdir(parents=True);source=business/descriptor['source_dir']
    manifest=read(business/'SERVICES.json')
    blobs=record_blobs(result['owned_account']);budget={'files':0,'bytes':0}
    if blobs:
        store=output/'TRANSITION_EVIDENCE';store.mkdir(mode=0o700);persist_evidence(store,blobs)
        write(output/'TRANSITION_EVIDENCE_INDEX.json',{'schema':'agi-alpha/portable-transition-evidence/v1','objects':{n:{'bytes':len(r),'sha256':n} for n,r in sorted(blobs.items())},'scope':'Exact referenced key-free canonical objects; no authority or account key'})
        initial,total=inventory(output);budget={'files':len(initial),'bytes':total}
    copy_source(source,output/'source',result['source']['files'],manifest,budget)
    copy_history(output/'source',result['owned_account'],manifest,budget=budget)
    admissions={}
    from commercial.ledger import digest
    for ident,ticket in result['owned_account'].get('source_transitions',{}).items():
        name=digest(ticket)+'.json';path=business/'TRANSITION_PREFLIGHT'/name
        if path.exists():
            if path.is_symlink():raise ValueError('PREFLIGHT_RECEIPT_SYMLINK_REFUSED')
            value=read(path)
            if value.get('body',{}).get('ticket_sha256')!=digest(ticket):raise ValueError('PUBLICATION_PREFLIGHT_TICKET_CHANGED')
            target=output/'TRANSITION_PREFLIGHT'/name;target.parent.mkdir(exist_ok=True);shutil.copyfile(path,target)
            admissions[ident]={'path':'TRANSITION_PREFLIGHT/'+name,'sha256':sha(target)}
        else:admissions[ident]={'status':'NOT_PRESENT_IN_THIS_HISTORICAL_VERSION'}
    if admissions:write(output/'PUBLICATION_ADMISSIONS.json',admissions)
    for name in ['RESULT.json','STATE.json','SERVICES.json','SCOREBOARD.json']:
        if (business/name).is_file():shutil.copyfile(business/name,output/name)
    inventory(output)
    roots=sorted(historical_roots(result['owned_account']),key=str)
    plan=output.parent/(output.name+'-offline-restore.json')
    from contextlib import nullcontext
    with unavailable_sources(roots,plan) if offline else nullcontext():
        code='import json,sys;from pathlib import Path;from connected_enterprise.verify import audit;p=Path(sys.argv[1]);print(json.dumps(audit(p/"source",json.load(open(p/"SERVICES.json")),json.load(open(p/"RESULT.json"))),sort_keys=True))'
        if blobs:
            code='import json,sys;from pathlib import Path;from connected_enterprise.verify import audit;from connected_enterprise.transition_evidence import output_scope;p=Path(sys.argv[1])\nwith output_scope(p):print(json.dumps(audit(p/"source",json.load(open(p/"SERVICES.json")),json.load(open(p/"RESULT.json"))),sort_keys=True))'
        env={**os.environ,'PYTHONPATH':str(output/'source'),'PYTHONDONTWRITEBYTECODE':'1'}
        done=subprocess.run([sys.executable,'-c',code,str(output)],cwd=output/'source',env=env,capture_output=True,text=True,timeout=300)
        (output.parent/(output.name+'-audit.stdout')).write_text(done.stdout)
        (output.parent/(output.name+'-audit.stderr')).write_text(done.stderr)
        if done.returncode:raise RuntimeError('PORTABLE_AUDIT_FAILED; preserved sibling stdout/stderr')
        checked=json.loads(done.stdout)
        if not checked.get('accepted'):raise ValueError('PUBLIC_AUDIT_NOT_ACCEPTED')
    receipt={'schema':'agi-alpha/completion023-portable-audit/v1','accepted':True,'offline_historical_sources':offline,'recursive_historical_closures':True,'private_account_or_key_exported':False,'executing_runtime_sha256':result['source']['sha256'],'audit':checked,'scope':'Exact-source key-free engineering reproduction; not fresh economic confirmation, original latest-account recovery or release download'}
    write(output/'PORTABLE_AUDIT.json',receipt)
    files,total=inventory(output);write(output/'INTEGRITY.json',{'files':files,'bytes':total,'guards':{'files':MAX_FILES,'bytes':MAX_BYTES}})
    inventory(output)
    archive=output.with_suffix('.zip')
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in sorted(output.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:z.write(path,path.relative_to(output))
    return {'accepted':True,'archive':str(archive),'archive_bytes':archive.stat().st_size,'archive_sha256':sha(archive),'public_files':len(files)+1,'source_sha256':result['source']['sha256']}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--business',required=True);parser.add_argument('--output',required=True);parser.add_argument('--offline-historical-sources',action='store_true');a=parser.parse_args()
    root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
    from enterprise.runner import RunLock
    business=Path(a.business).absolute();output=Path(a.output).absolute()
    with RunLock(business):print(json.dumps(export(business,output,a.offline_historical_sources),sort_keys=True))


if __name__=='__main__':main()
