"""Exact reviewed byte assembly; upload Git objects only, never move a ref."""
import argparse
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
REPO='MontrealAI/AGI-Alpha-Invention-Flywheel-Lab'
BASE='99769a8a4d19a8cfc1b3c6d05084d7ed99b76849'
EXPECTED={
 'connected_enterprise/billion036.py':('789c1b2167353620e3101577d8ca240e674dc853fc05caed31c8922ed796804f','69574a76e7709d6ccbe1a35e08ba845c6439a23e2d10fb9372e702b6ad51ee58'),
 'connected_enterprise/buyer_income.py':(None,'aa8504120229bbbdd7fab9c083b6df28a7b2096137ffe86fcfb38897bb5272a0'),
 'connected_enterprise/complete_offer_audit.py':('5af359d50c9cf5aa47bb70e7161d2546ce27830e65b78f425a3e93bd9dc273eb','9c2f95f912afe77f33e903185700415d456cc316e0fa089d71863b18d22dfc35'),
 'connected_enterprise/engine.py':('f65dd07d9cb1a6c4705e6af5286714f4f7d577d55b4245f63a71ecf2c175c585','bd85ad7260c1a8e6ccca70d42da3faf33a2267ec7d1c32dfb593306ba7258b53'),
 'connected_enterprise/joint_planning.py':('a4d2df11d4b5214f823c4df8c60cf3c9e33455ec33dded835ffe633806ad7d03','367d20bf9be36eee68b141f2d3fc6b07a64e560eef102e731207e04fac3bd12d'),
 'connected_enterprise/public_budget_gate051.py':(None,'d2cdae45317bca0aa553fcf46f029cde393657374b340501d1c5293daa14755e'),
 'connected_enterprise/recurring_business051.py':(None,'37474c6aaa120c1ccc881f99b139ede26d6d01802b9a3a4eb7bcac1b57ce0836'),
 'connected_enterprise/strategic_audit.py':('e21244667a6e774d0f14575fcb762c99d18d07d6c92853b8067c174a48813af1','1d09741adcf236ba155f2b4bc447aa2fd6c2b0b3eddce763a4ffe6d964341d74'),
 'connected_enterprise/verify.py':('9fc576ffb0d9abdde44672e81d4fbc9a66a81fbb84674ca0090d6f7ce6e55541','31ce707a9ddc5fa729102ecf437bc2fb26107ec1e3aa7c719d4bcd79e951f5d1'),
 'tests/test_connected_recurring_income051.py':(None,'68376ec458006fe914fd75b1a03251c41d7968b747c2ac537eb9d72acf5a62b2')}
BINDING='evidence/strategic024-publication/COMPOSED_SOURCE_BINDING.json'
SOURCE='78c84500a125ad09f8345a89b438dfae337d75ac6d8f648ca05a6ed783fab395'


def sha(path):return hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
def run(*args):subprocess.run(args,cwd=ROOT,check=True,timeout=480)

def guard():
    if os.environ.get('GITHUB_REPOSITORY')!=REPO or os.environ.get('GITHUB_REF')!='refs/heads/build/recurring-commerce-051':raise ValueError('EXACT_ASSEMBLY_BRANCH_REQUIRED')
    run('git','merge-base','--is-ancestor',BASE,'HEAD')

