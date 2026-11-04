import argparse,hashlib,json,struct,urllib.request,zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parent
URL='https://zenodo.org/api/records/15123604/files/Source-data-for-review.zip/content'
def fetch(start,size):
 if size>32*1024*1024:raise ValueError('RANGE_LIMIT')
 req=urllib.request.Request(URL,headers={'Range':f'bytes={start}-{start+size-1}','Accept-Encoding':'identity'})
 with urllib.request.urlopen(req,timeout=20) as response:
  if response.status!=206 or response.headers.get('Content-Range')!=f'bytes {start}-{start+size-1}/1978537477':raise ValueError('RANGE_IDENTITY')
  b=response.read(size+1)
  if len(b)!=size:raise ValueError('RANGE_LENGTH')
 return b
def read_entry(item):
 header=fetch(item['offset'],30);h=struct.unpack('<4s5H3L2H',header)
 if h[0]!=b'PK\x03\x04' or h[2]&1:raise ValueError('ZIP_HEADER')
 fn,extra=h[9:11];size=item['compressed_bytes'];b=fetch(item['offset']+30,fn+extra+size);encoded=b[:fn]
 if encoded.decode('utf-8',errors='replace')!=item['name']:raise ValueError('ZIP_FILENAME_IDENTITY')
 raw=b[fn+extra:]
 if item['compression']==8:
  d=zlib.decompressobj(-15);plain=d.decompress(raw,item['uncompressed_bytes']+1)
 elif item['compression']==0:plain=raw
 else:raise ValueError('UNSUPPORTED_ZIP_COMPRESSION')
 if len(plain)!=item['uncompressed_bytes'] or zlib.crc32(plain)!=item['crc32']:raise ValueError('ZIP_CONTENT_IDENTITY')
 return plain,len(header)+len(b)
def main():
 p=argparse.ArgumentParser();p.add_argument('--selection',choices=['readmes'],default='readmes');args=p.parse_args();items=json.loads((ROOT/'RAW_ARCHIVE_INVENTORY.json').read_text())['files'];selected=[x for x in items if x['name'].endswith('.txt')];out=[];(ROOT/'raw_readmes').mkdir(exist_ok=True)
 for j,item in enumerate(selected):
  if item['uncompressed_bytes']>65536:raise ValueError('README_LIMIT')
  b,n=read_entry(item);name=f'{j:02d}.txt';(ROOT/'raw_readmes'/name).write_bytes(b);out.append({'source':item,'local_file':'raw_readmes/'+name,'http_body_bytes':n,'sha256':hashlib.sha256(b).hexdigest()})
 (ROOT/'RAW_README_IDENTITIES.json').write_text(json.dumps(out,indent=2)+'\n')
 for item in out:print(item['source']['name']+'\n'+(ROOT/item['local_file']).read_text(errors='replace')+'\n')
if __name__=='__main__':main()
