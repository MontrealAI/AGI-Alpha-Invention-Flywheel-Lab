#!/usr/bin/env python3
"""Reproduce source-bound simulated accounts. No network, actual trades, or billing.
Requires the dependencies of the bundled historical native reference.
Output includes PRIVATE LOCAL SIMULATION AUTHORITY; do not publish --work.
"""
from pathlib import Path
from zipfile import ZipFile
import argparse
import hashlib
import json
import shutil
import stat
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, required=True, help='New private local POSIX directory')
    p.add_argument('--skip-tests', action='store_true', help='Run reproductions only; do not report suite completion')
    a = p.parse_args()
    work = a.work.absolute()
    if any(x.is_symlink() for x in (work,*work.parents)):
        raise SystemExit('Symlink output path rejected.')
    if work.exists():
        raise SystemExit('Use a NEW output directory; this driver never reseeds existing accounts.')
    archive = HERE/'native_reference.zip'
    provenance = json.loads((HERE.parent/'PROVENANCE.json').read_text())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != provenance['native_reference_archive_sha256']:
        raise SystemExit('Historical reference archive checksum mismatch.')
    work.mkdir(parents=True)
    source=work/'source';source.mkdir()
    with ZipFile(archive) as z:
        for item in z.infolist():
            path=Path(item.filename)
            target=(source/path).resolve()
            mode=item.external_attr >> 16
            if path.is_absolute() or '..' in path.parts or source.resolve() not in target.parents or stat.S_ISLNK(mode):
                raise SystemExit('Unsafe archive entry: '+item.filename)
        z.extractall(source)
    shutil.copytree(HERE/'native_additions',source,dirs_exist_ok=True)
    sys.path.insert(0,str(source))
    try:
        from genesis002.engine import run
        from genesis002.audit import audit
        from genesis002.common import read
    except ImportError as e:
        raise SystemExit('Missing reference dependency. Install requirements-commercial010.txt in a local virtual environment. '+str(e))
    if not a.skip_tests:
        with (work/'native_tests.log').open('w') as log:
            r=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_genesis002_*.py','-v'],cwd=source,stdout=log,stderr=subprocess.STDOUT)
        if r.returncode:
            raise SystemExit('Native tests failed; see native_tests.log. Existing evidence is preserved.')
    rows=[]
    for stress in ('central','no_demand','failed_acceptance','payment_failure'):
        output=work/stress
        config=read(source/'campaign/genesis-enterprise-002/INPUT.json')
        start=time.monotonic()
        result=run(source,output,config,stress=stress)
        checked=audit(source,output)
        before=(output/'NATIVE_EXPORT.json').read_bytes()
        resumed=run(source,output,resume=True,stress=stress)
        same=(resumed==result and before==(output/'NATIVE_EXPORT.json').read_bytes())
        if not checked['accepted'] or not same:
            raise SystemExit('Audit/resume failed; records retained at '+str(output))
        row={'scenario':stress,'cycles':config['cycles'],'settled':result['settled'],
             'modeled_profit_cents':result['modeled_profit_cents'],'actual_revenue_usd':result['actual_revenue_usd'],
             'audit_accepted':True,'resume_unchanged':same,'wall_seconds':time.monotonic()-start}
        rows.append(row);print(json.dumps(row))
    (work/'PUBLIC_SUMMARY.json').write_text(json.dumps({'scope':'AUTHORED_SIMULATION_NOT_ACTUAL_COMMERCE','native_reference':provenance['native_reference_commit'],'test_suite_run':not a.skip_tests,'records':rows},indent=2)+'\n')
    print('Completed. Only PUBLIC_SUMMARY.json is intended for ordinary sharing; keep account authority private.')

if __name__=='__main__':
    main()
