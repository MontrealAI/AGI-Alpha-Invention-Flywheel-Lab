from pathlib import Path
import urllib.request, json, hashlib, time, datetime
from concurrent.futures import ThreadPoolExecutor
root=Path(__file__).resolve().parent
base='https://nasa-ext.app.box.com/index.php?rm=box_download_shared_file&shared_name=3lbcjhnv4wz833vg42997euxufxui202&file_id=f_'
items=[('TTT_AM_315400_low_res.tif','1465770388439',196666399),('TTT_AM_315400_profilometry.zip','1465772485255',21336333),('disk_profilometry_top_height_metadata.csv','1465775003054',282),('disk_profilometry_top_optical_metadata.csv','1465774113141',277)]
assert sum(x[2]for x in items)<256*1024*1024

def download(item):
 name,ident,expected=item;start=time.monotonic(); p=root/name
 if p.exists():raise FileExistsError(p)
 url=base+ident;h=hashlib.sha256();n=0
 try:
  with urllib.request.urlopen(url,timeout=45) as f,p.open('wb') as o:
   while True:
    b=f.read(min(1024*1024,expected+1-n))
    if not b:break
    n+=len(b);h.update(b);o.write(b)
    if n>expected:raise ValueError('Declared source byte cap exceeded')
  assert n==expected,(n,expected)
  return {'file':name,'url':url,'bytes':n,'sha256':h.hexdigest(),'seconds':time.monotonic()-start,'status':'VERIFIED_BYTES'}
 except Exception as e:return {'file':name,'url':url,'bytes_written':n,'sha256_partial':h.hexdigest(),'seconds':time.monotonic()-start,'error':repr(e),'status':'FAILED'}
with ThreadPoolExecutor(max_workers=2)as ex:records=list(ex.map(download,items))
receipt={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'license':'NASA NTRS Work of US Government: Public Use Permitted','dataset':'https://ntrs.nasa.gov/citations/20240002767','records':records}
(root/'ACQUIRE.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
