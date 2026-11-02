"""Precommitted public dispatch requests and funded, late-bound deliveries.

The legacy task hash fields bind the request and checker, not a saved schedule.
Native preparation commits the actual delivered schedule hash.  This adapter
performs no financial mutation and preserves all earlier service schemas.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from collections import OrderedDict

from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from .acceptance import make_contract, verify

SCHEMA = 'production060/native-services/v1'
CRITICAL_SOURCES = (
    'production060/service.py', 'production060/native.py',
    'production060/acceptance.py', 'production060/dispatch.py',
    'production060/business.py', 'production060/evaluation.json',
    'commercial/ledger.py', 'connected_enterprise/finance.py',
)
_JSON_CACHE = OrderedDict()
_CHECK_CACHE = OrderedDict()
_CONTRACT_CACHE = OrderedDict()
_CACHE_BYTES = 32 * 1024 * 1024


def source_paths(root):
    root = Path(root)
    missing = [name for name in CRITICAL_SOURCES if not (root / name).is_file()]
    if missing:
        raise ValueError('PRODUCTION060_CRITICAL_SOURCE_MISSING:' + ','.join(missing))
    return sorted(set(CRITICAL_SOURCES) | {
        p.relative_to(root).as_posix() for p in (root / 'production060').glob('*.py')
        if p.is_file()
    })


def safe_path(root, relative):
    if not isinstance(relative, str) or not relative:
        raise ValueError('PRODUCTION060_RELATIVE_PATH_REQUIRED')
    p = Path(relative)
    if p.is_absolute() or '..' in p.parts or str(p) != relative:
        raise ValueError('PRODUCTION060_RELATIVE_PATH_REQUIRED')
    full = Path(root).resolve() / p
    if any(q.is_symlink() for q in (full, *full.parents)):
        raise ValueError('PRODUCTION060_SYMLINK_REFUSED')
    return full


def read_json(root, relative, expected=None):
    full = safe_path(root, relative)
    raw = full.read_bytes()
    if len(raw) > 2_000_000:
        raise ValueError('PRODUCTION060_RESOURCE_BOUNDED_JSON_REQUIRED')
    actual = hashlib.sha256(raw).hexdigest()
    if expected is not None and actual != expected:
        raise ValueError('PRODUCTION060_INPUT_BYTES_CHANGED:' + relative)
    key = (str(full), actual)
    if key in _JSON_CACHE:
        value, size = _JSON_CACHE.pop(key)
        _JSON_CACHE[key] = (value, size)
        return copy.deepcopy(value)
    value = strict_json(raw)
    _JSON_CACHE[key] = (value, len(raw))
    while sum(size for _, size in _JSON_CACHE.values()) > _CACHE_BYTES:
        _JSON_CACHE.popitem(last=False)
    return copy.deepcopy(value)


def _source_hashes(root):
    root = Path(root).resolve()
    result = {}
    for name in source_paths(root):
        path = safe_path(root, name)
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _validate_manifest(root, manifest):
    if (not isinstance(manifest, dict)
        or set(manifest) != {'schema', 'native_engine', 'account_namespace', 'source_hashes', 'jobs'}
        or manifest['schema'] != SCHEMA
        or manifest['native_engine'] not in {'exact-permanent-v2', 'exact-prospective-v2'}
        or manifest['account_namespace'] != 'adaptive012'
        or not isinstance(manifest['jobs'], list) or not manifest['jobs']):
        raise ValueError('EXACT_PRODUCTION060_MANIFEST_REQUIRED')
    expected = _source_hashes(root)
    if manifest['source_hashes'] != expected:
        raise ValueError('PRODUCTION060_SOURCE_CLOSURE_CHANGED')
    executing = Path(__file__).resolve().parents[1]
    for name, checksum in expected.items():
        if hashlib.sha256(safe_path(executing, name).read_bytes()).hexdigest() != checksum:
            raise ValueError('PRODUCTION060_EXECUTING_SOURCE_CHANGED:' + name)


def _request(root, row):
    if (not isinstance(row, dict) or set(row) != {'id', 'request', 'delivery_path'}
        or not isinstance(row['id'], str) or not row['id'] or len(row['id']) > 160):
        raise ValueError('EXACT_PRODUCTION060_JOB_REQUIRED')
    request = row['request']
    if (not isinstance(request, dict)
        or set(request) != {'id', 'instance_path', 'instance_sha256', 'resources_path', 'resources_sha256', 'contract'}
        or request['id'] != row['id']):
        raise ValueError('EXACT_PRODUCTION060_REQUEST_REQUIRED')
    instance = read_json(root, request['instance_path'], request['instance_sha256'])
    resources = read_json(root, request['resources_path'], request['resources_sha256'])
    contract = request['contract']
    if not isinstance(contract, dict):
        raise ValueError('PRODUCTION060_CHECKER_CONTRACT_REQUIRED')
    expected = make_contract(instance, resources, mode=contract.get('mode'),
                            planning_scope=contract.get('planning_scope'),
                            config=contract.get('search_config'))
    if contract != expected:
        raise ValueError('PRODUCTION060_CHECKER_CONTRACT_CHANGED')
    safe_path(root, row['delivery_path'])
    if not row['delivery_path'].startswith('production060/deliveries/'):
        raise ValueError('PRODUCTION060_DECLARED_DELIVERY_NAMESPACE_REQUIRED')
    if row['delivery_path'] in {request['instance_path'], request['resources_path']}:
        raise ValueError('PRODUCTION060_DELIVERY_CANNOT_REPLACE_PUBLIC_INPUT')
    return request, instance, resources


def prepare_manifest(root, requests, *, native_engine='exact-prospective-v2'):
    """Bind permitted public requests/checker before any schedule exists."""
    root = Path(root).resolve()
    rows = []
    for row in requests:
        if (not isinstance(row, dict)
            or set(row) - {'mode', 'planning_scope', 'config'} != {'id', 'instance_path', 'resources_path', 'delivery_path'}):
            raise ValueError('PRODUCTION060_PUBLIC_REQUEST_DESCRIPTION_REQUIRED')
        instance = read_json(root, row['instance_path'])
        resources = read_json(root, row['resources_path'])
        request = {
            'id': row['id'], 'instance_path': row['instance_path'],
            'instance_sha256': hashlib.sha256(safe_path(root, row['instance_path']).read_bytes()).hexdigest(),
            'resources_path': row['resources_path'],
            'resources_sha256': hashlib.sha256(safe_path(root, row['resources_path']).read_bytes()).hexdigest(),
            'contract': make_contract(instance, resources, mode=row.get('mode', 'cold'),
                                     planning_scope=row.get('planning_scope', 'offline'),
                                     config=row.get('config')),
        }
        rows.append({'id': row['id'], 'request': request, 'delivery_path': row['delivery_path']})
    manifest = {'schema': SCHEMA, 'native_engine': native_engine,
                'account_namespace': 'adaptive012', 'source_hashes': _source_hashes(root), 'jobs': rows}
    load_contracts(root, manifest)
    return manifest


def load_contracts(root, manifest):
    _validate_manifest(root, manifest)
    cache_key = (str(Path(root).resolve()), digest(manifest))
    if cache_key in _CONTRACT_CACHE:
        jobs, bindings = _CONTRACT_CACHE.pop(cache_key)
        # Reuse parsing and checker-contract construction only after fresh
        # bytes for every bound input have matched, including unused requests.
        for relative, expected in bindings:
            raw = safe_path(root, relative).read_bytes()
            if len(raw) > 2_000_000 or hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError('PRODUCTION060_INPUT_BYTES_CHANGED:' + relative)
        _CONTRACT_CACHE[cache_key] = (jobs, bindings)
        return copy.deepcopy(jobs)
    jobs = {}
    outputs = set()
    bindings = {}
    checker = manifest['source_hashes']['production060/acceptance.py']
    for row in manifest['jobs']:
        request, _, _ = _request(root, row)
        for prefix in ('instance', 'resources'):
            path, checksum = request[prefix + '_path'], request[prefix + '_sha256']
            if path in bindings and bindings[path] != checksum:
                raise ValueError('PRODUCTION060_INPUT_BINDING_CONFLICT')
            bindings[path] = checksum
        if row['id'] in jobs or row['delivery_path'] in outputs:
            raise ValueError('PRODUCTION060_UNIQUE_REQUEST_AND_DELIVERY_REQUIRED')
        outputs.add(row['delivery_path'])
        # Explicit new-schema semantics: task fields commit request + checker.
        job = {'id': row['id'], 'artifact_sha256': digest(request),
               'receipt_sha256': checker, 'request': copy.deepcopy(request),
               'delivery_path': row['delivery_path']}
        jobs[row['id']] = {'job': job, 'artifact': {'precommitted_request': digest(request)},
                          'receipt': {'checker_sha256': checker}}
    _CONTRACT_CACHE[cache_key] = (copy.deepcopy(jobs), tuple(sorted(bindings.items())))
    while len(_CONTRACT_CACHE) > 4:
        _CONTRACT_CACHE.popitem(last=False)
    return jobs


def rebind_prepared(root, manifest, actions, contracts=None):
    """Rebind every historical prepare, including later refunds and retries.

    The caller already verified the financial prefix and current full request
    authority. Exact unchanged request/checker/artifact content preserves the
    prior deterministic independent acceptance; no new success is inferred.
    """
    contracts = load_contracts(root, manifest) if contracts is None else contracts
    offers = {}
    for action in actions:
        args = action['args']
        if action['op'] == 'offer':
            if args['id'] in offers:
                raise ValueError('PRODUCTION060_UNIQUE_PREPARED_ORDER_REQUIRED')
            offers[args['id']] = args['job_id']
        elif action['op'] == 'event' and args['action'] == 'prepare':
            job_id = offers.get(args['id'])
            if job_id not in contracts:
                raise ValueError('PRODUCTION060_PREPARED_REQUEST_MISSING')
            path = safe_path(root, contracts[job_id]['job']['delivery_path'])
            raw = path.read_bytes()
            if len(raw) > 2_000_000:
                raise ValueError('PRODUCTION060_RESOURCE_BOUNDED_JSON_REQUIRED')
            # Delivered files are canonical JSON. An exact fresh byte hash
            # proves the same previously parsed/accepted artifact without
            # repeatedly deep-copying every historical schedule. Preserve
            # native canonical-content semantics for harmless formatting.
            expected = args.get('artifact_sha256')
            if hashlib.sha256(raw).hexdigest() != expected and digest(strict_json(raw)) != expected:
                raise ValueError('PRODUCTION060_ACTUAL_DELIVERY_HASH_CHANGED')


def _bound_request(root, manifest, job_id):
    # A replay already loaded the entire frozen manifest.  Rebind the exact
    # delivered request here rather than rereading every unrelated daily input
    # for each prepare in every financial prefix replay.
    _validate_manifest(root, manifest)
    rows = [row for row in manifest['jobs'] if isinstance(row, dict) and row.get('id') == job_id]
    if len(rows) != 1:
        raise ValueError('PRODUCTION060_UNKNOWN_OR_DUPLICATE_REQUEST')
    row = rows[0]
    if sum(r.get('delivery_path') == row.get('delivery_path') for r in manifest['jobs'] if isinstance(r, dict)) != 1:
        raise ValueError('PRODUCTION060_UNIQUE_REQUEST_AND_DELIVERY_REQUIRED')
    request, instance, resources = _request(root, row)
    return row, request, instance, resources


def has_request(root, manifest, job_id):
    _bound_request(root, manifest, job_id)
    return True


def delivery(root, manifest, job_id):
    row, _, _, _ = _bound_request(root, manifest, job_id)
    return read_json(root, row['delivery_path'])


def verify_delivery(root, manifest, job_id, artifact):
    _, request, instance, resources = _bound_request(root, manifest, job_id)
    return _verify_bound(manifest, request, instance, resources, artifact)


def _verify_bound(manifest, request, instance, resources, artifact):
    key = (digest(request), digest(manifest['source_hashes']), digest(artifact))
    if key not in _CHECK_CACHE:
        _CHECK_CACHE[key] = verify(instance, resources, artifact, request['contract'])
        while len(_CHECK_CACHE) > 512:
            _CHECK_CACHE.popitem(last=False)
    receipt = copy.deepcopy(_CHECK_CACHE[key])
    receipt.update(request_sha256=digest(request), artifact_sha256=digest(artifact),
                   checker_sha256=manifest['source_hashes']['production060/acceptance.py'])
    return receipt


def check_delivery(root, manifest, job_id, artifact):
    result = verify_delivery(root, manifest, job_id, artifact)
    return {'accepted': result['accepted'], 'decisive': True, 'scope': 'SIMULATED',
            'authority': result['checker_sha256']}


def write_delivery(root, manifest, job_id, artifact, *, replace_unprepared=False):
    row, request, instance, resources = _bound_request(root, manifest, job_id)
    path = safe_path(root, row['delivery_path'])
    data = canonical(artifact)
    if len(data) > 2_000_000:
        raise ValueError('PRODUCTION060_RESOURCE_BOUNDED_DELIVERY_REQUIRED')
    if path.exists() and path.read_bytes() != data and not replace_unprepared:
        raise ValueError('PRODUCTION060_EXISTING_DELIVERY_CHANGED')
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_bytes() != data:
        atomic_bytes(path, data)
    return _verify_bound(manifest, request, instance, resources, artifact)
