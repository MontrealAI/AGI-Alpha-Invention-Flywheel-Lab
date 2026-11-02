"""Source-bound bulk SIM contract; sampled actual work is never multiplied evidence."""
from pathlib import Path
import hashlib
from commercial.ledger import canonical,digest,strict_json
from commercial.persistence import atomic_bytes
from .quality import make_case,HOLDOUT_SEEDS
from .acceptance import verify

SCHEMA='growth067/native-services/v1'

def source_paths(root):
    return sorted([p.relative_to(root).as_posix() for p in (Path(root)/'growth067').iterdir() if p.suffix in {'.py','.json'}] + ['growth066/'+n+'.py' for n in ['__init__','quality','producer','market','money','policy']])

def hashes(root):
    return {p:hashlib.sha256((Path(root)/p).read_bytes()).hexdigest() for p in source_paths(Path(root))}

def safe(root,path):
    p=Path(root)/path
    if Path(path).is_absolute() or '..' in Path(path).parts or any(q.is_symlink() for q in [p,*p.parents]):raise ValueError('REGULAR_SCOPED_GROWTH_PATH_REQUIRED')
    return p

def manifest(root,run_id,months,configuration=None):
    configuration=configuration or {'mode':'TECHNICAL_UNIT_TEST','unit_price_microUSD':20_000_000,'quantity_limit':3}
    m={'configuration':configuration,'schema':SCHEMA,'native_engine':'exact-prospective-v2','account_namespace':'adaptive012','source_hashes':hashes(root),'jobs':[{'id':f'{run_id}-m{i}','request':{'month':i,'unit':'merchant_month_receivables_close_preparation','actual_seed':HOLDOUT_SEEDS[i%len(HOLDOUT_SEEDS)],'representation':'SIMULATED_HOMOGENEOUS_BULK_NOT_INDIVIDUAL_RENDERING'},'delivery_path':f'growth067/deliveries/{run_id}-m{i}.json'} for i in range(months)]}
    load_contracts(root,m);return m

def load_contracts(root,m):
    if set(m)!={'configuration','schema','native_engine','account_namespace','source_hashes','jobs'} or m['schema']!=SCHEMA or m['native_engine']!='exact-prospective-v2' or m['account_namespace']!='adaptive012':raise ValueError('EXACT_GROWTH_MANIFEST_REQUIRED')
    cfg=m['configuration']
    from .registration import design
    reg=design()
    if cfg.get('mode')=='TECHNICAL_UNIT_TEST':
        if cfg!={'mode':'TECHNICAL_UNIT_TEST','unit_price_microUSD':20_000_000,'quantity_limit':3}:raise ValueError('EXACT_TECHNICAL_FIXTURE_REQUIRED')
    elif cfg.get('mode')=='ECONOMIC':
        if reg['status']!='FROZEN':raise ValueError('ECONOMIC_REGISTRATION_NOT_FROZEN')
        if set(cfg)!={'mode','world','seed','opening','unit_cost','grow','funding_mode','policy_name'} or cfg['world'] not in reg['worlds'] or cfg['seed'] not in reg['development_seeds']+reg['holdout_seeds'] or cfg['opening'] not in [x*1_000_000 for x in reg['capital_candidates_usd']] or cfg['unit_cost'] not in reg['resource_cases_usd'] or type(cfg['grow']) is not bool or cfg['funding_mode'] not in {'capital_available','earned_only'} or cfg['policy_name'] not in reg['allocation_policies']:raise ValueError('REGISTERED_MARKET_CONFIGURATION_REQUIRED')
    else:raise ValueError('DECLARED_GROWTH_MODE_REQUIRED')
    if m['source_hashes']!=hashes(root) or hashes(Path(__file__).resolve().parents[1])!=m['source_hashes']:raise ValueError('GROWTH_SOURCE_CHANGED')
    out={};paths=set()
    for row in m['jobs']:
        if set(row)!={'id','request','delivery_path'} or row['id'] in out or row['delivery_path'] in paths:raise ValueError('UNIQUE_GROWTH_JOB_REQUIRED')
        r=row['request']
        if set(r)!={'month','unit','actual_seed','representation'} or type(r['month']) is not int or r['month']<0 or r['actual_seed'] not in HOLDOUT_SEEDS or r['representation']!='SIMULATED_HOMOGENEOUS_BULK_NOT_INDIVIDUAL_RENDERING' or r['unit']!='merchant_month_receivables_close_preparation':raise ValueError('EXACT_BULK_REQUEST_REQUIRED')
        if not row['delivery_path'].startswith('growth067/deliveries/') or not row['delivery_path'].endswith('.json'):raise ValueError('GROWTH_OUTPUT_SCOPE')
        safe(root,row['delivery_path']);paths.add(row['delivery_path'])
        job={'id':row['id'],'artifact_sha256':digest(r),'receipt_sha256':m['source_hashes']['growth067/acceptance.py'],'request':r,'delivery_path':row['delivery_path']}
        out[row['id']]={'job':job,'artifact':{'request_sha256':digest(r)},'receipt':{'checker_sha256':job['receipt_sha256']}}
    return out

def delivery(root,m,job_id):
    j=load_contracts(root,m)[job_id]['job'];return strict_json(safe(root,j['delivery_path']).read_bytes())

