"""Fresh independent acceptance subprocess; never imports producer into checker."""
import json,pathlib,resource,sys,time
sys.dont_write_bytecode=True
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]))
resource.setrlimit(resource.RLIMIT_CPU,(5,5));resource.setrlimit(resource.RLIMIT_AS,(268435456,268435456))
from research.genesis_bridge.core import _accept_local,verify_sources
verify_sources();data=json.loads(sys.stdin.buffer.read(2000000));start=time.process_time()
try:
 a=_accept_local(data['request'],data['execution'],data['fixture'])
 print(json.dumps({'acceptance':a,'cpu_seconds':time.process_time()-start,'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},allow_nan=False))
except (ValueError,AssertionError,KeyError,TypeError) as e:
 print(json.dumps({'error':str(e),'error_type':type(e).__name__}))
