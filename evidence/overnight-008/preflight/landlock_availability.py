import ctypes,datetime,errno,hashlib,json,os,pathlib,platform,sys,time
if platform.machine()!='x86_64': raise SystemExit('No known syscall map; refuse')
started=time.monotonic();libc=ctypes.CDLL(None,use_errno=True);libc.syscall.restype=ctypes.c_long
class Ruleset(ctypes.Structure): _fields_=[('handled_access_fs',ctypes.c_uint64)]
probes={}
for name,args in [('query_abi',(ctypes.c_long(444),ctypes.c_void_p(),ctypes.c_size_t(0),ctypes.c_uint(1))),('create_read_ruleset',(ctypes.c_long(444),ctypes.byref(Ruleset(4)),ctypes.c_size_t(ctypes.sizeof(Ruleset)),ctypes.c_uint(0)))]:
 ctypes.set_errno(0);value=libc.syscall(*args);error=ctypes.get_errno();probes[name]={'return':value,'errno':error,'error_name':errno.errorcode.get(error),'error_text':os.strerror(error)}
 if name=='create_read_ruleset' and value>=0: os.close(value)
status={line.split(':')[0]:line.split(':',1)[1].strip() for line in pathlib.Path('/proc/self/status').read_text().splitlines() if line.startswith(('NoNewPrivs:','Seccomp:','Seccomp_filters:'))}
headers=['/usr/include/x86_64-linux-gnu/asm/unistd_64.h','/usr/include/linux/landlock.h']
x={'schema':'agi-alpha-landlock-availability/v1','time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'kernel':platform.release(),'machine':platform.machine(),'python':sys.executable,'syscall_numbers':{'landlock_create_ruleset':444,'landlock_add_rule':445,'landlock_restrict_self':446},'header_sha256':{f:hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest() for f in headers},'probes':probes,'inherited_status':status,'available':probes['query_abi']['return']>=1,'qualified_for_untrusted_code':False,'wall_seconds':time.monotonic()-started,'execution_scope':'Trusted ABI-availability queries only. No untrusted code, baseline, privilege/credential change, new namespace or external access. Filesystem restriction was not installed. All effect/resource attack qualification is BLOCKED if ABI unavailable; no unrestricted fallback.'}
print(json.dumps(x,indent=2))
