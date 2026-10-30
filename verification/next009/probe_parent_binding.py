import argparse,hashlib,importlib.util,json,sys
from pathlib import Path

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main(root,output):
    output.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(root))
    candidate_path=root/'research/next009/successor.py';candidate_raw=candidate_path.read_bytes()
    spec=importlib.util.spec_from_file_location('successor_test_object',candidate_path);candidate=importlib.util.module_from_spec(spec);spec.loader.exec_module(candidate)
    paths={'plan':root/'evidence/next009/construction/networks-v2/artifacts/Net1/generated_plan.json','receipt':root/'evidence/next009/verification/net1-canonical-final-development/artifacts/ACCEPTANCE.json','verifier':root/'verification/next009/verify.py','protocol':root/'verification/next009/protocol.json'}
    expected={k:sha(p) for k,p in paths.items()}
    expected['candidate']=json.loads(paths['receipt'].read_text())['candidate_source_sha256']
    shadow=output/'shadow';instrument=shadow/'inventions/measurement009/compiler.py';instrument.parent.mkdir(parents=True)
    instrument.write_text("raise RuntimeError('unverified replacement instrument')\n")
    try:
        record=candidate.verified_parent(shadow,paths['plan'],paths['receipt'],paths['verifier'],paths['protocol'],expected)
        refused=False;outcome={'instrument':record['instrument'],'verification':record['verification'],'receipt_candidate_sha256':json.loads(paths['receipt'].read_text())['candidate_source_sha256']}
    except ValueError as error:
        refused=True;outcome={'error':str(error)}
    if candidate_path.read_bytes()!=candidate_raw:raise ValueError('CANDIDATE_CHANGED_DURING_PROBE')
    extra=[]
    for name,root_path,changes in [('legitimate_parent',root,{}),('forged_new_authority',shadow,{'candidate':sha(instrument)}),('wrong_expected_parent_hash',root,{'candidate':'0'*64})]:
        try:
            value=candidate.verified_parent(root_path,paths['plan'],paths['receipt'],paths['verifier'],paths['protocol'],{**expected,**changes})
            got=False;detail={'instrument':value['instrument']}
        except ValueError as error:got=True;detail={'error':str(error)}
        extra.append({'case':name,'refused':got,'passed':got==(name!='legitimate_parent'),'detail':detail})
    result={'schema':'agi-alpha/next009-parent-instrument-binding-adversary/v1','source_sha256':hashlib.sha256(candidate_raw).hexdigest(),'replacement_source_sha256':sha(instrument),'refused_unverified_instrument':refused,'outcome':outcome,'fresh_regressions':extra,'all_repair_checks_passed':refused and all(x['passed'] for x in extra),'scope':'Actual unchanged successor verified_parent tested against a verifier-owned shadow source root; no candidate or real parent file edited.'}
    (output/'REPORT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.root.resolve(),a.output.resolve())
