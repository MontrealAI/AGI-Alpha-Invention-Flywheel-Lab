"""Acquire the registered public early-supernova sample. No credentials or external writes."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SERVICE = 'https://api.ztf.fink-portal.org/api/v1/'
START_JD = Decimal('2461331.5')  # October 18 00:00 UTC
CUTOFF_JD = START_JD + 7
MAX_TARGETS = 36
CLASS_QUERY = {'class': 'Early SN Ia candidate', 'n': 300, 'startdate': '2026-10-18',
               'stopdate': '2026-10-25', 'columns': 'i:objectId,i:jd', 'output-format': 'json'}
COLUMNS = ('i:objectId,i:candid,i:jd,i:fid,i:magpsf,i:sigmapsf,i:isdiffpos,i:programid,'
           'i:field,i:rcid,i:jdstartref,i:jdendref,d:mag_rate,d:sigma_rate,d:delta_time,d:from_upper')


def select_targets(rows):
    latest = {}
    for row in rows:
        jd, name = row['i:jd'], row['i:objectId']
        if START_JD <= jd < CUTOFF_JD:
            latest[name] = max(latest.get(name, jd), jd)
    return sorted(sorted(latest, key=lambda name: (-latest[name], name))[:MAX_TARGETS])


def capture(folder, basename, method, query):
    url = SERVICE + method + '?' + urlencode(query)
    start = time.monotonic()
    req = Request(url, headers={'User-Agent': 'MONTREAL.AI-IGNITION-archive-study/1.0', 'Accept': 'application/json'})
    with urlopen(req, timeout=90) as response:
        body = response.read()
        status = response.status
    elapsed = time.monotonic() - start
    rows = json.loads(body, parse_float=Decimal)
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise ValueError('The broker did not return an array of records')
    name = basename + '.json.gz'
    # Retain the exact original public response so a recipient can reselect the sample.
    (folder / name).write_bytes(gzip.compress(body, compresslevel=9, mtime=0))
    return rows, {'file': name, 'url': url, 'status': status, 'observed_utc': datetime.now(timezone.utc).isoformat(),
                  'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body), 'rows': len(rows),
                  'wall_seconds': round(elapsed, 4)}


def capture_references(folder, names):
    requests = []
    for offset in range(0, len(names), 6):
        batch = names[offset:offset + 6]
        _, receipt = capture(folder, 'reference-' + str(offset // 6 + 1), 'objects',
                             {'objectId': ','.join(batch), 'columns': 'i:objectId,i:candid,i:field,i:rcid,i:rfid',
                              'output-format': 'json'})
        requests.append(receipt)
    (folder / 'reference-index.json').write_text(json.dumps(requests, indent=2) + '\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('directory', type=Path, help='New directory for this observation')
    args = ap.parse_args()
    args.directory.mkdir(parents=True, exist_ok=False)
    classes, receipt = capture(args.directory, 'class', 'latests', CLASS_QUERY)
    names = select_targets(classes)
    acquisitions = [receipt]
    for offset in range(0, len(names), 6):
        batch = names[offset:offset + 6]
        rows, receipt = capture(args.directory, 'objects-' + str(offset // 6 + 1), 'objects',
                                {'objectId': ','.join(batch), 'columns': COLUMNS, 'output-format': 'json'})
        if any(r.get('i:objectId') not in batch for r in rows):
            raise ValueError('Unexpected target in object response')
        acquisitions.append(receipt)
    index = {'publisher': 'Fink broker / Zwicky Transient Facility', 'selection': CLASS_QUERY,
             'start_jd': str(START_JD), 'cutoff_jd': str(CUTOFF_JD), 'selected_targets': names,
             'requests': acquisitions}
    (args.directory / 'index.json').write_text(json.dumps(index, indent=2) + '\n')
    capture_references(args.directory, names)
    print(json.dumps({'class_rows': len(classes), 'selected': len(names),
                      'object_rows': sum(r['rows'] for r in acquisitions[1:])}))


if __name__ == '__main__':
    main()
