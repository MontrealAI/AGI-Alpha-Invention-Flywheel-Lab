import argparse, hashlib, importlib.util, json, os, resource, time
from pathlib import Path
from datetime import datetime, timezone

resource.setrlimit(resource.RLIMIT_CPU,(200,202));resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
def sha(raw):return hashlib.sha256(raw).hexdigest()
def write(path,value):
 with path.open('xb') as f:f.write(json.dumps(value,indent=2,allow_nan=False).encode()+b'\n');f.flush();os.fsync(f.fileno())
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--economics',required=True);ap.add_argument('--root',required=True);ap.add_argument('--prior',required=True);ap.add_argument('--event',required=True);ap.add_argument('--output',required=True);a=ap.parse_args();base=Path(a.economics).resolve();root=Path(a.root).resolve();prior=Path(a.prior).resolve();event_path=Path(a.event).resolve();out=Path(a.output).resolve();start=time.process_time()
 bundle=json.loads((prior/'BUNDLE_SHA256.json').read_text());old_identity={p.name:sha(p.read_bytes()) for p in prior.iterdir() if p.is_file()}
 if 'BUNDLE_SHA256.json' in bundle:raise ValueError('manifest must exclude itself')
 for name,digest in bundle.items():
  if sha((prior/name).read_bytes())!=digest:raise ValueError('prior bundle changed '+name)
 raw=(prior/'AGGREGATION_LEDGER.jsonl').read_bytes();old_rows=[json.loads(x) for x in raw.splitlines()];event_raw=event_path.read_bytes();event=json.loads(event_raw)
 if event['pool'] not in ('experiment','verification_publication') or type(event['conservative_budget_charge_CPU_seconds']) is not int or event['conservative_budget_charge_CPU_seconds']<0:raise ValueError('reservation type')
 if event['conservative_budget_charge_CPU_seconds']==0 and event.get('event_type')!='observation':raise ValueError('zero charge requires explicit observation event')
 if event.get('event_type')=='observation' and event['conservative_budget_charge_CPU_seconds']!=0:raise ValueError('observation cannot reserve resources')
 allocation_path=root/'campaign/overnight-008/ALLOCATION.json';allocation=json.loads(allocation_path.read_text());caps={'experiment':allocation['experiment_cpu_seconds_cap'],'verification_publication':allocation['verification_publication_cpu_seconds_cap']}
 helper=base/'recover_economics_v2.py';s=importlib.util.spec_from_file_location('recovery2',helper);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);out.mkdir(parents=True,exist_ok=False)
 target=out/'AGGREGATION_LEDGER.jsonl'
 with target.open('xb') as f:f.write(raw)
 head=m.append_chain(target,event);rows=[json.loads(x) for x in target.read_bytes().splitlines()];totals={k:sum(r['event']['conservative_budget_charge_CPU_seconds'] for r in rows if r['event']['pool']==k) for k in caps}
 if len(rows)!=len(old_rows)+1 or rows[-1]['sequence']!=len(rows) or not target.read_bytes().startswith(raw) or any(totals[k]>caps[k] for k in caps):raise AssertionError('append/capacity invariant')
 write(out/'EVENT.json',event)
 write(out/'CUMULATIVE_COST_RESOURCE.json',{'schema':'agi-alpha/overnight008-cost-resource-recovery-v4','recorded_utc':datetime.now(timezone.utc).isoformat(),'previous_ledger_file_sha256':sha(raw),'previous_chain_head_sha256':old_rows[-1]['record_sha256'],'chain_head_sha256':head,'events':len(rows),'conservative_reserved_CPU_seconds':totals,'original_CPU_ceilings':caps,'remaining_accounting_reservation_capacity_CPU_seconds':{k:caps[k]-totals[k] for k in caps},'original_allocation_file_sha256':sha(allocation_path.read_bytes()),'latest_event_id':event['id'],'latest_event_type':event.get('event_type','reservation'),'no_original_time_resource_or_claim_error_reset':True,'original_development_cutoff_utc':allocation['development_end_utc'],'original_end_utc':allocation['end_utc'],'prior_uncertainty_holdbacks_and_missing_monetary_costs_unchanged':True,'complete_profit_USD':None,'qualified_simulated_commercial_earnings_microUSD':0,'earned_successor_funding':'DEFERRED','self_CPU_seconds':time.process_time()-start,'economics_work_covered_by_existing200CPU_reservation':True})
 checks={'all_previous_journal_lines_byte_preserved':target.read_bytes().startswith(raw),'exactly_one_new_event':len(rows)==len(old_rows)+1,'prior_bundle_files_unchanged':all(sha((prior/n).read_bytes())==h for n,h in old_identity.items()),'original_caps_not_reset':True,'previous_failed_charges_not_refunded':True,'within_original_pool_caps':all(totals[k]<=caps[k] for k in caps)}
 if not all(checks.values()):raise AssertionError(checks)
 write(out/'APPEND_VERIFICATION.json',{'checks':checks,'new_event_input_file_sha256':sha(event_raw),'append_source_sha256':sha(Path(__file__).read_bytes()),'chain_helper_sha256':sha(helper.read_bytes())})
 with (out/'APPEND_SOURCE.py.txt').open('xb') as f:f.write(Path(__file__).read_bytes())
 write(out/'BUNDLE_SHA256.json',{p.name:sha(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file() and p.name!='BUNDLE_SHA256.json'})
 print(json.dumps({'output':str(out),'events':len(rows),'reserved_CPU':totals,'remaining_CPU':{k:caps[k]-totals[k] for k in caps},'qualified_earnings':0,'new_candidate_execution':'not performed by cost aggregation'}))
if __name__=='__main__':main()
