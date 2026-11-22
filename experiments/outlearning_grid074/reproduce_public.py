"""Reproduce public negative test without modifying recorded artifacts.

All dependencies are in this payload or the Python standard library. The original
transfer_probe.py runs unchanged in an isolated temporary copy, because it writes
its timing/result/provenance. Candidate source is never changed.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).parent

def run():
    manifest=json.loads((ROOT/'MANIFEST.json').read_text())
    for item in manifest['files']:
        data=(ROOT/item['path']).read_bytes()
        assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256'],item['path']
    historical=json.loads((ROOT/'TRANSFER_RESULT.json').read_text())
    files=['transfer_probe.py','provenance.py','retained_symmetry.py','k1_card.json','k2_card.json',
           'K1_FREEZE.json','K1_OBSERVATIONS.json','K1_CONSTRUCTION.json']
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
    with tempfile.TemporaryDirectory(prefix='grid074-reproduce-') as tmp:
        for name in files:shutil.copyfile(ROOT/name,Path(tmp)/name)
        completed=subprocess.run([sys.executable,'transfer_probe.py'],cwd=tmp,env=env,check=True,capture_output=True,text=True)
        replay=json.loads(completed.stdout)
    assert replay['cases']==historical['cases']
    assert replay['decision']==historical['decision']
    independent=subprocess.run([sys.executable,'-B',str(ROOT/'independent_public_check.py')],cwd=ROOT,env=env,check=True,capture_output=True,text=True)
    checks=json.loads(independent.stdout)
    assert checks['passed'] and not checks['candidate_imported']
    # Ensure the reproduction did not alter any payload artifact.
    for item in manifest['files']:
        assert hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()==item['sha256'],item['path']
    return {'passed':True,'all_manifest_files_verified':len(manifest['files']),
            'original_transfer_procedure_replayed_unchanged':True,'historical_case_results_match':True,
            'recorded_artifacts_unmodified':True,'replay_cpu_seconds':replay['cpu_seconds'],
            'independent_check':checks}

if __name__=='__main__':print(json.dumps(run(),indent=2))
