"""One-time byte-preserving transport for the user-supplied public paper package."""
import base64,hashlib,io,shutil,subprocess,tempfile,zipfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[2]
TRANSPORT=ROOT/'_publication/genesis-v1.1.0'
data=(ROOT/'docs/alpha-genesis/ALPHA_GENESIS_FLYWHEEL_OMEGA_v1.1.0_SOURCE.zip').read_bytes()
if len(data)!=8358879 or hashlib.sha256(data).hexdigest()!='d0f1384e68046fcd6157d2c79a97032a4f6a809b0c19d88acf253b4730e4472a': raise ValueError('Approved public revision ZIP identity mismatch')
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
 expected={'ALPHA_GENESIS_FLYWHEEL_OMEGA.pdf':'7c1f2811a6e133efeabc49d2ed76d68cf08ee4f35d3ff196f2724cee6a04ae6f','ALPHA_GENESIS_FLYWHEEL_OMEGA.tex':'25cddbab8036f4774cc6fccef200565ff0dcaa9ac0263d58ab99088754e57e55'}
 for name,digest in expected.items():
  if hashlib.sha256((source/name).read_bytes()).hexdigest()!=digest: raise ValueError('Approved public revision identity mismatch')
 destination=ROOT/'docs/alpha-genesis/v1.1.0'
 if not destination.is_dir() or hashlib.sha256((destination/'SHA256SUMS').read_bytes()).hexdigest()!='793cad1f33fd15751ead180b96b28aecf8ca6e020d8e69a523a80273430ae5b6': raise ValueError('Unexpected prior publication edition')
 source_files={str(p.relative_to(source)):p for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
 old_files={str(p.relative_to(destination)) for p in destination.rglob('*') if p.is_file()}
 if set(source_files)!=old_files: raise ValueError('Publication revision inventory changed')
 for relative,file in source_files.items():
  (destination/relative).write_bytes(file.read_bytes())
 (ROOT/'docs/alpha-genesis/ALPHA_GENESIS_FLYWHEEL_OMEGA_v1.1.0_SOURCE.zip').write_bytes(data)
 shutil.copyfile(source/'ALPHA_GENESIS_FLYWHEEL_OMEGA.pdf',ROOT/'docs/research/alpha-genesis-flywheel-omega.pdf')
subprocess.run(['python3','-m','unittest','discover','-s','tests','-p','test_research_site.py','-v'],cwd=ROOT,check=True)
subprocess.run(['node','--test','tests/test_alpha_site.cjs'],cwd=ROOT,check=True)
shutil.rmtree(TRANSPORT)
(ROOT/'.github/workflows/genesis-publication-materialize.yml').unlink()
print('Approved public revision and PDF verified; temporary transport removed.')
