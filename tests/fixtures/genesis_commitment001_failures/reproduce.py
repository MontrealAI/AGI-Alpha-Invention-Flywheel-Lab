"""Replay two preserved failed files on fresh, disposable synthetic accounts.

The originals are byte-preserved pre-repair files. The rest of the dependency
environment is supplied by --source (use commit ffcc652); this is a fresh
counterexample replay, not the original execution or an original account.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ORIGINALS = {
    'F01': ('F01_native.py.original', 'native.py', 'b2f7d9a3ebe89030a700b221095c70821d7aca39c662ebe8c0343717b05351d3'),
    'F02': ('F02_runner.py.original', 'runner.py', 'fe63f79c457ac2065f94a44a4f456562486ab79e58a524edcac7c1a74a6b422d'),
}

F01 = r'''
import json, sys
from pathlib import Path
from campaign.genesis_commitment001 import service
from campaign.genesis_commitment001.delivery import default_requests
from campaign.genesis_commitment001.native import BusinessAccount
source=Path.cwd()
rows=[{'id':r['id'],'request':r,'delivery_path':'campaign/genesis_commitment001/deliveries/'+r['id']+'.json'} for r in default_requests()]
manifest=service.prepare_manifest(source,rows)
work={'capacity':{'supplier':'s','start':10,'end':12,'units':1},'costs':{'production':1000000},'expected_net':1000000,'job':'restore-first','order':'fresh','buyer':'buyer-fresh'}
with BusinessAccount(source,manifest,Path(sys.argv[1])/'account.sqlite',contract='fresh-original-F01-replay',suppliers={'s':{'units':1,'consent':'AUTHORED_SIMULATED_ACCEPTANCE'}}) as b:
    receipt=b.reserve_delivery('capacity-fresh',1000000,1,work,allow_seed=True)
    if receipt is None:raise RuntimeError('FRESH_RESERVATION_MUST_PASS')
    try:b.begin('restore-first','fresh','buyer-fresh',300000000,400000000,2,48,72)
    except ValueError as e:
        if str(e)!='PROSPECTIVE_ORDER_PRICE_OR_CLOCK_MISMATCH':raise
        print(json.dumps({'case':'F01','observed_error':str(e),'deadline':72,'maturity':72,'expect_failure':True}))
    else:raise RuntimeError('ORIGINAL_F01_FAILURE_NOT_REPRODUCED')
'''

F02 = r'''
import json,sys,zipfile
from pathlib import Path
from campaign.genesis_commitment001 import runner
output=Path(sys.argv[1])/'run'
runner.run(output,scenario='favorable_envelope',arm='retained')
marker=b'HARMLESS_SYNTHETIC_ORIGINAL_F02_REPLAY_MARKER'
(output/'EXTRA_ARTIFACT.json').write_bytes(marker)
archive=Path(sys.argv[1])/'public.zip'
runner.package(output,archive)
with zipfile.ZipFile(archive) as z:
    leaked=z.read('EXTRA_ARTIFACT.json')==marker
if not leaked:raise RuntimeError('ORIGINAL_F02_FAILURE_NOT_REPRODUCED')
print(json.dumps({'case':'F02','harmless_extra_artifact_copied':leaked,'expect_failure':True}))
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    args=parser.parse_args()
    source=args.source.resolve()
    sys.path.insert(0,str(source))
    from connected_enterprise.finance import source_paths_for_manifest
    from campaign.genesis_commitment001 import service
    names=source_paths_for_manifest({'schema':service.SCHEMA})
    fixture=Path(__file__).resolve().parent
    observations=[]
    with tempfile.TemporaryDirectory(prefix='commitment-original-failures-') as temporary:
        root=Path(temporary)
        for case,code in [('F01',F01),('F02',F02)]:
            original,target_name,wanted=ORIGINALS[case]
            content=(fixture/original).read_bytes()
            if hashlib.sha256(content).hexdigest()!=wanted:
                raise ValueError('ORIGINAL_BYTES_CHANGED:'+case)
            variant=root/case/'source'
            for name in names:
                target=variant/name;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source/name,target)
            (variant/'campaign/genesis_commitment001'/target_name).write_bytes(content)
            run=subprocess.run([sys.executable,'-c',code,str(root/case/'fresh')],cwd=variant,text=True,capture_output=True)
            if run.returncode:
                raise RuntimeError(case+' replay failed:\n'+run.stdout+run.stderr)
            observation=json.loads(run.stdout)
            observation['original_sha256']=wanted
            observations.append(observation)
    print(json.dumps({'scope':'fresh counterexamples using preserved failed files and caller-supplied dependencies; no historical account accessed','results':observations},indent=2))


if __name__=='__main__':
    main()
