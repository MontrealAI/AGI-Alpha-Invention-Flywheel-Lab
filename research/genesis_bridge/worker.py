"""Fixed trusted process; no arbitrary command/module or external actions."""
import hashlib,json,pathlib,resource,sys,time
sys.dont_write_bytecode=True
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]))
from research.genesis_bridge.core import read,validate_request,binding,verify_sources,digest
req=read(sys.argv[1]);validate_request(req)
lim=req['limits'];resource.setrlimit(resource.RLIMIT_CPU,(lim['cpu_seconds'],lim['cpu_seconds']))
resource.setrlimit(resource.RLIMIT_AS,(lim['memory_bytes'],lim['memory_bytes']))
from research.genesis097.instrument import analyze,compile_design
from research.genesis097.replay import replay_missing_sense
from research.genesis097.direct import analyze as direct
start=time.process_time();op=req['operation'];data=req['input']
if op=='compile':output=compile_design(data)
elif op in ('analyze','ordinary'):output=analyze(data)
elif op=='direct':output=direct(data)
elif op=='replay':output=replay_missing_sense(data['previous'],data['current'])
else:raise ValueError('not allowlisted')
r={'binding':binding(req),'output':output,'output_sha256':digest(output),'source_lock_sha256':verify_sources(),
   'python_version':sys.version,'python_executable_sha256':hashlib.sha256(pathlib.Path(sys.executable).read_bytes()).hexdigest(),
   'cpu_seconds':time.process_time()-start,'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
   'resource_scope':'adapter call CPU; Linux child lifetime high-water RSS in KiB; excludes startup CPU'}
print(json.dumps(r,sort_keys=True,allow_nan=False))
