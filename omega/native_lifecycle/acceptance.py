"""Independent, narrow acceptance for a synthetic downloadable onboarding demo."""
from __future__ import annotations

import hashlib
from commercial.ledger import canonical

EDITION = 'OMEGA-ENGINEERING-DEMO-1'
SCOPE = 'AUTHORED_ENGINEERING_FIXTURE_NOT_GENESIS_PRODUCT'
FILES = {
    'README.txt': 'Offline onboarding demonstration. Run: python demo.py\nThis is a test package, not Genesis Edition or a water safety instrument.\n',
    'demo.py': 'import json\nprint(json.dumps({"diagnostic":"local_python_ready","external_calls":0},sort_keys=True))\n',
}


def accept(package):
    if not isinstance(package, dict) or set(package) != {'schema', 'edition', 'scope', 'files', 'sha256'}:
        raise ValueError('EXACT_DOWNLOAD_PACKAGE_REQUIRED')
    if (package['schema'] != 'omega/download-package/v1' or package['edition'] != EDITION
            or package['scope'] != SCOPE or package['files'] != FILES):
        raise ValueError('DECLARED_DEMO_EDITION_AND_CONTENT_REQUIRED')
    expected = {name: hashlib.sha256(value.encode()).hexdigest() for name, value in FILES.items()}
    if canonical(package['sha256']) != canonical(expected):
        raise ValueError('DOWNLOAD_FILE_HASH_CHANGED')
    return {'accepted': True, 'edition': EDITION, 'scope': SCOPE,
            'package_sha256': hashlib.sha256(canonical(package)).hexdigest(),
            'meaning': 'Exact working onboarding demo only; no buyer-outcome or Genesis acceptance.'}
