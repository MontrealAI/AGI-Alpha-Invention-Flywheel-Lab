import hashlib,json,subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
BASE='215b22a5ed73b82ac1d909328d60157c48bd9958'
SOURCES=[]
def source(path,ref=BASE):
    raw=subprocess.run(['git','show',ref+':'+path],cwd=REPO,capture_output=True,check=True).stdout
    SOURCES.append({'path':path,'ref':ref,'git_blob_sha1':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),'sha256':hashlib.sha256(raw).hexdigest(),'url':'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/'+ref+'/'+path})
    return json.loads(raw) if path.endswith('.json') else raw.decode()
def main():
    foundry=source('docs/agi-alpha-flywheel/examples/foundry-results.json')
    r2=source('experiments/public_portfolio_20261102/evidence/economics-r2/report/CLAIMS.json')
    paired=source('experiments/paired_acquisition_20261102/evidence/SUMMARY.json')
    n3=source('experiments/next_series_20261102_365c3d6c/n3/RESULT_001.json')
    scope=source('experiments/public_portfolio_20261102/verification/FINAL_EXECUTION_VERDICT.json')
    technical=source('outlearning073/evidence/primary/TECHNICAL_SUMMARY.json','21f78996d25fe1d17b2c560be07e715ac8dc48d9')
    native=source('outlearning073/evidence/primary/native/SUMMARY.json','21f78996d25fe1d17b2c560be07e715ac8dc48d9')
    operational=source('operational075/evidence/SUMMARY.json','b32d6913754a6b83c3df76604647418de70d9748')
    grid=source('experiments/outlearning_grid074/TRANSFER_RESULT.json','000d2b30f2073a228c286c5ae736af71ab6fec41')
    texts=[('experiments/public_portfolio_20261102/README.md',BASE),('experiments/paired_acquisition_20261102/README.md',BASE),('experiments/next_series_20261102_365c3d6c/REPORT.md',BASE),('portfolio/blue-sky-20261102-dot/I1/REPORT.md','a5df603854f98cbd673204258c8d768e0c759975'),('portfolio/blue-sky-20261102-dot/W1/REPORT.md','a5df603854f98cbd673204258c8d768e0c759975'),('experiments/next_series_20261102/REPORT.md','b2d41c513dfc950648b39e64627a77ada0137a22'),('experiments/portfolio_20261102/README.md','418440e4587165488ccbf5a9d6bc04ba375a4675'),('outlearning073/README.md','21f78996d25fe1d17b2c560be07e715ac8dc48d9'),('experiments/outlearning_20261102_906c4f4d/README.md','7f94f8fed2026b14b53f4ff7c94e1a1f3c35ae68')]
    for path,ref in texts:source(path,ref)
    observations={'schema':'agi-alpha-flywheel-report/evidence/v1','report_date':'2026-11-02','review_date':'2026-11-03','baseline':BASE,'scope':'Compact source-audited public observations. Different experiments are not pooled. These are not complete native exports, fresh market observations, or a physical confirmation.','foundry':{'summary':foundry['summary'],'controls':foundry['controls'],'record_count':len(foundry['records']),'registered_requests_per_arm':foundry['registered_requests_per_arm']},'r2':{'cases':r2['case_summaries'],'verdict':scope,'window':r2['window_calendar_utc'],'finite_market':r2['finite_market_scope']},'paired':{k:paired[k] for k in ['bulk_passed','spatial_passed','registered_case_counts','control_checks_passed','limitation_witnesses_observed','numerical_contract_accepted','native_account_actions','actual_revenue_usd','physical_qualification']},'n3':{'denominators':n3['denominators'],'model_pass':n3['model_pass'],'physical_admission':n3['physical_admission'],'native_accounts_opened':n3['native_accounts_opened']},'outlearning073':{'K2':technical['arms']['K2'],'native_scope':native},'operational075':{'paired_total_driving_seconds_retained_minus_ordinary':operational['paired_total_driving_seconds_retained_minus_ordinary'],'native_account_operated':operational['native_account_operated'],'native_target_achieved':operational['native_target_achieved'],'economic_source':'Authored planning envelope, not native operation or observed demand'},'grid074':{'decision':grid['decision'],'cases':grid['cases'],'learned_advantage':grid['learned_advantage'],'newly_enabled_business':grid['newly_enabled_business']}}
    target=HERE/'evidence';target.mkdir(exist_ok=True)
    (target/'observations.json').write_text(json.dumps(observations,indent=2,sort_keys=True)+'\n')
    (target/'sources.json').write_text(json.dumps({'schema':'agi-alpha-flywheel-report/sources/v1','retrieval_date':'2026-11-03','baseline':BASE,'public_sources_only':True,'sources':SOURCES},indent=2,sort_keys=True)+'\n')
    print(json.dumps({'sources':len(SOURCES),'native_case_summaries':len(observations['r2']['cases']),'foundry_records':len(foundry['records'])}))
if __name__=='__main__':main()
