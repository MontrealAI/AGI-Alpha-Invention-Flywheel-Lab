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
from contextlib import nullcontext

MAX_FILES=10_000
MAX_BYTES=512*1024*1024


def read(path):
    from commercial.ledger import strict_json
    return strict_json(Path(path).read_bytes())


def write(path,value):
    Path(path).write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def copy_source(original,target,expected,manifest):
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
        dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)


def resolved_body(ticket):
    from connected_enterprise.transition_evidence import ticket_body, V2
    return ticket_body(ticket) if ticket.get('body',{}).get('schema')==V2 else ticket['body']


def reachable_evidence(record):
    """Resolve only hash-addressed bytes from the caller-selected active store."""
    from connected_enterprise.transition_evidence import V2, read_evidence_blob, ticket_body
    blobs={};seen=set();nodes=0
    def visit(value,depth=0):
        nonlocal nodes
        nodes+=1
        if depth>128 or nodes>2_000_000:raise ValueError('PORTABLE_TRANSITION_TRAVERSAL_BOUND')
        if isinstance(value,dict):
            if value.get('body',{}).__class__ is dict and value.get('body',{}).get('schema')==V2:
                # Full resolver validates wire shape, references and canonical content.
                body=ticket_body(value)
                for ref in value['body']['evidence'].values():
                    name=ref['sha256']
                    if name not in blobs:blobs[name]=read_evidence_blob(name)
                ident=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                if ident in seen:return
                seen.add(ident);visit(body,depth+1)
            else:
                for item in value.values():visit(item,depth+1)
        elif isinstance(value,list):
            for item in value:visit(item,depth+1)
    visit(record)
    return blobs


def copy_transition_evidence(output,record):
    from connected_enterprise.transition_evidence import persist_evidence
    blobs=reachable_evidence(record)
    if not blobs:return
    files,total=inventory(output)
    if len(files)+len(blobs)>MAX_FILES or total+sum(map(len,blobs.values()))>MAX_BYTES:
        raise ValueError('PUBLIC_ARCHIVE_GUARD_EXCEEDED')
    target=output/'transition-evidence';target.mkdir()
    persist_evidence(target,blobs)
    inventory(output)


def copy_history(target,record,manifest,seen=None):
    seen=set() if seen is None else seen
    for ticket in record.get('source_transitions',{}).values():
        body=resolved_body(ticket);identity=body['from_source']['sha256']
        if identity in seen:raise ValueError('HISTORICAL_SOURCE_CYCLE_REFUSED')
        source=Path(body['historical_root'])
        destination=target/'historical-source-versions'/identity
        if not destination.exists():
            runtime=body.get('operating',{}).get('from_runtime')
            if runtime is None:raise ValueError('PINNED_HISTORICAL_RUNTIME_INVENTORY_REQUIRED')
            expected=dict(runtime['files'])
            for name,bound in body['verifier_files'].items():
                if name in expected and expected[name]!=bound:raise ValueError('HISTORICAL_VERIFIER_HASH_CONFLICT')
                expected[name]=bound
            copy_source(source,destination,expected,manifest)
            copy_history(destination,body['prior_record'],manifest,seen|{identity})


def historical_roots(record):
    result=set()
    for ticket in record.get('source_transitions',{}).values():
        body=resolved_body(ticket)
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


