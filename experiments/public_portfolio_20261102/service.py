from __future__ import annotations
import copy
import hashlib
from pathlib import Path
from commercial.ledger import canonical, digest
from commercial.persistence import atomic_bytes
from production060.service import safe_path, read_json

SCHEMA = 'public-portfolio-20261102/native-services/v2'
PREFIX = 'experiments/public_portfolio_20261102/'
REGISTRY = PREFIX + 'FROZEN_SOURCES.json'
APPROVAL = PREFIX + 'verification/PRODUCT_APPROVALS.json'
VERIFIER = PREFIX + 'verification/verify_artifacts.py'
SOURCES = (PREFIX + '__init__.py', PREFIX + 'service.py', PREFIX + 'native.py',
           PREFIX + 'economics.py', PREFIX + 'ECONOMICS_PROTOCOL.json', REGISTRY,
           'experiments/__init__.py', 'production060/__init__.py',
           'production060/service.py', 'production060/acceptance.py',
           'commercial/__init__.py', 'commercial/tape_lease.py',
           'adaptive_enterprise/__init__.py', 'connected_enterprise/__init__.py',
           'vendor/__init__.py', 'vendor/alpha_claim/__init__.py')

def source_paths(root):
    registry = read_json(root, REGISTRY)
    if set(registry) != {'schema', 'files'} or registry['schema'] != 'public-portfolio/source-registry/v1':
        raise ValueError('PORTFOLIO_EXACT_SOURCE_REGISTRY_REQUIRED')
    files = registry['files']
    if not isinstance(files, list) or len(files) != len(set(files)):
        raise ValueError('PORTFOLIO_UNIQUE_SOURCE_PATHS_REQUIRED')
    for name in files:
        if not isinstance(name, str) or not name.startswith(PREFIX) or not safe_path(root, name).is_file():
            raise ValueError('PORTFOLIO_DECLARED_PUBLIC_SOURCE_REQUIRED')
    if APPROVAL not in files or VERIFIER not in files:
        raise ValueError('PORTFOLIO_FROZEN_VERIFIER_AUTHORITY_REQUIRED')
    return list(dict.fromkeys(SOURCES + tuple(files)))

def _source_hashes(root):
    return {name: hashlib.sha256(safe_path(root, name).read_bytes()).hexdigest() for name in source_paths(root)}

def _validate_manifest(root, manifest):
    if (not isinstance(manifest, dict) or set(manifest) != {'schema', 'native_engine', 'account_namespace', 'source_hashes', 'jobs'}
            or manifest['schema'] != SCHEMA or manifest['native_engine'] != 'exact-prospective-v2'
            or manifest['account_namespace'] != 'adaptive012' or not isinstance(manifest['jobs'], list)):
        raise ValueError('PORTFOLIO_EXACT_MANIFEST_REQUIRED')
    expected = _source_hashes(root)
    if manifest['source_hashes'] != expected or _source_hashes(Path(__file__).resolve().parents[2]) != expected:
        raise ValueError('PORTFOLIO_SOURCE_CLOSURE_CHANGED')

def _product(root, row):
    fields = {'id', 'route', 'stage', 'product_path', 'product_sha256', 'approval_path', 'approval_sha256', 'delivery_path'}
    if not isinstance(row, dict) or set(row) != fields or row['route'] not in {'purpose', 'interface', 'complementarity', 'arrangement', 'foundry'} or row['stage'] not in {'k1', 'k2'}:
        raise ValueError('PORTFOLIO_EXACT_LICENSE_PRODUCT_REQUIRED')
    if row['id'] != row['route'] + '-' + row['stage']:
        raise ValueError('PORTFOLIO_PRODUCT_ID_CHANGED')
    if row['approval_path'] != APPROVAL or row['product_path'] != PREFIX + row['route'] + '/products/' + row['stage'] + '.json':
        raise ValueError('PORTFOLIO_CANONICAL_VERIFIER_AND_PRODUCT_REQUIRED')
    registered = source_paths(root)
    if row['product_path'] not in registered or row['approval_path'] not in registered:
        raise ValueError('PORTFOLIO_FROZEN_PRODUCT_AND_AUTHORITY_REQUIRED')
    for field in ('product_path', 'approval_path', 'delivery_path'):
        if not isinstance(row[field], str) or not row[field].startswith(PREFIX):
            raise ValueError('PORTFOLIO_PUBLIC_NAMESPACE_REQUIRED')
        safe_path(root, row[field])
    if not row['delivery_path'].startswith(PREFIX + 'deliveries/') or row['delivery_path'] in {row['product_path'], row['approval_path']}:
        raise ValueError('PORTFOLIO_SEPARATE_DELIVERY_REQUIRED')
    product = read_json(root, row['product_path'], row['product_sha256'])
    approval = read_json(root, row['approval_path'], row['approval_sha256'])
    if (not isinstance(approval, dict) or approval.get('schema') != 'public-portfolio/native-product-approvals/v1'
            or not isinstance(approval.get('products'), list)):
        raise ValueError('PORTFOLIO_INDEPENDENT_APPROVAL_REQUIRED')
    matches = [p for p in approval['products'] if p.get('id') == row['id']]
    if len(matches) != 1:
        raise ValueError('PORTFOLIO_UNIQUE_PRODUCT_APPROVAL_REQUIRED')
    accepted = matches[0]
    if (accepted.get('accepted') is not True or accepted.get('scope') != 'COMPUTATIONAL_CONTRACT_ONLY'
            or accepted.get('product_path') != row['product_path'] or accepted.get('product_sha256') != row['product_sha256']
            or accepted.get('route') != row['route'] or accepted.get('stage') != row['stage']):
        raise ValueError('PORTFOLIO_APPROVED_BYTES_REQUIRED')
    if hashlib.sha256(safe_path(root, VERIFIER).read_bytes()).hexdigest() != accepted.get('verification_source_sha256'):
        raise ValueError('PORTFOLIO_VERIFICATION_SOURCE_CHANGED')
    if not isinstance(accepted.get('evidence'), list) or not accepted['evidence']:
        raise ValueError('PORTFOLIO_NONEMPTY_INDEPENDENT_EVIDENCE_REQUIRED')
    for evidence in accepted['evidence']:
        if not isinstance(evidence, dict) or set(evidence) != {'path', 'sha256'} or evidence['path'] not in registered:
            raise ValueError('PORTFOLIO_FROZEN_INDEPENDENT_EVIDENCE_REQUIRED')
        read_json(root, evidence['path'], evidence['sha256'])
    if not isinstance(product, dict) or product.get('id') != row['id'] or product.get('scope') != 'COMPUTATIONAL_CONTRACT_ONLY':
        raise ValueError('PORTFOLIO_COMPUTATIONAL_PRODUCT_SCOPE_REQUIRED')
    for artifact in product.get('artifacts', []):
        if not isinstance(artifact, dict) or set(artifact) != {'path', 'sha256'} or not artifact['path'].startswith(PREFIX):
            raise ValueError('PORTFOLIO_BOUND_ARTIFACT_REQUIRED')
        if hashlib.sha256(safe_path(root, artifact['path']).read_bytes()).hexdigest() != artifact['sha256']:
            raise ValueError('PORTFOLIO_LICENSE_CONTENT_CHANGED')
    if not product.get('artifacts'):
        raise ValueError('PORTFOLIO_NONEMPTY_LICENSE_CONTENT_REQUIRED')
    return product, accepted

