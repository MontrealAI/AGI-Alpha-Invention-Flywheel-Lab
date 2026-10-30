import argparse,gzip,hashlib,importlib.util,json,sys
from pathlib import Path

def main(root,source,input_path,output,expected):
    sys.path.insert(0,str(root));raw=source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('SUCCESSOR_SOURCE_MISMATCH')
    spec=importlib.util.spec_from_file_location('tested_successor_runtime',source);candidate=importlib.util.module_from_spec(spec);spec.loader.exec_module(candidate)
    payload=json.loads(gzip.decompress(input_path.read_bytes()));rows=[]
    for batch in payload['batches']:
        decoder=candidate.DriftInterpreter(payload['corpus'],batch['plan'])
        results=[]
        for case in batch['cases']:
            try:result={'case':case['case'],'result':decoder.diagnose(case['observations'])}
            except Exception as error:result={'case':case['case'],'error':type(error).__name__,'message':str(error)}
            results.append(result)
        rows.append({'name':batch['name'],'results':results})
    if source.read_bytes()!=raw:raise ValueError('SUCCESSOR_SOURCE_CHANGED')
    with output.open('x') as stream:json.dump({'source_sha256':expected,'batches':rows},stream,sort_keys=True,allow_nan=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--expected-source-sha256',required=True);a=p.parse_args();main(a.root.resolve(),a.source.resolve(),a.input.resolve(),a.output.resolve(),a.expected_source_sha256)
