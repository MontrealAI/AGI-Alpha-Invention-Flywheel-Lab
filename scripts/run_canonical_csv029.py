"""Fixed public native operating qualification; no advantage assumed or claimed."""
import argparse,copy,hashlib,json,os,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from adaptive_enterprise.instruments import prepare_services
from connected_enterprise.engine import default_config,run_world
from connected_enterprise.runner import identity
from connected_enterprise.verify import audit
from connected_enterprise.csv_backend029 import contract
from connected_enterprise.mechanism_choice import csv_costs
from scripts.run_funded_csv028 import policy
from commercial.ledger import digest
ARMS=('conventional','optimized_eligible','direct','equal_content','replanned','inherited')
PROTOCOL={'schema':'canonical-csv029-fixed-operating/v1','service_seed':2910311832,'market_seed':2910311833,'horizon_days':14,'customers':12,'arms':ARMS,
 'scope':'PUBLIC_NATIVE_OPERATING_BACKEND_QUALIFICATION_NOT_SCALE_OR_INVENTION',
 'exposure':'Development-exposed fixed diagnostic coverage instance. No untouched confirmation or favorable-seed profit selection.',
 'costs':'Existing common production envelope once plus explicit CSV proposal/adapter/extra verifier envelopes. Unknown measured engineering/model/host bills; these are authored model costs.',
 'controls':'Same canonical service inventory, market, seed, opening cash, obligations and horizon. Conventional baseline; optimized optional CSV; four explicitly diagnostic CSV execution modes. CSV equivalence does not imply benefit.'}
def run(arm):
 if arm not in ARMS:raise ValueError('FIXED_ARM_REQUIRED')
 with tempfile.TemporaryDirectory(prefix='canonical-csv029-') as d, tempfile.TemporaryDirectory(prefix='.canonical-csv029-',dir=ROOT) as inputs:
  m=prepare_services(ROOT,Path(inputs).name+'/inputs',cohort_seed=PROTOCOL['service_seed'])
  c=default_config();c.update(horizon_days=14,customer_pool=12,arrival_bps=10000,nonpayment_bps=0)
  p=policy()
  if arm!='conventional':
   p['csv_backend']=contract(ROOT,'replanned' if arm=='optimized_eligible' else arm);p['costs']['csv_backend']=csv_costs(p['csv_backend']);p['mode']='optimize' if arm=='optimized_eligible' else 'diagnostic_csv_backend'
  c['mechanism_policy']=p;source=identity(ROOT);cpu=time.process_time();wall=time.monotonic()
  r=run_world(ROOT,m,c,PROTOCOL['market_seed'],'baseline',Path(d)/'world',source=source);a=audit(ROOT,m,r)
  assert r['complete'] and a['accepted']
  csv=[o for o in r['orders'] if o.get('method_plan',{}).get('mode')=='csv_backend']
  if arm in ('direct','equal_content','replanned','inherited'):assert csv and all(o['service_receipt']['accepted'] for o in csv)
  else:assert not csv
  return {'protocol':PROTOCOL,'arm':arm,'source':source,'config':c,'manifest_sha256':digest(m),'complete':r['complete'],'audit':a,'summary':r['summary'],
   'paid_jobs':r['paid_jobs'],'profit_claim':'MODELED_FINITE_HORIZON_ONLY_NOT_MEASURED_COMPLETE_COST_ANNUAL_PROFIT','actual_profit':None,'actual_customers':0,'actual_collections':0,
   'result_sha256':digest(r),'orders':[{'id':o['id'],'job_id':o['job_id'],'outcome':o['outcome'],'price':o['price'],'complete_cost':o['complete_cost'],'method':o.get('method_plan',{}).get('mode'),
      'extra_method_cost':o.get('method_plan',{}).get('cost',0),'useful_outcome_sha256':o['service_receipt'].get('useful_outcome_sha256'),'backend':o.get('method_plan',{}).get('backend',{}).get('arm')} for o in r['orders']],
   'process_cpu_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-wall,'canonical_backend_executions':len(csv),
   'scope':'CANONICAL_ENGINE_NATIVE_PREPAYMENT_PRODUCTION_ACCEPTANCE_COLLECTION_AND_INDEPENDENT_OPERATING_AUDIT','invention_claim':False,'economic_advantage_claim':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--arm',choices=ARMS,required=True);p.add_argument('--output',required=True);args=p.parse_args()
 cpu=time.process_time();wall=time.monotonic()
 try:checkout=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
 except subprocess.CalledProcessError:checkout=None
 evidence={'protocol':PROTOCOL,'arm':args.arm,'checkout_commit':checkout,'workflow_run_id':os.environ.get('GITHUB_RUN_ID'),'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 try:
  r=run(args.arm);r.update(evidence,status='COMPLETED')
 except BaseException as error:
  r={**evidence,'status':'FAILED','error':type(error).__name__+': '+str(error),'source':identity(ROOT),'process_cpu_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-wall}
  Path(args.output).write_text(json.dumps(r,sort_keys=True,indent=2)+'\n');raise
 Path(args.output).write_text(json.dumps(r,sort_keys=True,indent=2)+'\n')
 print(json.dumps({'arm':args.arm,'complete':r['complete'],'audit':r['audit']['accepted'],'csv_executions':r['canonical_backend_executions']}))
