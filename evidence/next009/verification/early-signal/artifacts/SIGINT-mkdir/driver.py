import os,signal,sys
from pathlib import Path
sys.path.insert(0, '/workspace/scratch/85dffc7b798c/lab')
from experiments import resource006_v3 as module
output=Path('/workspace/scratch/85dffc7b798c/lab/evidence/next009/verification/early-signal/artifacts/SIGINT-mkdir/run')
fired=False
original_mkdir=Path.mkdir
original_write=module._write
def mkdir(self,*args,**kwargs):
    global fired
    value=original_mkdir(self,*args,**kwargs)
    if self==output and 'mkdir'=='mkdir' and not fired:
        fired=True;os.kill(os.getpid(),2)
    return value
def write(path,value):
    global fired
    if path.name=='PENDING.json' and 'mkdir'=='pending_write' and not fired:
        fired=True;os.kill(os.getpid(),2)
    return original_write(path,value)
Path.mkdir=mkdir
module._write=write
result=module.run([sys.executable,'-c',"from pathlib import Path;Path('/workspace/scratch/85dffc7b798c/lab/evidence/next009/verification/early-signal/artifacts/SIGINT-mkdir/worker_launched').write_text('ran')"],output,Path('/workspace/scratch/85dffc7b798c/lab/evidence/next009/verification/early-signal/artifacts/SIGINT-mkdir/fixture-ledger.json'),'SIGINT-mkdir',dict(wall_seconds=2,cpu_seconds=2,memory_bytes=134217728,output_bytes=65536,storage_bytes=131072))
assert fired
assert result['receipt']['state']=='interrupted',result
assert result['receipt']['descendant_survivors'] is False,result
assert not Path('/workspace/scratch/85dffc7b798c/lab/evidence/next009/verification/early-signal/artifacts/SIGINT-mkdir/worker_launched').exists()
