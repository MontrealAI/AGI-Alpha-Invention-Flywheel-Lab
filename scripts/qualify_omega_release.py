"""Qualify V4 from sealed source bytes using an independent engineering account.

This does not publish releases, install dependencies, alter original accounts, or
claim new commercial evidence. Only QUALIFICATION.json is intended for public
evidence; command logs and the private simulation recovery account remain local.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from commercial.ledger import canonical,digest,strict_json
from scripts.release_connected014 import archive_manifest,commit
from scripts.qualify_connected014 import run_command
from connected_enterprise.platform_runtime import command_budget

SCHEMA='omega/packaged-v4-qualification/v1'
PROBE="from mechanism_harness.cart_native import source_identity; import json; print(json.dumps(source_identity(),sort_keys=True))"
AUTHORITY_SUFFIXES=('.actions.jsonl','.adaptive-simulation-key','.connected-journal.json','.adaptive-account.json','.adaptive-proofs.json','.adaptive-resolutions.json')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return strict_json(Path(path).read_bytes())
def write(path,value):Path(path).write_bytes(canonical(value)+b'\n')


def authority_hashes(account):
    """Hash actual authority internally; checkpoint/cache metadata is derived."""
    result={}
    for suffix in AUTHORITY_SUFFIXES:
        p=Path(account)/('account.sqlite'+suffix)
        if suffix in ('.adaptive-proofs.json','.adaptive-resolutions.json') and not p.exists() and not p.is_symlink():
            result[suffix]=None;continue
        if not p.is_file() or any(q.is_symlink() for q in (p,*p.parents)):
            raise ValueError('EXISTING_REGULAR_V4_AUTHORITY_REQUIRED')
        result[suffix]=sha(p)
    return result


def verify_source(source,archive):
    source=Path(source);archive=Path(archive)
    if any(p.is_symlink() for p in (source,*source.parents,archive,*archive.parents)):
        raise ValueError('REGULAR_PACKAGED_V4_SOURCE_REQUIRED')
    manifest=archive_manifest(archive)
    if read(source/'SOURCE_MANIFEST.json')!=manifest:
        raise ValueError('EXTRACTED_V4_MANIFEST_CHANGED')
    native=manifest.get('omega_v4_native_source')
    if (not isinstance(native,dict) or not native
            or 'mechanism_harness/cart_native.py' not in native
            or 'mechanism_harness/cart_decision.py' not in native
            or any(manifest['files'].get(name)!=value for name,value in native.items())
            or 'requirements-omega-mechanisms-v3.txt' not in manifest['files']):
        raise ValueError('PACKAGED_V4_NATIVE_SOURCE_CLOSURE_REQUIRED')
    if any((p/'.git').exists() for p in (source,*source.parents)):
        raise ValueError('PACKAGED_V4_NO_GIT_EXECUTION_REQUIRED')
    for name,value in manifest['files'].items():
        p=source/name
        if not p.is_file() or any(q.is_symlink() for q in (p,*p.parents)) or sha(p)!=value:
            raise ValueError('EXTRACTED_V4_SOURCE_CHANGED:'+name)
    return manifest


def validate_receipt(receipt,source_manifest,archive_sha256,source_commit):
    expected_native=source_manifest.get('omega_v4_native_source')
    if (not isinstance(receipt,dict) or receipt.get('schema')!=SCHEMA
            or receipt.get('source_commit')!=commit(source_commit)
            or receipt.get('source_sha256')!=source_manifest['executing_source']['sha256']
            or receipt.get('source_archive_sha256')!=archive_sha256
            or not isinstance(expected_native,dict) or not expected_native
            or receipt.get('native_source')!=expected_native
            or receipt.get('native_source_sha256')!=digest(expected_native)
            or receipt.get('primary') is not False
            or receipt.get('mode')!='SEPARATE_ENGINEERING_REPRODUCTION'
            or type(receipt.get('actual_release_download')) is not bool):
        raise ValueError('SOURCE_BOUND_V4_QUALIFICATION_REQUIRED')
    for key in ('accepted','no_git_execution','source_files_unchanged','completed_resume_export_unchanged','completed_resume_authority_unchanged','native_audit_accepted'):
        if receipt.get(key) is not True:raise ValueError('EXECUTED_V4_QUALIFICATION_REQUIRED:'+key)
    rows=receipt.get('commands',[])
    if not isinstance(rows,list) or [r.get('stage') for r in rows]!=['source-identity','run','audit','resume']:
        raise ValueError('COMPLETE_V4_COMMAND_SEQUENCE_REQUIRED')
    operating_output=None
    if receipt['actual_release_download']:
        value=receipt.get('download_receipt_sha256')
        if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('ACTUAL_RELEASE_DOWNLOAD_RECEIPT_REQUIRED')
    for row in rows:
        if type(row.get('returncode')) is not int or row['returncode']!=0:
            raise ValueError('SUCCESSFUL_V4_COMMAND_REQUIRED')
        args=row.get('command',[])
        expected=['-c',PROBE] if row['stage']=='source-identity' else ['-m','mechanism_harness.cart_native',row['stage'],'--arm','adaptive','--stress','central','--output']
        size=1+len(expected)+(row['stage']!='source-identity')
        if not isinstance(args,list) or len(args)!=size or args[1:1+len(expected)]!=expected:
            raise ValueError('DECLARED_V4_COMMAND_REQUIRED')
        if row['stage']!='source-identity':
            target=args[-1]
            if not isinstance(target,str) or not target or not Path(target).is_absolute():
                raise ValueError('ABSOLUTE_V4_ENGINEERING_ACCOUNT_REQUIRED')
            if operating_output is None:operating_output=target
            elif target!=operating_output:raise ValueError('SAME_V4_ENGINEERING_ACCOUNT_REQUIRED')
        for stream in ('stdout_sha256','stderr_sha256'):
            value=row.get(stream)
            if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
                raise ValueError('V4_COMMAND_LOG_HASH_REQUIRED')
    return receipt


def qualify(source,archive,output,source_commit,download_receipt=None):
    source=Path(source).absolute();archive=Path(archive).absolute();output=Path(output).absolute()
    source_commit=commit(source_commit)
    if any(p.is_symlink() for p in (output,*output.parents)):raise ValueError('NEW_REGULAR_V4_OUTPUT_REQUIRED')
    output.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();commands=[]
    receipt={'schema':SCHEMA,'accepted':False,'source_commit':source_commit,'mode':'SEPARATE_ENGINEERING_REPRODUCTION','primary':False,
             'actual_release_download':download_receipt is not None,'commands':commands,
             'scope':'Sealed-source V4 engineering reproduction in a separate simulated account; original primary unchanged. No new demand, profit confirmation or release publication.'}
    try:
        manifest=verify_source(source,archive);native=manifest['omega_v4_native_source']
        receipt.update(source_sha256=manifest['executing_source']['sha256'],source_archive_sha256=sha(archive),native_source=native,native_source_sha256=digest(native),no_git_execution=True)
        if download_receipt is not None:
            downloaded=read(download_receipt)
            if (downloaded.get('schema')!='agi-alpha/connected014-actual-release-download/v1'
                    or downloaded.get('actual_release_download') is not True
                    or downloaded.get('source_commit')!=source_commit
                    or downloaded.get('tag')!='connected014-'+source_commit
                    or downloaded.get('source_sha256')!=receipt['source_sha256']
                    or downloaded.get('files',{}).get('connected014-source.zip')!=receipt['source_archive_sha256']):
                raise ValueError('ACTUAL_RELEASE_DOWNLOAD_BINDING_REQUIRED')
            receipt['download_receipt_sha256']=sha(download_receipt)
        deps={}
        for name in ('requirements-commercial010.txt','requirements-omega-mechanisms-v3.txt'):
            for line in (source/name).read_text().splitlines():
                if '==' not in line:continue
                package,pinned=line.strip().split('==',1);actual=importlib.metadata.version(package)
                if actual!=pinned:raise ValueError('PINNED_V4_DEPENDENCY_REQUIRED:'+package)
                deps[package]=actual
        receipt['runtime']={'python':sys.version,'dependencies':deps,'installation':'Exact available pins checked; no dependency installation performed by this command.'}
        budget=command_budget(None);seconds=budget['timeout_seconds'];deadline=None if seconds is None else time.monotonic()+seconds
        receipt['runtime_budget']=budget
        operation=output/'engineering-account'
        actions=[('source-identity',['-c',PROBE])]+[(action,['-m','mechanism_harness.cart_native',action,'--arm','adaptive','--stress','central','--output',str(operation)]) for action in ('run','audit','resume')]
        before_export=None;before_authority=None
        for index,(stage,args) in enumerate(actions,1):
            log=output/(str(index).zfill(2)+'-'+stage)
            row=run_command([sys.executable,*args],source,log,deadline,commands)
            row.update(stage=stage,stdout_sha256=sha(log.with_suffix('.stdout')),stderr_sha256=sha(log.with_suffix('.stderr')))
            if stage=='source-identity':
                if read(log.with_suffix('.stdout'))!=native:raise ValueError('EXTRACTED_V4_NATIVE_IDENTITY_CHANGED')
            elif stage=='run':
                before_export=(operation/'NATIVE_EXPORT.json').read_bytes();before_authority=authority_hashes(operation)
            elif stage=='audit':
                if read(log.with_suffix('.stdout')).get('accepted') is not True:raise ValueError('PACKAGED_V4_AUDIT_REJECTED')
                receipt['native_audit_accepted']=True
            elif stage=='resume':
                if (operation/'NATIVE_EXPORT.json').read_bytes()!=before_export:raise ValueError('PACKAGED_V4_RESUME_CHANGED_EXPORT')
                if authority_hashes(operation)!=before_authority:raise ValueError('PACKAGED_V4_RESUME_CHANGED_AUTHORITY')
                receipt.update(completed_resume_export_unchanged=True,completed_resume_authority_unchanged=True,native_export_sha256=hashlib.sha256(before_export).hexdigest())
        if verify_source(source,archive)!=manifest:raise ValueError('PACKAGED_V4_SOURCE_CHANGED')
        report=read(operation/'REPORT.json')
        if report['source']!=native or read(operation/'SOURCE.json')!=native:raise ValueError('ENGINEERING_ACCOUNT_SOURCE_CHANGED')
        receipt.update(accepted=True,source_files_unchanged=True,opportunities=report['opportunities'],settled_buyers=report['settled_buyers'],declined_buyers=report['declined_buyers'],actual_revenue_usd=0)
        validate_receipt(receipt,manifest,sha(archive),source_commit)
    except BaseException as exc:
        receipt['accepted']=False;receipt['failure']={'type':type(exc).__name__,'message':str(exc)}
        raise
    finally:
        receipt['wall_seconds']=time.monotonic()-started
        write(output/'QUALIFICATION.json',receipt)
    return receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('source','archive','output','source-commit'):parser.add_argument('--'+arg,required=True)
    parser.add_argument('--download-receipt');args=parser.parse_args(argv)
    result=qualify(args.source,args.archive,args.output,args.source_commit,args.download_receipt)
    print(json.dumps({'accepted':result['accepted'],'actual_release_download':result['actual_release_download'],'receipt':str(Path(args.output)/'QUALIFICATION.json')},sort_keys=True))

if __name__=='__main__':main()
