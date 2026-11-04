"""Qualify a sealed GENESIS source distribution in a fresh simulated account.

Only QUALIFICATION.json and public/ are publishable. Private operation
recovery state and command logs are preserved, including on failure.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.release_connected014 import archive_manifest, commit, read, write
from scripts.qualify_connected014 import run_command
from connected_enterprise.platform_runtime import command_budget

SCHEMA = 'genesis-enterprise/packaged-qualification/v1'
NUMERICAL_PINS = {'numpy': '2.3.5', 'scipy': '1.17.0'}
PROBE = """import hashlib, json, pathlib, sys
from genesis_enterprise import native
root = pathlib.Path.cwd().resolve()
files = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in native.source_files(root)}
packages = {pathlib.PurePosixPath(name).parts[0] for name in files if name.endswith('.py')}
for name, module in list(sys.modules.items()):
    if name.split('.')[0] not in packages:
        continue
    expected = root.joinpath(*name.split('.'))
    origin = getattr(module, '__file__', None)
    if origin is None:
        locations = list(getattr(module, '__path__', ()))
        valid = bool(locations) and all(pathlib.Path(p).resolve() == expected for p in locations)
    else:
        valid = pathlib.Path(origin).resolve() in (expected.with_suffix('.py'), expected / '__init__.py')
    if not valid:
        raise ValueError('EXTRACTED_MODULE_ORIGIN_REQUIRED:' + name)
