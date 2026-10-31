#!/usr/bin/env python3
"""Exposed adverse-world diagnostic, not fresh confirmation or a new champion."""
import argparse,copy,hashlib,json,os,subprocess,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from run_strategic024 import config as prior_config
from adaptive_enterprise.instruments import prepare_services
from connected_enterprise.engine import run_world
from connected_enterprise.runner import identity
from connected_enterprise.verify import audit
from commercial.ledger import digest
ARMS=('original_incumbent','matched_incumbent','quote_only','full_joint')
PROTOCOL={'schema':'strategic025-exposed-adverse-diagnostic/v1','seed':2610311602,'service_cohort_seed':2610311600,'horizon_days':28,'case':'adverse','arms':list(ARMS),
 'status':'EXPOSED_DEVELOPMENT_ABLATION_NOT_FRESH_CONFIRMATION',
 'cost_matching':'original_incumbent preserves published cost treatment; other arms share $80 setup, $0.15 qualification and identical paid method envelopes. Different actual quote/qualification counts and delivery/investment choices remain costs of the tested policies.',
 'interpretation':'matched_incumbent vs original isolates the combined additional cost/method treatment; quote_only vs matched_incumbent changes public strategic quoting while retaining legacy sequential admission/investment rules; full_joint vs quote_only changes joint shortlist allocation/admission and associated qualification workload. Not a fully orthogonal factorial and no standalone critic/invention advantage claim.',
 'outcomes':'Finish the fixed horizon and settlement drain; retain failed and loss-making outcomes. Do not adopt a correction from this exposed world without a separately frozen fresh comparison.',
 'missing_costs':'Actual host/model/integration billing unavailable beyond explicit model envelopes. No real commerce, annualization or billion-dollar scale claim.'}
def config(arm):
    cfg=prior_config('scale','adverse','incumbent' if arm=='original_incumbent' else 'joint')
    if arm=='matched_incumbent':cfg.pop('strategic_policy');cfg.pop('strategic_allocation_policy')
    if arm=='quote_only':cfg.pop('strategic_allocation_policy');cfg['strategic_execution']='sequential'
    return cfg

def main():
    p=argparse.ArgumentParser();p.add_argument('--arm',choices=ARMS,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);public=out/'public';public.mkdir()
    receipt={'protocol':PROTOCOL,'protocol_sha256':digest(PROTOCOL),'arm':a.arm,'status':'RUNNING','checkout_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'workflow_event_sha':os.environ.get('GITHUB_SHA'),'workflow_run_id':os.environ.get('GITHUB_RUN_ID'),'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    write=lambda:(public/'SUMMARY.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    start=time.process_time();wall=time.monotonic();write()
    try:
        manifest=prepare_services(ROOT,'.strategic025-inputs/'+a.arm,cohort_seed=PROTOCOL['service_cohort_seed']);cfg=config(a.arm);source=identity(ROOT)
        receipt.update(config=cfg,config_sha256=digest(cfg),source=source,manifest_sha256=digest(manifest));write()
        result=run_world(ROOT,manifest,cfg,PROTOCOL['seed'],'competitive_growth',out/'private',source=source);checked=audit(ROOT,manifest,result)
        if not result['complete'] or not checked['accepted']:raise ValueError('FULL_HORIZON_AND_OPERATING_AUDIT_REQUIRED')
        if a.arm=='quote_only' and not checked.get('strategic_decisions_rederived'):raise ValueError('SEQUENTIAL_STRATEGIC_PATH_NOT_EXECUTED')
        if a.arm=='full_joint' and not checked.get('joint_plans_rederived'):raise ValueError('JOINT_STRATEGIC_PATH_NOT_EXECUTED')
        receipt.update(status='COMPLETED',audit=checked,summary=result['summary'],paid_jobs=result['paid_jobs'],customers=result['customers'],repeat_customers=result['repeat_customers'],earned_continuations=result['profitable_earned_continuations'],conditional_commercial_success=result['conditional_simulated_commercial_success'],decision_counts=dict(Counter(d.get('kind','unknown') for d in result['decisions'])),
          expense_categories={category:sum(c['amount'] for c in result['costs'] if c['category']==category) for category in {c['category'] for c in result['costs']}},
          orders=[{k:o.get(k) for k in ('id','job_id','customer_id','qualified_time','collection_time','price','complete_cost','fee','outcome')}|{'method':o.get('method_plan',{}).get('mode','default')} for o in result['orders']],
          investments=[{k:i.get(k) for k in ('kind','cost','purchased_time','activation_time','expiry_time','predicted_net')} for i in result['investments']],
          decisions=[{k:d.get(k) for k in ('time','kind','customer_id','service_id','price','public_rival_price','buyer_choice')} for d in result['decisions']],
          evidence_scope='Compact inspected public in-job native and operating audits; not portable independent financial re-audit authority. Source/seed/manifest recipe permits fresh reproduction.',actual_customers=0,actual_profit=None,result_sha256=digest(result))
    except BaseException as exc:
        receipt.update(status='FAILED',error_type=type(exc).__name__,error=str(exc));raise
    finally:
        receipt.update(process_cpu_seconds=time.process_time()-start,wall_seconds=time.monotonic()-wall);write();print(json.dumps({k:receipt.get(k) for k in ('status','arm','paid_jobs','earned_continuations','conditional_commercial_success')}),flush=True)
if __name__=='__main__':main()