def prepare():
    guard()
    for path,(before,after) in EXPECTED.items():
        if before is not None and sha(path)!=before:raise ValueError('BASE_BYTES_CHANGED:'+path)
        if before is None and path!='tests/test_connected_recurring_income051.py' and sha(path)!=after:raise ValueError('NEW_BYTES_CHANGED:'+path)
    # Recover one known transport transcription, then require exact local test bytes.
    compressed=(ROOT/'build/recurring051/tests.py.gz').read_bytes()
    encoded=base64.b64encode(compressed).decode()
    if encoded.count('HopypypYqg2aeX6')!=1:raise ValueError('KNOWN_TEST_TRANSPORT_REQUIRED')
    encoded=encoded.replace('HopypypYqg2aeX6','HopypYqg2aeX6')
    raw=gzip.decompress(base64.b64decode(encoded+'='*(-len(encoded)%4)))
    if hashlib.sha256(raw).hexdigest()!=EXPECTED['tests/test_connected_recurring_income051.py'][1]:raise ValueError('TEST_TRANSPORT_IDENTITY_FAILED')
    (ROOT/'tests/test_connected_recurring_income051.py').write_bytes(raw)
    patch=(ROOT/'build/recurring051/runtime.patch').read_text()
    patch=patch.replace("+                policy=cfg['buyer_income_policy']", "+                income=cfg['buyer_income_policy']")
    patch=patch.replace("+                    if draw(seed,[day,buyer['id']],'buyer-external-income')<policy['receipt_bps']/10000:", "+                    if draw(seed,[day,buyer['id']],'buyer-external-income')<income['receipt_bps']/10000:")
    patch=patch.replace("+                        amount=policy['income_microUSD'];buyer['remaining_budget']+=amount;buyer['external_income_total']+=amount", "+                        amount=income['income_microUSD']\n+                        buyer['remaining_budget']+=amount;buyer['external_income_total']+=amount")
    transport=Path(os.environ['RUNNER_TEMP'])/'recurring051.patch';transport.write_text(patch)
    run('git','apply','--recount','--check',str(transport))
    run('git','apply','--recount',str(transport))
    for path,(_,after) in EXPECTED.items():
        if sha(path)!=after:raise ValueError('LOCAL_TESTED_BYTES_MISMATCH:'+path)
    from connected_enterprise.runner import identity
    source=identity(ROOT)
    if source['sha256']!=SOURCE:raise ValueError('LOCAL_CANONICAL_SOURCE_MISMATCH')
    binding=json.loads((ROOT/BINDING).read_text())
    if binding['current_source_sha256']!='ba510738584bb95d95a794dfb29eac3851407920e9c599cbd23abfc5ef80ffec':raise ValueError('EXPECTED_MAIN_BINDING_REQUIRED')
    prior=binding['historical_files'];binding['current_files']=source['files'];binding['current_source_sha256']=SOURCE
    binding['source_delta']={p:{'before_sha256':prior.get(p),'after_sha256':source['files'].get(p)} for p in sorted(set(prior)|set(source['files'])) if prior.get(p)!=source['files'].get(p)}
    for field in ('qualification_sha256','source_archive_sha256','public_archive_sha256'):binding[field]=None
    binding['qualification_status']='NOT_QUALIFIED_REGISTRATION_ONLY'
    binding['status']='UNQUALIFIED_REGISTRATION_REQUIRES_ACTUAL_CLEAN_SOURCE_QUALIFICATION'
    (ROOT/BINDING).write_text(json.dumps(binding,indent=2,sort_keys=True)+'\n')
    run(sys.executable,'-m','unittest','tests.test_connected_recurring_income051','tests.test_publication_binding','tests.test_publication_composition','-v')
    paths=[*EXPECTED,BINDING,'docs/harness/RECURRING051.md','.github/workflows/recurring-business051.yml']
    record={'source_sha256':SOURCE,'source_members':len(source['files']),'files':{p:sha(p) for p in paths},'status':'TESTED_CODE_ONLY_NOT_RELEASED'}
    (Path(os.environ['RUNNER_TEMP'])/'recurring051-prepared.json').write_text(json.dumps(record,indent=2)+'\n')


def upload():
    guard();record=json.loads((Path(os.environ['RUNNER_TEMP'])/'recurring051-prepared.json').read_text());objects=[]
    for path,expected in record['files'].items():
        if sha(path)!=expected:raise ValueError('POST_TEST_SOURCE_CHANGED')
        raw=(ROOT/path).read_bytes();blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        request=urllib.request.Request('https://api.github.com/repos/'+REPO+'/git/blobs',data=json.dumps({'encoding':'base64','content':base64.b64encode(raw).decode()}).encode(),method='POST',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=30) as response:value=json.load(response)
        if value.get('sha')!=blob:raise ValueError('STORED_BLOB_CHANGED')
        objects.append({'path':path,'sha':blob,'sha256':expected,'type':'blob','mode':'100644'})
    out=Path(os.environ['RUNNER_TEMP'])/'recurring051-objects.json';out.write_text(json.dumps({'base':BASE,'source_sha256':SOURCE,'objects':objects,'scope':'SOURCE_OBJECTS_ONLY_NO_BRANCH_MOVEMENT'},indent=2)+'\n');print(out.read_text())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','upload']);a=p.parse_args()
    prepare() if a.command=='prepare' else upload()
