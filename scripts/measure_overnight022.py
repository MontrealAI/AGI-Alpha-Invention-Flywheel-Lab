"""Record local command resources including reaped child processes."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import subprocess
import time


def main():
    p=argparse.ArgumentParser();p.add_argument('--receipt',required=True);p.add_argument('command',nargs=argparse.REMAINDER)
    a=p.parse_args();command=a.command[1:] if a.command[:1]==['--'] else a.command
    if not command:p.error('command required')
    path=Path(a.receipt).resolve();path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise FileExistsError('NEW_RESOURCE_RECEIPT_REQUIRED')
    started=datetime.now(timezone.utc).isoformat();wall=time.monotonic()
    path.with_suffix('.started.json').write_text(json.dumps({'command':command,'started_utc':started,'status':'STARTED_FINAL_RECEIPT_REQUIRED'},sort_keys=True)+'\n')
    before=resource.getrusage(resource.RUSAGE_CHILDREN)
    with path.with_suffix('.stdout').open('w') as out,path.with_suffix('.stderr').open('w') as err:
        completed=subprocess.run(command,stdout=out,stderr=err)
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt={'schema':'agi-alpha/overnight022-command-resource/v1','command':command,'started_utc':started,'finished_utc':datetime.now(timezone.utc).isoformat(),'exit_code':completed.returncode,'wall_seconds':time.monotonic()-wall,'children_user_cpu_seconds':after.ru_utime-before.ru_utime,'children_system_cpu_seconds':after.ru_stime-before.ru_stime,'total_measured_command_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'maximum_child_rss_KiB':after.ru_maxrss,'scope':'Reaped local command and descendants; excludes assistant inference, tool transport, external CI, preceding clone/review and unmeasured host billing. Maximum RSS is a kernel high-water mark, not concurrent aggregate memory. No allocation or quota is created by this receipt.'}
    path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps(receipt,sort_keys=True));return completed.returncode


if __name__=='__main__':raise SystemExit(main())
