"""Explicit current-runtime engine routing; historical commerce006 stays frozen.

The fresh-account prospective candidate retains the existing lifecycle and adds
new-commitment stop guards. This is a new source identity, not an authorized
upgrade of any existing account. The permanent default remains frozen.
"""
from pathlib import Path
from experiments.commerce006 import engine as legacy_engine, read_bytes, sha

ROOT = Path(__file__).absolute().parents[1]
PROSPECTIVE_PINS = {
    'vendor/alpha_claim/protected_exchange_prospective_v1.py': 'cc23e6f064302b38750caa3d755345cb6318b524d3bbdc0f9b86e6f6a4be7565',
    'commercial/terms.py': '5ade1ed96b540663ee0826cf66686ce5bf2a571187e273bcf6106963f2a42eb9',
}

EXACT_MONEY_PINS = {'vendor/alpha_claim/protected_exchange_exact_v2.py': '04a790f7982bd9ac0569f4da0bd37910b623d4c7c6210cbce80d7fd5aeac92dd', 'vendor/alpha_claim/protected_exchange_prospective_exact_v2.py': '4ddf6e0ba78b7405f658dba8632e3a1304ac2f940b978e5315a454f43a911b30', 'commercial/terms_exact_v2.py': '1effcefceca21356642be0db14b7f3a381f887b816c45f050ef2293503162478'}

def engine(root=None, *, version='legacy-permanent-v1'):
    if version not in {'legacy-permanent-v1', 'prospective-v1','exact-permanent-v2','exact-prospective-v2'}:
        raise ValueError('SUPPORTED_EXPLICIT_NATIVE_ENGINE_VERSION_REQUIRED')
    root = ROOT if root is None else Path(root)
    historical = legacy_engine(root)
    if version in {'exact-permanent-v2','exact-prospective-v2'}:
        for path,expected in EXACT_MONEY_PINS.items():
            if sha(read_bytes(root/path))!=expected:raise ValueError('PINNED_EXACT_MONEY_SOURCE_MISMATCH '+path)
        if version=='exact-permanent-v2':
            from vendor.alpha_claim.protected_exchange_exact_v2 import ProtectedExchange
        else:
            from vendor.alpha_claim.protected_exchange_prospective_exact_v2 import ProtectedExchange
        return ProtectedExchange
    if version == 'legacy-permanent-v1':
        return historical
    for path, expected in PROSPECTIVE_PINS.items():
        if sha(read_bytes(root / path)) != expected:
            raise ValueError('PINNED_EXCHANGE_SOURCE_MISMATCH ' + path)
    from vendor.alpha_claim.protected_exchange_prospective_v1 import ProtectedExchange
    return ProtectedExchange
