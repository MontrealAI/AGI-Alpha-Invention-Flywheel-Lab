"""Explicit current-runtime engine routing; historical commerce006 stays frozen.

Moving a byte-identical prospective implementation into a versioned module is a
new source identity, not an authorized upgrade of any existing account.
"""
from pathlib import Path
from experiments.commerce006 import engine as legacy_engine, read_bytes, sha

ROOT = Path(__file__).absolute().parents[1]
PROSPECTIVE_PINS = {
    'vendor/alpha_claim/protected_exchange_prospective_v1.py': 'a3bd70ec100f813e64bfaaabef97a6e336c8fd2d86c048c8a3c5e0ec3b664e42',
    'commercial/terms.py': '5ade1ed96b540663ee0826cf66686ce5bf2a571187e273bcf6106963f2a42eb9',
}


def engine(root=None, *, version='legacy-permanent-v1'):
    if version not in {'legacy-permanent-v1', 'prospective-v1'}:
        raise ValueError('SUPPORTED_EXPLICIT_NATIVE_ENGINE_VERSION_REQUIRED')
    root = ROOT if root is None else Path(root)
    historical = legacy_engine(root)
    if version == 'legacy-permanent-v1':
        return historical
    for path, expected in PROSPECTIVE_PINS.items():
        if sha(read_bytes(root / path)) != expected:
            raise ValueError('PINNED_EXCHANGE_SOURCE_MISMATCH ' + path)
    from vendor.alpha_claim.protected_exchange_prospective_v1 import ProtectedExchange
    return ProtectedExchange
