#!/usr/bin/env python3
"""Exposed native channel-menu wiring proof; not a fresh scaling experiment."""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from run_commoncost026 import method_policy,joint_policy,config as common_config
from adaptive_enterprise.instruments import prepare_services
from connected_enterprise.engine import default_config,run_world
from connected_enterprise.runner import identity
from connected_enterprise.verify import audit
from commercial.ledger import digest

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);pub=out/'public';pub.mkdir()
    r={'status':'RUNNING','seed':2610311751,'cohort_seed':2610311751,'scope':'EXPOSED_ENGINEERING_REPRODUCTION_NOT_FRESH_COMMERCIAL_OR_SCALE_CONFIRMATION','checkout_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'workflow_run_id':os.environ.get('GITHUB_RUN_ID'),'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    def write():(pub/'SUMMARY.json').write_text(json.dumps(r,sort_keys=True,indent=2)+'\n')
    write();cpu=time.process_time();wall=time.monotonic()
    try:
        manifest=prepare_services(ROOT,'.channel027-smoke',cohort_seed=r['cohort_seed'])
        cfg=default_config();cfg.update(horizon_days=14,customer_pool=36,arrival_bps=10000,retention_bps=10000,nonpayment_bps=0,price_pressure_bps=10000,clearing_hours=1,initial_slots=2,maximum_slots=3,mechanism_policy=method_policy(),strategic_policy=joint_policy(),strategic_allocation_policy=common_config('smoke','central','joint')['strategic_allocation_policy'])
        cfg['channel_menu_policy']={'schema':'connected-channel-menu/v1','contract_ids':['extended','pilot'],'conversion_bps':4000}
        source=identity(ROOT);r.update(config=cfg,config_sha256=digest(cfg),manifest_sha256=digest(manifest),source=source,policy_factory_sha256=hashlib.sha256((ROOT/'scripts/run_commoncost026.py').read_bytes()).hexdigest());write()
        result=run_world(ROOT,manifest,cfg,r['seed'],'competitive_growth',out/'private',source=source);checked=audit(ROOT,manifest,result)
        if not result['complete'] or not checked['accepted']:raise ValueError('COMPLETE_NATIVE_OPERATING_AUDIT_REQUIRED')
        investments=[{k:i.get(k) for k in ('id','plan_id','kind','contract_id','cost','purchased_time','activation_time','expiry_time')}|{'funding':i.get('funding_receipt',{}).get('funding')} for i in result['investments']]
        if not any(i['kind']=='acquisition' and i['contract_id'] in cfg['channel_menu_policy']['contract_ids'] for i in investments):raise ValueError('NAMED_CHANNEL_NOT_ACTUALLY_PURCHASED')
        r.update(status='COMPLETED',audit=checked,summary=result['summary'],paid_jobs=result['paid_jobs'],investments=investments,result_sha256=digest(result),joint_plans=len(result.get('joint_actions',{})),actual_customers=0,actual_profit=None,evidence_scope='Compact in-job audit, not portable ledger authority. Favorable authored engineering inputs, not a matched profit improvement or complete measured billing claim.')
    except BaseException as exc:r.update(status='FAILED',error=str(exc));raise
    finally:r.update(process_cpu_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-wall);write();print(json.dumps({k:r.get(k) for k in ('status','scope','paid_jobs','error')}))
if __name__=='__main__':main()
