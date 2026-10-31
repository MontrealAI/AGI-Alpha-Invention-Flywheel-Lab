"""Bounded local verification controller. Not part of the candidate runtime."""
import argparse, ctypes, datetime, fcntl, json, os, pathlib, resource, signal, stat, subprocess, sys, time, uuid

ROOT = pathlib.Path('/workspace/scratch/8ae627a67fcf')
CONTROL = ROOT / 'verification021-control'
STATE = CONTROL / 'resources.json'
LOCK = CONTROL / 'resources.lock'
HZ, PAGE = os.sysconf('SC_CLK_TCK'), os.sysconf('SC_PAGE_SIZE')
DEADLINE = datetime.datetime.fromisoformat('2026-10-31T01:51:04+00:00').timestamp()

def atomic(path, obj):
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(obj, indent=2) + '\n')
    os.replace(temp, path)

def transaction(fn):
    with LOCK.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(STATE.read_text())
        value = fn(state)
        atomic(STATE, state)
        return value

def files():
    result = {}
    pending=[str(ROOT)];prefix=len(str(ROOT))+1
    while pending:
        directory=pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():continue
                        if entry.is_dir(follow_symlinks=False):pending.append(entry.path)
                        else:
                            value=entry.stat(follow_symlinks=False)
                            if stat.S_ISREG(value.st_mode):result[entry.path[prefix:]]=value.st_size
                    except OSError:pass
        except OSError:pass
    return result

def group_usage(pgid):
    cpu, rss, pids = 0., 0, []
    for p in pathlib.Path('/proc').iterdir():
        if not p.name.isdigit(): continue
        try:
            raw = (p/'stat').read_text(); f = raw[raw.rfind(')')+2:].split()
            if int(f[2]) != pgid: continue
            cpu += sum(int(f[i]) for i in (11,12,13,14)) / HZ
            rss += int(f[21]) * PAGE
            pids.append(int(p.name))
        except (OSError, ValueError, IndexError): pass
    return cpu, rss, pids

