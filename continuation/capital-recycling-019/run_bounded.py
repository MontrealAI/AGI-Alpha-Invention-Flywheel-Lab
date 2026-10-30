import argparse, datetime, fcntl, json, os, resource, signal, subprocess, time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--name', required=True)
p.add_argument('--cwd', required=True)
p.add_argument('command', nargs=argparse.REMAINDER)
a = p.parse_args()
root = Path(__file__).resolve().parent
lock = (root / 'job.lock').open('a')
try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError: raise SystemExit('CONCURRENT_JOB_REFUSED_BEFORE_LAUNCH')
allocation = json.loads((root / 'ALLOCATION.json').read_text())
records = root / 'RESOURCES.jsonl'
prior = [json.loads(s) for s in records.read_text().splitlines()] if records.exists() else []
used = sum(r['cpu_seconds'] for r in prior)
budget = allocation['limits']
cycle_start = datetime.datetime.fromisoformat(allocation['registered_utc'].replace('Z', '+00:00')).timestamp()
remaining_wall = budget['wall_seconds_total'] - (time.time() - cycle_start)
if remaining_wall < 1: raise SystemExit('CYCLE_WALL_EXHAUSTED')
if used >= budget['cpu_seconds_total'] or any(not r['within_limits'] for r in prior):
    raise SystemExit('CYCLE_STOPPED: budget or prior failed envelope')
cpu = min(budget['cpu_seconds_per_job'], int(budget['cpu_seconds_total'] - used))
if cpu < 1: raise SystemExit('NO_CPU_REMAINDER')
out = root / (a.name + '.log')
if out.exists(): raise SystemExit('NEW_JOB_NAME_REQUIRED')
processor = min(os.sched_getaffinity(0))
def limits():
    os.setsid()
    os.sched_setaffinity(0, {processor})
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    resource.setrlimit(resource.RLIMIT_AS, (budget['memory_bytes'], budget['memory_bytes']))
    resource.setrlimit(resource.RLIMIT_FSIZE, (budget['added_disk_bytes'], budget['added_disk_bytes']))
started = time.time()
group_peak_rss = group_peak_processes = 0
stop_reason = None
before = resource.getrusage(resource.RUSAGE_CHILDREN)
with out.open('xb') as stream:
    proc = subprocess.Popen(a.command, cwd=a.cwd, stdout=stream, stderr=subprocess.STDOUT, preexec_fn=limits)
    try:
        while proc.poll() is None:
            rss = processes = 0
            for path in Path('/proc').iterdir():
                if not path.name.isdecimal(): continue
                try:
                    fields = (path / 'stat').read_text().rsplit(')', 1)[1].split()
                    if int(fields[2]) == proc.pid:
                        rss += int(fields[21]) * os.sysconf('SC_PAGE_SIZE')
                        processes += 1
                except (FileNotFoundError, ProcessLookupError, PermissionError): pass
            group_peak_rss = max(group_peak_rss, rss)
            group_peak_processes = max(group_peak_processes, processes)
            if rss > budget['memory_bytes']: stop_reason = 'GROUP_MEMORY_LIMIT'
            if time.time() - started >= min(cpu, budget['wall_seconds_per_job'], remaining_wall): stop_reason = 'JOB_WALL_LIMIT'
            if stop_reason:
                os.killpg(proc.pid, signal.SIGKILL)
                break
            try: proc.wait(timeout=.05)
            except subprocess.TimeoutExpired: pass
        code = proc.wait()
    finally:
        try: os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError: pass
after = resource.getrusage(resource.RUSAGE_CHILDREN)
elapsed = time.time() - started
measured_cpu = after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime
disk = sum(x.stat().st_size for x in root.parent.rglob('*') if x.is_file())
record = {'job': a.name, 'command': a.command, 'cwd': a.cwd, 'exit_code': code,
          'started_utc': datetime.datetime.fromtimestamp(started, datetime.timezone.utc).isoformat(),
          'cpu_seconds': measured_cpu, 'cumulative_cpu_seconds': used + measured_cpu,
          'wall_seconds': elapsed, 'peak_child_rss_kib': after.ru_maxrss,
          'sampled_peak_group_rss_bytes': group_peak_rss, 'peak_group_processes': group_peak_processes, 'stop_reason': stop_reason,
          'workspace_file_bytes': disk, 'one_processor': processor,
          'within_limits': stop_reason is None and measured_cpu <= cpu and used + measured_cpu <= budget['cpu_seconds_total'] and elapsed <= cpu + .25 and disk <= budget['added_disk_bytes']}
with records.open('a') as stream: stream.write(json.dumps(record, sort_keys=True) + '\n')
print(json.dumps(record, sort_keys=True))
print(out.read_text()[-22000:])
raise SystemExit(code if record['within_limits'] else 125)
