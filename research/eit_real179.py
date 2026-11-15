"""EIT179: prospective true-data namespace after independently diagnosed Apple sidecars."""
from __future__ import annotations
import argparse
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import sys
import time
from urllib.error import HTTPError, URLError
from zipfile import ZipFile, BadZipFile
from research import eit_chest177 as parent

FROZEN_PROTOCOL = '2759633a192a96e6a405fa8756ca8badbe653858'
SCHEMA = 'agi-alpha/eit179-real-agar-chest-direct-repeat/v1'
PINNED_SHA256 = 'ad193cd88288e3d6f8ea87f76d8ed2f06382291ab494d55efe08806c65ff994c'

def true_data_first_pair(entries):
    buckets={}
    for info in entries:
        if info.is_dir():
            continue
        path=PurePosixPath(info.filename)
        parts=path.parts
        # Exactly the real archive root's direct Data/ children: NOT __MACOSX sidecars.
        if (len(parts)!=3 or parts[0].casefold()!='agarchestphantom'
            or parts[1].casefold()!='data' or path.name.startswith('.')
            or path.suffix.casefold()!='.mat'):
            continue
        stem=path.stem
        if len(stem)<3 or stem[-2:].casefold() not in ('_1','_2'):
            continue
        identity=stem[:-2].casefold()
        slot=stem[-1]
        d=buckets.setdefault(identity,{})
        if slot in d:
            raise parent.Refused('AMBIGUOUS_TRUE_DATA_REPEAT')
        d[slot]=info
    possible=sorted(k for k,v in buckets.items() if set(v)=={'1','2'})
    if not possible:
        raise parent.Refused('NO_ELIGIBLE_REAL_DATA_REPEAT')
    chosen=possible[0]
    return chosen,buckets[chosen]['1'],buckets[chosen]['2']

def parse_pinned(raw):
    import numpy as np
    proof=parent.verify_source(raw)
    if proof['archive_sha256']!=PINNED_SHA256:
        raise parent.Refused('FROZEN_OBSERVED_SOURCE_SHA256_CHANGED')
    try:
        with ZipFile(BytesIO(raw)) as z:
            entries,total=parent._members(z)
            stem,m1,m2=true_data_first_pair(entries)
            first,second=parent._mat(z,m1),parent._mat(z,m2)
    except BadZipFile as e:
        raise parent.Refused('SOURCE_ZIP_INVALID') from e
    observations=[]
    for field in ('currents_matrix','voltages_matrix'):
        x,y=first['arrays'][field],second['arrays'][field]
        if x.shape!=y.shape:
            raise parent.Refused('REPEAT_DIMENSIONS_CHANGED')
        rms=float(np.sqrt(np.mean((x-y)**2)))
        scale=float(np.sqrt((np.mean(x*x)+np.mean(y*y))/2))
        observations.append({'field':field,'shape':list(x.shape),
                             'rms_direct_difference':rms,
                             'max_abs_direct_difference':float(np.max(np.abs(x-y))),
                             'mean_abs_first':float(np.mean(np.abs(x))),
                             'mean_abs_second':float(np.mean(np.abs(y))),
                             'relative_rms_discrepancy':rms/scale if scale else None})
    return {**proof,'status':'REAL_DATA_REPEAT_PARSED',
            'selected_true_data_stem':stem,'zip_members':len(entries),
            'zip_declared_uncompressed_bytes':total,
            'pairs':[{'path':x['path'],'sha256':x['sha256']} for x in (first,second)],
            'observations':observations,'apple_sidecar_exclusion_rule':'root/AgarChestPhantom/Data only',
            'original_eit177':'FAILED','diagnostic_eit178':'HEADER_DIAGNOSIS_RECORDED',
            'conductivity_reconstruction_tested':False,'real_commerce_proved':False}

def run(output):
    p=Path(output).absolute()
    if p.exists() or p.is_symlink():
        raise parent.Refused('CREATE_ONLY_RECEIPT')
    wall=time.perf_counter();cpu=time.process_time()
    result={'schema':SCHEMA,'protocol_commit':FROZEN_PROTOCOL,'status':'FAILED',
            'source':parent.SOURCE,'expected_publisher_size':parent.SIZE,
            'expected_md5':parent.MD5,'expected_observed_sha256':PINNED_SHA256,
            'archive_sha256':None,'original_eit177':'FAILED',
            'conductivity_reconstruction_tested':False,'real_commerce_proved':False}
    try:
        raw=parent.download_once()
        proof=parent.verify_source(raw)
        result['archive_sha256']=proof['archive_sha256']
        result.update(parse_pinned(raw))
        result['failure_code']=None
        code=0
    except HTTPError as e:
        result['failure_code']='HTTP_'+str(e.code);code=1
    except (parent.Refused,URLError,OSError,TimeoutError,ValueError) as e:
        result['failure_code']=str(e) if isinstance(e,parent.Refused) else type(e).__name__
        code=1
    result['self_cpu_seconds']=round(time.process_time()-cpu,6)
    result['wall_seconds']=round(time.perf_counter()-wall,6)
    result['whole_campaign_model_host_billing_usd']=None
    p.parent.mkdir(parents=True,exist_ok=True)
    with os.fdopen(os.open(p,os.O_CREAT | os.O_EXCL | os.O_WRONLY,0o644),'w') as f:
        json.dump(result,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
        f.flush();os.fsync(f.fileno())
    print(json.dumps({k:result.get(k) for k in ('status','archive_sha256','selected_true_data_stem','failure_code')},sort_keys=True))
    return code

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True)
    return run(p.parse_args().output)

if __name__=='__main__':
    sys.exit(main())
