"""Matched PR47 reuse with actual native research charges and optional manifest seam."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from adaptive_enterprise.instruments import prepare_services
from adaptive_enterprise.strategies import offer_catalog
from connected_enterprise.finance import JournalAccount
from connected_enterprise.mechanism_choice import MODES,COST_FIELDS
from connected_enterprise.funded_csv_adapter028 import run_funded,ARMS,binding


def policy():
    costs={m:dict.fromkeys(COST_FIELDS,0) for m in MODES if m!='hold'}
    costs['ordinary_reuse'].update(retrieval=10000,verification=200000)
    costs['critic_retain'].update(discovery=1000000,integration=500000,verification=300000,maintenance=10000)
    return {'mode':'optimize','costs':costs,'accept_collect_bps':9700,'future_equivalent_jobs':0,
        'public_basis':'Authored fixed service envelope; no independently measured demand or bills',
        'cost_contract':{'schema':'connected-method-cost-contract/v1','basis':'COMMON_COMPLETE_PRODUCTION_REPLACEMENT',
                        'production_envelope_microUSD':1500000,'covered_operations':['produce','acceptance_check']}}


def campaign(root,output,seed=2810311805):
    root=Path(root);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    spec=json.loads((root/'campaign/mechanism-harness-027/EXISTING_OPERATIONS.json').read_text())
    plan=json.loads((root/'campaign/mechanism-harness-027/PLAN.json').read_text())
    manifest=prepare_services(root,'funded-csv028-inputs-'+str(seed),cohort_seed=seed)
    offer=next(o for o in offer_catalog() if o['service_id']=='reconciliation' and o['method']=='generated_schema')
    rows=[]
    jobs=[j for j in manifest['jobs'] if j['service_id']=='reconciliation' and int(j['id'].split('-')[-1]) in (8,9,15)]
    for job in jobs:
        for arm in ARMS:
            directory=output/(job['id']+'-'+arm);directory.mkdir()
            account=JournalAccount(root,manifest,directory/'state.sqlite',opening=100000000,working=1000000,contract='funded-csv028')
            try:
                r=run_funded(root,account,spec,plan,None,directory/'delivery',arm=arm,ident='service',allow_seed=True,
                    native_manifest=manifest,native_job_id=job['id'],native_policy=policy(),native_offer=offer)
                actual=sum(e['request']['amount'] for e in account.export()['connected_journal']['entries'] if e['status']=='COMPLETE')
                assert actual==r['native_cost_microUSD']
                rows.append({'job_id':job['id'],**{k:v for k,v in r.items() if k!='source'}})
            finally:account.close()
    return {'schema':'funded-csv028-study/v1','source':binding(root),'seed':seed,'rows':rows,
        'scope':'SOURCE_BOUND_NATIVE_RESEARCH_PREPAYMENT_AND_NATIVE_MANIFEST_COMPATIBILITY',
        'canonical_engine_adoption':False,'actual_customers':0,'actual_collections_usd':0,'actual_profit':None,
        'cost_basis':'Authored USD envelopes, not measured bills; whole-invocation CPU/wall includes wrapper, native payments, adaptation, producer, extra revalidation and native audit. Setup/engineering/model/host billing unknown.',
        'claims_not_established':['Complete enterprise profit','Earned-funded scaling','Autonomous invention','Retained advantage','Global game optimum'],
        'controls':'Direct/equal-content/replanned/inherited share native input, typed intake, existing monetary selector, PR47 executor/checker and common production envelope.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='funded-csv028-') as d:
        report=campaign(ROOT,Path(d)/'private')
        with Path(a.output).open('x') as f:json.dump(report,f,sort_keys=True,indent=2)
    print(json.dumps({'cases':len(report['rows']),'accepted':sum(x['accepted'] for x in report['rows']),'engine_adoption':False}))
