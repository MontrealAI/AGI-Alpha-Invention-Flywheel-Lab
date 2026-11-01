"""One bounded, source-matched public CI attempt. No remote caches/artifacts."""
import hashlib,json,os,pathlib,shutil,signal,subprocess,sys,time,xml.etree.ElementTree as ET
P=pathlib.Path; HERE=P(__file__).resolve().parent
ROOT=P(os.environ['RUNNER_TEMP'])/'frontier-phase2'; ROOT.mkdir()
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
START=time.monotonic(); deadline=START+2400
receipt={'scope':'separate public CI attempt; local failures unchanged','steps':[]}
def sha(p):return hashlib.sha256(P(p).read_bytes()).hexdigest()
def save():
 receipt['setup_build_elapsed_seconds']=time.monotonic()-START
 (ROOT/'build_receipt.json').write_text(json.dumps(receipt,indent=2))
def run(label,cmd,cwd=ROOT):
 start=time.monotonic(); log=ROOT/(label+'.log')
 with log.open('w') as f:
  p=subprocess.Popen(cmd,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
  try:code=p.wait(timeout=max(1,deadline-time.monotonic()))
  except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait();code=124
 receipt['steps'].append({'label':label,'command':cmd,'exit':code,'seconds':time.monotonic()-start});save()
 print(label,code,log.read_text()[-14000:],flush=True)
 if code:raise RuntimeError(label+' failed')
 return log.read_text()
try:
 source=ROOT/'source';run('init',['git','init',str(source)])
 run('fetch',['git','fetch','--depth=1','https://github.com/quantumlib/tesseract-decoder.git','838d4f64acc16b5c15adda01302a719400329d4b'],source)
 run('checkout',['git','checkout','--detach','FETCH_HEAD'],source)
 receipt['patch_sha256']=sha(HERE/'terminal_list.patch')
 receipt['protocol_sha256']=sha(HERE/'FROZEN_PROTOCOL.md')
 receipt['source_commit']=run('source_identity',['git','rev-parse','HEAD'],source).strip()
 run('tools',['curl','--fail','--location','--proto','=https','--tlsv1.2','--output',str(ROOT/'bazelisk'),'https://github.com/bazelbuild/bazelisk/releases/download/v1.30.0/bazelisk-linux-amd64'])
 assert sha(ROOT/'bazelisk')=='a248ae2b2b62b5baebb748f6fba7203bff1a27e5d01b55399a8406744cb539e8'
 (ROOT/'bazelisk').chmod(0o755)
 os.environ.update(USE_BAZEL_VERSION='9.3.1',BAZELISK_HOME=str(ROOT/'bazelisk-home'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
 run('python_deps',[sys.executable,'-m','pip','install','--disable-pip-version-check','--no-cache-dir','--target',str(ROOT/'deps'),'stim==1.16.0','numpy==2.5.4','scipy==1.18.1'])
 receipt['compiler']=run('compiler',['g++','--version']);receipt['python']=sys.version
 bazel=[str(ROOT/'bazelisk'),'--batch','--nosystem_rc','--nohome_rc','--host_jvm_args=-Xmx256m','--host_jvm_args=-XX:ActiveProcessorCount=1','--output_user_root='+str(ROOT/'bazel-output')]
 flags=['--jobs=1','--loading_phase_threads=1','--local_resources=cpu=1','--local_resources=memory=512','--config=wheel','--repo_env=PYTHON_BIN_PATH='+sys.executable,'--repository_cache='+str(ROOT/'repository-cache'),'--remote_cache=','--remote_executor=']
 run('pristine_build',bazel+['build']+flags+['//src:tesseract_decoder','//src:tesseract_tests'],source)
 bazels=list((ROOT/'bazelisk-home').rglob('bin/bazel'));assert len(bazels)==1
 assert sha(bazels[0])=='7f775b54bbec487efaf0f49ccda1d2ed02cd34f582edfdd6aeeec76e39ef585c'
 receipt['bazel_sha256']=sha(bazels[0]);receipt['lock_pristine']=sha(source/'MODULE.bazel.lock')
 pristine=ROOT/'pristine';pristine.mkdir()
 for f in (source/'bazel-bin/src').glob('tesseract_decoder*.so'):shutil.copy2(f,pristine/f.name)
 assert list(pristine.glob('*.so'))
 regression='tesseract.DecoderErrorIndexMapsAreInOriginalDemCoordinates:tesseract.DecodersStripZeroProbabilityErrors:tesseract.DecodeToErrorsThrowsOnInvalidSymptom'
 run('pristine_regressions',bazel+['test']+flags+['--test_filter='+regression,'--test_output=all','--test_timeout=120','//src:tesseract_tests'],source)
 run('apply',['git','apply','--check',str(HERE/'terminal_list.patch')],source)
 run('patch',['git','apply',str(HERE/'terminal_list.patch')],source)
 run('modified_build',bazel+['build']+flags+['//src:tesseract_decoder','//src:tesseract_tests'],source)
 receipt['lock_modified']=sha(source/'MODULE.bazel.lock');assert receipt['lock_pristine']==receipt['lock_modified']
 receipt['extensions']={kind:[{'name':f.name,'sha256':sha(f)} for f in (ROOT/kind).glob('*.so')] for kind in ['pristine']}
 modified=ROOT/'modified';modified.mkdir()
 for f in (source/'bazel-bin/src').glob('tesseract_decoder*.so'):shutil.copy2(f,modified/f.name)
 run('cpp_tests',bazel+['test']+flags+['--test_filter=TesseractCandidateList.*:'+regression,'--test_output=all','--test_timeout=120','//src:tesseract_tests'],source)
 testxml=ET.parse(source/'bazel-testlogs/src/tesseract_tests/test.xml')
 cases=testxml.findall('.//testcase');assert len(cases)>=9 and not testxml.findall('.//failure')
 receipt['cpp_tests_executed']=[x.attrib.get('name') for x in cases]
 receipt['extensions']['modified']=[{'name':f.name,'sha256':sha(f)} for f in modified.glob('*.so')]
 run('interface_tests',[sys.executable,str(HERE/'check_list_api.py'),'--extension-dir',str(modified),'--helper-dir',str(source/'src/py'),'--deps',str(ROOT/'deps')])
 # Cross-build first-goal regression is supplied alongside the frozen harness.
 run('cross_build_tests',[sys.executable,str(HERE/'check_pristine_equivalence.py'),'--pristine-extension-dir',str(pristine),'--modified-extension-dir',str(modified),'--helper-dir',str(source/'src/py'),'--deps',str(ROOT/'deps')])
 receipt['status']='BUILD_AND_CORRECTNESS_PASS';save()
except Exception as e:
 receipt['status']='FAIL';receipt['error']=str(e);save();raise
finally:
 print('BUILD_RECEIPT_JSON='+json.dumps(receipt),flush=True)
