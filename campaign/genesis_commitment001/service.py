"""Frozen requests and independent SQLite delivery acceptance for native finance.

No money is stored here. The manifest binds source, buyer requirements and checker
before production; the native prepare action later binds actual SQLite output.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path

from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from .acceptance import validate_request, verify

SCHEMA = 'genesis-commitment001/native-services/v1'
PREFIX = 'campaign/genesis_commitment001/'
DELIVERIES = PREFIX + 'deliveries/'
REQUIRED_SOURCES = (
    PREFIX + '__init__.py', PREFIX + 'delivery.py', PREFIX + 'acceptance.py',
    PREFIX + 'service.py', PREFIX + 'native.py', PREFIX + 'runner.py',
    PREFIX + 'PROTOCOL.json', 'commercial/ledger.py', 'connected_enterprise/finance.py',
    'commercial/persistence.py', 'commercial/__init__.py',
    'connected_enterprise/__init__.py', 'adaptive_enterprise/__init__.py',
    'vendor/__init__.py', 'vendor/alpha_claim/__init__.py',
)


def _safe_path(root, relative):
    root = Path(root).absolute()
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError('COMMITMENT001_SYMLINK_REFUSED')
    if not isinstance(relative, str) or not relative:
        raise ValueError('COMMITMENT001_RELATIVE_PATH_REQUIRED')
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or str(path) != relative:
        raise ValueError('COMMITMENT001_RELATIVE_PATH_REQUIRED')
    result = root / path
    if any(p.is_symlink() for p in (result, *result.parents)):
        raise ValueError('COMMITMENT001_SYMLINK_REFUSED')
    return result


def _read_json(root, relative):
    path = _safe_path(root, relative)
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError('COMMITMENT001_BOUNDED_REGULAR_JSON_REQUIRED')
    return strict_json(path.read_bytes())


def source_paths(root):
    paths = set(REQUIRED_SOURCES)
    directory = _safe_path(root, PREFIX.rstrip('/'))
    for path in directory.glob('*.py'):
        if not path.name.startswith('test_'):
            paths.add(PREFIX + path.name)
    for name in paths:
        if not _safe_path(root, name).is_file():
            raise ValueError('COMMITMENT001_SOURCE_MISSING:' + name)
    return sorted(paths)


def _source_hashes(root):
    return {name: hashlib.sha256(_safe_path(root, name).read_bytes()).hexdigest()
            for name in source_paths(root)}


def _validate_manifest(root, manifest):
    if (not isinstance(manifest, dict)
            or set(manifest) != {'schema', 'native_engine', 'account_namespace', 'source_hashes', 'jobs'}
            or manifest['schema'] != SCHEMA
            or manifest['native_engine'] != 'exact-prospective-v2'
            or manifest['account_namespace'] != 'adaptive012'
            or not isinstance(manifest['jobs'], list) or not 1 <= len(manifest['jobs']) <= 1000):
        raise ValueError('EXACT_COMMITMENT001_MANIFEST_REQUIRED')
    expected = _source_hashes(root)
    if manifest['source_hashes'] != expected:
        raise ValueError('COMMITMENT001_SOURCE_CLOSURE_CHANGED')
    executing = Path(__file__).resolve().parents[2]
    if _source_hashes(executing) != expected:
        raise ValueError('COMMITMENT001_EXECUTING_SOURCE_CHANGED')


def _request(root, row):
    if not isinstance(row, dict) or set(row) != {'id', 'request', 'delivery_path'}:
        raise ValueError('EXACT_COMMITMENT001_JOB_REQUIRED')
    request = validate_request(row['request'])
    if row['id'] != request['id']:
        raise ValueError('COMMITMENT001_REQUEST_ID_CHANGED')
    output = row['delivery_path']
    _safe_path(root, output)
    if not output.startswith(DELIVERIES) or not output.endswith('.json'):
        raise ValueError('COMMITMENT001_DELIVERY_NAMESPACE_REQUIRED')
    return request


def prepare_manifest(root, requests, *, native_engine='exact-prospective-v2'):
    if not isinstance(requests, list):
        raise ValueError('COMMITMENT001_REQUESTS_REQUIRED')
    manifest = {'schema': SCHEMA, 'native_engine': native_engine,
                'account_namespace': 'adaptive012', 'source_hashes': _source_hashes(root),
                'jobs': copy.deepcopy(requests)}
    load_contracts(root, manifest)
    return manifest


def load_contracts(root, manifest):
    _validate_manifest(root, manifest)
    jobs, outputs = {}, set()
    checker = manifest['source_hashes'][PREFIX + 'acceptance.py']
    for row in manifest['jobs']:
        request = _request(root, row)
        if row['id'] in jobs or row['delivery_path'] in outputs:
            raise ValueError('COMMITMENT001_UNIQUE_REQUEST_AND_OUTPUT_REQUIRED')
        outputs.add(row['delivery_path'])
        job = {'id': row['id'], 'artifact_sha256': digest(request),
               'receipt_sha256': checker, 'request': request,
               'delivery_path': row['delivery_path']}
        jobs[row['id']] = {'job': job,
                           'artifact': {'precommitted_request': digest(request)},
                           'receipt': {'checker_sha256': checker}}
    return jobs


def _bound_request(root, manifest, job_id):
    contracts = load_contracts(root, manifest)
    if job_id not in contracts:
        raise ValueError('COMMITMENT001_UNKNOWN_REQUEST')
    row = next(row for row in manifest['jobs'] if row['id'] == job_id)
    return row, _request(root, row)


def has_request(root, manifest, job_id):
    _bound_request(root, manifest, job_id)
    return True


def delivery(root, manifest, job_id):
    row, _ = _bound_request(root, manifest, job_id)
    return _read_json(root, row['delivery_path'])


def verify_delivery(root, manifest, job_id, artifact):
    _, request = _bound_request(root, manifest, job_id)
    result = verify(request, artifact)
    result.update(request_sha256=digest(request), artifact_sha256=digest(artifact),
                  checker_sha256=manifest['source_hashes'][PREFIX + 'acceptance.py'])
    return result


def check_delivery(root, manifest, job_id, artifact):
    result = verify_delivery(root, manifest, job_id, artifact)
    return {'accepted': result['accepted'], 'decisive': True, 'scope': 'SIMULATED',
            'authority': result['checker_sha256']}


def write_delivery(root, manifest, job_id, artifact, *, replace_unprepared=False):
    row, _ = _bound_request(root, manifest, job_id)
    path = _safe_path(root, row['delivery_path'])
    data = canonical(artifact)
    if len(data) > 2_000_000:
        raise ValueError('COMMITMENT001_BOUNDED_DELIVERY_REQUIRED')
    if path.exists() and (not path.is_file() or (path.read_bytes() != data and not replace_unprepared)):
        raise ValueError('COMMITMENT001_EXISTING_DELIVERY_CHANGED')
    receipt = verify_delivery(root, manifest, job_id, artifact)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_bytes() != data:
        atomic_bytes(path, data)
    return receipt


def rebind_prepared(root, manifest, actions, contracts=None):
    contracts = load_contracts(root, manifest) if contracts is None else contracts
    offers = {}
    for action in actions:
        args = action['args']
        if action['op'] == 'offer':
            if args['id'] in offers:
                raise ValueError('COMMITMENT001_UNIQUE_PREPARED_ORDER_REQUIRED')
            offers[args['id']] = args['job_id']
        elif action['op'] == 'event' and args['action'] == 'prepare':
            job_id = offers.get(args['id'])
            if job_id not in contracts:
                raise ValueError('COMMITMENT001_PREPARED_REQUEST_MISSING')
            artifact = delivery(root, manifest, job_id)
            if digest(artifact) != args.get('artifact_sha256'):
                raise ValueError('COMMITMENT001_ACTUAL_DELIVERY_HASH_CHANGED')
            if not check_delivery(root, manifest, job_id, artifact)['accepted']:
                raise ValueError('COMMITMENT001_PREPARED_ACCEPTANCE_CHANGED')
