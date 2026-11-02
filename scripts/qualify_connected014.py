"""Qualify a bounded source archive, fresh operation and key-free public audit."""
from __future__ import annotations
import argparse
import hashlib
import json
import importlib.metadata
import os
from pathlib import Path, PurePosixPath
import resource
import signal
import stat
import subprocess
import sys
import time
import zipfile

REPOSITORY=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPOSITORY))
from connected_enterprise.runner import identity, source_paths
from connected_enterprise.platform_runtime import command_budget

LIMIT_BYTES=256_000_000

def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')

def extract_checked(archive,destination,expected=None):
    if destination.exists():raise FileExistsError('NEW_EXTRACTION_DIRECTORY_REQUIRED')
    with zipfile.ZipFile(archive) as z:
        infos=z.infolist();names=[i.filename for i in infos]
        if len(names)!=len(set(names)) or sum(i.file_size for i in infos)>LIMIT_BYTES:raise ValueError('BOUNDED_UNIQUE_ARCHIVE_REQUIRED')
        for item in infos:
            name=PurePosixPath(item.filename)
            if name.is_absolute() or '..' in name.parts or stat.S_ISLNK(item.external_attr>>16):raise ValueError('ARCHIVE_PATH_OR_SYMLINK_REFUSED')
            if item.filename.endswith('.adaptive-simulation-key') or '.sqlite' in item.filename or '.git' in name.parts:raise ValueError('PRIVATE_STATE_OR_GIT_IN_PUBLIC_ARCHIVE')
        if z.testzip() is not None:raise ValueError('ARCHIVE_CRC_FAILURE')
        if expected is not None:
            if set(names)!=set(expected)|{'SOURCE_MANIFEST.json'}:raise ValueError('EXACT_SOURCE_ARCHIVE_MEMBERS_REQUIRED')
            for name,digest in expected.items():
                if sha(z.read(name))!=digest:raise ValueError('SOURCE_ARCHIVE_MEMBER_HASH_CHANGED:'+name)
        z.extractall(destination)
    return {'files':len(infos),'uncompressed_bytes':sum(i.file_size for i in infos),'crc_verified':True}

def native_state(output):
    result={}
    for path in sorted((output/'worlds').glob('*/RESULT.json')):
        row=read(path)
        result[path.parent.name]={'actions_sha256':row['owned_account']['ledger']['actions_sha256'],'summary':row['summary']}
    if not result:raise ValueError('EXECUTED_NATIVE_WORLD_REQUIRED')
    return result

def _terminate_process_group(child):
    """Drain and reap this invocation's POSIX group, including orphaned children."""
    try: os.killpg(child.pid,signal.SIGTERM)
    except ProcessLookupError: pass
    drain=time.monotonic()+5
    while True:
        try: child.wait(timeout=max(0,drain-time.monotonic()))
        except subprocess.TimeoutExpired: pass
        try: os.killpg(child.pid,0)
        except ProcessLookupError: break
        remaining=drain-time.monotonic()
        if remaining<=0: break
        time.sleep(min(0.05,remaining))
    try: os.killpg(child.pid,signal.SIGKILL)
    except ProcessLookupError: pass
    child.wait()


