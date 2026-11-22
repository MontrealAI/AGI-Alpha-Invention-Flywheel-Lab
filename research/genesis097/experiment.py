import argparse,hashlib,itertools,json,time
from pathlib import Path
from .instrument import analyze,compile_design
from .forward import make_case
from .check import check_result

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--development',action='store_true');a=p.parse_args()
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('x') as receipt:
  receipt.write(json.dumps({'status':'started','development':a.development})+'\n')
 design=compile_design(json.loads(Path('campaign/genesis097/DESIGN_INPUT.json').read_text()))
 arms=['genesis_composition','conventional_kelvin']
 from .direct import analyze as direct
 arms.append('independent_direct_agent')
 rows=[];start=time.monotonic()
 for ti,truth in enumerate(('none','contact','sample','both')):
  for fi,family in enumerate(('noise','geometry','channels')):
   for rep in range(12):
    seed=(970000 if a.development else 980000)+ti*1000+fi*100+rep
    case=make_case(truth,family,rep,seed,design['currents_A'])
    # Only raw observations and calibration reach the estimator.
    for arm in arms:
     pred=(direct if arm=='independent_direct_agent' else analyze)(case['observation'])
     rows.append({'arm':arm,'case':case,'prediction':pred})
 result={'schema':'genesis097-numerical/v1','scope':'numerical measurement benchmark, not tomography or physical/customer qualification',
  'development':a.development,'arms':arms,'rows':rows,'design':design,'elapsed_seconds':time.monotonic()-start,
  'input_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path('campaign/genesis097/DESIGN_INPUT.json'),Path('campaign/genesis097/PROTOCOL.md'))},
  'source_sha256':{x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in sorted(Path('research/genesis097').glob('*.py'))}}
 a.output.parent.mkdir(parents=True,exist_ok=True)
 # Preserve the complete run before acceptance, including a failed run.
 a.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n')
 try:result['verification']=check_result(result)
 except Exception as error:
  result['acceptance_failure']={'type':type(error).__name__,'message':str(error)}
  a.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n')
  raise
 a.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n')
 print(json.dumps({'rows':len(rows),'verification':result['verification'],'elapsed_seconds':result['elapsed_seconds']}))
if __name__=='__main__':main()
