"""EIT175: fixed public ZIP-byte witness and unmodified repeat-measurement inspection."""
from __future__ import annotations

import argparse
from io import BytesIO
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zipfile import BadZipFile, ZipFile

SOURCE_URL = 'https://zenodo.org/api/records/24120439/files/AgarCylinderPhantom.zip/content'
EXPECTED_SIZE = 12_482_688
EXPECTED_MD5 = '658694f69f64075b6fefec2e2c597131'
MAX_DOWNLOAD = 20 * 1024 * 1024
MAX_ZIP_FILES = 2000
MAX_UNCOMPRESSED = 500 * 1024 * 1024
MAX_MEMBER_MAT = 64 * 1024 * 1024
MAX_ARRAY_VALUES = 2_000_000
SCHEMA = 'agi-alpha/eit-physical-repeat175-preflight/v1'

class SourceRefused(ValueError):
    pass

class RestrictedRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        p = urlsplit(newurl)
        if p.scheme != 'https' or p.hostname != 'zenodo.org':
            raise SourceRefused('UNEXPECTED_ARCHIVE_REDIRECT_REFUSED')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def download_fixed_archive():
    opener = build_opener(RestrictedRedirect())
    request = Request(SOURCE_URL, headers={'Accept':'application/octet-stream',
                'User-Agent':'AGI-ALPHA-EIT175-fixed-science-preflight/1'})
    with opener.open(request, timeout=60) as response:
        url = urlsplit(response.geturl())
        if response.status != 200 or url.scheme != 'https' or url.hostname != 'zenodo.org':
            raise SourceRefused('ORIGIN_OR_HTTP_STATUS_CHANGED')
        raw = response.read(MAX_DOWNLOAD + 1)
    return raw

def verify_archive_bytes(raw: bytes):
    if not isinstance(raw,bytes) or len(raw) != EXPECTED_SIZE or len(raw)>MAX_DOWNLOAD:
        raise SourceRefused('EXACT_ARCHIVE_SIZE_MISMATCH')
    md5 = hashlib.md5(raw,usedforsecurity=False).hexdigest()
    if md5.lower() != EXPECTED_MD5:
        raise SourceRefused('PUBLISHER_MD5_MISMATCH')
    return {'archive_size':len(raw),'archive_md5':md5,'archive_sha256':hashlib.sha256(raw).hexdigest()}

def _safe(name):
    if not isinstance(name,str) or not name or len(name)>260 or chr(92) in name or any(ord(x)<32 for x in name):
        return False
    p=PurePosixPath(name)
    return (not p.is_absolute() and not name.startswith('./') and
            not any(part in ('..','.') for part in name.split('/')) and
            all(32 <= ord(c) <= 126 for c in name))

def validate_archive(raw):
    try:
        zf=ZipFile(BytesIO(raw))
        items=zf.infolist()
        if not 1 <= len(items) <= MAX_ZIP_FILES:
            raise SourceRefused('BOUNDED_ARCHIVE_MEMBER_COUNT_REQUIRED')
        seen=set();total=0
        for item in items:
            name=item.filename
            if not _safe(name):
                raise SourceRefused('UNSAFE_ARCHIVE_MEMBER_PATH')
            low=name.casefold()
            if low in seen:
                raise SourceRefused('DUPLICATE_MEMBER_NAME')
            seen.add(low)
            if item.flag_bits & 1:
                raise SourceRefused('ENCRYPTED_ZIP_MEMBER')
            unixmode=(item.external_attr>>16)&0o170000
            if unixmode==stat.S_IFLNK:
                raise SourceRefused('ZIP_SYMLINK_MEMBER')
            if item.file_size < 0 or item.compress_size < 0:
                raise SourceRefused('NEGATIVE_ARCHIVE_MEMBER_LENGTH')
            total += item.file_size
            if total>MAX_UNCOMPRESSED:
                raise SourceRefused('UNCOMPRESSED_ZIP_SIZE_LIMIT')
        if zf.testzip() is not None:
            raise SourceRefused('INVALID_ZIP_DATA_CRC')
        return zf,items,total
    except (BadZipFile, OSError, EOFError, RuntimeError, zlib_error()) as exc:
        raise SourceRefused('INVALID_ZIP_DATA') from exc

def zlib_error():
    import zlib
    return zlib.error

def find_first_replicate(items):
    groups={}
    for item in items:
        if item.is_dir():continue
        path=PurePosixPath(item.filename)
        if 'data' not in [x.casefold() for x in path.parts[:-1]]:continue
        if not path.suffix.casefold()=='.mat':continue
        base=path.stem
        if len(base)<3 or base[-2:].casefold() not in ('_1','_2'):continue
        key=(str(path.parent)+'/'+base[:-2]).casefold()
        slot=base[-1]
        group=groups.setdefault(key,{})
        if slot in group:
            raise SourceRefused('AMBIGUOUS_REPEAT_PAIRS')
        group[slot]=item
    qualified=sorted(k for k,v in groups.items() if set(v)=={'1','2'})
    if not qualified:
        raise SourceRefused('NO_REGISTERED_REPEAT_PAIR_AVAILABLE')
    k=qualified[0]
    return (groups[k]['1'],groups[k]['2']),k

