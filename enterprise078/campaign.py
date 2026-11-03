import argparse,copy,hashlib,json,resource,shutil,time
from pathlib import Path
from commercial.ledger import canonical,digest,strict_json
from commercial.terms_exact_v2 import prospective_terms
from connected_enterprise.finance import audit_journal
from .construct import produce,learning_loop
from .verify import verify
from .service import prepare_manifest,source_paths
from .native import BusinessAccount
from .sqlite_referee import check as sqlite_check
USD=1000000
METHODS=('observation_selected_controller','ordinary_equal_content_controller')
REGIONS=('favorable','central','weak_demand','adverse','high_cost','uncollected','illiquid','underfunded','reference_100k','no_deployment')

def save(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(canonical(value)+b'\n')

def run_technical(root,out):
 requests=strict_json((root/'enterprise078/requests.json').read_bytes());rows=[]
 for request in requests:
  if request['id'].startswith(('dev','gateway','native')): continue
  for method in METHODS:
   t=time.perf_counter();cpu=time.process_time();artifact=produce(request,method);verdict=verify(request,artifact)
   rows.append({'request_id':request['id'],'family':request['family'],'kind':request['kind'],'method':method,'accepted':verdict['accepted'],'refused':artifact['status']=='refused','artifact_sha256':digest(artifact),'cpu_seconds':time.process_time()-cpu,'wall_seconds':time.perf_counter()-t,'selection_checks':artifact.get('selection',{}).get('selection_checks'), 'reason':artifact.get('reason')})
 save(out/'technical.json',rows);save(out/'sqlite_referee.json',sqlite_check())
 return rows

def economic(root,out,region,*,gateway=False):
 opening=(100000 if region=='reference_100k' else 8000 if region=='underfunded' else 25000)*USD
 protocol=strict_json((root/'enterprise078/PROTOCOL.json').read_bytes());mult=3 if region=='high_cost' else 1
 ids=['gateway-K1'] if gateway else ['native-K1','native-K2']
 manifest=prepare_manifest(root,[{'id':i,'delivery_path':f'enterprise078/deliveries/{region}/{i}.json'} for i in ids]);public=out/'public'/region;private=out/'private'/region;private.mkdir(parents=True,exist_ok=True)
 save(public/'manifest.json',manifest);rows=[];chain=None;retained=None;contract='enterprise078-'+region
 with BusinessAccount(root,manifest,private/'account',opening=opening,working=0,contract=contract) as a:
  startup=6000*mult*USD
  a.cost('whole-first-use-construction-search',startup,0)
  a.cost('maintenance',300*USD,1)
  if region=='no_deployment':
   rows.append({'decision':'NO_DEPLOY_AFTER_SEARCH','revenue':0})
  else:
   for index,job_id in enumerate(ids):
    hour=24+index*72;price=(12000 if index==0 else 18000)*USD
    budget=(0 if region=='weak_demand' else 30000)*USD
    rival=(6000 if region=='adverse' else 24000 if region=='favorable' else 14000 if index==0 else 20000)*USD
    selfservice=(13000 if index==0 else 19000)*USD
    acquisition=(600 if index==0 else 900)*USD
    row={'job_id':job_id,'hour':hour,'quote_microUSD':price,'buyer_budget_microUSD':budget,'outside_option_microUSD':min(rival,selfservice),'accepted':False,'collected':False}
    if index==1:
     before=copy.deepcopy(a.snapshot());need=3000*USD
     chain={'before':before,'required':need,'inherited_policy':retained,'funding':None}
     receipt=a.spend('K2-construction','new-characterization-construction',need,hour,{'asset':retained,'separate_outcome':'monotone transition bracket','equal_content_ordinary_allowed':True},expected_net=8000*USD,allow_seed=False)
     chain['funding']=receipt;chain['after']=copy.deepcopy(a.snapshot())
     if receipt is None:
      row['decision']='DEFER_UNFUNDED_K2';rows.append(row);break
    if a.snapshot()['summary']['available']<acquisition:
     row['decision']='STOP_UNFUNDED_ACQUISITION';rows.append(row);break
    a.cost('acquisition-'+job_id,acquisition,hour)
    if budget<price or price>=min(rival,selfservice):
     row['decision']='BUYER_DECLINES';rows.append(row);break
    production=(800 if index==0 else 1200)*mult*USD
    if a.snapshot()['summary']['available']<price+production+200000:
     row['decision']='DEFER_UNFUNDED_EXPOSURE_AND_PRODUCTION';rows.append(row);break
    order=region+'-'+job_id
    maturity=9000 if region=='illiquid' else hour+12
    terms=prospective_terms(order,price,maturity,hour+2,residual=500*USD,fee=200000,counterparty_obligations='Model-qualified software/digital-twin output only; no physical sample, instrument guarantee or live buyer. Full adverse refund and support remain producer obligations.')
    a.begin_order(job_id,order,'buyer-'+order,price,budget,hour,hour+3,terms)
    spend=a.spend('production-'+job_id,'unique-production-and-verification',production,hour,{'request':job_id,'modeled_complete_resource_envelope':True},expected_net=price-production,allow_seed=True)
    if spend is None:
     a.refund(order,hour+1);row['decision']='REFUND_UNFUNDED_PRODUCTION';rows.append(row);break
    request=next(r['request'] for r in manifest['jobs'] if r['id']==job_id)
    artifact=produce(request,retained=retained if index==1 else None)
    if region=='adverse': artifact['rows'][0]['quantity']+=1
    t=time.perf_counter();verdict=a.complete_order(order,job_id,artifact,hour+1)
    row.update(acceptance=verdict,accepted=verdict['accepted'],artifact_sha256=digest(artifact),gateway_seconds=time.perf_counter()-t,artifact_bytes=len(canonical(artifact)),production_receipt=spend)
    if not verdict['accepted']: a.refund(order,hour+2)
    elif region!='uncollected': a.release(order,hour+2);row['collected']=True
    if index==0 and verdict['accepted']: retained={'family':artifact['family'],'policy':artifact['policy'],'producer_sha256':manifest['source_hashes']['enterprise078/construct.py']}
    support=(500 if index==0 else 700)*USD
    a.cost('incurred-support-'+job_id,support,hour+3)
    tax=(max(0,a.snapshot()['summary']['profit'])*25)//100
    already=sum(e['args']['amount'] for e in a.export()['ledger']['actions'] if e['op']=='cost' and e['args']['id'].startswith('tax-'))
    pretax=a.snapshot()['summary']['profit']+already;due=max(0,pretax)//4-already
    if due>0: a.cost('tax-'+job_id,due,hour+3)
    row['after']=copy.deepcopy(a.snapshot());rows.append(row)
    a.advance(hour+13)
  a.advance(8760)
  audit=a.audit();record=a.export();summary=record['ledger']['summary']
  save(public/'account.json',record)
  result={'region':region,'opening_microUSD':opening,'contract':contract,'audit':audit,'summary':summary,'attempts':rows,'K1_K2_chain':chain,'manifest_sha256':digest(manifest),'export_sha256':digest(record),'scope':'CONDITIONAL_NATIVE_SIMULATION','final365_microUSD':summary['profit'],'window_hours':[0,8760],'equity_opportunity_cost_microUSD':opening*8//100,'actual_billing':None}
  save(public/'result.json',result)
 with BusinessAccount(root,manifest,private/'account',opening=opening,working=0,contract=contract) as a:
  if a.export()!=record: raise ValueError('REOPEN_CHANGED_HISTORY')
  a.audit()
 result['unchanged_reopen']=True;save(public/'result.json',result)
 return result

def run(root,out,mode):
 root=Path(root).resolve();out=Path(out).resolve()
 if out.exists(): raise ValueError('FRESH_EXPERIMENT_DIRECTORY_REQUIRED')
 out.mkdir(parents=True);frozen=out/'source';frozen.mkdir()
 paths=source_paths(root)
 for name in paths:
  dest=frozen/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,dest)
 source={n:hashlib.sha256((frozen/n).read_bytes()).hexdigest() for n in paths};save(out/'SOURCE.json',{'files':source,'sha256':digest(source)})
 start=time.perf_counter();cpu=time.process_time()
 if mode=='gateway': results=[economic(frozen,out,'gateway',gateway=True)];technical=[]
 else: technical=run_technical(frozen,out);results=[economic(frozen,out,r) for r in REGIONS]
 summary={'mode':mode,'source_sha256':digest(source),'technical_rows':len(technical),'accounts':[{'region':r['region'],'profit_microUSD':r['summary']['profit'],'accepted':sum(a.get('accepted',False) for a in r['attempts']),'audited':r['audit']['accepted'],'reopened':r['unchanged_reopen']} for r in results],'cpu_seconds':time.process_time()-cpu,'wall_seconds':time.perf_counter()-start,'observed_customers':0,'paid_model_API_calls':0,'three_billion_achieved':False}
 save(out/'SUMMARY.json',summary);return summary

def audit_output(out):
 out=Path(out).resolve();root=out/'source';source=strict_json((out/'SOURCE.json').read_bytes())
 if any(hashlib.sha256((root/n).read_bytes()).hexdigest()!=h for n,h in source['files'].items()): raise ValueError('FROZEN_SOURCE_CHANGED')
 seen=set();rows=[]
 for p in sorted((out/'public').glob('*/result.json')):
  result=strict_json(p.read_bytes());manifest=strict_json((p.parent/'manifest.json').read_bytes());record=strict_json((p.parent/'account.json').read_bytes())
  if digest(record) in seen: raise ValueError('DUPLICATE_ACCOUNT_EVIDENCE')
  seen.add(digest(record))
  if digest(manifest)!=result['manifest_sha256'] or digest(record)!=result['export_sha256']: raise ValueError('ACCOUNT_BINDING')
  config=record['ledger']['config']
  if config['opening']!=result['opening_microUSD'] or config['contract']!=result['contract'] or result['contract']!='enterprise078-'+p.parent.name: raise ValueError('REGISTERED_ACCOUNT_IDENTITY')
  row=audit_journal(record,root=root,manifest=manifest)
  if record['ledger']['summary']!=result['summary']: raise ValueError('DECLARED_SUMMARY_MISMATCH')
  rows.append({'region':p.parent.name,'accepted':row['accepted'],'actions':len(record['ledger']['actions'])})
 return {'accepted':all(r['accepted'] for r in rows),'accounts':rows,'scope':'key-free semantic replay; no ownership-HMAC authentication'}

def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=['gateway','run','audit']);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 value=audit_output(a.output) if a.command=='audit' else run(Path(__file__).resolve().parents[1],a.output,a.command)
 print(json.dumps(value,sort_keys=True))
if __name__=='__main__': main()
