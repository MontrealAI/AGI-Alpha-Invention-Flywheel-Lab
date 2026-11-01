"""Finite source-frozen operation of none, fixed and selective recourse."""
import argparse,copy,hashlib,json,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from commercial.ledger import digest
from connected_enterprise.runner import identity,write
from connected_enterprise.engine import default_config,fresh_account_config,run_world
from connected_enterprise.verify import audit
from adaptive_enterprise.instruments import prepare_complete_offer_services
from portfolio25.pricing import SCENARIOS

PROTOCOL='campaign/selective-recourse-048/PREREGISTRATION.json'
DRIVER='scripts/run_selective_recourse048.py'

def config(manifest,case,arm,p):
    cfg,m=fresh_account_config(manifest,root=ROOT)
    cfg.update(opening=p['opening_microUSD_per_separate_account'],horizon_days=p['horizon_days'],customer_pool=4,initial_slots=3,maximum_slots=3,arrival_bps=10000,retention_bps=10000,nonpayment_bps=0,clearing_hours=1)
    cfg['setup_cost']+=5_000_000;cfg['qualification_cost']+=50_000
    scenarios=copy.deepcopy(list(SCENARIOS))
    for s in scenarios:s.update(repeat_horizon=0,cost_shock=1)
    cfg['strategic_policy']={'schema':'connected-strategic-commerce/v1','public_basis':'Declared independent public two-atom buyer requests and complete outside choice; no private atoms enter policy. Authored engineering comparison.',
        'price_bps':[5500],'rival_price_bps':[10000],'rival_cost_bps':3000,'rival_response':'observed_quote','scenarios':scenarios}
    cfg['strategic_allocation_policy']={'max_customers':1 if case=='no_alternative' else 4,'risk':{'scenarios':{s['id']:round(s['weight']*10000) for s in scenarios},'worst_loss_limit':cfg['opening'],'downside_penalty_bps':2500,'max_states':262144,'authorized_allocation':cfg['opening'],'interactions':[]}}
    services=['reconciliation','kpi_variance','evidence_matrix','receivables_packet']
    values=dict.fromkeys(services,0);values['receivables_packet']=100_000_000 if case!='no_demand' else 0
    profile={'id':'selective048-authored-request','services':services,'price_grids':{s:[50_000_000] if s=='receivables_packet' else [20_000_000] for s in services},
        'atoms':[{'weight_bps':5000,'budget_microUSD':300_000_000,'values':dict.fromkeys(services,0)},{'weight_bps':5000,'budget_microUSD':300_000_000,'values':values}],
        'outside_options':[]}
    requested={f'SIM-customer-{i:03d}':[j['id'] for j in m['jobs'] if sorted(jj['id'] for jj in m['jobs'] if jj['service_id']==j['service_id']).index(j['id'])%4==i] for i in range(4)}
    cfg['complete_offer_policy']={'schema':'connected-complete-offer-market/v1','selection':'menu','profiles':[profile],'requested_jobs':requested}
    if arm=='fixed':cfg['refusal_recourse_policy']={'schema':'connected-refusal-recourse/v1','daily_planning_cost':p['daily_allowance_microUSD']}
    if arm=='selective':cfg['refusal_recourse_policy']={'schema':'connected-selective-refusal-recourse/v2','daily_planning_cost':p['daily_allowance_microUSD'],'daily_evaluation_cost':p['daily_selective_evaluation_microUSD']}
    return cfg,m

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--frozen',action='store_true');args=parser.parse_args()
    output=Path(args.output).resolve()
    if not args.frozen:
        if not output.exists():
            output.mkdir(parents=True);source=identity(ROOT)
            for name in sorted(set(source['files'])|{PROTOCOL,DRIVER}):
                target=output/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
            frozen={'source':source,'protocol_sha256':hashlib.sha256((ROOT/PROTOCOL).read_bytes()).hexdigest(),'driver_sha256':hashlib.sha256((ROOT/DRIVER).read_bytes()).hexdigest(),'registered_before_operation':True}
            frozen['sha256']=digest(frozen);write(output/'FROZEN.json',frozen)
        return subprocess.call([sys.executable,str(output/'source'/DRIVER),'--output',str(output),'--frozen'])
    frozen=json.loads((output/'FROZEN.json').read_text());pin=frozen.pop('sha256')
    if digest(frozen)!=pin or ROOT!=output/'source' or identity(ROOT)!=frozen['source'] or hashlib.sha256((ROOT/PROTOCOL).read_bytes()).hexdigest()!=frozen['protocol_sha256'] or hashlib.sha256((ROOT/DRIVER).read_bytes()).hexdigest()!=frozen['driver_sha256']:raise ValueError('SELECTIVE048_FROZEN_SOURCE_CHANGED')
    p=json.loads((ROOT/PROTOCOL).read_text());manifestpath=output/'MANIFEST.json'
    if not manifestpath.exists():
        m=prepare_complete_offer_services(ROOT,'generated-selective048',cohort_seed=p['service_cohort_seed'],packet_jobs=p['packet_jobs'],packet_rows=p['packet_rows']);write(manifestpath,m)
    m=json.loads(manifestpath.read_text());rows=[];cpu=time.process_time();wall=time.monotonic()
    for case in p['cases']:
        for arm in p['arms']:
            cfg,registered=config(m,case,arm,p);folder=output/'worlds'/case/arm
            try:
                result=run_world(ROOT,registered,cfg,p['seed'],'competitive_growth',folder,source=frozen['source'])
                checked=audit(ROOT,registered,result)
                if not checked['accepted']:raise ValueError('SELECTIVE048_NATIVE_AUDIT_REJECTED')
                row={'case':case,'arm':arm,'accepted_audit':True,'source_sha256':result['source']['sha256'],'config_sha256':digest(cfg),'result_sha256':digest(result),'summary':result['summary'],'paid_deliveries':sum(o['outcome']=='SETTLED' for o in result['orders']),
                    'allowance_microUSD':sum(c['amount'] for c in result['costs'] if c['category']=='prepaid_finite_refusal_recourse'),'evaluation_microUSD':sum(c['amount'] for c in result['costs'] if c['category']=='selective_recourse_public_evaluation'),
                    'selective_purchases':sum(w.get('selective_recourse_decision',{}).get('purchase',False) for w in result['joint_actions'].values()),'account_id':result['owned_account']['ledger']['config']['account_id'] if 'account_id' in result['owned_account']['ledger']['config'] else None}
                print(json.dumps({k:row[k] for k in ('case','arm','paid_deliveries','allowance_microUSD','evaluation_microUSD','summary')},sort_keys=True),flush=True)
            except Exception as error:
                row={'case':case,'arm':arm,'accepted_audit':False,'error':type(error).__name__+':'+str(error),'checkpoint_retained':(folder/'STATE.json').exists()}
                print(json.dumps(row,sort_keys=True),flush=True)
            rows.append(row);write(output/'SUMMARY.json',{'schema':'selective048-native-comparison/v1','protocol_sha256':frozen['protocol_sha256'],'source_sha256':frozen['source']['sha256'],'worlds':rows,'complete':len(rows)==len(p['cases'])*len(p['arms']),'actual_host_model_engineering_billing':None,'scope':p['scope'],'resource_observation':{'process_cpu_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-wall}})
    return 0 if all(r['accepted_audit'] for r in rows) else 1

if __name__=='__main__':raise SystemExit(main())
