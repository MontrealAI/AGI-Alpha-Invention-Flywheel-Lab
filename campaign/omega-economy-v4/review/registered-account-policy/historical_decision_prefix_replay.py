"""Reconstruct the archived V4 successor decision and paid prospect purchases from past data."""
import argparse, hashlib, json
from pathlib import Path

def dg(o): return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def read(p): return json.loads(p.read_bytes())
def check(x,msg):
    if not x: raise ValueError(msg)
def paid_dates(acc,export,arm):
    orders=read(acc/'ORDERS.json'); ds=read(acc/'PLAN.json')['decisions'];terms=read(acc/'CONTRACT.json')
    actions=export['ledger']['actions']; entries=export['connected_journal']['entries']
    decisions=[]; first=None
    for day,d in zip((90,118),ds,strict=True):
        pref=[a for a in actions if a['day']<day]
        bal=pref[-1]['after'];available=bal['available'];earned=bal['unrestrictedEarned']
        check(d['prefix']=={'sequence':len(pref),'actions_sha256':dg(pref),'available_microUSD':available,'earned_microUSD':earned},'STALE_PAID_PREFIX')
        warm=[r for r in orders if r['source']=='warm' and r['day']<day]
        n=sum(r['status']=='SETTLED' for r in warm)
        gross=sum(r['collections_microUSD']-r['fee_microUSD']-r['production_microUSD'] for r in warm)
        previous_paid=[r for r in orders if r['source']=='paid' and r['source_plan_id']==first and r['day']<day]
        exclusive=[r for r in previous_paid if int(r['buyer'][-3:])>=12 and r['status']=='SETTLED']
        at=sum(r['collections_microUSD'] for r in exclusive)-sum(r['quote_microUSD']+r['production_microUSD']+r['fee_microUSD'] for r in previous_paid)-(6_250_000 if first else 0)
        estimate=2*gross//n-6_250_000-42*100_000 if day==90 and n else at
        required=arm=='pilot' and n>0 and estimate>0 and earned>=6_250_000 and available>=18_250_000 and (day==90 or bool(first and exclusive))
        check(d['day']==day and d['policy']['expected_net_microUSD']==estimate and (d['policy']['action']=='BUY')==required,'WRONG_REQUIRED_CHANNEL_CHOICE')
        spends=[e for e in entries if e['request'].get('id')=='reach-pilot-'+('1' if day==90 else '2') and e['request']['operation']=='spend']
        check(len(spends)==int(required) and (d['funding'] is not None)==required and (d['purchase'] is not None)==required,'WRONG_CHANNEL_FINANCIAL_RECORD')
        if required:
            x=spends[0];check(x['request']['allow_seed'] is False and x['request']['amount']==6_250_000 and x['request']['day']==day and x['receipt']==d['funding'] and x['receipt']['funding']=='EARNED','WRONG_CHANNEL_FUNDING')
            if day==90:first=x['receipt']['plan_id']
        decisions.append({'day':day,'available_before_microUSD':available,'earned_before_microUSD':earned,'computed_expected_net_microUSD':estimate,'required_action':'BUY' if required else 'SKIP','actual_action':d['policy']['action']})
    return decisions
