import argparse, hashlib, json, os, signal, subprocess, sys, tempfile, time
from pathlib import Path

def main(root, output):
    output.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    wrapper = root/'experiments/resource006_v3.py'
    rows = []
    for signum, label in [(signal.SIGINT, 'SIGINT'), (signal.SIGTERM, 'SIGTERM')]:
        for point in ['mkdir', 'pending_write']:
            case = output/(label+'-'+point)
            case.mkdir()
            worker = case/'worker_launched'
            driver = '''import os,signal,sys
from pathlib import Path
sys.path.insert(0, %r)
from experiments import resource006_v3 as module
output=Path(%r)
fired=False
original_mkdir=Path.mkdir
original_write=module._write
def mkdir(self,*args,**kwargs):
    global fired
    value=original_mkdir(self,*args,**kwargs)
    if self==output and %r=='mkdir' and not fired:
        fired=True;os.kill(os.getpid(),%d)
    return value
def write(path,value):
    global fired
    if path.name=='PENDING.json' and %r=='pending_write' and not fired:
        fired=True;os.kill(os.getpid(),%d)
    return original_write(path,value)
Path.mkdir=mkdir
module._write=write
result=module.run([sys.executable,'-c',%r],output,Path(%r),%r,dict(wall_seconds=2,cpu_seconds=2,memory_bytes=134217728,output_bytes=65536,storage_bytes=131072))
assert fired
assert result['receipt']['state']=='interrupted',result
assert result['receipt']['descendant_survivors'] is False,result
assert not Path(%r).exists()
''' % (str(root),str(case/'run'),point,int(signum),point,int(signum),"from pathlib import Path;Path(%r).write_text('ran')"%str(worker),str(case/'fixture-ledger.json'),label+'-'+point,str(worker))
            driver_path = case/'driver.py'
            driver_path.write_text(driver)
            result = subprocess.run([sys.executable,str(driver_path)],capture_output=True,timeout=5)
            (case/'stdout.log').write_bytes(result.stdout)
            (case/'stderr.log').write_bytes(result.stderr)
            receipt_path=case/'run/RECEIPT.json'
            receipt=json.loads(receipt_path.read_text()) if receipt_path.exists() else None
            passed=result.returncode==0 and receipt is not None and receipt['state']=='interrupted' and receipt['descendant_survivors'] is False and not worker.exists()
            rows.append({'signal':label,'injection_point':point,'passed':passed,'exit_code':result.returncode,'receipt_sha256':hashlib.sha256(receipt_path.read_bytes()).hexdigest() if receipt else None})
    report={'schema':'agi-alpha/independent-early-signal-preflight009/v1','wrapper_sha256':hashlib.sha256(wrapper.read_bytes()).hexdigest(),'verifier_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'checks':rows,'passed':all(r['passed'] for r in rows),'wall_seconds':time.monotonic()-start,'scope':'Actual kernel signals during pre-worker initialization of inherited V3 wrapper; test-only injection fixes schedule without changing wrapper bytes. Does not repair or erase preserved frozen cycle001 failure. Shared host/model is procedural independence.'}
    (output/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    return 0 if report['passed'] else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(main(a.root.resolve(),a.output.resolve()))
