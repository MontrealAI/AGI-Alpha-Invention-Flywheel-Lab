import hashlib, json, os, subprocess, sys, tempfile
from pathlib import Path

SOURCE_BLOB='9866d004c412fc05c9f6292cf898307f177359df'
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(v):return hashlib.sha256(canonical(v)).hexdigest()
def source_inventory(root):
    root=Path(root).absolute();files={}
    for path in sorted(root.rglob('*.py')):
        rel=path.relative_to(root)
        if any(p in {'__pycache__','.git','.venv','historical-source-versions'} for p in rel.parts):continue
        files[rel.as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    return files

def synthetic_ticket_body(ticket):
    if set(ticket)!={'body','signature'}:raise ValueError('EXACT_SOURCE_TRANSITION_AUTHORIZATION_REQUIRED')
    return ticket['body']

def synthetic_verify_historical(ticket,manifest):
    body=synthetic_ticket_body(ticket)
    root=Path(body['historical_root']).absolute()
    if not root.is_dir() or source_inventory(root)!=body['verifier_files']:
        raise ValueError('PINNED_HISTORICAL_VERIFIER_CHANGED')
    payload={'record':body['prior_record'],'manifest':manifest,'root':str(root),'evidence_dir':None}
    code='''import json,sys,contextlib,importlib.util\nfrom connected_enterprise.finance import audit_journal\np=json.load(sys.stdin);scope=contextlib.nullcontext()\nwith scope:\n r=audit_journal(p['record'],root=p['root'],manifest=p['manifest'])\n assert r['accepted'];print(json.dumps(r,sort_keys=True))\n'''
    env={**os.environ,'PYTHONPATH':str(root),'PYTHONDONTWRITEBYTECODE':'1'}
    done=subprocess.run([sys.executable,'-c',code],input=json.dumps(payload),text=True,capture_output=True,cwd=root,env=env,timeout=10)
    if done.returncode:raise ValueError('PINNED_HISTORICAL_AUDIT_FAILED:'+done.stderr[-1200:])
    receipt=json.loads(done.stdout)
    if not receipt.get('accepted'):raise ValueError('PINNED_HISTORICAL_AUDIT_NOT_ACCEPTED')
    if source_inventory(root)!=body['verifier_files']:raise ValueError('HISTORICAL_VERIFIER_CHANGED_DURING_AUDIT')
    return receipt

def main():
    with tempfile.TemporaryDirectory(prefix='synthetic-public-verifier-boundary-') as td:
        root=Path(td)/'untrusted-historical-source'
        pkg=root/'connected_enterprise';pkg.mkdir(parents=True)
        marker=Path(td)/'synthetic-import-observed'
        (pkg/'finance.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').write_text("synthetic-marker-only")\ndef audit_journal(record,root,manifest):return {"accepted":True,"synthetic_only":True}\n')
        ticket={'body':{'historical_root':str(root),'verifier_files':source_inventory(root),'prior_record':{'synthetic':True}},'signature':'0'*64}
        receipt=synthetic_verify_historical(ticket,{'synthetic':True})
        result={'schema':'agi-alpha/keyfree-public-historical-verifier-synthetic-probe/v1','exact_reviewed_upgrades_git_blob':SOURCE_BLOB,'scope':'ISOLATED_MOCK_BOUNDARY_NOT_REAL_FINANCIAL_ACCOUNT','ticket_signature_verified':False,'self_consistent_source_inventory':True,'historical_python_import_executed':marker.read_text()=='synthetic-marker-only' if marker.exists() else False,'synthetic_audit_accepted':receipt.get('accepted') is True,'real_account_or_keys_touched':False,'verdict':'UNTRUSTED_CODE_EXECUTION_PRIMITIVE_REPRODUCED_IN_SYNTHETIC_ANALOGUE'}
        assert result['historical_python_import_executed'] and result['synthetic_audit_accepted']
        print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