def run_command(command,cwd,log,deadline,commands):
    remaining=None if deadline is None else deadline-time.monotonic()
    if remaining is not None and remaining<=0:raise TimeoutError('CLEAN_QUALIFICATION_WALL_BOUNDARY')
    start=time.monotonic();env={**os.environ,'PYTHONPATH':str(cwd),'PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1'}
    with log.with_suffix('.stdout').open('w') as stdout,log.with_suffix('.stderr').open('w') as stderr:
        child=subprocess.Popen(command,cwd=cwd,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
        try:returncode=child.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            _terminate_process_group(child)
            raise TimeoutError('CLEAN_QUALIFICATION_WALL_BOUNDARY')
        except BaseException:
            _terminate_process_group(child)
            raise
    record={'command':command,'cwd':str(cwd),'returncode':returncode,'wall_seconds':time.monotonic()-start,'stdout':log.with_suffix('.stdout').name,'stderr':log.with_suffix('.stderr').name}
    commands.append(record)
    if returncode:raise RuntimeError('CLEAN_COMMAND_FAILED:'+str(command)+':see '+str(log.with_suffix('.stderr')))
    return record

def qualify(output,smoke,timeout_seconds=None):
    output=Path(output).expanduser()
    if any(p.is_symlink() for p in [output,*output.parents]):raise ValueError('UNSYMLINKED_QUALIFICATION_ROOT_REQUIRED')
    output=output.resolve()
    if output.exists():raise FileExistsError('NEW_QUALIFICATION_OUTPUT_REQUIRED')
    output.mkdir(parents=True);start=time.monotonic();cpu0=resource.getrusage(resource.RUSAGE_CHILDREN);commands=[]
    receipt={'schema':'agi-alpha/connected014-clean-qualification/v1','accepted':False,'mode':'ENGINEERING_SMOKE' if smoke else 'REGISTERED_CONFIRMATION_REPRODUCTION','commands':commands,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    try:
        budget=command_budget(timeout_seconds)
        timeout_seconds=budget['timeout_seconds'];deadline=None if timeout_seconds is None else start+timeout_seconds
        receipt['runtime_budget']=budget
        dependencies={}
        for line in (REPOSITORY/'requirements-commercial010.txt').read_text().splitlines():
            if not line.strip() or line.lstrip().startswith('#'):continue
            package,expected=line.strip().split('==',1);actual=importlib.metadata.version(package)
            if actual!=expected:raise ValueError('PINNED_DEPENDENCY_REQUIRED:'+package+':'+expected+':found '+actual)
            dependencies[package]=actual
        receipt['runtime']={'python':sys.version,'dependencies':dependencies,'dependency_installation':'NOT_PERFORMED; exact preinstalled pinned runtime checked. Fresh dependency installation must be qualified separately.'}
        frozen_source=identity(REPOSITORY)
        names=set(source_paths(REPOSITORY))|{'AGENTS.md','requirements-commercial010.txt','scripts/qualify_connected014.py','docs/connected014/OPERATOR.md'}
        # Explicit non-executing prior bytes for historical paper verification.
        names.update(p.relative_to(REPOSITORY).as_posix() for p in (REPOSITORY/'historical/strategic024-prior-source').rglob('*.txt') if p.is_file())
        files={}
        for name in sorted(names):
            path=REPOSITORY/name
            if not path.is_file() or any(p.is_symlink() for p in [path,*path.parents]):raise ValueError('REGULAR_QUALIFICATION_SOURCE_REQUIRED:'+name)
            raw=path.read_bytes()
            if sum(len(v) for v in files.values())+len(raw)>LIMIT_BYTES:raise ValueError('BOUNDED_SOURCE_PACKAGE_REQUIRED')
            files[name]=raw
        manifest={'schema':'agi-alpha/connected014-source-distribution/v1','executing_source':frozen_source,'files':{k:sha(v) for k,v in files.items()},'git_required':False}
        archive=output/'connected014-source.zip'
        with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for name,raw in [*files.items(),('SOURCE_MANIFEST.json',(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode())]:
                info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,raw)
        source=output/'extracted-source';extraction=extract_checked(archive,source,manifest['files'])
        if (source/'.git').exists() or identity(source)!=frozen_source:raise ValueError('CLEAN_SOURCE_IDENTITY_CHANGED')
        operating=output/'operation';base=[sys.executable,'-m','connected_enterprise']
        run_command(base+['run','--output',str(operating)]+(['--smoke'] if smoke else []),source,output/'01-run',deadline,commands)
        if read(operating/'FROZEN.json')['source']!=frozen_source or read(operating/'FROZEN.json')['git_commit'] is not None:raise ValueError('FRESH_NO_GIT_EXECUTION_BINDING_CHANGED')
        before=native_state(operating)
        run_command(base+['resume','--output',str(operating)],source,output/'02-resume',deadline,commands)
        if native_state(operating)!=before:raise ValueError('COMPLETED_RESUME_CHANGED_NATIVE_FINANCIAL_RECORDS')
        run_command(base+['audit','--output',str(operating)],source,output/'03-audit',deadline,commands)
        audit=read(operating/'PACKAGE_AUDIT.json')
        if not audit.get('accepted'):raise ValueError('CLEAN_NATIVE_AND_OPERATING_AUDIT_REJECTED')
        public=output/'connected014-keyfree.zip'
        run_command(base+['package','--output',str(operating),'--archive',str(public)],source,output/'04-package',deadline,commands)
        public_copy=output/'public-copy';public_extraction=extract_checked(public,public_copy)
        run_command(base+['audit','--output',str(public_copy)],public_copy/'source',output/'05-public-audit',deadline,commands)
        public_audit=read(public_copy/'PACKAGE_AUDIT.json')
        if not public_audit.get('accepted') or public_audit['source_sha256']!=frozen_source['sha256']:raise ValueError('EXPORTED_PUBLIC_AUDIT_BINDING_CHANGED')
        receipt.update(accepted=True,source_sha256=frozen_source['sha256'],source_files=frozen_source['files'],source_archive={'bytes':archive.stat().st_size,'sha256':sha(archive.read_bytes()),'extraction':extraction},public_archive={'bytes':public.stat().st_size,'sha256':sha(public.read_bytes()),'extraction':public_extraction},no_git_execution=True,completed_resume_financially_unchanged=True,native_and_operating_audit=audit,keyfree_public_audit=public_audit,commercial_claim='Engineering packaging and reproduction qualification only; smoke output is not fresh commercial confirmation.')
    except BaseException as exc:
        receipt['failure']={'type':type(exc).__name__,'message':str(exc)}
        raise
    finally:
        cpu=resource.getrusage(resource.RUSAGE_CHILDREN)
        receipt.update(finished_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),wall_seconds=time.monotonic()-start,children_cpu_seconds=cpu.ru_utime+cpu.ru_stime-cpu0.ru_utime-cpu0.ru_stime,timeout_seconds=timeout_seconds)
        receipt['logs']={p.name:sha(p.read_bytes()) for p in sorted(output.glob('0*.*')) if p.is_file()}
        write(output/'QUALIFICATION.json',receipt)
    print(json.dumps({'accepted':receipt['accepted'],'receipt':str(output/'QUALIFICATION.json'),'source_sha256':receipt['source_sha256']},sort_keys=True))
    return receipt

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);parser.add_argument('--smoke',action='store_true');parser.add_argument('--timeout-seconds',type=int)
    args=parser.parse_args()
    try: command_budget(args.timeout_seconds)
    except (ValueError,TimeoutError) as error: parser.error(str(error))
    qualify(args.output,args.smoke,args.timeout_seconds)

if __name__=='__main__':main()
