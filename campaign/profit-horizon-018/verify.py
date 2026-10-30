import argparse
import gzip
import hashlib
import json
from pathlib import Path


def sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def verify(path):
    output=json.loads((path/'RESULT.json').read_bytes())
    with gzip.open(path/'trajectories.json.gz','rb') as stream: records=json.load(stream)
    if len(records)!=480 or len(output['matrix'])!=480:raise ValueError('COMPLETE_PREDECLARED_GRID_REQUIRED')
    index={(r['family'],r['policy'],r['capital_cents'],r['run']['seed']):r for r in records}
    if len(index)!=480:raise ValueError('DUPLICATE_WORLD')
    grid={(f,p,c,s) for f in ['base','weak_demand','price_and_cost_shock','supply_constraint','channel_failure']
          for p in ['keyed_legacy','cash_contract','paid_distribution','adaptive_allocation','distribution_and_allocation','joint']
          for c in [2500000,25000000] for s in range(10001,10009)}
    if set(index)!=grid:raise ValueError('PREDECLARED_WORLD_GRID_MISMATCH')
    checked=0
    for audit in output['matrix']:
        entry=index[(audit['family'],audit['policy'],audit['starting_capital_cents'],audit['seed'])]
        run,c=entry['run'],entry['config']
        if sha(run)!=audit['run_sha256'] or sha(run['monthly'])!=audit['monthly_sha256'] or sha(c)!=run['config_sha256']:
            raise ValueError('IDENTITY_MISMATCH')
        previous_r=previous_c=previous_k=0
        contributions=[]; crossing=None; expected=[]
        for m in run['monthly']:
            r,cost,k=(m[t] for t in ['cumulative_recognized_revenue_cents','cumulative_cost_cents','cumulative_collected_revenue_cents'])
            contributions.append((r-previous_r)-(cost-previous_c))
            if m['cumulative_profit_cents']!=r-cost or m['cash_cents']!=c['opening_cash_cents']+k-cost:
                raise ValueError('INDEPENDENT_MONEY_IDENTITY_FAILURE')
            if m['cash_cents']-m['restricted_cash_cents']!=m['available_cash_cents']:
                raise ValueError('INDEPENDENT_AVAILABLE_CASH_FAILURE')
            if k-previous_k!=m['collected_revenue_cents']:raise ValueError('INDEPENDENT_RECEIPT_FAILURE')
            if len(contributions)>=12:
                annual=sum(contributions[-12:]);n=m['month']
                earlier=run['monthly'][n-13] if n>12 else None
                annual_cost=cost-(earlier['cumulative_cost_cents'] if earlier else 0)
                annual_collected=k-(earlier['cumulative_collected_revenue_cents'] if earlier else 0)
                expected.append({'end_month':n,'accrual_profit_cents':annual,
                    'recognized_revenue_cents':r-(earlier['cumulative_recognized_revenue_cents'] if earlier else 0),
                    'cost_cents':annual_cost,'collected_revenue_cents':annual_collected,
                    'net_collected_less_expenses_cents':annual_collected-annual_cost})
                if crossing is None and annual>=300_000_000_000:crossing=n
            previous_r,previous_c,previous_k=r,cost,k
        if expected!=audit['profit_periods'] or crossing!=audit['first_trailing_12_profit_crossing_month']:
            raise ValueError('INDEPENDENT_PERIOD_OR_FIRST_PASSAGE_MISMATCH')
        if audit['month60_period']!=next((r for r in expected if r['end_month']==60),None):
            raise ValueError('MONTH60_CENSORING_MISMATCH')
        delay=0 if run.get('intervention',{}).get('settlement')=='same_period' else max(1,c['settlement_months'])
        settled=sum(m['collected_projection_jobs'] for m in run['monthly'] if m['month']+delay<=len(run['monthly']))
        if audit['settled_projection_jobs_by_recorded_month']!=settled:raise ValueError('SETTLED_COUNT_MISMATCH')
        if run['cumulative_profit_cents']!=run['cumulative_collected_revenue_cents']+run['terminal_receivables_cents']-run['cumulative_cost_cents']:
            raise ValueError('INDEPENDENT_TERMINAL_ACCRUAL_FAILURE')
        checked+=1
    if output['first_crossing_count']!=sum(r['first_trailing_12_profit_crossing_month'] is not None for r in output['matrix']):
        raise ValueError('CROSSING_AGGREGATE_MISMATCH')
    if len(output['summary'])!=10:raise ValueError('COMPLETE_SUMMARY_REQUIRED')
    for summary in output['summary']:
        rs=[r for r in output['matrix'] if r['family']==summary['family'] and r['starting_capital_cents']==summary['capital_cents'] and r['policy']=='paid_distribution']
        values=[r['month60_period']['accrual_profit_cents'] for r in rs if r['month60_period'] is not None]
        if len(rs)!=8 or summary['completed_month60']!=len(values) or summary['survivors']!=sum(r['cash_survival'] for r in rs):
            raise ValueError('SUMMARY_FAILURE_CENSORING_MISMATCH')
        if summary['mean_month60_annual_profit_cents']!=(sum(values)/len(values) if values else None):
            raise ValueError('SUMMARY_MEAN_MISMATCH')
    return {'accepted':True,'worlds_checked':checked,'periods_checked':sum(len(r['profit_periods']) for r in output['matrix']),
            'scope':'INDEPENDENT_READ_ONLY_ACCOUNTING_CODE; same host and author, no external certification',
            'result_sha256':hashlib.sha256((path/'RESULT.json').read_bytes()).hexdigest(),
            'trajectories_sha256':hashlib.sha256((path/'trajectories.json.gz').read_bytes()).hexdigest()}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--result-directory',required=True,type=Path);p.add_argument('--receipt',required=True,type=Path)
    a=p.parse_args()
    if a.receipt.exists():raise ValueError('NEW_RECEIPT_REQUIRED')
    result=verify(a.result_directory)
    a.receipt.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
