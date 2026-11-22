import argparse, hashlib, json
from fractions import Fraction
from pathlib import Path

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def money(value):
    if value is not None and (type(value) is not int or value<0):raise ValueError('nonnegative integer microUSD or null required')
    return value

def frontier(spec):
    if spec.get('schema')!='agi-alpha/conditional-economic-frontier008/v1':raise ValueError('schema')
    n=spec['admitted_inputs']
    if type(n) is not int or not 1<=n<=100000:raise ValueError('prospective cohort size')
    prices=spec['price_microUSD'];qs=spec['participation_fractions'];accept=Fraction(spec['acceptance_fraction']);refund=Fraction(spec['refund_fraction'])
    if not 0<=accept<=1 or not 0<=refund<=1:raise ValueError('fraction')
    costs=spec['costs_microUSD'];measured=sum(money(v) or 0 for v in costs.values());unknown=[k for k,v in costs.items() if v is None]
    rows=[]
    for p in prices:
        money(p)
        for raw in qs:
            q=Fraction(raw)
            if not 0<=q<=1:raise ValueError('participation')
            collections=n*q*accept*(1-refund)*p
            ceiling=collections-measured
            rows.append({'price_microUSD':p,'participation_fraction':str(q),'conditional_net_collection_microUSD':str(collections),'known_cost_microUSD':measured,'unknown_lifecycle_cost_ceiling_for_positive_profit_microUSD':str(ceiling),'complete_profit_microUSD':None if unknown else str(ceiling),'positive_complete_profit_established':not unknown and ceiling>0})
    if not any(Fraction(q)==0 for q in qs):raise ValueError('zero-participation case required')
    if spec.get('minimum_positive_demand_independently_established') is not False:raise ValueError('demand not established')
    return {'schema':'agi-alpha/economic-frontier008-result/v1','input_sha256':hashlib.sha256(canonical(spec)).hexdigest(),'scope':'conditional sensitivity, not calibrated market probabilities or commercial validation','admitted_inputs':n,'same_cohort_qualified_baseline_complete_profit':spec.get('baseline_complete_profit_microUSD'),'unknown_cost_categories':unknown,'rows':rows,'robust_positive_profit':'NOT_ESTABLISHED','negative_to_positive_complete_cost_profit':'UNKNOWN','unrestricted_commercial_earned_microUSD':0,'earned_successor_funding':'DEFER_NO_QUALIFIED_EARNINGS','reason':'Zero participation is permitted by evidence; unknown costs are not zero and no exact offering price/buyer demand has been observed.'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);args=ap.parse_args()
    raw=Path(args.input).read_bytes();spec=json.loads(raw);result=frontier(spec);result['input_file_sha256']=hashlib.sha256(raw).hexdigest();result['source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with Path(args.output).open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:result[k] for k in ['robust_positive_profit','negative_to_positive_complete_cost_profit','earned_successor_funding','unknown_cost_categories']}))
if __name__=='__main__':main()