def read_measurements(zf,item):
    if item.file_size<=0 or item.file_size>MAX_MEMBER_MAT:
        raise SourceRefused('BOUNDED_MEASUREMENT_MAT_REQUIRED')
    try:
        import h5py
        import numpy as np
        raw=zf.read(item)
        if len(raw)!=item.file_size:
            raise SourceRefused('MEASUREMENT_MEMBER_TRUNCATED')
        with h5py.File(BytesIO(raw),'r') as hf:
            if not {'currents_matrix','voltages_matrix','units_info'}.issubset(hf.keys()):
                raise SourceRefused('EXPECTED_MAT73_MEASUREMENT_FIELDS_MISSING')
            matrices=[]
            for key in ('currents_matrix','voltages_matrix'):
                field=hf[key]
                if not isinstance(field,h5py.Dataset) or len(field.shape)!=2:
                    raise SourceRefused('MATRIX_DATASET_RANK_REQUIRED')
                count=math.prod(field.shape)
                if not 0<count<=MAX_ARRAY_VALUES or field.dtype.kind not in ('i','u','f'):
                    raise SourceRefused('FINITE_BOUNDED_REAL_MATRIX_REQUIRED')
                data=np.asarray(field[...],dtype=np.float64)
                if not np.isfinite(data).all():
                    raise SourceRefused('FINITE_BOUNDED_REAL_MATRIX_REQUIRED')
                matrices.append(data)
            return {'member':item.filename,'member_sha256':hashlib.sha256(raw).hexdigest(),
                    'shapes':[list(x.shape) for x in matrices],'arrays':matrices}
    except SourceRefused:
        raise
    except Exception as exc:
        raise SourceRefused('MATLAB73_MEASUREMENT_READ_FAILED:'+type(exc).__name__) from exc

def inspect_archive(raw):
    import numpy as np
    identity=verify_archive_bytes(raw)
    zf,items,total=validate_archive(raw)
    try:
        selected,key=find_first_replicate(items)
        measurements=[read_measurements(zf,item) for item in selected]
    finally:
        zf.close()
    left,right=measurements
    if left['shapes']!=right['shapes']:
        raise SourceRefused('REPEAT_CURRENT_VOLTAGE_DIMENSIONS_CHANGED')
    results=[]
    for i,name in enumerate(('currents_matrix','voltages_matrix')):
        a,b=left['arrays'][i],right['arrays'][i]
        diff=a-b
        results.append({'field':name,'shape':list(a.shape),
                        'rms_direct_difference':float(np.sqrt(np.mean(np.square(diff)))),
                        'max_absolute_direct_difference':float(np.max(np.abs(diff))),
                        'mean_abs_first':float(np.mean(np.abs(a))),
                        'mean_abs_second':float(np.mean(np.abs(b)))})
    return {**identity,'status':'ARCHIVE_BYTES_AND_REPEAT_FIELDS_ACCESSIBLE',
            'zip_member_count':len(items),'zip_declared_uncompressed_bytes':total,
            'selected_repeat_stem':key,
            'selected_mat_members':[{'path':m['member'],'sha256':m['member_sha256'],'shapes':m['shapes']} for m in measurements],
            'direct_repeat_array_statistics':results,
            'raw_archive_bytes_verified':True,'some_measurement_arrays_parsed':True,
            'image_reconstruction_tested':False,'measurement_physics_independently_calibrated':False,
            'clinical_validity_established':False,'commercial_or_native_financial_progress':False}

def _write(path, receipt):
    path=Path(path).absolute()
    if path.exists() or path.is_symlink():
        raise SourceRefused('CREATE_ONLY_EIT175_RECEIPT_REQUIRED')
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
    try:
        with tmp.open('x',encoding='utf-8') as handle:
            json.dump(receipt,handle,sort_keys=True,indent=2,allow_nan=False)
            handle.write(chr(10))
        os.replace(tmp,path)
    finally:
        tmp.unlink(missing_ok=True)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args(argv)
    wc=time.perf_counter();cc=time.process_time()
    try:
        result=inspect_archive(download_fixed_archive())
        code=0
    except Exception as e:
        code=1
        result={'status':'FAILED','failure_class':type(e).__name__,'failure_code':str(e)[:220],
                'raw_archive_bytes_verified':False,'some_measurement_arrays_parsed':False,
                'image_reconstruction_tested':False,'commercial_or_native_financial_progress':False}
    result.update(schema=SCHEMA,source_url=SOURCE_URL,expected_publisher_md5=EXPECTED_MD5,
                  expected_archive_length_bytes=EXPECTED_SIZE,
                  cpu_self_seconds=round(time.process_time()-cc,6),
                  wall_seconds=round(time.perf_counter()-wc,6),
                  whole_campaign_and_actual_model_billing_usd=None)
    try:_write(args.output,result)
    except Exception as exc:
        print('EIT175_RECEIPT_WRITE_ERROR:'+type(exc).__name__,file=sys.stderr)
        return 1
    print(json.dumps({k:result.get(k) for k in
        ('schema','status','archive_size','archive_sha256','selected_repeat_stem','failure_code','cpu_self_seconds','wall_seconds')},sort_keys=True))
    return code

if __name__=='__main__':
    raise SystemExit(main())
