#!/usr/bin/env python3
"""Stage only three approved artwork files, with a verified existing-art fallback.
Run before the Atlas projection hash so a later artwork release upload triggers
normal scheduled Pages publication. No change to participant archive or gate.
"""
import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

NAME = 'FRONTIER-CONCLAVE-VISUALS.zip'
ARCHIVE_SHA = '96b4688790402adaa60d5aefe06cf23f637fb041baa440f37ae0eddc34dbb0aa'
ASSETS = {
    'arrival.webp': (457212, 'ac2b4f5e128ae05f626362a7de2a711684a744918fac4b9e3ca6ae6b2127eb8c'),
    'flywheel.webp': (570806, '08ca88f31a486d2a81494633ef2a31f43c726b739f68a6f06bf8b0aa731581da'),
    'sanctum.webp': (340096, '2bb3bcb56ca9d55c78ab224b207b699a3a73b23d5e5600ec870f887e743f75d3'),
}
FALLBACK = {
    'arrival.webp': 'double-flywheel-cover.webp',
    'flywheel.webp': 'double-flywheel-cover.webp',
    'sanctum.webp': 'double-flywheel-finale.webp',
}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def stage(site, archive=None):
    site = Path(site)
    if not (site / 'frontier-conclave.html').is_file():
        raise ValueError('Expected built site')
    dst = site / 'conclave-visuals'
    if dst.exists() or dst.is_symlink():
        raise ValueError('Artwork destination already exists')
    payloads = {}
    if archive is not None:
        archive = Path(archive)
        if archive.name != NAME or archive.stat().st_size != 1368438 or sha(archive.read_bytes()) != ARCHIVE_SHA:
            raise ValueError('Artwork ZIP does not match the approved image pack')
        with zipfile.ZipFile(archive) as z:
            if len(z.infolist()) != 3 or set(z.namelist()) != set(ASSETS):
                raise ValueError('Unexpected artwork members')
            for name, (size, digest) in ASSETS.items():
                if z.getinfo(name).file_size != size:
                    raise ValueError('Unexpected artwork size')
                data = z.read(name)
                if sha(data) != digest:
                    raise ValueError('Artwork digest mismatch')
                payloads[name] = data
        mode = 'celestial-2026-11-28'
    else:
        for name, source in FALLBACK.items():
            payloads[name] = (site / 'frontier-omega-alpha' / source).read_bytes()
        mode = 'existing-conclave'
    for data in payloads.values():
        if data[:4] != b'RIFF' or data[8:12] != b'WEBP':
            raise ValueError('Not a WebP image')
    dst.mkdir()
    for name, data in payloads.items():
        (dst / name).write_bytes(data)
    meta = {'schema':1, 'artwork':mode, 'sha256':{name:sha(data) for name,data in payloads.items()}}
    (dst / 'edition.json').write_text(json.dumps(meta, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(meta, sort_keys=True))

if __name__ == '__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--site', required=True, type=Path)
    cli.add_argument('--archive', type=Path)
    args=cli.parse_args()
    stage(args.site,args.archive)
