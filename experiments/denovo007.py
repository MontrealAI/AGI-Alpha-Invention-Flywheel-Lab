import argparse,hashlib,json,os,sys,tarfile,time,urllib.request
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent))
from denovo_baseline007 import TOOLS,run

JRE={'file':'temurin21-jre.tar.gz','url':'https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.13%2B9/OpenJDK21U-jre_x64_linux_hotspot_21.0.13_9.tar.gz','sha256':'a535a1df9c6284d9618872984e026ae0352d1f7e9e0605425c0e6114f47351dd','directory':'jdk-21.0.13+9-jre','license':'GPL-2.0-only WITH Classpath-exception-2.0'}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prepare(folder,download):
 folder.mkdir(parents=True,exist_ok=True);receipts=[]
 for name,info in [*TOOLS.items(),(JRE['file'],JRE)]:
  path=folder/name;start=time.perf_counter();cached=path.exists()
  if not cached:
   if not download:raise FileNotFoundError(f'{path}; use --download-tools for the pinned free public tools')
   partial=folder/f'{name}.partial-{time.time_ns()}'
   with urllib.request.urlopen(info['url'],timeout=60)as response,partial.open('xb')as writer:
    while block:=response.read(1024*1024):writer.write(block)
   if digest(partial)!=info['sha256']:raise ValueError(f'download identity mismatch; partial preserved at {partial}')
   partial.rename(path)
  if digest(path)!=info['sha256']:raise ValueError(f'cached tool identity mismatch: {path}')
  receipts.append({'file':name,'url':info['url'],'sha256':info['sha256'],'bytes':path.stat().st_size,'cached':cached,'wall_seconds':time.perf_counter()-start})
 target=folder/JRE['directory']
 if not target.exists():
  with tarfile.open(folder/JRE['file'])as archive:archive.extractall(folder,filter='data')
 java=target/'bin/java'
 with tarfile.open(folder/JRE['file'])as archive:expected=hashlib.sha256(archive.extractfile(JRE['directory']+'/bin/java').read()).hexdigest()
 if digest(java)!=expected:raise ValueError('Java executable differs from pinned distribution')
 os.chmod(java,java.stat().st_mode|0o100);return str(java),receipts
def main(a):
 if a.output.exists():raise FileExistsError(a.output)
 a.tools_dir=a.tools_dir.resolve();a.input=a.input.resolve();a.output=a.output.resolve();java,downloads=prepare(a.tools_dir,a.download_tools);a.output.mkdir(parents=True,exist_ok=False);identity={'source_sha256':digest(Path(__file__)),'helper_sha256':digest(Path(__file__).with_name('denovo_baseline007.py')),'input_sha256':digest(a.input),'tool_downloads':downloads,'java_archive':JRE,'scope':'Existing MAYGEN+MetFrag complete local baseline, depth2primary/depth3secondary/depth7strongconventional; all same anonymous real inputs. No chemical identity or calibrated coverage claim.'};(a.output/'RUN_IDENTITY.json').write_text(json.dumps(identity,indent=2)+'\n')
 for depth in a.depths:run(SimpleNamespace(input=a.input,tools=a.tools_dir,java=java,depth=depth,output=a.output/f'depth-{depth}'))
 manifest={str(p.relative_to(a.output)):digest(p)for p in a.output.rglob('*')if p.is_file()};(a.output/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,default=Path(__file__).resolve().parents[1]/'evidence/cycle-007/denovo-probe/anonymous-input.json');p.add_argument('--tools-dir',type=Path,required=True);p.add_argument('--download-tools',action='store_true');p.add_argument('--depths',type=int,nargs='+',choices=[2,3,7],default=[2,3,7]);p.add_argument('--output',type=Path,required=True);main(p.parse_args())
