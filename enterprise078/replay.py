import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
from .review import read,review,unpack
from .runtime import materialize

def replay(root,out):
 root=Path(root).resolve();out=Path(out).resolve()
 if out.exists(): raise ValueError('NEW_REPLAY_DIRECTORY_REQUIRED')
 out.mkdir(parents=True);science=materialize(root,out/'scientific-source')
 results={}
 for revision in ('original','v2'):
  archive=root/'enterprise078/evidence'/f'{revision}-public-evidence.zip';record=read(root/'enterprise078/evidence'/f'{revision}-archive.json')
  if hashlib.sha256(archive.read_bytes()).hexdigest()!=record['sha256']: raise ValueError('ARCHIVE_HASH_CHANGED')
  source=science
  if revision=='v2':
   source=out/'v2-source';source.mkdir()
   original=read(out/'original/SOURCE.json')
   for n in original['files']:
    p=source/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(science/n,p)
   protocol=read(root/'enterprise078/revisions/PROTOCOL.json');p=source/'enterprise078/campaign.py'
   if hashlib.sha256(p.read_bytes()).hexdigest()!=protocol['original_campaign_sha256']: raise ValueError('WRONG_PATCH_SOURCE')
   patch=root/'enterprise078/revisions/whole_delivery.patch'
   if hashlib.sha256(patch.read_bytes()).hexdigest()!=protocol['patch_sha256']: raise ValueError('PATCH_CHANGED')
   subprocess.run(['patch','--batch','--forward','-p1','-i',str(patch)],cwd=source,check=True,stdout=subprocess.PIPE)
   if hashlib.sha256(p.read_bytes()).hexdigest()!=protocol['revised_campaign_sha256']: raise ValueError('PATCH_RESULT_CHANGED')
  folder=unpack(archive,source,out/revision);result=review(folder,revision)
  env=os.environ.copy();env['PYTHONPATH']=str(folder/'source');env['PYTHONNOUSERSITE']='1'
  native=subprocess.run([sys.executable,'-m','enterprise078.campaign','audit','--output',str(folder)],cwd=folder/'source',env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  if native.returncode: raise RuntimeError(native.stderr)
  result['native_semantic_audit']=json.loads(native.stdout)
  if not result['accepted'] or result['native_semantic_audit']['accepted'] is not True: raise ValueError('NATIVE_REPLAY_REFUSED')
  results[revision]=result
 return {'accepted':True,'results':results,'scope':'original public evidence replay only; no private account creation or ownership-HMAC authentication'}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(replay(Path(__file__).resolve().parents[1],a.output),sort_keys=True))
