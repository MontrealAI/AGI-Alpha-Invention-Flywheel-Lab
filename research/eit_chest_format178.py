"""EIT178: one fixed public-source header classification; EIT177 remains FAILED."""
from __future__ import annotations
import argparse
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from zipfile import ZipFile, BadZipFile
from research import eit_chest177 as parent

SCHEMA = 'agi-alpha/eit178-chest-selected-pair-header-only/v1'
PROTOCOL_COMMIT = 'd32fc8e99f274d77478bad6ae9a146e8c2725c97'
HDF5 = b'\x89HDF\r\n\x1a\n'
MAT5 = b'MATLAB 5.0 MAT-file'
OFFSETS = (0, 512, 1024, 2048)

def classify(raw):
    if raw.startswith(MAT5):
        return 'MATLAB5_HEADER'
    if any(raw[i:i+len(HDF5)] == HDF5 for i in OFFSETS):
        return 'HDF5_SIGNATURE'
    return 'UNIDENTIFIED_HEADER'

def diagnose(raw):
    source = parent.verify_source(raw)
    try:
        with ZipFile(BytesIO(raw)) as z:
            entries, total = parent._members(z)
            key, first, second = parent._first_pair(entries)
            selected = []
            for item in (first, second):
                if not 0 < item.file_size <= parent.MAX_MAT:
                    raise parent.Refused('BOUNDED_SELECTED_MAT_REQUIRED')
                content = z.read(item)
                if len(content) != item.file_size:
                    raise parent.Refused('TRUNCATED_SELECTED_MAT')
                selected.append({'path':item.filename,'bytes':len(content),
                                 'sha256':hashlib.sha256(content).hexdigest(),
                                 'first_16_bytes_hex':content[:16].hex(),
                                 'header_class':classify(content)})
    except BadZipFile as e:
        raise parent.Refused('BAD_ZIP_MEMBER') from e
    return {**source, 'status':'FORMAT_DIAGNOSIS_RECORDED',
            'selected_repeat_stem':key, 'members':selected,
            'archive_member_count':len(entries),
            'declared_uncompressed_bytes':total,
            'original_eit177_result':'FAILED_INVALID_MAT73_MEMBER',
            'numerical_measurements_tested':False,
            'physical_inverse_problem_solved':False,
            'real_commercial_profit_proved':False}

def run(output):
    output=Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise parent.Refused('CREATE_ONLY_DIAGNOSTIC_RECEIPT')
    wall=time.perf_counter()
    cpu=time.process_time()
    record={'schema':SCHEMA,'protocol_commit':PROTOCOL_COMMIT,
            'parent_failure_workflow':43752021213,
            'source':parent.SOURCE,'publisher_md5_claim':parent.MD5,
            'publisher_size':parent.SIZE,'status':'FAILED',
            'archive_sha256':None, 'members':None,
            'original_eit177_result':'FAILED_INVALID_MAT73_MEMBER',
            'numerical_measurements_tested':False,
            'real_commercial_profit_proved':False}
    try:
        record.update(diagnose(parent.download_once()))
        record['failure_code']=None
        code=0
    except HTTPError as e:
        record['failure_code']='HTTP_'+str(e.code)
        code=1
    except (parent.Refused, URLError, OSError, TimeoutError, ValueError) as e:
        record['failure_code']=str(e) if isinstance(e,parent.Refused) else type(e).__name__
        code=1
    record['wall_seconds']=round(time.perf_counter()-wall,6)
    record['self_cpu_seconds']=round(time.process_time()-cpu,6)
    record['actual_account_model_host_bill_usd']=None
    output.parent.mkdir(parents=True,exist_ok=True)
    with os.fdopen(os.open(output,os.O_CREAT | os.O_EXCL | os.O_WRONLY,0o644),'w') as f:
        json.dump(record,f,indent=2,sort_keys=True,allow_nan=False)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps({k:record.get(k) for k in ('status','archive_sha256','members','failure_code')},sort_keys=True))
    return code

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True)
    return run(p.parse_args().output)

if __name__=='__main__':
    sys.exit(main())
