import datetime,json,os,pathlib,time
base=pathlib.Path(__file__).resolve().parent
parent=173021;hz=os.sysconf('SC_CLK_TCK');page=os.sysconf('SC_PAGE_SIZE');peak={'cpu_seconds':0.,'rss_bytes':0};samples=0
while not (base/'execution.json').exists():
 table={}
 for path in pathlib.Path('/proc').glob('[0-9]*/stat'):
  try:
   fields=path.read_text().rsplit(')',1)[1].split();table[int(path.parent.name)]=(int(fields[1]),sum(int(fields[i]) for i in [11,12,13,14])/hz,int(fields[21])*page)
  except (OSError,ValueError,IndexError):pass
 ids={parent};old=set()
 while old!=ids:
  old=set(ids);ids.update(pid for pid,(p,_,_) in table.items() if p in ids)
 cpu=sum(table[p][1] for p in ids if p in table);rss=sum(table[p][2] for p in ids if p in table)
 peak={'cpu_seconds':max(peak['cpu_seconds'],cpu),'rss_bytes':max(peak['rss_bytes'],rss)};samples+=1
 r={'schema':'agi-alpha/global-proc-resource-monitor/v1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'host_pid':parent,'peak':peak,'samples':samples,'namespace_note':'Initial watchdog used namespace-local PID against host /proc. This supplementary monitor resolves the host PID by exact frozen audit command line. Wall and scratch enforcement in initial watchdog remain accurate.'}
 (base/'proc-monitor.json').write_text(json.dumps(r,indent=2)+'\n')
 if cpu>2400 or rss>500_000_000:(base/'RESOURCE_BOUNDARY_OBSERVED.json').write_text(json.dumps(r)+'\n')
 time.sleep(2)
print(json.dumps(r))
