"""Rebuild six independent Reader V3 windows from attributed remote archaeological CT."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

import numpy as np

SPONSOR = 'https://vesuvius-challenge-open-data.s3.amazonaws.com/'
STORE = ('PHerc0139/segments/20260206000002-w054_2026020617/surface-volumes/'
         '9.362um-1.2m-113keV-volume-20250728140407.zarr/')
CHUNK = 28 * 128 * 128
BUDGET = 60_000_000


def get(url, limit, interval=None):
    headers = {} if interval is None else {'Range': 'bytes=%s-%s' % interval}
    with urlopen(Request(url, headers=headers), timeout=30) as r:
        if interval is not None and (r.status != 206 or
                r.headers.get('Content-Range') != 'bytes %s-%s/%s' % (*interval, CHUNK)):
            raise ValueError('server did not confirm the requested range')
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError('response exceeded limit')
    return data


def list_keys(prefix):
    url = SPONSOR + '?' + urlencode({'list-type': 2, 'prefix': prefix, 'max-keys': 1000})
    data = get(url, 512_000)
    root = ET.fromstring(data)
    if root.findtext('{*}IsTruncated') != 'false':
        raise ValueError('Incomplete object-store listing')
    return {e.findtext('{*}Key') for e in root.findall('{*}Contents')}, len(data)


def positions(size):
    starts = list(range(0, size - 384 + 1, 192))
    if starts[-1] != size - 384:
        starts.append(size - 384)
    return starts


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def run(output, *, select=None, byte_budget=BUDGET):
    output.mkdir(parents=True, exist_ok=True)
    raw = output / 'research_data'
    raw.mkdir(exist_ok=True)
    manifest = []
    wire = 0
    for level, shape in ((0, [28, 7660, 11140]), (3, [28, 958, 1393])):
        path = STORE + f'{level}/.zarray'
        meta = get(SPONSOR + path, 4096)
        wire += len(meta)
        expected = {'shape': shape, 'chunks': [28, 128, 128], 'dtype': '|u1', 'fill_value': 0,
                    'order': 'C', 'filters': None, 'compressor': None, 'dimension_separator': '/'}
        if not all(json.loads(meta).get(k) == v for k, v in expected.items()):
            raise ValueError('Upstream CT description changed')
        manifest.append({'path': path, 'sha256': sha256(meta).hexdigest()})
    low_keys, length = list_keys(STORE + '3/0/')
    wire += length
    if wire + len(low_keys) * CHUNK > byte_budget:
        raise ValueError('full occupancy exceeds registered byte budget')
    occupancy = np.zeros((958, 1393), dtype=bool)

    def collapse(key):
        data = get(SPONSOR + key, CHUNK)
        patch = np.frombuffer(data, np.uint8).reshape(28, 128, 128)
        return key, sha256(data).hexdigest(), np.any(patch, axis=0)

    with ThreadPoolExecutor(max_workers=6) as pool:
        for key, checksum, mask in pool.map(collapse, sorted(low_keys)):
            row, col = map(int, key.split('/')[-2:])
            tile = occupancy[row*128:(row+1)*128, col*128:(col+1)*128]
            tile[:] = mask[:tile.shape[0], :tile.shape[1]]
            wire += CHUNK
            manifest.append({'path': key, 'sha256': checksum})
    layout = [(y, x) for y in positions(7660) for x in positions(11140)
              if occupancy[y//8:(y+384+7)//8, x//8:(x+384+7)//8].any()]
    n = len(layout)
    center = min(range(n), key=lambda i: ((layout[i][0]+192-7660/2)**2+
                                         (layout[i][1]+192-11140/2)**2, layout[i]))
    indexes = list(dict.fromkeys((0, n//4, n//2, 3*n//4, n-1, center)))
    if select is not None:
        indexes = select(layout, indexes)
    windows = [{'ordinal': i, 'y': layout[i][0], 'x': layout[i][1]} for i in indexes]
    write(output/'window_selection.json', {'count': n, 'registered_windows': windows,
          'occupancy_sha256': sha256(occupancy.tobytes()).hexdigest(), 'selection_observed_before_full_resolution': True})
    needed = {(r, c) for w in windows for r in range(w['y']//128, (w['y']+383)//128+1)
              for c in range(w['x']//128, (w['x']+383)//128+1)}
    available = set()
    for row in sorted({r for r,c in needed}):
        keys, length = list_keys(STORE+f'0/0/{row}/')
        wire += length
        available |= keys
    count = 17 * 128 * 128
    intervals = (6 * 128 * 128, 23 * 128 * 128 - 1)
    present = {(r,c) for r,c in needed if STORE+f'0/0/{r}/{c}' in available}
    if wire + count * len(present) > byte_budget:
        raise ValueError('selected high-resolution windows exceed the registered byte budget')

    def fetch(pos):
        r, c = pos
        key = STORE + f'0/0/{r}/{c}'
        data = get(SPONSOR + key, count, intervals)
        if len(data) != count:
            raise ValueError('incomplete native planes')
        return pos, data, {'path': key, 'byte_range': list(intervals), 'sha256': sha256(data).hexdigest()}

    blocks = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        for pos, data, item in pool.map(fetch, sorted(present)):
            blocks[pos] = np.frombuffer(data, np.uint8).reshape(17,128,128)
            wire += len(data)
            manifest.append(item)
    for w in windows:
        y, x = w['y'], w['x']
        region = np.zeros((17,384,384), dtype=np.uint8)
        fill = []
        for r in range(y//128,(y+383)//128+1):
            for c in range(x//128,(x+383)//128+1):
                if (r,c) not in blocks:
                    fill.append([r,c])
                    continue
                sy, sx = max(y,128*r), max(x,128*c)
                ey, ex = min(y+384,128*(r+1)), min(x+384,128*(c+1))
                region[:,sy-y:ey-y,sx-x:ex-x] = blocks[r,c][:,sy-128*r:ey-128*r,sx-128*c:ex-128*c]
        data = region.tobytes()
        name = '%d_%d.raw' % (y,x)
        (raw/name).write_bytes(data)
        center_value = float(np.median(region))
        mad = float(np.median(np.abs(region-center_value)))
        w.update(filename=name, sha256=sha256(data).hexdigest(), mad=mad, median=center_value,
                 occupied=int(np.count_nonzero(region)), missing_fill_chunks=fill)
    write(output/'window_inputs.json', {'source': SPONSOR+STORE, 'bytes_received': wire, 'tiles': windows,
          'requests': manifest, 'license':'CC BY-NC 4.0; attribution to Vesuvius Challenge. CT redistribution excluded.'})
    print(json.dumps({'bytes': wire, 'scheduled': n, 'windows':[(w['ordinal'],w['mad'],w['occupied']) for w in windows]}))


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output',type=Path)
    run(parser.parse_args().output)
