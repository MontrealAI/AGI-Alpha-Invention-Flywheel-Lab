import argparse, hashlib, importlib.util, json, sys, time
from pathlib import Path

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def main(root,corpus_path,plan_path,output):
    output.mkdir(parents=True,exist_ok=False)
    checker_path=root/'verification/next009/verify.py'
    candidate_path=root/'inventions/measurement009/compiler.py'
    checker_raw=checker_path.read_bytes();candidate_raw=candidate_path.read_bytes()
    checker=load(checker_path,'independent_checker_probe')
    candidate=load(candidate_path,'candidate_runtime_probe')
    corpus,corpus_raw=checker.read(corpus_path);plan,plan_raw=checker.read(plan_path)
    data=checker.corpus_values(corpus)
    selected=[corpus['nodes'].index(s) for s in plan['sensors']]
    cases=checker.protected_cases(data,corpus['nodes'],corpus['sources'],selected,checker.exact('1'),1,8,'EXPOSED-DEVELOPMENT-BOUNDARY-NOT-CONFIRMATION')
    failures=[];results=[]
    for case in cases:
        observations={'trace':case['observations'],'reference':case['reference'],'outages':case['erased'],'known_zero_valid':True,'offset_constant':True}
        try:
            result=candidate.diagnose(corpus,plan,observations)
            passed=result['status']=='UNIQUE' and result['sources']==[case['true_source']]
        except Exception as error:
            result={'error':type(error).__name__,'message':str(error)};passed=False
        results.append({'case':case['case'],'true_source':case['true_source'],'candidate_result':result,'independent_compatible':case['compatible'],'passed':passed})
        if not passed: failures.append({'case':case,'candidate_result':result,'candidate_observations':observations})
    if candidate_path.read_bytes()!=candidate_raw or checker_path.read_bytes()!=checker_raw: raise ValueError('SOURCE_CHANGED_DURING_PROBE')
    report={'schema':'agi-alpha/next009-independent-runtime-development/v1','scope':'Exposed development probe, not protected confirmation. Candidate is called as tested object; expected truth/observations come from independent rational checker.','candidate_sha256':hashlib.sha256(candidate_raw).hexdigest(),'checker_sha256':hashlib.sha256(checker_raw).hexdigest(),'artifact_sha256':hashlib.sha256(plan_raw).hexdigest(),'cases':len(cases),'passed':sum(r['passed'] for r in results),'failed':len(failures),'results':results}
    (output/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    (output/'COUNTEREXAMPLES.json').write_text(json.dumps(failures,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('cases','passed','failed','candidate_sha256')}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--corpus',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.root.resolve(),a.corpus.resolve(),a.plan.resolve(),a.output.resolve())
