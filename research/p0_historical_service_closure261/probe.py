"""P0-261. No account, keys or monetary operations."""
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time

CASES = ["original", "python_only", "complete_stage", "missing_input", "changed_receipt", "restored"]
OWNER = "ced6c1cb004887dcdafaea59a2976020be649f8e"
CHILD = r"""
import json,sys
from pathlib import Path
root=Path(sys.argv[1]);deps=Path(sys.argv[2]);manifest_path=Path(sys.argv[3])
sys.path[:0]=[str(root),str(deps)]
from connected_enterprise.upgrades import source_inventory
from connected_enterprise.finance import source_identity
from adaptive_enterprise.instruments import prepare_services
from commercial.ledger import load_jobs,digest
import commercial.ledger,connected_enterprise.finance,adaptive_enterprise.instruments
for m in (commercial.ledger,connected_enterprise.finance,adaptive_enterprise.instruments):
    assert Path(m.__file__).resolve().is_relative_to(root)
inventory=source_inventory(root)
result={'inventory_sha256':digest(inventory),'inventory_count':len(inventory),'finance_identity':source_identity(root)['sha256']}
if sys.argv[4]=='original':
    manifest=prepare_services(root,'p0-261-generated',cohort_seed=261)
    manifest_path.write_text(json.dumps(manifest,sort_keys=True))
    Path(sys.argv[5]).write_text(json.dumps(inventory,sort_keys=True))
else:
    manifest=json.loads(manifest_path.read_text())
try:
    jobs=load_jobs(root,manifest)
    result.update(accepted=True,ids=sorted(jobs),outcome_sha256=digest(jobs),manifest_sha256=digest(manifest))
except (FileNotFoundError,ValueError) as exc:
    result.update(accepted=False,error_type=type(exc).__name__,error=str(exc))
print(json.dumps(result,sort_keys=True))
"""

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def copy_bound(src,dst,name,expected):
    rel=Path(name)
    if not isinstance(name,str) or not name or rel.is_absolute() or '..' in rel.parts or rel.as_posix()!=name:
        raise ValueError('NONCANONICAL_BOUND_PATH')
    origin=src/rel
    if not origin.is_file() or any(p.is_symlink() for p in (origin,*origin.parents)):
        raise ValueError('NONREGULAR_BOUND_SOURCE')
    raw=origin.read_bytes()
    if sha(raw)!=expected:
        raise ValueError('ORIGINAL_BOUND_BYTES_CHANGED')
    target=dst/rel
    if any(p.is_symlink() for p in (target,*target.parents)):
        raise ValueError('NONREGULAR_STAGE')
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(raw)
    if sha(target.read_bytes())!=expected:
        raise ValueError('STAGED_BOUND_BYTES_CHANGED')

