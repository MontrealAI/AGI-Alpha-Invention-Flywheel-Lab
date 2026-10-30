"""Execute the unchanged numerical NASA repair from downloaded public contents.

Engineering reproduction only; no new physical or commercial qualification.
"""
import argparse,hashlib,json,math,os,resource,subprocess,sys,tarfile,time
from pathlib import Path,PurePosixPath


def extract(path,commit,expected,output):
    expected=json.loads(Path(expected).read_text());output.mkdir(parents=True,exist_ok=False);found={};size=0
    with tarfile.open(path,'r:gz') as archive:
        for item in archive:
            p=PurePosixPath(item.name)
            if not p.parts or p.parts[0]!='AGI-Alpha-Invention-Flywheel-Lab-'+commit or p.is_absolute() or '..' in p.parts or '\\' in item.name:raise ValueError('ARCHIVE_PATH')
            if item.isdir():continue
            name=PurePosixPath(*p.parts[1:]).as_posix();size+=item.size
            if not item.isfile() or name not in expected or name in found or size>512*1024**2 or len(found)>=20000:raise ValueError('ARCHIVE_SCOPE')
            raw=archive.extractfile(item).read();blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
            if blob!=expected[name]:raise ValueError('GIT_BLOB_CHANGED')
            target=output/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw);found[name]=hashlib.sha256(raw).hexdigest()
    if set(found)!=set(expected):raise ValueError('GIT_TREE_INCOMPLETE')
    return found


def main():
    p=argparse.ArgumentParser();p.add_argument('--source-archive',required=True);p.add_argument('--source-commit',required=True);p.add_argument('--source-tree',required=True);p.add_argument('--data-archive',required=True);p.add_argument('--data-commit',required=True);p.add_argument('--data-tree',required=True);p.add_argument('--ct',required=True);p.add_argument('--profile',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    out=Path(a.output).absolute();out.mkdir(parents=True,exist_ok=False);start=time.monotonic();parent_start=time.process_time()
    soft,hard=resource.getrlimit(resource.RLIMIT_CPU);resource.setrlimit(resource.RLIMIT_CPU,(min(20,soft),hard))
    source=out/'downloaded-source';data=out/'downloaded-data';sf=extract(a.source_archive,a.source_commit,a.source_tree,source);df=extract(a.data_archive,a.data_commit,a.data_tree,data);runs=[]
    def call(name,args,cpu,wall):
        def bounds():
            resource.setrlimit(resource.RLIMIT_CPU,(cpu,cpu));resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30))
        before=resource.getrusage(resource.RUSAGE_CHILDREN);t=time.monotonic()
        with (out/(name+'.stdout.log')).open('xb')as stdout,(out/(name+'.stderr.log')).open('xb')as stderr:
            r=subprocess.run([sys.executable,*map(str,args)],cwd=source,stdout=stdout,stderr=stderr,timeout=wall,preexec_fn=bounds,start_new_session=True)
        after=resource.getrusage(resource.RUSAGE_CHILDREN);runs.append({'phase':name,'returncode':r.returncode,'waited_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'wall_seconds':time.monotonic()-t,'cpu_limit':cpu})
        (out/'PHASES.json').write_text(json.dumps(runs,indent=2)+'\n')
        if r.returncode:raise ValueError('PHASE_FAILED '+name)
    old=out/'restore/original47';repaired=out/'repaired';review=out/'separate-review'
    call('restore',[source/'scripts/restore_nasa_original008.py','--source',source/'research/nasa008/development','--archive',data,'--ct',Path(a.ct).absolute(),'--profile',Path(a.profile).absolute(),'--output',out/'restore'],60,180)
    call('repair',[source/'research/nasa008/coordinate-r2/repair.py','--old',old,'--output',repaired],60,180)
    call('separate-review',[source/'evidence/overnight-008/verifier-final-repair/check_nasa_coordinate_repair.py','--old',old,'--repair',source/'research/nasa008/coordinate-r2','--records',repaired,'--output',review],20,60)
    checked=json.loads((review/'REPORT.json').read_text())
    unchanged=all(hashlib.sha256((source/n).read_bytes()).hexdigest()==h for n,h in sf.items()) and all(hashlib.sha256((data/n).read_bytes()).hexdigest()==h for n,h in df.items())
    if not unchanged or checked.get('all_checks_passed') is not True:raise ValueError('SOURCE_OR_SEPARATE_CHECK_FAILED')
    report={'schema':'agi-alpha/downloaded-nasa-numerical-repair008/v1','source_commit':a.source_commit,'data_commit':a.data_commit,'source_files':len(sf),'data_files':len(df),'all_git_blobs_verified_before_execution':True,'source_bytes_unchanged':unchanged,'restored':json.loads((out/'restore/REPORT.json').read_text()),'separate_review':checked,'phases':runs,'parent_cpu_seconds':time.process_time()-parent_start,'wall_seconds':time.monotonic()-start,'scope':'Actual original47 restoration, unchanged physical-coordinate numerical repair and separate fixed checker from downloaded public contents. No protected scientific confirmation, physical uncertainty, enabling superiority or commercial success.'}
    (out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'source_bytes_unchanged':unchanged,'phases':len(runs),'review_keys':list(checked)}))
if __name__=='__main__':main()
