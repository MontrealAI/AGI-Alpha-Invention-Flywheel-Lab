import argparse,sys,json,hashlib
from pathlib import Path
from fractions import Fraction

p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--output',required=True);p.add_argument('--distance-margin',type=float,default=0);a=p.parse_args()
root=Path(__file__).resolve().parent;folder=root/'inputs'/a.case;out=Path(a.output);sys.path.insert(0,str(folder))
import _network_engine as client
d=json.loads((folder/'01.json').read_text());solution=json.loads((out/'solution.json').read_text())
if d['variant']=='mixed':
    from _network_mixed import prepare_mixed
    d=prepare_mixed(d)
decisions,errors=client.parse_solution(solution,d);errors+=client.check_structure(decisions,d);errors+=client.check_balance(decisions,d)
metrics=client.evaluate(decisions,d);covered,total=client.service_coverage(decisions,d)
floor=Fraction(str(d['service_coverage_floor']))
if covered*floor.denominator<floor.numerator*total:errors.append(('H4','Distance service floor violated'))
robust_covered=None
if a.distance_margin:
    from _network_delivery import delivery_distance
    robust_covered=sum(q for (k,p,n),q in decisions.customer_service.items() if delivery_distance(d,n,k)*(1+a.distance_margin)<=d['service_distance_km'])
    if robust_covered*floor.denominator<floor.numerator*total:errors.append(('ADDITIONAL_ROBUST_CLAUSE','Distance envelope coverage floor violated'))
production=json.loads((out/'production.json').read_text());delta=metrics['total_cost']-production['objective_yuan']
if abs(delta)>0.1:errors.append(('ACCOUNTING','Producer objective differs from source client accounting'))
result={'additional_distance_margin':a.distance_margin,'additional_robust_covered_pieces':robust_covered,'accepted':not errors,'errors':errors,'metrics':metrics,'producer_cost_delta_yuan':delta,'solution_sha256':hashlib.sha256((out/'solution.json').read_bytes()).hexdigest(),'scope':'Unchanged public client rules/accounting in a separate process; no hidden expert comparison, external certification or commercial acceptance.'}
(out/'client-acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'accepted':not errors,'errors':errors[:4],'cost':metrics['total_cost'],'coverage':metrics['service_coverage'],'accounting_delta':delta}));sys.exit(bool(errors))