def main():
    a = argparse.ArgumentParser(); a.add_argument('--init', action='store_true')
    a.add_argument('--name'); a.add_argument('--cwd', default=str(ROOT))
    a.add_argument('--cpu-stop', type=float, default=145.)
    a.add_argument('--wall-stop', type=float, default=295.)
    a.add_argument('--expected-stop', action='store_true')
    a.add_argument('command', nargs=argparse.REMAINDER); args=a.parse_args()
    CONTROL.mkdir(exist_ok=True)
    if args.init:
        if STATE.exists(): raise SystemExit('REFUSE_RESOURCE_RESET')
        baseline=files(); atomic(CONTROL/'disk-baseline.json',baseline)
        atomic(STATE, {'schema':'native021-verification-resources/v1',
            'accepted_utc':'2026-10-31T01:21:04Z','deadline_utc':'2026-10-31T01:51:04Z',
            'limits':{'total_cpu_seconds':600,'per_job_cpu_seconds':150,'per_job_wall_seconds':300,
                      'aggregate_memory_bytes':2*1024**3,'new_disk_bytes':256*1024**2,
                      'concurrent_jobs':2,'retrieval_bytes':16*1024**2},
            'setup_and_publication_cpu_allowance':30.,'charged_cpu_seconds':30.,
            'allowance_note':'Conservative allowance covers unmetered setup, read-only metadata, Git publication, shells and final receipt preparation; every experiment is additionally metered.',
            'retrieval_bytes':0,'max_new_disk_bytes':0,'max_aggregate_rss_bytes':0,
            'max_concurrent_jobs':0,'jobs':[],'active':{},'hosted_ci':0,'external_spending':0})
        print('initialized separate verification allocation');return
    assert args.name and args.command and args.cpu_stop <=145 and args.wall_stop<=295
    command=args.command[1:] if args.command[0]=='--' else args.command
    slot=None
    for i in range(2):
        f=(CONTROL/('slot-'+str(i))).open('a')
        try: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);slot=f;break
        except BlockingIOError: f.close()
    if slot is None: raise SystemExit('TWO_JOB_LIMIT')
    job=uuid.uuid4().hex; start=time.monotonic(); before=resource.getrusage(resource.RUSAGE_CHILDREN)
    def reserve(s):
        if time.time()>=DEADLINE or s['charged_cpu_seconds']+sum(x['cpu'] for x in s['active'].values())>=590:
            raise RuntimeError('ALLOCATION_EXHAUSTED')
        s['active'][job]={'name':args.name,'cpu':0.,'rss':0}
        s['max_concurrent_jobs']=max(s['max_concurrent_jobs'],len(s['active']))
    transaction(reserve)
    if ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)!=0:raise RuntimeError('SUBREAPER_FAILED')
    capture=CONTROL/(job+'.host.json')
    def prepare():
        resource.setrlimit(resource.RLIMIT_CPU,(150,150))
        resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
        resource.setrlimit(resource.RLIMIT_FSIZE,(256*1024**2,256*1024**2))
        raw=pathlib.Path('/proc/self/stat').read_text();f=raw[raw.rfind(')')+2:].split()
        capture.write_text(json.dumps({'pid':int(raw.split(' ',1)[0]),'pgid':int(f[2])}))
    log=CONTROL/(args.name+'.log')
    baseline=json.loads((CONTROL/'disk-baseline.json').read_text())
    reason=None;peak_cpu=0.;peak_rss=0;peak_count=0;last_disk=0.;growth=0;host=None
    env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1';env['TMPDIR']=str(CONTROL/'tmp')
    (CONTROL/'tmp').mkdir(exist_ok=True)
    with log.open('wb') as output:
        child=subprocess.Popen(command,cwd=args.cwd,stdout=output,stderr=subprocess.STDOUT,
                               env=env,start_new_session=True,preexec_fn=prepare)
        host=json.loads(capture.read_text())
        while True:
            cpu,rss,pids=group_usage(host['pgid']); own=time.process_time()
            rss += resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
            live=cpu+own+.2;peak_cpu=max(peak_cpu,live);peak_rss=max(peak_rss,rss);peak_count=max(peak_count,len(pids))
            elapsed=time.monotonic()-start
            if elapsed-last_disk>=2 or last_disk==0:
                current=files();growth=sum(max(0,size-baseline.get(name,0)) for name,size in current.items());last_disk=elapsed
            def update(s):
                s['active'][job].update(cpu=live,rss=rss)
                total=s['charged_cpu_seconds']+sum(x['cpu'] for x in s['active'].values())
                memory=sum(x['rss'] for x in s['active'].values())
                s['max_new_disk_bytes']=max(s['max_new_disk_bytes'],growth)
                s['max_aggregate_rss_bytes']=max(s['max_aggregate_rss_bytes'],memory)
                return total,memory
            total,memory=transaction(update)
            if live>=args.cpu_stop: reason='CPU_GUARD'
            elif elapsed>=args.wall_stop: reason='WALL_GUARD'
            elif time.time()>=DEADLINE-5: reason='ALLOCATION_WALL_GUARD'
            elif total>=590: reason='TOTAL_CPU_GUARD'
            elif memory>=2*1024**3: reason='MEMORY_GUARD'
            elif growth>=256*1024**2: reason='DISK_GUARD'
            if reason:
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                break
            if child.poll() is not None:break
            time.sleep(.1)
        code=child.wait()
        # Reap every adopted descendant after a process-group termination.
        drain=time.monotonic()+3
        while True:
            try: pid,status,usage=os.wait4(-1,os.WNOHANG)
            except ChildProcessError:break
            if pid==0:
                if time.monotonic()>=drain:reason=reason or 'UNREAPED_DESCENDANT';break
                time.sleep(.02)
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    child_cpu=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime
    current=files();growth=sum(max(0,size-baseline.get(name,0)) for name,size in current.items())
    controller_cpu=time.process_time()
    cpu=child_cpu+controller_cpu+.2
    receipt={'schema':'native021-local-job/v1','name':args.name,'job_id':job,'command':command,
             'cwd':args.cwd,'host_process_group':host,'exit_code':code,'stop_reason':reason,
             'expected_control_stop':args.expected_stop,'accepted':(reason=='CPU_GUARD') if args.expected_stop else (code==0 and reason is None),
             'child_and_waited_descendant_cpu_seconds':child_cpu,'controller_cpu_seconds':controller_cpu,
             'shell_cpu_allowance_seconds':.2,'charged_cpu_seconds':cpu,'peak_live_cpu_seconds':peak_cpu,
             'wall_seconds':time.monotonic()-start,'peak_rss_including_controller_bytes':peak_rss,
             'peak_observed_processes':peak_count,'new_disk_bytes_at_finish':growth,
             'per_job_limit_cpu_seconds':150,'per_job_limit_wall_seconds':300,
             'monitor_cpu_stop_seconds':args.cpu_stop,'monitor_wall_stop_seconds':args.wall_stop,
             'within_hard_limits':cpu<=150 and time.monotonic()-start<=300,
             'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    atomic(CONTROL/(args.name+'.receipt.json'),receipt)
    def finish(s):
        s['active'].pop(job);s['charged_cpu_seconds']+=cpu;s['jobs'].append(receipt)
        s['max_new_disk_bytes']=max(s['max_new_disk_bytes'],growth)
    transaction(finish)
    capture.unlink(missing_ok=True)
    print(json.dumps(receipt,sort_keys=True))
    raise SystemExit(0 if receipt['accepted'] and receipt['within_hard_limits'] else 1)

if __name__=='__main__':main()
