"""Independent P0-263 leaf memoization candidate; never run on an original account."""
import ast
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

OWNER = 'ced6c1cb004887dcdafaea59a2976020be649f8e'
PRIOR = '1851100612b8c80a1852f413057bdb635de62d3a'
METHODS = [
    'test_public_cli_upgrade_operation_resume_audit_and_scoreboard',
    'test_forward_engine_only_upgrade_preserves_prior_transition_and_same_business',
    'test_cached_historical_audit_rechecks_source_and_artifact_bytes',
]
HELPER = r'''
def _p0262_digest(raw):
    return hashlib.sha256(raw).hexdigest()

def _p0262_bound_path(root, name):
    rel = Path(name)
    if not name or rel.is_absolute() or '..' in rel.parts or rel.as_posix() != name:
        raise ValueError('P0262_NONCANONICAL_PATH')
    path = root / rel
    if not path.is_file() or any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError('P0262_NONREGULAR_MEMBER')
    return path

def _p0262_inventory(root):
    result = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink() or not (p.is_dir() or p.is_file()):
            raise ValueError('P0262_UNEXPECTED_MEMBER')
        if p.is_file():
            name = p.relative_to(root).as_posix()
            result[name] = _p0262_digest(_p0262_bound_path(root, name).read_bytes())
    return result

def _p0262_launch(kind, code, payload, root, files, manifest):
    import tempfile
    root = Path(root).absolute()
    deps = Path(os.environ['P0262_DEPS']).absolute()
    dep_manifest = Path(os.environ['P0262_DEP_MANIFEST']).read_bytes()
    if _p0262_digest(dep_manifest) != os.environ['P0262_DEP_MANIFEST_SHA']:
        raise ValueError('P0262_DEP_MANIFEST_CHANGED')
    dep_files = json.loads(dep_manifest)
    if _p0262_inventory(deps) != dep_files:
        raise ValueError('P0262_DEPENDENCIES_CHANGED')
    if source_inventory(root) != files:
        raise ValueError('P0262_SOURCE_CHANGED')
    bound = dict(files)
    for job in manifest['jobs']:
        for field in ('input', 'artifact', 'receipt'):
            name, expected = job[field], job[field+'_sha256']
            if name in bound and bound[name] != expected:
                raise ValueError('P0262_CONFLICTING_MEMBER')
            bound[name] = expected
    def verify_original():
        if source_inventory(root) != files:
            raise ValueError('P0262_SOURCE_CHANGED')
        for name, expected in bound.items():
            if _p0262_digest(_p0262_bound_path(root, name).read_bytes()) != expected:
                raise ValueError('P0262_BOUND_BYTES_CHANGED')
    with tempfile.TemporaryDirectory(prefix='p0262-stage-') as temporary:
        stage = Path(temporary)
        for name, expected in bound.items():
            raw = _p0262_bound_path(root, name).read_bytes()
            if _p0262_digest(raw) != expected:
                raise ValueError('P0262_BOUND_BYTES_CHANGED')
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        if _p0262_inventory(stage) != bound:
            raise ValueError('P0262_STAGE_CHANGED')
        env = {k: os.environ[k] for k in ('HOME','TMPDIR','P0262_DEPS','P0262_DEP_MANIFEST','P0262_DEP_MANIFEST_SHA','P0262_TRACE') if k in os.environ}
        env.update(PATH=os.defpath, LANG='C.UTF-8')
        prefix = 'import sys\nsys.path[:0]=' + repr([str(stage), str(deps)]) + '\n'
        # Preserve the original root in the authenticated payload and canonical
        # data lookup. Only module import resolution uses the staged tree.
        with open(env['P0262_TRACE'], 'a', encoding='utf-8') as trace:
            trace.write(kind+'\n')
        done = subprocess.run([sys.executable,'-I','-S','-B','-c',prefix+code],
                              input=json.dumps(payload), text=True, capture_output=True,
                              cwd=stage, env=env, timeout=60)
        verify_original()
        if _p0262_inventory(stage) != bound or _p0262_inventory(deps) != dep_files:
            raise ValueError('P0262_EXECUTION_CLOSURE_CHANGED')
        return done

'''
HELPER += r'''

def _p0263_leaf(record):
    return (not record.get('source_transitions') and
            not record.get('connected_journal', {}).get('source_history') and
            not any(a.get('op') == 'source_transition'
                    for a in record.get('ledger', {}).get('actions', [])))

def _p0263_context(root, files, manifest, payload, code):
    if not _p0263_leaf(payload['record']):
        return None
    root = Path(root).absolute()
    if source_inventory(root) != files:
        raise ValueError('P0263_SOURCE_CHANGED')
    for job in manifest['jobs']:
        for field in ('input', 'artifact', 'receipt'):
            name, expected = job[field], job[field+'_sha256']
            if _p0262_digest(_p0262_bound_path(root, name).read_bytes()) != expected:
                raise ValueError('P0263_SERVICE_BYTES_CHANGED')
    deps = Path(os.environ['P0262_DEPS']).absolute()
    dep_raw = Path(os.environ['P0262_DEP_MANIFEST']).read_bytes()
    if _p0262_digest(dep_raw) != os.environ['P0262_DEP_MANIFEST_SHA']:
        raise ValueError('P0263_DEP_MANIFEST_CHANGED')
    if _p0262_inventory(deps) != json.loads(dep_raw):
        raise ValueError('P0263_DEPENDENCIES_CHANGED')
    directory = payload.get('evidence_dir')
    store = None
    if directory is not None:
        scope = Path(directory).absolute()
        if not scope.is_dir() or any(p.is_symlink() for p in [scope,*scope.parents]):
            return None
        info = scope.stat()
        members = _p0262_inventory(scope)
        # Pending, unknown, nested or changed content never qualifies a hit.
        if any(len(n)!=64 or any(c not in '0123456789abcdef' for c in n)
               or n!=v for n,v in members.items()):
            return None
        store = {'path':str(scope),'device':info.st_dev,'inode':info.st_ino,'members':members}
    exe = Path(sys.executable).resolve()
    env = {k:os.environ[k] for k in ('HOME','TMPDIR','P0262_DEPS','P0262_DEP_MANIFEST',
             'P0262_DEP_MANIFEST_SHA','P0262_TRACE') if k in os.environ}
    return digest({'policy':'P0-263-leaf-only-v1','root':str(root),'files':files,
                   'manifest':manifest,'payload':payload,'code':code,
                   'launcher_sha256':_p0262_digest(Path(__file__).read_bytes()),
                   'interpreter':[str(exe),_p0262_digest(exe.read_bytes()),sys.version],
                   'flags':['-I','-S','-B'],'env':env,'path':os.defpath,'lang':'C.UTF-8',
                   'deps':str(deps),'dep_manifest_sha256':_p0262_digest(dep_raw),
                   'evidence':store})

def _p0263_trace_hit():
    with open(os.environ['P0262_TRACE'],'a',encoding='utf-8') as trace:
        trace.write('audit_hit\n')
'''

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def inventory(root):
    result = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink() or not (p.is_dir() or p.is_file()):
            raise ValueError('UNEXPECTED_DEP_MEMBER')
        if p.is_file():
            result[p.relative_to(root).as_posix()] = sha(p.read_bytes())
    return result

