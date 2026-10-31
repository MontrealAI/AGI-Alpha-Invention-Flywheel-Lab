#!/usr/bin/env python3
"""Strict compact membership/accounting check, not independent ledger replay."""
import argparse,hashlib,itertools,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from commercial.ledger import digest
from connected_enterprise.runner import identity
CAMPAIGN='repeat028'
from run_repeat028 import PROTOCOL,config
RUNNER='run_repeat028.py'
EXPECTED={(stage,case,seed,arm) for stage in ('smoke','scale') for case,seed,arm in itertools.product(PROTOCOL[stage]['cases'],PROTOCOL[stage]['seeds'],PROTOCOL['arms'])}
def key(r):return tuple(r[k] for k in ('stage','case','seed','arm'))
def expected_config(k):return config(k[0],k[1],k[3])

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);errors=[];rows={};seen=set()
    checkout=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    source=identity(ROOT);runnerhash=hashlib.sha256((ROOT/'scripts'/RUNNER).read_bytes()).hexdigest()
    files=list(a.input.rglob('SUMMARY.json'))
    if len(files)>len(EXPECTED):errors.append('EXCESS_RECEIPTS')
    for f in files:
        record={'artifact':f.parent.name}
        try:
            if f.stat().st_size>4*1024*1024:raise ValueError('RECEIPT_SIZE_BOUND')
            r=json.loads(f.read_text());k=key(r);record.update(key=k,status=r.get('status'),error=r.get('error'))
            if k not in EXPECTED or k in seen:raise ValueError('UNEXPECTED_OR_DUPLICATE_WORLD')
            seen.add(k)
            if r['protocol']!=PROTOCOL or r['protocol_sha256']!=digest(PROTOCOL):raise ValueError('PROTOCOL_MISMATCH')
            if r['checkout_commit']!=checkout or r['runner_sha256']!=runnerhash:raise ValueError('EXECUTING_CHECKOUT_OR_RUNNER_MISMATCH')
            if r.get('workflow_run_id')!=os.environ.get('GITHUB_RUN_ID'):raise ValueError('WORKFLOW_RUN_MISMATCH')
            if r['status']!='COMPLETED':raise ValueError('INCOMPLETE_OR_FAILED_WORLD')
            cfg=expected_config(k)
            if r['config']!=cfg or r['config_sha256']!=digest(cfg):raise ValueError('CONFIG_MISMATCH')
            if r['source']!=source or not r['audit']['accepted'] or r['audit']['source_sha256']!=source['sha256']:raise ValueError('SOURCE_OR_AUDIT_MISMATCH')
            if r['inventory_count']!=104 or not isinstance(r['inventory_fingerprint'],str) or len(r['inventory_fingerprint'])!=64:raise ValueError('DECLARED_INVENTORY_REQUIRED')
            s=r['summary']
            if any(type(s[x]) is not int for x in ('revenue','expenses','profit')) or s['revenue']-s['expenses']!=s['profit']:raise ValueError('PROFIT_IDENTITY_MISMATCH')
            record.update(inventory_fingerprint=r['inventory_fingerprint'],summary=s,paid_jobs=r['paid_jobs'],conditional_gate=r.get('conditional_simulated_commercial_success',r.get('conditional_commercial_success')),capital_metrics=r.get('capital_metrics'),expense_categories=r.get('expense_categories'),outside_choice_counts=r.get('outside_choice_counts'),self_service_outcomes=r.get('self_service_outcomes'))
            rows[k]=record
        except (KeyError,ValueError,TypeError) as exc:
            record['validation_error']=str(exc);errors.append(record)
    missing=sorted(EXPECTED-seen)
    if missing:errors.append({'missing_worlds':missing})
    if len({r['inventory_fingerprint'] for r in rows.values()})>1:errors.append('INVENTORY_CONTENT_MISMATCH')
    comparisons=[]
    for stage,case,seed in sorted({k[:3] for k in EXPECTED}):
        left=rows.get((stage,case,seed,'one'));right=rows.get((stage,case,seed,'two'))
        if left and right:
            comparisons.append({'stage':stage,'case':case,'seed':seed,'one_profit_microUSD':left['summary']['profit'],'two_profit_microUSD':right['summary']['profit'],'profit_delta_microUSD':right['summary']['profit']-left['summary']['profit'],'one_paid':left['paid_jobs'],'two_paid':right['paid_jobs'],'one_gate':left['conditional_gate'],'two_gate':right['conditional_gate']})
    report={'campaign':CAMPAIGN,'status':'COMPLETE' if not errors else 'INCOMPLETE_OR_INVALID','expected_worlds':len(EXPECTED),'valid_worlds':len(rows),'checkout_commit':checkout,'source_sha256':source['sha256'],'runner_sha256':runnerhash,'protocol_sha256':digest(PROTOCOL),'errors':errors,'worlds':list(rows.values()),'comparisons':comparisons,'scope':'Conditional modeled native operating comparisons, not pooled business income, annualized scale, actual commerce, independently portable audit or complete measured host/model billing. Common production envelope avoids duplicate substituted direct-work charges; candidate extra planning and genuine critic/retrieval envelopes remain authored, not measured cost savings. Negative profit or policy regression is retained, not an execution failure.'}
    (a.output/'COMPARISON.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as out:out.write('## '+CAMPAIGN+'\n'+json.dumps({'status':report['status'],'valid_worlds':len(rows),'expected_worlds':len(EXPECTED),'comparisons':comparisons},indent=2)+'\n'+report['scope']+'\n')
    print(json.dumps({'status':report['status'],'valid_worlds':len(rows),'expected_worlds':len(EXPECTED)}))
    if errors:raise SystemExit(1)
if __name__=='__main__':main()
