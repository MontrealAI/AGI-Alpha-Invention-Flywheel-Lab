"""Compact NIST ZIP ranges with CRC/memberSHA; no fullarchive download."""
import io,json,struct,zlib,urllib.request,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
BASE=Path(__file__).parent
URL='https://data.nist.gov/od/ds/mds2-2950/training_pairs.zip';SIZE=441187839

def fetch_range(url,size,start,end):
 req=urllib.request.Request(url,headers={'Range':f'bytes={start}-{end}'})
 with urllib.request.urlopen(req,timeout=90) as r:
  if r.status!=206 or r.headers.get('Content-Range')!=f'bytes {start}-{end}/{size}':raise ValueError('Range/source size mismatch')
  b=r.read()
 if len(b)!=end-start+1:raise ValueError('Range payload length mismatch')
 return b

def extract_members(block,start,entries):
 out=[]
 for e in entries:
  o=e['offset']-start;h=block[o:o+30];sig,ver,flag,method,mt,md,crc,cs,us,nl,el=struct.unpack('<4s5H3I2H',h)
  if sig!=b'PK\x03\x04' or method!=e['method']:raise ValueError('ZIP localheader mismatch')
  if block[o+30:o+30+nl].decode()!=e['name']:raise ValueError('ZIP name mismatch')
  a=o+30+nl+el;packed=block[a:a+e['compressed']];raw=zlib.decompress(packed,-15) if method==8 else packed
  if len(raw)!=e['size'] or zlib.crc32(raw)!=e['crc32']:raise ValueError('ZIP CRC/length mismatch')
  out.append((e,raw))
 return out

def source_split(split):
 entries=json.loads((BASE/'source_entries.json').read_text());prefix='training_pairs/'+split+'/'
 entries=[e for e in entries if e['name'].startswith(prefix) and e['name'].endswith('.png')]
 entries.sort(key=lambda e:e['name'])
 if len(entries)!={'train':1030,'val/train':114,'test':300}[split]:raise ValueError('source denominator mismatch')
 start=min(e['offset'] for e in entries);end=max(e['offset']+30+len(e['name'].encode())+e['compressed'] for e in entries)-1
 b=fetch_range(URL,SIZE,start,end)
 return extract_members(b,start,entries)

def decode_pair(raw):
 a=np.asarray(Image.open(io.BytesIO(raw)))
 if a.ndim==3:
  if not np.all(a[:,:,:3]==a[:,:,:1]):raise ValueError('nonidenticalRGB channels; source semantics unresolved')
  a=a[:,:,0]
 if a.shape!=(128,256):raise ValueError('pair shape mismatch')
 #Orientation is gated by sourcepreprocessing confirmation, never guessed fromoutcomes.
 return a[:,:128],a[:,128:]

def load_split(split,receipt):
 if not receipt:raise ValueError('requires prospective public split/finalfreeze receipt')
 pairs=source_split(split);masks=[];heights=[];records=[]
 for e,b in pairs:
  a,h=decode_pair(b);masks.append(a);heights.append(h)
  records.append({'name':e['name'],'crc32':e['crc32'],'sha256':hashlib.sha256(b).hexdigest(),'size':len(b),'source_split':split,'receipt':receipt})
 tag=split.replace('/','_');np.savez_compressed(BASE/f'{tag}.npz',mask=np.array(masks,dtype=np.uint8),height=np.array(heights,dtype=np.uint8))
 (BASE/f'{tag}_lineage.json').write_text(json.dumps(records,indent=2))
 return len(records)
