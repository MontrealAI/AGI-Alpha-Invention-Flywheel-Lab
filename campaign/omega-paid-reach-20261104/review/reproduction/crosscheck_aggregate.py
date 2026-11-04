"""Compare the independently reconstructed account state with the public study export."""
from pathlib import Path
import argparse
import hashlib
import json
p=argparse.ArgumentParser()
p.add_argument('first',type=Path)
p.add_argument('public',type=Path)
p.add_argument('output',type=Path)
args=p.parse_args()
a=json.loads(args.first.read_bytes())
b=json.loads(args.public.read_bytes())
canon={'collections':'collections','recognized_revenue':'revenue','incurred_expenses_including_tax':'expenses','cash_expenses_paid':'expensePaid','profit_after_modeled_tax':'profit','recovery_income':'recoveryIncome','cash':'cash','available_cash':'available','available_earned_cash':'unrestrictedEarned','payables':'payables','tail_reserve':'tailReserve','working_capital':'workingCapital','custody_restricted':'custodyRestricted','custody_reserve':'custodyReserve','reserved_investment':'reservedInvestment'}
checks=0
def same(lhs,rhs,context):
    global checks
    if lhs!=rhs:
        raise ValueError(f'{context}: {lhs!r} != {rhs!r}')
    checks+=1
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
same(a['accepted'],True,'auditor completion')
same(a['accounts'],10,'count')
same(a['source_sha256'],b['shared_design_and_prefix']['source_sha256'],'source')
same(set(a['paired_results']),set(b['pairs']),'environments')
for world,x in a['paired_results'].items():
    y=b['pairs'][world]
    same(x['pilot_minus_organic_after_tax_microUSD'],y['comparison']['pilot_minus_organic_financial_microUSD']['profit_after_modeled_tax'],world+' profit delta')
    same(x['pilot_minus_organic_settled_baskets'],y['comparison']['pilot_minus_organic_counts']['settled_baskets'],world+' basket delta')
    for arm in ('organic','pilot'):
        m=x['accounts'][arm];n=y[arm];r=n['reach_and_work'];k=world+'/'+arm
        same({key+'.json':v for key,v in m['public_file_sha256'].items()},n['artifact_file_sha256'],k+' file identities')
        same(m['native_events'],n['audited_native_action_count'],k+' event coverage')
        same(set(canon),set(n['financial_microUSD']),k+' economic field names')
        for key,raw in canon.items(): same(m['complete_native_financial_microUSD'][raw],n['financial_microUSD'][key],k+' '+key)
        same({key:v for key,v in r['status_counts'].items() if v},m['buyer_and_work_checks']['status'],k+' contact outcomes')
        same(m['buyer_and_work_checks']['unique_settled_buyers'],r['unique_settled_buyers'],k+' settled buyers')
        same(m['buyer_and_work_checks']['repeat_settled_buyers'],r['repeat_settled_buyers'],k+' repeat buyers')
        same(m['paid_reach']['raw_paid_exposures'],r['paid_exposures'],k+' paid reach')
        same(m['paid_reach']['distinct_exposed_buyers'],r['unique_paid_exposed_buyers'],k+' distinct reached buyers')
        same(m['paid_reach']['same_day_deduplications'],r['same_day_organic_paid_overlaps'],k+' overlap')
        for t,u in zip(m['tranches'],n['tranches'],strict=True):
            same(t['day'],u['day'],k+' decision day')
            same(t['decision'],u['action'],k+' decision')
            same(t['earned_microUSD'],u['earned_before_microUSD'],k+' eligible funding')
            same(t['expected_net_microUSD'],u['expected_net_microUSD'],k+' ex ante valuation')
with args.output.open('x') as f:
    json.dump({'accepted':True,'checks':checks,'accounts':10,'independent_audit_sha256':sha(args.first),'aggregate_sha256':sha(args.public),'scope':'Cross-comparison of all fifteen financial fields, order counts, exposure/overlap, both decisions and all five within-environment deltas.'},f,indent=2,sort_keys=True);f.write('\n')
print('accepted',checks,'checks')
