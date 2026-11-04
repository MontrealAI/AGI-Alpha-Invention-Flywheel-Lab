"""Call archived read-only finance replay on the originally recorded export and source."""
import concurrent.futures, hashlib, json, os, pathlib, subprocess, sys
root=pathlib.Path(__file__).resolve().parent
data=json.loads((root/'HISTORICAL_ACCOUNT_INITIALIZATION.json').read_bytes())
paid=json.loads((root/'REACH_PAIRED_EVIDENCE.json').read_bytes())
script="""
import contextlib,hashlib,io,json,sys
from pathlib import Path
from commercial.ledger import digest,strict_json
p=Path(sys.argv[1]);r=strict_json((p/'REPORT.json').read_bytes());e=strict_json((p/'NATIVE_EXPORT.json').read_bytes())
with contextlib.redirect_stdout(io.StringIO()):
 if sys.argv[2]=='paid':
  from mechanism_harness.reach_native import audit
  audit_receipt=audit(p); h=digest(audit_receipt)
  assert audit_receipt['accepted'] and audit_receipt['report_sha256']==digest(r) and audit_receipt['native_export_sha256']==digest(e)
  assert h==sys.argv[3]
 else:
  from connected_enterprise.finance import audit_journal
  audit_receipt=audit_journal(e,root=p/'runtime',manifest=strict_json((p/'MANIFEST.json').read_bytes()));h=digest(audit_receipt)
  assert audit_receipt==r['native_audit'] and audit_receipt['accepted'] and audit_receipt['connected_native_actions_covered']==len(e['ledger']['actions'])
print(h)
"""
out=root/'historical-portable-audits';out.mkdir(mode=0o700,exist_ok=False)
def run(v):
 k,row=v;a,w=row['arm'],row['environment']
 where={'original':'archive-source-f1074b1','corrected':'final-source-c6ddb25','paid':'reach-source-9187e8f'}[k]
 if k=='paid': acc=root/'reach-confirmation-accounts'/w/a
 else: acc=root/(('cart-' if k=='original' else 'cart-repaired-')+('diagnostics' if w in ('failed_acceptance','payment_failure') else 'runs'))/(a+'-'+w)
 if subprocess.check_output(['git','rev-parse','HEAD'],cwd=root/where,text=True).strip()!=data['comparisons'][k]['runtime_commit']: raise ValueError('WRONG_ARCHIVED_AUDIT_SOURCE')
 expected=paid['pairs'][w][a]['audit_receipt_sha256'] if k=='paid' else ''
 result=subprocess.run([sys.executable,'-B','-c',script,str(acc),k,expected],capture_output=True,text=True,cwd=root/where,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'})
 with (out/(k+'-'+a+'-'+w+'.log')).open('x') as log:log.write(result.stdout+result.stderr)
 h=result.stdout.strip()
 assert result.returncode==0 and len(h)==64,(k,a,w,result.returncode,result.stderr.splitlines()[-1:] if result.stderr else '')
 return {'cohort':k,'arm':a,'environment':w,'canonical_audit_sha256':h,'bound_published_report_or_receipt':True}
all_rows=[(k,r) for k,g in data['comparisons'].items() for r in g['accounts']]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex: rows=list(ex.map(run,all_rows))
with (out/'COMPLETE.json').open('x') as f:json.dump(rows,f,sort_keys=True)
print('Matched',len(rows),'canonical audit receipts')
