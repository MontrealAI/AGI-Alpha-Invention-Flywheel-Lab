"""Verification orchestration of unchanged, frozen candidate APIs and public CLI."""
import argparse,hashlib,json,pathlib,subprocess,sys
BASE=pathlib.Path('/workspace/scratch/8ae627a67fcf')
ROOT=BASE/'p0-native/campaign/verification-021-work/source'
OUT=BASE/'verification021-control/operating'
sys.path.insert(0,str(ROOT))
from connected_enterprise.runner import identity
from connected_enterprise import capital

def command(*args):
 p=subprocess.run([sys.executable,'-m','connected_enterprise',*map(str,args)],cwd=ROOT,capture_output=True,text=True)
 print(json.dumps({'command':list(map(str,args)),'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}),flush=True)
 p.check_returncode();return json.loads(p.stdout)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['enabled-step','disabled','finish','adverse']);a=parser.parse_args()
 assert identity(ROOT)['sha256']=='0a41cbe703772ddd831497fc094b0379f0eae99d4d24f9c62a40098e3aa3db4e'
 OUT.mkdir(exist_ok=True)
 output=OUT/'central-comparison'
 if a.phase in ('enabled-step','disabled','finish'):
  if not output.exists():
   capital.freeze(ROOT,json.loads((ROOT/'examples/native_capital020/central.json').read_text()),output,comparison=True)
   capital.register(output)
  if a.phase in ('enabled-step','disabled'):
   enabled=a.phase=='enabled-step';name='recycling_enabled' if enabled else 'recycling_disabled'
   business=output/'arms'/name
   key=business/'account.sqlite.adaptive-simulation-key'
   before=key.stat().st_ino if key.exists() else None
   result=capital.operate(output,business=business,enabled=enabled,max_events=12 if enabled else None)
   after=key.stat().st_ino
   assert before is None or before==after
   print(json.dumps({'phase':a.phase,'complete':result['complete'],'processed_events':result['state']['processed_events'],
    'orders':len(result['state']['orders']),'decisions':len(result['state']['decisions']),
    'summary':result['summary'],'private_key_inode_before':before,'private_key_inode_after':after}),flush=True)
  else:
   for name in ['recycling_enabled','recycling_disabled']:
    assert json.loads((output/'arms'/name/'RESULT.json').read_text())['complete'],'INCOMPLETE_COMPARISON_ARM'
   # The canonical frozen CLI completes its existing comparison and performs its audit.
   p=subprocess.run([sys.executable,'-m','connected_enterprise','_capital','--action','comparison','--output',str(output)],
                    cwd=output/'source',capture_output=True,text=True)
   print(p.stdout,flush=True);print(p.stderr,file=sys.stderr,flush=True);p.check_returncode()
   command('audit','--output',output)
   command('scoreboard','--output',output)
 else:
  for name in ['provider_default','outside_choice']:
   target=OUT/name
   command('register','--config',ROOT/'examples/native_capital020'/f'{name}.json','--output',target)
   command('operate','--output',target)
   command('audit','--output',target)
   command('scoreboard','--output',target)
 assert identity(ROOT)['sha256']=='0a41cbe703772ddd831497fc094b0379f0eae99d4d24f9c62a40098e3aa3db4e'

if __name__=='__main__':main()
