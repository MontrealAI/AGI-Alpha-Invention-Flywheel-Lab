"""Add typed dispatch to an isolated fresh fixture runtime; never edit native history."""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil

from commercial.ledger import canonical
from connected_enterprise.finance import SOURCE_PATHS
from adaptive_enterprise.instruments import SOURCE_PATHS as SERVICE_PATHS
from experiments.commerce006 import PINS
from .service import EXTRA_SOURCES

BASE_PINS = {
    'commercial/ledger.py': '7febf3102ee931e686bdb71bef0cef3e0c43fa5e45ba8a194cf7f0e6833894c5',
    'connected_enterprise/finance.py': '15047f90e9ffb06b5c405d2cdc93facd040fd5c1dfc5b2aadf2abaafb81595e2',
}
NATIVE_BASE_PROFILES = {
    '38846ad9b72ef04c10b2b97b3dbff52d1efc3790': BASE_PINS,
    '92f4351c99e6d86bf699117d1d9cd8f1ffcb5fbb': {
        'commercial/ledger.py': '2f5e0dd65a4905a0bfbc205441cbb0a54c344d80234173a36627b11156e7de0e',
        'connected_enterprise/finance.py': '7cb5f3b14adc6b931fbccbf3cc4f75deb4d0cbe10e876787c09d87f1255d6f79',
    },
}


def native_basis(hashes):
    for commit, expected in NATIVE_BASE_PROFILES.items():
        if hashes == expected:
            return commit
    raise ValueError('EXACT_PR191_NATIVE_SOURCE_REQUIRED:unrecognized_or_mixed_profile')


def stage(root, target):
    root, target = Path(root).resolve(), Path(target).absolute()
    if target.exists() or target.is_symlink() or any(p.is_symlink() for p in target.parents):
        raise ValueError('FRESH_SAFE_STAGED_RUNTIME_REQUIRED')
    native_hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in BASE_PINS}
    basis = native_basis(native_hashes)
    names = sorted(set(SOURCE_PATHS) | set(SERVICE_PATHS) | set(PINS) | set(EXTRA_SOURCES))
    originals = {}
    for name in names:
        source = root / name
        if any(p.is_symlink() for p in (source, *source.parents)):
            raise ValueError('SYMLINK_SOURCE_REFUSED')
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        originals[name] = hashlib.sha256(source.read_bytes()).hexdigest()
    inserts = {
        'commercial/ledger.py': [
            ('def load_jobs(root, manifest):\n', "    if isinstance(manifest, dict) and manifest.get('schema') == 'omega/download-fixture/v1':\n        from omega.native_lifecycle.service import load_jobs as download_jobs\n        return download_jobs(root, manifest)\n"),
            ('    def check(self, task, artifact):\n        self.validate(task)\n', "        if self.manifest.get('schema') == 'omega/download-fixture/v1':\n            from omega.native_lifecycle.service import check\n            return check(self.root, self.manifest, task['job_id'], artifact)\n")],
        'connected_enterprise/finance.py': [
            ('def source_paths_for_manifest(manifest=None):\n', "    if isinstance(manifest, dict) and manifest.get('schema') == 'omega/download-fixture/v1':\n        from omega.native_lifecycle.service import EXTRA_SOURCES\n        return SOURCE_PATHS + EXTRA_SOURCES\n")],
    }
    for name, changes in inserts.items():
        path = target / name
        code = path.read_text()
        for anchor, addition in changes:
            if code.count(anchor) != 1:
                raise ValueError('UNIQUE_TYPED_DISPATCH_ANCHOR_REQUIRED')
            code = code.replace(anchor, anchor + addition, 1)
        path.write_text(code)
    receipt = {'schema': 'omega/lifecycle-staged-source/v1',
               'scope': 'FRESH_ENGINEERING_FIXTURE_ONLY_NEVER_OPEN_ORIGINAL_AUTHORITY',
               'native_basis_commit': basis, 'native_basis_sha256': native_hashes,
               'original_sha256': originals,
               'staged_sha256': {n: hashlib.sha256((target / n).read_bytes()).hexdigest() for n in names},
               'modified_native_files': sorted(inserts), 'dispatch_insertions': 3}
    (target / 'STAGING.json').write_bytes(canonical(receipt) + b'\n')
    return receipt
