# SPDX-License-Identifier: Apache-2.0
"""Local lifecycle for bounded instruments. No external deployment or purchase authority."""
from __future__ import annotations
import argparse
from contextlib import contextmanager, nullcontext
import hashlib
import io
import zipfile
import json
import os
from pathlib import Path
import re
import uuid
from .adapters import BridgeError
from .instruments import evaluate, strict_portable_json, _json_equal, LOADED_SOURCE_SHA256

LIFECYCLE_LOADED_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

ID = re.compile(r'[a-z][a-z0-9_-]{0,63}\Z')
HEX = re.compile(r'[0-9a-f]{64}\Z')

def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()

def evaluator_identity():
    current = hashlib.sha256(Path(__file__).with_name('instruments.py').read_bytes()).hexdigest()
    if current != LOADED_SOURCE_SHA256:
        raise ValueError('Loaded evaluator differs from disk; restart and requalify')
    return current

def read(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('Missing or unsafe local record')
    return strict_portable_json(path.read_text())

def write(path, value):
    temp = path.with_name('.' + uuid.uuid4().hex + '.tmp')
    try:
        with os.fdopen(os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w', encoding='utf8') as stream:
            json.dump(value, stream, sort_keys=True, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)

def qualify(release):
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != LIFECYCLE_LOADED_SHA256 or release.get('lifecycle_sha256') != LIFECYCLE_LOADED_SHA256:
        raise ValueError('Deployment lifecycle changed; requalification required')
    if release.get('evaluator_sha256') != evaluator_identity():
        raise ValueError('Evaluator changed; requalification required')
    bound = release.get('max_operations')
    if type(bound) is not int or bound < 1 or bound > 1000000:
        raise ValueError('Invalid bounded evaluator operation limit')
    cases = release.get('cases')
    if not isinstance(cases, list) or not cases:
        raise ValueError('Independent acceptance cases required')
    for case in cases:
        if not isinstance(case, dict) or set(case) != {'input', 'expected'}:
            raise ValueError('Malformed acceptance case')
        if not _json_equal(evaluate(release['instrument'], case['input'], max_operations=bound)['output'], case['expected']):
            raise ValueError('Acceptance case failed')
    return len(cases)

class LocalDeployment:
    """Owner-controlled local store, not authenticated enterprise authorization."""
    def __init__(self, root, target, workshop_service=None):
        if not ID.fullmatch(target):
            raise ValueError('Invalid target identifier')
        root = Path(root)
        if root.is_symlink():
            raise ValueError('Symlink store refused')
        self.path = root / target
        if self.path.is_symlink():
            raise ValueError('Symlink target refused')
        if any(p.is_symlink() for p in (self.path, *self.path.parents)):
            raise ValueError('Symlink ancestor refused')
        self.path.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.workshop_service = workshop_service
        self._safe_path()

    def _safe_path(self):
        if any(p.is_symlink() for p in (self.path, *self.path.parents)):
            raise ValueError('Symlink ancestor refused')
        if os.name == 'posix' and self.path.stat().st_mode & 0o077:
            raise ValueError('Deployment target must be private (0700)')

    def _workshop_snapshot(self, binding):
        if self.workshop_service is None:
            raise ValueError('Bound workshop authority must be reopened before use')
        from . import workshop
        view = workshop.operate(self.workshop_service, 'get', {'run_id': binding['run_id']})
        if view['revision'] != binding['revision'] or not view['docket'].get('passed') or not view['docket'].get('current'):
            raise ValueError('Workshop admission changed or was revoked')
        blob = workshop.bundle(self.workshop_service, binding)
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            instrument = strict_portable_json(archive.read('instrument.json').decode())
            proof = strict_portable_json(archive.read('PROOF.json').decode())
        cases = [{'input': x['input'], 'expected': x['expected']} for x in proof['observations']]
        return instrument, cases, proof['max_operations']

    def install_workshop(self, run_id, revision, *, approved=False):
        if approved is not True:
            raise ValueError('Explicit local installation approval required')
        binding = {'run_id': run_id, 'revision': revision}
        instrument, cases, max_operations = self._workshop_snapshot(binding)
        return self.install(instrument, cases, approved=True, workshop_binding=binding, max_operations=max_operations)

    @contextmanager
    def locked(self):
        self._safe_path()
        lock = self.path / '.lock'
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise ValueError('Another operation or interrupted lock requires owner reconciliation') from None
        try:
            os.close(fd)
            yield
        finally:
            lock.unlink(missing_ok=True)

    def _load(self, identity):
        if not isinstance(identity, str) or not HEX.fullmatch(identity):
            raise ValueError('Invalid release identity')
        release = read(self.path / (identity + '.json'))
        if digest(release) != identity:
            raise ValueError('Release content changed')
        qualify(release)
        if release.get('workshop_binding'):
            instrument, cases, max_operations = self._workshop_snapshot(release['workshop_binding'])
            if digest(instrument) != digest(release['instrument']) or digest(cases) != digest(release['cases']) or max_operations != release['max_operations']:
                raise ValueError('Workshop evidence does not match deployed release')
        return release

    def install(self, instrument, cases, *, approved=False, workshop_binding=None, max_operations=10000):
        if approved is not True:
            raise ValueError('Explicit local installation approval required')
        release = {'schema': 'harness/local-release/v1', 'instrument': instrument,
                   'cases': cases, 'evaluator_sha256': evaluator_identity(),
                   'max_operations': max_operations, 'workshop_binding': workshop_binding, 'lifecycle_sha256': LIFECYCLE_LOADED_SHA256}
        if workshop_binding is not None:
            bound_instrument, bound_cases, bound_operations = self._workshop_snapshot(workshop_binding)
            if digest(bound_instrument) != digest(instrument) or digest(bound_cases) != digest(cases) or bound_operations != max_operations:
                raise ValueError('Workshop evidence does not match candidate')
        count = qualify(release)
        identity = digest(release)
        with self.locked():
            head_path = self.path / 'HEAD.json'
            old = read(head_path) if head_path.exists() else None
            # Do not need to execute a failed predecessor to replace it, but retain its identity.
            if old and (not isinstance(old, dict) or not HEX.fullmatch(str(old.get('current', '')))):
                raise ValueError('Invalid head; owner reconciliation required')
            release_path = self.path / (identity + '.json')
            if release_path.exists():
                self._load(identity)
            else:
                write(release_path, release)
            if not old or old['current'] != identity:
                write(head_path, {'current': identity, 'previous': old['current'] if old else None})
        return {'status': 'installed_local', 'release': identity, 'cases_passed': count,
                'external_deployment': False, 'production_approved': False}

    def run(self, inputs):
        with self.locked():
            try:
                head = read(self.path / 'HEAD.json')
                release = self._load(head['current'])
                binding = release.get('workshop_binding')
                authority_lock = self.workshop_service._lock(binding['run_id']) if binding else nullcontext()
                # Keep workshop revocation serialized with this bounded local execution.
                with authority_lock:
                    release = self._load(head['current'])
                    evaluated = evaluate(release['instrument'], inputs, max_operations=release['max_operations'])
                    output = evaluated['output']
                receipt = {'status': 'executed_local', 'release': head['current'],
                           'input_sha256': digest(inputs), 'output_sha256': digest(output),
                           'external_effects': False, 'runtime_acceptance_established': False}
                write(self.path / 'LAST-HEALTH.json', receipt)
                return {'output': output, 'receipt': receipt}
            except (ValueError, KeyError, TypeError, BridgeError) as error:
                # Only bounded error class is persisted; no customer input or secret-bearing message.
                write(self.path / 'LAST-HEALTH.json', {'status': 'blocked', 'reason': type(error).__name__,
                                                     'external_effects': False})
                raise

    def status(self):
        with self.locked():
            head = read(self.path / 'HEAD.json')
            release = self._load(head['current'])
            return {'status': 'qualified_local', 'release': head['current'],
                    'cases_passed': len(release['cases']), 'production_approved': False}

    def rollback(self, *, approved=False):
        if approved is not True:
            raise ValueError('Explicit local rollback approval required')
        with self.locked():
            head = read(self.path / 'HEAD.json')
            previous = head.get('previous')
            self._load(previous)  # requalify the prior bytes with the current evaluator
            write(self.path / 'HEAD.json', {'current': previous, 'previous': head['current']})
            return {'status': 'rolled_back_local', 'release': previous, 'production_approved': False}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'run', 'status', 'rollback'])
    parser.add_argument('--root', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--instrument')
    parser.add_argument('--cases')
    parser.add_argument('--input')
    parser.add_argument('--approve-local-change', action='store_true')
    args = parser.parse_args()
    service = LocalDeployment(args.root, args.target)
    if args.action == 'install':
        result = service.install(read(Path(args.instrument)), read(Path(args.cases)), approved=args.approve_local_change)
    elif args.action == 'run':
        result = service.run(read(Path(args.input)))
    elif args.action == 'rollback':
        result = service.rollback(approved=args.approve_local_change)
    else:
        result = service.status()
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__':
    main()
