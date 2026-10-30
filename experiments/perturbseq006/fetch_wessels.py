"""Download the public CC-BY4 scPerturb input with exact primary-source identity."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import requests

URL='https://zenodo.org/records/13350497/files/WesselsSatija2023.h5ad?download=1&agi-alpha-cycle=006-full'
SIZE=219393529
MD5='6897bfdcda928a678208fecf4eeb282e'

def run(output,route=None):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    target=output/'WesselsSatija2023.h5ad';report={'url':URL,'expected_size':SIZE,'expected_md5':MD5,'license':'CC-BY-4.0','full_outcomes_inspected':False}
    started=time.monotonic();sha=hashlib.sha256();md5=hashlib.md5();received=0
    session=requests.Session()
    if route:
        config=json.loads(Path(route).read_text());session.proxies=config['proxies'];session.verify=config['verify'];session.trust_env=False
    try:
        response=session.get(URL,stream=True,timeout=(20,20))
        report['status']=response.status_code
        if response.status_code!=200:
            response.close();raise ValueError('FULL_FILE_RESPONSE_REQUIRED')
        with target.open('xb') as stream:
            for block in response.iter_content(1048576):
                received+=len(block)
                if received>SIZE or received>500_000_000 or time.monotonic()-started>180:
                    raise ValueError('DOWNLOAD_BOUND_EXCEEDED')
                stream.write(block);sha.update(block);md5.update(block)
        response.close()
        report.update({'received_bytes':received,'sha256':sha.hexdigest(),'md5':md5.hexdigest()})
        if received!=SIZE or md5.hexdigest()!=MD5:
            raise ValueError('PRIMARY_SOURCE_IDENTITY_MISMATCH')
        import h5py
        import numpy as np
        with h5py.File(target,'r') as data:
            report['root_keys']=list(data.keys());report['obs_keys']=list(data['obs'].keys());report['var_keys']=list(data['var'].keys())
            matrix=data['X'];report['matrix']={'attrs':{k:v.decode() if isinstance(v,bytes) else v.tolist() if hasattr(v,'tolist') else v for k,v in matrix.attrs.items()}}
            if isinstance(matrix,h5py.Dataset):report['matrix'].update({'shape':matrix.shape,'dtype':str(matrix.dtype)})
            else:report['matrix']['storage']={k:{'shape':matrix[k].shape,'dtype':str(matrix[k].dtype)} for k in matrix}
            condition=data['obs']['perturbation']
            if isinstance(condition,h5py.Group):
                categories=condition['categories'][:];codes=condition['codes'][:];counts=np.bincount(codes[codes>=0],minlength=len(categories))
                report['conditions']=[{'label':c.decode() if isinstance(c,bytes) else str(c),'cells':int(counts[i])} for i,c in enumerate(categories)]
        report['state']='SOURCE_VERIFIED_METADATA_ONLY'
    except Exception as error:
        report['state']='FAILED';report['error']={'type':type(error).__name__,'message':str(error)};report['received_bytes']=received
    finally:
        session.close()
    report['wall_seconds']=time.monotonic()-started
    (output/'DOWNLOAD.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'state':report['state'],'received_bytes':received,'wall_seconds':report['wall_seconds']}))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--runtime-route');a=p.parse_args();r=run(a.output,a.runtime_route);raise SystemExit(int(r['state']=='FAILED'))
