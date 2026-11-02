"""Verify compact public bytes and replay without reading private account authority."""
from pathlib import Path
import hashlib,json,tempfile
from business_productivity065.verify import verify,ARMS
ROOT=Path(__file__).resolve().parents[2]
EVIDENCE=Path(__file__).resolve().parent/'evidence'
def main():
 manifest=json.loads((EVIDENCE/'MANIFEST.json').read_text())
 for relative,expected in manifest['sha256'].items():
  path=ROOT/relative
  if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('PUBLIC_EVIDENCE_CHANGED:'+relative)
 with tempfile.TemporaryDirectory(prefix='public065-audit-') as tmp:
  for arm in ARMS:(Path(tmp)/('productivity065-'+arm)).symlink_to(EVIDENCE/arm,target_is_directory=True)
  result=verify(ROOT,Path(tmp))
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
