import hashlib,json,math,time,zipfile
from collections import Counter
from pathlib import Path,PurePosixPath

root=Path(__file__).resolve().parent
archive=root/'data/joint_assembly_rotation.zip'
started=time.perf_counter()
cases={}
with zipfile.ZipFile(archive) as z:
    if sum(i.file_size for i in z.infolist())>32_000_000: raise ValueError('uncompressed budget')
    for info in z.infolist():
        p=PurePosixPath(info.filename)
        if '..' in p.parts or p.is_absolute(): raise ValueError('unsafe member')
        if info.is_dir() or p.suffix!='.obj': continue
        if info.file_size>4_000_000: raise ValueError('member budget')
        vs=[];fs=[]
        for line in z.read(info).decode('ascii').splitlines():
            t=line.split()
            if not t: continue
            if t[0]=='v':
                v=tuple(map(float,t[1:4]))
                if len(v)!=3 or not all(math.isfinite(x) for x in v): raise ValueError('vertex')
                vs.append(v)
            elif t[0]=='f':
                f=tuple(int(x.split('/')[0])-1 for x in t[1:])
                if len(f)!=3: raise ValueError('nontriangle')
                fs.append(f)
            if len(vs)>100000 or len(fs)>200000: raise ValueError('geometry budget')
        if not vs or not fs or any(min(f)<0 or max(f)>=len(vs) for f in fs): raise ValueError('indices')
        edges=Counter(tuple(sorted((f[i],f[(i+1)%3]))) for f in fs for i in range(3))
        item={'path':str(p),'sha256':hashlib.sha256(z.read(info)).hexdigest(),'vertices':len(vs),'triangles':len(fs),'edge_incidence_not_two':sum(n!=2 for n in edges.values()),'bounds':[[min(v[j] for v in vs) for j in range(3)],[max(v[j] for v in vs) for j in range(3)]]}
        cases.setdefault(str(p.parent),[]).append(item)
out={'scope':'data readiness only; no motion baseline, collision, physical or commercial claim','source':'https://people.csail.mit.edu/yunsheng/Assemble-Them-All/dataset_2403/joint_assembly_rotation.zip','archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'archive_bytes':archive.stat().st_size,'case_count':len(cases),'categories':dict(Counter(PurePosixPath(c).parts[1] for c in cases)),'part_count':sum(map(len,cases.values())),'all_cases_have_two_parts':all(len(x)==2 for x in cases.values()),'cases':cases,'elapsed_seconds':time.perf_counter()-started,'license':'Fusion360-derived data limited to noncommercial research; do not redistribute whole corpus','baseline_status':'NOT EXECUTED: native RedMax not qualified in this environment','next':'Run full current rotation-capable baseline in qualified native isolation, then test protected residual failures against identical CAD, tolerance and obligations.'}
(root/'DATA_READINESS.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='cases'},indent=2))
