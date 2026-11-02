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

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from adaptive_enterprise.instruments import prepare_services
from connected_enterprise.engine import default_config,run_world
from connected_enterprise.runner import identity
from connected_enterprise.verify import audit
from connected_enterprise.mechanism_choice import MODES
from commercial.ledger import digest
from portfolio25.pricing import SCENARIOS

def inventory_content_fingerprint(manifest):
    """Compare content across staging folders without changing native authority.

    Native admission commits full job rows, including their relative paths.
    Validate that original commitment before making a detached comparison view;
    only that view's three staging paths and path-dependent chunk hashes change.
    Source, seed, order, chunk boundaries, content hashes and other metadata stay.
    Physical source/input integrity remains the native loader/auditor's job.
    """
    from adaptive_enterprise.instruments import _validate_admission
    _validate_admission(manifest)
    jobs=[copy.deepcopy({key:value for key,value in job.items() if key not in {'input','artifact','receipt'}})
          for job in manifest['jobs']]
    cohort=copy.deepcopy(manifest['cohort_provenance'])
    admission=cohort.get('finite_admission')
    if admission is not None:
        for chunk in admission['chunks']:
            start,count=chunk['start'],chunk['count']
            chunk['jobs_sha256']=digest(jobs[start:start+count])
    return digest({'cohort':cohort,'jobs':jobs,'source_hashes':copy.deepcopy(manifest['source_hashes'])})

PROTOCOL={'schema':'commoncost026-public-fresh-comparison/v1',
 'smoke':{'horizon_days':14,'seeds':[2610311740],'cases':['central']},
 'scale':{'horizon_days':28,'seeds':[2610311737,2610311738],'cases':['central','parity','adverse']},
 'arms':['incumbent','joint'], 'service_cohort_seed':2610311735,
 'comparison':'Fresh same market/seed/inventory/opening cash/obligations pairs with common complete direct production envelope. Candidate retains disclosed extra $5 integration and $0.05 per qualification planning envelopes, not measured billing. No incumbent method charge is duplicated. No independent invention advantage claim.',
 'claim':'Fresh fixed modeled comparison of the explicit common-cost contract; not real revenue, annualization, billion-dollar scale or global optimality. All fixed cases retained, including adverse policy losses.',
 'evidence_scope':'Compact summary plus in-job native/operating audit; not a portable independent financial re-audit archive. Public source/protocol supports fresh reproduction. No private account authority uploaded.',
 'missing_costs':'Actual host/model/engineering integration billing unavailable. Explicit model envelopes are assumptions, not zero actual costs.',
 'stop':'Finish every fixed horizon and drain, or retain explicit failure. Never stop on first success or replace unfavorable seeds.'}

def joint_policy():
    scenarios=copy.deepcopy(list(SCENARIOS))
    for s in scenarios:s.update(repeat_horizon=0,cost_shock=1)
    return {'schema':'connected-strategic-commerce/v1','public_basis':'Frozen public independent value/budget range hypotheses; same-value complete-service alternatives. Not realized buyer utility, budget, scenario label or future draw. Rival availability is uncertain, not queried.',
      'price_bps':[5500,6999,8999,9299,9999],'rival_price_bps':[5500,7000,9000,10000],
      'rival_cost_bps':3000,'rival_response':'observed_quote','scenarios':scenarios,'demand_model':'connected_range',
      'connected_beliefs':{s['id']:{'min_value_bps':7000,'max_value_bps':21000,'min_budget_microUSD':0,'max_budget_microUSD':600000000,'rival_available_bps':8000} for s in scenarios}}

def method_policy():
    # Same complete production envelope covers produce+ordinary acceptance for all
    # substituted direct methods. Extra retained/critic work remains separately paid.
    zero={'execution':0,'discovery':0,'integration':0,'verification':0,'maintenance':0,'retrieval':0,'failed_attempts':0}
    costs={m:dict(zero) for m in MODES if m!='hold'}
    costs['ordinary_reuse'].update(retrieval=10000,verification=200000)
    costs['critic_retain'].update(discovery=1000000,integration=500000,failed_attempts=100000,verification=300000,maintenance=10000,retrieval=10000)
    return {'mode':'optimize','costs':costs,'accept_collect_bps':9700,'future_equivalent_jobs':0,
      'cost_contract':{'schema':'connected-method-cost-contract/v1','basis':'COMMON_COMPLETE_PRODUCTION_REPLACEMENT','production_envelope_microUSD':1500000,'covered_operations':['produce','acceptance_check']},
      'public_basis':'Common production envelope covers direct/generated/conventional execution and ordinary acceptance once. No measured savings claimed. Extra critic adjudication/comparison/retention and reused-memory retrieval/revalidation use explicit authored positive envelopes; host/model billing remains unknown.'}

