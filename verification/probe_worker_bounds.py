import argparse,hashlib,json,os,pathlib,signal,subprocess,sys,time

def probe(root,output):
    root=pathlib.Path(root).resolve();output=pathlib.Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    code="""import importlib.util,json,pathlib,resource,sys
s=importlib.util.spec_from_file_location('trusted_runner',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.limits()
r={'effective_limits':{name:resource.getrlimit(getattr(resource,name)) for name in ['RLIMIT_CPU','RLIMIT_AS','RLIMIT_FSIZE','RLIMIT_NOFILE']}}
try:bytearray(2*1024**3)
except MemoryError:r['memory_limit_enforced']=True
try:
 with open(sys.argv[2],'wb') as f:
  for i in range(20):f.write(b'x'*(1024**2))
except OSError as e:r['file_limit_enforced']=e.errno==27
files=[]
try:
 for i in range(200):files.append(open('/dev/null','rb'))
except OSError as e:r['fd_limit_enforced']=e.errno==24
for f in files:f.close()
print(json.dumps(r))
"""
    env={'PATH':os.defpath,'LANG':'C.UTF-8','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'}
    data=output/'file-limit.bin'
    child=subprocess.run([sys.executable,'-I','-c',code,str(root/'reproduce.py'),str(data)],capture_output=True,text=True,timeout=10,env=env)
    resource_record={'returncode':child.returncode,'stdout':child.stdout,'stderr':child.stderr,'runner_sha256':hashlib.sha256((root/'reproduce.py').read_bytes()).hexdigest(),'file_bytes_at_stop':data.stat().st_size if data.exists() else None}
    if child.returncode==0:resource_record.update(json.loads(child.stdout))
    if data.exists():data.unlink()
    (output/'resources.json').write_text(json.dumps(resource_record,indent=2)+'\n')
    interrupted=output/'interrupted-run'
    process=subprocess.Popen([sys.executable,'-I',str(root/'reproduce.py'),'--output',str(interrupted)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
    deadline=time.monotonic()+5
    while not (interrupted/'STARTED.json').exists() and process.poll() is None and time.monotonic()<deadline:time.sleep(.002)
    process.send_signal(signal.SIGINT)
    stdout,stderr=process.communicate(timeout=10)
    before={str(p.relative_to(interrupted)):hashlib.sha256(p.read_bytes()).hexdigest() for p in interrupted.rglob('*') if p.is_file()}
    restart=subprocess.run([sys.executable,'-I',str(root/'reproduce.py'),'--output',str(interrupted)],capture_output=True,text=True,timeout=10,env=env)
    after={str(p.relative_to(interrupted)):hashlib.sha256(p.read_bytes()).hexdigest() for p in interrupted.rglob('*') if p.is_file()}
    recovery={'interrupt_returncode':process.returncode,'interruption_record_exists':(interrupted/'INTERRUPTED.json').exists(),'complete_record_exists':(interrupted/'COMPLETE.json').exists(),'restart_returncode':restart.returncode,'partial_evidence_preserved':before==after,'stdout':stdout,'stderr':stderr,'restart_stderr':restart.stderr,'scope':'Actual SIGINT of reproduction parent after STARTED marker; same-directory restart must refuse without mutation. This does not test host power loss.'}
    (output/'interruption.json').write_text(json.dumps(recovery,indent=2)+'\n')
    return resource_record,recovery

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--output',required=True);a=p.parse_args();r,i=probe(a.root,a.output)
    checks={'resource_returncode':r['returncode'],'memory_limit_enforced':r.get('memory_limit_enforced'),'file_limit_enforced':r.get('file_limit_enforced'),'fd_limit_enforced':r.get('fd_limit_enforced'),'interrupt_record':i['interruption_record_exists'],'partial_preserved':i['partial_evidence_preserved'],'restart_refused':i['restart_returncode']!=0}
    print(json.dumps(checks))
    sys.exit(0 if r['returncode']==0 and all(checks[k] for k in checks if k!='resource_returncode') and not i['complete_record_exists'] else 1)
