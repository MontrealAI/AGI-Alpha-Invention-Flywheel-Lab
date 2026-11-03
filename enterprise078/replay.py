import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
from .review import read,review,unpack

def replay(root,out):
 root=Path(root).resolve();out=Path(out).resolve()
 if out.exists(): raise ValueError('NEW_REPLAY_DIRECTORY_REQUIRED')
 out.mkdir(parents=True)
 results={}
 for revision in ('original','v2'):
  archive=root/'enterprise078/evidence'/f'{revision}-public-evidence.zip';record=read(root/'enterprise078/evidence'/f'{revision}-archive.json')
  if hashlib.sha256(archive.read_bytes()).hexdigest()!=record['sha256']: raise ValueError('ARCHIVE_HASH_CHANGED')
  source=root
  if revision=='v2':
   source=out/'v2-source';source.mkdir()
   original=read(out/'original/SOURCE.json')
   for n in original['files']:
    p=source/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/n,p)
   protocol=read(root/'enterprise078/revisions/PROTOCOL.json');p=source/'enterprise078/campaign.py'
   if hashlib.sha256(p.read_bytes()).hexdigest()!=protocol['original_campaign_sha256']: raise ValueError('WRONG_PATCH_SOURCE')
   patch=root/'enterprise078/revisions/whole_delivery.patch'
   if hashlib.sha256(patch.read_bytes()).hexdigest()!=protocol['patch_sha256']: raise ValueError('PATCH_CHANGED')
   subprocess.run(['patch','--batch','--forward','-p1','-i',str(patch)],cwd=source,check=True,stdout=subprocess.PIPE)
   if hashlib.sha256(p.read_bytes()).hexdigest()!=protocol['revised_campaign_sha256']: raise ValueError('PATCH_RESULT_CHANGED')
  folder=unpack(archive,source,out/revision)
  result=review(folder,revision)
  env=os.environ.copy();env['PYTHONPATH']=str(folder/'source')
  native=subprocess.run([sys.executable,'-m','enterprise078.campaign','audit','--output',str(folder)],cwd=folder/'source',env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  if native.returncode: raise RuntimeError(native.stderr)
  result['native_semantic_audit']=json.loads(native.stdout);results[revision]=result
 return {'accepted':all(r['accepted'] and r['native_semantic_audit']['accepted'] for r in results.values()),'results':results,'scope':'original public evidence replay only; no private account creation or ownership-HMAC authentication'}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(replay(Path(__file__).resolve().parents[1],a.output),sort_keys=True))
