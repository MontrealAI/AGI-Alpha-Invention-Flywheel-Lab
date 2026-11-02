"""Finite, source-bound conditional business test; no paid APIs or real commerce."""
from pathlib import Path
from decimal import Decimal, ROUND_CEILING
import argparse, json, hashlib, subprocess, sys, os, resource, time
from commercial.ledger import digest, strict_json
from commercial.terms_exact_v2 import prospective_terms
from connected_enterprise.finance import source_identity
from .service import prepare_manifest
from .native import BusinessAccount, audit_export

MICRO=1000000

def money(x):return int((Decimal(str(x))*MICRO).to_integral_value(rounding=ROUND_CEILING))
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def model_cost(row,reg):
 p=reg['costs']['price_proxy'];return row['input_tokens_estimated']/1e6*p['input_per_million_usd']+row['output_tokens_estimated']/1e6*p['output_per_million_usd']+row['other_resources_usd']

def produce(root,job,destination,receipt):
 before=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.monotonic()
 command=[sys.executable,str(root/'inventory061/quality_constructor.py'),'--input',str(root/job['request']['instance_path']),'--output',str(destination)]
 try:
  result=subprocess.run(command,cwd=root,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),capture_output=True,text=True)
 except OSError as error:
  result=subprocess.CompletedProcess(command,127,'',str(error))
 except KeyboardInterrupt:
  save(destination.parent/(destination.name+'-interrupted.json'),{'interrupted':True,'funding_receipt':receipt,'recovery':'Preserve this exact account and partial producer state; do not reseed or retry blindly.'})
  raise
 after=resource.getrusage(resource.RUSAGE_CHILDREN)
 observed={'command':command,'exit_code':result.returncode,'wall_seconds':time.monotonic()-start,'reaped_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'max_rss_kib':after.ru_maxrss,'external_model_calls':0,'actual_total_model_billing':None,'native_funding_receipt':receipt,'funding_before_process':True,'stderr':result.stderr[-3000:]}
 save(destination.parent/(destination.name+'-resource.json'),observed)
 if result.returncode:return None,observed
 try:
  artifact=strict_json((destination/'solution.json').read_bytes())
 except (OSError,ValueError,TypeError) as error:
  observed['artifact_error']=type(error).__name__+': '+str(error)
  save(destination.parent/(destination.name+'-resource.json'),observed)
  return None,observed
 return artifact,observed

def run(root,output,arm):
 root=root.resolve();output=output.resolve()
 if output.exists():raise ValueError('NEW_STATE_REQUIRED_NEVER_RESEED')
 output.mkdir(parents=True)
 reg=strict_json((root/'business_productivity065/PREREGISTRATION.json').read_bytes())
 rows=[{'id':'original','instance_path':'inventory061/inputs/01.json','scenario':'original','delivery_path':f'business_productivity065/deliveries/{arm}-original.json'}, {'id':'plus20','instance_path':'business_productivity065/scenario_plus20.json','scenario':'demand_plus20pct_ceil','delivery_path':f'business_productivity065/deliveries/{arm}-plus20.json'}]
 manifest=prepare_manifest(root,rows);save(output/'manifest.json',manifest)
 source=source_identity(root,manifest);save(output/'source.json',source)
 report={'arm':arm,'scope':'ACTUAL_PRODUCTION_CONDITIONAL_NATIVE_SIM_ECONOMICS','primary_seed_usd':100000,'preregistration_sha256':hashlib.sha256((root/'business_productivity065/PREREGISTRATION.json').read_bytes()).hexdigest(),'source_sha256':source['sha256'],'observed_buyers':0,'deliveries':[],'costs':[],'funding_checks':[],'actual_billing':None}
 with BusinessAccount(root,manifest,output/'owned-account.json',contract='business-productivity065-'+arm) as a:
  def cost(ident,value,hour):
   a.cost(ident,money(value),hour);report['costs'].append({'id':ident,'amount_usd':value,'hour':hour})
  def tax(ident,hour):
   # Pay only cumulative provision not already charged.
   paid=sum(x['amount_usd'] for x in report['costs'] if x['id'].startswith('tax-'))
   pretax=a.snapshot()['summary']['profit']/MICRO+paid
   due=max(0,pretax)*reg['costs']['tax_positive_profit']-paid
   if due>0:cost('tax-'+ident,due,hour)
  first=model_cost(reg['costs']['first'],reg);second=model_cost(reg['costs']['second'],reg)
  first_receipt=a.spend('first-complete-lifecycle','inventory_engineering',money(first),0,{'registration_sha256':report['preregistration_sha256'],'complete_lifecycle':'All preregistered agent stages plus resource allocation, estimated not metered'},expected_net=0,allow_seed=True)
  if not first_receipt:raise ValueError('FIRST_FUNDING_REFUSED')
  report['costs'].append({'id':'first-complete-lifecycle','amount_usd':first,'hour':0})
  if arm=='no_demand':report['decision']='NO_PURCHASE_RETAIN_INCURRED_COST_NO_COLLECTION'
  else:
   prices=[75,40] if arm=='competitive_imitation' else reg['market']['quotes_usd']
   delayed=arm=='payment_delay'; collection=170 if delayed else 25;maturity=200 if delayed else 73
   terms=prospective_terms('first',money(prices[0]),maturity,collection,residual=money(10),fee=money(3),counterparty_obligations='SIMULATED fixed-price historical inventory plan only. No observed buyer or future service guarantee; public algorithm remains freely reusable.')
   a.begin_order('original','first','sim-buyer-first',money(prices[0]),money(prices[0]),1,(171 if delayed else 26),terms)
   artifact,observed=produce(root,manifest['jobs'][0],output/'producer-first',first_receipt)
   accepted=a.complete_order('first','original',artifact,25) if artifact is not None else {'accepted':False,'metrics':None,'errors':['PRODUCER_FAILED_SEE_RESOURCE_RECEIPT']};save(output/'first-acceptance.json',accepted)
   report['deliveries'].append({'job':'original','production':observed,'accepted':accepted['accepted'],'artifact_sha256':digest(artifact) if artifact is not None else None,'metrics':accepted['metrics']})
   if not accepted['accepted']:
    a.refund('first',25);report['decision']='FIRST_REJECTED_NO_COLLECTION'
   else:
    if not delayed:
     cost('payment-first',prices[0]*.029+.30,25);a.release('first',25)
    a.advance(74);tax('first',74)
    before=a.snapshot()['summary'];record_before=digest(a.export())
    amount=1000 if arm=='insufficient_earned_cash' else second
    expected=max(0,prices[1]-second-prices[1]*.029-.30)
    receipt=a.spend('successor-earned-reservation','inventory_scenario_revision',money(amount),75,{'registration_sha256':report['preregistration_sha256'],'request_sha256':digest(manifest['jobs'][1]['request']),'purpose':'Second distinct modeled demand-scenario policy production plus verification/delivery/support'},expected_net=money(expected),allow_seed=False)
    unchanged=record_before==digest(a.export())
    report['funding_checks'].append({'amount_usd':amount,'summary_before':before,'receipt':receipt,'refusal_unchanged':unchanged if receipt is None else None,'allow_seed':False})
    if receipt is None:report['decision']='SUCCESSOR_DECLINED_NO_UNRESTRICTED_EARNED_FUNDS'
    else:
     if receipt['funding']!='EARNED':raise ValueError('SUCCESSOR_MUST_USE_EARNED')
     report['costs'].append({'id':'successor-complete-lifecycle','amount_usd':amount,'hour':75})
     terms2=prospective_terms('second',money(prices[1]),148,100,residual=money(10),fee=money(3),counterparty_obligations='SIMULATED distinct demand-stress policy revision; no actual customer or future performance guarantee.')
     a.begin_order('plus20','second','sim-buyer-second',money(prices[1]),money(prices[1]),76,101,terms2)
     artifact2,observed2=produce(root,manifest['jobs'][1],output/'producer-second',receipt)
     accepted2=a.complete_order('second','plus20',artifact2,100) if artifact2 is not None else {'accepted':False,'metrics':None,'errors':['PRODUCER_FAILED_SEE_RESOURCE_RECEIPT']};save(output/'second-acceptance.json',accepted2)
     report['deliveries'].append({'job':'plus20','production':observed2,'accepted':accepted2['accepted'],'artifact_sha256':digest(artifact2) if artifact2 is not None else None,'metrics':accepted2['metrics']})
     if accepted2['accepted']:
      cost('payment-second',prices[1]*.029+.30,100);a.release('second',100);report['decision']='TWO_ACCEPTED_DELIVERIES_SECOND_EARNED_FUNDED_SIM'
     else:a.refund('second',100);report['decision']='SECOND_REJECTED_COST_RETAINED'
    if delayed:
     cost('payment-first',prices[0]*.029+.30,170);a.release('first',170)
  a.advance(239);tax('final',239)
  export=a.export();report['summary']=a.snapshot()['summary'];report['native_audit']=a.audit();report['public_export_sha256']=digest(export)
  report['checkpoint']=a.seal_checkpoint({'arm':arm,'horizon_hours':240,'source_sha256':source['sha256']})
  a.verify_checkpoint(report['checkpoint']);save(output/'public-export.json',export);save(output/'result.json',report)
 independent=audit_export(export,root=root,manifest=manifest);save(output/'independent-audit.json',independent)
 with BusinessAccount(root,manifest,output/'owned-account.json',contract='business-productivity065-'+arm) as reopened:
  reopened.verify_checkpoint(report['checkpoint'])
  if reopened.export()!=export:raise ValueError('REOPEN_CHANGED_HISTORY')
  save(output/'reopen.json',{'same_export':True,'new_actions':0,'reseeded':False,'audit':reopened.audit()})
 return report

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--output',type=Path,required=True);p.add_argument('--arm',choices=['conditional','no_demand','payment_delay','competitive_imitation','insufficient_earned_cash'],required=True);a=p.parse_args()
 r=run(a.root,a.output,a.arm);print(json.dumps({'arm':r['arm'],'decision':r['decision'],'summary':r['summary'],'audit_accepted':r['native_audit']['accepted']}))
if __name__=='__main__':main()
