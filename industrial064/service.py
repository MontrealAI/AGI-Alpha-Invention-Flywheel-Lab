"""Source-bound requests and late-bound industrial plans; no financial authority."""
from __future__ import annotations
import copy
import hashlib
from pathlib import Path
from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from production060.service import safe_path
from .acceptance import verify

SCHEMA = 'industrial064/native-services/v1'
REQUEST_KEYS = {'id', 'input_path', 'input_sha256', 'distance_margin', 'cost_ceiling_yuan'}


def source_paths(root, manifest=None):
    root = Path(root)
    paths = {'industrial064/economics.json', 'industrial064/registration.json',
             'industrial064/service.py', 'industrial064/native.py', 'industrial064/acceptance.py',
             'industrial064/construct.py', 'commercial/ledger.py', 'connected_enterprise/finance.py',
             'production060/service.py', 'production060/acceptance.py'}
    paths.update(p.relative_to(root).as_posix() for p in (root/'industrial064').glob('*.py'))
    paths.update(p.relative_to(root).as_posix() for p in (root/'industrial062').glob('*.py'))
    paths.update(p.relative_to(root).as_posix() for p in (root/'industrial062'/'inputs').rglob('*.py'))
    if manifest is not None:
        paths.update(row['request']['input_path'] for row in manifest['jobs'])
    return sorted(paths)


def hashes(root, manifest):
    return {name: hashlib.sha256(safe_path(root, name).read_bytes()).hexdigest()
            for name in source_paths(root, manifest)}


def read(root, relative, expected=None):
    raw = safe_path(root, relative).read_bytes()
    if len(raw) > 2_000_000 or (expected is not None and hashlib.sha256(raw).hexdigest() != expected):
        raise ValueError('INDUSTRIAL064_BOUND_BYTES_CHANGED:' + relative)
    return strict_json(raw)


def prepare_manifest(root, requests):
    manifest = {'schema': SCHEMA, 'native_engine': 'exact-prospective-v2',
                'account_namespace': 'adaptive012', 'source_hashes': {}, 'jobs': copy.deepcopy(requests)}
    manifest['source_hashes'] = hashes(root, manifest)
    load_contracts(root, manifest)
    return manifest


def load_contracts(root, manifest):
    if (not isinstance(manifest, dict) or set(manifest) != {'schema', 'native_engine', 'account_namespace', 'source_hashes', 'jobs'}
        or manifest['schema'] != SCHEMA or manifest['native_engine'] != 'exact-prospective-v2'
        or manifest['account_namespace'] != 'adaptive012' or not isinstance(manifest.get('jobs'), list)
        or not manifest['jobs']):
        raise ValueError('INDUSTRIAL064_EXACT_MANIFEST_REQUIRED')
    jobs = {}; outputs = set(); requests = []
    for row in manifest['jobs']:
        if not isinstance(row, dict) or set(row) != {'id', 'request', 'delivery_path'}:
            raise ValueError('INDUSTRIAL064_EXACT_JOB_REQUIRED')
        req = row['request']; ident = row['id']
        if (not isinstance(req, dict) or set(req) != REQUEST_KEYS or req['id'] != ident
            or not isinstance(ident, str) or not ident.strip() or len(ident) > 160 or ident in jobs
            or type(req['distance_margin']) not in (float, int) or req['distance_margin'] != 0.10
            or type(req['cost_ceiling_yuan']) not in (float, int) or not 0 < req['cost_ceiling_yuan'] < 1e15
            or not isinstance(req['input_sha256'], str) or len(req['input_sha256']) != 64):
            raise ValueError('INDUSTRIAL064_REGISTERED_REQUEST_REQUIRED')
        read(root, req['input_path'], req['input_sha256'])
        path = row['delivery_path']; safe_path(root, path)
        if not path.startswith('industrial064/deliveries/') or not path.endswith('.json') or path in outputs:
            raise ValueError('INDUSTRIAL064_UNIQUE_DELIVERY_NAMESPACE_REQUIRED')
        outputs.add(path); requests.append(req)
        checker = manifest['source_hashes'].get('industrial064/acceptance.py')
        job = {'id': ident, 'artifact_sha256': digest(req), 'receipt_sha256': checker,
               'request': copy.deepcopy(req), 'delivery_path': path}
        jobs[ident] = {'job': job, 'artifact': {'precommitted_request': digest(req)}, 'receipt': {'checker_sha256': checker}}
    registered = read(root, 'industrial064/registration.json')
    if registered.get('requests') != requests:
        raise ValueError('INDUSTRIAL064_REGISTERED_REQUESTS_CHANGED')
    if manifest['source_hashes'] != hashes(root, manifest) or hashes(Path(__file__).resolve().parents[1], manifest) != manifest['source_hashes']:
        raise ValueError('INDUSTRIAL064_SOURCE_CLOSURE_CHANGED')
    return jobs


def has_request(root, manifest, job_id):
    if job_id not in load_contracts(root, manifest):
        raise ValueError('INDUSTRIAL064_UNKNOWN_REQUEST')
    return True


def delivery(root, manifest, job_id):
    return read(root, load_contracts(root, manifest)[job_id]['job']['delivery_path'])


def verify_delivery(root, manifest, job_id, artifact):
    jobs = load_contracts(root, manifest)
    if job_id not in jobs:
        raise ValueError('INDUSTRIAL064_UNKNOWN_REQUEST')
    receipt = verify(root, jobs[job_id]['job']['request'], artifact)
    receipt.update(artifact_sha256=digest(artifact), request_sha256=digest(jobs[job_id]['job']['request']),
                   checker_sha256=manifest['source_hashes']['industrial064/acceptance.py'])
    return receipt


def check_delivery(root, manifest, job_id, artifact):
    receipt = verify_delivery(root, manifest, job_id, artifact)
    return {'accepted': receipt['accepted'], 'decisive': True, 'scope': 'SIMULATED', 'authority': receipt['checker_sha256']}


def write_delivery(root, manifest, job_id, artifact):
    jobs = load_contracts(root, manifest)
    receipt = verify_delivery(root, manifest, job_id, artifact)
    if not receipt['accepted']:
        return receipt
    path = safe_path(root, jobs[job_id]['job']['delivery_path']); raw = canonical(artifact)
    if len(raw) > 2_000_000:
        raise ValueError('INDUSTRIAL064_RESOURCE_BOUNDED_DELIVERY_REQUIRED')
    if path.exists() and strict_json(path.read_bytes()) != artifact:
        raise ValueError('INDUSTRIAL064_EXISTING_DELIVERY_CHANGED')
    path.parent.mkdir(parents=True, exist_ok=True); atomic_bytes(path, raw)
    return receipt


def rebind_prepared(root, manifest, actions, contracts=None):
    jobs = load_contracts(root, manifest) if contracts is None else contracts
    offers = {}
    for action in actions:
        args = action['args']
        if action['op'] == 'offer':
            if args['id'] in offers:
                raise ValueError('INDUSTRIAL064_UNIQUE_ORDER_REQUIRED')
            offers[args['id']] = args['job_id']
        elif action['op'] == 'event' and args['action'] == 'prepare':
            job_id = offers.get(args['id'])
            if job_id not in jobs:
                raise ValueError('INDUSTRIAL064_PREPARED_REQUEST_MISSING')
            artifact = read(root, jobs[job_id]['job']['delivery_path'])
            if digest(artifact) != args.get('artifact_sha256'):
                raise ValueError('INDUSTRIAL064_ACTUAL_DELIVERY_HASH_CHANGED')
