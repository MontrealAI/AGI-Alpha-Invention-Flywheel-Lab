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


def copy_history(target,record,manifest,seen=None):
    seen=set() if seen is None else seen
    for ticket in record.get('source_transitions',{}).values():
        body=ticket['body'];identity=body['from_source']['sha256']
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
        result.add(Path(ticket['body']['historical_root']))
        result.update(historical_roots(ticket['body']['prior_record']))
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


def export(business,output,offline):
    descriptor=read(business/'OPERATOR.json');result=read(business/'RESULT.json')
    if not result['complete']:raise ValueError('COMPLETE_REGISTERED_HORIZON_REQUIRED')
    if output.exists() or any(p.is_symlink() for p in [output,*output.parents]):raise FileExistsError('NEW_PUBLIC_OUTPUT_REQUIRED')
    output.mkdir(parents=True);source=business/descriptor['source_dir']
    manifest=read(business/'SERVICES.json')
    copy_source(source,output/'source',result['source']['files'],manifest)
    copy_history(output/'source',result['owned_account'],manifest)
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
        code='import json,sys;from pathlib import Path;from connected_enterprise.verify import audit;p=Path(sys.argv[1]);print(json.dumps(audit(p/"source",json.load(open(p/"SERVICES.json")),json.load(open(p/"RESULT.json"))),sort_keys=True))'
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


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--business',required=True);parser.add_argument('--output',required=True);parser.add_argument('--offline-historical-sources',action='store_true');a=parser.parse_args()
    root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
    from enterprise.runner import RunLock
    business=Path(a.business).absolute();output=Path(a.output).absolute()
    with RunLock(business):print(json.dumps(export(business,output,a.offline_historical_sources),sort_keys=True))


if __name__=='__main__':main()
