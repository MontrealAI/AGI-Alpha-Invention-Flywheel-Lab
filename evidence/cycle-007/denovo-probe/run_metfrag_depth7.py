from pathlib import Path
import hashlib,json,resource,subprocess,time,sys
base=Path('/workspace/scratch/92d546ab6009/denovo_probe');data=json.loads((base/'anonymous-input.json').read_text());out=base/'strong-depth7';java=base/'tools/jdk-21.0.13+9-jre/bin/java';jar=base/'tools/MetFragCommandLine-2.6.11.jar';sdf=base/'enumeration/C7H17N.sdf';receipts=[];prepare_only='--prepare-only'in sys.argv
if not prepare_only and(out/'receipts.json').exists():raise FileExistsError('refuse receipt overwrite')
for query in data['queries']:
 qid=query['query_id'];peaks=[]
 for obs in query['observations']:
  total=sum(p[1]for p in obs['peaks']);peaks.extend((mz,intensity/total)for mz,intensity in obs['peaks']if intensity>0)
 peaks.sort();clusters=[]
 for mz,intensity in peaks:
  if not clusters or mz-clusters[-1][0][0]>0.001:clusters.append([])
  clusters[-1].append((mz,intensity))
 merged=[(sum(m*i for m,i in c)/sum(i for m,i in c),sum(i for m,i in c))for c in clusters];peakpath=out/f'{qid}.peaks.txt';peakpath.write_text(''.join(f'{mz:.8f} {i:.12f}\n'for mz,i in merged));result=out/qid;result.mkdir(exist_ok=True)
 if not prepare_only and any(result.iterdir()):raise FileExistsError('refuse result overwrite')
 settings={'PeakListPath':str(peakpath),'MetFragDatabaseType':'LocalSDF','LocalDatabasePath':str(sdf),'NeutralPrecursorMolecularFormula':query['formula'],'NeutralPrecursorMass':query['neutral_monoisotopic_mass'],'FragmentPeakMatchAbsoluteMassDeviation':0.001,'FragmentPeakMatchRelativeMassDeviation':5,'PrecursorIonMode':1,'IsPositiveIonMode':'True','MetFragScoreTypes':'FragmenterScore','MetFragScoreWeights':'1.0','MetFragCandidateWriter':'CSV','SampleName':qid,'ResultsPath':str(result),'NumberThreads':2,'MaximumTreeDepth':7};params=out/f'{qid}.params';params.write_text(''.join(f'{k} = {v}\n'for k,v in settings.items()))
 if prepare_only:continue
 cmd=[str(java),'-XX:ActiveProcessorCount=2','-Xmx1024m','-Djava.net.useSystemProxies=false','-Dhttp.proxyHost=127.0.0.1','-Dhttp.proxyPort=9','-Dhttps.proxyHost=127.0.0.1','-Dhttps.proxyPort=9','-jar',str(jar),str(params)];before=resource.getrusage(resource.RUSAGE_CHILDREN);t=time.perf_counter();p=subprocess.run(cmd,capture_output=True,text=True,timeout=90,preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_CPU,(90,95)));after=resource.getrusage(resource.RUSAGE_CHILDREN);log=p.stdout+p.stderr;(out/f'{qid}.log').write_text(log);r={'query_id':qid,'command':cmd,'returncode':p.returncode,'wall_seconds':time.perf_counter()-t,'child_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'settings':settings,'pooled_peak_count':len(merged),'params_sha256':hashlib.sha256(params.read_bytes()).hexdigest(),'log_sha256':hashlib.sha256(log.encode()).hexdigest(),'input_sha256':hashlib.sha256((base/'anonymous-input.json').read_bytes()).hexdigest(),'sdf_sha256':hashlib.sha256(sdf.read_bytes()).hexdigest(),'metfrag_jar_sha256':hashlib.sha256(jar.read_bytes()).hexdigest(),'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};receipts.append(r);(out/'receipts.json').write_text(json.dumps(receipts,indent=2)+'\n');print(json.dumps({k:r[k]for k in ['query_id','returncode','wall_seconds','child_cpu_seconds','pooled_peak_count']}),flush=True)
