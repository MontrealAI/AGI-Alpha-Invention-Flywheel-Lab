"""Deterministic standalone bridge package; no financial/repository fallback."""
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, re, stat, subprocess, sys, time, venv, zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
LOCK='campaign/genesis-execution-bridge/SOURCE_LOCK.json'
EXTRAS=(LOCK,'scripts/release_genesis_bridge.py','tests/test_genesis_bridge_package.py',
        'campaign/genesis-execution-bridge/PACKAGE_PROTOCOL.md')
MAX_FILES=64
MAX_BYTES=2*1024*1024
MANIFEST='BRIDGE_PACKAGE_MANIFEST.json'

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def loads(b):
 def pairs(rows):
  d={}
  for k,v in rows:
   if k in d:raise ValueError('duplicate JSON key')
   d[k]=v
  return d
 return json.loads(b,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
def write(p,b):
 with pathlib.Path(p).open('xb') as f:f.write(b)
def safe_path(p):
 p=pathlib.Path(p).absolute()
 if any(x.is_symlink() for x in [p,*p.parents]):raise ValueError('symlink path refused')
 return p
def commit(s):
 if not isinstance(s,str) or re.fullmatch('[0-9a-f]{40}',s) is None:raise ValueError('full commit required')
 return s
def member(name):
 p=pathlib.PurePosixPath(name)
 if not name or '\\' in name or p.is_absolute() or '..' in p.parts or p.as_posix()!=name or name.endswith('/'):
  raise ValueError('unsafe archive member')
 return name
def inventory(root):
 root=safe_path(root);lock=loads((root/LOCK).read_bytes())
 if lock.get('schema')!='bridge-source-lock/v1' or not isinstance(lock.get('sha256'),dict):raise ValueError('source lock schema')
 names=set(lock['sha256'])|set(EXTRAS)
 if len(names)>MAX_FILES:raise ValueError('file bound')
 data={}
 for name in sorted(names):
  member(name);p=safe_path(root/name)
  if not p.is_file():raise ValueError('missing regular source: '+name)
  b=p.read_bytes()
  if name in lock['sha256'] and sha(b)!=lock['sha256'][name]:raise ValueError('source lock mismatch: '+name)
  data[name]=b
 if sum(map(len,data.values()))>MAX_BYTES:raise ValueError('byte bound')
 return data,lock

def build(root,out,source_commit):
 source_commit=commit(source_commit);root=safe_path(root);out=safe_path(out)
 data,lock=inventory(root);out.mkdir(parents=True,exist_ok=False)
 m={'schema':'genesis-bridge-standalone/v1','source_commit':source_commit,'source_binding':'caller supplies exact checked-out commit; workflow verifies HEAD',
    'source_lock_sha256':sha(canonical(lock)),'files':{p:sha(b) for p,b in data.items()},
    'license_status':'No root LICENSE or NOTICE is declared in this package; no new license grant is made.',
    'scope':'offline finite synthetic bridge, no ledger, no actual commerce or physical validation'}
 encoded=canonical(m)+b'\n'
 with zipfile.ZipFile(out/'genesis-bridge-source.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p,b in [*data.items(),(MANIFEST,encoded)]:
   info=zipfile.ZipInfo(p,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=(stat.S_IFREG|0o644)<<16
   z.writestr(info,b)
 archive_sha=sha((out/'genesis-bridge-source.zip').read_bytes())
 write(out/'PACKAGE_MANIFEST.json',encoded)
 write(out/'SHA256SUMS.txt',(archive_sha+'  genesis-bridge-source.zip\n'+sha(encoded)+'  PACKAGE_MANIFEST.json\n').encode())
 return {'archive_sha256':archive_sha,'source_commit':source_commit,'files':len(data),'uncompressed_bytes':sum(map(len,data.values()))}

def extract(archive,out,expected_sha,source_commit):
 source_commit=commit(source_commit);archive=safe_path(archive);out=safe_path(out)
 if re.fullmatch('[0-9a-f]{64}',expected_sha or '') is None:raise ValueError('external expected archive SHA256 required')
 if archive.stat().st_size>MAX_BYTES:raise ValueError('compressed byte bound')
 raw=archive.read_bytes()
 if sha(raw)!=expected_sha:raise ValueError('download checksum mismatch')
 with zipfile.ZipFile(archive) as z:
  infos=z.infolist();names=[member(x.filename) for x in infos]
  if len(names)!=len(set(names)) or len(names)>MAX_FILES or sum(x.file_size for x in infos)>MAX_BYTES:
   raise ValueError('duplicate or oversized archive')
  for x in infos:
   mode=x.external_attr>>16
   if not stat.S_ISREG(mode) or x.flag_bits&1:raise ValueError('nonregular or encrypted archive member')
  if MANIFEST not in names:raise ValueError('manifest absent')
  m=loads(z.read(MANIFEST))
  if m.get('schema')!='genesis-bridge-standalone/v1' or m.get('source_commit')!=source_commit:raise ValueError('manifest identity mismatch')
  if set(names)!=set(m['files'])|{MANIFEST}:raise ValueError('archive inventory mismatch')
  data={p:z.read(p) for p in m['files']}
  if any(sha(b)!=m['files'][p] for p,b in data.items()):raise ValueError('member checksum mismatch')
  lock=loads(data[LOCK])
  if sha(canonical(lock))!=m['source_lock_sha256']:raise ValueError('lock identity mismatch')
  if set(data)!=set(lock['sha256'])|set(EXTRAS):raise ValueError('exact closure mismatch')
  if any(sha(data[p])!=h for p,h in lock['sha256'].items()):raise ValueError('locked dependency mismatch')
 out.mkdir(parents=True,exist_ok=False)
 for p,b in data.items():
  target=out/p;target.parent.mkdir(parents=True,exist_ok=True);write(target,b)
 write(out/MANIFEST,canonical(m)+b'\n')
 return m

def qualify(archive,out,expected_sha,source_commit):
 out=safe_path(out);out.mkdir(parents=True,exist_ok=False)
 source=out/'source';receipt={'schema':'genesis-bridge-downloaded-qualification/v1','source_commit':commit(source_commit),
  'archive_sha256':expected_sha,'accepted':False,'commands':[],'monetary_cost':None,
  'coverage':'subprocess wall only; bridge outputs contain adapter/checker CPU/RSS; excludes development and actual host/model billing'}
 try:
  m=extract(archive,source,expected_sha,source_commit)
  venv.EnvBuilder(with_pip=False,symlinks=True,system_site_packages=False).create(out/'runtime')
  interpreter=out/'runtime/bin/python'
  receipt['runtime_isolation']='fresh venv without pip or system site-packages; trusted interpreter symlink only; loaded bridge/instrument/checker origins asserted inside extraction'
  (out/'tmp').mkdir()
  # Absolute isolated interpreter; deliberately remove repository paths and environment Python paths.
  prefix="import pathlib,sys; root=pathlib.Path.cwd().resolve(); sys.path.insert(0,str(root)); from research.genesis_bridge import core; core.verify_sources(); from research.genesis097 import instrument,check,replay,direct; assert all(pathlib.Path(m.__file__).resolve().is_relative_to(root) for m in (core,instrument,check,replay,direct)); "
  jobs=[('bridge_tests',prefix+"import unittest; suite=unittest.defaultTestLoader.loadTestsFromName('research.genesis_bridge.test_bridge'); result=unittest.TextTestRunner(verbosity=2).run(suite); sys.exit(not result.wasSuccessful())"),
        ('package_tests',prefix+"import unittest; suite=unittest.defaultTestLoader.discover('tests',pattern='test_genesis_bridge_package.py'); result=unittest.TextTestRunner(verbosity=2).run(suite); sys.exit(not result.wasSuccessful())"),
        ('bridge_demo',prefix+"from research.genesis_bridge.demo import run_demo; r=run_demo(pathlib.Path(sys.argv[1])); print(r['same_kernel_equal_outputs'])")]
  for name,program in jobs:
   before=time.monotonic();args=[str(interpreter),'-I','-B','-c',program]
   if name=='bridge_demo':args.append(str(out/'operation'))
   p=subprocess.run(args,cwd=source,env={'PATH':os.defpath,'PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(out/'tmp')},capture_output=True,timeout=300)
   write(out/(name+'.stdout'),p.stdout);write(out/(name+'.stderr'),p.stderr)
   receipt['commands'].append({'name':name,'exit_code':p.returncode,'wall_seconds':time.monotonic()-before,'stdout_sha256':sha(p.stdout),'stderr_sha256':sha(p.stderr),'cwd':'extracted source only','isolated_interpreter':True})
   if p.returncode:raise ValueError('extracted command failed: '+name)
  summary=loads((out/'operation/SUMMARY.json').read_bytes())
  if summary['source_lock_sha256']!=m['source_lock_sha256'] or not summary['same_kernel_equal_outputs'] or len(summary['successors'])!=12 or any(x['acceptance']!='PASS' for x in summary['successors']):raise ValueError('fixed reproduction mismatch')
  receipt.update(accepted=True,source_lock_sha256=m['source_lock_sha256'],summary=summary,
    scope='actual extracted package operation, not a release claim absent separate download provenance')
 except Exception as e:
  receipt['error']=type(e).__name__+': '+str(e)
 finally:write(out/'QUALIFICATION.json',canonical(receipt)+b'\n')
 return receipt

def main():
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
 b=s.add_parser('build');b.add_argument('--source',type=pathlib.Path,required=True);b.add_argument('--out',type=pathlib.Path,required=True);b.add_argument('--source-commit',required=True)
 q=s.add_parser('qualify');q.add_argument('--archive',type=pathlib.Path,required=True);q.add_argument('--out',type=pathlib.Path,required=True);q.add_argument('--source-commit',required=True);q.add_argument('--expected-sha',required=True)
 a=p.parse_args()
 result=build(a.source,a.out,a.source_commit) if a.command=='build' else qualify(a.archive,a.out,a.expected_sha,a.source_commit)
 print(json.dumps(result if a.command=='build' else {k:result.get(k) for k in ('accepted','source_commit','archive_sha256','error')}))
 if a.command=='qualify' and not result['accepted']:raise SystemExit(1)
if __name__=='__main__':main()
