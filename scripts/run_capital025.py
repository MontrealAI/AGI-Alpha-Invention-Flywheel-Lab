#!/usr/bin/env python3
"""Fresh-account finite capital-package comparison, never migration or live finance."""
import argparse
from collections import Counter
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from adaptive_enterprise.instruments import prepare_services
from connected_enterprise.engine import default_config,run_world
from connected_enterprise.runner import identity
from connected_enterprise.verify import audit
from connected_enterprise.capital_lifecycle import default_policy,validate_policy
from commercial.ledger import digest,canonical
from run_strategic024 import joint_policy,method_policy

PROTOCOL={'schema':'capital025-fresh-native-package/v1',
 'integration':{'horizon_days':14,'seeds':[2610311643],'capitals':['low']},
 'long':{'horizon_days':98,'seeds':[2610311644,2610311645],'capitals':['low','reference']},
 'policies':['incumbent','joint'],'liabilities':['permanent','prospective'],
 'opening_microUSD':{'low':250000000,'reference':5000000000},'working_microUSD':25000000,
 'jobs_per_service':96,'service_cohort_seed':2610311642,'cash_diagnostic_available':100000000000,
 'liability_package':{'protection_hours':72,'residual_microUSD':1000000,'premium_microUSD':250000,'coverage_limit_microUSD':0},
 'comparison':'Fresh native accounts; same opportunities, inventory, capital and market within each four-arm cell. Financing package differs in premium/residual/finite liability promises: not a pure maturity effect or equivalent insurance guarantee.',
 'claim':'Conditional modeled native capital/strategy development experiment. Current28day data shows reserve growth, not binding cash. Require observed cash-caused deferrals before claiming maturity enables activity.',
 'inventory':'Equal predeclared96 synthetic jobs per service, generated and checked before operation. Not market demand or free operating capacity; actual service production and investment costs remain native. Generator CPU is recorded, billing unavailable.',
 'accounting':'Recognized modeled revenue minus incurred modeled expenses. Principal locks are not expenses; maturity cannot create cash or profit. Outstanding claims/residual obligations survive.',
 'limits':['No real commerce, insurance, legal finality, paid inference or outside spend.','Actual host/model/engineering billing unavailable beyond explicit envelopes.','No pooling different capital scenarios, annualization, billion-dollar qualification or universal game equilibrium.','Finite prospective liabilities are authored contract assumptions, not validated real-world risk transfer.'],
 'stop':'Every fixed admission horizon plus settlement/maturity drain completes or retains explicit failure; no favorable seed replacement or early success stop.'}

def config(stage,capital,policy,liability):
    cfg=default_config();cfg.update(horizon_days=PROTOCOL[stage]['horizon_days'],customer_pool=12,
      opening=PROTOCOL['opening_microUSD'][capital],working=PROTOCOL['working_microUSD'],cash_diagnostic_available=PROTOCOL['cash_diagnostic_available'])
    if policy=='joint':
        cfg['mechanism_policy']=method_policy();cfg['strategic_policy']=joint_policy()
        cfg['setup_cost']+=5000000;cfg['qualification_cost']+=50000
        cfg['strategic_allocation_policy']={'max_customers':6,'risk':{'scenarios':{'baseline':5000,'ai_parity_price_war':3000,'differentiated_verified_service':2000},'worst_loss_limit':cfg['opening'],'downside_penalty_bps':2500,'max_states':262144,'authorized_allocation':cfg['opening'],'interactions':[]}}
    if liability=='prospective':
        terms=default_policy();terms.update(PROTOCOL['liability_package']);cfg['prospective_policy']=validate_policy(terms)
        cfg['limits']=[x for x in cfg['limits'] if 'Permanent native principal' not in x]+['Authored finite-liability package with 72-hour protection after deadline, retained $1 residual and $0.25 modeled premium; coverage 0. Not insurance or legal finality.']
    return cfg

