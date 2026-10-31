#!/usr/bin/env python3
"""Strict compact membership/accounting check, not independent ledger replay."""
import argparse,hashlib,itertools,json,os,subprocess,sys,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from commercial.ledger import digest
from connected_enterprise.runner import identity
CAMPAIGN='complete_offer032'
from run_complete_offer032 import PROTOCOL,config
RUNNER='run_complete_offer032.py'
EXPECTED={(stage,case,seed,arm) for stage in ('smoke','scale') for case,seed,arm in itertools.product(PROTOCOL[stage]['cases'],PROTOCOL[stage]['seeds'],PROTOCOL['arms'])}
def key(r):return tuple(r[k] for k in ('stage','case','seed','arm'))
def expected_config(k,jobs):return config(k[0],k[1],k[3],jobs)

def main():
    if PROTOCOL['status']!='FROZEN':raise ValueError('UNFROZEN_PROTOCOL')
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
            cfg=expected_config(k,r['request_inventory'])
            if r['config']!=cfg or r['config_sha256']!=digest(cfg):raise ValueError('CONFIG_MISMATCH')
            if r['policy_factory_sha256']!=hashlib.sha256((ROOT/'scripts/run_commoncost026.py').read_bytes()).hexdigest():raise ValueError('POLICY_FACTORY_MISMATCH')
            if r['optional_cash_diagnostic_status']!='UNAVAILABLE_NOT_REQUESTED':raise ValueError('DIAGNOSTIC_SCOPE_MISMATCH')
            if r['trailing_profit']['trailing_365_day_profit_microUSD'] is not None:raise ValueError('SHORT_HORIZON_ANNUAL_PROFIT_CLAIM')
            cpu=r['kernel_cpu'];keys=('self_user','self_system','children_user','children_system')
            if any(type(cpu[k]) not in (int,float) or not math.isfinite(cpu[k]) or cpu[k]<0 for k in (*keys,'total_cpu_seconds')) or abs(sum(cpu[k] for k in keys)-cpu['total_cpu_seconds'])>1e-6:raise ValueError('KERNEL_CPU_IDENTITY')
            if set(r['phase_cpu'])!={'inventory','native_operation_and_observed_metrics','canonical_financial_operating_audit','compact_profit_and_outcome_observers'}:raise ValueError('PHASE_CPU_COVERAGE')
            for phase in r['phase_cpu'].values():
                if any(type(phase[k]) not in (int,float) or not math.isfinite(phase[k]) or phase[k]<0 for k in (*keys,'total_cpu_seconds')) or abs(sum(phase[k] for k in keys)-phase['total_cpu_seconds'])>1e-6:raise ValueError('PHASE_CPU_IDENTITY')
            if sum(v['total_cpu_seconds'] for v in r['phase_cpu'].values())>cpu['total_cpu_seconds']+1e-6:raise ValueError('PHASE_CPU_EXCEEDS_TOTAL')
            if r['source']!=source or not r['audit']['accepted'] or r['audit']['source_sha256']!=source['sha256']:raise ValueError('SOURCE_OR_AUDIT_MISMATCH')
            if r['inventory_count']!=392 or not isinstance(r['inventory_fingerprint'],str) or len(r['inventory_fingerprint'])!=64:raise ValueError('DECLARED_INVENTORY_REQUIRED')
            inventory=r['request_inventory']
            if len(inventory)!=392 or len({j['id'] for j in inventory})!=392 or any(set(j)!={'id','service_id'} for j in inventory):raise ValueError('EXACT_REQUEST_INVENTORY_REQUIRED')
            counts={service:sum(j['service_id']==service for j in inventory) for service in {'reconciliation','kpi_variance','evidence_matrix','operations_bundle','receivables_packet'}}
            if counts!={'reconciliation':96,'kpi_variance':96,'evidence_matrix':96,'operations_bundle':8,'receivables_packet':96}:raise ValueError('REQUEST_INVENTORY_SCOPE_CHANGED')
            s=r['summary']
            if any(type(s[x]) is not int for x in ('revenue','expenses','profit')) or type(s.get('recoveryIncome',0)) is not int or s['revenue']+s.get('recoveryIncome',0)-s['expenses']!=s['profit']:raise ValueError('PROFIT_IDENTITY_MISMATCH')
            record.update(request_inventory_sha256=digest(r['request_inventory']),orders=r.get('orders'),inventory_fingerprint=r['inventory_fingerprint'],summary=s,paid_jobs=r['paid_jobs'],conditional_gate=r.get('conditional_simulated_commercial_success',r.get('conditional_commercial_success')),capital_metrics=r.get('capital_metrics'),expense_categories=r.get('expense_categories'),productive_expansion=r.get('productive_expansion'),phase_cpu=r.get('phase_cpu'),kernel_cpu=r.get('kernel_cpu'),trailing_profit=r.get('trailing_profit'))
            rows[k]=record
        except (KeyError,ValueError,TypeError) as exc:
            record['validation_error']=str(exc);errors.append(record)
    missing=sorted(EXPECTED-seen)
    if missing:errors.append({'missing_worlds':missing})
    if len({r['inventory_fingerprint'] for r in rows.values()})>1:errors.append('INVENTORY_CONTENT_MISMATCH')
    if len({r['request_inventory_sha256'] for r in rows.values()})>1:errors.append('REQUEST_INVENTORY_CHANGED')
    comparisons=[]
    for stage,case,seed in sorted({k[:3] for k in EXPECTED}):
        left=rows.get((stage,case,seed,'restricted'));right=rows.get((stage,case,seed,'menu'))
        if left and right:
            comparisons.append({'stage':stage,'case':case,'seed':seed,'restricted_profit_microUSD':left['summary']['profit'],'menu_profit_microUSD':right['summary']['profit'],'profit_delta_microUSD':right['summary']['profit']-left['summary']['profit'],'restricted_paid':left['paid_jobs'],'menu_paid':right['paid_jobs'],'restricted_gate':left['conditional_gate'],'menu_gate':right['conditional_gate'],'additional_unmodeled_development_cost_break_even_microUSD':right['summary']['profit']-left['summary']['profit']})
    report={'campaign':CAMPAIGN,'status':'COMPLETE' if not errors else 'INCOMPLETE_OR_INVALID','expected_worlds':len(EXPECTED),'valid_worlds':len(rows),'checkout_commit':checkout,'source_sha256':source['sha256'],'runner_sha256':runnerhash,'protocol_sha256':digest(PROTOCOL),'errors':errors,'worlds':list(rows.values()),'comparisons':comparisons,'scope':'Conditional independent-outcome-value/native-offer comparisons, not pooled income, annualized scale or actual commerce. Same request inventory/market/capital; menu has explicit additional $50 development envelope. Human/AI/self-service outside prices, buyer effort/amortization and demand are uncertain authored hypotheses, not measured willingness to pay. Fixed no-bid evaluation costs remain incurred. Actual host/model billing unknown. Negative outcomes retained.'}
    (a.output/'COMPARISON.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as out:out.write('## '+CAMPAIGN+'\n'+json.dumps({'status':report['status'],'valid_worlds':len(rows),'expected_worlds':len(EXPECTED),'comparisons':comparisons},indent=2)+'\n'+report['scope']+'\n')
    print(json.dumps({'status':report['status'],'valid_worlds':len(rows),'expected_worlds':len(EXPECTED)}))
    if errors:raise SystemExit(1)
if __name__=='__main__':main()
