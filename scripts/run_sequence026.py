#!/usr/bin/env python3
"""Fixed public sequence integration comparison; synthetic, not scale qualification."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from run_commoncost026 import config as prior_config
from run_strategic024 import PROTOCOL as PRIOR_PROTOCOL
from adaptive_enterprise.instruments import prepare_services
from connected_enterprise.engine import run_world
from connected_enterprise.runner import identity
from connected_enterprise.verify import audit
from commercial.ledger import digest

PROTOCOL={'schema':'sequence026-current-menu-composition-development/v2',
 'repair_edition':{'prior_head':'80531c99b1f4f3712c67de8b9452262260df8ff7','prior_run':41240919851,'failure':'menu_overlap_wiring_fixture/sequence FINITE_COSTED_INVESTMENTS_REQUIRED','change':'Remove obsolete raw-nine investment wrapper ceiling; unchanged total128 option and explicit max_states bounds. Same fixed eight cases/arms/seed, now exposed reproduction after repair, not fresh confirmation.'},
 'registration_change':'Before any new composition campaign outcomes, reduce 16 proposed worlds to8 for fast decisive integration: one exposed seed, old single-pilot control, real-menu central, overlap wiring and adverse worlds, each joint/sequence matched. Old evidence remains untouched.',
 'source_scope':'Rebased current runtime and common production contract; old PR44 results remain exposed historical evidence, not results for this source.',
 'horizon_days':14,'seeds':[2610311726],
 'arms':['joint','sequence'],'cases':['central','menu_central','menu_overlap_wiring_fixture','menu_adverse'],
 'hypotheses':{'schema':'public-sequence-window/v1','provenance':'Authored uncertain future-window availability/service/arrival and rival-price hypotheses. No private future draws, calibrated demand or future income authority.','window_delay_days':3,'owned_contact_count':4,'owned_available_bps':2500,'service_share_bps':3333,'arrival_bps':7000,'future_rival_price_bps':9000},
 'channel_forecast':'Menu arms reuse actual ChannelBook transitions under four fixed declared public surrogate seeds, never actual future draws. All intervening attempts are charged; only final-window delivery credited. This is an uncalibrated conservative scenario approximation, not an optimal full-horizon policy.',
 'limits':'Developer-authored two-stage composition, not autonomous mechanism invention, inherited discovery advantage, global optimum, annual scale or actual commerce. Future costs conservatively prefunded after max commitments of all current shortlisted customers. Low-invoice fixture only tests purchase wiring, never economic confirmation.',
 'evidence_scope':'Compact in-job financial/operating audits and hashes, not a portable independent replay archive. No private authority or customer inputs exported.',
 'stop':'All fixed cases/seeds/arms complete or publish explicit failure. Do not replace bad outcomes.'}


def config(case,arm):
    cfg=prior_config('smoke','central','joint')
    if case=='low_invoice_wiring_fixture':
        cfg['setup_cost']=0;cfg['capacity_price']=1_000_000
        cfg['channels']['pilot'].update(price_microUSD=1_000_000,support_microUSD=0)
    if case in ('menu_central','menu_overlap_wiring_fixture','menu_adverse'):
        cfg['channel_menu_policy']={'schema':'connected-channel-menu/v1','contract_ids':['extended','pilot'],'conversion_bps':4000}
        if case=='menu_overlap_wiring_fixture':
            cfg['setup_cost']=0;cfg['capacity_price']=1_000_000
            cfg['channels']['pilot'].update(price_microUSD=1_000_000,support_microUSD=0,duration_days=5,contact_cooldown_days=2)
            cfg['channels']['extended'].update(price_microUSD=1_250_000,support_microUSD=0,lead_days=1,duration_days=5,contact_cooldown_days=2)
    if case=='menu_adverse':cfg.update(nonpayment_bps=1200,clearing_hours=96,retention_bps=8000,price_pressure_bps=7000)
    if arm=='sequence':
        cfg['strategic_allocation_policy']['sequence']=dict(PROTOCOL['hypotheses'])
        if case in ('low_invoice_wiring_fixture','menu_overlap_wiring_fixture'):
            cfg['strategic_allocation_policy']['sequence'].update(service_share_bps=10000,owned_available_bps=5000)
    return cfg


def main():
    p=argparse.ArgumentParser();p.add_argument('--case',choices=PROTOCOL['cases'],required=True)
    p.add_argument('--arm',choices=PROTOCOL['arms'],required=True);p.add_argument('--seed',type=int,choices=PROTOCOL['seeds'],required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    out=args.output.resolve();out.mkdir(exist_ok=False,parents=True);public=out/'public';public.mkdir()
    r={'protocol':PROTOCOL,'protocol_sha256':digest(PROTOCOL),'case':args.case,'seed':args.seed,'arm':args.arm,
       'status':'RUNNING','checkout_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
       'workflow_run_id':os.environ.get('GITHUB_RUN_ID'),'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
       'policy_factory_sha256':hashlib.sha256(Path(__file__).with_name('run_commoncost026.py').read_bytes()).hexdigest()}
    def save():(public/'SUMMARY.json').write_text(json.dumps(r,sort_keys=True,indent=2)+'\n')
    start=time.process_time();wall=time.monotonic();save()
    try:
        manifest=prepare_services(ROOT,'.sequence026-inputs/'+args.case+'-'+args.arm+'-'+str(args.seed),cohort_seed=PRIOR_PROTOCOL['service_cohort_seed'])
        cfg=config(args.case,args.arm);source=identity(ROOT)
        r.update(config=cfg,config_sha256=digest(cfg),source=source,manifest_sha256=digest(manifest));save()
        result=run_world(ROOT,manifest,cfg,args.seed,'competitive_growth',out/'private',source=source)
        checked=audit(ROOT,manifest,result)
        resumed=run_world(ROOT,manifest,cfg,args.seed,'competitive_growth',out/'private',source=source)
        resumed_audit=audit(ROOT,manifest,resumed)
        stable=('summary','investments','orders','events')
        if (any(result[k]!=resumed[k] for k in stable) or
            checked['native_actions_sha256']!=resumed_audit['native_actions_sha256'] or
            not resumed_audit['accepted']):
            raise ValueError('COMPLETED_RESUME_CHANGED_FINANCES_OR_CONTRACTS')
        if not result['complete'] or not checked['accepted']:raise ValueError('COMPLETE_NATIVE_OPERATING_AUDIT_REQUIRED')
        r.update(status='COMPLETED',summary=result['summary'],audit=checked,complete=True,
            paid_jobs=result['paid_jobs'],profitable_earned_continuations=result['profitable_earned_continuations'],
            conditional_simulated_commercial_success=result['conditional_simulated_commercial_success'],
            resume_financially_unchanged=True,resume_native_and_operating_unchanged=True,
            resumed_audit_sha256=digest(resumed_audit),result_sha256=digest(result),
            investments=[{k:i[k] for k in ('id','kind','cost','purchased_time','activation_time','expiry_time')} for i in result['investments']],
            sequence_routes=[{'time':x['time'],'first_actions':[{'id':o['id'],'kind':o['execution']['first_investment'],'contingent_capacity':o['execution']['contingent_capacity']} for o in x['allocation']['decision']['selected_options'] if 'first_investment' in o['execution']]} for x in result['joint_actions'].values()],
            actual_profit=None,actual_collections=0,missing_costs='Host/model and engineering billing unmeasured; existing explicit modeled envelopes, not zero actual cost.')
    except BaseException as e:
        r.update(status='FAILED',error_type=type(e).__name__,error=str(e));raise
    finally:
        r.update(process_cpu_seconds=time.process_time()-start,wall_seconds=time.monotonic()-wall);save()


if __name__=='__main__':main()
