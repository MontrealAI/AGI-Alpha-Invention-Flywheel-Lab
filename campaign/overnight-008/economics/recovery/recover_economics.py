import argparse, hashlib, importlib.util, json, os, resource, sys, time
from fractions import Fraction
from pathlib import Path
from datetime import datetime, timezone

resource.setrlimit(resource.RLIMIT_CPU,(200,202))
resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
PINS={'vendor/__init__.py':'be8bdfe2c1e80537aa8346db6e39112224381b56a853f94d460c00d29692db54','vendor/alpha_claim/__init__.py':'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855','vendor/alpha_claim/contracts.py':'3536b96c4b7ee46f9af7d807e02685aa55e42daae7f7c56b7e9029ca2cde0964','vendor/alpha_claim/protected_exchange.py':'7b72c911d99a9aa12dc1f412d3b66f69ba58f3d4f2f50291310a7fd849df5272'}
def canon(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_text())
def write_new(p,v):
 with p.open('xb') as f:f.write(json.dumps(v,indent=2,allow_nan=False).encode()+b'\n');f.flush();os.fsync(f.fileno())
def source(root,relative):
 p=root/relative
 if p.is_symlink():raise ValueError('symlink source')
 return {'path':relative,'sha256':sha(p.read_bytes())}
def append_chain(path,event):
 prior='0'*64;seen={};count=0
 if path.exists():
  for line in path.read_bytes().splitlines():
   row=json.loads(line);digest=row.pop('record_sha256')
   if row['previous_sha256']!=prior or sha(canon(row))!=digest:raise ValueError('ledger chain mismatch')
   prior=digest;seen[row['event']['id']]=row['event'];count+=1
 if event['id'] in seen:
  if seen[event['id']]!=event:raise ValueError('ledger event rebind')
  return prior
 row={'sequence':count+1,'previous_sha256':prior,'event':event};row['record_sha256']=sha(canon(row))
 fd=os.open(path,os.O_CREAT|os.O_WRONLY|os.O_APPEND,0o644)
 with os.fdopen(fd,'ab') as f:f.write(canon(row)+b'\n');f.flush();os.fsync(f.fileno())
 return row['record_sha256']
def worker_inventory(root):
 base=root/'evidence/overnight-008';exclude={'observability-development-r1','observability-development-r2','retained-crauste-development-r1','inherited-regressions-008','inherited-regressions-008-r2','archive-and-isolation-sized-008','preflight'};unique={};duplicates=[]
 def visit(v,path,pointer=()):
  if isinstance(v,dict):
   if isinstance(v.get('limits'),dict) and type(v['limits'].get('cpu_seconds')) in (int,float) and ('worker' in v or 'returncode' in v or 'stdout_sha256' in v):
    h=sha(canon(v));loc={'source':source(root,str(path.relative_to(root))),'pointer':'.'.join(pointer)}
    if h in unique:duplicates.append({'receipt_sha256':h,'copy':loc,'first':unique[h]['location']})
    else:unique[h]={'receipt_sha256':h,'location':loc,'cpu_ceiling_seconds':v['limits']['cpu_seconds'],'reported_worker_cpu_seconds':v.get('worker',{}).get('worker_cpu_seconds')}
    return
   for k,w in v.items():visit(w,path,pointer+(k,))
  elif isinstance(v,list):
   for i,w in enumerate(v):visit(w,path,pointer+(str(i),))
 for p in sorted(base.rglob('*.json')):
  if p.relative_to(base).parts[0] in exclude:continue
  visit(read(p),p)
 return {'scope':'Non-enclosed worker receipts; covered by the2000CPU verifier uncertainty reservation, NEVER added again to charged totals','receipts':list(unique.values()),'identical_copies_excluded':duplicates,'distinct_worker_ceiling_seconds':sum(r['cpu_ceiling_seconds'] for r in unique.values()),'reported_worker_cpu_subtotal_seconds':sum(r['reported_worker_cpu_seconds'] or 0 for r in unique.values()),'missing_worker_rusage_is_not_zero':True,'controller_and_unwaited_CPU_complete':False}
