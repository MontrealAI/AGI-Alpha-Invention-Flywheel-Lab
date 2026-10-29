"""Add exactly 64px CT-only halo to the already selected regions."""
import concurrent.futures as cf
import hashlib,json,time,urllib.request,urllib.error
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent
C=R/'ct-chunks'
B='https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHerc0343P/segments/20250511003658-tifxyz/surface-volumes/8.64um-1.2m-116keV-volume-20250521134555.zarr/0/'
prior=(R/'CT_REGION_RECEIPT.json').read_bytes();regions=json.loads(prior)['selected']
keys=sorted({(yy,xx) for v in regions.values() for yy in range((v['origin_yx'][0]-64)//128,(v['origin_yx'][0]+256+63)//128+1) for xx in range((v['origin_yx'][1]-64)//128,(v['origin_yx'][1]+256+63)//128+1)})
def load(k):
 y,x=k;p=C/f'0_{y}_{x}.bin';u=B+f'0/{y}/{x}';headers={};status='CACHED_EXACT_BYTES'
 if p.exists():raw=p.read_bytes()
 else:
  try:
   with urllib.request.urlopen(u,timeout=30) as r:
    raw=r.read();headers={k.lower():v for k,v in r.headers.items()};status='FETCHED'
   p.write_bytes(raw)
  except urllib.error.HTTPError as e:
   if e.code!=404:raise
   raw=bytes(31*128*128);status='HTTP404_ZARR_SPEC_FILL0'
 if len(raw)!=31*128*128:raise ValueError((k,len(raw)))
 return k,np.frombuffer(raw,np.uint8).reshape(31,128,128),dict(chunk_yx=list(k),url=u,status=status,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),etag=headers.get('etag'),last_modified=headers.get('last-modified'))
with cf.ThreadPoolExecutor(max_workers=4) as ex:chunks=list(ex.map(load,keys))
d={k:a for k,a,r in chunks};selected={}
for name,v in regions.items():
 y,x=v['origin_yx'];y-=64;x-=64;cy,cx=y//128,x//128
 a=np.concatenate([np.concatenate([d[(yy,xx)] for xx in range(cx,(x+383)//128+1)],axis=2) for yy in range(cy,(y+383)//128+1)],axis=1)
 a=a[:,y-cy*128:y-cy*128+384,x-cx*128:x-cx*128+384]
 p=R/(name+'_halo_ct.npy');np.save(p,a,allow_pickle=False)
 selected[name]=dict(global_origin_yx=[y,x],shape_zyx=list(a.shape),core_local_yxhw=[64,64,256,256],path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
rec=dict(completed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),region_receipt_sha256=hashlib.sha256(prior).hexdigest(),halo_pixels=64,truth_read=False,photos_read=False,selected=selected,chunks=[r for k,a,r in chunks])
(R/'CT_HALO_RECEIPT.json').write_text(json.dumps(rec,indent=2)+'\n');print(json.dumps(selected,indent=2))
