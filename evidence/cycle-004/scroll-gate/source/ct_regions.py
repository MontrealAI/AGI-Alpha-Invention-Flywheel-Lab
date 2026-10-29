"""Material-only CT selection under frozen CT_REGION_SELECTION.json. No label or photo reads."""
import concurrent.futures as cf
import hashlib
import json
from pathlib import Path
import time
import urllib.request
import urllib.error

import numpy as np

ROOT=Path(__file__).resolve().parent
spec_bytes=(ROOT/'CT_REGION_SELECTION.json').read_bytes()
spec=json.loads(spec_bytes)
BASE='https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHerc0343P/segments/20250511003658-tifxyz/surface-volumes/8.64um-1.2m-116keV-volume-20250521134555.zarr/0/'
CACHE=ROOT/'ct-chunks'
CACHE.mkdir(exist_ok=True)
def get_chunk(key):
 y,x=key;url=BASE+f'0/{y}/{x}'
 p=CACHE/f'0_{y}_{x}.bin'
 status='FETCHED'
 if p.exists():
  raw=p.read_bytes();headers={};status='CACHED_EXACT_BYTES'
 else:
  try:
   with urllib.request.urlopen(url,timeout=30) as r:
    raw=r.read();headers={k.lower():v for k,v in r.headers.items()}
  except urllib.error.HTTPError as e:
   if e.code!=404:raise
   # Missing chunks are source-defined fill 0 in the pinned Zarr v2 metadata.
   meta=json.loads((ROOT/'sealed-inputs/ct_zarray.json').read_text())
   if meta['fill_value']!=0 or meta['dtype']!='|u1' or meta['compressor'] is not None:raise
   raw=bytes(31*128*128);headers={};status='HTTP404_ZARR_SPEC_FILL0'
 if len(raw)!=31*128*128:raise ValueError((key,len(raw),'unexpected chunk length'))
 if status=='FETCHED':p.write_bytes(raw)
 return key,np.frombuffer(raw,np.uint8).reshape(31,128,128),dict(key=list(key),url=url,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),status=status,etag=headers.get('etag'),last_modified=headers.get('last-modified'))
keys=sorted({(y//128+dy,x//128+dx) for y,x in spec['candidate_origins_yx_row_major'] for dy in range(2) for dx in range(2)})
with cf.ThreadPoolExecutor(max_workers=4) as ex:
 rows=list(ex.map(get_chunk,keys))
chunks={key:a for key,a,rec in rows}
windows=[]
for y,x in spec['candidate_origins_yx_row_major']:
 a=np.concatenate([np.concatenate([chunks[(y//128+dy,x//128+dx)] for dx in range(2)],axis=2) for dy in range(2)],axis=1)
 frac=float((a[15]>0).mean())
 windows.append(dict(origin_yx=[y,x],shape_zyx=list(a.shape),middle_support_fraction=frac,qualifies=frac>=.60,array=a))
good=[r for r in windows if r['qualifies']]
if not good:raise ValueError('No predeclared CT window qualifies; no silent selection rewrite')
dev=good[0];dy,dx=dev['origin_yx']
other=[r for r in good if sum((p-q)**2 for p,q in zip(r['origin_yx'],[dy,dx]))>=768**2]
if not other:raise ValueError('No distant confirmation window qualifies')
confirm=max(other,key=lambda r:sum((p-q)**2 for p,q in zip(r['origin_yx'],[dy,dx])))
out={}
for name,r in [('development',dev),('confirmation',confirm)]:
 path=ROOT/(name+'_ct.npy');np.save(path,r['array'],allow_pickle=False)
 out[name]={k:v for k,v in r.items() if k!='array'}
 out[name].update(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
rec=dict(completed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
 selection_spec_sha256=hashlib.sha256(spec_bytes).hexdigest(),
 truth_pixels_read=False,photos_read=False,model_read_or_executed=False,
 selected=out,ct_support_survey=[{k:v for k,v in r.items() if k!='array'} for r in windows],chunks=[rec for _,_,rec in rows])
(ROOT/'CT_REGION_RECEIPT.json').write_text(json.dumps(rec,indent=2)+'\n')
print(json.dumps({k:rec[k] for k in ['completed_utc','selection_spec_sha256','selected','truth_pixels_read']},indent=2))
