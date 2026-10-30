import argparse, hashlib, importlib.util, json, os, resource, time
from pathlib import Path
from datetime import datetime, timezone

resource.setrlimit(resource.RLIMIT_CPU,(200,202));resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
def sha(v):return hashlib.sha256(v).hexdigest()
def write(path,value):
 with path.open('xb') as f:f.write(json.dumps(value,indent=2,allow_nan=False).encode()+b'\n');f.flush();os.fsync(f.fileno())
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--economics',required=True);ap.add_argument('--output',required=True);args=ap.parse_args();base=Path(args.economics).resolve();out=Path(args.output).resolve();prior=base/'run003';start=time.process_time();out.mkdir(parents=True,exist_ok=False)
 frozen=json.loads((base/'RECOVERY_FILES_SHA256.json').read_text())
 for name,digest in frozen.items():
  if sha((base/name).read_bytes())!=digest:raise ValueError('original frozen artifact changed '+name)
 prior_bundle=json.loads((prior/'BUNDLE_SHA256.json').read_text())
 for name,digest in prior_bundle.items():
  if sha((prior/name).read_bytes())!=digest:raise ValueError('event20 bundle changed '+name)
 original=(prior/'AGGREGATION_LEDGER.jsonl').read_bytes();target=out/'AGGREGATION_LEDGER.jsonl'
 with target.open('xb') as f:f.write(original)
 helper=base/'recover_economics_v2.py';spec=importlib.util.spec_from_file_location('recovery2',helper);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 event={'id':'recovery-reservation/downloaded-public-XCT-full-qualification-r1','pool':'verification_publication','conservative_budget_charge_CPU_seconds':900,'charge_is_measured_cost':False,'origin':{'authority':'Integration owner direct prospective task2026-10-30; original10000CPU verifier/publication ceiling unchanged'},'purpose':'Actual source-bound constructor and independent Fraction qualification from downloaded next public packet; replaces no original failed artifacts','prospective_component_limits_CPU_seconds':{'frozen_full_constructor_hard_limit':705,'fraction_checker':180,'supervision_and_margin':15},'observed_CPU_seconds':None,'new_codeload_packet_bytes_cap':128*1024**2,'previous_known_codeload_bytes':107741667,'next_download_actual_bytes':None,'raw_data_about17_8MB_reused_not_falsely_counted_as_a_new_download':True,'scope':'Fresh public-download qualification is distinct from earlier43fe integration child runs and their1300CPU reservation. Nested constructor/checker work is covered by this900, not an additive charge.','refund_CPU_seconds':0,'qualified_simulated_commercial_earnings_microUSD':0,'original_end_utc':'2026-10-30T11:07:44Z','original_final90minute_reserve_starts_utc':'2026-10-30T09:37:44Z','new_spending_authority_USD':0}
 head=m.append_chain(target,event);rows=[json.loads(s) for s in target.read_bytes().splitlines()]
 if len(rows)!=21 or not target.read_bytes().startswith(original) or rows[-1]['sequence']!=21:raise AssertionError('append-only event21 invariant')
 totals={p:sum(r['event']['conservative_budget_charge_CPU_seconds'] for r in rows if r['event']['pool']==p) for p in ('experiment','verification_publication')};caps={'experiment':36000,'verification_publication':10000}
 if any(totals[p]>caps[p] for p in caps):raise AssertionError('original ceiling exceeded')
 receipt={'schema':'agi-alpha/overnight008-public-XCT-qualification-reservation/v1','recorded_utc':datetime.now(timezone.utc).isoformat(),'previous_ledger_sha256':sha(original),'previous_chain_head_sha256':json.loads(original.splitlines()[-1])['record_sha256'],'chain_head_sha256':head,'events':21,'conservative_reserved_CPU_seconds':totals,'original_CPU_ceilings':caps,'remaining_accounting_reservation_capacity_CPU_seconds':{p:caps[p]-totals[p] for p in caps},'new_verification_publication_reservation_CPU_seconds':900,'actual_future_qualification_receipt':'PENDING root versioned source/download/execution receipt; approximate local25CPU is not substituted for the future measured run','new_network_actual_bytes':None,'all_previous_unknown_costs_stay_unknown':True,'original_final90minute_time_reserve_preserved':True,'qualified_simulated_commercial_earnings_microUSD':0,'successor_funding':'DEFER_NO_QUALIFIED_EARNINGS','new_paid_API_calls':0,'new_real_commerce':False,'self_CPU_seconds':time.process_time()-start,'economics_work_already_inside_existing200CPU_reservation':True}
 write(out/'CUMULATIVE_COST_RESOURCE.json',receipt)
 checks={'original21_manifest_files_unchanged':all(sha((base/n).read_bytes())==d for n,d in frozen.items()),'run003_bundle_unchanged':all(sha((prior/n).read_bytes())==d for n,d in prior_bundle.items()),'prior20_lines_byte_preserved':target.read_bytes().startswith(original),'event21_added_exactly_once':rows[-1]['event']['id']==event['id'],'no_original_capacity_reset':True,'new900_not_double_counted_inside_old1300':True,'within_original10k_verifier_ceiling':totals['verification_publication']<=10000}
 if not all(checks.values()):raise AssertionError(checks)
 write(out/'APPEND_VERIFICATION.json',{'checks':checks,'recorded_utc':receipt['recorded_utc'],'source_sha256':sha(Path(__file__).read_bytes()),'chain_helper_sha256':sha(helper.read_bytes())})
 with (out/'APPEND_SOURCE.py.txt').open('xb') as f:f.write(Path(__file__).read_bytes())
 write(out/'BUNDLE_SHA256.json',{p.name:sha(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file()})
 print(json.dumps({'output':str(out),'events':21,'reserved_CPU':totals,'remaining_CPU':receipt['remaining_accounting_reservation_capacity_CPU_seconds'],'qualified_earnings':0,'source_bound_qualification':'reserved, not yet executed'}))
if __name__=='__main__':main()
