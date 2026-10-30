import datetime,hashlib,json,os,pathlib,signal,subprocess,sys,time
base=pathlib.Path(__file__).resolve().parent
allocation=base.parent/'AGI-Alpha-Invention-Flywheel-Lab/campaign/connected-014/ALLOCATION.json'
if not allocation.exists():raise SystemExit('FRESH_ALLOCATION_REQUIRED')
root=(base/'extracted').resolve();command=[sys.executable,'-m','adaptive_enterprise','audit','--output',str(root)]
started=time.monotonic();utc=datetime.datetime.now(datetime.timezone.utc).isoformat();hz=os.sysconf('SC_CLK_TCK');page=os.sysconf('SC_PAGE_SIZE')
peak={'cpu_seconds':0.,'rss_bytes':0,'scratch_bytes':0};reason=None
with (base/'audit.stdout').open('w') as out,(base/'audit.stderr').open('w') as err:
 p=subprocess.Popen(command,cwd=root/'source',stdout=out,stderr=err,start_new_session=True,env={**os.environ,'TMPDIR':str(base)})
 while p.poll() is None:
  table={}
  for path in pathlib.Path('/proc').glob('[0-9]*/stat'):
   try:
    pid=int(path.parent.name);fields=path.read_text().rsplit(')',1)[1].split();table[pid]=(int(fields[1]),sum(int(fields[i]) for i in [11,12,13,14])/hz,int(fields[21])*page)
   except (OSError,ValueError,IndexError):pass
  ids={p.pid};old=set()
  while old!=ids:
   old=set(ids);ids.update(pid for pid,(parent,_,_) in table.items() if parent in ids)
  cpu=sum(table[pid][1] for pid in ids if pid in table);rss=sum(table[pid][2] for pid in ids if pid in table)
  size=sum(x.stat().st_size for x in base.rglob('*') if x.is_file())
  peak={k:max(peak[k],v) for k,v in {'cpu_seconds':cpu,'rss_bytes':rss,'scratch_bytes':size}.items()}
  receipt={'started_utc':utc,'command':command,'cwd':str(root/'source'),'pid':p.pid,'wall_seconds':time.monotonic()-started,'peak':peak,'allocation_sha256':hashlib.sha256(allocation.read_bytes()).hexdigest()}
  (base/'monitor.json').write_text(json.dumps(receipt,indent=2)+'\n')
  if cpu>=2400:reason='CPU_2400_SECONDS_BOUNDARY'
  elif rss>=500_000_000:reason='RSS_500MB_BOUNDARY'
  elif size>=500_000_000:reason='SCRATCH_500MB_BOUNDARY'
  elif time.monotonic()-started>=900:reason='WALL_15_MINUTES_BOUNDARY'
  if reason:
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=10)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
   break
  time.sleep(2)
 rc=p.wait()
receipt.update({'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'wall_seconds':time.monotonic()-started,'returncode':rc,'boundary':reason,'stdout_sha256':hashlib.sha256((base/'audit.stdout').read_bytes()).hexdigest(),'stderr_sha256':hashlib.sha256((base/'audit.stderr').read_bytes()).hexdigest()})
(base/'execution.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if rc or reason:raise SystemExit(1)
