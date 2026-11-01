"""Narrow original-public-request inventory schema over unchanged native money.

The request binds original client inputs and independently authored acceptance.
The actual funded output is late bound by the native prepare action hash.
"""
from __future__ import annotations
import copy
import hashlib
from pathlib import Path

from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from production060.service import safe_path
from .independent_acceptance import verify, check_additional_quality95, SOURCE_SHA256

SCHEMA = 'inventory061/native-services/v1'
INPUTS = tuple('inventory061/inputs/' + name for name in SOURCE_SHA256)
SOURCES = ('inventory061/__init__.py', 'inventory061/service.py',
           'inventory061/native.py', 'inventory061/operate.py',
           'inventory061/constructor.py', 'inventory061/quality_constructor.py',
           'inventory061/independent_acceptance.py', 'inventory061/economics.json',
           'inventory061/QUALITY_CONTRACT_V2.json', 'inventory061/REGISTRATION.json',
           'inventory061/LICENSE-OR-License.txt', 'production060/service.py',
           'production060/acceptance.py',
           'commercial/ledger.py', 'connected_enterprise/finance.py') + INPUTS


def hashes(root):
    return {name: hashlib.sha256(safe_path(root, name).read_bytes()).hexdigest()
            for name in sorted(SOURCES)}


def read(root, relative, expected=None):
    raw = safe_path(root, relative).read_bytes()
    if len(raw) > 2_000_000 or (expected is not None and hashlib.sha256(raw).hexdigest() != expected):
        raise ValueError('INVENTORY061_BOUND_BYTES_CHANGED:' + relative)
    return strict_json(raw)


def prepare_manifest(root, *, delivery_path='inventory061/deliveries/conditional/solution.json'):
    request = {'id': 'orlicense13-quality95',
               'source_commit': '2bda4b8d6ddd4bd1cb62b89acee0c7c2f1914d47',
               'input_sha256': {name: hashlib.sha256(safe_path(root, 'inventory061/inputs/' + name).read_bytes()).hexdigest()
                                for name in SOURCE_SHA256},
               'quality': 'each48_joint_CDC_RDC_success_count_at_least347_of365',
               'original_contract': 'inventory-harbor-7',
               'quality_contract_sha256': hashlib.sha256(safe_path(root, 'inventory061/QUALITY_CONTRACT_V2.json').read_bytes()).hexdigest()}
    manifest = {'schema': SCHEMA, 'native_engine': 'exact-prospective-v2',
                'account_namespace': 'adaptive012', 'source_hashes': hashes(root),
                'jobs': [{'id': request['id'], 'request': request, 'delivery_path': delivery_path}]}
    load_contracts(root, manifest)
    return manifest


def load_contracts(root, manifest):
    if (not isinstance(manifest, dict) or set(manifest) != {'schema', 'native_engine', 'account_namespace', 'source_hashes', 'jobs'}
        or manifest['schema'] != SCHEMA or manifest['native_engine'] != 'exact-prospective-v2'
        or manifest['account_namespace'] != 'adaptive012' or len(manifest.get('jobs', [])) != 1):
        raise ValueError('INVENTORY061_EXACT_MANIFEST_REQUIRED')
    if manifest['source_hashes'] != hashes(root) or hashes(Path(__file__).resolve().parents[1]) != manifest['source_hashes']:
        raise ValueError('INVENTORY061_SOURCE_CLOSURE_CHANGED')
    row = manifest['jobs'][0]
    if not isinstance(row, dict) or set(row) != {'id', 'request', 'delivery_path'}:
        raise ValueError('INVENTORY061_EXACT_JOB_REQUIRED')
    req = row['request']
    expected = {name: hashlib.sha256(safe_path(root, 'inventory061/inputs/' + name).read_bytes()).hexdigest()
                for name in SOURCE_SHA256}
    if expected != SOURCE_SHA256 or req != {
        'id': 'orlicense13-quality95', 'source_commit': '2bda4b8d6ddd4bd1cb62b89acee0c7c2f1914d47',
        'input_sha256': expected, 'quality': 'each48_joint_CDC_RDC_success_count_at_least347_of365',
        'original_contract': 'inventory-harbor-7',
        'quality_contract_sha256': manifest['source_hashes']['inventory061/QUALITY_CONTRACT_V2.json']} or row['id'] != req['id']:
        raise ValueError('INVENTORY061_ORIGINAL_REQUEST_CHANGED')
    safe_path(root, row['delivery_path'])
    if not row['delivery_path'].startswith('inventory061/deliveries/') or not row['delivery_path'].endswith('/solution.json'):
        raise ValueError('INVENTORY061_DELIVERY_NAMESPACE_REQUIRED')
    checker = manifest['source_hashes']['inventory061/independent_acceptance.py']
    job = {'id': row['id'], 'artifact_sha256': digest(req), 'receipt_sha256': checker,
           'request': copy.deepcopy(req), 'delivery_path': row['delivery_path']}
    return {row['id']: {'job': job, 'artifact': {'precommitted_request': digest(req)},
                        'receipt': {'checker_sha256': checker}}}


