"""Costed recurring service operation through the canonical native enterprise.

Outside buyer receipts are a declared market assumption, never company income.
The comparison changes the seller's costed screening policy, not buyer funding.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes

ROOT=Path(__file__).resolve().parents[1]
M=1_000_000
SCHEMA='agi-alpha/recurring-business051/v1'
PROTOCOL={
    'schema':SCHEMA,'seed':261101151,'cohort_seed':261101151,
    'opening_microUSD_per_independent_account':100000*M,
    'target_trailing365_profit_microUSD':3_000_000_000*M,
    'cases':{'central_year':{'horizon_days':365,'rival_packet_price_microUSD':65*M},
             'strong_rival':{'horizon_days':60,'rival_packet_price_microUSD':15*M}},
    'arms':['ordinary','public_budget_screen'],
    'customer_pool':4,'jobs_per_service':32,'packet_jobs':64,'packet_rows':8,
    'initial_buyer_budget_microUSD':50*M,
    'buyer_income':{'schema':'agi-alpha/connected014-buyer-income/v1','first_day':30,'period_days':30,'income_microUSD':50*M,'receipt_bps':10000},
    'screen_development_cost_microUSD':5*M,'screen_daily_cost_microUSD':10000,
    'evidence_role':'FIXED_AUTHORED_ENGINEERING_COMPARISON_NOT_MARKET_CALIBRATION',
    'comparison':'Identical recurring buyer funding, inventory, prices, outside choices and initial capital inside each pair; only costed public affordability screening differs.',
    'stop':'Complete all registered horizons and drain, or report incomplete. No seed replacement, demand adjustment, profit-driven retry or automatic promotion.',
    'billing':'Native authored envelopes include setup, failed offers, production, independent checking, fees, taxes, maintenance and screening. Actual host/model/developer bills remain unknown.',
    'limits':['No real customers, outreach or payments.','Deterministic buyer outside income is assumed, not observed or caused by the enterprise.',
              'Four-buyer annual recurrence does not establish customer acquisition or billion-dollar scale.',
              'No claim of novel invention, improved inventor or universal optimality.','Matched businesses have separate accounts; never pool their balances.']}


def read(path):return strict_json(Path(path).read_bytes())
def write(path,value):atomic_bytes(Path(path),canonical(value)+b'\n')


def configuration(manifest,case,arm,root=ROOT):
    from .engine import fresh_account_config, validate_config
    from portfolio25.pricing import SCENARIOS
    if case not in PROTOCOL['cases'] or arm not in PROTOCOL['arms']:raise ValueError('REGISTERED_CASE_AND_ARM_REQUIRED')
    cfg,manifest=fresh_account_config(manifest,root=root)
    cfg.update(horizon_days=PROTOCOL['cases'][case]['horizon_days'],customer_pool=PROTOCOL['customer_pool'],
        opening=PROTOCOL['opening_microUSD_per_independent_account'],initial_slots=3,maximum_slots=3,
        arrival_bps=10000,retention_bps=10000,nonpayment_bps=0,clearing_hours=24)
    services=['reconciliation','kpi_variance','evidence_matrix','receivables_packet']
    values={s:100*M if s=='receivables_packet' else 40*M for s in services}
    profile={'id':'recurring-complete-work','services':services,
        'price_grids':{s:[50*M] if s=='receivables_packet' else [20*M,25*M] for s in services},
        'atoms':[{'weight_bps':10000,'budget_microUSD':PROTOCOL['initial_buyer_budget_microUSD'],'values':values}],
        'outside_options':[{'name':'competing-complete-outcome','provider':'rival','service_id':'receivables_packet',
             'price':PROTOCOL['cases'][case]['rival_packet_price_microUSD'],'quality_bps':10000,'delay_cost':0}]}
    groups={}
    for job in manifest['jobs']:groups.setdefault(job['service_id'],[]).append(job['id'])
    requested={f'SIM-customer-{i:03d}':[] for i in range(cfg['customer_pool'])}
    for ids in groups.values():
        for i,job in enumerate(sorted(ids)):requested[f'SIM-customer-{i%cfg["customer_pool"]:03d}'].append(job)
    cfg['complete_offer_policy']={'schema':'connected-complete-offer-market/v1','selection':'menu','profiles':[profile],'requested_jobs':requested}
    scenarios=copy.deepcopy(list(SCENARIOS))
    for scenario in scenarios:scenario.update(repeat_horizon=0,cost_shock=1)
    cfg['strategic_policy']={'schema':'connected-strategic-commerce/v1','public_basis':'Fixed public synthetic values/budgets; no observed customer demand or future private draw.',
        'ranking_arithmetic':'exact-rational-v1','price_bps':[5500,7000,9000,10000],'rival_price_bps':[5500,7000,9000,10000],
        'rival_cost_bps':3000,'rival_response':'observed_quote','scenarios':scenarios,'demand_model':'connected_range',
        'connected_beliefs':{s['id']:{'min_value_bps':7000,'max_value_bps':21000,'min_budget_microUSD':0,'max_budget_microUSD':600*M,'rival_available_bps':8000} for s in scenarios}}
    cfg['strategic_allocation_policy']={'max_customers':4,'risk':{
        'scenarios':{'baseline':5000,'ai_parity_price_war':3000,'differentiated_verified_service':2000},
        'worst_loss_limit':cfg['opening'],'downside_penalty_bps':2500,'max_states':262144,
        'authorized_allocation':cfg['opening'],'interactions':[]}}
    cfg['buyer_income_policy']=copy.deepcopy(PROTOCOL['buyer_income'])
    if arm=='public_budget_screen':
        cfg['setup_cost']+=PROTOCOL['screen_development_cost_microUSD']
        cfg['public_budget_gate']={'schema':'connected-public-budget-gate051/v1','daily_cost_microUSD':PROTOCOL['screen_daily_cost_microUSD']}
    return validate_config(cfg),manifest


def normal(path):
    path=Path(path).absolute()
    if '..' in path.parts or any(p.is_symlink() for p in [path,*path.parents]):raise ValueError('NORMAL_NON_SYMLINK_PATH_REQUIRED')
    return path


def register(output,case,arm):
    from .runner import source_paths,identity
    from adaptive_enterprise.instruments import prepare_complete_offer_services
    if case not in PROTOCOL['cases'] or arm not in PROTOCOL['arms']:raise ValueError('REGISTERED_CASE_AND_ARM_REQUIRED')
    output=normal(output);output.mkdir(parents=True,exist_ok=False);frozen=output/'source';frozen.mkdir()
    for name in source_paths(ROOT):
        origin=ROOT/name;target=frozen/name
        if origin.is_symlink():raise ValueError('SOURCE_SYMLINK_REFUSED')
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(origin,target)
    if identity(ROOT)!=identity(frozen):raise ValueError('EXACT_SOURCE_FREEZE_REQUIRED')
    manifest=prepare_complete_offer_services(frozen,'workloads/recurring051',cohort_seed=PROTOCOL['cohort_seed'],
        jobs_per_service=PROTOCOL['jobs_per_service'],packet_jobs=PROTOCOL['packet_jobs'],packet_rows=PROTOCOL['packet_rows'])
    cfg,manifest=configuration(manifest,case,arm,root=frozen)
    plan={'schema':SCHEMA,'protocol':PROTOCOL,'case':case,'arm':arm,'source':identity(frozen),'manifest':manifest,'config':cfg}
    write(output/'REGISTERED.json',plan)
    return plan


def validate_inventory(root,manifest):
    from adaptive_enterprise.instruments import audit_admission
    admission=manifest.get('cohort_provenance',{}).get('finite_admission',{})
    geometry={'primitive_jobs_per_service':PROTOCOL['jobs_per_service'],
        'packet_jobs':PROTOCOL['packet_jobs'],'packet_rows_per_kind':PROTOCOL['packet_rows'],'chunk_size':64}
    if manifest.get('native_engine')!='exact-permanent-v2' or any(type(admission.get(k)) is not int or admission[k]!=v for k,v in geometry.items()):
        raise ValueError('REGISTERED_RECURRING_WORK_GEOMETRY_REQUIRED')
    if manifest.get('cohort_provenance',{}).get('cohort_seed_sha256')!=digest(PROTOCOL['cohort_seed']):
        raise ValueError('REGISTERED_RECURRING_COHORT_SEED_REQUIRED')
    return audit_admission(root,manifest,cohort_seed=PROTOCOL['cohort_seed'])


def load_registered(output):
    from .runner import identity
    output=normal(output);plan=read(output/'REGISTERED.json')
    if plan.get('schema')!=SCHEMA or plan.get('protocol')!=PROTOCOL:raise ValueError('EXACT_REGISTERED_PROTOCOL_REQUIRED')
    if plan['source']!=identity(ROOT) or plan['source']!=identity(output/'source'):raise ValueError('EXECUTING_FROZEN_SOURCE_MISMATCH')
    validate_inventory(output/'source',plan['manifest'])
    cfg,manifest=configuration(plan['manifest'],plan['case'],plan['arm'],root=output/'source')
    if cfg!=plan['config'] or manifest!=plan['manifest']:raise ValueError('REGISTERED_CONFIG_OR_MANIFEST_CHANGED')
    return output,plan


def summarize(output):
    from .verify import audit
    from .scale import trailing_profit
    from .billion036 import first_passage
    output,plan=load_registered(output);result=read(output/'private'/'RESULT.json')
    if result['source']!=plan['source'] or result['config']!=plan['config'] or result['seed']!=PROTOCOL['seed'] or result['arm']!='competitive_growth':
        raise ValueError('REGISTERED_NATIVE_WORLD_REQUIRED')
    checked=audit(output/'source',plan['manifest'],result)
    if checked['accepted'] is not True or result['complete'] is not True:raise ValueError('COMPLETE_NATIVE_AUDIT_REQUIRED')
    annual=trailing_profit(result['owned_account']['ledger'],operating_end_hour=plan['config']['horizon_days']*24,operating_complete=True)
    milestone=first_passage(result['owned_account']['ledger'],operating_end_hour=plan['config']['horizon_days']*24,operating_complete=True,target_microUSD=PROTOCOL['target_trailing365_profit_microUSD'])
    s=result['summary'];categories={}
    for cost in result['costs']:categories[cost['category']]=categories.get(cost['category'],0)+cost['amount']
    orders=[{k:o[k] for k in ('id','job_id','customer_id','price','complete_cost','outcome','qualified_time','acceptance_time','collection_time')}|{
        'service':o['offer']['service_id'],'accepted':o['service_receipt']['accepted'],
        'artifact_sha256':o['service_receipt'].get('actual_execution_artifact_sha256'),'funding':o['funding_receipt']['funding']} for o in result['orders']]
    monthly=[]
    for start in range(0,plan['config']['horizon_days'],30):
        end=min(start+30,plan['config']['horizon_days']);settled=[o for o in orders if o['outcome']=='SETTLED' and start*24<=o['collection_time']<end*24]
        monthly.append({'start_day':start,'end_day_exclusive':end,'collected_microUSD':sum(o['price'] for o in settled),'paid_orders':len(settled)})
    return {'schema':SCHEMA,'case':plan['case'],'arm':plan['arm'],'protocol_sha256':digest(PROTOCOL),
        'registration_sha256':digest(plan),'source_sha256':plan['source']['sha256'],'result_sha256':digest(result),
        'evidence_role':PROTOCOL['evidence_role'],'native_audit_accepted':True,'complete':True,
        'summary':s,'cost_categories_microUSD':categories,'paid_orders':result['paid_jobs'],
        'paying_customers':result['customers'],'repeat_customers':result['repeat_customers'],
        'modeled_external_buyer_income_microUSD':checked['external_buyer_income_microUSD_recomputed'],
        'external_income_is_enterprise_revenue':False,'orders':orders,'monthly_collections':monthly,
        'annual_observer':annual,'three_billion_observer':milestone,
        'obligations_covered':s['payables']==0 and s['reservedInvestment']==0 and s['cash']>=sum(s[k] for k in ('custodyReserve','tailReserve','workingCapital')) and not s['investmentStopped'],
        'profit_identity_verified':s['profit']==s['revenue']+s.get('recoveryIncome',0)-s['expenses'],
        'actual_profit':None,'actual_customers':0,'actual_collections':0,'actual_host_model_developer_billing':None,
        'authority':[],'limits':PROTOCOL['limits'],'billing':PROTOCOL['billing'],
        'runtime':{'python':sys.version,'cryptography':importlib.metadata.version('cryptography')}}


def execute(output,max_events):
    from .engine import run_world
    output,plan=load_registered(output);start=time.process_time();wall=time.monotonic();error=None
    result=None
    try:
        result=run_world(output/'source',plan['manifest'],plan['config'],PROTOCOL['seed'],'competitive_growth',output/'private',source=plan['source'],stop_after_events=max_events)
        if result['complete']:
            report=summarize(output);(output/'public').mkdir(exist_ok=True);write(output/'public'/'SUMMARY.json',report)
        return {'complete':result['complete'],'processed_events':result['processed_events'],'profit_microUSD':result['summary']['profit']}
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc)};raise
    finally:
        receipts=read(output/'COMMANDS.json') if (output/'COMMANDS.json').exists() else []
        receipts.append({'process_cpu_seconds':time.process_time()-start,'wall_seconds':time.monotonic()-wall,
            'complete':bool(result and result['complete']),'error':error,'scope':'This finishing process only, not billing or unrecorded interrupted work.'})
        write(output/'COMMANDS.json',receipts)


def compare(control,candidate):
    a=summarize(control);b=summarize(candidate)
    pa=read(Path(control)/'REGISTERED.json');pb=read(Path(candidate)/'REGISTERED.json')
    ca,cb=copy.deepcopy(pa['config']),copy.deepcopy(pb['config']);cb.pop('public_budget_gate',None);cb['setup_cost']-=PROTOCOL['screen_development_cost_microUSD']
    def workload(m):
        m=copy.deepcopy(m);m.get('resource_receipt',{}).pop('process_cpu_seconds',None);return digest(m)
    if (a['arm']!='ordinary' or b['arm']!='public_budget_screen' or a['case']!=b['case'] or a['source_sha256']!=b['source_sha256'] or ca!=cb or workload(pa['manifest'])!=workload(pb['manifest'])):
        raise ValueError('MATCHED_SOURCE_MARKET_WORKLOAD_AND_CAPITAL_REQUIRED')
    outcome=lambda row:[{k:o[k] for k in ('job_id','customer_id','price','outcome','acceptance_time','collection_time','accepted','artifact_sha256')} for o in row['orders']]
    comparable=outcome(a)==outcome(b)
    delta=b['summary']['profit']-a['summary']['profit'];annual_a=a['annual_observer']['trailing_365_day_profit_microUSD'];annual_b=b['annual_observer']['trailing_365_day_profit_microUSD']
    qualified=all(x['obligations_covered'] and x['profit_identity_verified'] for x in (a,b))
    selected='public_budget_screen' if qualified and comparable and delta>0 and b['summary']['profit']>0 else 'ordinary' if qualified and a['summary']['profit']>0 else 'NO_SUPPORTED_PROFITABLE_POLICY'
    return {'schema':SCHEMA,'control':a,'candidate':b,'same_accepted_paid_work':comparable,
        'modeled_profit_delta_microUSD':delta,'trailing365_profit_delta_microUSD':annual_b-annual_a if annual_a is not None and annual_b is not None else None,
        'case_local_recommendation':selected,'adoption_authority':[],
        'scope':'Audited source-bound fixed-market policy comparison. No automatic default promotion, empirical demand validation or better-inventor claim.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('run');p.add_argument('--output',type=Path,required=True);p.add_argument('--case',choices=PROTOCOL['cases'],required=True);p.add_argument('--arm',choices=PROTOCOL['arms'],required=True);p.add_argument('--max-events',type=int,default=2500)
    for name in ('resume','_execute','verify'):
        p=sub.add_parser(name);p.add_argument('--output',type=Path,required=True)
        if name!='verify':p.add_argument('--max-events',type=int,default=2500)
    p=sub.add_parser('compare');p.add_argument('--control',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if hasattr(args,'max_events') and args.max_events<1:raise ValueError('POSITIVE_EVENT_QUANTUM_REQUIRED')
    if args.command=='run':register(args.output,args.case,args.arm)
    if args.command in ('run','resume'):
        out=normal(args.output)
        subprocess.run([sys.executable,'-m','connected_enterprise.recurring_business051','_execute','--output',str(out),'--max-events',str(args.max_events)],cwd=out/'source',check=True,timeout=1200)
    elif args.command=='_execute':print(json.dumps(execute(args.output,args.max_events)),flush=True)
    elif args.command=='verify':
        report=summarize(args.output)
        if report!=read(args.output/'public'/'SUMMARY.json'):raise ValueError('PUBLIC_SUMMARY_CHANGED')
        print(json.dumps({'accepted':True,'case':report['case'],'arm':report['arm'],'annual_profit_microUSD':report['annual_observer']['trailing_365_day_profit_microUSD']}))
    elif args.command=='compare':
        report_path=normal(args.report)
        if report_path.exists():raise ValueError('NEW_REPORT_PATH_REQUIRED')
        report=compare(args.control,args.candidate);write(report_path,report)
        print(json.dumps({k:report[k] for k in ('same_accepted_paid_work','modeled_profit_delta_microUSD','trailing365_profit_delta_microUSD','case_local_recommendation')}))

if __name__=='__main__':main()
