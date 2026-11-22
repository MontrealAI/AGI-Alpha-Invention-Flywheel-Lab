import datetime,json,struct,urllib.request
from pathlib import Path

r=Path(__file__).resolve().parent;url='https://zenodo.org/api/records/15123604/files/Source-data-for-review.zip/content';total=1978537477;start=total-131072
out={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'requested_range':[start,total-1],'whole_archive_downloaded':False,'source_total_bytes':total,'audit_stage':'Public archive directory inventory only; no candidate execution'}
try:
 req=urllib.request.Request(url,headers={'Range':f'bytes={start}-{total-1}','Accept-Encoding':'identity'})
 with urllib.request.urlopen(req,timeout=20) as response:
  out['status']=response.status;out['content_range']=response.headers.get('Content-Range');out['content_length']=response.headers.get('Content-Length')
  if response.status!=206:raise ValueError('SERVER_DID_NOT_HONOR_RANGE')
  data=response.read(131073)
  if len(data)>131072:raise ValueError('RANGE_BUDGET')
  out['read_bytes']=len(data);(r/'ZIP_TAIL.bin').write_bytes(data)
  k=data.rfind(b'PK\x05\x06')
  if k<0:raise ValueError('NO_EOCD')
  e=struct.unpack_from('<4s4H2LH',data,k);out['zip_entries']=e[4];out['directory_bytes']=e[5];out['directory_offset']=e[6]
except Exception as e:out['error']=type(e).__name__+': '+str(e)
(r/'ZIP_RANGE_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
