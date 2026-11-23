"""P0-255: repair the observed bootstrap failure; run the same frozen cases once."""
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time
from owner_patch253 import git_blob_id
from owner_patch255 import patch_legacy_owner, static_gates

HERE = Path(__file__).resolve().parent
OWNER = 'ced6c1cb004887dcdafaea59a2976020be649f8e'
RESEARCH_PATCH_BLOB = '4d49b96ecc4569b310b74ed660aa3104ade2c273'
METHODS = [
    'tests.test_connected_operating_upgrade.OperatingUpgradeTests.test_forward_engine_only_upgrade_preserves_prior_transition_and_same_business',
    'tests.test_connected_operating_upgrade.OperatingUpgradeTests.test_second_transition_native_commit_crash_recovers_without_downgrade',
    'tests.p0254_sentinel.OwnerPatchNative254.test_second_preparation_does_not_execute_target_codec',
]

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def git_head(path):
    return subprocess.check_output(['git','rev-parse','HEAD'], cwd=path, text=True).strip()

def main():
    owner = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    expected_research = sys.argv[3]
    assert git_head(HERE) == expected_research
    assert git_head(owner) == OWNER
    assert git_blob_id((HERE/'owner_patch253.py').read_bytes()) == RESEARCH_PATCH_BLOB
    upgrades = owner/'connected_enterprise/upgrades.py'
    codec = owner/'connected_enterprise/transition_evidence.py'
    old = upgrades.read_bytes()
    assert git_blob_id(old) == '9866d004c412fc05c9f6292cf898307f177359df'
    assert git_blob_id(codec.read_bytes()) == '2397091ef8e1960ad13950693d5b3cd04e2ff7c5'
    manifest_bytes = (owner/'historical/successor022/MANIFEST.json').read_bytes()
    patch = patch_legacy_owner(old, codec.read_bytes(), manifest_bytes)
    gates = static_gates(old, codec.read_bytes(), manifest_bytes, patch)
    upgrades.write_bytes(patch)
    witness = owner/'tests/p0254_sentinel.py'
    assert not witness.exists()
    shutil.copyfile(HERE/'test_native254_sentinel.py', witness)
    old_tests = owner/'tests/test_connected_operating_upgrade.py'
    old_test_sha = sha(old_tests.read_bytes())
    manifest = json.loads((owner/'historical/successor022/MANIFEST.json').read_text())
    legacy = manifest['versions']['9facd934d9ae763691e8a51052a67793cac5b48e']['files']
    out.mkdir(parents=True, exist_ok=False)
    private = out.parent/'p0255-private'
    private.mkdir(mode=0o700)
    results = []
    for i, method in enumerate(METHODS if all(g['accepted'] for g in gates) else []):
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.monotonic()
        log = private/f'case-{i}.log'
        case_tmp = private/f'case-{i}'
        case_tmp.mkdir(mode=0o700)
        env = {'PATH':os.environ['PATH'], 'HOME':str(private), 'TMPDIR':str(case_tmp),
               'PYTHONDONTWRITEBYTECODE':'1', 'PYTHONPATH':str(owner)}
        with log.open('wb') as stream:
            p = subprocess.run([sys.executable,'-B','-m','unittest','-v',method],
                               cwd=owner, env=env, stdout=stream, stderr=subprocess.STDOUT)
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        raw = log.read_bytes()
        # Never print or upload native logs, account files, signatures or key bytes.
        known = [token for token in (
            'SOURCE_UPGRADE_AUTHORIZATION_FAILED','ModuleNotFoundError',
            'No module named \'connected_enterprise.transition_evidence\'',
            'TARGET_CODEC_SIDE_EFFECT','OPERATING_SOURCE_AUTHORITY_CHANGED',
            'TimeoutExpired','AssertionError','SIGNATURE_MISMATCH',
            'OWNER_CODECLESS_LEGACY_INVENTORY_CHANGED','OWNER_HISTORICAL_CODEC_CHANGED',
            'NameError','UnboundLocalError','SyntaxError'
        ) if token.encode() in raw]
        result = {'method':method, 'exit':p.returncode,
                  'wall_seconds':time.monotonic()-start,
                  'waited_child_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
                  'private_log_sha256':sha(raw), 'diagnostic_markers':known}
        results.append(result)
        print(json.dumps(result, sort_keys=True), flush=True)
    assert sha(old_tests.read_bytes()) == old_test_sha
    assert upgrades.read_bytes() == patch
    receipt = {'schema':'agi-alpha/p0-255-native-bootstrap-trial/v1',
               'prior_failed_run':45257570305,'static_gates':gates,
               'patch_generator_sha256':sha((HERE/'owner_patch255.py').read_bytes()),
               'research_commit':expected_research,'owner_commit':OWNER,
               'patch_sha256':sha(patch),'owner_tests_sha256':old_test_sha,
               'witness_sha256':sha(witness.read_bytes()),
               'legacy_codec_present': 'connected_enterprise/transition_evidence.py' in legacy,
               'cases':results,'accepted':all(g['accepted'] for g in gates) and len(results)==len(METHODS) and all(x['exit']==0 for x in results),
               'scope':'isolated fresh simulated native accounts only',
               'original_account_accessed':False,'owner_branch_modified':False,
               'whole_episode_billing_usd':None,'actual_commerce_qualified':False}
    (out/'RESULT.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    # Only the compact receipt leaves this job. No state, log, or key upload.
    return 0 if receipt['accepted'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
