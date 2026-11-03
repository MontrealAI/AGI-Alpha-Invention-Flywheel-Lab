from __future__ import annotations
import copy
import hashlib
from pathlib import Path
from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes

SCHEMA = 'outlearning-906c4f4d/native-services/v1'
FOLDER = 'experiments/outlearning_20261102_906c4f4d'
SOURCE_FILES = ('__init__.py', 'service.py', 'native.py', 'economics.py', 'study.py',
                'world.py', 'evaluate.py', 'treatment.py', 'baseline.py',
                'ECONOMIC_PROTOCOL.json', 'PROTOCOL.json', 'RETAINED_CONTENT.json',
                'K1_DEVELOPMENT.json', 'K1_ADDITIONAL_PROBES.json')


def _safe(root, relative):
    p = Path(relative)
    if p.is_absolute() or '..' in p.parts or not str(p).startswith(FOLDER + '/'):
        raise ValueError('OUTLEARNING_RELATIVE_NAMESPACE_REQUIRED')
    path = Path(root).absolute() / p
    if any(x.is_symlink() for x in (path, *path.parents)):
        raise ValueError('OUTLEARNING_SYMLINK_REFUSED')
    return path


def source_paths(root):
    names = [FOLDER + '/' + name for name in SOURCE_FILES]
    for name in names:
        if not _safe(root, name).is_file():
            raise ValueError('OUTLEARNING_SOURCE_MISSING:' + name)
    return names


def _hashes(root):
    return {name: hashlib.sha256(_safe(root, name).read_bytes()).hexdigest() for name in source_paths(root)}


def _validate(root, manifest):
    fields = {'schema', 'native_engine', 'account_namespace', 'source_hashes', 'jobs'}
    if (not isinstance(manifest, dict) or set(manifest) != fields or manifest['schema'] != SCHEMA
            or manifest['native_engine'] != 'exact-prospective-v2' or manifest['account_namespace'] != 'adaptive012'
            or not isinstance(manifest['jobs'], list) or not manifest['jobs']):
        raise ValueError('OUTLEARNING_EXACT_MANIFEST_REQUIRED')
    expected = _hashes(root)
    if manifest['source_hashes'] != expected or _hashes(Path(__file__).resolve().parents[2]) != expected:
        raise ValueError('OUTLEARNING_EXECUTING_SOURCE_CHANGED')


def prepare_manifest(root, requests, namespace):
    if not isinstance(namespace, str) or not namespace.replace('-', '').isalnum():
        raise ValueError('OUTLEARNING_RUNTIME_NAMESPACE_REQUIRED')
    rows = []
    for request in requests:
        ident = request['id']
        if not isinstance(ident, str) or not ident.replace('-', '').replace('_', '').isalnum():
            raise ValueError('OUTLEARNING_JOB_ID_REQUIRED')
        rows.append({'id': ident, 'request': copy.deepcopy(request),
                     'delivery_path': f'{FOLDER}/runtime/{namespace}/{ident}.json'})
    manifest = {'schema': SCHEMA, 'native_engine': 'exact-prospective-v2',
                'account_namespace': 'adaptive012', 'source_hashes': _hashes(root), 'jobs': rows}
    load_contracts(root, manifest)
    return manifest


def load_contracts(root, manifest):
    _validate(root, manifest)
    jobs, paths = {}, set()
    authority = digest(manifest['source_hashes'])
    for row in manifest['jobs']:
        if (not isinstance(row, dict) or set(row) != {'id', 'request', 'delivery_path'}
                or row['id'] in jobs or row['delivery_path'] in paths or row['request'].get('id') != row['id']
                or not row['delivery_path'].startswith(FOLDER + '/runtime/')):
            raise ValueError('OUTLEARNING_UNIQUE_BOUND_REQUEST_REQUIRED')
        _safe(root, row['delivery_path'])
        request = row['request']
        if set(request) != {'id', 'case_spec', 'acceptance'} or request['acceptance'] != 'SAFE_ACROSS_CHALLENGES_AND_ACTUAL_COMPLETE':
            raise ValueError('OUTLEARNING_UNCHANGED_ACCEPTANCE_REQUIRED')
        from .study import validate_case_spec
        validate_case_spec(request['case_spec'])
        job = {'id': row['id'], 'artifact_sha256': digest(request), 'receipt_sha256': authority,
               'request': copy.deepcopy(request), 'delivery_path': row['delivery_path']}
        jobs[row['id']] = {'job': job, 'artifact': {'precommitted_request': digest(request)},
                           'receipt': {'checker_sha256': authority}}
        paths.add(row['delivery_path'])
    return jobs


def _bound(root, manifest, job_id):
    contracts = load_contracts(root, manifest)
    if job_id not in contracts:
        raise ValueError('OUTLEARNING_UNKNOWN_REQUEST')
    return next(row for row in manifest['jobs'] if row['id'] == job_id)


def delivery(root, manifest, job_id):
    row = _bound(root, manifest, job_id)
    return strict_json(_safe(root, row['delivery_path']).read_bytes())


def verify_delivery(root, manifest, job_id, artifact):
    row = _bound(root, manifest, job_id)
    if not isinstance(artifact, dict) or set(artifact) != {'request_sha256', 'program'} or artifact['request_sha256'] != digest(row['request']):
        raise ValueError('OUTLEARNING_DELIVERY_REQUEST_CHANGED')
    from .study import evaluate_program
    result = evaluate_program(row['request']['case_spec'], artifact['program'])
    return {'accepted': result['complete_delivery'], 'evaluation': result,
            'artifact_sha256': digest(artifact), 'request_sha256': digest(row['request']),
            'checker_sha256': digest(manifest['source_hashes'])}


def check_delivery(root, manifest, job_id, artifact):
    result = verify_delivery(root, manifest, job_id, artifact)
    return {'accepted': result['accepted'], 'decisive': True, 'scope': 'SIMULATED', 'authority': result['checker_sha256']}


def write_delivery(root, manifest, job_id, artifact):
    row = _bound(root, manifest, job_id)
    data = canonical(artifact)
    if len(data) > 2_000_000:
        raise ValueError('OUTLEARNING_BOUNDED_ARTIFACT_REQUIRED')
    path = _safe(root, row['delivery_path'])
    if path.exists() and path.read_bytes() != data:
        raise ValueError('OUTLEARNING_EXISTING_DELIVERY_CHANGED')
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        atomic_bytes(path, data)
    return verify_delivery(root, manifest, job_id, artifact)


def rebind_prepared(root, manifest, actions, contracts=None):
    contracts = load_contracts(root, manifest) if contracts is None else contracts
    offers = {}
    for action in actions:
        args = action['args']
        if action['op'] == 'offer':
            if args['id'] in offers:
                raise ValueError('OUTLEARNING_DUPLICATE_OFFER')
            offers[args['id']] = args['job_id']
        elif action['op'] == 'event' and args['action'] == 'prepare':
            job_id = offers.get(args['id'])
            if job_id not in contracts:
                raise ValueError('OUTLEARNING_PREPARED_REQUEST_MISSING')
            artifact = delivery(root, manifest, job_id)
            if digest(artifact) != args.get('artifact_sha256') or not check_delivery(root, manifest, job_id, artifact)['accepted']:
                raise ValueError('OUTLEARNING_PREPARED_EVIDENCE_CHANGED')
