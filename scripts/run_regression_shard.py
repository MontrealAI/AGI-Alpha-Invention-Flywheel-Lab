"""Run a complete deterministic partition of source-bound unittest modules."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

def main():
    p=argparse.ArgumentParser();p.add_argument('--pattern',required=True);p.add_argument('--index',required=True,type=int);p.add_argument('--count',required=True,type=int);p.add_argument('--receipt',required=True);p.add_argument('--isolate',action='append',default=[])
    a=p.parse_args()
    if a.pattern not in {'test_*.py','test_connected*.py'} or not 0<=a.index<a.count<=8:raise ValueError('DECLARED_COMPLETE_TEST_PARTITION_REQUIRED')
    root=Path(__file__).resolve().parents[1];files=sorted((root/'tests').glob(a.pattern))
    if len(a.isolate)!=len(set(a.isolate)) or len(a.isolate)>=a.count or any(n not in {f.name for f in files} for n in a.isolate):raise ValueError('EXACT_ISOLATED_MODULE_PARTITION_REQUIRED')
    isolated=[next(f for f in files if f.name==n) for n in a.isolate];others=[f for f in files if f not in isolated]
    selected=[isolated[a.index]] if a.index<len(isolated) else others[a.index-len(isolated)::a.count-len(isolated)]
    if not selected:raise ValueError('NONEMPTY_REGRESSION_SHARD_REQUIRED')
    out=Path(a.receipt).absolute();out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():raise FileExistsError('NEW_RESOURCE_RECEIPT_REQUIRED')
    inventory={f.relative_to(root).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    receipt={'schema':'agi-alpha/source-regression-shard/v1','source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'pattern':a.pattern,'index':a.index,'count':a.count,'all_modules':inventory,'selected_modules':[f.relative_to(root).as_posix() for f in selected],'isolated_modules':a.isolate,'partition':'Each declared expensive module owns one shard; remaining sorted modules partition modulo remaining shards. Every module appears exactly once. No test exclusion or early-success rule.','status':'STARTED'}
    out.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n');start=time.monotonic();before=resource.getrusage(resource.RUSAGE_CHILDREN)
    command=[sys.executable,'-m','unittest',*['tests.'+f.stem for f in selected],'-v']
    with out.with_suffix('.stdout').open('w') as stdout,out.with_suffix('.stderr').open('w') as stderr:
        completed=subprocess.run(command,cwd=root,stdout=stdout,stderr=stderr)
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt.update(status='FINISHED',exit_code=completed.returncode,command=command,wall_seconds=time.monotonic()-start,children_cpu_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,maximum_child_rss_KiB=after.ru_maxrss)
    out.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n');print(json.dumps({k:receipt[k] for k in ['source_commit','index','count','exit_code','wall_seconds','children_cpu_seconds']},sort_keys=True));return completed.returncode

if __name__=='__main__':raise SystemExit(main())
