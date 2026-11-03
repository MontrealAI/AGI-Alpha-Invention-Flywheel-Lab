"""Run the retained conventional network constructor only after caller funding."""
import json, shutil, subprocess, sys, tempfile
from pathlib import Path

def construct(root, request, output):
    root=Path(root); output=Path(output)
    if output.exists(): raise ValueError('FRESH_OUTPUT_REQUIRED')
    # Original constructor accepts a folder containing 01.json. The fresh
    # request input is copied, never a historical answer or prebuilt artifact.
    with tempfile.TemporaryDirectory(prefix='industrial064-request-') as td:
        folder=Path(td); shutil.copyfile(root/request['input_path'],folder/'01.json')
        code='from industrial062.construct import construct; from pathlib import Path; construct(Path(__import__("sys").argv[1]),Path(__import__("sys").argv[2]),120,0.10)'
        proc=subprocess.run([sys.executable,'-c',code,str(folder),str(output)],cwd=root,capture_output=True,text=True,timeout=155)
        if proc.returncode: raise RuntimeError('PRODUCER_FAILED:'+proc.stderr[-2000:])
    receipt=json.loads((output/'production.json').read_text())
    if not (output/'solution.json').exists(): raise ValueError('NO_ACCEPTABLE_PLAN:'+receipt['status'])
    return json.loads((output/'solution.json').read_text()),receipt