def head(root):
    return subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()

def build(owner, prior):
    sys.path.insert(0,str(prior/'research/source_transition_trust246'))
    from owner_patch253 import git_blob_id
    from owner_patch255 import patch_legacy_owner, static_gates
    old = (owner/'connected_enterprise/upgrades.py').read_bytes()
    codec = (owner/'connected_enterprise/transition_evidence.py').read_bytes()
    manifest = (owner/'historical/successor022/MANIFEST.json').read_bytes()
    if git_blob_id(old) != '9866d004c412fc05c9f6292cf898307f177359df':
        raise ValueError('OWNER_SOURCE_CHANGED')
    patch = patch_legacy_owner(old,codec,manifest)
    gates = static_gates(old,codec,manifest,patch)
    if not all(x['accepted'] for x in gates):
        raise ValueError('P0255_STATIC_GATES_FAILED')
    source = patch.decode()
    def replace(old, new):
        nonlocal source
        if source.count(old)!=1:
            raise ValueError('P0262_PATCH_ANCHOR_CHANGED')
        source=source.replace(old,new,1)
    replace('def verify_historical(',HELPER+'def verify_historical(')
    replace("    if cache_key in _HISTORICAL_AUDITS:\n        return copy.deepcopy(_HISTORICAL_AUDITS[cache_key])\n",
            "    # P0-262 conservative uncached control; no cache qualification.\n")
    replace("    if len(_HISTORICAL_AUDITS) >= 128:\n        _HISTORICAL_AUDITS.pop(next(iter(_HISTORICAL_AUDITS)))\n    _HISTORICAL_AUDITS[cache_key] = copy.deepcopy(receipt)\n","")
    for root,kind,files in [('root','audit',"body['verifier_files']"),('historical_root','authorize','files')]:
        old_call = ("    env = {**os.environ, 'PYTHONPATH': str("+root+"), 'PYTHONDONTWRITEBYTECODE': '1'}\n"
            "    done = subprocess.run([sys.executable, '-c', code], input=json.dumps(payload),\n"
            "                          text=True, capture_output=True, cwd="+root+", env=env, timeout=60)")
        replace(old_call,"    done = _p0262_launch("+repr(kind)+", code, payload, "+root+", "+files+", manifest)")
    replace("    done = _p0262_launch('audit', code, payload, root, body['verifier_files'], manifest)",
            "    context = _p0263_context(root, body['verifier_files'], manifest, payload, code)\n"
            "    memo_key = (cache_key, context)\n"
            "    if context is not None and memo_key in _HISTORICAL_AUDITS:\n"
            "        _p0263_trace_hit()\n"
            "        return copy.deepcopy(_HISTORICAL_AUDITS[memo_key])\n"
            "    done = _p0262_launch('audit', code, payload, root, body['verifier_files'], manifest)")
    replace("    load_jobs(root, manifest)\n    return receipt\n",
            "    load_jobs(root, manifest)\n"
            "    if context is not None:\n"
            "        if _p0263_context(root, body['verifier_files'], manifest, payload, code) != context:\n"
            "            raise ValueError('P0263_CONTEXT_CHANGED_DURING_AUDIT')\n"
            "        if len(_HISTORICAL_AUDITS) >= 128:\n"
            "            _HISTORICAL_AUDITS.pop(next(iter(_HISTORICAL_AUDITS)))\n"
            "        _HISTORICAL_AUDITS[memo_key] = copy.deepcopy(receipt)\n"
            "    return receipt\n")
    ast.parse(source)
    if 'codec_source' in source or 'exec(p[' in source:
        raise ValueError('SUCCESSOR_EXECUTION_REMAINS')
    return source.encode(),gates


