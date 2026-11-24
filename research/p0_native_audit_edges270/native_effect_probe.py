"""P0-270B: exact owner module, native CAS effect boundary, no financial operations."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time

OWNER = 'ced6c1cb004887dcdafaea59a2976020be649f8e'
BLOB = '2397091ef8e1960ad13950693d5b3cd04e2ff7c5'
def git_blob(raw):
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
def load_native(source):
    if git_blob(source.read_bytes()) != BLOB:
        raise ValueError('EXACT_OWNER_MODULE_REQUIRED')
    spec=importlib.util.spec_from_file_location('native_evidence270b',source)
    module=importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode=True
    spec.loader.exec_module(module)
    return module

def run(source, output):
    started=time.monotonic()
    cpu0=[resource.getrusage(k) for k in (resource.RUSAGE_SELF,resource.RUSAGE_CHILDREN)]
    m=load_native(source)
    # Key-free codec descriptor only, deliberately not a financially valid ticket.
    body={k:None for k in m.FIELDS}
    body.update(schema=m.V1,id='codec-fixture-270b',counter=1,day=0,
                prior_record={'fixture':'record','value':1},
                prior_envelope={'fixture':'envelope','value':2})
    blobs={}
    ticket={'body':m.externalize(body,blobs),'signature':'0'*64}
    target=next(iter(blobs))
    checks=[]
    def check(name, f):
        try:
            result=f()
            checks.append({'name':name,'pass':result is True})
        except Exception as e:
            # No paths, tickets, data or stack traces in public receipt.
            checks.append({'name':name,'pass':False,'error_type':type(e).__name__})
    def expected_error(f,message):
        try:f()
        except ValueError as e:return str(e)==message
        return False
    with tempfile.TemporaryDirectory(prefix='p0-270b-') as tmp:
        base=Path(tmp).resolve()
        def fixture(name,alias=True):
            root=base/name
            root.mkdir()
            m.persist_evidence(root,blobs)
            if alias:os.link(root/target,root/('.pending-'+target))
            return root
        def exact(root):
            return all((root/k).read_bytes()==v for k,v in blobs.items())
        def resolve(root):
            with m.evidence_directory(root):
                return m.ticket_body(ticket)
        def memory():
            with m.evidence_scope(blobs):
                return m.ticket_body(ticket)
        def first():
            root=fixture('first')
            observed=resolve(root)
            return observed==body and exact(root) and not (root/('.pending-'+target)).exists()
        def idempotent():
            root=fixture('idempotent')
            a=resolve(root)
            before=sorted(x.name for x in root.iterdir())
            b=resolve(root)
            return a==b==body and before==sorted(x.name for x in root.iterdir()) and exact(root)
        def effect_difference():
            disk=fixture('effect-disk')
            mem=fixture('effect-memory')
            a=resolve(disk)
            b=memory()
            return a==b==body and not (disk/('.pending-'+target)).exists() and (mem/('.pending-'+target)).exists() and exact(mem)
        def non_alias():
            root=fixture('non-alias',alias=False)
            pending=root/('.pending-'+target)
            pending.write_bytes(blobs[target])
            return resolve(root)==body and pending.exists() and exact(root) and pending.stat().st_ino!=(root/target).stat().st_ino
        def corrupted_alias():
            root=fixture('corrupt')
            (root/target).write_bytes(b'corrupted fixture')
            rejected=expected_error(lambda:resolve(root),'TRANSITION_EVIDENCE_MISSING_OR_CHANGED')
            return rejected and (root/target).exists() and (root/('.pending-'+target)).exists()
        def snapshot():
            root=fixture('snapshot')
            with m.evidence_directory(root):
                snapshot_bytes={k:m.read_evidence_blob(k) for k in blobs}
                directory_result=m.ticket_body(ticket)
            with m.evidence_scope(snapshot_bytes):
                memory_result=m.ticket_body(ticket)
                no_route=m.current_store_directory() is None
            broken=copy.deepcopy(snapshot_bytes)
            broken[target]=b'invalid'
            def invalid():
                with m.evidence_scope(broken):pass
            return (snapshot_bytes==blobs and directory_result==memory_result==body
                    and no_route and not (root/('.pending-'+target)).exists()
                    and expected_error(invalid,'TRANSITION_BUNDLE_BOUND_OR_HASH_CHANGED'))
        def child_route():
            root=fixture('child')
            # No account, key, import from the repo or unrestricted environment.
            child="""import hashlib,importlib.util,json,sys
from pathlib import Path
p=json.load(sys.stdin)
path=Path(p['source'])
raw=path.read_bytes()
blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\\0'+raw).hexdigest()
assert blob==p['blob']
spec=importlib.util.spec_from_file_location('native_evidence_child270b',path)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
try:
 if p['route'] is None: result=m.ticket_body(p['ticket'])
 else:
  with m.evidence_directory(p['route']):result=m.ticket_body(p['ticket'])
 print(json.dumps({'body_sha256':hashlib.sha256(m.canonical(result)).hexdigest()}))
except ValueError as e:
 print(json.dumps({'error':str(e)}))
"""
            expected=hashlib.sha256(m.canonical(body)).hexdigest()
            def launch(route):
                p={'source':str(source),'blob':BLOB,'ticket':ticket,'route':route}
                done=subprocess.run([sys.executable,'-I','-B','-c',child],
                    input=json.dumps(p),text=True,capture_output=True,check=True,cwd=base)
                return json.loads(done.stdout)
            with m.evidence_scope(blobs):
                absent=launch(None)
                still_pending=(root/('.pending-'+target)).exists()
                routed=launch(str(root))
            return (absent=={'error':'EXPLICIT_TRANSITION_EVIDENCE_SCOPE_REQUIRED'}
                    and still_pending and routed=={'body_sha256':expected}
                    and not (root/('.pending-'+target)).exists() and exact(root))
        for name,fn in [('directory_recovery',first),('idempotence',idempotent),
                        ('equal_result_different_effect',effect_difference),('non_alias_preserved',non_alias),
                        ('corruption_fails_closed',corrupted_alias),('snapshot_native_codec',snapshot),
                        ('isolated_child_requires_route',child_route)]:
            check(name,fn)
    cpu1=[resource.getrusage(k) for k in (resource.RUSAGE_SELF,resource.RUSAGE_CHILDREN)]
    cpu=[round((b.ru_utime+b.ru_stime)-(a.ru_utime+a.ru_stime),9) for a,b in zip(cpu0,cpu1)]
    receipt={'schema':'p0-270b-native-cas-effect/v1','source_commit':OWNER,'native_module_blob':BLOB,
             'executed_probe_blob':git_blob(Path(__file__).read_bytes()),'python':sys.version.split()[0],
             'checks':checks,'passed':sum(c['pass'] for c in checks),'total':len(checks),
             'accepted':len(checks)==7 and all(c['pass'] for c in checks),
             'self_cpu_seconds':cpu[0],'waited_child_cpu_seconds':cpu[1],
             'wall_seconds':time.monotonic()-started,'actual_billing':None,
             'scope':'NATIVE_CAS_CODEC_STORAGE_EFFECT_DEVELOPMENT_ONLY',
             'native_account_operation':False,'native_audit_equivalence':False,'cache_adopted':False}
    output.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    return 0 if receipt['accepted'] else 1

if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('usage: probe.py pinned-owner-transition_evidence.py receipt.json')
    raise SystemExit(run(Path(sys.argv[1]).resolve(strict=True),Path(sys.argv[2])))
