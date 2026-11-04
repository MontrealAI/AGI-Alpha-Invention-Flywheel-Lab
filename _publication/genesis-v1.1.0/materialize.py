"""One-time byte-preserving transport for the user-supplied public paper package."""
import base64,hashlib,io,shutil,subprocess,tempfile,zipfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[2]
TRANSPORT=ROOT/'_publication/genesis-v1.1.0'
data=(ROOT/'docs/alpha-genesis/ALPHA_GENESIS_FLYWHEEL_OMEGA_v1.1.0_SOURCE.zip').read_bytes()
if len(data)!=8358324 or hashlib.sha256(data).hexdigest()!='8b059f63073f26f63320dfdf793f00156d00e4667faf0e244de6552f19da8a77': raise ValueError('Original source ZIP identity mismatch')
with tempfile.TemporaryDirectory() as temp:
 source=Path(temp)/'source';source.mkdir()
 with zipfile.ZipFile(io.BytesIO(data)) as archive:
  infos=archive.infolist()
  if len(infos)!=36 or sum(i.file_size for i in infos)>10*1024*1024: raise ValueError('Unexpected package inventory')
  for info in infos:
   p=PurePosixPath(info.filename)
   if p.is_absolute() or '..' in p.parts or '\\' in info.filename or info.is_dir() or (info.external_attr>>16)&0o170000==0o120000: raise ValueError('Unsafe archive member')
   target=source/info.filename;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(info))
 subprocess.run(['python3','verify.py'],cwd=source,check=True)
 expected={'ALPHA_GENESIS_FLYWHEEL_OMEGA.pdf':'0e4baa13ebede0d638d5260c250b6f28aa5d68e2f16b7c27697a696ddb34a171','ALPHA_GENESIS_FLYWHEEL_OMEGA.tex':'0617446315264e0eb511f17f570a0ef56cbf76488b29fb7542b03b9cef25759d'}
 for name,digest in expected.items():
  if hashlib.sha256((source/name).read_bytes()).hexdigest()!=digest: raise ValueError('Latest attachment mismatch')
 destination=ROOT/'docs/alpha-genesis/v1.1.0'
 if destination.exists(): raise ValueError('Refuse to overwrite an edition')
 shutil.copytree(source,destination,ignore=shutil.ignore_patterns('__pycache__'))
 (ROOT/'docs/alpha-genesis/ALPHA_GENESIS_FLYWHEEL_OMEGA_v1.1.0_SOURCE.zip').write_bytes(data)
 shutil.copyfile(source/'ALPHA_GENESIS_FLYWHEEL_OMEGA.pdf',ROOT/'docs/research/alpha-genesis-flywheel-omega.pdf')
subprocess.run(['python3','-m','unittest','discover','-s','tests','-p','test_research_site.py','-v'],cwd=ROOT,check=True)
subprocess.run(['node','--test','tests/test_alpha_site.cjs'],cwd=ROOT,check=True)
shutil.rmtree(TRANSPORT)
(ROOT/'.github/workflows/genesis-publication-materialize.yml').unlink()
print('Exact1.1 source package and latest PDF verified; temporary transport removed.')
