"""Execute generated menus through the existing source-bound native account.

Fresh synthetic 365-day comparison, not live trade. No second ledger, no private
customer data, no assumed receipt, and no adaptation of a frozen prior account.
"""
from __future__ import annotations
import argparse
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil

from commercial.ledger import canonical,digest,strict_json
from commercial.persistence import atomic_bytes
from connected_enterprise.finance import JournalAccount,SOURCE_PATHS,audit_journal
from adaptive_enterprise import instruments as substrate
from adaptive_enterprise.checkers import audit_delivery
from . import market_program as v,mechanism_campaign as campaign
from .inventor_native import completed_resume, require_resume_authority

ROOT=Path(__file__).resolve().parents[1]
CENT=10_000
OPENING=100_000*1_000_000
CONTRACT='omega-private-mechanisms-v3-fresh-synthetic'
TARIFF={'setup_cents':2000,'discovery_per_market_cents':500,'quote_cents':10,
        'maintenance_cents':1200,'successor_cents':500,'tax_bps':2000}
ARMS=('generated','standard','full_control')


def save(path,value):atomic_bytes(Path(path),canonical(value)+b'\n')
def read(path):return strict_json(Path(path).read_bytes())

def checked_path(output):
    out=Path(output).absolute()
    if any(p.is_symlink() for p in (out,*out.parents)):raise ValueError('REGULAR_OWNED_OUTPUT_REQUIRED')
    return out


