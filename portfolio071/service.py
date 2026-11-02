from __future__ import annotations
import copy
import hashlib
from pathlib import Path
from commercial.ledger import canonical, digest, strict_json

SCHEMA = 'portfolio071/native-services/v1'
SOURCES = ('portfolio071/__init__.py', 'portfolio071/thermal.py',
           'portfolio071/verification.py', 'portfolio071/arrangement.py',
           'portfolio071/economics.py', 'portfolio071/service.py',
           'portfolio071/reproduce.py', 'requirements-portfolio071.txt',
           'experiments/portfolio_20261102/ECONOMICS_PREREGISTRATION.md',
           'commercial/ledger.py', 'connected_enterprise/finance.py',
           'commercial/terms_exact_v2.py', 'connected_enterprise/scale.py',
           'commercial/__init__.py', 'connected_enterprise/__init__.py',
           'adaptive_enterprise/__init__.py', 'vendor/__init__.py',
           'vendor/alpha_claim/__init__.py')


def safe_path(root, name):
    if not isinstance(name, str) or not name:
        raise ValueError('PORTFOLIO071_RELATIVE_PATH_REQUIRED')
    rel = Path(name)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('PORTFOLIO071_RELATIVE_PATH_REQUIRED')
    path = Path(root).absolute() / rel
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('PORTFOLIO071_SYMLINK_REFUSED')
    return path


def source_paths(root):
    for name in SOURCES:
        if not safe_path(root, name).is_file():
            raise ValueError('PORTFOLIO071_SOURCE_MISSING:' + name)
    return list(SOURCES)


def source_hashes(root):
    return {name: hashlib.sha256(safe_path(root, name).read_bytes()).hexdigest()
            for name in source_paths(root)}


def _bound(root, name, expected):
    raw = safe_path(root, name).read_bytes()
    if len(raw) > 1_000_000 or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('PORTFOLIO071_SOURCE_OR_ARTIFACT_CHANGED')
    return strict_json(raw)


def _validate_manifest(root, manifest):
    if (not isinstance(manifest, dict)
        or set(manifest) != {'schema', 'native_engine', 'account_namespace', 'source_hashes', 'jobs'}
        or manifest['schema'] != SCHEMA or manifest['native_engine'] != 'exact-prospective-v2'
        or manifest['account_namespace'] != 'adaptive012'
        or not isinstance(manifest['jobs'], list) or not manifest['jobs']):
        raise ValueError('PORTFOLIO071_EXACT_STATIC_MANIFEST_REQUIRED')
    hashes = source_hashes(root)
    if manifest['source_hashes'] != hashes:
        raise ValueError('PORTFOLIO071_SOURCE_CLOSURE_CHANGED')
    if source_hashes(Path(__file__).resolve().parents[1]) != hashes:
        raise ValueError('PORTFOLIO071_EXECUTING_SOURCE_CHANGED')


def _checked(root, manifest, row, artifact=None):
    from portfolio071.verification import check_delivery as scientific_check
    fields = {'id', 'input', 'input_sha256', 'artifact', 'artifact_sha256', 'receipt', 'receipt_sha256'}
    if not isinstance(row, dict) or set(row) != fields or not isinstance(row['id'], str) or not row['id']:
        raise ValueError('PORTFOLIO071_EXACT_STATIC_JOB_REQUIRED')
    if len(row['id']) > 100 or '/' in row['id'] or '\\' in row['id'] or row['id'] in {'.', '..'}:
        raise ValueError('PORTFOLIO071_BOUNDED_JOB_ID_REQUIRED')
    for field in ('input', 'artifact', 'receipt'):
        if not row[field].startswith('portfolio071/deliveries/' + row['id'] + '/'):
            raise ValueError('PORTFOLIO071_DELIVERY_NAMESPACE_REQUIRED')
    request = _bound(root, row['input'], row['input_sha256'])
    current = _bound(root, row['artifact'], row['artifact_sha256'])
    receipt = _bound(root, row['receipt'], row['receipt_sha256'])
    if artifact is not None and canonical(artifact) != canonical(current):
        raise ValueError('PORTFOLIO071_PREPARED_ARTIFACT_CHANGED')
    if request.get('id') != row['id']:
        raise ValueError('PORTFOLIO071_REQUEST_ID_CHANGED')
    fresh = scientific_check(copy.deepcopy(request), copy.deepcopy(current))
    expected = {**fresh, 'request_sha256': row['input_sha256'],
                'artifact_sha256': row['artifact_sha256'],
                'checker_source_sha256': manifest['source_hashes']['portfolio071/verification.py']}
    if fresh.get('accepted') is not True or receipt != expected:
        raise ValueError('PORTFOLIO071_INDEPENDENT_SCIENTIFIC_ACCEPTANCE_REQUIRED')
    return {'job': copy.deepcopy(row), 'artifact': current, 'receipt': receipt}