def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['integration','long'],required=True)
    p.add_argument('--capital',choices=['low','reference'],required=True);p.add_argument('--policy',choices=PROTOCOL['policies'],required=True)
    p.add_argument('--liability',choices=PROTOCOL['liabilities'],required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.seed not in PROTOCOL[a.stage]['seeds'] or a.capital not in PROTOCOL[a.stage]['capitals']:raise ValueError('OUTSIDE_FROZEN_CAPITAL_PROTOCOL')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);public=out/'public';public.mkdir()
    receipt={'protocol':PROTOCOL,'protocol_sha256':digest(PROTOCOL),'stage':a.stage,'capital':a.capital,'policy':a.policy,'liability':a.liability,'seed':a.seed,
      'checkout_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'workflow_event_sha':os.environ.get('GITHUB_SHA'),'workflow_run_id':os.environ.get('GITHUB_RUN_ID'),
      'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'policy_factory_sha256':hashlib.sha256((ROOT/'scripts/run_strategic024.py').read_bytes()).hexdigest(),'status':'RUNNING',
      'evidence_scope':'Compact summary with in-job native/operating audit; not a portable independent financial audit archive. No account key or raw authority uploaded.'}
    write=lambda:(public/'SUMMARY.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    write();cpu=time.process_time();wall=time.monotonic()
    try:
        cfg=config(a.stage,a.capital,a.policy,a.liability)
        relative='.capital025-inputs/'+'-'.join([a.stage,a.capital,a.policy,a.liability,str(a.seed)])
        manifest=prepare_services(ROOT,relative,cohort_seed=PROTOCOL['service_cohort_seed'],jobs_per_service=PROTOCOL['jobs_per_service'])
        if a.liability=='prospective':manifest['native_engine']='prospective-v1'
        (ROOT/relative/'MANIFEST.json').write_bytes(canonical(manifest)+b'\n')
        inventory_fingerprint=digest({'cohort':manifest['cohort_provenance'],'jobs':[{k:v for k,v in job.items() if k not in {'input','artifact','receipt'}} for job in manifest['jobs']]})
        source=identity(ROOT);receipt.update(inventory_fingerprint=inventory_fingerprint,config=cfg,config_sha256=digest(cfg),source=source,manifest_sha256=digest(manifest),inventory_count=len(manifest['jobs']),inventory_generation=manifest['resource_receipt']);write()
        result=run_world(ROOT,manifest,cfg,a.seed,'competitive_growth',out/'private',source=source)
        checked=audit(ROOT,manifest,result)
        if not result['complete'] or not checked['accepted']:raise ValueError('COMPLETE_NATIVE_OPERATING_AUDIT_REQUIRED')
        joint=result.get('joint_actions',{})
        if a.policy=='joint' and not joint:raise ValueError('JOINT_PATH_NOT_EXECUTED')
        s=result['summary'];diagnostics=result.get('capital_metrics')
        if diagnostics is None:raise ValueError('AUDITABLE_CAPITAL_METRICS_REQUIRED')
        receipt.update(status='COMPLETED',audit=checked,summary=s,capital_metrics=diagnostics,
          paid_jobs=result['paid_jobs'],customers=result['customers'],repeat_customers=result['repeat_customers'],profitable_earned_continuations=result['profitable_earned_continuations'],
          conditional_simulated_commercial_success=result['conditional_simulated_commercial_success'],actual_collections=0,actual_profit=None,
          decision_counts=dict(Counter(d.get('kind','unknown') for d in result['decisions'])),
          orders=[{k:o.get(k) for k in ('id','job_id','customer_id','price','complete_cost','fee','premium','outcome','qualified_time','collection_time','maturity_time')}|{'method':o.get('method_plan',{}).get('mode','default'),'terms_sha256':o.get('terms_sha256')} for o in result['orders']],
          investments=[{k:i.get(k) for k in ('plan_id','kind','cost','activation_time','expiry_time')} for i in result['investments']],
          obligations={k:s.get(k) for k in ('cash','available','payables','custodyReserve','tailReserve','workingCapital','reservedInvestment','unrestrictedEarned')},
          result_sha256=digest(result),joint_decision_count=len(joint))
    except BaseException as exc:receipt.update(status='FAILED',error_type=type(exc).__name__,error=str(exc));raise
    finally:
        receipt.update(process_cpu_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-wall);write()
        print(json.dumps({k:receipt.get(k) for k in ('status','stage','capital','policy','liability','seed','paid_jobs','conditional_simulated_commercial_success','process_cpu_seconds')}),flush=True)
if __name__=='__main__':main()
