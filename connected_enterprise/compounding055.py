"""Finite recurring commerce registration and compact public native readout."""
import argparse
import copy
import json
from pathlib import Path
from commercial.ledger import canonical,digest
from .engine import default_config
from .registration import SCHEMA

COHORT=2611010552
EVALUATION_SEED=2611010551
DEVELOPMENT_SEED=2611010550


def job_id(service,index,cohort=COHORT):
    token=digest(['adaptive012-fresh-source',cohort,service,index])[:10]
    return f'adaptive012-{service}-{token}-{str(index).zfill(3)}'


def configuration(world,horizon=365):
    cfg=default_config()
    cfg.update(horizon_days=horizon,customer_pool=12,opening=100_000_000_000,
        monetary_policy='exact-integer-v2',initial_slots=1,maximum_slots=3)
    cfg['audience_policy']={'schema':'connected-audience/v1','owned_audience_count':4}
    from portfolio25.pricing import SCENARIOS
    scenarios=copy.deepcopy(list(SCENARIOS))
    for scenario in scenarios:scenario.update(repeat_horizon=0,cost_shock=1)
    cfg['strategic_policy']={'schema':'connected-strategic-commerce/v1',
        'public_basis':'Registered authored complete-outcome values, annual budgets, competent full-quality alternatives. No empirical demand or private future information.',
        'price_bps':[5000,10000],'rival_price_bps':[5000,10000],
        'rival_cost_bps':3000,'rival_response':'observed_quote','scenarios':scenarios,
        'ranking_arithmetic':'exact-rational-v1'}
    cfg['strategic_allocation_policy']={'max_customers':8,'risk':{
        'scenarios':{'baseline':5000,'ai_parity_price_war':3000,'differentiated_verified_service':2000},
        'worst_loss_limit':cfg['opening'],'downside_penalty_bps':2500,
        'max_states':262144,'authorized_allocation':cfg['opening'],'interactions':[]}}
    cfg['channel_menu_policy']={'schema':'connected-channel-menu/v1','contract_ids':['pilot'],'conversion_bps':4000}
    cfg['startup_acquisition_policy']={'schema':'connected-startup-acquisition/v1',
        'contract_ids':['pilot'],'conversion_bps':4000,'planning_cost_microUSD':100_000}
    service='reconciliation'
    profile={'id':'recurring-small-export-'+world,'services':[service],
        'price_grids':{service:[2_000_000,5_000_000,10_000_000,20_000_000]},
        'atoms':[{'weight_bps':weight,'budget_microUSD':budget*1_000_000,
                  'values':{service:value*1_000_000}}
                 for weight,budget,value in [(2500,180,40),(5000,400,65),(2500,580,85)]],
        'outside_options':[
            {'name':'competent-human-complete','provider':'human','service_id':service,'price':30_000_000,'quality_bps':10000,'delay_cost':0},
            {'name':'competent-human-plus-ai','provider':'rival','service_id':service,'price':10_000_000 if world=='central' else 5_000_000 if world=='commodity' else 20_000_000,'quality_bps':10000,'delay_cost':0},
            {'name':'autonomous-complete','provider':'rival','service_id':service,'price':6_000_000,'quality_bps':10000,'delay_cost':0},
            {'name':'competent-self-service','provider':'self_service','service_id':service,'price':0,'quality_bps':10000,'delay_cost':(5 if world=='central' else 2 if world=='commodity' else 12)*1_000_000}]}
    requests={f'SIM-customer-{i:03d}':[] for i in range(12)}
    # Each assigned source is a different period; ambiguous typed fixtures remain
    # explicit failed/unavailable inputs instead of acquiring invented facts.
    for month,day in enumerate(range(0,min(horizon,360),30)):
        for i,buyer in enumerate(requests):
            index=month*12+i
            release=day+(0 if world=='synchronized' else i)
            if release>=horizon:continue
            requests[buyer].append({'job_id':job_id(service,index),
                'release_hour':release*24,'expiry_hour':min(horizon,release+7)*24})
    cfg['complete_offer_policy']={'schema':'connected-complete-offer-market/v1',
        'selection':'menu','profiles':[profile],
        'requested_jobs':{buyer:[r['job_id'] for r in rows] for buyer,rows in requests.items()}}
    cfg['recurring_request_policy']={'schema':'connected-recurring-requests/v1',
        'jobs_per_service':max(32,12*((min(horizon,360)+29)//30)),'chunk_size':32,'requests':requests}
    cfg['cost_evidence']+=' Recurring055 uses existing positive envelopes, including shared development/failed search75 and daily maintenance0.10. All recurring public eligibility and lifetime valuation share that mandatory prepaid daily planning envelope; the conditional additional0.10 startup fee covers a nonempty candidate certificate and authority validation. Every quote, acquisition, fulfillment, refund and support contract is native charged. Annual buyer budgets180/400/580 are finite authored budgets, not replenished. No actual billing measured.'
    if world=='adverse':
        cfg.update(nonpayment_bps=1200,clearing_hours=168,retention_bps=8000,
            setup_cost=500_000_000,production_cost=4_500_000,
            supplier_outage_start_day=180,supplier_outage_days=14)
        for terms in cfg['channels'].values():
            terms['price_microUSD']*=10;terms['realization_bps']=2500
    if world not in {'central','friction','commodity','adverse','synchronized'}:raise ValueError('REGISTERED_WORLD_REQUIRED')
    return cfg


def registration(development=False):
    horizon=14 if development else 365
    worlds=['central','friction'] if development else ['central','friction','commodity','adverse','synchronized']
    return {'schema':SCHEMA,'label':'compounding055-development' if development else 'compounding055-account-year',
        'evidence_role':'development' if development else 'finite_authored_comparison',
        'seeds':[DEVELOPMENT_SEED if development else EVALUATION_SEED],
        'configs':{world:configuration(world,horizon) for world in worlds},
        'arms':['channel','growth'],'control_arm':'channel','candidate_arm':'growth',
        'service_cohort_seed':COHORT,'workers':2}


def compact(output):
    from .runner import read_freeze,tasks
    from .scale import trailing_profit
    output=Path(output).resolve();f=read_freeze(output);rows=[]
    for task in tasks(f['protocol']):
        path=output/'worlds'/task['id']/'RESULT.json'
        if not path.exists():rows.append({'task':task,'status':'NOT_STARTED'});continue
        result=json.loads(path.read_text());orders=result['orders'];settled=[o for o in orders if o['outcome']=='SETTLED'];summary=result['summary']
        annual=trailing_profit(result['owned_account']['ledger'],operating_end_hour=result['config']['horizon_days']*24,operating_complete=result['complete'])
        by_month=[sum(o['collection_time'] is not None and month*30*24<=o['collection_time']<min((month+1)*30,365)*24 for o in orders) for month in range(13)]
        first=settled[0] if settled else None
        second=next((o for o in settled if first and o['customer_id']==first['customer_id'] and o['id']!=first['id']),None)
        trace=lambda o:None if o is None else {k:o.get(k) for k in ('id','job_id','customer_id','qualified_time','collection_time','price','complete_cost','onboarding','outcome','funding_receipt')}
        rows.append({'task':task,'status':'COMPLETE' if result['complete'] else 'PAUSED',
            'result_sha256':digest(result),'account_identity_sha256':digest(result['owned_account']['ledger']['config']),
            'summary_microUSD':summary,'trailing_365':annual,'paid_deliveries':len(settled),
            'collections_by_30_day_bin':by_month,'last_collection_hour':max((o['collection_time'] for o in settled),default=None),
            'unpaid_orders':[o['id'] for o in orders if o['outcome']=='PENDING'],
            'refunded_or_failed_orders':[o['id'] for o in orders if o['outcome'] not in {'PENDING','SETTLED'}],
            'first_to_second':{'first':trace(first),'same_customer_successor':trace(second),
                'retained_means':'Authenticated paid onboarding/context; later compatible work avoids the declared onboarding fee.',
                'counterfactual_without_onboarding':None if second is None else {'legitimate_available_route':'Pay the same0.50USD onboarding from available seed or cash and deliver the same accepted outcome.','additional_cost_microUSD':result['config']['onboarding_cost'],'second_order_direct_surplus_microUSD':second['price']-second['complete_cost']-result['config']['onboarding_cost'],'claim':'ORDINARY_REUSE_OR_SEQUENCING; NOT_NEWLY_INACCESSIBLE_OPPORTUNITY'}},
            'whole_connected_costs_microUSD':summary['expenses'],
            'investments':[{k:i.get(k) for k in ('id','plan_id','kind','cost','funding_receipt','activation_time','expiry_time')} for i in result['investments']],
            'scope':'NATIVE_SIMULATION; deterministic controller; no live model agent, real customer, actual commerce or measured API billing'})
    return {'schema':'compounding-enterprise055/compact/v1','source_sha256':f['source']['sha256'],
        'frozen_sha256':f['sha256'],'rows':rows,'actual_commercial_profit':None,
        'unknown_actual_billing':None,'discovery_method_advantage':'NOT_CLAIMED',
        'target_microUSD':3_000_000_000_000_000,
        'cost_sensitivity':'Each additional dollar of whole-enterprise included-resource cost reduces modeled profit by one dollar before tax adjustments. The frozen adverse arm raises setup and variable cost; missing actual billing is not zero.',
        'comparison':'channel is competent ordinary commerce plus acquisition; growth adds capacity only when its public-history criterion permits. This is ordinary established control, not an autonomous discovery comparison. Initial seed allows legitimate purchases; earned provenance is not a causal impossibility proof.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['input','report']);parser.add_argument('--output',required=True);parser.add_argument('--development',action='store_true');args=parser.parse_args()
    if args.command=='input':
        from .registration import validate
        value=validate(registration(args.development));Path(args.output).write_bytes(canonical(value)+b'\n');print(json.dumps({'input_sha256':digest(value),'path':args.output,'accounts_created':False}));return
    value=compact(args.output);print(json.dumps(value,sort_keys=True))

if __name__=='__main__':main()
