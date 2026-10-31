import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

metadata_path, target, receipt_path = map(Path, sys.argv[1:4])
metadata=json.loads(metadata_path.read_text());target.mkdir(exist_ok=False)
if metadata['draft'] or metadata['tag']!='connected014-8abfb96d4ef859e30ca344d7933ec2a2f49012c1':raise ValueError('EXPECTED_PUBLIC_RELEASE_REQUIRED')
start=time.monotonic();rows=[]
def download(asset):
    name=asset['name']
    if Path(name).name!=name:raise ValueError('REGULAR_RELEASE_ASSET_NAME_REQUIRED')
    expected='https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/download/'+metadata['tag']+'/'+name
    if asset['url']!=expected:raise ValueError('EXACT_PUBLISHED_ASSET_URL_REQUIRED')
    destination=target/name
    p=subprocess.run(['curl','--fail','--location','--silent','--show-error','--output',str(destination),asset['url']],capture_output=True,text=True)
    row={'name':name,'url':asset['url'],'exit_code':p.returncode,'stderr':p.stderr,'asset_id':asset['id']}
    if destination.exists():row.update(bytes=destination.stat().st_size,sha256=hashlib.sha256(destination.read_bytes()).hexdigest())
    if not p.returncode and row['bytes']!=asset['bytes']:row['failure']='PUBLIC_ASSET_SIZE_MISMATCH'
    if not p.returncode and asset.get('digest') and asset['digest']!='sha256:'+row['sha256']:row['failure']='PUBLIC_ASSET_DIGEST_MISMATCH'
    return row
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    rows=list(pool.map(download,metadata['assets']))
receipt={'schema':'agi-alpha/operator022-actual-public-release-download/v1','source_commit':'8abfb96d4ef859e30ca344d7933ec2a2f49012c1','tag':metadata['tag'],'release_url':metadata['html_url'],'published_at':metadata['published_at'],'downloaded_at_utc':datetime.now(timezone.utc).isoformat(),'actual_public_release_download':all(r['exit_code']==0 and 'failure' not in r for r in rows),'assets':rows,'wall_seconds':time.monotonic()-start,'scope':'Direct public release asset HTTP downloads; no checkout or CI artifact substituted.'}
receipt_path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
print(json.dumps({'accepted':receipt['actual_public_release_download'],'assets':len(rows),'failed':[r['name'] for r in rows if r['exit_code'] or 'failure' in r]},sort_keys=True))
if not receipt['actual_public_release_download']:raise SystemExit(1)
