"""EIT177 exact public AgarChest source/pair preflight. No inversion or financial claims."""
from __future__ import annotations
import argparse
from io import BytesIO
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zipfile import BadZipFile, ZipFile

SOURCE = 'https://zenodo.org/api/records/24120439/files/AgarChestPhantom.zip/content'
SIZE = 24_539_080
MD5 = '8514af69c0277f339d5576dd4eb9a598'
MAX_READ = 32 * 1024 * 1024
MAX_MAT = 64 * 1024 * 1024
MAX_TOTAL = 500 * 1024 * 1024
MAX_VALUES = 2_000_000
SCHEMA = 'agi-alpha/eit177-agar-chest-direct-repeat/v1'
FROZEN_PROTOCOL_COMMIT = '3461e808d315ab60a36a9d3113c32e78a443efae'

class Refused(ValueError):
    pass

def _same_host(url):
    u = urlsplit(url)
    return u.scheme == 'https' and u.hostname == 'zenodo.org' and u.port in (None, 443)

class ZenodoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _same_host(newurl):
            raise Refused('REDIRECT_OUTSIDE_PINNED_HOST')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def download_once(opener=None):
    req = Request(SOURCE, headers={'Accept': '*/*', 'User-Agent': 'AGI-ALPHA-EIT177-chest/1'}, method='GET')
    with (opener or build_opener(ZenodoRedirect())).open(req, timeout=60) as resp:
        if resp.status != 200 or not _same_host(resp.geturl()):
            raise Refused('NON200_OR_ORIGIN_CHANGED')
        raw = resp.read(MAX_READ + 1)
    return raw

def verify_source(raw):
    if type(raw) is not bytes or len(raw) != SIZE:
        raise Refused('EXACT_SOURCE_SIZE_MISMATCH')
    if hashlib.md5(raw, usedforsecurity=False).hexdigest() != MD5:
        raise Refused('PUBLISHER_MD5_MISMATCH')
    return {'archive_size': len(raw), 'archive_md5': MD5,
            'archive_sha256': hashlib.sha256(raw).hexdigest()}

def _members(z):
    items = z.infolist()
    if not items or len(items) > 2000:
        raise Refused('ZIP_MEMBER_COUNT_BOUNDS')
    seen, total = set(), 0
    for info in items:
        name = info.filename
        p = PurePosixPath(name)
        if (not name or len(name) > 240 or name.startswith('/') or '\\' in name or '\x00' in name
            or any(part in ('', '.', '..') for part in name.rstrip('/').split('/'))
            or not all(32 <= ord(c) < 127 for c in name)
            or stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK):
            raise Refused('UNSAFE_ARCHIVE_MEMBER')
        if p.as_posix().casefold() in seen:
            raise Refused('DUPLICATE_CASEFOLD_ARCHIVE_MEMBER')
        seen.add(p.as_posix().casefold())
        if info.flag_bits & 1:
            raise Refused('ENCRYPTED_ARCHIVE_MEMBER')
        if info.file_size < 0:
            raise Refused('NEGATIVE_UNCOMPRESSED_SIZE')
        total += info.file_size
        if total > MAX_TOTAL:
            raise Refused('ZIP_DECLARED_UNCOMPRESSED_RESOURCE_BOUND')
    if z.testzip() is not None:
        raise Refused('ZIP_BAD_CRC')
    return items, total

def _first_pair(items):
    found = {}
    for item in items:
        if item.is_dir():
            continue
        p = PurePosixPath(item.filename)
        if not any(x.casefold() == 'data' for x in p.parts[:-1]) or p.suffix.casefold() != '.mat':
            continue
        if len(p.stem) < 3 or p.stem[-2:].casefold() not in ('_1', '_2'):
            continue
        key = (str(p.parent) + '/' + p.stem[:-2]).casefold()
        slot = p.stem[-1]
        d = found.setdefault(key, {})
        if slot in d:
            raise Refused('AMBIGUOUS_PAIR_NAME')
        d[slot] = item
    candidates = sorted(k for k,v in found.items() if set(v) == {'1', '2'})
    if not candidates:
        raise Refused('NO_EXACT_REPEATED_DATA_PAIR')
    key = candidates[0]
    return key, found[key]['1'], found[key]['2']

