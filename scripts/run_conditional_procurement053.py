"""Bounded conditional procurement fixtures over the one canonical native ledger.

No real suppliers, customers, agreements or payments. The ten scenario accounts
are independent; neither their seed capital nor their earnings are pooled.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from adaptive_enterprise.instruments import (SOURCE_PATHS as INSTRUMENT_SOURCES,
    prepare_services, audit_admission, check_job, execute_job)
from connected_enterprise.finance import JournalAccount,SOURCE_PATHS,audit_journal
from commercial.ledger import digest,read_bound

PROTOCOL_PATH=ROOT/'campaign/conditional-procurement-053/PROTOCOL.json'


def model_from_protocol():
    protocol=json.loads(PROTOCOL_PATH.read_text())
    first,second=protocol['first_buyer'],protocol['second_buyer']
    model={'opening':protocol['opening_microUSD'],'setup_search_development':protocol['setup_search_development_microUSD'],
        'bundle_assembly':protocol['assembly_microUSD'],'proposal_per_opportunity':protocol['proposal_microUSD_per_opportunity'],
        'payment_bps':protocol['payment_fee']['bps'],'payment_fixed':protocol['payment_fee']['fixed_microUSD'],
        'tax_bps':protocol['tax_bps'],'primitive_price':first['price_microUSD'],'bundle_price':second['price_microUSD'],
        'primitive_buyer':{'benefit':first['benefit_microUSD'],'ordinary_outside':first['ordinary_complete_outside_microUSD'],
            'switching':first['switching_microUSD']},
        'bundle_buyer':{'benefit':second['benefit_microUSD'],'ordinary_outside':second['ordinary_complete_outside_microUSD'],
            'self_service':second['self_service_price_microUSD'],'self_service_quality_bps':second['self_service_quality_bps'],
            'switching':second['switching_microUSD']}}
    model.update({k+'_per_component':v for k,v in protocol['component_costs_microUSD'].items()})
    model.update({k+'_per_sale':v for k,v in protocol['shared_sale_costs_microUSD'].items()})
    return model,tuple(protocol['cases']),tuple(protocol['policies'])


MODEL,CASES,POLICIES=model_from_protocol()


def invoice(components,price,*,surcharge=0):
    result={key:MODEL[key]*components for key in ('production_per_component','supplier_per_component',
        'verification_per_component','support_per_component')}
    result.update({key:MODEL[key] for key in ('acquisition_per_sale','onboarding_per_sale','maintenance_per_sale','financing_per_sale')})
    result['bundle_assembly']=MODEL['bundle_assembly'] if components==3 else 0
    result['provider_surcharge']=surcharge
    result['payment_fee']=(price*MODEL['payment_bps']+9999)//10000+MODEL['payment_fixed']
    return result


def participation(kind,case):
    b=MODEL[kind+'_buyer'];benefit=0 if case=='no_demand' else b['benefit']
    price=MODEL[kind+'_price']
    ours=benefit-price-b['switching'];ordinary=benefit-b['ordinary_outside']
    options={'us':ours,'ordinary_complete':ordinary,'no_purchase':0}
    if kind=='bundle':options['self_service']=benefit*b['self_service_quality_bps']//10000-b['self_service']
    return {'selected':ours>max(v for k,v in options.items() if k!='us'),
        'utilities_microUSD':options,'scope':'Authored public fixture utilities, not actual buyer consent.'}


def _procurement_plan(root,manifest,job,case,policy,earned):
    from connected_enterprise.conditional_procurement053 import fixture_quotes,select,SERVICES,ASSEMBLY
    raw=read_bound(root,job['input'],job['input_sha256'])
    quotes=fixture_quotes(raw,case=case,now=24)
    costs=invoice(3,MODEL['bundle_price'])
    base_procurement=3*(MODEL['production_per_component']+MODEL['supplier_per_component'])+MODEL['bundle_assembly']
    overhead=sum(costs.values())-base_procurement
    budget=max(0,earned-overhead)
    selection=select(raw,quotes,now=24,budget_microUSD=budget,policy=policy)
    parts=sum(min(q['cost_microUSD'] for q in quotes if q['service_id']==service)for service in SERVICES)
    integrated=[q['cost_microUSD'] for q in quotes if q['service_id']=='operations_bundle']
    lowest=min([parts]+integrated)+ASSEMBLY
    return {'valid':selection['status']=='READY','selection':selection,'quotes':quotes,'case':case,
        'non_procurement_invoice':overhead,'base_procurement':base_procurement,
        'lowest_quoted_complete_invoice':lowest+overhead,'input_sha256':job['input_sha256']}


def _procurement_execute(root,manifest,job,plan):
    from connected_enterprise.conditional_procurement053 import execute
    raw=read_bound(root,job['input'],job['input_sha256'])
    result=execute(raw,plan['quotes'],plan['selection'],now=24,
        default_service='kpi_variance' if plan['case']=='provider_default' else None)
    if result['accepted']:
        check_job(root,manifest,job,artifact=result['artifact'])
    return result


def _settle(account,job,ident,price,day,tax_paid):
    account.execute('wallet',{'buyer':ident+'-SIM-wallet','amount':price},day)
    account.execute('offer',{'id':ident,'buyer':ident+'-SIM-wallet','price':price,
        'job_id':job['id'],'deadline':day+12},day)
    for offset,action in enumerate(('consent','fund','prepare','release')):
        account.execute('event',{'id':ident,'event_id':ident+'-'+action,'action':action},day+offset)
    profit=account.snapshot()['summary']['profit']
    tax=max(0,max(0,profit+tax_paid)*MODEL['tax_bps']//10000-tax_paid)
    if tax:account.cost(ident+'-tax',tax,day+3)
    return tax_paid+tax


def run_case(source,manifest,private,case,policy,prereg_digest):
    accepted=[j for j in manifest['jobs'] if j['accepted']]
    bundle=next(j for j in accepted if j['service_id']=='operations_bundle')
    primitive=next(j for j in accepted if j['service_id']=='reconciliation'
        and not set(j['work_keys'])&set(bundle['work_keys']))
    path=private/(case+'-'+policy+'.sqlite')
    contract='conditional-procurement053-'+case+'-'+policy
    account=JournalAccount(source,manifest,path,opening=MODEL['opening'],working=0,contract=contract)
    opportunities=[];tax_paid=0
    try:
        setup=account.spend('setup','research_search_development',MODEL['setup_search_development'],0,
            {'preregistration_sha256':prereg_digest},1,allow_seed=True)
        if setup is None:raise ValueError('SETUP_NOT_FUNDED')
        for index,(kind,job) in enumerate((('primitive',primitive),('bundle',bundle))):
            day=index*24
            proposal=account.spend('proposal-'+str(index),'finite_procurement_search',MODEL['proposal_per_opportunity'],day,
                {'job_id':job['id'],'preregistration_sha256':prereg_digest},1,allow_seed=True)
            if proposal is None:raise ValueError('PROPOSAL_NOT_FUNDED')
            row={'kind':kind,'job_id':job['id'],'work_keys':job['work_keys'],
                'proposal_cost':MODEL['proposal_per_opportunity'],'proposal_funding':proposal['funding'],
                'participation':participation(kind,case)}
            opportunities.append(row)
            if not row['participation']['selected']:
                row['outcome']='NO_DEMAND_NO_PRODUCTION';continue
            plan=None
            if kind=='bundle':
                earned=account.snapshot()['summary']['unrestrictedEarned']
                plan=_procurement_plan(source,manifest,job,case,policy,earned)
                row['procurement_plan_sha256']=digest(plan)
                row['selected_quote_ids']=plan['selection']['quote_ids']
                row['procurement_budget']=plan['selection']['budget_microUSD']
                if not plan['valid']:
                    row['outcome']='EXPIRED_BEFORE_RESERVATION' if case=='expired' else 'UNAFFORDABLE_NO_RESERVATION'
                    row['lowest_quoted_complete_invoice']=plan['lowest_quoted_complete_invoice']
                    row['earned_before_invoice']=earned
                    row['earned_shortfall']=max(0,plan['lowest_quoted_complete_invoice']-earned)
                    continue
            price=MODEL[kind+'_price']
            costs=invoice(1 if kind=='primitive' else 3,price)
            if plan is not None:
                costs['selected_quote_adjustment']=plan['selection']['total_microUSD']-plan['base_procurement']
            amount=sum(costs.values());row['invoice_components']=costs
            available=account.snapshot()['summary']['unrestrictedEarned']
            row['earned_before_invoice']=available
            funded=account.spend('production-'+str(index),'complete_source_bound_delivery',amount,day,
                {'job_id':job['id'],'invoice':costs,'plan':plan,'preregistration_sha256':prereg_digest},
                price-amount,allow_seed=kind=='primitive')
            if funded is None:
                row['outcome']='UNAFFORDABLE_NO_RESERVATION';row['earned_shortfall']=max(0,amount-available);continue
            row['invoice_funding']=funded['funding'];row['funding_receipt_sha256']=digest(funded)
            if kind=='primitive':
                produced=execute_job(source,job)
            else:
                produced=_procurement_execute(source,manifest,job,plan)
            row['production_accepted']=produced['accepted']
            if not produced['accepted']:
                row['outcome']='PROVIDER_DEFAULT_FULL_INVOICE_INCURRED';continue
            row['production_sha256']=digest(produced)
            row['accepted_component_count']=1 if kind=='primitive' else 3
            row['accepted_component_bindings']=([{'job_id':job['id'],'input_sha256':job['input_sha256'],
                'artifact_sha256':job['artifact_sha256'],'accepted':True}] if kind=='primitive'
                else produced['check']['component_acceptance'])
            tax_paid=_settle(account,job,'sale-'+str(index),price,day,tax_paid)
            row['outcome']='ACCEPTED_COLLECTED';row['collections']=price
        audit=account.audit();independent=audit_journal(account.export(),root=source,manifest=manifest)
        before=account.snapshot();native_source=account.source['sha256']
    finally:account.close()
    with JournalAccount(source,manifest,path,opening=MODEL['opening'],working=0,contract=contract) as reopened:
        if reopened.snapshot()!=before:raise ValueError('SAME_ACCOUNT_REOPEN_CHANGED_FINANCES')
        replay=reopened.audit()
    return {'case':case,'policy':policy,'opportunities':opportunities,
        'native_source_sha256':native_source,'native_audit_accepted':audit['accepted'],
        'independent_audit_accepted':independent['accepted'],'reopen_audit_accepted':replay['accepted'],
        'same_account_reopen_unchanged':True,'summary':before['summary'],
        'financed_by_earnings':opportunities[1].get('invoice_funding')=='EARNED'
            and opportunities[1]['outcome']=='ACCEPTED_COLLECTED'}


def run(output,cases=CASES,policies=POLICIES):
    if (MODEL,CASES,POLICIES)!=model_from_protocol():raise ValueError('PROTOCOL_CHANGED_AFTER_IMPORT')
    output=Path(output)
    if not output.is_absolute() or output.exists():raise ValueError('NEW_ABSOLUTE_OUTPUT_REQUIRED')
    if not cases or any(c not in CASES for c in cases) or len(cases)!=len(set(cases)):raise ValueError('DECLARED_CASE_SUBSET_REQUIRED')
    if not policies or any(p not in POLICIES for p in policies) or len(policies)!=len(set(policies)):raise ValueError('DECLARED_POLICY_SUBSET_REQUIRED')
    output.mkdir(parents=True,mode=0o700);private=output/'private';private.mkdir(mode=0o700)
    source=private/'source';source.mkdir()
    names=set(SOURCE_PATHS)|set(INSTRUMENT_SOURCES)
    for name in sorted(names):
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    from connected_enterprise.conditional_procurement053 import DEPENDENCIES
    bound_names=sorted(names|set(DEPENDENCIES)|{'scripts/run_conditional_procurement053.py',
        'campaign/conditional-procurement-053/PROTOCOL.json'})
    def binding():return {n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in bound_names}
    before=binding()
    prereg={'schema':'conditional-procurement053-native/v1','model':MODEL,'cases':list(cases),'policies':list(policies),
        'source_hashes':before,'case_subset_scope':'FULL_FINITE_EXPERIMENT' if tuple(cases)==CASES and tuple(policies)==POLICIES else 'ENGINEERING_TEST_SUBSET',
        'limits':['All suppliers, quotes, participation and payments are public authored local fixtures, not real agreements.',
            'Complete modeled envelopes include search, failed production and verification; actual billing unknown.',
            'No customer value calibration or discovered economic advantage. Ordinary exhaustive control may tie or win.',
            'Proposal work may use explicit seed research funds; second full delivery invoice requires current earned funds.',
            'Independent scenario accounts are not a pooled business. No signing secrets read or exported.']}
    (output/'PREREGISTRATION.json').write_text(json.dumps(prereg,indent=2)+'\n')
    manifest=prepare_services(source,'services',cohort_seed=53001)
    manifest['native_engine']='exact-permanent-v2';origin=audit_admission(source,manifest,cohort_seed=53001)
    results=[run_case(source,manifest,private,case,policy,digest(prereg)) for case in cases for policy in policies]
    if binding()!=before:raise ValueError('EXPERIMENT_SOURCE_CHANGED_DURING_RUN')
    result={'schema':'conditional-procurement053-native-result/v1','preregistration_sha256':digest(prereg),
        'source_binding_sha256':digest(before),'origin_audit_accepted':origin['accepted'],'cases':results,
        'scope':'CONDITIONAL_NATIVE_SIMULATION_NOT_ACTUAL_COMMERCE','actual_revenue':None,'actual_complete_cost':None,
        'causal_composed_advantage':None,'public_allowlist':['PREREGISTRATION.json','RESULT.json']}
    (output/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(run(args.output),indent=2))
