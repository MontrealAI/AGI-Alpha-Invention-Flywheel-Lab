import argparse,hashlib,json,math,resource,subprocess,time
from pathlib import Path

TOOLS={'MAYGEN-1.8.jar':{'sha256':'d3ef19a6d97624df82027846ab81abb6a62de0cc72be274dfe6f7506d41b72c4','url':'https://github.com/MehmetAzizYirik/MAYGEN/releases/download/V1.8/MAYGEN-1.8.jar','license':'MIT'},'MetFragCommandLine-2.6.11.jar':{'sha256':'8c55322fbc706c76df109dd886257262029695837bb1fb2211d4b88d945d8cfb','url':'https://github.com/ipb-halle/MetFragRelaunched/releases/download/v2.6.11/MetFragCommandLine-2.6.11.jar','license':'LGPL-2.1-or-later'}}
JAVA_CPU_REMAINING=300.0
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def execute(cmd,folder,name):
 global JAVA_CPU_REMAINING
 if JAVA_CPU_REMAINING<1:raise RuntimeError('Java campaign CPU allowance exhausted; existing receipts preserved')
 allowance=min(90,int(JAVA_CPU_REMAINING));budget_before=JAVA_CPU_REMAINING
 before=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.perf_counter();status='COMPLETED'
 try:p=subprocess.run(cmd,capture_output=True,text=True,timeout=90,preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_CPU,(allowance,allowance+1)));code=p.returncode;out=p.stdout;err=p.stderr
 except subprocess.TimeoutExpired as e:code=None;out=e.stdout or b'';err=e.stderr or b'';status='TIMEOUT'
 after=resource.getrusage(resource.RUSAGE_CHILDREN);out=out.decode(errors='replace')if isinstance(out,bytes)else out;err=err.decode(errors='replace')if isinstance(err,bytes)else err;(folder/f'{name}.stdout').write_text(out);(folder/f'{name}.stderr').write_text(err)
 spent=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime;JAVA_CPU_REMAINING-=spent
 receipt={'java_CPU_budget_before':budget_before,'java_CPU_budget_after':JAVA_CPU_REMAINING,'process_CPU_soft_limit':allowance,'command':cmd,'status':status,'returncode':code,'wall_seconds':time.perf_counter()-start,'child_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'stdout_sha256':digest(folder/f'{name}.stdout'),'stderr_sha256':digest(folder/f'{name}.stderr')};save(folder/f'{name}.receipt.json',receipt)
 if code!=0:raise RuntimeError(f'{name} failed; preserved receipt {folder/name}')
 return receipt
def pool(observations):
 peaks=[]
 for observation in observations:
  entries=observation['peaks']
  if not entries or any(not math.isfinite(v)or v<0 for row in entries for v in row):raise ValueError('invalid peak list')
  total=sum(row[1]for row in entries)
  if total<=0:raise ValueError('empty intensity')
  peaks.extend((mz,intensity/total)for mz,intensity in entries if intensity>0)
 peaks.sort();clusters=[]
 for mz,intensity in peaks:
  if not clusters or mz-clusters[-1][0][0]>0.001:clusters.append([])
  clusters[-1].append((mz,intensity))
 return [(sum(m*i for m,i in c)/sum(i for m,i in c),sum(i for m,i in c))for c in clusters]
def run(a):
 data=json.loads(a.input.read_text());queries=data['queries'];formulas={q['formula']for q in queries}
 if formulas!={'C7H17N'}:raise ValueError('qualified scope is the frozen C7H17N development cohort')
 for name,expected in TOOLS.items():
  if digest(a.tools/name)!=expected['sha256']:raise ValueError(f'tool identity mismatch: {name}')
 a.output.mkdir(parents=True,exist_ok=False);save(a.output/'identity.json',{'input_sha256':digest(a.input),'source_sha256':digest(Path(__file__)),'tools':TOOLS,'scope':'Ordinary MAYGEN plus local MetFrag baseline; constitutional graphs only, no chemical identity guarantee.','depth':a.depth,'limits':{'threads':2,'heap_MiB':1024,'CPU_seconds_per_process':90,'wall_seconds_per_process':90}});receipts=[];enum=a.output/'enumeration';enum.mkdir();prefix=[a.java,'-XX:ActiveProcessorCount=2','-Xmx1024m'];receipts.append(execute(prefix+['-jar',str(a.tools/'MAYGEN-1.8.jar'),'-f','C7H17N','-o',str(enum)+'/', '-sdf','-v','-t'],a.output,'enumerate'));sdf=enum/'C7H17N.sdf'
 for q in queries:
  name=q['query_id']
  if not name.isalnum():raise ValueError('invalid query identifier')
  output=a.output/name;output.mkdir();peaks=pool(q['observations']);peakfile=output/'peaks.txt';peakfile.write_text(''.join(f'{mz:.8f} {intensity:.12f}\n'for mz,intensity in peaks));settings={'PeakListPath':str(peakfile),'MetFragDatabaseType':'LocalSDF','LocalDatabasePath':str(sdf),'NeutralPrecursorMolecularFormula':q['formula'],'NeutralPrecursorMass':q['neutral_monoisotopic_mass'],'FragmentPeakMatchAbsoluteMassDeviation':0.001,'FragmentPeakMatchRelativeMassDeviation':5,'PrecursorIonMode':1,'IsPositiveIonMode':'True','MetFragScoreTypes':'FragmenterScore','MetFragScoreWeights':'1.0','MetFragCandidateWriter':'CSV','SampleName':name,'ResultsPath':str(output),'NumberThreads':2,'MaximumTreeDepth':a.depth};param=output/'params.txt';param.write_text(''.join(f'{k} = {v}\n'for k,v in settings.items()));save(output/'PRE_EXECUTION.json',{'settings':settings,'input_sha256':digest(a.input),'params_sha256':digest(param),'peaks_sha256':digest(peakfile),'sdf_sha256':digest(sdf)});cmd=prefix+['-Djava.net.useSystemProxies=false','-Dhttp.proxyHost=127.0.0.1','-Dhttp.proxyPort=9','-Dhttps.proxyHost=127.0.0.1','-Dhttps.proxyPort=9','-jar',str(a.tools/'MetFragCommandLine-2.6.11.jar'),str(param)];receipts.append(execute(cmd,output,'metfrag'))
 save(a.output/'receipts.json',receipts);print(json.dumps({'scope':'ordinary baseline execution only','output':str(a.output),'wall_seconds':sum(r['wall_seconds']for r in receipts),'child_cpu_seconds':sum(r['child_cpu_seconds']for r in receipts)}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--tools',type=Path,required=True);p.add_argument('--java',required=True);p.add_argument('--depth',type=int,choices=[2,3,7],default=2);p.add_argument('--output',type=Path,required=True);run(p.parse_args())
