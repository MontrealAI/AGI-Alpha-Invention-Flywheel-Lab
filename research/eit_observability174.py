"""Bounded Zenodo source-metadata check; not a physical, clinical or financial result."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

URL = 'https://zenodo.org/api/records/24120439'
DOI = '10.5281/zenodo.24120439'
RECORD_ID = 24120439
MAX_BYTES = 1024 * 1024
FAMILIES = ('AgarCylinderPhantom', 'AgarChestPhantom', 'HeadPhantom')
VERSION = 'agi-alpha/eit-observatory174-metadata-preflight/v1'

class PreflightError(ValueError):
    pass

class ZenodoOnlyRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        u = urlsplit(newurl)
        if u.scheme != 'https' or u.hostname != 'zenodo.org':
            raise PreflightError('NON_ZENODO_OR_INSECURE_REDIRECT_REFUSED')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def download_metadata():
    opener = build_opener(ZenodoOnlyRedirect())
    req = Request(URL, headers={'Accept':'application/json','User-Agent':'AGI-ALPHA-EIT174-metadata-only/1'})
    with opener.open(req, timeout=25) as response:
        if getattr(response, 'status', 200) != 200:
            raise PreflightError('PUBLIC_METADATA_HTTP_NOT_OK')
        u = urlsplit(response.geturl())
        if u.scheme != 'https' or u.hostname != 'zenodo.org':
            raise PreflightError('PUBLIC_METADATA_ORIGIN_CHANGED')
        return response.read(MAX_BYTES + 1)

def _plain_name(name):
    return (isinstance(name, str) and 0 < len(name) <= 180
            and name not in {'.','..'} and not name.startswith('.')
            and not any(c in name for c in ('/', chr(92), chr(0), chr(13), chr(10)))
            and all(32 <= ord(c) < 127 for c in name))

def validate_metadata(raw: bytes):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
        raise PreflightError('BOUNDED_NONEMPTY_METADATA_REQUIRED')
    try:
        data = json.loads(raw.decode('utf-8'))
    except (UnicodeError, ValueError) as exc:
        raise PreflightError('VALID_UTF8_JSON_METADATA_REQUIRED') from exc
    if not isinstance(data, dict) or type(data.get('id')) is not int or data['id'] != RECORD_ID:
        raise PreflightError('EXACT_ZENODO_RECORD_ID_REQUIRED')
    if str(data.get('doi','')).lower() != DOI:
        raise PreflightError('EXACT_VERSION_DOI_REQUIRED')
    md = data.get('metadata')
    if not isinstance(md, dict) or not isinstance(md.get('title'),str) or not md['title'].strip():
        raise PreflightError('PUBLISHER_TITLE_REQUIRED')
    files = data.get('files')
    if not isinstance(files,list) or not 3 <= len(files) <= 200:
        raise PreflightError('BOUNDED_FILE_LIST_REQUIRED')
    seen,listed,matched = set(),[],{}
    allowed = {f.casefold():f for f in FAMILIES}
    for entry in files:
        if not isinstance(entry,dict):
            raise PreflightError('PUBLISHER_FILE_RECORD_REQUIRED')
        name = entry.get('key')
        if not _plain_name(name):
            raise PreflightError('PLAIN_ARCHIVE_BASENAME_REQUIRED')
        if name.casefold() in seen:
            raise PreflightError('DUPLICATE_FILE_BASENAME_REFUSED')
        seen.add(name.casefold())
        size = entry.get('size')
        if type(size) is not int or not 0 < size <= 2**40:
            raise PreflightError('POSITIVE_BOUNDED_PUBLISHER_SIZE_REQUIRED')
        checksum = entry.get('checksum')
        if checksum is not None and (not isinstance(checksum,str) or
                not re.fullmatch(r'[a-z0-9_-]{2,24}:[a-fA-F0-9]{16,128}',checksum)):
            raise PreflightError('PUBLISHER_CHECKSUM_SHAPE_CHANGED')
        listed.append({'name':name,'publisher_size_bytes':size,
                       'publisher_claimed_checksum':checksum,
                       'archive_bytes_downloaded':False,'independent_file_digest':None})
        if name.lower().endswith('.zip'):
            stem = name[:-4].casefold()
            if stem in allowed:
                if stem in matched:
                    raise PreflightError('DUPLICATE_EXPECTED_FAMILY_REFUSED')
                matched[stem] = name
    if set(matched) != set(allowed):
        raise PreflightError('THREE_EXACT_EXPERIMENT_FAMILIES_REQUIRED')
    license_obj = md.get('license')
    license_id = license_obj.get('id') if isinstance(license_obj,dict) else (license_obj if isinstance(license_obj,str) else None)
    return {'schema':VERSION,'status':'METADATA_PREFLIGHT_PASS','source_url':URL,'expected_doi':DOI,
            'record_id':RECORD_ID,'metadata_sha256':hashlib.sha256(raw).hexdigest(),
            'metadata_length_bytes':len(raw),'publisher_title':md['title'],
            'publisher_version':md.get('version'),'publisher_license_identifier':license_id,
            'archive_families':{allowed[k]:matched[k] for k in sorted(matched)},
            'listed_publisher_files':listed,'raw_experimental_data_verified':False,
            'image_reconstruction_or_physical_observability_tested':False,
            'clinical_or_commercial_validation':False,'actual_external_bill_usd':None,
            'scope':'SOURCE_METADATA_ONLY_NO_CONDUCTIVITY_INFERENCE_OR_BUYER_EVIDENCE'}

def _write(path,data):
    path = Path(path).absolute()
    if path.exists() or path.is_symlink():
        raise PreflightError('CREATE_ONLY_RECEIPT_REQUIRED')
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp = path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
    try:
        with tmp.open('x',encoding='utf-8') as f:
            json.dump(data,f,indent=2,sort_keys=True)
            f.write(chr(10))
        os.replace(tmp,path)
    finally:
        tmp.unlink(missing_ok=True)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    wall=time.perf_counter()
    cpu=time.process_time()
    try:
        receipt=validate_metadata(download_metadata())
        code=0
    except Exception as exc:
        receipt={'schema':VERSION,'status':'FAILED','source_url':URL,
                 'failure_class':type(exc).__name__,'failure_code':str(exc)[:180],
                 'raw_experimental_data_verified':False,
                 'image_reconstruction_or_physical_observability_tested':False,
                 'actual_external_bill_usd':None}
        code=1
    receipt['process_self_cpu_seconds']=round(time.process_time()-cpu,6)
    receipt['wall_seconds']=round(time.perf_counter()-wall,6)
    try:
        _write(args.output,receipt)
    except Exception as exc:
        print('RECEIPT_WRITE_FAILED:'+type(exc).__name__,file=sys.stderr)
        return 1
    print(json.dumps({k:receipt.get(k) for k in ('schema','status','metadata_sha256',
          'archive_families','failure_code','process_self_cpu_seconds','wall_seconds')},sort_keys=True))
    return code

if __name__=='__main__':
    raise SystemExit(main())