def inspect(root,cohort,row):
    arm,world=row['arm'],row['environment']
    if cohort=='paid': acc=root/'reach-confirmation-accounts'/world/arm
    else:acc=root/(('cart-' if cohort=='original' else 'cart-repaired-')+('diagnostics' if world in ('payment_failure','failed_acceptance') else 'runs'))/(arm+'-'+world)
    exp=read(acc/'NATIVE_EXPORT.json');r=read(acc/'REPORT.json');m=read(acc/'MANIFEST.json')
    check(hashlib.sha256((acc/'NATIVE_EXPORT.json').read_bytes()).hexdigest()==row['native_export_file_sha256'] and dg(r)==row['canonical_report_sha256'],'ARCHIVED_EXPORT_OR_REPORT_DRIFT')
    a=exp['ledger']['actions']; js=exp['connected_journal']['entries'];days=[x['day'] for x in a];jdays=[x['request']['day'] for x in js]
    for d in (days,jdays):
        check(all(type(v) is int and 0<=v<365 for v in d) and d==sorted(d) and d[0]==0 and d[-1]==364,'DAY_OUTSIDE_CLOSED_OR_DISORDERED_YEAR')
    prefix='reach-' if cohort=='paid' else 'v4-'
    ids=[prefix+'maintenance',prefix+'modeled-tax']
    indexes=[]
    for id_ in ids:
        hits=[i for i,x in enumerate(a) if x['op']=='cost' and x['args']['id']==id_]
        check(len(hits)==1 and a[hits[0]]['day']==364,'WRONG_YEAR_END_COST')
        indexes.append(hits[0])
    maintenance,tax=indexes
    check(maintenance+1==tax and a[maintenance]['args']['amount']==12_000_000,'WRONG_CLOSE_ORDER')
    state=a[tax]['after'];k={'arm':arm,'environment':world,'start_day':days[0],'last_day':days[-1],'closed_window_days':[0,365],
        'native_action_count':len(a),'complete_chronological_native_and_resource_journal_year':True,'annual_maintenance_and_tax_before_close':True}
    if cohort=='paid':
        check(tax==len(a)-1 and not any(e['request'].get('id')=='v4-successor' for e in js),'WRONG_PAID_YEAR_END')
        k['distribution_decisions']=paid_dates(acc,exp,arm);return k
    eligible=min(state['available'],state['unrestrictedEarned'])>=5_000_000 and not (m.get('native_engine') in ('prospective-v1','exact-prospective-v2') and state['investmentStopped'])
    suffix=a[tax+1:];entry=[e for e in js if e['request'].get('id')=='v4-successor'];suc=r['successor'];actual=suc is not None
    check(actual==eligible and (acc/'SUCCESSOR.json').exists()==eligible and len(entry)==int(eligible),'OMITTED_OR_UNSUPPORTED_SUCCESSOR')
    if eligible:
        funding=entry[0]['receipt'];q=entry[0]['request']
        check([(x['op'],x['args']['id'],x['args']['amount']) for x in suffix]==[('reserve',funding['plan_id'],5_000_000),('finish',funding['plan_id'],5_000_000)],'WRONG_SUCCESSOR_YEAR_END_TAPE')
        check(q['day']==364 and q['amount']==5_000_000 and q['kind']=='instrument' and q['expected_net']==1 and q['allow_seed'] is False and funding['funding']=='EARNED' and suc['funding']==funding,'WRONG_SUCCESSOR_FUNDING')
        check(suc==read(acc/'SUCCESSOR.json') and suc['verified'] and suc['productive_verification']['accepted'],'FUNDED_SUCCESSOR_MISSING_ACCEPTED_WORK')
    else:check(not suffix,'EXTRANEOUS_POST_TAX_ACTION')
    k.update(tax_microUSD=a[tax]['args']['amount'],decision_after_native_sequence=a[tax]['seq'],decision_prefix_actions_sha256=dg(a[:tax+1]),earned_before_microUSD=state['unrestrictedEarned'],
        available_before_microUSD=state['available'],native_investment_stopped=state['investmentStopped'],required_successor=eligible,actual_successor=actual,successor_spend_microUSD=5_000_000 if eligible else 0)
    return k
def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--audit-receipts',type=Path);p.add_argument('--output',required=True,type=Path)
    args=p.parse_args();data=read(args.root/'HISTORICAL_ACCOUNT_INITIALIZATION.json')
    result={labels:[inspect(args.root,labels,x) for x in data['comparisons'][labels]['accounts']] for labels in ('original','corrected','paid')}
    if args.audit_receipts:
        receipts=read(args.audit_receipts);check(len(receipts)==25,'INCOMPLETE_AUDIT_RECEIPTS')
        for cohort,rows in result.items():
            for row in rows:
                got=[r for r in receipts if (r['cohort'],r['arm'],r['environment'])==(cohort,row['arm'],row['environment'])]
                check(len(got)==1 and got[0]['bound_published_report_or_receipt'],'UNMATCHED_AUDIT_RECEIPT');row['canonical_audit_sha256']=got[0]['canonical_audit_sha256']
    record={'schema':'omega/historical-decision-and-close-replay/v1','accepted':True,'canonical_audit_rederived':bool(args.audit_receipts),'source_commits':{k:v['runtime_commit'] for k,v in data['comparisons'].items()},
        'scope':'Retrospective decision from actual dated native prefix, annual operating close and canonical public audit comparison. V4 has a mandatory earned-only $5 successor wherever its declared native funding gate permits. Paid-reach has different day-90 and day-118 supplier rules and no $5 successor. Every account remains independent. No signer read or existing writer opened.','account_count':25,'rejected_account_cases':[],'decision_reviewer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'accounts':result}
    with args.output.open('x') as f:json.dump(record,f,sort_keys=True,indent=2);f.write('\n')
    print({k:([sum(r['required_successor'] for r in v),len(v)] if k!='paid' else [sum(x['required_action']=='BUY' for r in v for x in r['distribution_decisions']),20]) for k,v in result.items()})
if __name__=='__main__':main()
