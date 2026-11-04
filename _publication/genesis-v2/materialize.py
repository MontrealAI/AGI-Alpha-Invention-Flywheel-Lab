"""One-time exact-byte publication of the authorized research companion."""
import hashlib,io,shutil,subprocess,tempfile,zipfile,os
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[2]
data=(ROOT/'docs/alpha-genesis/ALPHA_GENESIS_FLYWHEEL_OMEGA_v2_COMPLETE.zip').read_bytes()
if len(data)!=1656245 or hashlib.sha256(data).hexdigest()!='50e7cb5b16de095eb1657c929bde9915b03284130f664f2fbae65cdd4a898feb': raise ValueError('Authorized ZIP identity mismatch')
with tempfile.TemporaryDirectory() as temp:
 base=Path(temp)
 with zipfile.ZipFile(io.BytesIO(data)) as z:
  infos=z.infolist()
  if len(infos)!=68 or sum(i.file_size for i in infos)!=1943592: raise ValueError('Inventory mismatch')
  for i in infos:
   p=PurePosixPath(i.filename)
   if p.is_absolute() or '..' in p.parts or '\\' in i.filename or i.is_dir() or (i.external_attr>>16)&0o170000==0o120000 or p.parts[0]!='ALPHA_GENESIS_FLYWHEEL_OMEGA_v2': raise ValueError('Unsafe archive member')
   target=base/i.filename;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(i))
 source=base/'ALPHA_GENESIS_FLYWHEEL_OMEGA_v2'
 subprocess.run(['python3','verify_release.py'],cwd=source,check=True)
 env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
 for folder in ('analysis','reproduction/decision_v01','reproduction/composition_001'):
  args=['python3','-m','unittest','discover','-s','tests','-v'] if folder!='analysis' else ['python3','-m','unittest','-v']
  subprocess.run(args,cwd=source/folder,env=env,check=True)
 pdf=source/'ALPHA_GENESIS_FLYWHEEL_OMEGA_v2.pdf'
 if hashlib.sha256(pdf.read_bytes()).hexdigest()!='4bd6400c247b5fea0d336e2cba11e69890b0596e24ebd51931ada257fe78414f': raise ValueError('PDF mismatch')
 target=ROOT/'docs/alpha-genesis/v2.0'
 if target.exists(): raise ValueError('Never overwrite an existing edition')
 shutil.copytree(source,target)
 shutil.copyfile(pdf,ROOT/'docs/research/alpha-genesis-flywheel-omega-v2.pdf')
subprocess.run(['python3','-m','unittest','discover','-s','tests','-p','test_research_site.py','-v'],cwd=ROOT,check=True)
subprocess.run(['node','--test','tests/test_alpha_site.cjs'],cwd=ROOT,check=True)
shutil.rmtree(ROOT/'_publication/genesis-v2')
(ROOT/'.github/workflows/genesis-v2-publication.yml').unlink()
print('Exact edition2 published; prior edition preserved; temporary workflow removed.')