def check_delivery(root,m,job_id,a):
    job=load_contracts(root,m)[job_id]['job'];r=job['request']
    required={'schema','request_sha256','actual_output','modeled_fulfillment_count','actual_template_count','empirical_per_unit_acceptance','market_receipt'}
    if not isinstance(a,dict) or set(a)!=required or a['schema']!='growth067/bulk-delivery/v1' or a['request_sha256']!=digest(r) or type(a['actual_template_count']) is not int or a['actual_template_count']!=1 or a['empirical_per_unit_acceptance'] is not False or type(a['modeled_fulfillment_count']) is not int or a['modeled_fulfillment_count']<=0:return {'accepted':False,'decisive':True,'scope':'SIMULATED','authority':job['receipt_sha256']}
    packet,truth=make_case(r['actual_seed']);q=verify(packet,a['actual_output'],truth)
    market=a['market_receipt'];count=a['modeled_fulfillment_count']
    valid=isinstance(market,dict) and type(market.get('production_capacity')) is int and type(market.get('chosen_orders')) is int and type(market.get('quality_accepted')) is int and type(market.get('collected_units')) is int and 0<count==market['collected_units']<=market['quality_accepted']<=market['chosen_orders']<=market['production_capacity']
    cfg=m['configuration']
    if cfg['mode']=='TECHNICAL_UNIT_TEST':
        valid=valid and count<=cfg['quantity_limit']
    else:
        decision=read_decision(root,m,job_id)
        valid=valid and market==decision['proposal'] and count==decision['proposal']['collected_units']
    return {'accepted':q['accepted'] and valid,'decisive':True,'scope':'SIMULATED_BULK_CONTRACT_WITH_ACTUAL_TEMPLATE','authority':job['receipt_sha256']}

def write_delivery(root,m,job_id,a):
    q=check_delivery(root,m,job_id,a)
    if not q['accepted']:raise ValueError('BULK_DELIVERY_REJECTED')
    path=safe(root,load_contracts(root,m)[job_id]['job']['delivery_path']);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and strict_json(path.read_bytes())!=a:raise ValueError('EXISTING_GROWTH_ARTIFACT_CHANGED')
    atomic_bytes(path,canonical(a));return q

def rebind_prepared(root,m,actions,contracts=None):
    offers={}
    for action in actions:
        a=action['args']
        if action['op']=='offer':offers[a['id']]=a
        elif action['op']=='event' and a['action']=='prepare':
            offer=offers[a['id']];payload=delivery(root,m,offer['job_id'])
            validate_prepared_order(root,m,offer['job_id'],payload,offer['price'])
            if digest(payload)!=a['artifact_sha256'] or not check_delivery(root,m,offer['job_id'],payload)['accepted']:raise ValueError('GROWTH_PREPARED_ARTIFACT_CHANGED')


def read_decision(root,m,job_id):
    path=safe(root,load_contracts(root,m)[job_id]['job']['delivery_path'].replace('/deliveries/','/decisions/'))
    decision=strict_json(path.read_bytes())
    if m['configuration']['mode']!='ECONOMIC':raise ValueError('ECONOMIC_DECISION_REQUIRED')
    from .policy import propose
    from .registration import design
    cfg=m['configuration'];reg=design();world=reg['worlds'][cfg['world']]
    result=propose(decision['state'],decision['summary'],world,reg,cfg['seed'],cfg['unit_cost'],cfg['opening'],grow=cfg['grow'],funding_mode=cfg['funding_mode'],policy_name=cfg['policy_name'])
    if result!=decision['proposal']:raise ValueError('MARKET_PROPOSAL_NOT_RECOMPUTED')
    return decision


def validate_prepared_order(root,m,job_id,artifact,price):
    cfg=m['configuration']
    if cfg['mode']=='TECHNICAL_UNIT_TEST':unit=cfg['unit_price_microUSD']
    else:unit=round(read_decision(root,m,job_id)['proposal']['unit_price_usd']*1_000_000)
    if type(price) is not int or price!=artifact['modeled_fulfillment_count']*unit:raise ValueError('BULK_QUANTITY_PRICE_NOT_BOUND')


def validate_offer(root,m,args,actions,summary):
    if m['configuration']['mode']=='TECHNICAL_UNIT_TEST':return
    d=read_decision(root,m,args['job_id'])
    if args.get('decision_sha256')!=digest(d):raise ValueError('PRECOMMITTED_MARKET_DECISION_REQUIRED')
    p=d['proposal']
    if summary['expenses']-d['summary']['expenses']!=sum(p['costs_microUSD'].values()):raise ValueError('COMPLETE_MONTH_RESOURCE_COST_NOT_PAID')
    count=p['chosen_orders']-p['collected_units'] if args['id'].endswith('-uncollected') else p['collected_units']
    if args['price']!=count*round(p['unit_price_usd']*1_000_000):raise ValueError('MARKET_ORDER_PRICE_QUANTITY_CHANGED')

    cfg=m['configuration']
    from .registration import design
    reg=design();world=reg['worlds'][cfg['world']]
    terms=[x['args']['terms'] for x in actions if x['op']=='register_terms' and x['args']['id']==args['terms_id']]
    unit=round(p['unit_price_usd']*1_000_000)
    collection=p['month']*reg['month_days']*24+world['settlement_days']*24
    expected={'price_microUSD':count*unit,'expected_collection_day':collection,'maturity_day':collection+world['tail_days']*24,'exposure_microUSD':count*(unit+200_000),'residual_microUSD':count*round(world['residual_per_unit_usd']*1_000_000),'fee_microUSD':0,'premium_microUSD':0,'coverage_limit_microUSD':0}
    if len(terms)!=1 or any(terms[0][k]!=v for k,v in expected.items()) or args['deadline']!=collection+24:raise ValueError('REGISTERED_BULK_TERMS_CHANGED')