def _export(business,output,offline):
    descriptor=read(business/'OPERATOR.json');result=read(business/'RESULT.json')
    if not result['complete']:raise ValueError('COMPLETE_REGISTERED_HORIZON_REQUIRED')
    if output.exists() or any(p.is_symlink() for p in [output,*output.parents]):raise FileExistsError('NEW_PUBLIC_OUTPUT_REQUIRED')
    output.mkdir(parents=True);source=business/descriptor['source_dir']
    manifest=read(business/'SERVICES.json')
    copy_source(source,output/'source',result['source']['files'],manifest)
    copy_history(output/'source',result['owned_account'],manifest)
    copy_transition_evidence(output,result['owned_account'])
    for name in ['RESULT.json','STATE.json','SERVICES.json','SCOREBOARD.json']:
        if (business/name).is_file():shutil.copyfile(business/name,output/name)
    inventory(output)
    roots=sorted(historical_roots(result['owned_account']),key=str);renamed=[]
    plan=output.parent/(output.name+'-offline-restore.json')
    try:
        if offline:
            write(plan,{'scope':'Temporarily unavailable owned historical SOURCE directories only; no account or key movement','renames':[{'original':str(p),'temporary':str(p.with_name(p.name+'-completion023-offline'))} for p in roots]})
            for original in roots:
                temporary=original.with_name(original.name+'-completion023-offline')
                if temporary.exists():raise FileExistsError('OFFLINE_SOURCE_TARGET_EXISTS')
                original.rename(temporary);renamed.append((original,temporary))
        code='\n'.join(['import json,sys','from pathlib import Path','from contextlib import nullcontext','from connected_enterprise.verify import audit','p=Path(sys.argv[1])','store=p/"transition-evidence"','if store.exists():',' from connected_enterprise.transition_evidence import evidence_directory',' context=evidence_directory(store)','else: context=nullcontext()','with context:',' print(json.dumps(audit(p/"source",json.load(open(p/"SERVICES.json")),json.load(open(p/"RESULT.json"))),sort_keys=True))'])
        env={**os.environ,'PYTHONPATH':str(output/'source'),'PYTHONDONTWRITEBYTECODE':'1'}
        done=subprocess.run([sys.executable,'-c',code,str(output)],cwd=output/'source',env=env,capture_output=True,text=True,timeout=300)
        (output.parent/(output.name+'-audit.stdout')).write_text(done.stdout)
        (output.parent/(output.name+'-audit.stderr')).write_text(done.stderr)
        if done.returncode:raise RuntimeError('PORTABLE_AUDIT_FAILED; preserved sibling stdout/stderr')
        checked=json.loads(done.stdout)
        if not checked.get('accepted'):raise ValueError('PUBLIC_AUDIT_NOT_ACCEPTED')
    finally:
        for original,temporary in reversed(renamed):temporary.rename(original)
    receipt={'schema':'agi-alpha/completion023-portable-audit/v1','accepted':True,'offline_historical_sources':offline,'recursive_historical_closures':True,'private_account_or_key_exported':False,'executing_runtime_sha256':result['source']['sha256'],'audit':checked,'scope':'Key-free reproduction of original exposed candidate; not composed-source or published-release qualification'}
    write(output/'PORTABLE_AUDIT.json',receipt)
    files,total=inventory(output);write(output/'INTEGRITY.json',{'files':files,'bytes':total,'guards':{'files':MAX_FILES,'bytes':MAX_BYTES}})
    inventory(output)
    archive=output.with_suffix('.zip')
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in sorted(output.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:z.write(path,path.relative_to(output))
    return {'accepted':True,'archive':str(archive),'archive_bytes':archive.stat().st_size,'archive_sha256':sha(archive),'public_files':len(files)+1,'source_sha256':result['source']['sha256']}


def export(business,output,offline):
    from connected_enterprise.transition_evidence import evidence_directory
    business=Path(business).absolute();output=Path(output).absolute()
    store=business/'transition-evidence'
    with evidence_directory(store) if store.exists() else nullcontext():
        return _export(business,output,offline)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--business',required=True);parser.add_argument('--output',required=True);parser.add_argument('--offline-historical-sources',action='store_true');a=parser.parse_args()
    root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
    from enterprise.runner import RunLock
    business=Path(a.business).absolute();output=Path(a.output).absolute()
    with RunLock(business):print(json.dumps(export(business,output,a.offline_historical_sources),sort_keys=True))


if __name__=='__main__':main()
