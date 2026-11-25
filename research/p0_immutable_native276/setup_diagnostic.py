"""Frozen 2026-11-25: one synthetic setup localization, not a P0-276 retry.

Purpose: distinguish unshare, mount, copy, inventory, remount, ready and
capability-stripped worker failures without native code or account state.
One standard hosted execution; stop at first failed command; no sudo, sysctl,
host config changes, alternate runner or permission bypass. No raw stderr,
paths, environment, or credentials retained. Success only establishes
synthetic setup feasibility on this run, not historical native equivalence.
"""
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time

VERIFY = r"""
import sys,json,hashlib,pathlib,stat
root=pathlib.Path(sys.argv[1])
expected=json.loads(pathlib.Path(sys.argv[2]).read_text())
actual={}
for p in root.rglob('*'):
    info=p.lstat()
    if stat.S_ISDIR(info.st_mode): continue
    if not stat.S_ISREG(info.st_mode): raise ValueError('P0276_NONREGULAR_SNAPSHOT')
    actual[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
if expected!=actual:raise ValueError('P0276_SNAPSHOT_INVENTORY_MISMATCH')
"""
SETUP = r"""
set -eu
root=$1; stage=$2; manifest=$3; marker=$4; ready=$5; py=$6; verify=$7; worker=$8
mark() { printf '%s\n' "$1" >> "$marker"; }
mark namespace_entered
mark mount_started
mount -t tmpfs -o mode=0700 tmpfs "$root"
mark mount_completed
mark copy_started
cp -R "$stage/." "$root/"
mark copy_completed
mark inventory_started
"$py" -I -S -B -c "$verify" "$root" "$manifest"
mark inventory_completed
mark remount_started
mount -o remount,ro "$root"
mark remount_completed
touch "$ready"
mark ready
cd "$root"
mark worker_started
exec setpriv --bounding-set=-all --inh-caps=-all --ambient-caps=-all --no-new-privs "$py" -I -S -B -c "$worker" "$root"
"""
WORKER = r"""
import os,sys,pathlib,hashlib
root=pathlib.Path(sys.argv[1])
assert os.statvfs(root).f_flag & os.ST_RDONLY
assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
status=dict(line.split(':',1) for line in pathlib.Path('/proc/self/status').read_text().splitlines() if ':' in line)
assert int(status['CapEff'].strip(),16)==0 and status['NoNewPrivs'].strip()=='1'
assert (root/'payload.txt').read_bytes()==b'P0-276 synthetic setup control\n'
print('synthetic_worker_passed')
"""
def main():
    started=time.monotonic()
    self0=resource.getrusage(resource.RUSAGE_SELF)
    child0=resource.getrusage(resource.RUSAGE_CHILDREN)
    out=Path(sys.argv[1]).resolve()
    result={'schema':'p0-276-setup-diagnostic/v1','native_account_accessed':False,
            'native_qualification':False,'actual_billing_usd':None,
            'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    expected=['namespace_entered','mount_started','mount_completed','copy_started','copy_completed',
              'inventory_started','inventory_completed','remount_started','remount_completed','ready','worker_started']
    try:
        with tempfile.TemporaryDirectory(prefix='p0276-setup-') as tmp:
            base=Path(tmp); root=base/'root'; stage=base/'stage'; home=base/'home'
            for p in (root,stage,home):p.mkdir(mode=0o700)
            payload=b'P0-276 synthetic setup control\n'
            (stage/'payload.txt').write_bytes(payload)
            manifest=base/'manifest.json'
            manifest.write_text(json.dumps({'payload.txt':hashlib.sha256(payload).hexdigest()},sort_keys=True))
            marker=base/'stages'; ready=base/'ready'
            cmd=['unshare','-Urnm','--propagation','private','sh','-c',SETUP,'sh',
                 str(root),str(stage),str(manifest),str(marker),str(ready),sys.executable,VERIFY,WORKER]
            env={'PATH':os.environ['PATH'],'HOME':str(home),'TMPDIR':str(base),'PYTHONDONTWRITEBYTECODE':'1'}
            p=subprocess.run(cmd,cwd='/',env=env,capture_output=True,text=True)
            stages=marker.read_text().splitlines() if marker.exists() else []
            if stages!=expected[:len(stages)]: raise ValueError('UNEXPECTED_STAGE_ORDER')
            err=p.stderr.lower()
            classes=[x for x in ('operation not permitted','permission denied','not found','invalid argument','read-only file system','p0276_snapshot_inventory_mismatch') if x in err]
            result.update(exit_code=p.returncode,stages=stages,ready=ready.exists(),
                          stderr_classes=classes,stderr_present=bool(err),
                          synthetic_worker_passed=p.stdout.strip()=='synthetic_worker_passed',
                          qualified=p.returncode==0 and stages==expected and ready.exists() and p.stdout.strip()=='synthetic_worker_passed')
    except Exception as exc:
        result.update(qualified=False,exception_type=type(exc).__name__)
    finally:
        s=resource.getrusage(resource.RUSAGE_SELF); c=resource.getrusage(resource.RUSAGE_CHILDREN)
        result.update(self_cpu_seconds=s.ru_utime+s.ru_stime-self0.ru_utime-self0.ru_stime,
                      waited_child_cpu_seconds=c.ru_utime+c.ru_stime-child0.ru_utime-child0.ru_stime,
                      wall_seconds=time.monotonic()-started)
        out.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    return 0 if result['qualified'] else 1

if __name__=='__main__':
    raise SystemExit(main())
