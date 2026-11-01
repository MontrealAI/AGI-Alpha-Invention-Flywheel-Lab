#!/usr/bin/env python3
"""Fixed native throughput qualification; no changes to the economic objective."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
MICRO=1_000_000
PROTOCOL={
    'schema':'agi-alpha/market-index049-qualification/v1','seed':261101049,'cohort_seed':261101049,
    'cases':{'small':{'buyers':4,'days':4,'jobs_per_service':32,'packet_jobs':8},
             'acquisition':{'buyers':48,'days':21,'jobs_per_service':128,'packet_jobs':64}},
    'opening_microUSD':100000*MICRO,'packet_rows':8,
    'scope':'Fixed authored native execution and runtime semantic-parity experiment, not real commerce or calibrated demand.',
    'comparison':'Original complete-offer implementation versus semantics-preserving prepared-profile and request-ID lookup.',
    'stop':'Complete both fixed cases or preserve an explicit incomplete/error; no seed replacement or profit-driven retries.',
    'unknown_costs':'Host/model/developer billing is unknown. Resource timings are telemetry, not profit or cost discounts.'}


def read(path):
    from commercial.ledger import strict_json
    return strict_json(Path(path).read_bytes())


def write(path,value):
    from commercial.ledger import canonical
    from commercial.persistence import atomic_bytes
    atomic_bytes(Path(path),canonical(value)+b'\n')


def config(manifest,case):
    from connected_enterprise.engine import fresh_account_config,validate_config
    from portfolio25.pricing import SCENARIOS
    cfg,manifest=fresh_account_config(manifest,root=ROOT)
    setting=PROTOCOL['cases'][case];n=setting['buyers']
    services=['reconciliation','kpi_variance','evidence_matrix','receivables_packet']
    values=dict.fromkeys(services,40*MICRO);values['receivables_packet']=100*MICRO
    profile={'id':'fixed-complete-work','services':services,
        'price_grids':{s:[20*MICRO,25*MICRO] if s!='receivables_packet' else [50*MICRO] for s in services},
        'atoms':[{'weight_bps':10000,'budget_microUSD':600*MICRO,'values':values}],
        'outside_options':[{'name':'rival-packet','provider':'rival','service_id':'receivables_packet','price':65*MICRO,'quality_bps':10000,'delay_cost':0},
                           {'name':'self-service-packet','provider':'self_service','service_id':'receivables_packet','price':15*MICRO,'quality_bps':6000,'delay_cost':5*MICRO}]}
    by_service={}
    for job in manifest['jobs']:by_service.setdefault(job['service_id'],[]).append(job['id'])
    requested={f'SIM-customer-{i:03d}':[] for i in range(n)}
    for ids in by_service.values():
        for i,ident in enumerate(sorted(ids)):requested[f'SIM-customer-{i%n:03d}'].append(ident)
    scenarios=copy.deepcopy(list(SCENARIOS))
    for scenario in scenarios:scenario.update(repeat_horizon=0,cost_shock=1)
    cfg.update(horizon_days=setting['days'],customer_pool=n,opening=PROTOCOL['opening_microUSD'],initial_slots=3,maximum_slots=3,
               arrival_bps=10000,retention_bps=10000,nonpayment_bps=0,clearing_hours=24)
    cfg['complete_offer_policy']={'schema':'connected-complete-offer-market/v1','selection':'menu','profiles':[profile],'requested_jobs':requested}
    cfg['strategic_policy']={'schema':'connected-strategic-commerce/v1','public_basis':'Explicit authored performance fixture, not observed market demand.',
        'price_bps':[5500,7000,9000,10000],'rival_price_bps':[5500,7000,9000,10000],
        'rival_cost_bps':3000,'rival_response':'observed_quote','scenarios':scenarios,'demand_model':'connected_range',
        'connected_beliefs':{s['id']:{'min_value_bps':7000,'max_value_bps':21000,'min_budget_microUSD':0,'max_budget_microUSD':600*MICRO,'rival_available_bps':8000} for s in scenarios}}
    cfg['strategic_allocation_policy']={'max_customers':4,'risk':{'scenarios':{'baseline':5000,'ai_parity_price_war':3000,'differentiated_verified_service':2000},
        'worst_loss_limit':cfg['opening'],'downside_penalty_bps':2500,'max_states':262144,'authorized_allocation':cfg['opening'],'interactions':[]}}
    cfg['channel_menu_policy']={'schema':'connected-channel-menu/v1','contract_ids':['extended','pilot'],'conversion_bps':2500}
    return validate_config(cfg),manifest


def semantic_projection(result):
    # Each source is independently audited before this explicit cross-source
    # projection. Source-specific signatures/hashes are not financial variables.
    from commercial.ledger import digest
    order_fields=('id','customer_id','job_id','work_keys','offer','price','qualified_time','production_time','acceptance_time','collection_time','outcome','complete_cost','fee','onboarding','production_cost','support_cost','capacity_units','acquisition_source_plan_id','capacity_source_plan_id','capacity_source_plan_ids')
    decision_fields=('kind','time','customer_id','service_id','price','chosen','buyer_choice','outside_option_name','outside_service_id','outside_spend','market_context','joint_recourse_round')
    investment_fields=('id','plan_id','kind','cost','purchased_time','activation_time','expiry_time','capacity_units','contract_receipt','predicted_net')
    fields={k:result[k] for k in ('config','seed','arm','summary','buyers','market','channels','complete','processed_events','paid_jobs','accepted_jobs','customers','repeat_customers','stop_reasons')}
    fields['orders']=[{k:o[k] for k in order_fields if k in o}|{'accepted':o['service_receipt']['accepted'],'artifact_sha256':o['service_receipt'].get('actual_execution_artifact_sha256'),'resource_funding':o['funding_receipt']['funding']} for o in result['orders']]
    fields['decisions']=[{k:d[k] for k in decision_fields if k in d} for d in result['decisions']]
    fields['investments']=[{k:i[k] for k in investment_fields if k in i}|{'funding':i['funding_receipt']['funding']} for i in result['investments']]
    fields['costs']=[{k:c[k] for k in ('id','amount','category','time')} for c in result['costs']]
    return {'sha256':digest(fields),'projection':fields}


def audit_and_report(output,registration):
    from connected_enterprise.verify import audit
    from connected_enterprise.runner import identity
    from commercial.ledger import digest
    if identity(ROOT)!=registration['source'] or digest(PROTOCOL)!=registration['protocol_sha256']:
        raise ValueError('EXACT_REGISTERED_SOURCE_REQUIRED')
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=registration['driver_sha256']:
        raise ValueError('QUALIFICATION_DRIVER_CHANGED')
    result=read(output/'private'/'RESULT.json')
    cfg,manifest=config(registration['manifest'],registration['case'])
    if result['config']!=cfg or result['source']!=registration['source'] or result['seed']!=PROTOCOL['seed']:
        raise ValueError('NATIVE_PROTOCOL_CHANGED')
    checked=audit(ROOT,manifest,result)
    if not result['complete'] or checked['accepted'] is not True:raise ValueError('COMPLETE_NATIVE_AUDIT_REQUIRED')
    if result['summary']['profit']!=result['summary']['revenue']-result['summary']['expenses']:raise ValueError('PROFIT_IDENTITY_FAILED')
    projection=semantic_projection(result)
    paid=[o for o in result['orders'] if o['outcome']=='SETTLED'];acquired=[o for o in paid if o['acquisition_source_plan_id']]
    report={'schema':PROTOCOL['schema'],'protocol':PROTOCOL,'case':registration['case'],'source_sha256':registration['source']['sha256'],
        'driver_sha256':registration['driver_sha256'],'result_sha256':digest(result),'native_audit_accepted':True,
        'summary':result['summary'],'paid_orders':result['paid_jobs'],'paying_customers':result['customers'],
        'paid_acquired_customers':len({o['customer_id'] for o in acquired}),'paid_acquired_orders':len(acquired),
        'paid_channel_exposures':sum(i['realized_exposures'] for i in result['channels']['instances'].values()),
        'channel_invoices_microUSD':sum(i['cost'] for i in result['investments'] if i['kind']=='acquisition'),
        'result_semantics_sha256':projection['sha256'],'resource_receipt':result['resource_receipt'],
        'actual_customers':0,'actual_collections':0,'actual_profit':None}
    write(output/'PUBLIC.json',report);write(output/'SEMANTICS.json',projection)
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['run','verify']);p.add_argument('--case',choices=PROTOCOL['cases'],required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--max-events',type=int,default=100)
    a=p.parse_args();out=a.output.absolute()
    if '..' in out.parts or any(x.is_symlink() for x in [out,*out.parents]) or a.max_events<1:raise ValueError('NEW_NORMAL_OUTPUT_AND_POSITIVE_EVENT_BOUND_REQUIRED')
    from connected_enterprise.runner import identity
    from commercial.ledger import digest
    if a.command=='verify':
        report=audit_and_report(out,read(out/'REGISTRATION.json'));print(json.dumps({k:report[k] for k in ('case','native_audit_accepted','paid_orders','paying_customers','paid_acquired_customers','summary')}));return
    if not out.exists():
        from adaptive_enterprise.instruments import prepare_complete_offer_services
        out.mkdir(parents=True,exist_ok=False)
        rel='.market-index049-inputs/'+a.case
        spec=PROTOCOL['cases'][a.case]
        manifest=prepare_complete_offer_services(ROOT,rel,cohort_seed=PROTOCOL['cohort_seed'],jobs_per_service=spec['jobs_per_service'],packet_jobs=spec['packet_jobs'],packet_rows=PROTOCOL['packet_rows'])
        cfg,manifest=config(manifest,a.case)
        registration={'source':identity(ROOT),'case':a.case,'protocol_sha256':digest(PROTOCOL),'manifest':manifest,'config':cfg,'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        write(out/'REGISTRATION.json',registration)
    registration=read(out/'REGISTRATION.json')
    if registration['case']!=a.case or registration['source']!=identity(ROOT) or registration['protocol_sha256']!=digest(PROTOCOL) or registration['driver_sha256']!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest():raise ValueError('RESTART_CANNOT_CHANGE_SOURCE_OR_REGISTRATION')
    cfg,manifest=config(registration['manifest'],a.case)
    if cfg!=registration['config']:raise ValueError('RESTART_CONFIG_CHANGED')
    from connected_enterprise.engine import run_world
    begin=time.process_time();result=run_world(ROOT,manifest,cfg,PROTOCOL['seed'],'competitive_growth',out/'private',source=registration['source'],stop_after_events=a.max_events)
    record={'operation':'run_or_same_account_resume','cpu_seconds':time.process_time()-begin,'complete':result['complete'],'processed_events':result['processed_events']}
    records=read(out/'COMMANDS.json') if (out/'COMMANDS.json').exists() else []
    records.append(record);write(out/'COMMANDS.json',records)
    if result['complete']:
        report=audit_and_report(out,registration)
        print(json.dumps({'case':a.case,'complete':True,'profit_microUSD':report['summary']['profit'],'paid_customers':report['paying_customers'],'paid_acquired_customers':report['paid_acquired_customers'],'native_audit':True}))
    else:print(json.dumps(record))

if __name__=='__main__':main()