def _mat(z, member):
    import h5py
    import numpy as np
    if not 0 < member.file_size <= MAX_MAT:
        raise Refused('MAT_MEMBER_SIZE_BOUNDS')
    raw = z.read(member)
    if len(raw) != member.file_size:
        raise Refused('TRUNCATED_MAT_MEMBER')
    try:
        with h5py.File(BytesIO(raw), 'r') as f:
            if not {'currents_matrix', 'voltages_matrix', 'units_info'}.issubset(f.keys()):
                raise Refused('REQUIRED_MAT73_FIELDS_MISSING')
            arrays = {}
            for field in ('currents_matrix', 'voltages_matrix'):
                ds = f[field]
                if (not isinstance(ds, h5py.Dataset) or len(ds.shape) != 2
                    or not 0 < math.prod(ds.shape) <= MAX_VALUES or ds.dtype.kind not in ('f', 'i', 'u')):
                    raise Refused('REAL_BOUNDED_RANK2_MATRIX_REQUIRED')
                array = np.asarray(ds[...], dtype=np.float64)
                if not np.isfinite(array).all():
                    raise Refused('NONFINITE_MEASUREMENT')
                arrays[field] = array
    except (OSError, RuntimeError) as exc:
        raise Refused('INVALID_MAT73_MEMBER') from exc
    return {'path': member.filename, 'sha256': hashlib.sha256(raw).hexdigest(), 'arrays': arrays}

def inspect(raw):
    import numpy as np
    proof = verify_source(raw)
    try:
        with ZipFile(BytesIO(raw)) as z:
            items, total = _members(z)
            key, m1, m2 = _first_pair(items)
            a, b = _mat(z, m1), _mat(z, m2)
    except BadZipFile as exc:
        raise Refused('INVALID_ZIP') from exc
    measurements = []
    for field in ('currents_matrix', 'voltages_matrix'):
        x, y = a['arrays'][field], b['arrays'][field]
        if x.shape != y.shape:
            raise Refused('REPEAT_DIMENSIONS_CHANGED')
        diff = x - y
        scale = float(np.sqrt((np.mean(x*x) + np.mean(y*y))/2))
        rms = float(np.sqrt(np.mean(diff*diff)))
        measurements.append({'field': field, 'shape': list(x.shape),
                             'rms_direct_difference': rms,
                             'max_abs_direct_difference': float(np.max(np.abs(diff))),
                             'mean_abs_first': float(np.mean(np.abs(x))),
                             'mean_abs_second': float(np.mean(np.abs(y))),
                             'relative_rms_discrepancy': rms/scale if scale else None})
    return {**proof, 'status': 'REPEAT_FIELDS_ACCESSIBLE', 'selected_repeat_stem': key,
            'member_count': len(items), 'declared_uncompressed_bytes': total,
            'paired_members': [{'path':m['path'], 'sha256':m['sha256']} for m in (a,b)],
            'measurements': measurements, 'physical_inversion_tested': False,
            'new_observability_demonstrated': False, 'commercial_proof': False}

def run(path):
    path = Path(path).absolute()
    if path.exists() or path.is_symlink():
        raise Refused('CREATE_ONLY_RECEIPT_REQUIRED')
    started = time.perf_counter()
    cpu = time.process_time()
    receipt = {'schema': SCHEMA, 'protocol_commit': FROZEN_PROTOCOL_COMMIT,
               'source': SOURCE, 'publisher_size': SIZE, 'publisher_md5_claim': MD5,
               'status': 'FAILED', 'archive_sha256': None, 'selected_repeat_stem': None,
               'physical_inversion_tested': False, 'commercial_proof': False}
    try:
        receipt.update(inspect(download_once()))
        receipt['failure_code'] = None
        exit_code = 0
    except HTTPError as exc:
        receipt['failure_code'] = 'HTTP_' + str(exc.code)
        exit_code = 1
    except (Refused, URLError, OSError, TimeoutError, ValueError) as exc:
        receipt['failure_code'] = str(exc) if isinstance(exc, Refused) else type(exc).__name__
        exit_code = 1
    receipt['self_cpu_seconds'] = round(time.process_time()-cpu, 6)
    receipt['wall_seconds'] = round(time.perf_counter()-started, 6)
    receipt['full_campaign_bill_usd'] = None
    path.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644), 'w') as fp:
        json.dump(receipt, fp, indent=2, sort_keys=True, allow_nan=False)
        fp.write('\n')
        fp.flush()
        os.fsync(fp.fileno())
    print(json.dumps({k:receipt.get(k) for k in ('status','archive_sha256','selected_repeat_stem','failure_code')}, sort_keys=True))
    return exit_code

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    return run(p.parse_args().output)

if __name__ == '__main__':
    sys.exit(main())
