"""Typed static download acceptance; no financial state or mutation."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path

from commercial.ledger import canonical, digest, read_bound
from .acceptance import accept

SCHEMA = 'omega/download-fixture/v1'
EXTRA_SOURCES = ('omega/seller_lifecycle.py', 'omega/native_lifecycle/acceptance.py',
                 'omega/native_lifecycle/service.py', 'omega/native_lifecycle/stage.py',
                 'campaign/omega-continuation-bdd6/SELLER_FIXTURE.json')


def _sources(root):
    from connected_enterprise.finance import SOURCE_PATHS
    from experiments.commerce006 import PINS
    from adaptive_enterprise.instruments import SOURCE_PATHS as service_paths
    names = sorted(set(SOURCE_PATHS) | set(PINS) | set(service_paths) | set(EXTRA_SOURCES))
    result = {}
    for name in names:
        path = Path(root) / name
        if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('REGULAR_DOWNLOAD_SOURCE_REQUIRED:' + name)
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def manifest_for(root, package_path):
    package_raw = (Path(root) / package_path).read_bytes()
    from commercial.ledger import strict_json
    package = strict_json(package_raw)
    receipt = accept(package)
    receipt_path = 'download-fixture/acceptance.json'
    receipt_raw = canonical(receipt) + b'\n'
    (Path(root) / receipt_path).write_bytes(receipt_raw)
    return {'schema': SCHEMA, 'account_namespace': 'adaptive012', 'native_engine': 'exact-permanent-v2',
            'scope': 'ENGINEERING_ONLY_NOT_ORIGINAL_ACCOUNT', 'source_hashes': _sources(root),
            'jobs': [{'id': 'demo-download', 'service_id': 'typed_demo_download', 'accepted': True,
                      'artifact': package_path, 'artifact_sha256': hashlib.sha256(package_raw).hexdigest(),
                      'receipt': receipt_path, 'receipt_sha256': hashlib.sha256(receipt_raw).hexdigest()}]}


def load_jobs(root, manifest):
    if (not isinstance(manifest, dict) or set(manifest) != {'schema', 'account_namespace', 'native_engine', 'scope', 'source_hashes', 'jobs'}
            or manifest['schema'] != SCHEMA or manifest['account_namespace'] != 'adaptive012'
            or manifest['native_engine'] != 'exact-permanent-v2'
            or manifest['scope'] != 'ENGINEERING_ONLY_NOT_ORIGINAL_ACCOUNT'):
        raise ValueError('EXACT_DOWNLOAD_FIXTURE_MANIFEST_REQUIRED')
    if manifest['source_hashes'] != _sources(root) or _sources(root) != _sources(Path(__file__).resolve().parents[2]):
        raise ValueError('DOWNLOAD_SOURCE_IDENTITY_CHANGED')
    if not isinstance(manifest['jobs'], list) or len(manifest['jobs']) != 1:
        raise ValueError('ONE_STATIC_DEMO_PACKAGE_REQUIRED')
    job = manifest['jobs'][0]
    fields = {'id', 'service_id', 'accepted', 'artifact', 'artifact_sha256', 'receipt', 'receipt_sha256'}
    if (not isinstance(job, dict) or set(job) != fields or job['id'] != 'demo-download'
            or job['service_id'] != 'typed_demo_download' or job['accepted'] is not True
            or job['artifact'] != 'download-fixture/package.json' or job['receipt'] != 'download-fixture/acceptance.json'):
        raise ValueError('EXACT_TYPED_DEMO_JOB_REQUIRED')
    artifact = read_bound(root, job['artifact'], job['artifact_sha256'])
    receipt = read_bound(root, job['receipt'], job['receipt_sha256'])
    if canonical(receipt) != canonical(accept(artifact)):
        raise ValueError('INDEPENDENT_DOWNLOAD_ACCEPTANCE_CHANGED')
    return {job['id']: {'job': copy.deepcopy(job), 'artifact': artifact, 'receipt': receipt}}


def check(root, manifest, job_id, artifact):
    checked = load_jobs(root, manifest)
    if job_id not in checked:
        raise ValueError('UNKNOWN_DOWNLOAD_JOB')
    actual = accept(artifact)
    if canonical(artifact) != canonical(checked[job_id]['artifact']):
        raise ValueError('DELIVERED_PACKAGE_CHANGED')
    return {'accepted': actual['accepted'], 'decisive': True, 'scope': 'SIMULATED',
            'authority': checked[job_id]['job']['receipt_sha256']}