def load_contracts(root, manifest):
    _validate_manifest(root, manifest)
    jobs = {}
    paths = set()
    for row in manifest['jobs']:
        checked = _checked(root, manifest, row)
        if row['id'] in jobs or any(row[field] in paths for field in ('input', 'artifact', 'receipt')):
            raise ValueError('PORTFOLIO071_UNIQUE_STATIC_DELIVERY_REQUIRED')
        paths.update(row[field] for field in ('input', 'artifact', 'receipt'))
        jobs[row['id']] = checked
    _validate_manifest(root, manifest)
    return jobs


def check_delivery(root, manifest, job_id, artifact):
    _validate_manifest(root, manifest)
    matches = [row for row in manifest['jobs'] if row['id'] == job_id]
    if len(matches) != 1:
        raise ValueError('PORTFOLIO071_UNKNOWN_STATIC_JOB')
    checked = _checked(root, manifest, matches[0], artifact)
    return {'accepted': True, 'decisive': True, 'scope': 'SIMULATED',
            'authority': checked['job']['receipt_sha256']}


def prepare_manifest(root, deliveries):
    from portfolio071.verification import check_delivery as scientific_check
    hashes = source_hashes(root)
    jobs = []
    for request, artifact in deliveries:
        if not isinstance(request, dict) or not isinstance(request.get('id'), str):
            raise ValueError('PORTFOLIO071_REQUEST_ID_REQUIRED')
        ident = request['id']
        if not ident or len(ident) > 100 or '/' in ident or '\\' in ident or ident in {'.', '..'}:
            raise ValueError('PORTFOLIO071_BOUNDED_JOB_ID_REQUIRED')
        accepted = scientific_check(copy.deepcopy(request), copy.deepcopy(artifact))
        if accepted.get('accepted') is not True:
            raise ValueError('PORTFOLIO071_UNACCEPTED_ARTIFACT_CANNOT_BE_SOLD')
        values = {'input': request, 'artifact': artifact}
        row = {'id': ident}
        for field, value in values.items():
            name = 'portfolio071/deliveries/' + ident + '/' + field + '.json'
            raw = canonical(value)
            if len(raw) > 1_000_000:
                raise ValueError('PORTFOLIO071_BOUNDED_DELIVERY_REQUIRED')
            path = safe_path(root, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                if path.read_bytes() != raw:
                    raise ValueError('PORTFOLIO071_EXISTING_ARTIFACT_OVERWRITE_REFUSED')
            else:
                with path.open('xb') as stream:
                    stream.write(raw)
            row.update({field: name, field + '_sha256': hashlib.sha256(raw).hexdigest()})
        receipt = {**accepted, 'request_sha256': row['input_sha256'],
                   'artifact_sha256': row['artifact_sha256'],
                   'checker_source_sha256': hashes['portfolio071/verification.py']}
        name = 'portfolio071/deliveries/' + ident + '/receipt.json'
        raw = canonical(receipt)
        path = safe_path(root, name)
        if path.exists():
            if path.read_bytes() != raw:
                raise ValueError('PORTFOLIO071_EXISTING_RECEIPT_OVERWRITE_REFUSED')
        else:
            with path.open('xb') as stream:
                stream.write(raw)
        row.update(receipt=name, receipt_sha256=hashlib.sha256(raw).hexdigest())
        jobs.append(row)
    manifest = {'schema': SCHEMA, 'native_engine': 'exact-prospective-v2',
                'account_namespace': 'adaptive012', 'source_hashes': hashes, 'jobs': jobs}
    load_contracts(root, manifest)
    return manifest
