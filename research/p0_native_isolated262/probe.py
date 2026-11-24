"""Independent P0-262 candidate; never run on an original account."""
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
    ast.parse(source)
    if 'codec_source' in source or 'exec(p[' in source:
        raise ValueError('SUCCESSOR_EXECUTION_REMAINS')
    return source.encode(),gates

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
                 'private_log_sha256':sha(raw),
                 'diagnostic_markers':[s for s in ['P0262_','ModuleNotFoundError','TimeoutExpired',
                      'SOURCE_UPGRADE_AUTHORIZATION_FAILED','PINNED_HISTORICAL_AUDIT_FAILED',
                      'AssertionError','FileNotFoundError','NameError','ImportError','SIGNATURE_MISMATCH'] if s.encode() in raw]}
            receipt['cases'].append(row)
            print(json.dumps(row,sort_keys=True),flush=True)
        receipt['owner_tests_unchanged']=sha(test.read_bytes())==original_test
        receipt['patched_source_unchanged']=target.read_bytes()==patch
        receipt['accepted']=(len(receipt['cases'])==len(METHODS) and
          all(x['exit']==0 and x['authorize_launches']>0 and x['audit_launches']>0 for x in receipt['cases']) and
          receipt['owner_tests_unchanged'] and receipt['patched_source_unchanged'])
    except Exception as exc:
        receipt['failure_type']=type(exc).__name__
        # Exception messages may contain private paths. Do not export them.
        receipt['failure_code']=str(exc) if str(exc).startswith(('P0262_','P0255_','WRONG_PINNED_HEAD','OWNER_SOURCE_CHANGED')) else 'SEE_PRIVATE_LOCAL_DIAGNOSTIC'
    finally:
        cpu1=resource.getrusage(resource.RUSAGE_CHILDREN)
        receipt['wall_seconds']=time.monotonic()-start
        receipt['waited_child_cpu_seconds']=cpu1.ru_utime+cpu1.ru_stime-cpu0.ru_utime-cpu0.ru_stime
        out.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    return 0 if receipt['accepted'] else 1

if __name__=='__main__':
    raise SystemExit(main())
