"""One fresh, bounded simulated operating turn; actual checked SQLite artifacts.

Run, resume and audit use canonical JournalAccount. No real commerce is claimed.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from connected_enterprise.finance import source_paths_for_manifest, audit_journal
from . import service
from .delivery import produce, default_requests
from .native import BusinessAccount, OPENING, capacity_rows, validate_capacity

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'campaign/genesis_commitment001/'
UNIT = 1_000_000


def read(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 64_000_000:
        raise ValueError('BOUNDED_REGULAR_RECORD_REQUIRED')
    return strict_json(path.read_bytes())


def save(path, value):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('SYMLINK_REFUSED')
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_bytes(path, canonical(value)+b'\n')


def safe_output(path):
    p = Path(path).absolute()
    if any(x.is_symlink() for x in (p,*p.parents)):
        raise ValueError('SYMLINK_REFUSED')
    return p


def source_identity():
    names = source_paths_for_manifest({'schema':service.SCHEMA})
    return {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(set(names))}


def protocol():
    p = read(ROOT/PREFIX/'PROTOCOL.json')
    if p['opening_microUSD'] != OPENING or p['schema'] != 'genesis-commitment001/protocol/v1':
        raise ValueError('EXACT_PRIMARY_SEED_AND_PROTOCOL_REQUIRED')
    return p


def amount(p, dollars, scenario):
    return dollars * UNIT * p['cost_multiplier'].get(scenario, 1)


def delivery_work(p, stage, scenario, start):
    order = 'turn-first' if stage == 'first' else 'turn-successor'
    job = 'restore-first' if stage == 'first' else 'migration-next'
    return {'job':job,'order':order,'buyer':'SIM-'+stage,
            'capacity':{'supplier':'shared-worker','start':start,'end':start+4,'units':1},
            'costs':{k:amount(p,v,scenario) for k,v in p[stage+'_costs_usd'].items()},
            'expected_net':1}


def economic_case(p, stage, scenario):
    b = dict(p['buyer'][stage]);alternatives=dict(p['alternatives_usd'])
    settings=p['scenario_economics']
    if scenario=='favorable_envelope' or scenario in settings['favorable_inherited_by']:
        if stage=='first':b=dict(settings['favorable_envelope']['first_buyer'])
        alternatives={k:settings['favorable_envelope']['all_alternative_prices_usd'] for k in alternatives}
    elif scenario=='demand_only':
        alternatives={k:settings['demand_only']['all_alternative_prices_usd'] for k in alternatives}
    return b, alternatives


def choose_buyer(p, stage, scenario):
    """Only the response-time buyer observes its private valuation and budget.

    The seller posts the registered price, then acts on the returned decision.
    A delayed rival response is revealed at hour 2, never before the quote.
    """
    b, alternatives = economic_case(p,stage,scenario)
    value = 0 if scenario == 'no_demand' else b['value_usd']
    if scenario in {'rival_response', 'commodity_pressure'}:
        alternatives['self_service_total'] = 20 if scenario == 'rival_response' else 100
    outside = max(b['outside_utility_usd'], *(value-v for v in alternatives.values()), 0)
    own = value-b['price_usd']-b['friction_usd']
    buys = b['budget_usd'] >= b['price_usd'] and own > outside
    return {'buy':buys,'value_usd':value,'budget_usd':b['budget_usd'],
            'price_usd':b['price_usd'],'own_utility_usd':own,'outside_utility_usd':outside,
            'alternatives_usd':alternatives,'response_hour':2 if stage=='first' else None,
            'scope':'AUTHORED_MODEL_NOT_CUSTOMER_CONSENT'}


def _spend(account, ident, kind, cents, hour, *, allow_seed, work=None):
    result = account.spend(ident, kind, cents, hour, work or {'cost_category':kind}, 1, allow_seed=allow_seed)
    if result is None:
        raise ValueError('UNAFFORDABLE_REGISTERED_SPEND:'+ident)
    return result


def _tax(account, p, ident, hour):
    entries = account.export()['connected_journal']['entries']
    old = next((e for e in entries if e['key']=='native:cost:'+ident), None)
    if old is not None:
        due = old['request']['args']['amount']
    else:
        paid = sum(a['args']['amount'] for a in account.export()['ledger']['actions']
                   if a['op']=='cost' and a['args']['id'].startswith('turn-tax-'))
        pretax = max(0, account.snapshot()['summary']['profit']+paid)
        due = max(0, pretax*p['tax_numerator']//p['tax_denominator']-paid)
    account.cost(ident, due, hour)


def _register(out, scenario, arm):
    p = protocol()
    if scenario not in p['scenarios'] or arm not in p['arms']:
        raise ValueError('REGISTERED_SCENARIO_AND_ARM_REQUIRED')
    out.mkdir(parents=True, exist_ok=False)
    source = source_identity()
    runtime = out/'source'
    for name in source:
        dest=runtime/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,dest)
    requests=[{'id':r['id'],'request':r,'delivery_path':PREFIX+'deliveries/'+r['id']+'.json'} for r in default_requests()]
    manifest = service.prepare_manifest(runtime, requests)
    reg={'schema':'genesis-commitment001/registration/v1','source':source,'protocol':p,
         'scenario':scenario,'arm':arm,'opening_microUSD':OPENING,'fresh_account':True,
         'prior_account_migrated':False,'manifest_sha256':digest(manifest)}
    reg['binding']=digest(reg)
    save(out/'REGISTRATION.json',reg);save(out/'MANIFEST.json',manifest)
    return reg,manifest


def _bound(out):
    reg,manifest=read(out/'REGISTRATION.json'),read(out/'MANIFEST.json')
    check={k:v for k,v in reg.items() if k!='binding'}
    if digest(check)!=reg['binding'] or reg['source']!=source_identity() or reg['protocol']!=protocol() or reg['manifest_sha256']!=digest(manifest):
        raise ValueError('REGISTERED_SOURCE_OR_PROTOCOL_CHANGED')
    if reg['scenario'] not in reg['protocol']['scenarios'] or reg['arm'] not in reg['protocol']['arms'] or reg['opening_microUSD']!=OPENING or not reg['fresh_account'] or reg['prior_account_migrated']:
        raise ValueError('REGISTERED_ACCOUNT_IDENTITY_CHANGED')
    for name,sha in reg['source'].items():
        file=out/'source'/name
        if file.is_symlink() or hashlib.sha256(file.read_bytes()).hexdigest()!=sha:
            raise ValueError('FROZEN_RUNTIME_CHANGED')
    expected_requests=[{'id':r['id'],'request':r,'delivery_path':PREFIX+'deliveries/'+r['id']+'.json'} for r in default_requests()]
    if manifest != service.prepare_manifest(out/'source',expected_requests):
        raise ValueError('REGISTERED_DEFAULT_REQUESTS_CHANGED')
    service.load_contracts(out/'source',manifest)
    return reg,manifest


def _summary(out,reg,record):
    ledger=record['ledger'];summary=ledger['summary'];orders={r['id']:r['state'] for r in ledger['orders']}
    entries=record['connected_journal']['entries']
    successor=next((e for e in entries if e['key']=='spend:successor-development'),None)
    cost_items=[]
    for e in entries:
        q=e['request']
        if e['status']=='COMPLETE' and q['operation']=='spend':
            cost_items.append({'id':q['id'],'amount_microUSD':q['amount'],'hour':q['day'],
                               'funding':e['funding'],'breakdown':q['work'].get('costs',{})})
        elif e['status']=='COMPLETE' and q['operation']=='execute' and q['op']=='cost':
            cost_items.append({'id':q['args']['id'],'amount_microUSD':q['args']['amount'],'hour':q['day'],'funding':'NATIVE_COST','breakdown':{}})
    paid = [a for a in ledger['actions'] if a['op']=='event' and a['args']['action']=='release']
    first=orders.get('turn-first','NO_ORDER');second=orders.get('turn-successor','NO_ORDER')
    return {'schema':'genesis-commitment001/report/v1','binding':reg['binding'],
        'scenario':reg['scenario'],'arm':reg['arm'],'scope':reg['protocol']['scope'],
        'opening_microUSD':OPENING,'borrowed_microUSD':0,'actual_revenue_microUSD':0,
        'native_summary':summary,'cost_items':cost_items,'first_state':first,'successor_state':second,
        'collected_orders':[a['args']['id'] for a in paid],
        'successor_development_funding':successor['receipt']['funding'] if successor else None,
        'complete_simulated_turn':first=='released' and second=='released' and successor is not None and successor['receipt']['funding']=='EARNED',
        'capacity_commitments':capacity_rows(record),'first_buyer_choice':choose_buyer(reg['protocol'],'first',reg['scenario']),
        'unknown_actual_costs':reg['protocol']['unknown_actual_costs'],
        'horizon_hours':[0,120],'trailing_365_day_profit':None,
        'accounting_basis':'Native incurred-cost/collected-release simulation; buyer custody is restricted and maturity is not income.',
        'commercial_verdict':'CONDITIONAL_AUTHORED_MODEL_ONLY','discovery_advantage':'NOT_ESTABLISHED',
        'real_demand':'NOT_ESTABLISHED','production_environment':'trusted local POSIX single-account simulation only'}


def run(output, *, scenario='central', arm='retained', resume=False, max_steps=None, fault=None):
    out=safe_output(output)
    if resume:
        reg,manifest=_bound(out)
        if (scenario,arm)!=(reg['scenario'],reg['arm']):
            raise ValueError('RESUME_SCENARIO_OR_ARM_CHANGED')
        if (out/'REPORT.json').exists():
            audit(out)
            # Audit live authority read-only; never execute pending intents after completion.
            return _completed(out,reg,manifest)
    else:
        reg,manifest=_register(out,scenario,arm)
    p=reg['protocol'];private=out/'private';private.mkdir(mode=0o700,exist_ok=True)
    account_path=private/'account.sqlite';state_path=private/'STATE.json'
    if resume and any(private.glob('account.sqlite*')):
        for suffix in ('.adaptive-simulation-key','.actions.jsonl','.connected-journal.json'):
            if not account_path.with_name(account_path.name+suffix).is_file():
                raise ValueError('EXISTING_ACCOUNT_AUTHORITY_REQUIRED')
    collect=80 if scenario=='payment_delay' else 10
    next_hour=collect+12
    steps=0
    with BusinessAccount(out/'source',manifest,account_path,contract='commitment001-'+reg['binding'][:20],suppliers=p['suppliers'],require_pristine=not state_path.exists()) as business:
        account=business.account
        state=account.verify_checkpoint(read(state_path)) if state_path.exists() else {'binding':reg['binding'],'phase':'setup','first_choice':None,'first_funding':None,'successor_funding':None,'successor_enabled':False,'contention_rejected':None,'pending_collection_observed':False}
        if state['binding']!=reg['binding']:raise ValueError('CHECKPOINT_BINDING_CHANGED')
        save(state_path,account.seal_checkpoint(state))
        while state['phase']!='complete' and (max_steps is None or steps<max_steps):
            phase=state['phase']
            if phase=='setup':
                for key,value in p['setup_costs_usd'].items():
                    _spend(account,'setup-'+key,key,amount(p,value,scenario),0,allow_seed=True)
                state['phase']='quote'
            elif phase=='quote':
                _spend(account,'first-acquisition','acquisition',amount(p,sum(p['acquisition_costs_usd'].values()),scenario),1,allow_seed=True)
                state['phase']='decision'
            elif phase=='decision':
                state['first_choice']=choose_buyer(p,'first',scenario)
                state['phase']='first_reserve' if state['first_choice']['buy'] else 'close'
            elif phase=='first_reserve':
                work=delivery_work(p,'first',scenario,4)
                funding=business.reserve_delivery('capacity-turn-first',sum(work['costs'].values()),3,work,allow_seed=True)
                if funding is None:raise ValueError('FIRST_REGISTERED_DELIVERY_NOT_FUNDED')
                state['first_funding']=funding
                contender=copy.deepcopy(work);contender.update(order='turn-contender',buyer='SIM-contender')
                rejected=business.reserve_delivery('capacity-turn-contender',sum(contender['costs'].values()),3,contender,allow_seed=True)
                if rejected is not None:raise ValueError('DOUBLE_SOLD_CAPACITY')
                state['contention_rejected']=True;state['phase']='first_order'
            elif phase=='first_order':
                b,_=economic_case(p,'first',scenario)
                business.begin('restore-first','turn-first','SIM-first',b['price_usd']*UNIT,b['budget_usd']*UNIT,3,collect,collect+8)
                state['phase']='first_produce'
            elif phase=='first_produce':
                artifact=produce(default_requests()[0],method=arm)
                if scenario=='bad_output':artifact['request_id']='wrong-delivery'
                save(out/'FIRST_ARTIFACT.json',artifact)
                state['phase']='first_accept'
            elif phase=='first_accept':
                artifact=read(out/'FIRST_ARTIFACT.json')
                if scenario=='shared_shock':
                    business.event('turn-first','refund',7)
                    state['phase']='close'
                else:
                    receipt=business.deliver('restore-first','turn-first',artifact,7)
                    save(out/'FIRST_ACCEPTANCE.json',receipt)
                    if not receipt['accepted']:
                        business.event('turn-first','refund',7);state['phase']='close'
                    else:state['phase']='first_collect'
            elif phase=='first_collect':
                if scenario=='payment_delay':
                    # At hour 10 the accepted deposit remains restricted, not earnings.
                    prior_release=next((a for a in account.export()['ledger']['actions'] if a['op']=='event' and a['args']['id']=='turn-first' and a['args']['action']=='release'),None)
                    before=prior_release['before'] if prior_release else account.snapshot()['summary']
                    if before['unrestrictedEarned']>0:
                        raise ValueError('UNPAID_WORK_MUST_NOT_FUND_SUCCESSOR')
                    state['pending_collection_observed']=True
                business.event('turn-first','release',collect)
                account.cost('first-payment-fee',amount(p,p['payment_fee_usd'],scenario),collect)
                _tax(account,p,'turn-tax-first',collect)
                state['phase']='first_mature'
            elif phase=='first_mature':
                account.advance_financial(collect+9)
                state['phase']='successor_decision'
            elif phase=='successor_decision':
                budget=amount(p,p['successor_development_usd']+p['successor_acquisition_usd']+sum(p['successor_costs_usd'].values())+p['payment_fee_usd'],scenario)
                snap=account.snapshot()['summary']
                # The complete successor budget must be affordable before commissioning.
                state['successor_enabled']=choose_buyer(p,'successor',scenario)['buy'] and min(snap['available'],snap['unrestrictedEarned'])>=budget
                state['phase']='successor_develop' if state['successor_enabled'] else 'close'
            elif phase=='successor_develop':
                _spend(account,'successor-development','development',amount(p,p['successor_development_usd'],scenario),next_hour,allow_seed=False,
                    work={'retained_means':'source-exact data conservation and independent database verification','distinct_outcome':'normalized schema migration','cost_basis':p['cost_basis']})
                _spend(account,'successor-acquisition','acquisition',amount(p,p['successor_acquisition_usd'],scenario),next_hour,allow_seed=False)
                state['phase']='successor_reserve'
            elif phase=='successor_reserve':
                work=delivery_work(p,'successor',scenario,next_hour+2)
                funding=business.reserve_delivery('capacity-turn-successor',sum(work['costs'].values()),next_hour+1,work,allow_seed=False)
                if funding is None:raise ValueError('SUCCESSOR_FULL_BUDGET_NO_LONGER_AVAILABLE')
                state['successor_funding']=funding;state['phase']='successor_order'
            elif phase=='successor_order':
                b,_=economic_case(p,'successor',scenario)
                business.begin('migration-next','turn-successor','SIM-successor',b['price_usd']*UNIT,b['budget_usd']*UNIT,next_hour+1,next_hour+8,next_hour+16)
                state['phase']='successor_produce'
            elif phase=='successor_produce':
                save(out/'SUCCESSOR_ARTIFACT.json',produce(default_requests()[1],method=arm));state['phase']='successor_accept'
            elif phase=='successor_accept':
                checked=business.deliver('migration-next','turn-successor',read(out/'SUCCESSOR_ARTIFACT.json'),next_hour+5)
                save(out/'SUCCESSOR_ACCEPTANCE.json',checked)
                if not checked['accepted']:raise ValueError('SUCCESSOR_ACCEPTANCE_FAILED')
                state['phase']='successor_collect'
            elif phase=='successor_collect':
                business.event('turn-successor','release',next_hour+8)
                account.cost('successor-payment-fee',amount(p,p['payment_fee_usd'],scenario),next_hour+8)
                account.advance_financial(next_hour+17)
                state['phase']='close'
            elif phase=='close':
                account.cost('closing-maintenance',amount(p,p['closing_maintenance_usd'],scenario),120)
                _tax(account,p,'turn-tax-final',120)
                state['phase']='complete'
            else:raise ValueError('REGISTERED_PHASE_REQUIRED')
            if fault is not None:fault(phase,account,state)
            save(state_path,account.seal_checkpoint(state));steps+=1
        exported=account.export()
        save(out/'NATIVE_EXPORT.json',exported)
        if state['phase']!='complete':
            return {'complete':False,'phase':state['phase'],'steps':steps,'binding':reg['binding']}
        report=_summary(out,reg,exported)
        save(out/'EXECUTION.json',state);save(out/'REPORT.json',report)
    audit(out)
    return report


def _completed(out,reg,manifest):
    # Opening only after verifying no pending journal intent is permitted.
    path=out/'private'/'account.sqlite'
    for suffix in ('.adaptive-simulation-key','.actions.jsonl','.connected-journal.json'):
        if not path.with_name(path.name+suffix).is_file():raise ValueError('EXISTING_ACCOUNT_AUTHORITY_REQUIRED')
    envelope=read(path.with_name(path.name+'.connected-journal.json'))
    if any(e['status']=='PENDING' for e in envelope['body']['entries']):raise ValueError('COMPLETED_ACCOUNT_HAS_PENDING_INTENT')
    with BusinessAccount(out/'source',manifest,path,contract='commitment001-'+reg['binding'][:20],suppliers=reg['protocol']['suppliers']) as business:
        if business.account.export()!=read(out/'NATIVE_EXPORT.json'):
            raise ValueError('COMPLETED_ACCOUNT_DIFFERS')
    return read(out/'REPORT.json')


def _audit_public_deliveries(out, reg, manifest, first_bought, successor):
    """Bind exported duplicates to the checked delivery and registered outcome.

    Shared-shock production was never delivered; its valid output is evidence of
    production only. The bad-output specimen is the registered rejected delivery,
    never a prepared native claim or an acceptance by a real participant.
    """
    scenario = reg['scenario']
    for stage, job, produced in (('FIRST', 'restore-first', first_bought),
                                 ('SUCCESSOR', 'migration-next', successor)):
        delivered = produced and not (stage == 'FIRST' and scenario == 'shared_shock')
        row = next(row for row in manifest['jobs'] if row['id'] == job)
        artifact_path = out/(stage+'_ARTIFACT.json')
        receipt_path = out/(stage+'_ACCEPTANCE.json')
        source_path = out/'source'/row['delivery_path']
        for path, expected in ((artifact_path, produced), (receipt_path, delivered),
                               (source_path, delivered)):
            if not expected and (path.exists() or path.is_symlink()):
                raise ValueError('UNPRODUCED_PUBLIC_DELIVERY_RECORD')
            if expected and (path.is_symlink() or not path.is_file()):
                raise ValueError('REGULAR_EXPECTED_DELIVERY_RECORD_REQUIRED')
        if not produced:
            continue
        artifact = read(artifact_path)
        if not isinstance(artifact, dict) or artifact.get('method') != reg['arm']:
            raise ValueError('REGISTERED_DELIVERY_METHOD_CHANGED')
        checked = service.verify_delivery(out/'source', manifest, job, artifact)
        rejected = stage == 'FIRST' and scenario == 'bad_output'
        if rejected:
            repaired = copy.deepcopy(artifact)
            if repaired.pop('request_id', None) != 'wrong-delivery':
                raise ValueError('REGISTERED_REJECTED_SPECIMEN_CHANGED')
            if not service.verify_delivery(out/'source', manifest, job, repaired)['accepted']:
                raise ValueError('REGISTERED_REJECTION_CAUSE_CHANGED')
        if checked['accepted'] is not (not rejected):
            raise ValueError('REGISTERED_DELIVERY_ACCEPTANCE_CHANGED')
        if delivered:
            if digest(artifact) != digest(service.delivery(out/'source', manifest, job)):
                raise ValueError('PUBLIC_DELIVERY_DIFFERS_FROM_NATIVE_SOURCE')
            if canonical(read(receipt_path)) != canonical(checked):
                raise ValueError('PUBLIC_ACCEPTANCE_DIFFERS_FROM_CHECKER')


def audit(output):
    out=safe_output(output);reg,manifest=_bound(out);p=reg['protocol'];scenario=reg['scenario']
    record=read(out/'NATIVE_EXPORT.json')
    if record['ledger']['config']['contract'] != 'commitment001-'+reg['binding'][:20]:
        raise ValueError('REGISTERED_NATIVE_CONTRACT_CHANGED')
    native=audit_journal(record,root=out/'source',manifest=manifest)
    if not native['accepted']:raise ValueError('NATIVE_REPLAY_REJECTED')
    if record['ledger']['config']['opening']!=OPENING:raise ValueError('EXACT_SEED_REQUIRED')
    entries=record['connected_journal']['entries'];keys=[e['key'] for e in entries]
    if len(keys)!=len(set(keys)) or any(e['status']!='COMPLETE' for e in entries):raise ValueError('COMPLETE_UNIQUE_ACTIONS_REQUIRED')
    bykey=dict(zip(keys,entries));ledger=record['ledger'];orders={r['id']:r for r in ledger['orders']}
    expected_spends={}
    for k,v in p['setup_costs_usd'].items():expected_spends['setup-'+k]=(amount(p,v,scenario),0,True)
    expected_spends['first-acquisition']=(amount(p,sum(p['acquisition_costs_usd'].values()),scenario),1,True)
    choice=choose_buyer(p,'first',scenario)
    first_bought=choice['buy']
    expected_orders={'turn-first'} if first_bought else set()
    collect=80 if scenario=='payment_delay' else 10;nh=collect+12
    first_success=first_bought and scenario not in {'bad_output','shared_shock'}
    if first_bought:
        work=delivery_work(p,'first',scenario,4);expected_spends['capacity-turn-first']=(sum(work['costs'].values()),3,True)
        if bykey.get('spend:capacity-turn-first',{}).get('request',{}).get('work')!=work:raise ValueError('FIRST_COMMITMENT_CHANGED')
    # The exact post-maturity prefix determines eligibility; a claimed flag cannot.
    successor=False
    if first_success:
        mat=[a for a in ledger['actions'] if a['op']=='mature' and a['args']['id']=='turn-first']
        if len(mat)!=1 or mat[0]['day']!=collect+9:raise ValueError('FIRST_MATURITY_REQUIRED')
        budget=amount(p,p['successor_development_usd']+p['successor_acquisition_usd']+sum(p['successor_costs_usd'].values())+p['payment_fee_usd'],scenario)
        snap=mat[0]['after'];successor=choose_buyer(p,'successor',scenario)['buy'] and min(snap['available'],snap['unrestrictedEarned'])>=budget
    if successor:
        expected_orders.add('turn-successor')
        expected_spends['successor-development']=(amount(p,p['successor_development_usd'],scenario),nh,False)
        expected_spends['successor-acquisition']=(amount(p,p['successor_acquisition_usd'],scenario),nh,False)
        work=delivery_work(p,'successor',scenario,nh+2)
        expected_spends['capacity-turn-successor']=(sum(work['costs'].values()),nh+1,False)
        if bykey.get('spend:capacity-turn-successor',{}).get('request',{}).get('work')!=work:raise ValueError('SUCCESSOR_COMMITMENT_CHANGED')
    spends=[e for e in entries if e['request']['operation']=='spend']
    if {e['request']['id'] for e in spends}!=set(expected_spends):raise ValueError('REGISTERED_SPEND_SET_CHANGED')
    for e in spends:
        q=e['request'];wanted=expected_spends[q['id']]
        if (q['amount'],q['day'],q['allow_seed'])!=wanted or q['expected_net']!=1:raise ValueError('REGISTERED_SPEND_CHANGED')
        if not wanted[2] and e['funding']!='EARNED':raise ValueError('SUCCESSOR_MUST_USE_EARNINGS')
        if q['id'].startswith('setup-'):
            kind=q['id'][6:];work={'cost_category':kind}
        elif q['id'] in {'first-acquisition','successor-acquisition'}:
            kind='acquisition';work={'cost_category':kind}
        elif q['id']=='successor-development':
            kind='development';work={'retained_means':'source-exact data conservation and independent database verification','distinct_outcome':'normalized schema migration','cost_basis':p['cost_basis']}
        else:
            kind='committed_delivery';work=delivery_work(p,'first' if q['id']=='capacity-turn-first' else 'successor',scenario,4 if q['id']=='capacity-turn-first' else nh+2)
        if q['kind']!=kind or q['work']!=work:raise ValueError('REGISTERED_EXPENSE_SCOPE_CHANGED')
    if set(orders)!=expected_orders:raise ValueError('REGISTERED_ORDER_SET_CHANGED')
    _audit_public_deliveries(out, reg, manifest, first_bought, successor)
    # Every promise follows its prepaid production/resource commitment.
    for order,row in orders.items():
        stage='first' if order=='turn-first' else 'successor';q=bykey['spend:capacity-'+order]['request']
        offer=bykey['native:offer:'+order]['request'];b,_=economic_case(p,stage,scenario)
        if keys.index('spend:capacity-'+order)>=keys.index('native:offer:'+order):raise ValueError('PROMISE_PRECEDES_RESOURCE_COMMITMENT')
        if offer['args']['price']!=b['price_usd']*UNIT or offer['args']['buyer']!='SIM-'+stage or offer['args']['job_id']!=q['work']['job']:raise ValueError('REGISTERED_PROMISE_CHANGED')
        want='released' if stage=='successor' or first_success else 'refunded'
        if row['state']!=want:raise ValueError('REGISTERED_OUTCOME_CHANGED')
    # Consume the entire permitted native command set and exact event chronology.
    from commercial.terms_exact_v2 import prospective_terms
    expected_native={}
    for order in expected_orders:
        first=order=='turn-first';stage='first' if first else 'successor'
        b,_=economic_case(p,stage,scenario);at=3 if first else nh+1
        coll=collect if first else nh+8;mat=coll+8
        job='restore-first' if first else 'migration-next';buyer='SIM-'+stage
        def command(key,op,args,day):
            expected_native[key]={'operation':'execute','op':op,'args':args,'day':day}
        command('native:wallet:'+buyer,'wallet',{'buyer':buyer,'amount':b['budget_usd']*UNIT},at)
        command('native:register_terms:'+order+'-terms','register_terms',{'id':order+'-terms','terms':prospective_terms(order,b['price_usd']*UNIT,mat,coll,residual=50_000_000)},at)
        command('native:offer:'+order,'offer',{'id':order,'buyer':buyer,'price':b['price_usd']*UNIT,'job_id':job,'deadline':coll+1,'terms_id':order+'-terms'},at)
        for action in ('consent','fund'):
            command('native:event:'+order+':'+order+'-'+action,'event',{'id':order,'action':action,'event_id':order+'-'+action},at)
        if first and not first_success:
            command('native:event:'+order+':'+order+'-refund','event',{'id':order,'action':'refund','event_id':order+'-refund'},7)
        else:
            artifact=service.delivery(out/'source',manifest,job)
            command('native:event:'+order+':'+order+'-prepare','event',{'id':order,'action':'prepare','event_id':order+'-prepare','artifact_sha256':digest(artifact)},7 if first else nh+5)
            command('native:event:'+order+':'+order+'-release','event',{'id':order,'action':'release','event_id':order+'-release'},coll)
            terms=prospective_terms(order,b['price_usd']*UNIT,mat,coll,residual=50_000_000)
            event_id='maturity:'+order+':'+digest(terms)[:20]
            command('native:mature:'+order+':'+event_id,'mature',{'id':order,'event_id':event_id},mat+1)
    actual_non_cost={e['key']:e['request'] for e in entries if e['request']['operation']=='execute' and e['request']['op']!='cost'}
    if actual_non_cost!=expected_native:
        raise ValueError('REGISTERED_NATIVE_CHRONOLOGY_OR_TERMS_CHANGED')
    # Reject double use in a sweep over every interval boundary, including adjacency.
    caps=capacity_rows(record)
    for row in caps:validate_capacity({k:v for k,v in row.items() if k!='id'},p['suppliers'])
    for supplier,terms in p['suppliers'].items():
        rows=[r for r in caps if r['supplier']==supplier]
        for point in {t for r in rows for t in (r['start'],r['end'])}:
            if sum(r['units'] for r in rows if r['start']<=point<r['end'])>terms['units']:raise ValueError('CAPACITY_OVERCOMMITTED')
    expected_costs={'closing-maintenance':(amount(p,p['closing_maintenance_usd'],scenario),120),'turn-tax-final':(None,120)}
    if first_success:expected_costs.update({'first-payment-fee':(amount(p,p['payment_fee_usd'],scenario),collect),'turn-tax-first':(None,collect)})
    if successor:expected_costs['successor-payment-fee']=(amount(p,p['payment_fee_usd'],scenario),nh+8)
    costs=[a for a in ledger['actions'] if a['op']=='cost' and not a['args']['id'].startswith('connected014-seed-')]
    if {a['args']['id'] for a in costs}!=set(expected_costs):raise ValueError('REGISTERED_COMPLETE_COST_SET_CHANGED')
    paid_tax=0
    for a in costs:
        ident=a['args']['id'];wanted,hour=expected_costs[ident]
        if a['day']!=hour:raise ValueError('COST_CHRONOLOGY_CHANGED')
        if ident.startswith('turn-tax-'):
            wanted=max(0,max(0,a['before']['profit']+paid_tax)*p['tax_numerator']//p['tax_denominator']-paid_tax)
            paid_tax+=a['args']['amount']
        if a['args']['amount']!=wanted:raise ValueError('REGISTERED_COMPLETE_COST_CHANGED')
    expected_state={'binding':reg['binding'],'phase':'complete',
        'first_choice':choice,'first_funding':bykey['spend:capacity-turn-first']['receipt'] if first_bought else None,
        'successor_funding':bykey['spend:capacity-turn-successor']['receipt'] if successor else None,
        'successor_enabled':successor,'contention_rejected':True if first_bought else None,
        'pending_collection_observed':scenario=='payment_delay' and first_success}
    if read(out/'EXECUTION.json')!=expected_state:raise ValueError('EXECUTION_TRANSITION_CLAIM_CHANGED')
    report=read(out/'REPORT.json')
    if report!=_summary(out,reg,record):raise ValueError('REPORT_CLAIM_CHANGED')
    if sum(c['amount_microUSD'] for c in report['cost_items'])!=ledger['summary']['expenses']:raise ValueError('COST_RECONCILIATION_FAILED')
    receipt={'accepted':True,'binding':reg['binding'],'native_replay':True,'capacity_replay':True,'complete_cost_replay':True,'public_delivery_replay':True,'complete_simulated_turn':report['complete_simulated_turn'],'scope':'AUTHORED_SIMULATION_ONLY'}
    save(out/'AUDIT.json',receipt)
    return receipt


def package(output,archive):
    out=safe_output(output);audit(out);archive=safe_output(archive)
    if archive.exists():raise ValueError('NEW_ARCHIVE_REQUIRED')
    reg,manifest=_bound(out);report=read(out/'REPORT.json')
    allowed=['REGISTRATION.json','MANIFEST.json','NATIVE_EXPORT.json','REPORT.json','EXECUTION.json','AUDIT.json']
    if report['first_state']!='NO_ORDER':
        allowed.append('FIRST_ARTIFACT.json')
        if reg['scenario']!='shared_shock':allowed.append('FIRST_ACCEPTANCE.json')
    if report['successor_state']!='NO_ORDER':
        allowed.extend(['SUCCESSOR_ARTIFACT.json','SUCCESSOR_ACCEPTANCE.json'])
    root_names={p.name for p in out.iterdir()}
    if root_names-set(allowed)-{'source','private'}:
        raise ValueError('UNREGISTERED_PUBLIC_ROOT_FILE')
    for name in allowed:
        path=out/name
        if path.is_symlink() or not path.is_file():raise ValueError('REGULAR_EXPECTED_PUBLIC_FILE_REQUIRED')
    source_files=set(reg['source'])
    source_files.update(row['delivery_path'] for row in manifest['jobs'] if (out/'source'/row['delivery_path']).is_file())
    paths=list((out/'source').rglob('*'))
    if any(p.is_symlink() for p in paths):raise ValueError('PUBLIC_SOURCE_SYMLINK_REFUSED')
    observed={p.relative_to(out/'source').as_posix() for p in paths if p.is_file() and '__pycache__' not in p.parts}
    if observed!=source_files:raise ValueError('UNREGISTERED_PUBLIC_SOURCE_FILE')
    # All paths are checked before creating an archive; no glob-suffix exports.
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for name in allowed:z.write(out/name,name)
        for name in sorted(source_files):z.write(out/'source'/name,'source/'+name)
    return {'archive':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'private_authority_included':False}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=['run','resume','audit','package']);ap.add_argument('--output',required=True);ap.add_argument('--scenario',default='central');ap.add_argument('--arm',default='retained');ap.add_argument('--max-steps',type=int);ap.add_argument('--archive')
    args=ap.parse_args()
    if args.command in {'run','resume'}:result=run(args.output,scenario=args.scenario,arm=args.arm,resume=args.command=='resume',max_steps=args.max_steps)
    elif args.command=='audit':result=audit(args.output)
    else:result=package(args.output,args.archive)
    print(json.dumps(result,sort_keys=True,indent=2))


if __name__=='__main__':main()
