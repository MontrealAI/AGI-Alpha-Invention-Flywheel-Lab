"""Capture labeled event times for one public wheel and its alternate build index."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from zipfile import ZipFile


WHEEL = 'tzdata-2025.2-py2.py3-none-any.whl'
SOURCES = {
    'pypi': 'https://pypi.org/pypi/tzdata/2025.2/json',
    'piwheels': 'https://www.piwheels.org/project/tzdata/json/',
    'upstream': 'https://api.github.com/repos/python/tzdata/releases/tags/2025.2',
}


def now():
    return datetime.now(timezone.utc).isoformat()


def capture(url):
    start = now()
    request = Request(url, headers={'User-Agent': 'Frontier-Public-Evidence-Capture/1.0'})
    with urlopen(request, timeout=25) as reply:
        body = reply.read(2_000_001)
        if len(body) > 2_000_000:
            raise ValueError('Capture limit exceeded')
        event = dict(requested_utc=start, retrieved_utc=now(), requested_url=url,
                     response_url=reply.url, status=reply.status, bytes=len(body),
                     date_header=reply.headers.get('Date'), last_modified_header=reply.headers.get('Last-Modified'),
                     etag=reply.headers.get('Etag'), sha256=sha256(body).hexdigest())
    return body, event


def entries(archive):
    with ZipFile(BytesIO(archive)) as wheel:
        records = [info for info in wheel.infolist() if not info.is_dir()]
        if sum(info.file_size for info in records) > 8_000_000:
            raise ValueError('Decompression limit exceeded')
        if len({info.filename for info in records}) != len(records):
            raise ValueError('Duplicate ZIP member name')
        return {info.filename: sha256(wheel.read(info)).hexdigest() for info in records}


def study(output):
    output.mkdir()
    metadata, events = {}, {}
    for evidence, url in SOURCES.items():
        raw, event = capture(url)
        (output / f'{evidence}.json').write_bytes(raw)
        metadata[evidence], events[evidence] = json.loads(raw), event
    files = {
        'pypi': next(file for file in metadata['pypi']['urls'] if file['filename'] == WHEEL),
        'piwheels': metadata['piwheels']['releases']['2025.2']['files'][WHEEL],
    }
    upstream = metadata['upstream']
    events['pypi'].update(role='Primary distribution registry',
        source_event_utc=files['pypi']['upload_time_iso_8601'], source_event_meaning='Registry-side wheel upload')
    events['piwheels'].update(role='Alternative ARM wheel build index',
        source_event_value=metadata['piwheels']['releases']['2025.2']['released'],
        source_event_meaning='Index’s release field; metadata response declares no independent build/visibility UTC')
    events['upstream'].update(role='Maintainer release record for same tag', source_event_utc=upstream['published_at'],
        source_event_meaning='Repository release publication, not wheel publication', source_event_created_utc=upstream['created_at'])
    distribution, events['pypi-wheel'] = capture(files['pypi']['url'])
    alternate, events['piwheels-wheel'] = capture(urljoin(SOURCES['piwheels'], files['piwheels']['file_url']))
    assert events['pypi-wheel']['sha256'] == files['pypi']['digests']['sha256']
    assert events['piwheels-wheel']['sha256'] == files['piwheels']['filehash']
    payload, other = entries(distribution), entries(alternate)
    a, b = set(payload), set(other)
    differing = sorted(name for name in a & b if payload[name] != other[name])
    wheel_same = distribution == alternate
    report = {
        'case': 'U05', 'specimen': WHEEL, 'scope': 'One public artifact and one alternate build index', 'events': events,
        'sha256_verified_for_each_download': True, 'identical_wheel_bytes': wheel_same,
        'archive_members': {'pypi': len(payload), 'piwheels': len(other), 'only_pypi': sorted(a-b),
                            'only_piwheels': sorted(b-a), 'different_content': differing},
        'inference': [
            'PyPI has a self-reported upload time for a byte-identified wheel. The maintainer release describes a source tag and a separate event.',
            'The piwheels result is a separately built wheel under the same version and filename. Its released field cannot date first visibility of those bytes.',
            'First positive capture is an upper bound on first visibility for a documented observation path. With no previous negative probe, first visibility is left-censored.',
            'For future releases, define identity and path first, poll both paths on a UTC schedule, store status and hashes, and bracket each first visibility between last negative and first positive. Failed retrieval is missing evidence. Report a lead only if the resulting intervals establish an order.',
        ],
    }
    with (output/'RELEASE-EVENTS.json').open('x', encoding='utf-8') as file:
        json.dump(report, file, indent=2, ensure_ascii=False)
        file.write('\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    study(parser.parse_args().output)