def source_identity():
    names=set(SOURCE_PATHS)|set(substrate.SOURCE_PATHS)|set(campaign.SOURCE_NAMES)|{'mechanism_harness/mechanism_native.py','mechanism_harness/inventor_native.py'}
    result={}
    for name in sorted(names):
        p=ROOT/name
        if not p.is_file() or any(q.is_symlink() for q in (p,*p.parents)):raise ValueError('REGULAR_SOURCE_REQUIRED:'+name)
        result[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def selected_program(case,arm):
    key={'generated':'inherited','full_control':'full_control','standard':case.get('best_standard')}[arm]
    run=case['runs'].get(key)
    if run is None or run['program'] is None:return v.null_program(case['market'])
    program=run['program']
    if not v.verify(case['market'],program)['accepted']:raise ValueError('UNVERIFIED_CONTRACT')
    return program


def private_type(typ,market,program,stress):
    p={k:copy.deepcopy(typ[k]) for k in ('values','budget_cents','outside_utility')}
    if stress=='no_demand':p['values']=[0]*len(p['values'])
    elif stress=='copycat':
        options=[p['outside_utility']]
        for r in program['rules']:
            j=next(i for i,o in enumerate(market['outcomes']) if o['id']==r['outcome_id'])
            if j and r['price_cents']<=p['budget_cents']:options.append(p['values'][j]-r['price_cents'])
        p['outside_utility']=max(options)
    return p


def fractions_of_price(price,services,market):
    weights=[]
    for s in services:
        singles=[o['cost_cents'] for o in market['outcomes'] if o['services']==[s]]
        weights.append(singles[0] if singles and singles[0]>0 else 1)
    total=sum(weights);parts=[price*w//total for w in weights]
    parts[-1]+=price-sum(parts)
    if any(x<=0 for x in parts):raise ValueError('POSITIVE_COMPONENT_PRICES_REQUIRED')
    return parts


def ledger_costs(study,records,successor):
    spends={'v3-setup':TARIFF['setup_cents']*CENT,
            'v3-discovery':len(campaign.CASES)*TARIFF['discovery_per_market_cents']*CENT}
    costs={'v3-freeze-'+digest(campaign.logical(study))[:24]:0,
           'v3-maintenance':TARIFF['maintenance_cents']*CENT}
    revenue=0
    for r in records:
        spends[f"v3-quote-{r['ordinal']}"]=TARIFF['quote_cents']*CENT
        if r['status'] in ('SETTLED','REFUNDED'):
            spends[f"v3-production-{r['ordinal']}"]=r['outcome']['cost_cents']*CENT
        if r['status']=='SETTLED':
            revenue+=r['choice']['price_cents']*CENT
            costs[f"v3-fee-{r['ordinal']}"]=v.fee(r['choice']['price_cents'],r['payment_bps'])*CENT
    pretax=revenue-sum(spends.values())-sum(costs.values())
    # Conservative declared provision before successor R&D; no deduction is
    # assumed for that last expenditure. This is NOT a real tax calculation.
    costs['v3-modeled-tax']=max(0,pretax)*TARIFF['tax_bps']//10000
    if successor is not None:spends['v3-successor']=TARIFF['successor_cents']*CENT
    return spends,costs,revenue


def run(output,*,arm='generated',stress='central',resume=False):
    if arm not in ARMS or stress not in ('central','no_demand','copycat','failed_acceptance'):
        raise ValueError('REGISTERED_ARM_AND_STRESS_REQUIRED')
    out=checked_path(output);source=source_identity()
    if not resume:
        out.mkdir(parents=True,exist_ok=True)
        if any(out.iterdir()):raise FileExistsError('NEW_ACCOUNT_REQUIRED_USE_RESUME')
        save(out/'SOURCE.json',source);save(out/'CONTRACT.json',{'arm':arm,'stress':stress,'tariff':TARIFF})
    elif not out.is_dir() or read(out/'SOURCE.json')!=source or read(out/'CONTRACT.json')!={'arm':arm,'stress':stress,'tariff':TARIFF}:
        raise ValueError('SOURCE_MATCHED_EXISTING_ACCOUNT_REQUIRED')
    if resume:
        require_resume_authority(out)
        if (out/'REPORT.json').exists():
            return completed_resume(out, opening=OPENING, contract=CONTRACT,
                                    report_name='REPORT.json', public_audit=audit)
    runtime=out/'runtime'
    if not (out/'MANIFEST.json').exists():
        for name in set(SOURCE_PATHS)|set(substrate.SOURCE_PATHS):
            target=runtime/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
        manifest=substrate.prepare_services(runtime,'services',cohort_seed=391900,jobs_per_service=max(32,8+len(campaign.CASES)*9))
        save(out/'MANIFEST.json',manifest)
    manifest=read(out/'MANIFEST.json')
    account=JournalAccount(runtime,manifest,out/'account.sqlite',opening=OPENING,working=0,contract=CONTRACT)
    records=[];successor=None
    try:
        for ident,kind,cost in (('v3-setup','setup',TARIFF['setup_cents']),
                                ('v3-discovery','discovery',len(campaign.CASES)*TARIFF['discovery_per_market_cents'])):
            if account.spend(ident,kind,cost*CENT,0,{'source':source,'arm':arm,'tariff':TARIFF,'basis':'AUTHORED_PREPAID_RESOURCE_ENVELOPE'},1,allow_seed=True) is None:
                raise ValueError('UNFUNDED_CONSTRUCTION')
        if (out/'STUDY.json').exists():
            study=read(out/'STUDY.json');campaign.audit(study)
        else:
            study=campaign.execute();study['source']=campaign.source_identity();save(out/'STUDY.json',study)
        if not study['all_synthesized_programs_verified']:raise ValueError('NO_OPERATION_FROM_UNRESOLVED_MECHANISM')
        frozen_id='v3-freeze-'+digest(campaign.logical(study))[:24]
        account.cost(frozen_id,0,1)  # source-bound publication before any private buyer selection
        ordinal=0
        for case in study['cases']:
            m=case['market'];p=selected_program(case,arm)
            for typ in m['types']:
                ordinal+=1;day=2+ordinal*3
                file=out/f'order-{ordinal:03d}.json'
                if file.exists():
                    r=read(file)
                    if r['program_sha256']!=digest(p) or r['market_sha256']!=digest(m):raise ValueError('FROZEN_ORDER_CHANGED')
                else:
                    work={'source':source,'market_sha256':digest(m),'program_sha256':digest(p),'ordinal':ordinal}
                    paid=account.spend(f'v3-quote-{ordinal}','acquisition',TARIFF['quote_cents']*CENT,day,work,1,allow_seed=True)
                    if paid is None:raise ValueError('UNFUNDED_ACQUISITION')
                    private=private_type(typ,m,p,stress);choice=v.buyer_choose(m,p,private)
                    outcome=next(o for o in m['outcomes'] if o['id']==choice['outcome_id'])
                    jobs=[]
                    for service in outcome['services']:
                        job=[j for j in manifest['jobs'] if j['service_id']==service][7+ordinal]
                        raw=read(runtime/job['input']);jobs.append({'job':job,'raw':raw})
                    supported=all(j['job']['service_id']!='reconciliation' or all(j['raw']['units'].get(t) for t in ('invoices','payments')) for j in jobs)
                    fee=v.fee(choice['price_cents'],m['payment_bps'])
                    required=(choice['price_cents']+outcome['cost_cents']+fee)*CENT
                    affordable=account.snapshot()['summary']['available']>=required
                    r={'ordinal':ordinal,'day':day,'market_sha256':digest(m),'program_sha256':digest(p),
                       'type_id':typ['id'],'private_type':private,'choice':choice,'outcome':outcome,
                       'payment_bps':m['payment_bps'],'jobs':jobs,'supported':supported,'affordable':affordable,
                       'status':'PLANNED','artifacts':[]}
                    save(file,r)
                if r['choice']['declined'] or not r['supported'] or not r['affordable']:
                    r['status']='DECLINED'
                else:
                    buyer=f'SIM-v3-buyer-{ordinal}'
                    prices=fractions_of_price(r['choice']['price_cents'],r['outcome']['services'],m)
                    account.execute('wallet',{'buyer':buyer,'amount':r['private_type']['budget_cents']*CENT},day)
                    ids=[]
                    for j,(jobrec,price) in enumerate(zip(r['jobs'],prices)):
                        ident=f'v3-trade-{ordinal}-{j}';ids.append(ident)
                        account.execute('offer',{'id':ident,'buyer':buyer,'price':price*CENT,'job_id':jobrec['job']['id'],'deadline':day+5},day)
                        for action in ('consent','fund'):
                            account.execute('event',{'id':ident,'action':action,'event_id':ident+'-'+action},day)
                    work={'source':source,'program_sha256':digest(p),'request_sha256':digest({'market':digest(m),'buyer':buyer,'choice':r['choice'],'jobs':[j['job']['id'] for j in r['jobs']]})}
                    paid=account.spend(f'v3-production-{ordinal}','production_contract',r['outcome']['cost_cents']*CENT,day,work,
                                       max(1,r['choice']['seller_contribution_cents']*CENT),allow_seed=True)
                    if paid is None:raise ValueError('UNFUNDED_PRODUCTION_AFTER_ORDER')
                    artifacts=[]
                    for j in r['jobs']:
                        sid=j['job']['service_id'];raw=j['raw']
                        artifact=substrate.produce(raw,'generated_schema',mode='conventional')
                        if stress=='failed_acceptance':artifact['outcome_scope']='intake_readiness'
                        check=audit_delivery(sid,raw,artifact)
                        reference=read(runtime/j['job']['artifact'])
                        equivalent=substrate._semantics(reference)==substrate._semantics(artifact)
                        artifacts.append({'artifact':artifact,'check':check,'admitted_outcome_equal':equivalent})
                    accepted=all(a['check']['accepted'] and a['artifact']['outcome_scope']=='complete_outcome' and a['admitted_outcome_equal'] for a in artifacts)
                    if accepted:
                        account.cost(f'v3-fee-{ordinal}',v.fee(r['choice']['price_cents'],m['payment_bps'])*CENT,day)
                        for ident in ids:
                            for action in ('prepare','release'):
                                account.execute('event',{'id':ident,'action':action,'event_id':ident+'-'+action},day+1)
                        r['status']='SETTLED'
                    else:
                        for ident in ids:account.execute('event',{'id':ident,'action':'refund','event_id':ident+'-refund'},day+1)
                        r['status']='REFUNDED'
                    r['artifacts']=artifacts;r['funding']=paid;r['native_order_ids']=ids;r['component_prices_cents']=prices
                save(file,r);records.append(r)
        account.cost('v3-maintenance',TARIFF['maintenance_cents']*CENT,364)
        spends,costs,revenue=ledger_costs(study,records,None)
        account.cost('v3-modeled-tax',costs['v3-modeled-tax'],364)
        # Spend earned money only after every declared annual obligation is paid.
        work={'source':source,'parent_memory_sha256':digest(study['cases'][-1]['memory_after']),
              'purpose':'Construct and independently verify a fresh private-information mechanism'}
        funding=account.spend('v3-successor','instrument',TARIFF['successor_cents']*CENT,364,work,1,allow_seed=False)
        if funding is not None:
            from .market_cases import market
            from .mechanism_synthesis import synthesize
            mnext=market(391104,'substitute')
            built=synthesize(mnext,memory=study['cases'][-1]['memory_after'])
            successor={'funding':funding,'market':mnext,'construction':built,
                       'verified':built['program'] is not None and v.verify(mnext,built['program'])['accepted'],
                       'scope':'Executed earned-funded successor, not unique causal enablement or a registered confirmation case.'}
            save(out/'SUCCESSOR.json',successor)
        exported=account.export();save(out/'NATIVE_EXPORT.json',exported)
        result={'schema':'omega/native-private-mechanisms/v3','source':source,'arm':arm,'stress':stress,
                'study_logical_sha256':digest(campaign.logical(study)),'records_sha256':[digest(r) for r in records],
                'native_summary':account.snapshot()['summary'],'native_audit':account.audit(),'tariff':TARIFF,
                'opportunities':len(records),'settled_buyers':sum(r['status']=='SETTLED' for r in records),
                'declined_buyers':sum(r['status']=='DECLINED' for r in records),'refunded_buyers':sum(r['status']=='REFUNDED' for r in records),
                'successor':successor,'opening_microUSD':OPENING,'clock':{'start_day':0,'end_day':364,'days':365},
                'actual_revenue_usd':0,'scope':'Generated private-information menus, executed source-bound outcomes, declared modeled costs and canonical native simulated commerce. No real buyers or complete-lifecycle superiority claim.'}
        if source!=source_identity():raise ValueError('SOURCE_CHANGED_DURING_RUN')
        save(out/'REPORT.json',result)
    finally:account.close()
    audit(out)
    return result


def audit(output):
    out=checked_path(output);r=read(out/'REPORT.json');study=read(out/'STUDY.json');source=source_identity()
    if (r['source']!=source or read(out/'SOURCE.json')!=source or r['actual_revenue_usd']!=0
            or r['opening_microUSD']!=OPENING or r['tariff']!=TARIFF
            or r['clock']!={'start_day':0,'end_day':364,'days':365}):raise ValueError('SOURCE_OR_CLAIM_CHANGED')
    if r['study_logical_sha256']!=digest(campaign.logical(study)):raise ValueError('STUDY_CHANGED')
    campaign.audit_resources(study)
    if read(out/'CONTRACT.json')!={'arm':r['arm'],'stress':r['stress'],'tariff':TARIFF}:raise ValueError('REGISTERED_CONTRACT_CHANGED')
    manifest=read(out/'MANIFEST.json');runtime=out/'runtime';exp=read(out/'NATIVE_EXPORT.json')
    audit_journal(exp,root=runtime,manifest=manifest)
    if exp['ledger']['summary']!=r['native_summary']:raise ValueError('FINANCIAL_SUMMARY_CHANGED')
    acts=exp['ledger']['actions'];journal=exp['connected_journal']['entries'];records=[];ordinal=0;native_ids=[]
    for case,(seed,family) in zip(study['cases'],campaign.CASES):
        from .market_cases import market
        m=market(seed,family)
        if m!=case['market']:raise ValueError('PUBLIC_MARKET_CHANGED')
        p=selected_program(case,r['arm'])
        for typ in m['types']:
            ordinal+=1;rec=read(out/f'order-{ordinal:03d}.json');records.append(rec)
            private=private_type(typ,m,p,r['stress']);choice=v.buyer_choose(m,p,private)
            if (rec['ordinal']!=ordinal or rec['day']!=2+ordinal*3 or rec['type_id']!=typ['id']
                    or rec['market_sha256']!=digest(m) or rec['program_sha256']!=digest(p)
                    or rec['private_type']!=private or rec['choice']!=choice):raise ValueError('STRATEGIC_CHOICE_CHANGED')
            outcome=next(o for o in m['outcomes'] if o['id']==choice['outcome_id'])
            if rec['outcome']!=outcome or rec['payment_bps']!=m['payment_bps']:raise ValueError('PRODUCT_OR_FEES_CHANGED')
            jobs=[]
            for service in outcome['services']:
                job=[j for j in manifest['jobs'] if j['service_id']==service][7+ordinal]
                jobs.append({'job':job,'raw':read(runtime/job['input'])})
            if jobs!=rec['jobs']:raise ValueError('PRODUCTIVE_SOURCE_CHANGED')
            known=all(j['job']['service_id']!='reconciliation' or all(j['raw']['units'].get(t) for t in ('invoices','payments')) for j in jobs)
            if rec['supported']!=known:raise ValueError('READINESS_CHANGED')
            quote=[e for e in journal if e['request'].get('operation')=='spend' and e['request'].get('id')==f'v3-quote-{ordinal}']
            expected_work={'source':source,'market_sha256':digest(m),'program_sha256':digest(p),'ordinal':ordinal}
            if len(quote)!=1 or quote[0]['request']['work']!=expected_work or quote[0]['request']['day']!=rec['day']:
                raise ValueError('SOURCE_BOUND_QUOTE_REQUIRED')
            available=acts[quote[0]['receipt']['native_event_sequence']]['after']['available']
            required=(choice['price_cents']+outcome['cost_cents']+v.fee(choice['price_cents'],m['payment_bps']))*CENT
            if rec['affordable']!=(available>=required):raise ValueError('CURRENT_CASH_CHOICE_CHANGED')
            related=[a for a in acts if a['op']=='offer' and a['args']['id'].startswith(f'v3-trade-{ordinal}-')]
            if choice['declined'] or not known or not rec['affordable']:
                if rec['status']!='DECLINED' or related:raise ValueError('FALSE_REFUSAL_OR_FORCED_SALE')
                continue
            prices=fractions_of_price(choice['price_cents'],outcome['services'],m)
            if rec['component_prices_cents']!=prices or len(related)!=len(prices) or len(rec['artifacts'])!=len(prices):raise ValueError('COMPONENT_BUDGET_CHANGED')
            wallet=[a for a in acts if a['op']=='wallet' and a['args']['buyer']==f'SIM-v3-buyer-{ordinal}']
            if len(wallet)!=1 or wallet[0]['args']['amount']!=private['budget_cents']*CENT or wallet[0]['day']!=rec['day']:
                raise ValueError('VOLUNTARY_BUYER_BUDGET_CHANGED')
            production=[e for e in journal if e['request'].get('operation')=='spend' and e['request'].get('id')==f'v3-production-{ordinal}']
            prod_work={'source':source,'program_sha256':digest(p),'request_sha256':digest({'market':digest(m),'buyer':f'SIM-v3-buyer-{ordinal}','choice':choice,'jobs':[j['job']['id'] for j in jobs]})}
            if len(production)!=1 or production[0]['request']['work']!=prod_work or production[0]['request']['day']!=rec['day'] or production[0]['receipt']!=rec['funding']:
                raise ValueError('SOURCE_BOUND_PRODUCTION_REQUIRED')
            for j,(jr,price,saved) in enumerate(zip(jobs,prices,rec['artifacts'])):
                artifact=substrate.produce(jr['raw'],'generated_schema',mode='conventional')
                if r['stress']=='failed_acceptance':artifact['outcome_scope']='intake_readiness'
                check=audit_delivery(jr['job']['service_id'],jr['raw'],artifact)
                equal=substrate._semantics(read(runtime/jr['job']['artifact']))==substrate._semantics(artifact)
                if saved!={'artifact':artifact,'check':check,'admitted_outcome_equal':equal}:raise ValueError('INDEPENDENT_OUTPUT_CHECK_CHANGED')
                ident=f'v3-trade-{ordinal}-{j}';native_ids.append(ident)
                of=[a for a in related if a['args']['id']==ident]
                if len(of)!=1 or of[0]['args']!={'id':ident,'buyer':f'SIM-v3-buyer-{ordinal}','price':price*CENT,'job_id':jr['job']['id'],'deadline':rec['day']+5}:raise ValueError('NATIVE_OFFER_CHANGED')
                events=[a for a in acts if a['op']=='event' and a['args']['id']==ident]
                wanted=['consent','fund','prepare','release'] if rec['status']=='SETTLED' else ['consent','fund','refund']
                if [a['args']['action'] for a in events]!=wanted or [a['day'] for a in events]!=[rec['day'],rec['day']]+[rec['day']+1]*(len(wanted)-2):raise ValueError('NATIVE_LIFECYCLE_INCOMPLETE')
            accepted=all(a['check']['accepted'] and a['admitted_outcome_equal'] and a['artifact']['outcome_scope']=='complete_outcome' for a in rec['artifacts'])
            if rec['status']!=('SETTLED' if accepted else 'REFUNDED'):raise ValueError('UNACCEPTED_REVENUE')
    if {a['args']['id'] for a in acts if a['op']=='offer'}!=set(native_ids):raise ValueError('UNREPORTED_ORDER')
    successor=r['successor']
    if successor is not None:
        from .market_cases import market
        if successor['market']!=market(391104,'substitute'):raise ValueError('FRESH_SUCCESSOR_CHANGED')
        payments=[e for e in journal if e['request'].get('operation')=='spend' and e['request'].get('id')=='v3-successor']
        if len(payments)!=1 or payments[0]['receipt']!=successor['funding'] or payments[0]['request']['allow_seed'] is not False:raise ValueError('EARNED_SUCCESSOR_REQUIRED')
        if successor!=read(out/'SUCCESSOR.json') or successor['funding']['funding']!='EARNED':raise ValueError('UNSUPPORTED_SUCCESSOR_FUNDING')
        built=successor['construction'];ok=built['program'] is not None and v.verify(successor['market'],built['program'])['accepted']
        if successor['verified']!=ok:raise ValueError('UNVERIFIED_SUCCESSOR')
    spends,costs,revenue=ledger_costs(study,records,successor)
    actual_spends=[e for e in journal if e['request']['operation']=='spend']
    actual_costs=[e for e in journal if e['request']['operation']=='execute' and e['request']['op']=='cost']
    if len(actual_spends)!=len(spends) or {e['request']['id'] for e in actual_spends}!=set(spends):raise ValueError('MISSING_OR_EXTRA_RESOURCE_COST')
    for e in actual_spends:
        q=e['request']
        if e['status']!='COMPLETE' or q['amount']!=spends[q['id']] or q['work'].get('source')!=source:raise ValueError('UNBOUND_RESOURCE_COST')
    if len(actual_costs)!=len(costs) or {e['request']['args']['id'] for e in actual_costs}!=set(costs):raise ValueError('MISSING_OR_EXTRA_REQUIRED_DEBIT')
    for e in actual_costs:
        ident=e['request']['args']['id']
        day=1 if ident.startswith('v3-freeze-') else 364 if ident in ('v3-maintenance','v3-modeled-tax') else 2+int(ident.rsplit('-',1)[1])*3
        if e['status']!='COMPLETE' or e['request']['args']['amount']!=costs[ident] or e['request']['day']!=day:raise ValueError('COST_OR_TAX_DERIVATION_CHANGED')
    freeze_pos=[idx for idx,a in enumerate(acts) if a['op']=='cost' and a['args']['id'].startswith('v3-freeze-')]
    if len(freeze_pos)!=1 or any(idx<freeze_pos[0] for idx,a in enumerate(acts) if a['op'] in ('wallet','offer')):raise ValueError('PUBLIC_FREEZE_MUST_PRECEDE_BUYER')
    total=sum(spends.values())+sum(costs.values());summary=exp['ledger']['summary']
    if summary['revenue']!=revenue or summary['collections']!=revenue or summary['expenses']!=total or summary['profit']!=revenue-total:raise ValueError('COMPLETE_ACCOUNTING_NOT_RECONSTRUCTED')
    if r['records_sha256']!=[digest(x) for x in records] or r['opportunities']!=ordinal:raise ValueError('DENOMINATORS_CHANGED')
    for field,status in (('settled_buyers','SETTLED'),('declined_buyers','DECLINED'),('refunded_buyers','REFUNDED')):
        if r[field]!=sum(x['status']==status for x in records):raise ValueError('OPERATING_COUNTS_CHANGED')
    return {'accepted':True,'report_sha256':digest(r),'verified_expenses_microUSD':total,'verified_revenue_microUSD':revenue,
            'scope':'Canonical native financial audit plus independent complete outcome, buyer choice and contractual cost reconstruction.'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('run','resume','audit'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--arm',choices=ARMS,default='generated')
    p.add_argument('--stress',choices=('central','no_demand','copycat','failed_acceptance'),default='central')
    a=p.parse_args(argv)
    r=audit(a.output) if a.command=='audit' else run(a.output,arm=a.arm,stress=a.stress,resume=a.command=='resume')
    print(json.dumps(r if a.command=='audit' else {k:r[k] for k in ('arm','stress','opportunities','settled_buyers','declined_buyers','refunded_buyers','native_summary','actual_revenue_usd','scope')},indent=2))

if __name__=='__main__':main()