def engine_probe(root,out):
 for relative,pin in PINS.items():
  if sha((root/relative).read_bytes())!=pin:raise ValueError('pinned exchange source changed')
 sys.path.insert(0,str(root))
 from vendor.alpha_claim.protected_exchange import ProtectedExchange
 from vendor.alpha_claim.contracts import digest
 task={'schema':'agi-alpha/no-earned-funds-recovery008/v1','scope':'internal deposit-accounting qualification only; no buyer/price calibration'}
 def validate(v):
  if v!=task:raise ValueError('task mismatch')
 def check(t,a):return {'accepted':False,'decisive':True,'reason':'No qualified commercial delivery or demand'}
 ex=ProtectedExchange(out/'NO_EARNED_FUNDS.sqlite',key=b'8'*32,contract='overnight008/recovery-no-earnings/v1',validate=validate,check=check,opening=100000000,working=1000000)
 checks=[];snapshots={}
 def blocked(name):
  try:ex.reserve_investment(name,1,1,intent_hash=digest(task))
  except ValueError as error:checks.append({'check':name,'passed':True,'error':str(error)})
  else:raise AssertionError('unearned investment admitted')
 try:
  snapshots['opening_capital_only']=ex.snapshot();blocked('opening-capital-cannot-fund')
  ex.wallet('INTERNAL_QUALIFICATION_DEPOSIT_ACCOUNT',2000000)
  ex.offer('deposit-only','INTERNAL_QUALIFICATION_DEPOSIT_ACCOUNT',1000000,'nonrecourse-simulated',task,100)
  row=ex.order('deposit-only');terms={k:row[k] for k in ('id','buyer','price','rail','task_hash','contract','deadline')}
  ex.event('deposit-only','consent','consent',{'buyer':row['buyer'],'termsHash':digest(terms)},0)
  ex.event('deposit-only','fund','fund',ex.provider.issue(ex.order('deposit-only'),'funded'),1)
  snapshots['refundable_deposit_restricted']=ex.snapshot();blocked('deposit-cannot-fund')
  try:ex.event('deposit-only','prepare','prepare',{'no_qualified_delivery':True},2)
  except ValueError:checks.append({'check':'unsupported-delivery-refused','passed':True})
  else:raise AssertionError('unsupported delivery accepted')
  ex.event('deposit-only','refund','refund',{},3);before=ex.snapshot();ex.event('deposit-only','refund','refund',{},3)
  if ex.snapshot()!=before:raise AssertionError('duplicate refund changed accounts')
  checks.append({'check':'duplicate-refund-idempotent','passed':True});snapshots['refund-releases-restriction-not-revenue']=ex.snapshot();blocked('refunded-deposit-cannot-fund')
  for name,v in snapshots.items():
   if any(v[k]!=0 for k in ('revenue','collections','profit','unrestrictedEarned')):raise AssertionError('unearned profit/income '+name)
  if snapshots['refundable_deposit_restricted']['custodyRestricted']!=1000000:raise AssertionError('deposit not restricted')
  journal=[dict(r) for r in ex.db.execute('SELECT seq,order_id,kind,amount FROM journal ORDER BY seq')]
  return {'schema':'agi-alpha/no-earned-funds-recovery008-result/v1','source_pins':PINS,'scope':'Executed narrow ledger qualification. Account,price,capital are internal engineering inputs, NOT real or economically calibrated buyers','snapshots':snapshots,'checks':checks,'journal':journal,'qualified_simulated_commercial_earnings_microUSD':0,'actual_receipts_microUSD':0,'complete_profit_USD':None,'qualified_successor_funding':'DEFERRED','unknown_complete_costs_remain_outside_engine_and_block_commercial_admission':True,'new_external_spending':0}
 finally:ex.close()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output',required=True);args=ap.parse_args();root=Path(args.root).resolve();out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False);start=time.monotonic();cpu=time.process_time();timestamp=datetime.now(timezone.utc).isoformat()
 allocation=read(root/'campaign/overnight-008/ALLOCATION.json');ledger=read(root/'evidence/overnight-008/RESOURCE_LEDGER.json');events=[]
 def event(ident,pool,charge,origin,**extra):
  events.append({'id':ident,'pool':pool,'conservative_budget_charge_CPU_seconds':charge,'charge_is_measured_cost':False,'origin':origin,**extra})
 for name,r in ledger['runs'].items():
  p=root/'evidence/overnight-008'/name/'RECEIPT.json';raw=p.read_bytes()
  if sha(raw)!=r['receipt_sha256']:raise ValueError('public receipt changed '+name)
  pool='experiment' if name.startswith(('observability-development','retained-crauste')) else 'verification_publication'
  event('public/'+name,pool,r['budget_cpu_seconds'],source(root,str(p.relative_to(root))),observed_waited_CPU_seconds=r['observed_waited_cpu_seconds'],full_group_CPU_attribution_complete=False,outcome=r['outcome'],refund_CPU_seconds=0,nested_worker_receipts_included=True)
 declaration={'source':'Root recovery coordination2026-10-30T07:20Z, inherited prior-continuation reservations; private receipts lost','private_XCT_CPU_reservations':[600,1200,1200],'read_only_review_CPU_reservation':240,'uncertainty_holdback_experiment_CPU':5000,'uncertainty_holdback_verification_CPU':2000,'recovery_suballocations_CPU':{'integration':1000,'builder':1000,'research':600,'verifier':1000,'paper':600,'economics':200},'authority_scope':'Original six-hour resource envelope only; no new spending/access/paid calls; no reset or refunds','uncertainty_holdback_status':'Explicit conservative reconciliation reservations accepted by integration owner. They are not measured actual use or independently proven full-process CPU upper bounds.'}
 write_new(out/'ROOT_RESOURCE_DECLARATION.json',declaration)
 for i,cap in enumerate(declaration['private_XCT_CPU_reservations'],1):event('lost-private-XCT-reservation/'+str(i),'experiment',cap,{'path':'ROOT_RESOURCE_DECLARATION.json','sha256':sha((out/'ROOT_RESOURCE_DECLARATION.json').read_bytes())},observed_CPU_seconds=None,private_originals_available=False,refund_CPU_seconds=0)
 event('public-exact-obstruction-review','verification_publication',240,{'url':'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/12#issuecomment-6516456134'},observed_CPU_seconds=16.187812,observation_scope='Public review report, original private receipt unavailable',refund_CPU_seconds=0)
 event('prior-unmetered-experiment-holdback','experiment',5000,{'path':'ROOT_RESOURCE_DECLARATION.json'},observed_CPU_seconds=None,covered='Standalone science/data/forcing/controller and other missing pre-interruption experiment costs. Source duplicates and nested worker data are supporting observations, not additive new charges.')
 event('prior-unmetered-verifier-publication-holdback','verification_publication',2000,{'path':'ROOT_RESOURCE_DECLARATION.json'},observed_CPU_seconds=None,covered='Preflight60 and isolation120 ceilings,193 distinct standalone worker ceilings548, first XCT review116.258044 reported selfCPU, missing controller/paper costs; excludes separately charged latest240 review')
 for name,cap in declaration['recovery_suballocations_CPU'].items():event('recovery-reservation/'+name,'experiment' if name in ('integration','builder','research') else 'verification_publication',cap,{'path':'ROOT_RESOURCE_DECLARATION.json'},observed_CPU_seconds=None,refund_CPU_seconds=0)
 previous='0'*64
 for e in events:previous=append_chain(out/'AGGREGATION_LEDGER.jsonl',e)
 totals={k:sum(e['conservative_budget_charge_CPU_seconds'] for e in events if e['pool']==k) for k in ('experiment','verification_publication')};caps={'experiment':allocation['experiment_cpu_seconds_cap'],'verification_publication':allocation['verification_publication_cpu_seconds_cap']}
 if any(totals[k]>caps[k] for k in caps):raise ValueError('original capacity exceeded')
 totals_report={'schema':'agi-alpha/overnight008-cost-resource-recovery/v1','recorded_utc':timestamp,'public_anchor_commit':'3360acaffa088ca4e9cc595412026210cb4952b2','original_allocation':source(root,'campaign/overnight-008/ALLOCATION.json'),'prior_subledger':source(root,'evidence/overnight-008/RESOURCE_LEDGER.json'),'prior_subledger_capacity5400_is_not_a_new_campaign_allocation':True,'append_only_chain_head_sha256':previous,'events':len(events),'conservative_charged_CPU_seconds':totals,'original_CPU_ceilings':caps,'remaining_reservation_capacity_CPU_seconds':{k:caps[k]-totals[k] for k in caps},'remaining_capacity_scope':'Accounting after explicit integration-owner uncertainty holdbacks; incomplete historical metering prevents an independently verified total actual-process CPU claim. No authority beyond original end11:07:44Z.','reported_public_enclosing_waited_CPU_seconds':sum(r['observed_waited_cpu_seconds'] for r in ledger['runs'].values()),'public_enclosing_observed_CPU_is_not_complete_cost':True,'monetary_cost_categories':{k:{'USD':None,'lower_bound_USD':0,'finite_upper_bound_USD':None,'unknown_is_not_zero':True} for k in ('discovery_and_rejected_search','model_inference','data_network_storage','construction_integration','verification_repair','delivery_fees','support_maintenance','warranty_refund_terminal_obligations','capital_financing_taxes')},'complete_enterprise_cost_USD':None,'complete_profit_USD':None,'deployable_unit_cost_USD':None,'actual_receipts_USD':0,'qualified_simulated_commercial_earnings_microUSD':0,'commercial_admission':False,'new_spending_authority_USD':0,'missing_private_artifacts_are_not_recreated_under_old_hashes':True,'no_refunds_or_ceiling_resets':True}
 write_new(out/'CUMULATIVE_COST_RESOURCE.json',totals_report);write_new(out/'WORKER_RECEIPT_INVENTORY.json',worker_inventory(root))
 frontier_source=root/'campaign/overnight-008/economics/frontier008.py';spec=importlib.util.spec_from_file_location('public_frontier008',frontier_source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 f_input=read(root/'campaign/overnight-008/economics/FRONTIER_INPUT.json');f_input.update(cohort_scope='One technical development opportunity; no economically admitted buyer cohort; source-bound support target currently falsified, not an order',price_microUSD=[0,66330000,163900000],price_support='Public Duke reconstruction and MICROCT industry hourly-rate sensitivity anchors; not this offering price, avoided hours or actual WTP')
 f_result=module.frontier(f_input);f_result['reused_kernel_source']=source(root,'campaign/overnight-008/economics/frontier008.py');f_result['economic_cohort_admitted']=False;f_result['optimistic_acceptance_not_observed']=True;f_result['price_source']=source(root,'campaign/overnight-008/economics/xct/SOURCES.json');write_new(out/'CONDITIONAL_FRONTIER_INPUT.json',f_input);write_new(out/'CONDITIONAL_FRONTIER_RESULT.json',f_result)
 rational={'schema':'agi-alpha/rational-participation-frontier008/v1','observed_buyer_value_advantage_USD':None,'trust_discount_distribution':None,'minimum_positive_participation':0,'buyer_unknowns':['independent completed-outcome utility advantage over free ordinary method','validation/calibration/switching/procurement cost','common model-mismatch/refund probability'],'rule':'Buy only if trust-adjusted incremental completed-outcome value exceeds price plus all incremental buyer costs relative to strongest alternative/non-entry. No positive advantage evidence => participation UNKNOWN, not invented.','rows':[],'actual_buyer_decisions':0,'outside_options':['free ordinary LP/dual certificate and checking','full conventional reconstruction/UQ','postpone','non-entry'],'investment_attractiveness':'UNKNOWN; incremental NPV relative to strongest outside option unmeasured; no earned cash available'}
 for p in f_input['price_microUSD']:
  for trust in ('0','1/2','1'):
   t=Fraction(trust);rational['rows'].append({'price_microUSD':p,'trust_sensitivity':trust,'minimum_incremental_value_microUSD_before_unknown_buyer_costs':None if t==0 else str(Fraction(p)/t),'full_condition':'trust*incremental_value >= price+K_buyer; K_buyer unpriced, not0','participation_from_actual_evidence':'UNKNOWN; zero included','sensitivity_is_not_calibrated_probability':True})
 write_new(out/'RATIONAL_PARTICIPATION.json',rational);write_new(out/'NO_EARNED_FUNDS.json',engine_probe(root,out))
 measured={'self_CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'peak_RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'ceiling_CPU_seconds':200,'ceiling_memory_bytes':2*1024**3,'already_charged_in':'recovery-reservation/economics','no_budget_refund':True,'complete_monetary_cost_USD':None,'external_paid_API_calls':0,'new_external_spending':0};write_new(out/'RECOVERY_RECEIPT.json',measured)
 manifest={p.name:sha(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file()};write_new(out/'FILES_SHA256.json',manifest)
 print(json.dumps({'output':str(out),'charged':totals,'remaining_capacity':totals_report['remaining_reservation_capacity_CPU_seconds'],'no_earned_funds_checks':True,'complete_profit':'UNKNOWN','recovery_CPU_seconds':measured['self_CPU_seconds']}))
if __name__=='__main__':main()
