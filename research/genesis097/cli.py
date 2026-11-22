"""Offline editable instrument interface. Never opens or drives hardware."""
import argparse,hashlib,json
from pathlib import Path
from .instrument import analyze,compile_design

def main():
 p=argparse.ArgumentParser();p.add_argument('operation',choices=('compile','analyze'));p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 raw=a.input.read_bytes();data=json.loads(raw)
 result=compile_design(data) if a.operation=='compile' else analyze(data)
 receipt={'operation':a.operation,'input_sha256':hashlib.sha256(raw).hexdigest(),
  'scope':'offline numerical analysis; caller-supplied bounds are not physical calibration',
  'hardware_actuated':False,'result':result}
 a.output.write_text(json.dumps(receipt,sort_keys=True,indent=2,allow_nan=False)+'\n')
if __name__=='__main__':main()
