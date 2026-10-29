import hashlib, importlib.util, json, pathlib, sys
import verify
candidate_path=pathlib.Path(sys.argv[1])
expected_sha=sys.argv[2]
if verify.sha_file(candidate_path)!=expected_sha:raise ValueError('candidate source mismatch')
spec=importlib.util.spec_from_file_location('frozen_candidate',candidate_path)
candidate=importlib.util.module_from_spec(spec);spec.loader.exec_module(candidate)
model=verify.protected_panel()[-1]['model']
original=candidate.legacy_screen(model)
repaired=candidate.screen(model)
old_errors=verify.compare(model,original)
new_errors=verify.compare(model,repaired)
assert old_errors and not new_errors
output=pathlib.Path(sys.argv[3]);output.mkdir(parents=True,exist_ok=False)
record={'schema':'agi-alpha-seeded-criticism-repair-v1','candidate_sha256':expected_sha,'verifier_spec_sha256':verify.SPEC_SHA,'case':model,'legacy_result':original,'repaired_result':repaired,'original_errors':old_errors,'repaired_errors':new_errors,'verdict':'Seeded naive singular-outage handling fails the unchanged independent DC specification; bridge guard repairs this failure. This is an engineering transition, not autonomous discovery, a historical inherited failure, novelty or commercial advantage.','exposure':'Verifier source viewed by builder before freeze; all evidence is development engineering and no fresh-confirmation claim is made.'}
(output/'criticism_repair.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
print(json.dumps({'original_errors':old_errors,'repaired_errors':new_errors}))