def config(stage,case,arm):
    cfg=default_config();cfg.update(horizon_days=PROTOCOL[stage]['horizon_days'],customer_pool=12)
    if case=='parity':cfg['price_pressure_bps']=7000
    if case=='adverse':cfg.update(nonpayment_bps=1200,clearing_hours=96,retention_bps=8000)
    if arm=='joint':
        cfg['mechanism_policy']=method_policy();cfg['strategic_policy']=joint_policy()
        # Existing pricing extension envelopes reused as explicit new-development
        # assumptions, not measured inference/engineering bills.
        cfg['setup_cost']+=5000000;cfg['qualification_cost']+=50000
        cfg['strategic_allocation_policy']={'max_customers':6,'risk':{
            'scenarios':{'baseline':5000,'ai_parity_price_war':3000,'differentiated_verified_service':2000},
            'worst_loss_limit':cfg['opening'],'downside_penalty_bps':2500,'max_states':262144,
            'authorized_allocation':cfg['opening'],'interactions':[]}}
    return cfg

def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['smoke','scale'],required=True)
    p.add_argument('--case',choices=['central','parity','adverse'],required=True);p.add_argument('--seed',type=int,required=True)
    p.add_argument('--arm',choices=PROTOCOL['arms'],required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.seed not in PROTOCOL[a.stage]['seeds'] or a.case not in PROTOCOL[a.stage]['cases']:raise ValueError('OUTSIDE_FIXED_PUBLIC_PROTOCOL')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    public=out/'public';public.mkdir()
    receipt={'protocol':PROTOCOL,'protocol_sha256':digest(PROTOCOL),'stage':a.stage,'case':a.case,'seed':a.seed,'arm':a.arm,
             'checkout_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'workflow_event_sha':os.environ.get('GITHUB_SHA'),'workflow_run_id':os.environ.get('GITHUB_RUN_ID'),
             'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'status':'RUNNING'}
    write=lambda:(public/'SUMMARY.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    write();start=time.process_time();wall=time.monotonic()
    try:
        relative='.commoncost026-inputs/'+a.stage+'-'+a.case+'-'+str(a.seed)+'-'+a.arm
        manifest=prepare_services(ROOT,relative,cohort_seed=PROTOCOL['service_cohort_seed'])
        cfg=config(a.stage,a.case,a.arm);source=identity(ROOT)
        receipt.update(inventory_count=len(manifest['jobs']),inventory_fingerprint=inventory_content_fingerprint(manifest),config=cfg,config_sha256=digest(cfg),source=source,manifest_sha256=digest(manifest));write()
        result=run_world(ROOT,manifest,cfg,a.seed,'competitive_growth',out/'private',source=source)
        checked=audit(ROOT,manifest,result)
        joint=result.get('joint_actions',result.get('operating_state',{}).get('joint_actions',{}))
        if a.arm=='joint' and not joint:raise ValueError('JOINT_OPERATING_PATH_NOT_EXECUTED')
        if not result['complete'] or not checked['accepted']:raise ValueError('FULL_HORIZON_AND_OPERATING_AUDIT_REQUIRED')
        receipt.update(status='COMPLETED',complete=True,audit=checked,summary=result['summary'],
          paid_jobs=result['paid_jobs'],customers=result['customers'],repeat_customers=result['repeat_customers'],
          profitable_earned_continuations=result['profitable_earned_continuations'],
          conditional_simulated_commercial_success=result['conditional_simulated_commercial_success'],
          actual_collections=0,actual_profit=None,result_sha256=digest(result),
          orders=[{k:o.get(k) for k in ('id','job_id','customer_id','price','complete_cost','fee','outcome','qualified_time','collection_time')}|{'method':o.get('method_plan',{}).get('mode','default')} for o in result['orders']],
          investments=[{k:i.get(k) for k in ('plan_id','kind','cost','activation_time','expiry_time')} for i in result['investments']],
          joint_decision_count=len(joint),
          decision_counts=dict(Counter(d.get('kind','unknown') for d in result['decisions'])),
          joint_combinations=[{'time':v['time'],'states_evaluated':v['allocation']['decision']['states_evaluated'],
              'selected':v['allocation']['decision']['selected'],'scope':v['allocation']['decision']['optimality_scope'],
              'risk_scope':v['allocation']['risk_scope']} for v in joint.values()],
          obligations={k:result['summary'].get(k) for k in ('cash','available','payables','custodyReserve','tailReserve','workingCapital','reservedInvestment','unrestrictedEarned')},
          finance_identities={'revenue_minus_expenses':result['summary']['revenue']-result['summary']['expenses'],
                              'reported_profit':result['summary']['profit'],
                              'cash_covers_custody_tail_and_working_only':result['summary']['cash']>=sum(result['summary'][k] for k in ('custodyReserve','tailReserve','workingCapital'))})
    except BaseException as exc:
        receipt.update(status='FAILED',error_type=type(exc).__name__,error=str(exc));raise
    finally:
        receipt.update(process_cpu_seconds=time.process_time()-start,wall_seconds=time.monotonic()-wall)
        write()
        print(json.dumps({k:receipt.get(k) for k in ('status','stage','case','seed','arm','paid_jobs','conditional_simulated_commercial_success','process_cpu_seconds')}),flush=True)

if __name__=='__main__':main()
