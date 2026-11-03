import argparse,hashlib,json
from pathlib import Path

EXPECTED_FREEZE='c13a7411587736a18f1adc6422a15e026b6c934524eba745b344da82befff570'
OVERRIDES={n:'enterprise078/frozen_native/'+n for n in ('commercial/ledger.py','connected_enterprise/finance.py')}

def digest(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def materialize(root,destination):
 root=Path(root).resolve();destination=Path(destination).resolve()
 frozen=json.loads((root/'enterprise078/FROZEN.json').read_text())
 if frozen['sha256']!=EXPECTED_FREEZE or digest(frozen['files'])!=EXPECTED_FREEZE:
  raise ValueError('ORIGINAL_306_FILE_FREEZE_REQUIRED')
 if destination.exists(): raise ValueError('NEW_SCIENTIFIC_DIRECTORY_REQUIRED')
 payload={}
 for name,expected in frozen['files'].items():
  relative=Path(name)
  if relative.is_absolute() or '..' in relative.parts: raise ValueError('RELATIVE_FROZEN_SOURCE_REQUIRED')
  p=root/OVERRIDES.get(name,name)
  if not p.is_file() or p.is_symlink() or any(q.is_symlink() for q in p.parents): raise ValueError('REGULAR_FROZEN_SOURCE_REQUIRED')
  raw=p.read_bytes()
  if hashlib.sha256(raw).hexdigest()!=expected: raise ValueError('FROZEN_SOURCE_BYTES_CHANGED:'+name)
  payload[name]=raw
 destination.mkdir(parents=True)
 for name,raw in payload.items():
  p=destination/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
 return destination

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 root=materialize(Path(__file__).resolve().parents[1],a.output)
 print(json.dumps({'source':str(root),'files':306,'freeze':EXPECTED_FREEZE,'scope':'exact historical scientific runtime; no accounts created'}))
