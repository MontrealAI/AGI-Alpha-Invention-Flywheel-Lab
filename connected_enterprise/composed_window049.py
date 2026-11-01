"""Finite source-frozen comparison over the canonical enterprise, never a ledger."""
from __future__ import annotations
import argparse,copy,json,shutil,tempfile
from pathlib import Path
from commercial.ledger import digest,strict_json
from commercial.persistence import atomic_bytes
from .cooperation044 import configuration as prior_configuration,_inventory_identity
from .runner import identity,source_paths
ROOT=Path(__file__).resolve().parents[1]
PROTOCOL={'schema':'agi-alpha/composed-window049/v1','seed':2611010491,'cohort_seed':2611010492,'horizon_days':21,'opening_microUSD':100000000000,'customer_pool':8,'packet_jobs':24,'packet_rows':12,'jobs_per_service':32,'cases':['central','no_demand'],'arms':['conventional','composed'],'primary_metric':'Whole-account native recognized revenue plus recovery minus incurred expenses after drain; not annualized.','evidence_role':'EXPOSED_FINITE_ENGINEERING_COMPARISON_NOT_FRESH_CONFIRMATION','comparison':'Existing exact quantity/follower-game/current-channel-menu incumbent versus the same allowed contracts and public market plus composed one-window forecast. Same public authored hypotheses are disclosed for both; only candidate consumes them through sequence_options. This pair is not the requested full five-policy factorial and cannot establish general joint-policy superiority.','costs':'Common native modeled acquisition, production, checking, support, fee, tax, failure, maintenance and protected obligations; candidate pays extra5USD setup and0.05USD daily planning. Actual host/model/engineering billing remains unknown.','public_window':{'schema':'public-sequence-window/v1','composition':'complete-offer-quantity-v1','provenance':'Fixed authored availability/service/arrival assumptions and paired public contact seeds; no realized future draws or calibrated demand.','window_delay_days':3,'owned_contact_count':4,'owned_available_bps':2500,'service_share_bps':10000,'arrival_bps':7000,'future_rival_price_bps':9000},'stop':'Exactly these four separate fresh accounts through21 operating days plus normal drain, or authentic checkpoint on interruption; no seed replacement, losing-arm extension, top-up or balance pooling.'}

