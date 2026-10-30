import datetime,hashlib,json,os,resource,signal,subprocess,sys,time
from pathlib import Path
root=Path('/workspace/scratch/b156b0353186/agi-alpha');out=root.parent/'completion015-confirmation';logs=root.parent/'operation015-watch';records=[];ticks=os.sysconf('SC_CLK_TCK');deadline=datetime.datetime.fromisoformat('2026-10-30T20:25:00+00:00').timestamp()

def write(value):
 p=logs/'RESOURCE.json';q=p.with_suffix('.tmp');q.write_text(json.dumps(value,indent=2)+'\n');q.replace(p)

def phase(name,args,cwd,cpu_cap,wall_cap):
 start=time.monotonic();cpu0=resource.getrusage(resource.RUSAGE_CHILDREN);peak=0.;reason=None
 with (logs/(name+'.stdout')).open('w') as stdout,(logs/(name+'.stderr')).open('w') as stderr:
  p=subprocess.Popen(args,cwd=cwd,stdout=stdout,stderr=stderr,start_new_session=True)
  try:
   while p.poll() is None:
    current=0.
    for d in Path('/proc').iterdir():
     if not d.name.isdigit():continue
     try:
      f=(d/'stat').read_text().rsplit(')',1)[1].split()
      if int(f[2])==p.pid:current+=sum(int(f[i]) for i in [11,12,13,14])/ticks
     except (OSError,ValueError,IndexError):pass
    peak=max(peak,current);wall=time.monotonic()-start
    write({'completed':records,'active':name,'observed_active_cpu_seconds':peak,'active_wall_seconds':wall,'cpu_cap':cpu_cap,'wall_cap':wall_cap,'actual_billing':'UNKNOWN_NOT_ZERO'})
    if peak>=cpu_cap:reason='REGISTERED_PHASE_CPU_BOUNDARY'
    if wall>=wall_cap or time.time()>=deadline:reason='REGISTERED_PHASE_WALL_OR_ABSOLUTE_BOUNDARY'
    if reason:break
    time.sleep(.5)
  finally:
   if p.poll() is None:
    os.killpg(p.pid,signal.SIGTERM)
    try:p.wait(timeout=3)
    except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
   usage=resource.getrusage(resource.RUSAGE_CHILDREN);exact=usage.ru_utime+usage.ru_stime-cpu0.ru_utime-cpu0.ru_stime
   row={'phase':name,'command':args,'returncode':p.returncode,'reason':reason,'wall_seconds':time.monotonic()-start,'children_cpu_seconds':exact,'observed_cpu_lower_bound':peak,'cpu_cap':cpu_cap,'scope':'Original registered accounts; no reseed, direct record edit or copied balances.'};records.append(row);write({'completed':records,'accepted':all(x['returncode']==0 and x['reason'] is None for x in records),'actual_billing':'UNKNOWN_NOT_ZERO'});print(json.dumps(row),flush=True)
 if p.returncode or reason:raise SystemExit(124 if reason else p.returncode)

phase('01-fresh-run',[sys.executable,'-m','connected_enterprise','run','--output',str(out)],root,600,600)
phase('02-independent-audit',[sys.executable,'-m','connected_enterprise','audit','--output',str(out)],out/'source',70,180)
phase('03-public-package',[sys.executable,'-m','connected_enterprise','package','--output',str(out),'--archive',str(root.parent/'completion015-public.zip')],out/'source',70,180)
