"""Capture authorized public Atlas sources and replay evidence decisions offline."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit

import evidence_truth
from frontier_public_watch import fetch
from science_substrate import read_json


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def write_json(path, value):
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(raw)
    return sha256(raw).hexdigest()


def source_path(raw_root, name):
    # File names never come from an endpoint or its response.
    if not isinstance(name, str) or not name.isascii() or not name.replace('-', '').isalnum():
        raise ValueError('Source identifier must be a plain name')
    return raw_root / (name + '.source')


def capture(request, raw_root):
    raw_root.mkdir(exist_ok=False)
    rows = {}
    limits = request['allowlisted_hostnames']
    for source in request['sources']:
        name, url = source['id'], source['url']
        address = urlsplit(url)
        if (name in rows or address.scheme != 'https' or address.hostname not in limits
                or address.username or address.password or address.fragment or address.port not in (None, 443)):
            raise ValueError('Source must be a unique authorized public HTTPS endpoint')
        path = source_path(raw_root, name)
        started_at = utc_now()
        start = time.monotonic_ns()
        try:
            raw = fetch(url, 2_000_000)
        except (OSError, ValueError) as error:
            rows[name] = {'url': url, 'status': error.code if isinstance(error, HTTPError) else None,
                          'error_type': type(error).__name__, 'started_at': started_at,
                          'finished_at': utc_now(), 'elapsed_ns': time.monotonic_ns() - start}
            continue
        elapsed_ns = time.monotonic_ns() - start
        finished_at = utc_now()
        with path.open('xb') as stream:
            stream.write(raw)
        rows[name] = {'url': url, 'status': 200, 'bytes': len(raw), 'sha256': sha256(raw).hexdigest(),
                      'started_at': started_at, 'finished_at': finished_at, 'elapsed_ns': elapsed_ns}
    return rows


def quote_witness(raw, proof):
    representation = proof.get('representation', 'utf8')
    if representation == 'pdf_text':
        content = subprocess.run(('pdftotext', '-nopgbrk', '-', '-'), input=raw, stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, check=True, timeout=10).stdout.decode()
    elif representation == 'utf8':
        content = raw.decode()
    else:
        raise ValueError('Unregistered witness representation')
    if proof['json_path']:
        content = json.loads(content)
        for field in proof['json_path']:
            content = content[field]
    quote = proof['quote']
    if not isinstance(content, str) or not isinstance(quote, str) or not quote.strip() or quote not in content:
        raise ValueError('Primary-source quoted span missing')
    return {'offset_utf8': len(content[:content.index(quote)].encode()),
            'locator_field_utf8_sha256': sha256(content.encode()).hexdigest(), **proof}


def verify_projection(document, captures, raw_root):
    source_map = evidence_truth.sources(document['sources'])
    primary_bytes = {}
    for name, source in source_map.items():
        receipt = captures[name]
        path = source_path(raw_root, name)
        with path.open('rb') as stream:
            raw = stream.read(2_000_001)
        if (receipt['status'] != 200 or receipt['url'] != source['url']
                or not 0 < len(raw) == receipt['bytes'] <= 2_000_000
                or sha256(raw).hexdigest() != receipt['sha256'] or receipt['sha256'] != source['sha256']
                or source['binding'] != 'source_bytes'):
            raise ValueError('Source bytes did not match the capture and operation')
        primary_bytes[name] = raw

    verified = {}
    for case in document['cases']:
        proofs = document['witnesses'][case['id']]
        records = case['records']
        if set(proofs) != {record['id'] for record in records}:
            raise ValueError('Every projected observation needs an exact source span')
        verified[case['id']] = {
            record['id']: [quote_witness(primary_bytes[record['source']], proof) for proof in proofs[record['id']]]
            for record in records
        }
        if any(not facts for facts in verified[case['id']].values()):
            raise ValueError('Every projected observation needs an exact source span')
    return verified


def withdrawn(document):
    """Remove version, track, platform and configuration checks, holding other inputs fixed."""
    modified = deepcopy(document)
    for case in modified['cases']:
        if case['kind'] == 'product_stage':
            case['scope'] = {key: case['scope'][key] for key in ('product', 'feature')}
    return modified


def decide(document, captures, raw_root):
    started_at = utc_now()
    start = time.monotonic_ns()
    witnesses = verify_projection(document, captures, raw_root)
    binding_ns = time.monotonic_ns() - start
    start = time.monotonic_ns()
    retained = evidence_truth.evaluate(document)
    retained_ns = time.monotonic_ns() - start
    start = time.monotonic_ns()
    reduced = evidence_truth.evaluate(withdrawn(document))
    return {'started_at': started_at, 'finished_at': utc_now(),
            'scope': 'raw-byte verification plus exact operator-declared source semantics',
            'binding_ns': binding_ns, 'retained_ns': retained_ns, 'withdrawn_ns': time.monotonic_ns() - start,
            'projected_witnesses': witnesses, 'retained': retained, 'withdrawn_extra_scope': reduced}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('capture', 'decide'))
    parser.add_argument('input', type=Path)
    parser.add_argument('directory', type=Path)
    options = parser.parse_args()
    raw_root = options.directory / 'raw'
    captures_path = options.directory / 'captures.json'
    spec = read_json(options.input)
    if options.action == 'capture':
        value = capture(spec, raw_root)
        print(write_json(captures_path, value))
    else:
        captures = read_json(captures_path)
        print(write_json(options.directory / 'decisions.json', decide(spec, captures, raw_root)))


if __name__ == '__main__':
    main()
