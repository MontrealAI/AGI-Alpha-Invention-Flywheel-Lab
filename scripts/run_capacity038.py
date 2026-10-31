#!/usr/bin/env python3
"""Finite public development comparison; exact source, no live account export.

Run each case/seed/arm in a fresh Actions job. No best-seed selection or early
success termination. Results are conditional native SIM, never actual commerce.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
import time
import resource

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from adaptive_enterprise.instruments import prepare_complete_offer_services
from connected_enterprise.engine import default_config,run_world
from connected_enterprise.runner import identity
from connected_enterprise.verify import audit
from commercial.ledger import digest
from connected_enterprise.scale import trailing_profit
from outcome_receipts import customer_outcomes

PROTOCOL={'schema': 'capacity038-comparison/v1', 'status': 'FROZEN', 'horizon_days': 42, 'pairs': [{'case': 'positive', 'seed': 2610312311}, {'case': 'positive', 'seed': 2610312312}, {'case': 'costly_capacity', 'seed': 2610312311}, {'case': 'self_service_no_retention', 'seed': 2610312312}], 'arms': ['incumbent', 'quantity'], 'service_cohort_seed': 2610312309, 'jobs_per_service': 128, 'packet_jobs': 128, 'packet_rows': 40, 'customer_pool': 48, 'opening_microUSD': 5000000000, 'working_microUSD': 25000000, 'common_packet_development_microUSD': 50000000, 'quantity_implementation_microUSD': 5000000, 'financial_package': 'Matched existing permanent native liability package. No reliance on incomplete capital025 qualification.', 'comparison': 'Both use complete-offer menu. One-unit legacy capacity heuristic vs quantity-aware observed-backlog recourse. Only capacity policy and disclosed $5 treatment implementation envelope differ.', 'forecast_scope': 'Authored retention9000bps, current observed unserved finite menu, same next-opportunity24h and production duration. No invented future requests or projected receipts funding current commitments. Hard control jointly changes self-service competitiveness and actual/forecast retention to0; not isolated effects.', 'cost_scope': 'Same $50 packet-development envelope both arms; quantity extra$5. Production/components, evaluated offers, fees/tax/support/refunds/acquisition/capacity incurred natively. Actual host/model/engineering billing unknown; no measured frontier-model performance.', 'claim': '42-day native conditional operating-volume and capacity comparison, not annual or billion-scale profit or actual commerce.', 'evidence_scope': 'Compact source-bound in-job audits, not portable independent financial re-audit; no private native authority or large logs.', 'stop': 'Exactly8worlds; preserve losses/failures. No automatic expansion or favorable-world selection. Existing16-day engineering proof and essential capacity/finance tests prerequisite; no separate economic smoke.'}

from run_commoncost026 import method_policy,joint_policy
SERVICES=['reconciliation','kpi_variance','evidence_matrix','receivables_packet']

def request_mapping(jobs):
    return {f'SIM-customer-{i:03d}':[j['id'] for service in SERVICES for n,j in enumerate(sorted((x for x in jobs if x['service_id']==service),key=lambda x:x['id'])) if n%PROTOCOL['customer_pool']==i] for i in range(PROTOCOL['customer_pool'])}

def profile(case):
    # Independent outcome values and budgets: neither is derived from our price.
    atoms=[{'weight_bps':3000,'budget_microUSD':180000000,'values':{'reconciliation':25000000,'kpi_variance':20000000,'evidence_matrix':20000000,'receivables_packet':45000000}},
           {'weight_bps':4000,'budget_microUSD':400000000,'values':{'reconciliation':45000000,'kpi_variance':35000000,'evidence_matrix':35000000,'receivables_packet':120000000}},
           {'weight_bps':3000,'budget_microUSD':800000000,'values':{'reconciliation':60000000,'kpi_variance':50000000,'evidence_matrix':50000000,'receivables_packet':200000000}}]
    outside=[]
    for service in SERVICES:
        packet=service=='receivables_packet'
        for provider,price,quality,effort in [('human',120000000 if packet else 45000000,10000,0),('rival',85000000 if packet else 30000000,10000,0),('self_service',10000000 if packet else 3000000,8000,20000000 if packet else 12000000)]:
            if case=='self_service_no_retention' and provider=='self_service':quality=10000;effort=2000000
            outside.append({'name':provider+'-'+service,'provider':provider,'service_id':service,'price':price,'quality_bps':quality,'delay_cost':effort})
    return {'id':'declared-'+case,'services':SERVICES,'price_grids':{s:([30000000,50000000,75000000] if s=='receivables_packet' else [15000000,25000000]) for s in SERVICES},'atoms':atoms,'outside_options':outside}

def config(stage,case,arm,jobs):
    cfg=default_config();cfg.update(horizon_days=PROTOCOL['horizon_days'],customer_pool=PROTOCOL['customer_pool'],opening=PROTOCOL['opening_microUSD'],working=PROTOCOL['working_microUSD'],initial_slots=3,maximum_slots=12)
    if case=='costly_capacity':cfg['capacity_price']=40000000
    if case=='self_service_no_retention':cfg['retention_bps']=0
    cfg['mechanism_policy']=method_policy();cfg['strategic_policy']=joint_policy()
    cfg['setup_cost']+=5000000+PROTOCOL['common_packet_development_microUSD']+(PROTOCOL['quantity_implementation_microUSD'] if arm=='quantity' else 0);cfg['qualification_cost']+=50000
    cfg['strategic_allocation_policy']={'max_customers':4,'risk':{'scenarios':{'baseline':5000,'ai_parity_price_war':3000,'differentiated_verified_service':2000},'worst_loss_limit':cfg['opening'],'downside_penalty_bps':2500,'max_states':262144,'authorized_allocation':cfg['opening'],'interactions':[]}}
    cfg['channel_menu_policy']={'schema':'connected-channel-menu/v1','contract_ids':['extended','pilot'],'conversion_bps':4000}
    cfg['complete_offer_policy']={'schema':'connected-complete-offer-market/v1','selection':'menu','profiles':[profile(case)],'requested_jobs':request_mapping(jobs)}
    if arm=='quantity':cfg['strategic_allocation_policy']['capacity_menu']={'max_quantity':6,'opportunity_delay_hours':24,'retention_bps':0 if case=='self_service_no_retention' else 9000}
    if cfg['production_hours']>24 or cfg['capacity_lead_hours']>24:raise ValueError('DECLARED_RECOURSE_INTERVAL_INCOMPATIBLE')
    return cfg

def cpu_usage():
    own,children=resource.getrusage(resource.RUSAGE_SELF),resource.getrusage(resource.RUSAGE_CHILDREN)
    return {'self_user':own.ru_utime,'self_system':own.ru_stime,'children_user':children.ru_utime,'children_system':children.ru_stime}

def cpu_delta(before,after):
    values={k:after[k]-before[k] for k in before}
    if any(v<0 for v in values.values()):raise ValueError('NONMONOTONIC_KERNEL_COUNTER')
    return dict(values,total_cpu_seconds=sum(values.values()),scope='POSIX self plus waited children CPU; no host/model billing or human-time inference')

def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['scale'],required=True)
    p.add_argument('--case',choices=['positive','costly_capacity','self_service_no_retention'],required=True);p.add_argument('--seed',type=int,required=True)
    p.add_argument('--arm',choices=PROTOCOL['arms'],required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if PROTOCOL['status']!='FROZEN':raise ValueError('DRAFT_PROTOCOL_NO_EXECUTION')
    if {'case':a.case,'seed':a.seed} not in PROTOCOL['pairs']:raise ValueError('OUTSIDE_FIXED_PUBLIC_PROTOCOL')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    public=out/'public';public.mkdir()
    receipt={'protocol':PROTOCOL,'protocol_sha256':digest(PROTOCOL),'stage':a.stage,'case':a.case,'seed':a.seed,'arm':a.arm,
             'checkout_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'workflow_event_sha':os.environ.get('GITHUB_SHA'),'workflow_run_id':os.environ.get('GITHUB_RUN_ID'),
             'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'policy_factory_sha256':hashlib.sha256((ROOT/'scripts/run_commoncost026.py').read_bytes()).hexdigest(),'status':'RUNNING','phase_cpu':{}}
    write=lambda:(public/'SUMMARY.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    write();start=time.process_time();wall=time.monotonic();kernel_start=cpu_usage()
    try:
        relative='.capacity038-inputs/'+a.stage+'-'+a.case+'-'+str(a.seed)+'-'+a.arm
        phase=cpu_usage();manifest=prepare_complete_offer_services(ROOT,relative,cohort_seed=PROTOCOL['service_cohort_seed'],jobs_per_service=PROTOCOL['jobs_per_service'],packet_jobs=PROTOCOL['packet_jobs'],packet_rows=PROTOCOL['packet_rows'])
        receipt['phase_cpu']['inventory']=cpu_delta(phase,cpu_usage())
        cfg=config(a.stage,a.case,a.arm,manifest['jobs']);source=identity(ROOT)
        receipt.update(request_inventory=[{'id':j['id'],'service_id':j['service_id']} for j in manifest['jobs']],inventory_count=len(manifest['jobs']),inventory_fingerprint=digest({'cohort':manifest['cohort_provenance'],'jobs':[{k:v for k,v in job.items() if k not in {'input','artifact','receipt'}} for job in manifest['jobs']]}),config=cfg,config_sha256=digest(cfg),source=source,manifest_sha256=digest(manifest));write()
        phase=cpu_usage();result=run_world(ROOT,manifest,cfg,a.seed,'competitive_growth',out/'private',source=source)
        receipt['phase_cpu']['native_operation_and_observed_metrics']=cpu_delta(phase,cpu_usage())
        phase=cpu_usage();checked=audit(ROOT,manifest,result)
        receipt['phase_cpu']['canonical_financial_operating_audit']=cpu_delta(phase,cpu_usage())
        joint=result.get('joint_actions',result.get('operating_state',{}).get('joint_actions',{}))
        if not joint:raise ValueError('JOINT_OPERATING_PATH_NOT_EXECUTED')
        if not result['complete'] or not checked['accepted']:raise ValueError('FULL_HORIZON_AND_OPERATING_AUDIT_REQUIRED')
        phase=cpu_usage();profit_observer=trailing_profit(result['owned_account']['ledger'],operating_end_hour=cfg['horizon_days']*24,operating_complete=result['complete'])
        outcomes=customer_outcomes(result,checked)
        receipt['phase_cpu']['compact_profit_and_outcome_observers']=cpu_delta(phase,cpu_usage())
        receipt.update(status='COMPLETED',complete=True,audit=checked,summary=result['summary'],
          paid_jobs=result['paid_jobs'],customers=result['customers'],repeat_customers=result['repeat_customers'],
          profitable_earned_continuations=result['profitable_earned_continuations'],
          conditional_simulated_commercial_success=result['conditional_simulated_commercial_success'],
          actual_collections=0,actual_profit=None,result_sha256=digest(result),
          trailing_profit=profit_observer,customer_outcomes=outcomes,capital_metrics=result.get('capital_metrics'),
          optional_cash_diagnostic_status='UNAVAILABLE_NOT_REQUESTED',
          productive_expansion=result['productive_expansion'],
          expense_category_scope='Operating cost-event projection; canonical native expenses and incurred obligations are authoritative, not assumed exhaustive category reconciliation',
          expense_categories={k:sum(c['amount'] for c in result['costs'] if c['category']==k) for k in sorted({c['category'] for c in result['costs']})},
          orders=[{k:o.get(k) for k in ('id','job_id','customer_id','price','complete_cost','fee','outcome','qualified_time','collection_time','capacity_units','work_keys','production_time','capacity_source_plan_ids')}|{'method':o.get('method_plan',{}).get('mode','default'),'service_id':o['offer']['service_id']} for o in result['orders']],
          investments=[{k:i.get(k) for k in ('plan_id','kind','contract_id','cost','purchased_time','activation_time','expiry_time','capacity_units','predicted_net')} for i in result['investments']],
          capacity_forecasts=[{'time':v['time'],'recourse':v['capacity_recourse']['recourse'],'option_count':len(v['capacity_recourse']['options']),'inputs_sha256':v['capacity_recourse']['inputs_sha256'],'scope':v['capacity_recourse']['scope']} for v in joint.values() if v.get('capacity_recourse')],
          capacity_realization_scope='Native quantity invoices/activation/expiry and order source IDs; later settled collections are attributed links, not isolated incremental causal profit. Forecast net is not income.',
          joint_decision_count=len(joint),
          decision_counts=dict(Counter(d.get('kind','unknown') for d in result['decisions'])),
          joint_combinations=[{'time':v['time'],'states_evaluated':v['allocation']['decision']['states_evaluated'],
              'selected':v['allocation']['decision']['selected'],'scope':v['allocation']['decision']['optimality_scope'],
              'risk_scope':v['allocation']['risk_scope']} for v in joint.values()],
          obligations={k:result['summary'].get(k) for k in ('cash','available','payables','custodyReserve','tailReserve','workingCapital','reservedInvestment','unrestrictedEarned')},
          finance_identities={'recognized_revenue_plus_recovery_minus_expenses':result['summary']['revenue']+result['summary'].get('recoveryIncome',0)-result['summary']['expenses'],
                              'reported_profit':result['summary']['profit'],
                              'cash_covers_custody_tail_and_working_only':result['summary']['cash']>=sum(result['summary'][k] for k in ('custodyReserve','tailReserve','workingCapital'))})
    except BaseException as exc:
        receipt.update(status='FAILED',error_type=type(exc).__name__,error=str(exc));raise
    finally:
        receipt.update(process_cpu_seconds=time.process_time()-start,wall_seconds=time.monotonic()-wall,kernel_cpu=cpu_delta(kernel_start,cpu_usage()))
        write()
        print(json.dumps({k:receipt.get(k) for k in ('status','stage','case','seed','arm','paid_jobs','conditional_simulated_commercial_success','process_cpu_seconds')}),flush=True)

if __name__=='__main__':main()
