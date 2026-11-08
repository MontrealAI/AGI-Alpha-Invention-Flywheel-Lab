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
from connected_enterprise.runner import LEGACY_RELEASE_PATHS, REACH_MARKERS, REACH_NATIVE_PATHS, REACH_RELEASE_PATHS, TRIAL_REACH_RELEASE_PATHS

SCHEMA='omega/packaged-v4-qualification/v1'
PROBE="from mechanism_harness.cart_native import source_identity; import json; print(json.dumps(source_identity(),sort_keys=True))"
REACH_PROBE = PROBE.replace('mechanism_harness.cart_native', 'mechanism_harness.reach_native')
REACH_SCHEMA = 'omega/packaged-paid-reach-qualification/v1'
AUTHORITY_SUFFIXES=('.actions.jsonl','.adaptive-simulation-key','.connected-journal.json','.adaptive-account.json','.adaptive-proofs.json','.adaptive-resolutions.json')
# Only these two immutable trial paths are added to the native source map.
# The rest of the trial closure is mandatory in a packaged trial edition.
TRIAL_NATIVE_SOURCE_PATHS = frozenset({
    'campaign/omega-trial-once-20261107/PROTOCOL.md',
    'tests/test_omega_trial_once_20261107.py',
})


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return strict_json(Path(path).read_bytes())
def write(path,value):Path(path).write_bytes(canonical(value)+b'\n')


def reach_source(manifest):
    """A partial pilot cannot fall back to the historical V4-only receipt."""
    files = manifest.get('files', {})
    if not REACH_MARKERS.intersection(files) and 'omega_reach_native_source' not in manifest:
        return None
    cart = manifest.get('omega_v4_native_source')
    if (not isinstance(cart, dict) or not set(cart).issuperset({
            'mechanism_harness/cart_native.py', 'mechanism_harness/cart_decision.py',
            'mechanism_harness/inventor_native.py'})):
        raise ValueError('PAID_REACH_REQUIRES_V4_NATIVE_SOURCE')
    native = manifest.get('omega_reach_native_source')
    # A trial edition is required whenever its file closure is advertised OR
    # its native source map refers to a trial file. No manifest downgrade by
    # dropping all trial files while retaining the new native source map.
    trial = bool(set(TRIAL_REACH_RELEASE_PATHS).intersection(files)
                 or (isinstance(native, dict)
                     and TRIAL_NATIVE_SOURCE_PATHS.intersection(native)))
    expected = set(cart) | set(REACH_NATIVE_PATHS)
    required = expected | set(REACH_RELEASE_PATHS) | set(LEGACY_RELEASE_PATHS)
    if trial:
        expected |= TRIAL_NATIVE_SOURCE_PATHS
        required |= set(TRIAL_REACH_RELEASE_PATHS)
    if (not isinstance(native, dict) or set(native) != expected
            or not required <= files.keys()
            or any(native[name] != value for name, value in cart.items())
            or any(files.get(name) != value for name, value in native.items())):
        raise ValueError('PAID_REACH_EXACT_NATIVE_SOURCE_CLOSURE_REQUIRED')
    return native


def account_actions(target, reach=False):
    if reach:
        module = 'mechanism_harness.reach_native'
        return [('source-identity', ['-c', REACH_PROBE]),
                ('run', ['-m', module, 'run', target, '--arm', 'pilot', '--scenario', 'central']),
                ('audit', ['-m', module, 'audit', target]),
                ('resume', ['-m', module, 'resume', target])]
    return [('source-identity', ['-c', PROBE])] + [
        (stage, ['-m', 'mechanism_harness.cart_native', stage, '--arm', 'adaptive',
                 '--stress', 'central', '--output', target]) for stage in ('run', 'audit', 'resume')]


def checked_commands(rows, reach=False):
    if (not isinstance(rows, list) or len(rows) != 4 or any(not isinstance(r, dict) for r in rows)
            or not isinstance(rows[1].get('command'), list) or len(rows[1]['command']) < 5):
        raise ValueError('COMPLETE_V4_COMMAND_SEQUENCE_REQUIRED')
    target = rows[1]['command'][4 if reach else -1]
    if not isinstance(target, str) or not Path(target).is_absolute() or (reach and '..' in Path(target).parts):
        raise ValueError('ABSOLUTE_V4_ENGINEERING_ACCOUNT_REQUIRED')
    for row, (stage, args) in zip(rows, account_actions(target, reach)):
        command = row.get('command')
        if (row.get('stage') != stage or not isinstance(command, list) or command[1:] != args
                or type(row.get('returncode')) is not int or row['returncode'] != 0):
            raise ValueError('DECLARED_SUCCESSFUL_V4_COMMAND_REQUIRED')
        for stream in ('stdout_sha256', 'stderr_sha256'):
            value = row.get(stream)
            if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
                raise ValueError('V4_COMMAND_LOG_HASH_REQUIRED')
    return Path(target)


