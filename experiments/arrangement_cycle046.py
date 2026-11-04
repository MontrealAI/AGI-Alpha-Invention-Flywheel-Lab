"""Fixed native complete-offer/capacity experiment. No new ledger or simulator.
All buyers, costs and supplier terms are authored synthetic assumptions.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, shutil, subprocess, sys, time
from pathlib import Path
from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from connected_enterprise.runner import identity
from connected_enterprise.engine import fresh_account_config, validate_config, run_world
from connected_enterprise.verify import audit
from adaptive_enterprise.instruments import prepare_complete_offer_services
from adaptive_enterprise.allocation import default_riskpolicy
from portfolio25.pricing import SCENARIOS
ROOT=Path(__file__).resolve().parents[1]
SCHEMA='agi-alpha/native-arrangement-cycle046/v1'
DRIVER_FILES=('experiments/arrangement_cycle046.py','tests/test_arrangement_cycle046.py')
MICRO=1_000_000


def driver_identity(root):
    result={}
    for name in DRIVER_FILES:
        p=Path(root)/name
        if p.is_symlink() or not p.is_file() or any(x.is_symlink() for x in p.parents):
            raise ValueError('NORMAL_EXPERIMENT_SOURCE_REQUIRED')
        result[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def check_source(frozen):
    if identity(ROOT)!=frozen['source'] or driver_identity(ROOT)!=frozen['driver_files']:
        raise ValueError('FROZEN_NATIVE_OR_EXPERIMENT_SOURCE_CHANGED')


def protocol():
    return {'schema':SCHEMA,'scope':'FINITE_AUTHORED_NATIVE_SIMULATION','opening_microUSD':100_000*MICRO,
        'external_funding_microUSD':0,'arms':['one_unit','complementary'],'seed':2611010461,
        'cases':[{'id':'central','buyers':8,'days':14,'max_slots':3,'rival_price':180*MICRO},
                 {'id':'larger','buyers':24,'days':28,'max_slots':6,'rival_price':180*MICRO},
                 {'id':'strong_outside','buyers':8,'days':14,'max_slots':3,'rival_price':15*MICRO}],
        'services':{'primitive_jobs_per_service':32,'packet_jobs':64,'rows_per_packet':12},
        'assumptions':{'packet_value':180*MICRO,'narrow_value':55*MICRO,'narrow_price':30*MICRO,
                       'packet_price':120*MICRO,'buyer_budget':1500*MICRO,'capacity_unit_cost':8*MICRO,
                       'arrival_bps':9500,'retention_bps':9800,'nonpayment_bps':100},
        'limits':['One fixed seed, identical exogenous market within pair, no seed replacement.',
                  'Native execution of synthetic work, not calibrated demand or actual customers.',
                  'Only allowed capacity search quantity differs. More elaborate policy may lose.',
                  'Actual model/host/development billing unknown; no annualization or invention claim.']}


def validate(p):
    if canonical(p)!=canonical(protocol()):raise ValueError('EXACT_FIXED_PROTOCOL_REQUIRED')
    return p


def write(path,value):atomic_bytes(Path(path),canonical(value)+b'\n')


def config(p,case,arm,manifest):
    validate(p)
    if case not in p['cases'] or arm not in p['arms']:raise ValueError('REGISTERED_CASE_ARM_REQUIRED')
    cfg,admitted=fresh_account_config(manifest,root=ROOT)
    a=p['assumptions']
    cfg.update(opening=p['opening_microUSD'],horizon_days=case['days'],customer_pool=case['buyers'],
        initial_slots=1,maximum_slots=case['max_slots'],capacity_price=a['capacity_unit_cost'],
        arrival_bps=a['arrival_bps'],retention_bps=a['retention_bps'],nonpayment_bps=a['nonpayment_bps'])
    cfg['channels']['pilot']['owned_audience_count']=case['buyers']
    scenarios=[dict(SCENARIOS[0],id='central',weight=1.0,accept_prob=.98,collect_prob=.99,cost_shock=1.,repeat_horizon=0)]
    cfg['strategic_policy']={'schema':'connected-strategic-commerce/v1',
        'public_basis':'Frozen authored request hypotheses, not measured private preferences.',
        'price_bps':[10000],'rival_price_bps':[10000],'rival_cost_bps':8000,
        'rival_response':'observed_quote','scenarios':scenarios}
    risk=default_riskpolicy();risk.update(scenarios={'central':10000},authorized_allocation=1000*MICRO,max_states=65536,worst_loss_limit=30*MICRO)
    cfg['strategic_allocation_policy']={'risk':risk,'max_customers':2,
        'capacity_menu':{'max_quantity':1 if arm=='one_unit' else case['max_slots']-1,
                         'opportunity_delay_hours':48,'retention_bps':8000}}
    services=['reconciliation','receivables_packet']
    profile={'id':'complete-cash-application','services':services,
        'price_grids':{'reconciliation':[a['narrow_price']],'receivables_packet':[a['packet_price']]},
        'atoms':[{'weight_bps':10000,'budget_microUSD':a['buyer_budget'],
                  'values':{'reconciliation':a['narrow_value'],'receivables_packet':a['packet_value']}}],
        'outside_options':[{'name':'competent-human','provider':'human','service_id':'receivables_packet','price':220*MICRO,'quality_bps':10000,'delay_cost':0},
            {'name':'autonomous-rival','provider':'rival','service_id':'receivables_packet','price':case['rival_price'],'quality_bps':10000,'delay_cost':0},
            {'name':'self-service','provider':'self_service','service_id':'receivables_packet','price':60*MICRO,'quality_bps':3000,'delay_cost':10*MICRO}]}
    requested={f'SIM-customer-{i:03d}':[] for i in range(case['buyers'])}
    for service in services:
        jobs=sorted((j for j in manifest['jobs'] if j['service_id']==service and j['accepted']),key=lambda j:j['id'])
        for i,job in enumerate(jobs):requested[f'SIM-customer-{i%case["buyers"]:03d}'].append(job['id'])
    cfg['complete_offer_policy']={'schema':'connected-complete-offer-market/v1','selection':'menu','profiles':[profile],'requested_jobs':requested}
    return validate_config(cfg),admitted


def links(order):
    out=set(order.get('capacity_source_plan_ids') or [])
    for key in ('capacity_source_plan_id','acquisition_source_plan_id'):
        if order.get(key):out.add(order[key])
    return out


def witness(result):
    """Derive only from independently audited native results; never authenticates them.
    Conservatively includes every linked loss, every required enabler invoice,
    and separately assigns all enterprise costs to the linked collections.
    """
    if result.get('complete') is not True:raise ValueError('COMPLETED_NATIVE_RESULT_REQUIRED')
    ledger=result['owned_account']['ledger'];s=result['summary']
    if canonical(ledger['summary'])!=canonical(s) or digest(ledger['actions'])!=ledger['actions_sha256']:
        raise ValueError('NATIVE_HISTORY_OR_SUMMARY_CHANGED')
    plans={i['plan_id']:i for i in result['investments']}
    if len(plans)!=len(result['investments']):raise ValueError('DUPLICATE_ENABLER_ID')
    settled=[o for o in result['orders'] if o['outcome']=='SETTLED']
    chains=[]
    for target in sorted(settled,key=lambda o:(o['collection_time'],o['id'])):
        if target['offer']['service_id']!='receivables_packet' or target.get('capacity_units')!=3:continue
        required=links(target)
        if not required:continue
        if not required<=plans.keys():raise ValueError('MISSING_REQUIRED_ENABLER')
        enablers=[plans[k] for k in required]
        if any(i['funding_receipt'].get('funding')!='EARNED' for i in enablers):continue
        if any(not i['activation_time']<=target['qualified_time']<i['expiry_time'] for i in enablers):raise ValueError('SUCCESSOR_OUTSIDE_ENABLER_LIFETIME')
        first_purchase=min(i['purchased_time'] for i in enablers)
        prior=[o for o in settled if o['collection_time']<first_purchase and o['offer']['service_id']!='receivables_packet']
        if not prior:continue
        first=max(prior,key=lambda o:(o['collection_time'],o['id']))
        closure=set(required)
        while True:
            cohort=[o for o in result['orders'] if links(o)&closure]
            expanded=closure|set().union(*(links(o) for o in cohort))
            if expanded==closure:break
            closure=expanded
        if not closure<=plans.keys():raise ValueError('MISSING_COHORT_ENABLER')
        if any(plans[k]['funding_receipt'].get('funding')!='EARNED' for k in closure):continue
        revenue=sum(o['price'] for o in cohort if o['outcome']=='SETTLED')
        cost=sum(o['complete_cost'] for o in cohort)+sum(plans[k]['cost'] for k in closure)
        chains.append({'first_order':first['id'],'first_service':first['offer']['service_id'],
            'first_collection_hour':first['collection_time'],'first_collection_microUSD':first['price'],
            'first_order_contribution_microUSD':first['price']-first['complete_cost'],
            'enablers':[{'plan_id':k,'kind':plans[k]['kind'],'hour':plans[k]['purchased_time'],
                         'invoice_microUSD':plans[k]['cost'],'capacity_units':plans[k].get('capacity_units',0),
                         'funding':plans[k]['funding_receipt']['funding']} for k in sorted(closure)],
            'successor_order':target['id'],'successor_service':target['offer']['service_id'],
            'successor_collection_hour':target['collection_time'],'successor_collection_microUSD':target['price'],
            'successor_order_contribution_microUSD':target['price']-target['complete_cost'],
            'cohort_all_orders':len(cohort),'cohort_settled':sum(o['outcome']=='SETTLED' for o in cohort),
            'cohort_collections_microUSD':revenue,'cohort_cost_and_enabler_invoice_microUSD':cost,
            'cohort_contribution_before_shared_overhead_microUSD':revenue-cost,
            'conservative_after_all_enterprise_expenses_microUSD':revenue-s['expenses']-s.get('refunds',0)})
        break
    passed=bool(chains and s['profit']>0 and chains[0]['conservative_after_all_enterprise_expenses_microUSD']>0)
    return {'status':'NATIVE_FUNDED_COMPLEMENTARY_SUCCESSOR' if passed else 'NOT_ESTABLISHED',
        'chains':chains,'native_actions_sha256':ledger['actions_sha256'],'causal_profit_advantage':None,
        'new_invention':False,'inventor_improvement':False,'actual_collections_microUSD':0,'authority':[]}


def project(result,checked):
    if checked.get('accepted') is not True:raise ValueError('CANONICAL_AUDIT_REQUIRED')
    return {'audit_accepted':True,'result_sha256':digest(result),'summary':copy.deepcopy(result['summary']),
        'paid_jobs':result['paid_jobs'],'customers':result['customers'],'repeat_customers':result['repeat_customers'],
        'accepted_packets':sum(o['outcome']=='SETTLED' and o['offer']['service_id']=='receivables_packet' for o in result['orders']),
        'buyer_choices':{x:sum(d.get('buyer_choice')==x for d in result['decisions']) for x in ('us','human','rival','self_service','decline')},
        'investments':[{'kind':i['kind'],'cost_microUSD':i['cost'],'capacity_units':i.get('capacity_units',0),'purchased_hour':i['purchased_time'],'funding':i['funding_receipt'].get('funding')} for i in result['investments']],
        'mechanism':witness(result)}


def retain_mechanism(summary):
    """Compress verified comparisons into a scoped applicability rule, not authority."""
    rows = {}
    for case in protocol()['cases']:
        a, b = (summary['worlds'][case['id']+'-'+arm] for arm in protocol()['arms'])
        if not (a['audit_accepted'] is True and b['audit_accepted'] is True):
            raise ValueError('AUDITED_COMPARISONS_REQUIRED')
        if max(a['summary']['profit'], b['summary']['profit']) <= 0:
            choice = 'NO_SUPPORTED_PROFITABLE_EXPANSION'
        elif b['summary']['profit'] > a['summary']['profit'] and b['mechanism']['status'] == 'NATIVE_FUNDED_COMPLEMENTARY_SUCCESSOR':
            choice = 'COMPLEMENTARY_CAPACITY_SEARCH'
        else:
            choice = 'RETAIN_SIMPLER_ONE_UNIT_POLICY'
        rows[case['id']] = {'choice':choice, 'observed_profit_delta_microUSD':b['summary']['profit']-a['summary']['profit'],
            'evidence_sha256':digest([a['result_sha256'],b['result_sha256']])}
    return {'schema':'agi-alpha/applicability-capsule046/v1',
        'source_sha256':summary['source_sha256'], 'experiment_sha256':summary['experiment_sha256'], 'protocol_sha256':summary['protocol_sha256'],
        'rule':'Evaluate a complementary resource bundle when individual increments cannot satisfy the complete accepted outcome; keep ordinary production eligible.',
        'required_rechecks':['fresh native available and unrestricted earned cash','current supplier price, expiry and permissions',
                            'observed unserved request and current outside alternatives','full outcome quality and full resource cost'],
        'observed_regions':rows, 'known_method_not_new_invention':True,
        'current_proof':None, 'authority':[], 'execution_authority':False,
        'transfer_limit':'Re-evaluate on a new mission; no inferred private values, consent, horizon extrapolation or scientific generality.'}


def validate_result_header(recorded, frozen, p):
    if (recorded.get('schema') != SCHEMA or recorded.get('scope') != p['scope']
            or recorded.get('complete') is not True
            or recorded.get('source_sha256') != frozen['source']['sha256']
            or recorded.get('protocol_sha256') != digest(p)
            or recorded.get('experiment_sha256') != digest(frozen['driver_files'])
            or type(recorded.get('opening_per_world_microUSD')) is not int
            or recorded['opening_per_world_microUSD'] != p['opening_microUSD']
            or type(recorded.get('external_funding_microUSD')) is not int
            or recorded['external_funding_microUSD'] != 0
            or type(recorded.get('actual_customers')) is not int
            or recorded['actual_customers'] != 0
            or recorded.get('actual_profit_microUSD') is not None
            or recorded.get('limits') != p['limits']):
        raise ValueError('CURRENT_COMPLETED_SOURCE_BOUND_SIMULATED_RESULT_REQUIRED')



def verify(output):
    output=Path(output).absolute();frozen=strict_json((output/'FREEZE.json').read_bytes())
    check_source(frozen)
    p=validate(strict_json((output/'PROTOCOL.json').read_bytes()))
    recorded=strict_json((output/'public'/'RESULT.json').read_bytes())
    validate_result_header(recorded,frozen,p)
    manifest=strict_json((output/'SERVICES.json').read_bytes());actual={}
    for case in p['cases']:
        for arm in p['arms']:
            name=case['id']+'-'+arm;cfg,admitted=config(p,case,arm,manifest)
            result=strict_json((output/'private'/name/'RESULT.json').read_bytes())
            if canonical(result['config'])!=canonical(cfg) or result['seed']!=p['seed'] or result['arm']!='competitive_growth':
                raise ValueError('WORLD_CHANGED_AFTER_REGISTRATION')
            actual[name]=project(result,audit(ROOT,admitted,result))
    if canonical(actual)!=canonical(recorded['worlds']):raise ValueError('PUBLIC_RESULT_CHANGED')
    for case in p['cases']:
        a,b=(actual[case['id']+'-'+arm] for arm in p['arms'])
        expected={'profit_delta_microUSD':b['summary']['profit']-a['summary']['profit'],
                  'paid_job_delta':b['paid_jobs']-a['paid_jobs'],'packet_delta':b['accepted_packets']-a['accepted_packets']}
        if canonical(expected)!=canonical(recorded['comparisons'][case['id']]):raise ValueError('COMPARISON_CHANGED')
    capsule=strict_json((output/'public'/'MECHANISM.json').read_bytes())
    if canonical(capsule)!=canonical(retain_mechanism(recorded)):raise ValueError('RETAINED_SCOPE_CHANGED')
    return {'accepted':True,'worlds':len(actual),'source_sha256':frozen['source']['sha256'],
            'experiment_sha256':digest(frozen['driver_files']),
            'scope':'CANONICALLY_REAUDITED_FIXED_SYNTHETIC_EXPERIMENT','funding_authority':False}


def execute(output):
    output=Path(output).absolute();frozen=strict_json((output/'FREEZE.json').read_bytes())
    check_source(frozen)
    p=validate(strict_json((output/'PROTOCOL.json').read_bytes()))
    if digest(p)!=frozen['protocol_sha256']:raise ValueError('PROTOCOL_CHANGED')
    manifest_path=output/'SERVICES.json'
    if manifest_path.exists():manifest=strict_json(manifest_path.read_bytes())
    else:
        manifest=prepare_complete_offer_services(ROOT,'arrangement-inputs',cohort_seed=p['seed'],
            jobs_per_service=p['services']['primitive_jobs_per_service'],packet_jobs=p['services']['packet_jobs'],packet_rows=p['services']['rows_per_packet'])
        write(manifest_path,manifest)
    results={};start,cpu=time.monotonic(),time.process_time()
    for case in p['cases']:
        for arm in p['arms']:
            name=case['id']+'-'+arm;cfg,admitted=config(p,case,arm,manifest)
            result=run_world(ROOT,admitted,cfg,p['seed'],'competitive_growth',output/'private'/name,source=frozen['source'])
            results[name]=project(result,audit(ROOT,admitted,result))
            write(output/'public'/'PROGRESS.json',{'source_sha256':frozen['source']['sha256'],'completed':results,'expected_worlds':6,'complete':False})
            print(json.dumps({'world':name,'profit':result['summary']['profit'],'paid':result['paid_jobs'],'packets':results[name]['accepted_packets'],'witness':results[name]['mechanism']['status']}),flush=True)
    comparisons={}
    for case in p['cases']:
        a,b=(results[case['id']+'-'+arm] for arm in p['arms'])
        comparisons[case['id']]={'profit_delta_microUSD':b['summary']['profit']-a['summary']['profit'],'paid_job_delta':b['paid_jobs']-a['paid_jobs'],'packet_delta':b['accepted_packets']-a['accepted_packets']}
    summary={'schema':SCHEMA,'scope':p['scope'],'complete':True,'source_sha256':frozen['source']['sha256'],
        'experiment_sha256':digest(frozen['driver_files']),'protocol_sha256':digest(p),'opening_per_world_microUSD':p['opening_microUSD'],'external_funding_microUSD':0,
        'worlds':results,'comparisons':comparisons,'measured_wall_seconds':time.monotonic()-start,
        'process_cpu_seconds':time.process_time()-cpu,'python':sys.version,'actual_customers':0,'actual_profit_microUSD':None,
        'unmeasured_costs':['actual development labor','actual host bill','actual model bill'],'limits':p['limits']}
    write(output/'public'/'RESULT.json',summary)
    write(output/'public'/'MECHANISM.json',retain_mechanism(summary))
    (output/'public'/'PROGRESS.json').unlink(missing_ok=True)
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['run','resume','operate','verify']);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv);output=args.output.absolute()
    if '..' in output.parts or any(p.is_symlink() for p in (output,*output.parents)):raise ValueError('NORMAL_PRIVATE_OUTPUT_REQUIRED')
    if args.command=='verify':
        print(json.dumps(verify(output),sort_keys=True));return 0
    if args.command=='run':
        if output.exists() or not output.parent.is_dir():raise ValueError('FRESH_OUTPUT_REQUIRED')
        source=identity(ROOT);output.mkdir(mode=0o700);(output/'public').mkdir()
        drivers=driver_identity(ROOT)
        for name in set(source['files'])|set(drivers):
            target=output/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
        write(output/'PROTOCOL.json',protocol());write(output/'FREEZE.json',{'source':source,'driver_files':drivers,'protocol_sha256':digest(protocol())})
    if args.command in ('run','resume'):
        return subprocess.call([sys.executable,'-m','experiments.arrangement_cycle046','operate','--output',str(output)],cwd=output/'source')
    execute(output);return 0


if __name__=='__main__':raise SystemExit(main())
