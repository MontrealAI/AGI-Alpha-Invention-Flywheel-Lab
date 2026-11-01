import argparse,sys,json,copy,hashlib
from pathlib import Path

root=Path(__file__).resolve().parent;p=argparse.ArgumentParser();p.add_argument('--deliveries-root',default=str(root));p.add_argument('--output',default=str(root/'robust-stress-accounting.json'));a=p.parse_args();deliveries=Path(a.deliveries_root)
folder=root/'inputs/15_network_direct';sys.path.insert(0,str(folder));import _network_engine as client
from _network_delivery import delivery_distance,delivery_transit_days
raw=json.loads((folder/'01.json').read_text());d=copy.deepcopy(raw);out=deliveries/'output-direct-robust10';solution=json.loads((out/'solution.json').read_text());decisions,errors=client.parse_solution(solution,raw)
for (customer,product,node),quantity in decisions.customer_service.items():
    d['arcs']['node_to_customer']['distance_km'].setdefault(node,{})[customer]=delivery_distance(raw,node,customer)*1.10
    d['arcs']['node_to_customer']['transit_days'].setdefault(node,{})[customer]=delivery_transit_days(raw,node,customer)*1.10
errors+=client.check_structure(decisions,d);errors+=client.check_balance(decisions,d);metrics=client.evaluate(decisions,d)
if metrics['service_coverage']<0.75:errors.append(('H4','Stress distance coverage failed'))
nominal=client.evaluate(decisions,raw);baseline=json.loads((root/'evidence/output-tiered-cp/production.json').read_text());lower=baseline['source_objective_lower_bound_yuan']
result={'schema':'industrial062/robust-complete-source-sensitivity/v1','accepted':not errors,'errors':errors,'scenario':'All used terminal distances AND terminal transit days increase10percent; other source costs/inputs unchanged. Authored deterministic stress, not calibrated uncertainty.','original_input_sha256':hashlib.sha256((folder/'01.json').read_bytes()).hexdigest(),'stressed_input_canonical_sha256':hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'metrics':metrics,'nominal_robust_plan_cost_yuan':nominal['total_cost'],'cost_increase_in_stress_yuan':metrics['total_cost']-nominal['total_cost'],'conservative_annual_implementation_plus_fee_headroom_yuan':lower-metrics['total_cost'],'comparison':'Worst-case direct-plan cost compared against lower bound for UNSTRESSED hierarchical cost; the latter also cannot attain75percent distance coverage underthis10percentstress. Source-model result only; no transition cost, actual road validation, agreement or vendor revenue.'}
Path(a.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'accepted':not errors,'cost':metrics['total_cost'],'coverage':metrics['service_coverage'],'headroom':result['conservative_annual_implementation_plus_fee_headroom_yuan']}));sys.exit(bool(errors))
