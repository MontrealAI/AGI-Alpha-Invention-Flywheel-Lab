from pathlib import Path
import hashlib,json,time,resource
p=Path(__file__).parent;t=time.perf_counter();b=(p/'PAX2.k63.gfa').read_bytes();S={};L=[]
for z in b.decode().splitlines():
 a=z.split('\t')
 if a[0]=='S':S[a[1]]=a[2]
 if a[0]=='L':L.append(a)
rc=lambda s:s.translate(str.maketrans('ACGT','TGCA'))[::-1]
bad=[]
for a in L:
 x=S[a[1]] if a[2]=='+' else rc(S[a[1]]);y=S[a[3]] if a[4]=='+' else rc(S[a[3]])
 if x[-62:]!=y[:62]:bad.append(a)
out={'scope':'real published human PAX2 graph ingestion/overlap check; not biological quantification or rank-identifiability test','source_commit':'97bd0aa5592304155dafc236de1c123603d33ed3','source_path':'Figures/SupplementalFigure5/bifrost_LRGASP.human.PAX2.k-63.gfa','git_blob':hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest(),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'segments':len(S),'directed_links':len(L),'overlap_violations':len(bad),'transcript_paths_supplied':sum(z.startswith(b'P\t') for z in b.splitlines()),'quantification_baseline_executed':False,'reason':'No kallisto installed; official SIRV ZIP access returned403; public GFA lacks transcript path labels, so no abundance/identifiability inference is valid','wall_seconds':time.perf_counter()-t,'cpu_seconds':resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime}
(p/'RESULT.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