def main():
    owner,deps,out=map(lambda x:Path(x).resolve(),sys.argv[1:4])
    receipt={'owner_commit':OWNER,'probe_sha256':sha(Path(__file__).read_bytes()),'cases':{k:{'status':'NOT_RUN'} for k in CASES},'original_account_access':False,'native_migration':False,'commerce':False,'billing':None}
    started=time.monotonic()
    cpu0=resource.getrusage(resource.RUSAGE_CHILDREN)
    try:
        actual=subprocess.check_output(['git','-C',str(owner),'rev-parse','HEAD'],text=True).strip()
        if actual!=OWNER: raise ValueError('WRONG_OWNER_HEAD')
        with tempfile.TemporaryDirectory(prefix='p0-261-') as temp:
            base=Path(temp).resolve()
            stage=base/'stage';stage.mkdir()
            manifest_path=base/'manifest.json'; inventory_path=base/'inventory.json'
            def run(case,root):
                start=time.monotonic();before=resource.getrusage(resource.RUSAGE_CHILDREN)
                env={'PATH':os.defpath,'LANG':'C.UTF-8','HOME':str(base)}
                done=subprocess.run([sys.executable,'-I','-S','-B','-c',CHILD,str(root),str(deps),str(manifest_path),case,str(inventory_path)],cwd=base,env=env,capture_output=True,text=True)
                after=resource.getrusage(resource.RUSAGE_CHILDREN)
                row={'status':'FAIL','returncode':done.returncode,'wall_seconds':time.monotonic()-start,'waited_child_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime}
                receipt['cases'][case]=row
                if done.returncode:
                    row['diagnostic']=done.stderr[-2000:]
                    raise ValueError('UNEXPECTED_CHILD_FAILURE:'+case)
                result=json.loads(done.stdout)
                row['result']=result
                return result
            def require(case,ok):
                if not ok: raise ValueError('REGISTERED_CASE_FAILED:'+case)
                receipt['cases'][case]['status']='PASS'
            baseline=run('original',owner)
            require('original',baseline['accepted'] is True and bool(baseline['ids']))
            inv=json.loads(inventory_path.read_text())
            manifest=json.loads(manifest_path.read_text())
            assert sha(canonical(inv))==baseline['inventory_sha256']
            assert sha(canonical(manifest))==baseline['manifest_sha256']
            receipt['generated_job_count']=len(manifest['jobs'])
            for name,expected in inv.items(): copy_bound(owner,stage,name,expected)
            def identity(result):
                return all(result[k]==baseline[k] for k in ['inventory_sha256','inventory_count','finance_identity'])
            def missing(result):
                return identity(result) and result['accepted'] is False and result['error_type']=='FileNotFoundError'
            def same(result):
                return identity(result) and result['accepted'] is True and all(result[k]==baseline[k] for k in ['ids','outcome_sha256','manifest_sha256'])
            require('python_only',missing(run('python_only',stage)))
            bound={}
            for job in manifest['jobs']:
                for field in ('input','artifact','receipt'):
                    path,expected=job[field],job[field+'_sha256']
                    if path in bound and bound[path]!=expected: raise ValueError('CONFLICTING_BOUND_PATH')
                    bound[path]=expected
            for name,expected in bound.items(): copy_bound(owner,stage,name,expected)
            receipt['bound_data_count']=len(bound)
            receipt['bound_data_bytes']=sum((stage/name).stat().st_size for name in bound)
            receipt['bound_data_inventory_sha256']=sha(canonical(bound))
            require('complete_stage',same(run('complete_stage',stage)))
            first=min(manifest['jobs'],key=lambda j:j['id'])
            inp,rec=first['input'],first['receipt']
            (stage/inp).unlink()
            require('missing_input',missing(run('missing_input',stage)))
            copy_bound(owner,stage,inp,bound[inp])
            with (stage/rec).open('ab') as f:f.write(b' ')
            changed=run('changed_receipt',stage)
            require('changed_receipt',identity(changed) and changed['accepted'] is False and changed['error_type']=='ValueError' and changed['error']=='SOURCE_OR_ARTIFACT_CHANGED')
            copy_bound(owner,stage,rec,bound[rec])
            if any(sha((stage/name).read_bytes())!=expected for name,expected in {**inv,**bound}.items()): raise ValueError('RESTORE_INVENTORY_MISMATCH')
            expected_files=set(inv)|set(bound)
            actual_files={p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file()}
            if actual_files!=expected_files: raise ValueError('RESTORE_MEMBERSHIP_MISMATCH')
            require('restored',same(run('restored',stage)))
    except Exception as exc:
        receipt['failure']=type(exc).__name__+': '+str(exc)
    finally:
        after=resource.getrusage(resource.RUSAGE_CHILDREN)
        receipt['waited_child_cpu_seconds']=after.ru_utime+after.ru_stime-cpu0.ru_utime-cpu0.ru_stime
        receipt['wall_seconds']=time.monotonic()-started
        receipt['passed']=sum(row['status']=='PASS' for row in receipt['cases'].values())
        out.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    return 0 if receipt['passed']==len(CASES) and 'failure' not in receipt else 1

if __name__=='__main__':
    raise SystemExit(main())