def context_checks(patch):
    import tempfile
    # Execute only extracted pure helpers, never an owner account or signer.
    nodes = [n for n in ast.parse(patch).body if isinstance(n,ast.FunctionDef)
             and n.name in {'_p0262_digest','_p0262_bound_path','_p0262_inventory',
                            '_p0263_leaf','_p0263_context','source_inventory'}]
    ns = dict(hashlib=hashlib,json=json,os=os,Path=Path,sys=sys,
              __file__=__file__,digest=lambda x:sha(json.dumps(x,sort_keys=True).encode()))
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<context-checks>','exec'),ns)
    with tempfile.TemporaryDirectory(prefix='p0263-keyfree-') as temp:
        root=Path(temp)/'root';root.mkdir()
        dep=Path(temp)/'dep';dep.mkdir()
        scope=Path(temp)/'scope';scope.mkdir()
        py=root/'sample.py';py.write_bytes(b'x=1\n')
        data=root/'data.json';data.write_bytes(b'{}')
        wheel=dep/'module.py';wheel.write_bytes(b'x=2\n')
        manifest_path=Path(temp)/'deps.json'
        manifest_path.write_text(json.dumps(inventory(dep),sort_keys=True))
        keys={'P0262_DEPS':str(dep),'P0262_DEP_MANIFEST':str(manifest_path),
              'P0262_DEP_MANIFEST_SHA':sha(manifest_path.read_bytes())}
        old={k:os.environ.get(k) for k in keys};os.environ.update(keys)
        files=ns['source_inventory'](root)
        manifest={'jobs':[{k:v for field in ('input','artifact','receipt')
                            for k,v in ((field,'data.json'),(field+'_sha256',sha(data.read_bytes())))}]}
        payload={'record':{'ledger':{'actions':[]},'connected_journal':{}},'evidence_dir':str(scope)}
        def context():return ns['_p0263_context'](root,files,manifest,payload,'fixed')
        def rejects(path,marker):
            original=path.read_bytes()
            try:
                path.write_bytes(original+b'\n')
                try: context()
                except ValueError as e:return str(e)==marker
                return False
            finally:path.write_bytes(original)
        try:
            base=context()
            results={'stable_context':bool(base and base==context()),
                     'changed_source_rejected':rejects(py,'P0263_SOURCE_CHANGED'),
                     'changed_service_rejected':rejects(data,'P0263_SERVICE_BYTES_CHANGED'),
                     'changed_dependency_rejected':rejects(wheel,'P0263_DEPENDENCIES_CHANGED')}
            raw=b'{"synthetic":true}'
            (scope/sha(raw)).write_bytes(raw)
            results['changed_evidence_invalidates']=bool(context() and context()!=base)
            pending=scope/('.pending-'+sha(raw));pending.write_bytes(raw)
            results['pending_evidence_abstains']=context() is None
            pending.unlink()
            payload['record']['ledger']['actions']=[{'op':'source_transition'}]
            results['nested_history_abstains']=context() is None
            return results
        finally:
            for k,v in old.items():
                if v is None:os.environ.pop(k,None)
                else:os.environ[k]=v

