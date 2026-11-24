"""Development only: mediate the owner's historical -c launch shape without changing historical source."""
import hashlib
import json
import os
from pathlib import Path
import py_compile
import resource
import shlex
import subprocess
import sys
import tempfile
import time

OWNER = 'ced6c1cb004887dcdafaea59a2976020be649f8e'
OWNER_BLOB = '9866d004c412fc05c9f6292cf898307f177359df'
LEAF = "import sample,sys,json; print(json.dumps({'value':sample.VALUE,'isolated':sys.flags.isolated,'no_site':sys.flags.no_site,'no_write':sys.dont_write_bytecode,'prefix':bool(sys.pycache_prefix)}))"
PARENT = """import os,sys,json,subprocess
from pathlib import Path
p=json.load(sys.stdin);root=Path(p['child']);code=p['code'];payload={}
env = {**os.environ, 'PYTHONPATH': str(root), 'PYTHONDONTWRITEBYTECODE': '1'}
done = subprocess.run([sys.executable, '-c', code], input=json.dumps(payload),
                          text=True, capture_output=True, cwd=root, env=env, timeout=60)
print(json.dumps({'exit':done.returncode,'output':done.stdout,'reason':done.stderr.strip()}))
"""
BOOT = '''import hashlib,json,os,sys,tempfile
from pathlib import Path
base=Path(__file__).parent
policy=json.loads((base/'policy.json').read_text())
root=Path.cwd()
def digest(b):return hashlib.sha256(b).hexdigest()
def fail(code):raise SystemExit(code)
def inventory():
 result={}
 for p in sorted(root.rglob('*.py')):
  if p.is_symlink() or any(q.is_symlink() for q in p.parents):fail('SYMLINK')
  result[p.relative_to(root).as_posix()]=digest(p.read_bytes())
 return result
if str(root) not in policy['roots'] or os.environ.get('PYTHONPATH')!=str(root):fail('ROOT_NOT_AUTHORIZED')
if len(sys.argv)!=3 or sys.argv[1]!='-c' or digest(sys.argv[2].encode()) not in policy['codes']:fail('CALL_NOT_AUTHORIZED')
if inventory()!=policy['roots'][str(root)]:fail('SOURCE_CHANGED')
if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and sys.pycache_prefix):fail('LAUNCH_POLICY_MISMATCH')
sys.path.insert(0,str(root))
sys.executable=str(base/'launch')
code=sys.argv[2];sys.argv=['-c']
with (base/'launches.jsonl').open('a') as log:log.write(json.dumps({'root':root.name,'code':digest(code.encode()),'isolated':sys.flags.isolated,'no_site':sys.flags.no_site,'no_write':sys.dont_write_bytecode,'prefix_empty':not any(Path(sys.pycache_prefix).iterdir())})+'\\n')
exec(compile(code,'<registered-call>','exec'),{'__name__':'__main__'})
if inventory()!=policy['roots'][str(root)]:fail('SOURCE_CHANGED_DURING_EXECUTION')
'''

def sha(b): return hashlib.sha256(b).hexdigest()

def run():
    start=time.monotonic(); before=resource.getrusage(resource.RUSAGE_CHILDREN)
    with tempfile.TemporaryDirectory(prefix='p0266-') as temp:
        base=Path(temp); parent=base/'parent'; child=base/'child'; other=base/'other'
        for p in (parent,child,other):p.mkdir()
        sample=child/'sample.py'; sample.write_text("VALUE='OLD'\n")
        stamp=sample.stat();py_compile.compile(str(sample),doraise=True,invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
        sample.write_text("VALUE='NEW'\n");os.utime(sample,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
        (base/'bootstrap.py').write_text(BOOT)
        policy={'roots':{str(parent):{},str(child):{'sample.py':sha(sample.read_bytes())}},'codes':[sha(x.encode()) for x in (PARENT,LEAF)]}
        (base/'policy.json').write_text(json.dumps(policy,sort_keys=True))
        launch=base/'launch'
        launch.write_text('#!/bin/sh\nset -eu\np=$(mktemp -d '+shlex.quote(str(base/'cache.XXXXXX'))+')\ntrap \'rm -rf "$p"\' EXIT\n'+shlex.quote(str(Path(sys.executable).resolve()))+' -I -S -B -X "pycache_prefix=$p" '+shlex.quote(str(base/'bootstrap.py'))+' "$@"\n')
        launch.chmod(0o700)
        def call(exe,root,code,payload,extra=None):
            env={**os.environ,'PYTHONPATH':str(root),'PYTHONDONTWRITEBYTECODE':'1'}
            if extra:env.update(extra)
            return subprocess.run([str(exe),'-c',code],input=json.dumps(payload),text=True,capture_output=True,cwd=root,env=env,timeout=60)
        def nested(exe,root=child,code=LEAF,extra=None):
            done=call(exe,parent,PARENT,{'child':str(root),'code':code},extra)
            if done.returncode:raise RuntimeError('PARENT_FAILED:'+done.stderr.strip())
            return json.loads(done.stdout)
        def value(row):return json.loads(row['output']) if row['exit']==0 else None
        ordinary=nested(sys.executable)
        first=nested(launch);second=nested(launch)
        injected=nested(launch,extra={'PYTHONHOME':'/nonexistent','PYTHONPYCACHEPREFIX':str(other),'PYTHONUSERBASE':str(other)})
        forbidden_root=nested(launch,root=other)
        forbidden_call=nested(launch,code='print(123)')
        original=sample.read_bytes();sample.write_bytes(original+b'\n')
        changed=nested(launch);sample.write_bytes(original)
        restored=nested(launch)
        receipts=[json.loads(x) for x in (base/'launches.jsonl').read_text().splitlines()]
        def guarded(row):
            v=value(row);return v=={'value':'NEW','isolated':1,'no_site':1,'no_write':True,'prefix':True}
        checks={'ordinary_reads_stale':value(ordinary)['value']=='OLD','recursive_policy_first':guarded(first),'recursive_policy_second':guarded(second),'python_startup_env_ignored':guarded(injected),'unauthorized_root_rejected':forbidden_root['exit']!=0 and forbidden_root['reason']=='ROOT_NOT_AUTHORIZED','unregistered_call_rejected':forbidden_call['exit']!=0 and forbidden_call['reason']=='CALL_NOT_AUTHORIZED','source_mutation_rejected':changed['exit']!=0 and changed['reason']=='SOURCE_CHANGED','restoration_parity':guarded(restored),'all_mediated_launch_receipts':len(receipts)==11 and all(r['isolated']==1 and r['no_site']==1 and r['no_write'] and r['prefix_empty'] for r in receipts)}
        result={'scope':'synthetic historical launch shape, not native qualification','owner_commit':OWNER,'owner_blob':OWNER_BLOB,'checks':checks,'accepted':all(checks.values()),'ordinary':value(ordinary),'mediated':value(first),'receipt_count':len(receipts),'receipts':receipts,'actual_billing_usd':None,'probe_sha256':sha(Path(__file__).read_bytes())}
    after=resource.getrusage(resource.RUSAGE_CHILDREN);result['waited_child_cpu_seconds']=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime;result['wall_seconds']=time.monotonic()-start
    print(json.dumps(result,sort_keys=True));return 0 if result['accepted'] else 1

if __name__=='__main__':raise SystemExit(run())
