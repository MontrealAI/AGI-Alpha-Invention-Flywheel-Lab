"""Fetch pinned public inputs into this experiment directory; no installation."""
from pathlib import Path,PurePosixPath
from urllib.request import urlopen
import hashlib,zipfile,json
ROOT=Path(__file__).resolve().parent
ARCHIVES={
'Codes_Python.zip':'330d76f3c7148d2840f7f207cd90d7a98eb1d972867b70188096043c9e3261a2',
'EvaluationData.zip':'e1003c2b652280fa052a8655ec80893e480d8a377ab7e516fced125b3ebc45c0',
'EvaluationData_full.zip':'85c47f91c0cd15889a96108b389550edafd8bba46b40fd84447e63a62534ce42'}
CUQI='c3a9465a3aeb5c2ced6c72aa357afa584fa9b9e7'
def sha(b):return hashlib.sha256(b).hexdigest()
def fetch(url,path,expected):
 if not path.exists():
  with urlopen(url,timeout=60) as r:b=r.read(10_000_001)
  if len(b)>10_000_000:raise ValueError('unexpected download size')
  if sha(b)!=expected:raise ValueError('source hash mismatch: '+url)
  path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b)
 elif sha(path.read_bytes())!=expected:raise ValueError('existing source hash mismatch: '+str(path))
def main():
 manifest=json.loads((ROOT/'SOURCE_MANIFEST.json').read_text())
 for name,h in ARCHIVES.items():
  path=ROOT/name;fetch(f'https://zenodo.org/api/records/10986692/files/{name}/content',path,h)
  out=ROOT/('source' if name=='Codes_Python.zip' else 'data')
  with zipfile.ZipFile(path) as z:
   if sum(i.file_size for i in z.infolist())>50_000_000:raise ValueError('unexpected expanded archive size')
   for info in z.infolist():
    p=PurePosixPath(info.filename)
    if p.is_absolute() or '..' in p.parts:raise ValueError('unsafe archive member')
    if info.is_dir():continue
    if name=='Codes_Python.zip':keep=len(p.parts)==2 and (p.suffix=='.py' or p.name=='Mesh_sparse.mat')
    else:keep=(any(x in p.parts for x in ['level1','level4','level7']) and p.name in ['data1.mat','ref.mat']) or (any(x in p.parts for x in ['level_1','level_4','level_7']) and p.name=='1_true.mat')
    if keep:
     target=out/str(p);target.parent.mkdir(parents=True,exist_ok=True);b=z.read(info)
     if target.exists() and target.read_bytes()!=b:raise ValueError('refuse changed local source')
     target.write_bytes(b)
 for name,h in manifest['cuqi3_files'].items():
  fetch(f'https://raw.githubusercontent.com/CUQI-DTU/KTC2023-CUQI3/{CUQI}/{name}',ROOT/'cuqi3'/name,h)
 print('Pinned source and selected evaluation files verified; no code executed.')
if __name__=='__main__':main()
