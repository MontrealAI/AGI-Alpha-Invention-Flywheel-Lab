import hashlib,json,os,resource,subprocess,sys,tempfile,time
from pathlib import Path

def sha(b): return hashlib.sha256(b).hexdigest()
def inventory(root): return {str(p.relative_to(root)):sha(p.read_bytes()) for p in sorted(root.rglob('*')) if p.is_file()}
def invoke(root,shadow,code):
    return subprocess.run([sys.executable,'-I','-S','-B','-c',code,str(root)],env={**os.environ,'PYTHONPATH':str(shadow)},capture_output=True,text=True,timeout=10)
READ="""import sys,json,hashlib,pathlib
r=pathlib.Path(sys.argv[1]);sys.path.insert(0,str(r))
from sample import worker
print(json.dumps({'value':worker.VALUE,'origin':worker.__file__,'job':hashlib.sha256((r/'job.json').read_bytes()).hexdigest()},sort_keys=True))
"""
CHECK=READ+"""import subprocess,os,errno
nested=subprocess.run([sys.executable,'-I','-S','-B','-c',"""+repr(READ)+""",str(r)],capture_output=True,text=True,check=True)
checks={}
for p in (r/'new',r/'job.json'):
 try:p.write_bytes(b'changed')
 except OSError as e:checks[p.name]=e.errno==errno.EROFS
 else:checks[p.name]=False
remount=subprocess.run(['mount','-o','remount,rw',str(r)],capture_output=True,text=True)
print(json.dumps({'nested':json.loads(nested.stdout),'writes_denied':checks,'remount_denied':remount.returncode!=0,'caps':next(x.strip() for x in pathlib.Path('/proc/self/status').read_text().splitlines() if x.startswith('CapEff:')),'no_new_privs':next(x.strip() for x in pathlib.Path('/proc/self/status').read_text().splitlines() if x.startswith('NoNewPrivs:'))},sort_keys=True))
"""

def main():
    start=time.monotonic(); a=resource.getrusage(resource.RUSAGE_SELF); b=resource.getrusage(resource.RUSAGE_CHILDREN)
    result={'scope':'local synthetic platform feasibility; not native qualification','checks':{},'actual_billing_usd':None,'source_sha256':sha(Path(__file__).read_bytes()),'python':sys.version.split()[0]}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);root=d/'source';stage=d/'stage';shadow=d/'shadow'
            original={'sample/__init__.py':b'', 'sample/worker.py':b'VALUE = "original"\n','job.json':b'{"job":"original"}\n'}
            changed={'sample/worker.py':b'VALUE = "replacement"\n','job.json':b'{"job":"replacement"}\n'}
            for dest in (root,stage):
                for name,raw in original.items():
                    p=dest/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
            (shadow/'sample').mkdir(parents=True);(shadow/'sample/__init__.py').write_text('');(shadow/'sample/worker.py').write_text('VALUE = "shadow"\n')
            pinned={k:sha(v) for k,v in original.items()};result['pinned']=pinned
            expected={'value':'original','origin':str(root/'sample/worker.py'),'job':pinned['job.json']}
            expected_changed={**expected,'value':'replacement','job':sha(changed['job.json'])}
            for name,raw in changed.items():(root/name).write_bytes(raw)
            ordinary=invoke(root,shadow,READ);result['ordinary_rc']=ordinary.returncode
            result['checks']['ordinary_changed']=ordinary.returncode==0 and json.loads(ordinary.stdout)==expected_changed
            for name,raw in original.items():(root/name).write_bytes(raw)
            result['checks']['ordinary_hashes_restored']=inventory(root)==pinned
            # Namespace setup is separate from the capability-stripped worker; all staging bytes are checked before readiness.
            setup='''set -eu
mount -t tmpfs -o size=4m,mode=0700 tmpfs "$1"
cp -R "$2/." "$1/"
"$3" -I -S -B -c 'import sys,hashlib,json,pathlib;r=pathlib.Path(sys.argv[1]);actual={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in r.rglob("*") if p.is_file()};assert actual==json.loads(sys.argv[2])' "$1" "$4"
mount -o remount,ro "$1"
touch "$5"
while [ ! -f "$6" ]; do sleep 0.02; done
exec setpriv --bounding-set=-all --inh-caps=-all --ambient-caps=-all --no-new-privs "$3" -I -S -B -c "$7" "$1"
'''
            ready=d/'ready';go=d/'go'
            p=subprocess.Popen(['unshare','-Urnm','--propagation','private','sh','-c',setup,'sh',str(root),str(stage),sys.executable,json.dumps(pinned),str(ready),str(go),CHECK],env={**os.environ,'PYTHONPATH':str(shadow)},stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                deadline=time.monotonic()+10
                while not ready.exists() and p.poll() is None and time.monotonic()<deadline:time.sleep(.02)
                result['checks']['snapshot_ready']=ready.exists()
                if ready.exists():
                    for name,raw in changed.items():(root/name).write_bytes(raw)
                    go.touch()
                out,err=p.communicate(timeout=10);result['snapshot_rc']=p.returncode
                if p.returncode==0:
                    rows=[json.loads(line) for line in out.splitlines()];first,second=rows
                    result['checks']['parent_original']=first==expected
                    result['checks']['nested_original']=second['nested']==expected
                    result['checks']['writes_denied']=all(second['writes_denied'].values()) and len(second['writes_denied'])==2
                    result['checks']['remount_denied']=second['remount_denied'] and second['caps'].split()[-1]=='0000000000000000' and second['no_new_privs'].split()[-1]=='1'
                    result['checks']['outside_still_changed']=inventory(root)=={**pinned,**{k:sha(v) for k,v in changed.items()}}
                else:result['error']=err[-1000:]
            finally:
                if p.poll() is None:p.kill();p.communicate()
                for name,raw in original.items():(root/name).write_bytes(raw)
            result['checks']['final_hashes_restored']=inventory(root)==pinned
    except Exception as exc:result['error']=repr(exc)
    expected_keys={'ordinary_changed','ordinary_hashes_restored','snapshot_ready','parent_original','nested_original','writes_denied','remount_denied','outside_still_changed','final_hashes_restored'}
    result['accepted']=set(result['checks'])==expected_keys and all(result['checks'].values()) and 'error' not in result
    c=resource.getrusage(resource.RUSAGE_SELF);e=resource.getrusage(resource.RUSAGE_CHILDREN)
    result['cpu_self_seconds']=c.ru_utime+c.ru_stime-a.ru_utime-a.ru_stime
    result['cpu_waited_children_seconds']=e.ru_utime+e.ru_stime-b.ru_utime-b.ru_stime
    result['wall_seconds']=time.monotonic()-start
    print(json.dumps(result,sort_keys=True,indent=2));return 0 if result['accepted'] else 1
if __name__=='__main__':sys.exit(main())