def read(path):return strict_json(Path(path).read_bytes())
def write(path,value):atomic_bytes(Path(path),json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n')
def configuration(manifest,case,arm,root=ROOT):
 if case not in PROTOCOL['cases'] or arm not in PROTOCOL['arms']:raise ValueError('REGISTERED_COMPOSED_CASE_ARM_REQUIRED')
 cfg,manifest=prior_configuration(manifest,case,'earned_capacity',root=root)
 cfg.update(horizon_days=PROTOCOL['horizon_days'],customer_pool=PROTOCOL['customer_pool'],opening=PROTOCOL['opening_microUSD'])
 cfg['strategic_policy']['ranking_arithmetic']='exact-rational-v1'
 cfg['channel_menu_policy']={'schema':'connected-channel-menu/v1','contract_ids':['pilot'],'conversion_bps':4000}
 cfg['complete_offer_policy']['requested_jobs']={f'SIM-customer-{i:03d}':[j['id'] for j in manifest['jobs']] for i in range(cfg['customer_pool'])}
 scenarios=cfg['strategic_allocation_policy']['risk']['scenarios']
 cfg['strategic_allocation_policy']['strategic_game']={'schema':'connected-finite-follower-regret/v1','public_basis':'Matched authored finite forecast response stress, not observed rival dynamics.','max_response_states':1000000,'scenarios':{s:{'budget':0,'responses':[{'id':'unchanged','haircut_bps':{},'capture_bps':0,'cost':0},{'id':'compete','haircut_bps':{'delivery':100,'capacity':100,'acquisition':100},'capture_bps':5000,'cost':0}]} for s in scenarios}}
 if arm=='composed':cfg['strategic_allocation_policy']['sequence']=copy.deepcopy(PROTOCOL['public_window']);cfg['setup_cost']+=5000000;cfg['maintenance_daily']+=50000
 from .engine import validate_config
 return validate_config(cfg),manifest

def prepare(output,case,arm):
 if case not in PROTOCOL['cases'] or arm not in PROTOCOL['arms']:raise ValueError('REGISTERED_COMPOSED_CASE_ARM_REQUIRED')
 output=Path(output).absolute()
 if '..' in output.parts or any(p.is_symlink() for p in [output,*output.parents]):raise ValueError('NORMALIZED_NEW_OUTPUT_REQUIRED')
 output.mkdir(parents=True,exist_ok=False);source=output/'source'
 for name in source_paths(ROOT):
  target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
 if identity(ROOT)!=identity(source):raise ValueError('SOURCE_FREEZE_CHANGED')
 from adaptive_enterprise.instruments import prepare_complete_offer_services
 manifest=prepare_complete_offer_services(source,'workloads/composed049',cohort_seed=PROTOCOL['cohort_seed'],jobs_per_service=PROTOCOL['jobs_per_service'],packet_jobs=PROTOCOL['packet_jobs'],packet_rows=PROTOCOL['packet_rows'])
 cfg,manifest=configuration(manifest,case,arm,root=source)
 write(output/'REGISTERED.json',{'protocol':PROTOCOL,'case':case,'arm':arm,'source':identity(source),'config':cfg,'manifest':manifest})
 return {'registered':str(output/'REGISTERED.json'),'source_sha256':identity(source)['sha256'],'next':'Run this frozen module from the output/source directory.'}

def validate_inventory(manifest,root):
 from adaptive_enterprise.instruments import SOURCE_PATHS,prepare_complete_offer_services
 with tempfile.TemporaryDirectory(prefix='composed049-origin-') as temporary:
  origin=Path(temporary)
  for name in SOURCE_PATHS:
   target=origin/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(Path(root)/name,target)
  expected=prepare_complete_offer_services(origin,'workloads/composed049',cohort_seed=PROTOCOL['cohort_seed'],jobs_per_service=PROTOCOL['jobs_per_service'],packet_jobs=PROTOCOL['packet_jobs'],packet_rows=PROTOCOL['packet_rows'])
  expected['native_engine']='exact-permanent-v2'
  if _inventory_identity(manifest)!=_inventory_identity(expected):raise ValueError('REGISTERED_COMPOSED_COHORT_CHANGED')
  for job in expected['jobs']:
   for field in ('input','artifact','receipt'):
    if (Path(root)/job[field]).read_bytes()!=(origin/job[field]).read_bytes():raise ValueError('REGISTERED_COMPOSED_ARTIFACT_CHANGED')
 return {'registered_jobs_rederived':len(expected['jobs']),'manifest_identity_sha256':_inventory_identity(expected)}

def plan(output):
 output=Path(output).absolute();p=read(output/'REGISTERED.json')
 if '..' in output.parts or any(x.is_symlink() for x in [output,*output.parents]):raise ValueError('NORMALIZED_OUTPUT_REQUIRED')
 if p['protocol']!=PROTOCOL or p['source']!=identity(output/'source') or identity(ROOT)!=p['source']:raise ValueError('SOURCE_BOUND_PROTOCOL_CHANGED')
 validate_inventory(p['manifest'],output/'source')
 cfg,m=configuration(p['manifest'],p['case'],p['arm'],root=output/'source')
 if cfg!=p['config'] or m!=p['manifest']:raise ValueError('REGISTERED_INPUT_CHANGED')
 return output,p

def verify(output):
 output,p=plan(output);r=read(output/'private/RESULT.json')
 if r['source']!=p['source'] or r['config']!=p['config'] or r['seed']!=PROTOCOL['seed'] or r['arm']!='competitive_growth':raise ValueError('REGISTERED_RESULT_CHANGED')
 from .verify import audit
 a=audit(output/'source',p['manifest'],r)
 if not a['accepted'] or not r['complete']:raise ValueError('COMPLETE_AUDITED_NATIVE_RESULT_REQUIRED')
 s=r['summary']
 if s['profit']!=s['revenue']+s['recoveryIncome']-s['expenses']:raise ValueError('COMPLETE_PROFIT_IDENTITY_FAILED')
 selected=[o for wrapper in r['joint_actions'].values() for o in wrapper['allocation']['decision']['selected_options'] if 'first_investment' in o['execution']]
 return {'schema':PROTOCOL['schema'],'case':p['case'],'arm':p['arm'],'source_sha256':p['source']['sha256'],'protocol_sha256':digest(PROTOCOL),'config_sha256':digest(p['config']),'manifest_identity_sha256':_inventory_identity(p['manifest']),'result_sha256':digest(r),'native_actions_sha256':r['owned_account']['ledger']['actions_sha256'],'independent_audit_accepted':True,'audit_sha256':digest(a),'opening_microUSD':p['config']['opening'],'operating_days':p['config']['horizon_days'],'paid_jobs':r['paid_jobs'],'paying_customers':r['customers'],'repeat_customers':r['repeat_customers'],'summary':s,'investments':[{k:i.get(k) for k in ('id','kind','capacity_units','cost','purchased_time','activation_time','expiry_time')} for i in r['investments']],'selected_sequence_first_actions':[{'id':o['id'],'kind':o['kind'],'purchased_units':o['execution'].get('purchased_units'),'contingent_capacity_units':o['execution'].get('contingent_capacity_units')} for o in selected],'settled_packets':sum(o['offer']['service_id']=='receivables_packet' and o['outcome']=='SETTLED' for o in r['orders']),'actual_commerce_profit':None,'actual_host_model_engineering_billing':None,'scope':PROTOCOL['evidence_role']}

def operate(output,max_events=None):
 if max_events is not None and (type(max_events) is not int or max_events<1):raise ValueError('POSITIVE_EVENT_CHECKPOINT_REQUIRED')
 output,p=plan(output)
 from .engine import run_world
 r=run_world(ROOT,p['manifest'],p['config'],PROTOCOL['seed'],'competitive_growth',output/'private',source=p['source'],stop_after_events=max_events)
 if not r['complete']:return {'complete':False,'processed_events':r['processed_events'],'source_sha256':p['source']['sha256'],'checkpoint':str(output/'private/STATE.json'),'next':'Resume this same frozen module and output; never copy balances.'}
 before=r['owned_account'];again=run_world(ROOT,p['manifest'],p['config'],PROTOCOL['seed'],'competitive_growth',output/'private',source=p['source'])
 if before!=again['owned_account']:raise ValueError('SAME_ACCOUNT_RESUME_CHANGED_NATIVE_HISTORY')
 result=verify(output);result['resume_financially_unchanged']=True;write(output/'PUBLIC.json',result);return result

def main():
 parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','run','verify']);parser.add_argument('--output',required=True,type=Path);parser.add_argument('--case',choices=PROTOCOL['cases']);parser.add_argument('--arm',choices=PROTOCOL['arms']);parser.add_argument('--max-events',type=int);args=parser.parse_args()
 if args.command=='prepare':result=prepare(args.output,args.case,args.arm)
 elif args.command=='run':result=operate(args.output,args.max_events)
 else:result=verify(args.output)
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
