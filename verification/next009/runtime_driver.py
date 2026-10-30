import argparse, hashlib, importlib.util, json
from pathlib import Path

def main(candidate_path,input_path,output_path,expected):
    raw=candidate_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected: raise ValueError('FROZEN_CANDIDATE_MISMATCH')
    spec=importlib.util.spec_from_file_location('frozen_next009_candidate',candidate_path)
    candidate=importlib.util.module_from_spec(spec);spec.loader.exec_module(candidate)
    data=json.loads(input_path.read_text())
    corpus,plan=data['corpus'],data['plan'];rows=[]
    for case in data['cases']:
        try:
            result=candidate.diagnose(corpus,plan,case['observations'])
            rows.append({'case':case['case'],'result':result})
        except Exception as error:
            rows.append({'case':case['case'],'error':type(error).__name__,'message':str(error)})
    if candidate_path.read_bytes()!=raw: raise ValueError('CANDIDATE_CHANGED_DURING_EXECUTION')
    with output_path.open('x') as stream: json.dump({'candidate_sha256':expected,'results':rows},stream,sort_keys=True,allow_nan=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--expected-candidate-sha256',required=True);a=p.parse_args();main(a.candidate.resolve(),a.input.resolve(),a.output.resolve(),a.expected_candidate_sha256)
