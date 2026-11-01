"""Assemble exact reviewed bytes into Git blobs, without changing any branch."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
BASE = '7333cb483a9fb261177e89a094f72ab896aab82c'
REPO = 'MontrealAI/AGI-Alpha-Invention-Flywheel-Lab'
CHANGED = {
 'connected_enterprise/complete_offer_audit.py': ('59a2414073d993f42a5483c3f419b16ad3e03659ceeb2a6ab8e22bd09f5169c6','00629342448fb05f78820a361502b798d30b5377c59d2ed63bbf618c24aa2dd5'),
 'connected_enterprise/complete_offer_market.py': ('05a42eff5715d5ff0e0c52de3050c15c1ec13bf6895ff7fa4ea033763ea5e180','819cc9aa7fb23e5c5db08e107651e6280797e0776b5d0757cefe4ae6ca56f9f9'),
 'connected_enterprise/engine.py': ('b157315d3f3c3ce55f0242de42602906d967ac15c80cf6d4eec2bf59b90aea48','a50282dd1ca8dc6f159b86f68fd69c9fa6324ef5641cd27b274f0e685d176e89'),
 'connected_enterprise/joint_planning.py': ('a17e1a61d28c76ab06f10ba55bc882f6668c4728d3d1b0ba65ac9cb09001e741','946540b644b7b08188c954e9437a68297adc0efa7b3ae3af672171cb76deb8e6'),
 'connected_enterprise/verify.py': ('73072fcae301c1f5f09948079044a9173f772f78f4c114b101013107019525b1','34c2088dfa631080085ddc50dec8966fc77a66a9a9678a6afcf805a79ff4460b')}
NEW = {
 'tests/test_connected_market_index049.py': '14fc8b729d75fe7f1e15ff933272f90687329dd024839e39d678bb27f94915e8',
 'scripts/qualify_market_index049.py': '14b7b0c9d7c8ef974a2cbe84b4068d2179d0d13af40dd39547dcc90fcd9d7716'}
BINDING = 'evidence/strategic024-publication/COMPOSED_SOURCE_BINDING.json'

def sha(path):
    p = ROOT / path
    if p.is_symlink() or not p.is_file(): raise ValueError('REGULAR_REVIEWED_MEMBER_REQUIRED')
    return hashlib.sha256(p.read_bytes()).hexdigest()

def run(*args): subprocess.run(args, cwd=ROOT, check=True, timeout=240)

def main():
    if os.environ.get('GITHUB_REPOSITORY') != REPO or os.environ.get('GITHUB_REF') != 'refs/heads/build/native-market-index-049':
        raise ValueError('EXACT_ASSEMBLY_BRANCH_REQUIRED')
    run('git','merge-base','--is-ancestor',BASE,'HEAD')
    for path,(before,_) in CHANGED.items():
        if sha(path) != before: raise ValueError('BASE_BYTES_CHANGED:'+path)
    for path,expected in NEW.items():
        if sha(path) != expected: raise ValueError('NEW_BYTES_CHANGED:'+path)
    run('git','apply','--check','build/market049/market049.patch')
    run('git','apply','build/market049/market049.patch')
    for path,(_,after) in CHANGED.items():
        if sha(path) != after: raise ValueError('PATCH_BYTES_CHANGED:'+path)
    from connected_enterprise.runner import identity
    source = identity(ROOT)
    if source['sha256'] != '56d98e075776be4f8274b85aa87a1375c149af0782c5967920d91163acd0520b':
        raise ValueError('LOCAL_TESTED_SOURCE_MISMATCH')
    binding = json.loads((ROOT/BINDING).read_text())
    before = binding['current_source_sha256']
    if before != '8ea5bff31a9d6b92dacefa15813f4c353916ebf2971919fbaa1ff06bd91fd901':
        raise ValueError('EXPECTED_MAIN_REGISTRATION_REQUIRED')
    prior = binding['historical_files']
    binding['current_files'] = source['files']; binding['current_source_sha256'] = source['sha256']
    binding['source_delta'] = {p:{'before_sha256':prior.get(p),'after_sha256':source['files'].get(p)} for p in sorted(set(prior)|set(source['files'])) if prior.get(p)!=source['files'].get(p)}
    for field in ('qualification_sha256','source_archive_sha256','public_archive_sha256'): binding[field] = None
    binding['qualification_status'] = 'NOT_QUALIFIED_REGISTRATION_ONLY'
    binding['status'] = 'UNQUALIFIED_REGISTRATION_REQUIRES_ACTUAL_CLEAN_SOURCE_QUALIFICATION'
    (ROOT/BINDING).write_text(json.dumps(binding,indent=2,sort_keys=True)+'\n')
    run(sys.executable,'-m','unittest','tests.test_connected_market_index049','tests.test_publication_binding','tests.test_publication_composition','-v')
    paths = [*CHANGED,*NEW,BINDING,'docs/harness/MARKET_INDEX049.md','.github/workflows/market-index049.yml']
    objects=[]
    for path in paths:
        raw=(ROOT/path).read_bytes()
        expected=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        payload=json.dumps({'encoding':'base64','content':base64.b64encode(raw).decode()}).encode()
        request=urllib.request.Request('https://api.github.com/repos/'+REPO+'/git/blobs',data=payload,method='POST',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json','X-GitHub-Api-Version':'2022-11-28'})
        with urllib.request.urlopen(request,timeout=30) as response: returned=json.load(response)
        if returned.get('sha') != expected: raise ValueError('STORED_BLOB_MISMATCH')
        objects.append({'path':path,'sha':expected,'mode':'100644','type':'blob','sha256':hashlib.sha256(raw).hexdigest()})
    out=Path(os.environ['RUNNER_TEMP'])/'market049-objects.json'
    out.write_text(json.dumps({'base':BASE,'source_sha256':source['sha256'],'source_members':len(source['files']),'objects':objects,'scope':'TESTED_CODE_OBJECTS_ONLY_NO_BRANCH_UPDATE_NO_RELEASE_CLAIM'},indent=2,sort_keys=True)+'\n')
    print(out.read_text())

if __name__=='__main__':main()
