"""Read-only source pinning. No image decode for IR, labels or truth masks."""
import concurrent.futures as cf
import hashlib
import json
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'sealed-inputs'
RAW.mkdir(exist_ok=True)
GH = 'https://raw.githubusercontent.com/DomRusso2/ir-truth-9um/7e96b969d3a1407504db4826543136573bda78b8/'
FRONT = 'https://dl.ash2txt.org/fragments/PHerc0343P/paths/2um_front_surface/'
SV = 'https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHerc0343P/segments/20250511003658-tifxyz/surface-volumes/8.64um-1.2m-116keV-volume-20250521134555.zarr/'
FILES = {
 'ir_truth_ink.png': GH+'data/truth_ink.png',
 'ir_truth_noink.png': GH+'data/truth_noink.png',
 'ir_valid.png': GH+'data/valid.png',
 'ir_traced_full.png': GH+'data/ink_traced_full.png',
 'ir_photo_on_ct.png': GH+'data/ir_photo_on_8.64um.png',
 'ir_pose.json': GH+'data/pose_front_to_8.64um.json',
 'source_front_ir.png': FRONT+'343P_ir.png',
 'source_front_labels.png': FRONT+'343P_inklabels.png',
 'source_front_mask.png': FRONT+'343P_mask.png',
 'ct_zattrs.json': SV+'.zattrs',
 'ct_zarray.json': SV+'0/.zarray',
}

def fetch(item):
 name,url=item
 target=RAW/name
 started=time.time()
 try:
  with urllib.request.urlopen(url,timeout=75) as r:
   data=r.read(); headers=dict(r.headers)
  target.write_bytes(data)
  return dict(name=name,url=url,path=str(target),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
   etag=headers.get('ETag'),last_modified=headers.get('Last-Modified'),content_type=headers.get('Content-Type'),
   elapsed_seconds=round(time.time()-started,3),status='FETCHED_UNDECODED')
 except Exception as e:
  return dict(name=name,url=url,status='FAILED',error=type(e).__name__+': '+str(e),elapsed_seconds=round(time.time()-started,3))

with cf.ThreadPoolExecutor(max_workers=4) as ex:
 results=list(ex.map(fetch,FILES.items()))
receipt=dict(accessed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
 repo_commit='7e96b969d3a1407504db4826543136573bda78b8',truth_pixels_decoded=False,
 full_photo_pixels_decoded=False,ct_pixels_decoded=False,files=results)
(ROOT/'FIXTURE_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
