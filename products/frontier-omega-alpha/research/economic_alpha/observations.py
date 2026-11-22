"""Acquire bounded primary-source observations without executing source content."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
import re
import subprocess
from urllib.parse import urlsplit

MAX_BYTES = 12 * 1024 * 1024
HOSTS = {'blog.prusa3d.com', 'www.prusa3d.com', 'www.partium.io', 'openrepair.org', 'github.com', 'lean-lang.org'}
SENTINELS = {
    'release': (r'October 21\.?\s+2026', r'400\s*°\s*C', r'INDX'),
    'upgrade': (r'CORE One L', r'INDX', r'400\s*°\s*C'),
    'stock': (r'290\s*°\s*C', r'55\s*°\s*C'),
    'large': (r'290\s*°\s*C', r'60\s*°\s*C'),
}


def observe_source(item):
    name, entry = item
    url = urlsplit(entry['url'])
    if (url.scheme != 'https' or url.hostname not in HOSTS or url.username or url.password
            or url.fragment or url.port not in (None, 443)):
        raise ValueError('Use only the registered primary-source endpoints')
    command = ['curl', '-q', '--silent', '--fail', '--proto', '=https', '--max-time', '23',
               '--max-filesize', str(MAX_BYTES), '--header', 'Accept-Encoding: identity', '--user-agent',
               'ALPHA-1 public technical research', '--write-out', '\n%{http_code}', '--', entry['url']]
    result = subprocess.run(command, capture_output=True, timeout=25, check=False)
    if result.returncode or len(result.stdout) <= 4 or not result.stdout.endswith(b'\n200'):
        return name, {**entry, 'state': 'unavailable', 'transport_code': result.returncode}
    raw = result.stdout[:-4]
    if len(raw) > MAX_BYTES:
        raise ValueError('Source exceeds observation byte limit')
    content = unescape(re.sub(r'<[^>]+>', ' ', raw.decode('utf-8', 'replace')))
    flattened = ' '.join(content.split())
    return name, {**entry, 'state': 'observed', 'bytes': len(raw), 'sha256': sha256(raw).hexdigest(),
                  'content_sentinels': [bool(re.search(pattern, flattened, re.IGNORECASE))
                                        for pattern in SENTINELS.get(name, ())]}


def collect(protocol):
    with ThreadPoolExecutor(max_workers=4) as pool:
        sources = dict(pool.map(observe_source, protocol['sources'].items()))
    return {'acquired_utc': datetime.now(timezone.utc).isoformat(), 'sources': sources}


def assert_observation(receipt, protocol):
    checked = receipt['sources']
    for name, expected in SENTINELS.items():
        entry = checked.get(name, {})
        if (entry.get('state') != 'observed' or any(entry.get(key) != value for key, value in protocol['sources'][name].items())
                or not re.fullmatch(r'[0-9a-f]{64}', entry.get('sha256', ''))
                or type(entry.get('bytes')) is not int or not 0 < entry['bytes'] <= MAX_BYTES
                or entry.get('content_sentinels') != [True] * len(expected)):
            raise ValueError('Incomplete named OEM source observation: ' + name)