print(json.dumps({'files': files, 'sha256': native.digest(files)}, sort_keys=True))
"""


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe(path):
    path = Path(path).absolute()
    if '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('REGULAR_UNTRAVERSED_PATH_REQUIRED')
    return path


def verify_source(source, archive):
    source, archive = safe(source), safe(archive)
    if any((p / '.git').exists() for p in (source, *source.parents)):
        raise ValueError('EXTRACTED_SOURCE_NOT_CHECKOUT_REQUIRED')
    manifest = archive_manifest(archive)
    if read(source / 'SOURCE_MANIFEST.json') != manifest:
        raise ValueError('EXTRACTED_MANIFEST_CHANGED')
    actual = set()
    for path in source.rglob('*'):
        safe(path)
        if path.is_file():
            actual.add(path.relative_to(source).as_posix())
        elif not path.is_dir():
            raise ValueError('REGULAR_SOURCE_FILES_REQUIRED')
    if actual != set(manifest['files']) | {'SOURCE_MANIFEST.json'}:
        raise ValueError('EXACT_EXTRACTED_SOURCE_REQUIRED')
    for name, expected in manifest['files'].items():
        if sha(safe(source / name)) != expected:
            raise ValueError('EXTRACTED_SOURCE_CHANGED:' + name)
    from connected_enterprise.runner import genesis_release_paths
    from genesis_enterprise.native import source_files
    closure = genesis_release_paths(source)
    if not closure or not set(closure).issubset(manifest['files']):
        raise ValueError('COMPLETE_GENESIS_RELEASE_REQUIRED')
    names = source_files(source)
    if not names or not set(names).issubset(manifest['files']):
        raise ValueError('COMPLETE_GENESIS_NATIVE_SOURCE_REQUIRED')
    files = {name: manifest['files'][name] for name in names}
    identity = {'files': files, 'sha256': hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()}
    return manifest, identity


def validate_download(path, manifest, archive_sha256, source_commit):
    downloaded = read(safe(path))
    if (downloaded.get('schema') != 'agi-alpha/connected014-actual-release-download/v1'
            or downloaded.get('actual_release_download') is not True
            or downloaded.get('source_commit') != source_commit
            or downloaded.get('tag') != 'connected014-' + source_commit
            or downloaded.get('source_sha256') != manifest['executing_source']['sha256']
            or downloaded.get('files', {}).get('connected014-source.zip') != archive_sha256):
        raise ValueError('ACTUAL_RELEASE_DOWNLOAD_BINDING_REQUIRED')
    return sha(path)


def runtime_versions(source):
    pins = dict(NUMERICAL_PINS)
    for line in (source / 'requirements-commercial010.txt').read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        name, expected = line.strip().split('==', 1)
        pins[name] = expected
    if 'cryptography' not in pins:
        raise ValueError('PINNED_CRYPTO_RUNTIME_REQUIRED')
    for name, expected in pins.items():
        if importlib.metadata.version(name) != expected:
            raise ValueError('PINNED_DEPENDENCY_REQUIRED:' + name)
    return {'python': sys.version, 'dependencies': pins, 'installation': 'NOT_PERFORMED; exact preinstalled pins checked'}


def command_actions(operation, public):
    return [('source-identity', ['-c', PROBE]),
            ('pilot', ['-m', 'connected_enterprise.genesis', 'pilot', '--output', str(operation)]),
            ('resume', ['-m', 'connected_enterprise.genesis', 'resume', '--output', str(operation)]),
            ('audit', ['-m', 'connected_enterprise.genesis', 'audit', '--output', str(operation)]),
            ('export', ['-m', 'connected_enterprise.genesis', 'export', '--output', str(operation), '--destination', str(public)]),
            ('public-audit', ['-m', 'connected_enterprise.genesis', 'audit', '--output', str(public)])]


def validate_receipt(receipt, manifest, archive_sha256, source_commit):
    from genesis_enterprise.native import source_files
    from connected_enterprise.runner import GENESIS_RELEASE_PATHS
    files = manifest['files']
    if not set(GENESIS_RELEASE_PATHS).issubset(files):
        raise ValueError('COMPLETE_GENESIS_RELEASE_REQUIRED')
    names = source_files(ROOT)
    if not set(names).issubset(files):
        raise ValueError('COMPLETE_GENESIS_NATIVE_SOURCE_REQUIRED')
    native_files = {name: files[name] for name in names}
    native = {'files': native_files, 'sha256': hashlib.sha256(json.dumps(native_files,
        sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()}
    if (not isinstance(receipt, dict) or receipt.get('schema') != SCHEMA
            or receipt.get('source_commit') != commit(source_commit)
            or receipt.get('source_sha256') != manifest['executing_source']['sha256']
            or receipt.get('source_archive_sha256') != archive_sha256
            or receipt.get('native_source') != native
            or receipt.get('native_source_sha256') != native['sha256']
            or type(receipt.get('actual_release_download')) is not bool):
        raise ValueError('SOURCE_BOUND_GENESIS_QUALIFICATION_REQUIRED')
    for key in ('accepted', 'no_git_execution', 'source_files_unchanged',
                'completed_resume_export_unchanged', 'native_audit_accepted', 'public_audit_accepted'):
        if receipt.get(key) is not True:
            raise ValueError('EXECUTED_GENESIS_QUALIFICATION_REQUIRED:' + key)
    def valid_hash(value):
        return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)
    if not valid_hash(receipt.get('native_export_sha256')) or receipt.get('public_export') != 'public':
        raise ValueError('KEYFREE_NATIVE_EXPORT_REQUIRED')
    if receipt['actual_release_download'] and not valid_hash(receipt.get('download_receipt_sha256')):
        raise ValueError('ACTUAL_RELEASE_DOWNLOAD_RECEIPT_REQUIRED')
    rows = receipt.get('commands')
    if (not isinstance(rows, list) or len(rows) != 6 or any(not isinstance(row, dict) for row in rows)
            or not isinstance(rows[1].get('command'), list) or len(rows[1]['command']) != 6):
        raise ValueError('COMPLETE_GENESIS_COMMAND_SEQUENCE_REQUIRED')
    operation = Path(rows[1]['command'][-1])
    if not operation.is_absolute() or '..' in operation.parts or operation.name != 'engineering-account':
        raise ValueError('ABSOLUTE_SEPARATE_GENESIS_ACCOUNT_REQUIRED')
    interpreter = rows[1]['command'][0]
    if not isinstance(interpreter, str) or not interpreter:
        raise ValueError('GENESIS_INTERPRETER_REQUIRED')
    for row, (stage, args) in zip(rows, command_actions(operation, operation.parent / 'public')):
        if (row.get('stage') != stage or row.get('command') != [interpreter, *args]
                or type(row.get('returncode')) is not int or row['returncode'] != 0
                or any(not valid_hash(row.get(key)) for key in ('stdout_sha256', 'stderr_sha256'))):
            raise ValueError('SUCCESSFUL_GENESIS_COMMAND_REQUIRED')
    return receipt


def qualify(source, archive, output, source_commit, download_receipt=None):
    source, archive, output = safe(source), safe(archive), safe(output)
    source_commit = commit(source_commit)
    if source.resolve() != ROOT:
        raise ValueError('EXECUTE_HELPER_FROM_EXTRACTED_SOURCE_REQUIRED')
    if source == output or source in output.parents:
        raise ValueError('OUTPUT_OUTSIDE_SOURCE_REQUIRED')
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    receipt = {'schema': SCHEMA, 'accepted': False, 'source_commit': source_commit,
               'actual_release_download': False, 'commands': [],
               'scope': 'Fresh native simulation; no real commerce, original-account migration or discovery-superiority claim.'}
    try:
        manifest, native = verify_source(source, archive)
        receipt.update(source_sha256=manifest['executing_source']['sha256'],
                       source_archive_sha256=sha(archive), native_source=native,
                       native_source_sha256=native['sha256'], no_git_execution=True)
        if download_receipt is not None:
            receipt['download_receipt_sha256'] = validate_download(download_receipt, manifest, sha(archive), source_commit)
            receipt['actual_release_download'] = True
        receipt['runtime'] = runtime_versions(source)
        budget = command_budget(None)
        receipt['runtime_budget'] = budget
        seconds = budget['timeout_seconds']
        deadline = None if seconds is None else time.monotonic() + seconds
        operation, public = output / 'engineering-account', output / 'public'
        actions = command_actions(operation, public)
        before = None
        for index, (stage, args) in enumerate(actions):
            log = output / f'{index:02d}-{stage}'
            rows = []
            try:
                run_command([sys.executable, *args], source, log, deadline, rows)
            finally:
                receipt['commands'].append({'stage': stage, 'command': [sys.executable, *args],
                    'returncode': rows[-1]['returncode'] if rows else None,
                    'stdout_sha256': sha(log.with_suffix('.stdout')) if log.with_suffix('.stdout').is_file() else None,
                    'stderr_sha256': sha(log.with_suffix('.stderr')) if log.with_suffix('.stderr').is_file() else None})
            result = read(log.with_suffix('.stdout'))
            if stage == 'source-identity' and result != native:
                raise ValueError('EXTRACTED_NATIVE_IDENTITY_CHANGED')
            if stage in ('pilot', 'resume', 'audit', 'public-audit'):
                if any(result.get(key) is not True for key in ('accepted', 'complete', 'native_audit_accepted')):
                    raise ValueError('COMPLETE_NATIVE_AUDIT_REQUIRED:' + stage)
            if stage == 'pilot':
                before = (operation / 'public/native-export.json').read_bytes()
            if stage == 'resume':
                if (operation / 'public/native-export.json').read_bytes() != before:
                    raise ValueError('COMPLETED_RESUME_CHANGED_NATIVE_EXPORT')
                receipt['completed_resume_export_unchanged'] = True
            if stage == 'export' and (result.get('accepted') is not True or result.get('contains_recovery_authority') is not False):
                raise ValueError('KEYFREE_PUBLIC_EXPORT_REQUIRED')
        if read(operation / 'SOURCE.json') != native or read(public / 'SOURCE.json') != native:
            raise ValueError('OPERATION_SOURCE_IDENTITY_CHANGED')
        if (public / 'public/native-export.json').read_bytes() != before:
            raise ValueError('PUBLIC_NATIVE_EXPORT_CHANGED')
        if verify_source(source, archive) != (manifest, native):
            raise ValueError('SOURCE_CHANGED_DURING_QUALIFICATION')
        receipt.update(accepted=True, source_files_unchanged=True, native_audit_accepted=True,
                       public_audit_accepted=True, native_export_sha256=hashlib.sha256(before).hexdigest(),
                       public_export='public', actual_revenue=0)
        validate_receipt(receipt, manifest, sha(archive), source_commit)
    except BaseException as exc:
        receipt['accepted'] = False
        receipt['failure'] = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        receipt['wall_seconds'] = time.monotonic() - started
        write(output / 'QUALIFICATION.json', receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'archive', 'output', 'source-commit'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--download-receipt')
    args = parser.parse_args(argv)
    result = qualify(args.source, args.archive, args.output, args.source_commit, args.download_receipt)
    print(json.dumps({'accepted': result['accepted'], 'actual_release_download': result['actual_release_download'],
                      'receipt': str(Path(args.output) / 'QUALIFICATION.json')}, sort_keys=True))


if __name__ == '__main__':
    main()
