import argparse, hashlib, importlib.util, json, os, resource, time
from pathlib import Path
from datetime import datetime, timezone

resource.setrlimit(resource.RLIMIT_CPU,(200,202));resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
def sha(v):return hashlib.sha256(v).hexdigest()
def canon(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def write(path,value):
 with path.open('xb') as f:f.write(json.dumps(value,indent=2,allow_nan=False).encode()+b'\n');f.flush();os.fsync(f.fileno())
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--economics',required=True);ap.add_argument('--workspace',required=True);ap.add_argument('--output',required=True);a=ap.parse_args();base=Path(a.economics).resolve();workspace=Path(a.workspace).resolve();prior=base/'run005';out=Path(a.output).resolve();start=time.process_time();out.mkdir(parents=True,exist_ok=False)
 old_files={p.name:sha(p.read_bytes()) for p in sorted(prior.iterdir()) if p.is_file()};bundle=json.loads((prior/'BUNDLE_SHA256.json').read_text())
 for name,digest in bundle.items():
  if sha((prior/name).read_bytes())!=digest:raise ValueError('prior event21 bundle changed '+name)
 for name,digest in json.loads((base/'RECOVERY_FILES_SHA256.json').read_text()).items():
  if sha((base/name).read_bytes())!=digest:raise ValueError('original frozen file changed '+name)
 raw=(prior/'AGGREGATION_LEDGER.jsonl').read_bytes();target=out/'AGGREGATION_LEDGER.jsonl'
 with target.open('xb') as f:f.write(raw)
 helper=base/'recover_economics_v2.py';s=importlib.util.spec_from_file_location('recovery2',helper);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
 event={'id':'recovery-reservation/downloaded-public-XCT-56dc-retry-r2','pool':'verification_publication','conservative_budget_charge_CPU_seconds':900,'charge_is_measured_cost':False,'origin':{'authority':'Integration owner prospective task2026-10-30, exact56dc downloaded-package retry under original10000CPU verification/publication envelope'},'source_commit':'56dc5a4490ecdd0f5a317908c33b5acfc6dc0f54','previous_event21_failed_reservation900_retained_no_refund':True,'prior_failure_reported_waited_CPU_seconds':2.525127,'failure_scope':'Trusted qualifier child FSIZE32MiB prevented source-bound runner from requesting its recorded64MiB file limit in preexec; candidate/verifier/model/gates untouched','retry_invocation_limits':{'CPU_seconds':900,'address_space_bytes':2*1024**3,'file_size_bytes':64*1024**2},'original_final90min_reserve_starts_utc':'2026-10-30T09:37:44Z','original_end_utc':'2026-10-30T11:07:44Z','refund_CPU_seconds':0,'new_spending_USD':0,'qualified_simulated_commercial_earnings_microUSD':0}
 head=m.append_chain(target,event);rows=[json.loads(x) for x in target.read_bytes().splitlines()];totals={k:sum(r['event']['conservative_budget_charge_CPU_seconds'] for r in rows if r['event']['pool']==k) for k in ('experiment','verification_publication')};caps={'experiment':36000,'verification_publication':10000}
 if len(rows)!=22 or rows[-1]['sequence']!=22 or not target.read_bytes().startswith(raw) or any(totals[k]>caps[k] for k in caps):raise AssertionError('event22 append invariant')
 observations=[]
 for name in ['downloaded-56dc-xct-bound/RECEIPT.json','downloaded-56dc-xct-direct-bound/RECEIPT.json']:
  p=workspace/name;b=p.read_bytes();v=json.loads(b);observations.append({'path':name,'file_sha256':sha(b),'canonical_semantic_sha256':sha(canon(v)),'state':v['state'],'limits':v['limits'],'reported_waited_CPU_seconds':v['waited_cpu_seconds'],'full_group_CPU_attribution_complete':v.get('aggregate_cpu_complete') is True,'reservation_covered_by_event':21 if '-direct-' not in name else 22,'additional_charge_for_observation':0})
 replay=workspace/'downloaded-56dc-xct-direct/REPLAY_RECEIPT.json';rraw=replay.read_bytes();rv=json.loads(rraw);download=workspace/'source-56dc-download.json';d=json.loads(download.read_text())
 write(out/'OBSERVATIONS.json',{'schema':'agi-alpha/event21-failure-event22-observations008/v1','observations':observations,'latest_actual_replay':{'path':str(replay.relative_to(workspace)),'file_sha256':sha(rraw),'status':rv['status'],'separate_report_status':rv.get('separate_report_status'),'child_CPU_seconds':rv.get('resources',{}).get('child_cpu_seconds'),'scope':rv['scope'],'candidate_source_sha256':rv['source_sha256'],'separate_verifier_sha256':rv.get('separate_verifier_sha256')},'archive_download':{'source_file':str(download.relative_to(workspace)),'source_file_sha256':sha(download.read_bytes()),**d},'all_network_total_bytes':None,'duplicate_archive_paths_not_assumed_distinct_transfers':True,'actual_full_view_obstruction_replay_is_not_commercial_success':True,'no_nested_CPU_double_charge_or_refund':True})
 write(out/'CUMULATIVE_COST_RESOURCE.json',{'schema':'agi-alpha/overnight008-cost-resource-recovery-v3','recorded_utc':datetime.now(timezone.utc).isoformat(),'prior_ledger_sha256':sha(raw),'prior_chain_head_sha256':json.loads(raw.splitlines()[-1])['record_sha256'],'chain_head_sha256':head,'events':22,'conservative_reserved_CPU_seconds':totals,'original_CPU_ceilings':caps,'remaining_accounting_reservation_capacity_CPU_seconds':{k:caps[k]-totals[k] for k in caps},'event21_charge900_unchanged':True,'event22_additional_verifier_charge900':True,'final90minute_time_reserve_unchanged':True,'all_monetary_cost_unknowns_retained':True,'complete_profit_USD':None,'qualified_simulated_commercial_earnings_microUSD':0,'earned_successor_funding':'DEFERRED','no_new_spending_or_error_budget_reset':True,'self_CPU_seconds':time.process_time()-start,'already_inside_economics200CPU_reservation':True})
 checks={'first21_journal_lines_byte_unchanged':target.read_bytes().startswith(raw),'event22_exactly_once':len(rows)==22,'event21_failed900_not_refunded':rows[-2]['event']['conservative_budget_charge_CPU_seconds']==900,'prior_run005_all_files_unchanged':all(sha((prior/n).read_bytes())==h for n,h in old_files.items()),'verifier_total6740_and_remaining3260':totals['verification_publication']==6740 and caps['verification_publication']-totals['verification_publication']==3260,'original_experiment_pool_unchanged':totals['experiment']==11660}
 if not all(checks.values()):raise AssertionError(checks)
 write(out/'APPEND_VERIFICATION.json',{'checks':checks,'append_source_sha256':sha(Path(__file__).read_bytes()),'chain_helper_sha256':sha(helper.read_bytes())})
 with (out/'APPEND_SOURCE.py.txt').open('xb') as f:f.write(Path(__file__).read_bytes())
 write(out/'BUNDLE_SHA256.json',{p.name:sha(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file() and p.name!='BUNDLE_SHA256.json'})
 print(json.dumps({'output':str(out),'events':22,'reserved_CPU':totals,'remaining_CPU':{k:caps[k]-totals[k] for k in caps},'latest_replay_status':rv['status'],'latest_waited_CPU':observations[-1]['reported_waited_CPU_seconds'],'qualified_earnings':0}))
if __name__=='__main__':main()