def main():
    owner,prior,deps,out = map(lambda x:Path(x).resolve(),sys.argv[1:5])
    receipt={'owner_commit':OWNER,'prior_research_commit':PRIOR,'probe_sha256':sha(Path(__file__).read_bytes()),
             'cases':[],'accepted':False,'original_account_accessed':False,'actual_commerce':False,
             'cache_reuse_qualified':False,'whole_episode_billing_usd':None}
    start=time.monotonic()
    cpu0=resource.getrusage(resource.RUSAGE_CHILDREN)
    try:
        if head(owner)!=OWNER or head(prior)!=PRIOR: raise ValueError('WRONG_PINNED_HEAD')
        test=owner/'tests/test_connected_operating_upgrade.py'
        original_test=sha(test.read_bytes())
        patch,gates=build(owner,prior)
        receipt['context_checks']=context_checks(patch)
        if not all(receipt['context_checks'].values()):raise ValueError('P0263_CONTEXT_CHECK_FAILED')
        target=owner/'connected_enterprise/upgrades.py'
        target.write_bytes(patch)
        receipt.update(patch_sha256=sha(patch),static_gates=gates,owner_tests_sha256=original_test)
        private=out.parent/'p0262-private'
        private.mkdir(mode=0o700)
        dep_manifest=private/'deps.json'
        dep_manifest.write_text(json.dumps(inventory(deps),sort_keys=True,separators=(',',':')))
        receipt['dependency_manifest_sha256']=sha(dep_manifest.read_bytes())
        receipt['dependency_count']=len(json.loads(dep_manifest.read_text()))
        for i,method in enumerate(METHODS):
            case=private/str(i);case.mkdir(mode=0o700)
            trace=case/'launches.txt'
            env={'PATH':os.defpath,'HOME':str(private),'TMPDIR':str(case),
                 'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(owner),
                 'P0262_DEPS':str(deps),'P0262_DEP_MANIFEST':str(dep_manifest),
                 'P0262_DEP_MANIFEST_SHA':receipt['dependency_manifest_sha256'],'P0262_TRACE':str(trace)}
            before=resource.getrusage(resource.RUSAGE_CHILDREN);t=time.monotonic()
            log=case/'private.log'
            with log.open('wb') as stream:
                done=subprocess.run([sys.executable,'-B','-m','unittest','-v',
                    'tests.test_connected_operating_upgrade.OperatingUpgradeTests.'+method],
                    cwd=owner,env=env,stdout=stream,stderr=subprocess.STDOUT)
            after=resource.getrusage(resource.RUSAGE_CHILDREN)
            raw=log.read_bytes()
            launches=trace.read_text().splitlines() if trace.exists() else []
            row={'method':method,'exit':done.returncode,'wall_seconds':time.monotonic()-t,
                 'waited_child_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
                 'authorize_launches':launches.count('authorize'),'audit_launches':launches.count('audit'),
                 'audit_hits':launches.count('audit_hit'),
                 'private_log_sha256':sha(raw),
                 'diagnostic_markers':[s for s in ['P0262_','P0263_','ModuleNotFoundError','TimeoutExpired',
                      'SOURCE_UPGRADE_AUTHORIZATION_FAILED','PINNED_HISTORICAL_AUDIT_FAILED',
                      'AssertionError','FileNotFoundError','NameError','ImportError','SIGNATURE_MISMATCH'] if s.encode() in raw]}
            receipt['cases'].append(row)
            print(json.dumps(row,sort_keys=True),flush=True)
        receipt['owner_tests_unchanged']=sha(test.read_bytes())==original_test
        receipt['patched_source_unchanged']=target.read_bytes()==patch
        receipt['accepted']=(len(receipt['cases'])==len(METHODS) and
          all(x['exit']==0 and x['authorize_launches']>0 and x['audit_launches']>0 for x in receipt['cases']) and
          receipt['owner_tests_unchanged'] and receipt['patched_source_unchanged'] and
          sum(x['audit_hits'] for x in receipt['cases'])>0)
        receipt['cache_reuse_qualified']=receipt['accepted']
    except Exception as exc:
        receipt['failure_type']=type(exc).__name__
        # Exception messages may contain private paths. Do not export them.
        receipt['failure_code']=str(exc) if str(exc).startswith(('P0262_','P0263_','P0255_','WRONG_PINNED_HEAD','OWNER_SOURCE_CHANGED')) else 'SEE_PRIVATE_LOCAL_DIAGNOSTIC'
    finally:
        cpu1=resource.getrusage(resource.RUSAGE_CHILDREN)
        receipt['wall_seconds']=time.monotonic()-start
        receipt['waited_child_cpu_seconds']=cpu1.ru_utime+cpu1.ru_stime-cpu0.ru_utime-cpu0.ru_stime
        out.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    return 0 if receipt['accepted'] else 1

if __name__=='__main__':
    raise SystemExit(main())
