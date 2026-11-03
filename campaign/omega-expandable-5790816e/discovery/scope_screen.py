"""Necessary scale conditions, never revenue or a new simulated account."""
import argparse
import ast
import hashlib
import json
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--registration',required=True)
p.add_argument('--output',required=True)
p.add_argument('--market-source')
a=p.parse_args(); raw=Path(a.registration).read_bytes(); r=json.loads(raw)
market_path=Path(a.market_source) if a.market_source else Path(a.registration).resolve().parents[2]/'omega/expansion_market.py'
market_raw=market_path.read_bytes()
price_rows=[node for node in ast.parse(market_raw).body if isinstance(node,ast.Assign)
            and any(isinstance(t,ast.Name) and t.id=='PRICES' for t in node.targets)]
if len(price_rows)!=1:raise ValueError('ONE_REGISTERED_PRICE_MENU_REQUIRED')
prices=ast.literal_eval(price_rows[0].value)
target=Decimal(3000000000); cfg=r['native_config']
audience=max(w['audience'] for w in r['worlds'].values())
rows=[]
for cents in prices:
    processing=(cents*cfg['payment_bps']+9999)//10000+cfg['payment_fixed_cents']
    net_before_tax=Decimal(cents-processing-sum(cfg['unit_costs_cents'].values()))/100
    net=net_before_tax*(1-Decimal(cfg['income_tax_bps'])/10000)
    minimum=int((target/net).quantize(Decimal(1),rounding=ROUND_CEILING))
    rows.append({'price_USD':str(Decimal(cents)/100),
        'audience_gross_upper_bound_USD':str(Decimal(audience*cents)/100),
        'best_declared_variable_after_tax_contribution_USD':str(net),
        'minimum_accepted_collections_ignoring_all_acquisition_failure_other_cost':minimum,
        'scale_multiple_of_registered_audience':str(Decimal(minimum)/audience)})
result={'scope':'NECESSARY_CONDITION_SCREEN_NOT_FINANCIAL_EXECUTION_OR_DEMAND',
    'registration_sha256':hashlib.sha256(raw).hexdigest(),
    'market_source_sha256':hashlib.sha256(market_raw).hexdigest(),
    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'target_rolling365_profit_USD':str(target),'registered_max_unique_audience':audience,
    'one_edition_sale_per_buyer':True,'rows':rows,
    'verdict':'Registered finite world cannot attain objective even before complete modeled costs',
    'not_inferred':['Real-world maximum audience','Demand forecast','Permission to increase audience silently',
                    'Qualified large-scale native operation','General impossibility of objective']}
Path(a.output).write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
print(json.dumps(result,sort_keys=True))
