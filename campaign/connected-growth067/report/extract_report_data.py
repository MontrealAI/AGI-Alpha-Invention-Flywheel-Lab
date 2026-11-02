from pathlib import Path
import json, zipfile, hashlib, bisect, csv
from collections import defaultdict
from decimal import Decimal
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--artifact',type=Path,required=True)
parser.add_argument('--audit',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
ROOT=args.output;ROOT.mkdir(parents=True,exist_ok=True)
ZIP=args.artifact
with zipfile.ZipFile(ZIP) as z:
    r=json.loads(z.read('dev-100000-distribution_first/result.json'))
    e=json.loads(z.read('dev-100000-distribution_first/public-export.json'))
    package=json.loads(z.read('dev-100000-distribution_first/PACKAGE.json'))
audit=json.loads(args.audit.read_text())
actions=e['ledger']['actions']; END=43800; YEAR=8760
assert all(actions[i]['day']<=actions[i+1]['day'] for i in range(len(actions)-1))
hours=[a['day'] for a in actions]
def before(t):
    i=bisect.bisect_left(hours,t)-1
    return actions[i]['after'] if i>=0 else actions[0]['before']
times=sorted({0,END}|{h+1 for h in hours if h<END})
series=[]
for t in times:
    s=before(t)
    series.append(dict(hour=t,day=str(Decimal(t)/24),cash_microUSD=s['cash'],available_microUSD=s['available'],protected_microUSD=s['cash']-s['available'],tail_microUSD=s['tailReserve'],profit_microUSD=s['profit'],revenue_microUSD=s['revenue'],expenses_microUSD=s['expenses']))
rolltimes=sorted({YEAR,END}|{h+1 for h in hours if YEAR<=h+1<=END}|{h+YEAR+1 for h in hours if YEAR<=h+YEAR+1<=END})
rolling=[dict(hour=t,day=str(Decimal(t)/24),profit_microUSD=before(t)['profit']-before(t-YEAR)['profit']) for t in rolltimes]
assert rolling[-1]['profit_microUSD']==r['annual']['trailing_365_day_profit_microUSD']==16641713166780
assert series[-1]['profit_microUSD']==25261803108132
assert series[-1]['protected_microUSD']==7772556800000
stages=defaultdict(int)
vol=[]
cum=0; actual=0
for row in r['rows']:
    p=row['decision']['proposal']
    for kind,receipt in row['funding'].items():
        if receipt: stages[kind]+=p['costs_microUSD'][kind]
    cum+=p['collected_units']; actual+=int(row['actual_production'] is not None)
    vol.append(dict(month=p['month'],modeled_collected_units=p['collected_units'],modeled_cumulative_units=cum,actual_template_productions=int(row['actual_production'] is not None),actual_cumulative_productions=actual,quality_failed=p['quality_failed'],uncollected_units=p['uncollected_units'],chosen_orders=p['chosen_orders'],unit_price_usd=p['unit_price_usd']))
assert cum==r['modeled_collected_units']==765114
costs=dict(stages)
costs['setup']=audit['audit']['complete_cost_checks']['setup_microUSD']
costs['processing']=audit['audit']['complete_cost_checks']['processing_microUSD']
costs['tax']=audit['audit']['complete_cost_checks']['tax_paid_microUSD']
assert sum(costs.values())==r['summary']['expenses']==20635476891868
prod=[x['actual_production'] for x in r['rows'] if x['actual_production']]
data=dict(schema='agi-alpha/growth067-interim-report/v1',scope='SELECTED_COMPLETED_CONTROL_CASE_NOT_CAMPAIGN_RESULT',source=dict(run_id=41467872078,artifact_id=13157389058,zip_sha256=hashlib.sha256(ZIP.read_bytes()).hexdigest(),native_actions_sha256=e['ledger']['actions_sha256'],package=package,executed_source_commit='8d615b1e850f81838b7ff77f87fee8964bf1f280',preregistration_sha256='4bfb47a46e5bbd676bfd2ad24eaff5630b20883dd5b438cbbd564d3c1e32a088',source_files_independently_matched=68),configuration=r['configuration'],operating_end_hour=END,final_window=[35040,43800],sampling='Prefix before integer hour t; all same-hour actions atomic. Event changes at h+1, rolling expiries at h+8761. Plot steps, not interpolation. Plot dollars derive from integer microUSD.',series=series,rolling365=rolling,volume=vol,costs_microUSD=costs,operating_endpoint=before(END),post_drain_endpoint=r['summary'],settlement_drain_hour=r['settlement_drain_hour'],actual_template_productions=len(prod),unique_actual_input_hashes=len({x['input_sha256'] for x in prod}),unique_actual_output_hashes=len({x['output_sha256'] for x in prod}),modeled_collected_units=cum,modeled_chosen_orders=sum(x['chosen_orders'] for x in vol),modeled_quality_failed=sum(x['quality_failed'] for x in vol),modeled_uncollected=sum(x['uncollected_units'] for x in vol),growth_funding=audit['growth_funding'],attainment=r['attainment'],actual_model_billing=r['actual_model_billing'],opportunity_cost_sensitivity=r['opportunity_cost_sensitivity'])
(ROOT/'data.json').write_text(json.dumps(data,indent=2)+'\n')
(ROOT/'independent-replay.json').write_text(json.dumps(audit,indent=2)+'\n')
for name,rows in [('native-series.csv',series),('rolling365.csv',rolling),('volume.csv',vol)]:
    with (ROOT/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps({k:data[k] for k in ['actual_template_productions','unique_actual_input_hashes','unique_actual_output_hashes','modeled_collected_units','modeled_chosen_orders','modeled_quality_failed','modeled_uncollected','attainment','actual_model_billing','opportunity_cost_sensitivity']},indent=2))
print('rows',len(series),len(rolling),'costs',costs,'total',sum(costs.values()))