def has_request(root, manifest, job_id):
    if job_id not in load_contracts(root, manifest):
        raise ValueError('INVENTORY061_UNKNOWN_REQUEST')
    return True


def delivery(root, manifest, job_id):
    jobs = load_contracts(root, manifest)
    return read(root, jobs[job_id]['job']['delivery_path'])


def verify_delivery(root, manifest, job_id, artifact):
    jobs = load_contracts(root, manifest)
    if job_id not in jobs:
        raise ValueError('INVENTORY061_UNKNOWN_REQUEST')
    instance = read(root, 'inventory061/inputs/01.json', SOURCE_SHA256['01.json'])
    receipt = verify(instance, artifact)
    receipt['original_contract_accepted'] = receipt['accepted']
    receipt['additional_quality95'] = check_additional_quality95(receipt)
    receipt['accepted'] = receipt['accepted'] and receipt['additional_quality95']['accepted']
    if not receipt['accepted'] and not receipt['errors']:
        receipt['errors'].append('INVENTORY061_ADDITIONAL_QUALITY95_FAILED')
    receipt.update(artifact_sha256=digest(artifact),
                   request_sha256=digest(jobs[job_id]['job']['request']),
                   checker_sha256=manifest['source_hashes']['inventory061/independent_acceptance.py'])
    return receipt


def check_delivery(root, manifest, job_id, artifact):
    receipt = verify_delivery(root, manifest, job_id, artifact)
    return {'accepted': receipt['accepted'], 'decisive': True, 'scope': 'SIMULATED',
            'authority': receipt['checker_sha256']}


def write_delivery(root, manifest, job_id, artifact):
    jobs = load_contracts(root, manifest)
    receipt = verify_delivery(root, manifest, job_id, artifact)
    if not receipt['accepted']:
        return receipt
    path = safe_path(root, jobs[job_id]['job']['delivery_path'])
    raw = canonical(artifact)
    if len(raw) > 2_000_000:
        raise ValueError('INVENTORY061_RESOURCE_BOUNDED_DELIVERY_REQUIRED')
    if path.exists() and strict_json(path.read_bytes()) != artifact:
        raise ValueError('INVENTORY061_EXISTING_DELIVERY_CHANGED')
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_bytes(path, raw)
    return receipt


def rebind_prepared(root, manifest, actions, contracts=None):
    jobs = load_contracts(root, manifest) if contracts is None else contracts
    offers = {}
    for action in actions:
        args = action['args']
        if action['op'] == 'offer':
            if args['id'] in offers:
                raise ValueError('INVENTORY061_UNIQUE_ORDER_REQUIRED')
            offers[args['id']] = args['job_id']
        elif action['op'] == 'event' and args['action'] == 'prepare':
            job_id = offers.get(args['id'])
            if job_id not in jobs:
                raise ValueError('INVENTORY061_PREPARED_REQUEST_MISSING')
            artifact = read(root, jobs[job_id]['job']['delivery_path'])
            if digest(artifact) != args.get('artifact_sha256'):
                raise ValueError('INVENTORY061_ACTUAL_DELIVERY_HASH_CHANGED')
