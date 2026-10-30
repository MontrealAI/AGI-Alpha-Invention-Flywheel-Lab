from pathlib import Path
import subprocess,time,json,resource,hashlib
root=Path(__file__).parent
python='/workspace/scratch/92d546ab6009/dependency-probe-venv/bin/python'
tests=['-m','pytest','-q','source/app_b','source/tutorial002.py','source/tutorial003.py']
steps=[('baseline_tests',tests),('upgrade_httpx',['-m','pip','install','httpx==0.28.1']),('direct_upgrade_tests',tests),('official_route',['-m','pip','install','fastapi==0.110.1','httpx==0.28.1']),('official_route_tests',tests)]
receipts=[]
for name,args in steps:
 start=time.perf_counter(); before=resource.getrusage(resource.RUSAGE_CHILDREN)
 p=subprocess.run([python,*args],cwd=root,text=True,capture_output=True,timeout=120)
 after=resource.getrusage(resource.RUSAGE_CHILDREN)
 out=p.stdout+p.stderr; (root/'receipts'/f'{name}.log').write_text(out)
 freeze=subprocess.run([python,'-m','pip','freeze'],text=True,capture_output=True,timeout=30).stdout
 receipt={'step':name,'command':[python,*args],'returncode':p.returncode,'wall_seconds':time.perf_counter()-start,'child_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'output_sha256':hashlib.sha256(out.encode()).hexdigest(),'freeze':freeze.splitlines()}
 receipts.append(receipt); (root/'probe_receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
 print(json.dumps({k:receipt[k] for k in ['step','returncode','wall_seconds','child_cpu_seconds']}),flush=True)