def validate_reach(receipt, manifest, cart_account):
    native = reach_source(manifest)
    if native is None:
        if 'paid_reach' in receipt:
            raise ValueError('UNREGISTERED_PAID_REACH_RECEIPT')
        return
    nested = receipt.get('paid_reach')
    bound = ('source_commit', 'source_sha256', 'source_archive_sha256', 'actual_release_download')
    keys = {'schema', 'primary', 'arm', 'scenario', 'native_source_sha256', 'commands',
            'native_export_sha256', 'accepted', 'native_audit_accepted', 'completed_resume_export_unchanged',
            'completed_resume_authority_unchanged', *bound}
    if receipt['actual_release_download']:
        keys.add('download_receipt_sha256')
        bound += ('download_receipt_sha256',)
    if (not isinstance(nested, dict) or set(nested) != keys or nested['schema'] != REACH_SCHEMA
            or nested['primary'] is not False or nested['arm'] != 'pilot' or nested['scenario'] != 'central'
            or type(nested['actual_release_download']) is not bool
            or any(nested[key] != receipt[key] for key in bound)
            or nested['native_source_sha256'] != digest(native)
            or any(nested[key] is not True for key in ('accepted', 'native_audit_accepted',
                   'completed_resume_export_unchanged', 'completed_resume_authority_unchanged'))):
        raise ValueError('SOURCE_BOUND_PAID_REACH_RECEIPT_REQUIRED')
    export = nested['native_export_sha256']
    if not isinstance(export, str) or len(export) != 64 or any(c not in '0123456789abcdef' for c in export):
        raise ValueError('PAID_REACH_NATIVE_EXPORT_REQUIRED')
    reach_account = checked_commands(nested['commands'], reach=True)
    fields = {'stage', 'command', 'returncode', 'stdout_sha256', 'stderr_sha256'}
    interpreter = receipt['commands'][0]['command'][0]
    if (not isinstance(interpreter, str) or any(set(row) != fields or row['command'][0] != interpreter
            for row in nested['commands'])
            or reach_account != cart_account.parent / 'paid-reach' / 'engineering-account'):
        raise ValueError('SEPARATE_COMPACT_PAID_REACH_OPERATION_REQUIRED')

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
    if receipt['actual_release_download']:
        value=receipt.get('download_receipt_sha256')
        if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('ACTUAL_RELEASE_DOWNLOAD_RECEIPT_REQUIRED')
    validate_reach(receipt, source_manifest, checked_commands(receipt.get('commands')))
    return receipt


def exercise_account(source, logs, operation, native, deadline, receipt, reach=False):
    before_export = before_authority = None
    for index, (stage, args) in enumerate(account_actions(str(operation), reach), 1):
        log = logs / f'{index:02d}-{stage}'
        commands = [] if reach else receipt['commands']
        try:
            row = run_command([sys.executable, *args], source, log, deadline, commands)
        finally:
            if reach and commands:
                # Failed commands also export only the permitted fields.
                item = commands[-1]
                receipt['commands'].append({'stage': stage, 'command': item['command'],
                    'returncode': item['returncode'], 'stdout_sha256': sha(log.with_suffix('.stdout')),
                    'stderr_sha256': sha(log.with_suffix('.stderr'))})
        if not reach:
            row.update(stage=stage, stdout_sha256=sha(log.with_suffix('.stdout')),
                       stderr_sha256=sha(log.with_suffix('.stderr')))
        if stage == 'source-identity':
            if read(log.with_suffix('.stdout')) != native:
                raise ValueError('EXTRACTED_V4_NATIVE_IDENTITY_CHANGED')
        elif stage == 'run':
            before_export = (operation/'NATIVE_EXPORT.json').read_bytes()
            before_authority = authority_hashes(operation)
        elif stage == 'audit':
            if read(log.with_suffix('.stdout')).get('accepted') is not True:
                raise ValueError('PACKAGED_V4_AUDIT_REJECTED')
            receipt['native_audit_accepted'] = True
        elif stage == 'resume':
            if (operation/'NATIVE_EXPORT.json').read_bytes() != before_export:
                raise ValueError('PACKAGED_V4_RESUME_CHANGED_EXPORT')
            if authority_hashes(operation) != before_authority:
                raise ValueError('PACKAGED_V4_RESUME_CHANGED_AUTHORITY')
            receipt.update(completed_resume_export_unchanged=True, completed_resume_authority_unchanged=True,
                           native_export_sha256=hashlib.sha256(before_export).hexdigest())
    if read(operation/'SOURCE.json') != native:
        raise ValueError('ENGINEERING_ACCOUNT_SOURCE_CHANGED')
    if reach:
        contract = read(operation/'CONTRACT.json')
        if (contract.get('arm') != 'pilot' or contract.get('scenario') != 'central'
                or contract.get('source_sha256') != digest(native)):
            raise ValueError('PAID_REACH_ENGINEERING_CONTRACT_CHANGED')


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
        exercise_account(source, output, operation, native, deadline, receipt)
        pilot = reach_source(manifest)
        if pilot is not None:
            logs = output/'paid-reach'
            logs.mkdir()
            nested = {key: receipt[key] for key in ('source_commit', 'source_sha256', 'source_archive_sha256',
                      'actual_release_download', 'download_receipt_sha256') if key in receipt}
            nested.update(schema=REACH_SCHEMA, primary=False, arm='pilot', scenario='central',
                          native_source_sha256=digest(pilot), commands=[], accepted=False)
            receipt['paid_reach'] = nested
            exercise_account(source, logs, logs/'engineering-account', pilot, deadline, nested, reach=True)
            nested['accepted'] = True
        if verify_source(source,archive)!=manifest:raise ValueError('PACKAGED_V4_SOURCE_CHANGED')
        report=read(operation/'REPORT.json')
        if report['source']!=native:raise ValueError('ENGINEERING_ACCOUNT_SOURCE_CHANGED')
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
