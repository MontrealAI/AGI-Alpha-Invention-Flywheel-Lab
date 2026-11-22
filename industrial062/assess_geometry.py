import json,importlib.util,argparse
from pathlib import Path

root=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--output',default=str(root/'geometry-upper-bounds.json'));a=p.parse_args()
spec=importlib.util.spec_from_file_location('source_delivery',root/'inputs/15_network_direct/_network_delivery.py');client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
rows=[]
for task in ['14_network_tiered','15_network_direct','16_network_mixed']:
    d=json.loads((root/'inputs'/task/'01.json').read_text());nodes=list(d['regional_centers'])+(list(d['factories'])+list(d['central_warehouses']) if d['variant']=='direct' else []);total=d['totals']['demand_pieces'];bounds={}
    for multiplier in [1,1.01,1.05,1.1]:
        count=0
        for customer,record in d['customers'].items():
            for product,quantity in record['demand'].items():
                distances=[]
                for node in nodes:
                    if node in d['factories'] and product not in d['factories'][node]['products']:continue
                    km=client.delivery_distance(d,node,customer) if d['variant']=='direct' else d['arcs']['node_to_customer']['distance_km'].get(node,{}).get(customer)
                    if km is not None:distances.append(km)
                if distances and min(distances)*multiplier<=d['service_distance_km']:count+=quantity
        bounds[str(multiplier)]={'covered_pieces_upper_bound':count,'total_pieces':total,'coverage_upper_bound':count/total}
    rows.append({'case':task,'capacity_relaxed_geometry_bound':bounds})
result={'scope':'Nearest-endpoint upper bound relaxing upstream reachability, capacities and all cost constraints; not necessarily attainable.10percent multiplier is an authored sensitivity, not calibrated real-world confidence. Base contracts/results unchanged.','rows':rows}
Path(a.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'cases':len(rows),'tiered_upper_at1_1':rows[0]['capacity_relaxed_geometry_bound']['1.1']['coverage_upper_bound']}))
