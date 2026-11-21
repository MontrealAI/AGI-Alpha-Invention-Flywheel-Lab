"""Bind a frozen package to the unchanged scientific checker without code review.

Manifest: {package_root, entry, source_hashes:{relative_path:sha256},
           construction_freeze_path(optional)}. Source is hashed, never displayed.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import resource
import runpy
import sys
import tempfile
import time

HERE=Path(__file__).resolve().parent
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources(root):
    return {str(p.relative_to(root)):digest(p) for p in sorted(root.rglob('*.py')) if p.is_file()}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',required=True)
    parser.add_argument('--output',required=True);parser.add_argument('--receipt',required=True)
    args=parser.parse_args();started=time.perf_counter();cpu=time.process_time()
    manifest_path=Path(args.manifest).resolve();manifest=json.loads(manifest_path.read_text())
    root=Path(manifest['package_root']).resolve();entry=(root/manifest['entry']).resolve()
    expected=manifest['source_hashes']
    if not entry.is_relative_to(root):raise ValueError('Entry escapes package root')
    if manifest['entry'] not in expected:raise ValueError('Entry is not in frozen source map')
    for name,sha in expected.items():
        path=(root/name).resolve()
        if not path.is_relative_to(root):raise ValueError('Dependency escapes package root')
        if digest(path)!=sha:raise ValueError('Frozen source mismatch: '+name)
    before=sources(root)
    resource.setrlimit(resource.RLIMIT_AS,(10*1024**3,10*1024**3))
    receipt={'schema':'frontier.executed_source_package.v1',
             'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'manifest_path':str(manifest_path),'manifest_sha256':digest(manifest_path),
             'wrapper_sha256':digest(__file__),'checker_sha256':digest(HERE/'qualify.py'),
             'entry':str(entry),'expected_source_hashes':expected,'all_package_python_sources_before':before,
             'ordinary_process_memory_limit_bytes':10*1024**3,
             'procedural_scope':'Source identity and read-only verification; no adversarial execution-security claim.'}
    if manifest.get('construction_freeze_path'):
        freeze=Path(manifest['construction_freeze_path']).resolve()
        receipt['construction_freeze_path']=str(freeze)
        receipt['construction_freeze_sha256']=digest(freeze)
    error=None
    try:
        # An empty cache prefix prevents stale package bytecode from substituting
        # for the exact hashed source. It does not modify constructor workspaces.
        with tempfile.TemporaryDirectory(prefix='frontier-verifier-pycache-') as cache:
            sys.pycache_prefix=cache
            sys.argv=[str(HERE/'qualify.py'),str(entry),'--output',str(Path(args.output).resolve())]
            runpy.run_path(str(HERE/'qualify.py'),run_name='__main__')
    except BaseException as exc:
        error=type(exc).__name__+': '+str(exc)
        receipt['execution_error']=error
    imported={};unbound=[];outside_workspace=[]
    workspace=HERE.parents[2]
    for name,module in list(sys.modules.items()):
        file=getattr(module,'__file__',None)
        if not file:continue
        path=Path(file).resolve()
        if path.suffix not in ('.py','.pyc'):continue
        if path.suffix=='.pyc':continue
        if path.is_relative_to(root):
            rel=str(path.relative_to(root));sha=digest(path)
            imported[name]={'relative_path':rel,'sha256':sha}
            if expected.get(rel)!=sha:unbound.append(rel)
        elif path.is_relative_to(workspace) and not path.is_relative_to(HERE):
            outside_workspace.append({'module':name,'path':str(path),'sha256':digest(path)})
    after=sources(root)
    receipt.update({'loaded_package_modules':imported,'unbound_loaded_source_paths':sorted(set(unbound)),
                    'loaded_other_workspace_python_sources':outside_workspace,
                    'all_package_python_sources_after':after,
                    'source_tree_unchanged':before==after,
                    'package_identity_pass':error is None and not unbound and not outside_workspace and before==after,
                    'wall_seconds':time.perf_counter()-started,'cpu_seconds':time.process_time()-cpu,
                    'maximum_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                    'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
    for package in ('numpy','scipy'):
        module=sys.modules.get(package)
        if module is not None:receipt.setdefault('runtime_versions',{})[package]=getattr(module,'__version__','unknown')
    output=Path(args.output)
    if output.exists():receipt['qualification_receipt_sha256']=digest(output)
    Path(args.receipt).write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'package_identity_pass':receipt['package_identity_pass'],
                      'loaded_package_source_count':len(imported),'wrapper_wall_seconds':receipt['wall_seconds']}))
    if error is not None:raise RuntimeError(error)


if __name__=='__main__':main()