def prepare_manifest(root, products, delivery_prefix):
    rows = []
    for product in products:
        row = copy.deepcopy(product)
        row['delivery_path'] = PREFIX + 'deliveries/' + delivery_prefix + '/' + row['id'] + '.json'
        rows.append(row)
    manifest = {'schema': SCHEMA, 'native_engine': 'exact-prospective-v2', 'account_namespace': 'adaptive012',
                'source_hashes': _source_hashes(root), 'jobs': rows}
    load_contracts(root, manifest)
    return manifest

def load_contracts(root, manifest):
    _validate_manifest(root, manifest)
    jobs, outputs = {}, set()
    for row in manifest['jobs']:
        product, approval = _product(root, row)
        if row['id'] in jobs or row['delivery_path'] in outputs:
            raise ValueError('PORTFOLIO_UNIQUE_LICENSE_AND_DELIVERY_REQUIRED')
        outputs.add(row['delivery_path'])
        job = {'id': row['id'], 'artifact_sha256': digest(product), 'receipt_sha256': row['approval_sha256'],
               'request': copy.deepcopy(row), 'delivery_path': row['delivery_path']}
        jobs[row['id']] = {'job': job, 'artifact': product, 'receipt': approval}
    return jobs

def delivery(root, manifest, job_id):
    load_contracts(root, manifest)
    row = next(r for r in manifest['jobs'] if r['id'] == job_id)
    return read_json(root, row['delivery_path'])

def check_delivery(root, manifest, job_id, artifact):
    contracts = load_contracts(root, manifest)
    if job_id not in contracts:
        raise ValueError('PORTFOLIO_UNKNOWN_LICENSE_PRODUCT')
    expected = contracts[job_id]
    return {'accepted': canonical(artifact) == canonical(expected['artifact']), 'decisive': True, 'scope': 'SIMULATED',
            'authority': expected['job']['receipt_sha256']}

def write_delivery(root, manifest, job_id, artifact):
    result = check_delivery(root, manifest, job_id, artifact)
    result['artifact_sha256'] = digest(artifact)
    if not result['accepted']:
        return result
    row = next(r for r in manifest['jobs'] if r['id'] == job_id)
    path = safe_path(root, row['delivery_path'])
    data = canonical(artifact)
    if path.exists() and path.read_bytes() != data:
        raise ValueError('PORTFOLIO_EXISTING_LICENSE_DELIVERY_CHANGED')
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        atomic_bytes(path, data)
    return result

def rebind_prepared(root, manifest, actions, contracts=None):
    contracts = load_contracts(root, manifest) if contracts is None else contracts
    offers = {}
    for action in actions:
        args = action['args']
        if action['op'] == 'offer':
            if args['id'] in offers:
                raise ValueError('PORTFOLIO_UNIQUE_ORDER_REQUIRED')
            offers[args['id']] = args['job_id']
        elif action['op'] == 'event' and args['action'] == 'prepare':
            ident = offers.get(args['id'])
            if ident not in contracts:
                raise ValueError('PORTFOLIO_PREPARED_LICENSE_MISSING')
            artifact = delivery(root, manifest, ident)
            if digest(artifact) != args.get('artifact_sha256') or not check_delivery(root, manifest, ident, artifact)['accepted']:
                raise ValueError('PORTFOLIO_PREPARED_CONTENT_CHANGED')
