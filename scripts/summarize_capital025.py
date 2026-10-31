#!/usr/bin/env python3
"""Strict compact membership/accounting check, not independent ledger replay."""
import argparse,hashlib,itertools,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from commercial.ledger import digest
from connected_enterprise.runner import identity
CAMPAIGN='capital025'
if CAMPAIGN=='capital025':
    from run_capital025 import PROTOCOL,config
    RUNNER='run_capital025.py'
    EXPECTED={(stage,capital,seed,policy,liability) for stage in ('integration','long') for capital,seed,policy,liability in itertools.product(PROTOCOL[stage]['capitals'],PROTOCOL[stage]['seeds'],PROTOCOL['policies'],PROTOCOL['liabilities'])}
    def key(r):return tuple(r[k] for k in ('stage','capital','seed','policy','liability'))
    def expected_config(k):return config(k[0],k[1],k[3],k[4])
else:
    from run_strategic025_ablation import PROTOCOL,config
    RUNNER='run_strategic025_ablation.py'
    EXPECTED={(arm,) for arm in PROTOCOL['arms']}
    def key(r):return (r['arm'],)
    def expected_config(k):return config(k[0])

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
            if CAMPAIGN=='capital025' and r['policy_factory_sha256']!=hashlib.sha256((ROOT/'scripts/run_strategic024.py').read_bytes()).hexdigest():raise ValueError('POLICY_FACTORY_MISMATCH')
            s=r['summary']
            if any(type(s[x]) is not int for x in ('revenue','expenses','profit')) or s['revenue']-s['expenses']!=s['profit']:raise ValueError('PROFIT_IDENTITY_MISMATCH')
            if CAMPAIGN=='ablation025' and sum(r['expense_categories'].values())!=s['expenses']:raise ValueError('EXPENSE_CATEGORIES_MISMATCH')
            if CAMPAIGN=='capital025' and (r['inventory_count']!=296 or not isinstance(r['inventory_fingerprint'],str) or len(r['inventory_fingerprint'])!=64):raise ValueError('DECLARED_EQUAL_INVENTORY_REQUIRED')
            record.update(inventory_fingerprint=r.get('inventory_fingerprint'),summary=s,paid_jobs=r['paid_jobs'],conditional_gate=r.get('conditional_simulated_commercial_success',r.get('conditional_commercial_success')),capital_metrics=r.get('capital_metrics'),expense_categories=r.get('expense_categories'))
            rows[k]=record
        except (KeyError,ValueError,TypeError) as exc:
            record['validation_error']=str(exc);errors.append(record)
    missing=sorted(EXPECTED-seen)
    if missing:errors.append({'missing_worlds':missing})
    if CAMPAIGN=='capital025' and len({r['inventory_fingerprint'] for r in rows.values()})>1:errors.append('MATCHED_INVENTORY_CONTENT_DIFFERS')
    comparisons=[]
    if CAMPAIGN=='capital025':
        for stage,capital,seed in sorted({k[:3] for k in EXPECTED}):
            cell={p+'/'+l:rows.get((stage,capital,seed,p,l)) for p,l in itertools.product(PROTOCOL['policies'],PROTOCOL['liabilities'])}
            if all(cell.values()):
                profits={name:r['summary']['profit'] for name,r in cell.items()}
                comparisons.append({'stage':stage,'capital':capital,'seed':seed,'profits_microUSD':profits,'strategy_delta_by_package':{l:profits['joint/'+l]-profits['incumbent/'+l] for l in PROTOCOL['liabilities']},'package_delta_by_policy':{p:profits[p+'/prospective']-profits[p+'/permanent'] for p in PROTOCOL['policies']}})
    elif all(k in rows for k in EXPECTED):
        for first,second in [('original_incumbent','matched_incumbent'),('matched_incumbent','quote_only'),('quote_only','full_joint')]:
            comparisons.append({'from':first,'to':second,'profit_delta_microUSD':rows[(second,)]['summary']['profit']-rows[(first,)]['summary']['profit']})
    report={'campaign':CAMPAIGN,'status':'COMPLETE' if not errors else 'INCOMPLETE_OR_INVALID','expected_worlds':len(EXPECTED),'valid_worlds':len(rows),'checkout_commit':checkout,'source_sha256':source['sha256'],'runner_sha256':runnerhash,'protocol_sha256':digest(PROTOCOL),'errors':errors,'worlds':list(rows.values()),'comparisons':comparisons,'scope':'Conditional modeled native operating comparisons, not pooled business income, annualized scale, actual commerce, independently portable audit or complete measured host/model billing. Finite-liability packages differ in risk and costs. Exposed ablation is not fresh confirmation. Negative profit or policy regression is retained, not an execution failure.'}
    (a.output/'COMPARISON.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as out:out.write('## '+CAMPAIGN+'\n'+json.dumps({'status':report['status'],'valid_worlds':len(rows),'expected_worlds':len(EXPECTED),'comparisons':comparisons},indent=2)+'\n'+report['scope']+'\n')
    print(json.dumps({'status':report['status'],'valid_worlds':len(rows),'expected_worlds':len(EXPECTED)}))
    if errors:raise SystemExit(1)
if __name__=='__main__':main()
