"""Verify the unmodified CLI's exported archive against all six archived field input hashes."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time
import zipfile


def check(work, product, output):
    start = time.monotonic()
    began = datetime.now(timezone.utc).isoformat()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / 'recipient.zip'
    with tempfile.TemporaryDirectory() as state:
        cli = [sys.executable, '-B', '-m', 'ignition', '--state', state]
        def run(args):
            proc = subprocess.run(cli+args, cwd=product, text=True, capture_output=True)
            if proc.returncode:
                raise ValueError(proc.stderr)
            return json.loads(proc.stdout)
        mission = run(['start','examples/scroll.json','--request-id','final-production-replay'])
        if mission['status'] != 'verified':
            raise ValueError(mission.get('error') or mission['status'])
        run(['export',mission['id'],str(archive),'--version','1'])
    subprocess.run([sys.executable, '-B', str(work/'bench_recipient.py'), str(archive), str(work/'run'),
                    str(output/'window_result.json')],check=True)
    before=json.loads((work/'run'/'window_result.json').read_text())
    after=json.loads((output/'window_result.json').read_text())
    def outputs(blob):
        return [(r['ordinal'],r['source_sha256'],r['recipient_output_sha256']) for r in blob['tests']]
    if outputs(before)!=outputs(after):
        raise ValueError('different output vs original frozen trial')
    with zipfile.ZipFile(archive) as z:
        hashes={k:hashlib.sha256(z.read(k)).hexdigest() for k in z.namelist()}
    (output/'member_hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
    u=resource.getrusage(resource.RUSAGE_CHILDREN)
    summary={'started_utc':began, 'wall_seconds_including_cli_start_and_export':time.monotonic()-start,
             'child_user_cpu_seconds':u.ru_utime,'child_system_cpu_seconds':u.ru_stime,'peak_child_rss_kib_linux':u.ru_maxrss,
             'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'zip_bytes':archive.stat().st_size,
             'mission_input_sha256':mission['input_sha256'],'prior_outputs_matched':len(after['tests']),'additional_ct_downloads':0}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(summary, [(v['ordinal'],v['incumbent_over_candidate']) for v in after['tests']])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('work',type=Path);p.add_argument('product',type=Path);p.add_argument('output',type=Path)
    args=p.parse_args()
    check(args.work.resolve(),args.product.resolve(),args.output.resolve())
