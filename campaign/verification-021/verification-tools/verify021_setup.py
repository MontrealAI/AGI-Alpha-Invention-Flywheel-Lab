import hashlib,json,pathlib,shutil,sys
ROOT=pathlib.Path('/workspace/scratch/8ae627a67fcf/p0-native')
sys.path.insert(0,str(ROOT))
from connected_enterprise.runner import identity,source_paths
from connected_enterprise.finance import source_identity
DEST=ROOT/'campaign/verification-021-work/source'
PUBLIC=ROOT/'campaign/verification-021'
PUBLIC.mkdir(exist_ok=True)
expected='0a41cbe703772ddd831497fc094b0379f0eae99d4d24f9c62a40098e3aa3db4e'
assert identity(ROOT)['sha256']==expected
paths=set(source_paths(ROOT))
paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'tests').glob('*.py'))
paths.update(['campaign/native-capital-020/run_qualification.py',
 'campaign/native-capital-020/independent/test_ordinary_portable_upgrade.py',
 'campaign/native-capital-020/independent/test_maturity_funds_successor.py',
 'campaign/native-capital-020/independent/maturity_successor_protocol.json'])
for name in sorted(paths):
 target=DEST/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
(DEST/'campaign/native-capital-020/qualification').mkdir(exist_ok=True)
assert identity(DEST)==identity(ROOT)
failed=['campaign/native-capital-020/qualification/final-legacy.json',
        'campaign/native-capital-020/qualification/final-legacy.log',
        'campaign/native-capital-020/run_qualification.before-main-guard.py.txt',
        'campaign/native-capital-020/RESOURCES.json',
        'campaign/native-capital-020/HARD_STOP.json']
result={'candidate_commit':'fff440f64087ae1daa088e329f980c4827729b05',
 'source_identity':identity(ROOT),'financial_source':source_identity(ROOT),
 'copied_files':len(paths),'original_failed_evidence_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in failed},
 'prepared_test_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in paths if n.startswith('campaign/native-capital-020/')},
 'isolation':'Exact selected source bytes plus unchanged test files; evidence is written outside the original checkpoint.'}
(PUBLIC/'SOURCE_VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['source_identity','financial_source']},indent=2))
