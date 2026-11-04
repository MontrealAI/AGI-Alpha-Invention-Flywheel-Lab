"""Opt-in continuation through the existing JournalAccount; no second ledger."""
from __future__ import annotations
import copy
from fractions import Fraction
import hashlib
from pathlib import Path
import shutil

from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from connected_enterprise.finance import JournalAccount, SOURCE_PATHS, audit_journal
from adaptive_enterprise import instruments as substrate
from adaptive_enterprise.checkers import audit_delivery

MICRO=1_000_000
OPENING=100_000*MICRO
CONTRACT='omega-inventor-201-fresh-diagnostic-v1'
INDEXES=tuple(range(8,24))
TARIFF={'setup':100*MICRO,'discovery':200*MICRO,'quote':MICRO,
        'delivery_base':2*MICRO,'metered_operation':10_000,'verification':3*MICRO,
        'support':2*MICRO,'annual_maintenance':120*MICRO,'successor':50*MICRO,
        'payment_bps':300,'tax_bps':2000}


def save(path,value):atomic_bytes(Path(path),canonical(value)+b'\n')
def read(path):return strict_json(Path(path).read_bytes())


def audit_registered_journal(exported, *, root, manifest, opening, contract):
    """Bind an internally replayable ledger to this operator's registered terms."""
    config = exported['ledger']['config']
    expected = {'opening': opening, 'working': 0, 'contract': contract}
    # Canonical JSON keeps booleans and floats distinct from integer money.
    if canonical({key: config.get(key) for key in expected}) != canonical(expected):
        raise ValueError('REGISTERED_NATIVE_ACCOUNT_CONFIG_CHANGED')
    return audit_journal(exported, root=root, manifest=manifest)


def audit_earned_successor(exported, manifest, record, path, *, ident, day, amount, work,
                           maintenance, tax, before_maintenance):
    """Reconstruct the scheduled earned-only choice and the complete closing sequence."""
    journal = exported['connected_journal']['entries']
    actions = exported['ledger']['actions']
    closing = [entry for entry in journal if entry['request']['day'] >= day]
    closing_actions = [action for action in actions if action['day'] >= day]
    tax_actions = [action for action in closing_actions if action['op'] == 'cost' and action['args']['id'] == tax]
    if len(tax_actions) != 1:
        raise ValueError('REGISTERED_CLOSING_TAX_REQUIRED')
    state = closing_actions[0]['before'] if before_maintenance else tax_actions[0]['after']
    stopped = manifest.get('native_engine') in ('prospective-v1', 'exact-prospective-v2') and state['investmentStopped']
    eligible = not stopped and min(state['available'], state['unrestrictedEarned']) >= amount
    if eligible != (record is not None) or eligible != path.is_file():
        raise ValueError('REGISTERED_EARNED_SUCCESSOR_DECISION_CHANGED')
    costs = [('execute', 'cost', maintenance), ('execute', 'cost', tax)]
    funding = [('spend', None, ident)] if eligible else []
    actual = [(req['operation'], req.get('op'), req.get('id', req.get('args', {}).get('id')))
              for req in (entry['request'] for entry in closing)]
    if actual != (funding + costs if before_maintenance else costs + funding):
        raise ValueError('REGISTERED_YEAR_END_SEQUENCE_CHANGED')
    if eligible:
        payment = closing[0] if before_maintenance else closing[-1]
        expected = {'operation': 'spend', 'id': ident, 'kind': 'instrument', 'amount': amount,
                    'day': day, 'work': work, 'expected_net': 1, 'allow_seed': False}
        if (canonical(payment['request']) != canonical(expected) or payment['status'] != 'COMPLETE'
                or payment['funding'] != 'EARNED' or canonical(record['funding']) != canonical(payment['receipt'])):
            raise ValueError('REGISTERED_SUCCESSOR_FUNDING_CHANGED')


def trade_operations(buyer, budget, offers, day, *, settled):
    """Build the registered non-cost native operations from a checked buyer decision."""
    operations = [('wallet', {'buyer': buyer, 'amount': budget}, day)]
    for offer in offers:
        operations.append(('offer', offer, day))
        for event in ('consent', 'fund'):
            operations.append(('event', {'id': offer['id'], 'action': event, 'event_id': offer['id'] + '-' + event}, day))
    for offer in offers:
        for event in (('prepare', 'release') if settled else ('refund',)):
            operations.append(('event', {'id': offer['id'], 'action': event, 'event_id': offer['id'] + '-' + event}, day + 1))
    return operations


def audit_trade_operations(exported, expected):
    entries = [entry for entry in exported['connected_journal']['entries']
               if entry['request']['operation'] == 'execute' and entry['request']['op'] != 'cost']
    actual = [(req['op'], req['args'], req['day']) for req in (entry['request'] for entry in entries)]
    if canonical(actual) != canonical(expected) or any(entry['status'] != 'COMPLETE' for entry in entries):
        raise ValueError('REGISTERED_NATIVE_TRADE_OPERATIONS_CHANGED')


def require_resume_authority(output):
    """A prepared fixture may precede account creation. Operating receipts cannot."""
    output = Path(output)
    receipts = ('FROZEN_POLICY.json', 'CONFIRMATION.json', 'STUDY.json', 'V2_STUDY.json',
                'SUCCESSOR.json', 'TAX.json', 'NATIVE_RESULT.json', 'NATIVE_EXPORT.json',
                'REPORT.json', 'REPORT.html', 'V2_REPORT.json')
    started = (any((output / name).exists() for name in receipts) or any(output.glob('order-*.json'))
               or any(p.name != 'account.sqlite.writer.lock' for p in output.glob('account.sqlite*')))
    if not started:
        return
    required = ('account.sqlite.actions.jsonl', 'account.sqlite.adaptive-simulation-key',
                'account.sqlite.connected-journal.json', 'MANIFEST.json', 'runtime/services/MANIFEST.json')
    for name in required:
        path = output / name
        if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('EXISTING_NATIVE_AUTHORITY_REQUIRED_FOR_RESUME:' + name)


class _CompletedJournalAccount(JournalAccount):
    def _recover(self):
        # A separate native writer may have committed a signed intent after the
        # report closed. Under the canonical lease, decline to execute that intent.
        if any(entry['status'] == 'PENDING' for entry in self._journal['entries']):
            raise ValueError('COMPLETED_NATIVE_ACCOUNT_DIFFERS_FROM_RECORDED_EXPORT:PENDING_INTENT')
        super()._recover()


def completed_resume(output, *, opening, contract, report_name, public_audit):
    """Compare the complete signed local history and validate the published economics."""
    account = _CompletedJournalAccount(output / 'runtime', read(output / 'MANIFEST.json'),
                                       output / 'account.sqlite', opening=opening, working=0, contract=contract)
    try:
        live_digest = digest(account.export())
        if digest(read(output / 'NATIVE_EXPORT.json')) != live_digest:
            raise ValueError('COMPLETED_NATIVE_ACCOUNT_DIFFERS_FROM_RECORDED_EXPORT')
        checked = public_audit(output)
        report = read(output / report_name)
        if checked['accepted'] is not True or checked['report_sha256'] != digest(report):
            raise ValueError('AUDITED_COMPLETED_REPORT_CHANGED')
        if digest(read(output / 'NATIVE_EXPORT.json')) != live_digest:
            raise ValueError('COMPLETED_NATIVE_ACCOUNT_DIFFERS_FROM_RECORDED_EXPORT')
        return report
    finally:
        account.close()


def begin(output,source):
    """Fixture admission precedes the account; its full modeled setup is charged."""
    root=Path(output)/'runtime'
    manifest_path=Path(output)/'MANIFEST.json'
    from .inventor import ROOT
    if not manifest_path.exists():
        for name in set(SOURCE_PATHS)|set(substrate.SOURCE_PATHS):
            target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/name,target)
        manifest=substrate.prepare_services(root,'services',cohort_seed=81001)
        save(manifest_path,manifest)
    manifest=read(manifest_path)
    account=JournalAccount(root,manifest,Path(output)/'account.sqlite',opening=OPENING,
                           working=0,contract=CONTRACT)
    for ident,kind in (('setup','setup'),('discovery','discovery')):
        paid=account.spend('omega-'+ident,kind,TARIFF[kind],0,
                           {'source':source,'tariff':TARIFF,'scope':'AUTHORED_RESOURCE_ENVELOPE_NOT_ACTUAL_BILL'},
                           1,allow_seed=True)
        if paid is None:account.close();raise ValueError('UNFUNDED_INITIAL_CONSTRUCTION')
    return root,manifest,account


def choose(cost,available,*,copycat=False,value=250*MICRO,budget=250*MICRO):
    """Finite public complete-information game with prepaid modeled delivery cost.

    Rival cost/price grid and buyer utility are authored market assumptions.
    This exhaustive independent implementation includes refusal and nonentry.
    """
    if any(type(x) is not int or x<0 for x in (cost,available,value,budget)) or type(copycat) is not bool:
        raise ValueError('EXACT_NONNEGATIVE_PUBLIC_GAME_INPUTS_REQUIRED')
    grid=[99*MICRO,149*MICRO,199*MICRO]
    outside=50*MICRO
    rival_cost=cost if copycat else 100*MICRO
    rows=[]
    for quote in grid:
        responses=[]
        for rival_quote in (None,*grid):
            ours=value-quote if quote<=budget else -10**30
            rival=value-rival_quote if rival_quote is not None and rival_quote<=budget else -10**30
            buyer=('seller' if ours>max(outside,rival) else 'rival' if rival>outside and rival>=ours else 'outside')
            profit=(rival_quote-rival_cost if buyer=='rival' else 0) if rival_quote is not None else 0
            responses.append({'rival_quote':rival_quote,'rival_profit':profit,'buyer':buyer})
        best=max(r['rival_profit'] for r in responses)
        tied=[r for r in responses if r['rival_profit']==best]
        response=min(tied,key=lambda r:(r['buyer']=='seller',r['rival_quote'] is not None,r['rival_quote'] or 0))
        fee=(quote*TARIFF['payment_bps']+9999)//10000
        net=quote-cost-fee if response['buyer']=='seller' else 0
        rows.append({'quote':quote,'response':response,'net':net,'fee':fee,
                     'affordable':cost+fee+quote+MICRO<=available})
    eligible=[r for r in rows if r['affordable'] and r['net']>0]
    winner=max(eligible,key=lambda r:(r['net'],-r['quote'])) if eligible else None
    return {'selected':winner,'alternatives':rows,'copycat':copycat,'value':value,'budget':budget,
            'delivery_cost':cost,'available_at_decision':available,'scope':'EXACT_DECLARED_SINGLE_BUYER_GAME_NO_WORLD_OPTIMALITY'}


def operate(output,p,source,acquisition_work,session=None):
    from .inventor import execute
    output=Path(output)
    root,manifest,account=begin(output,source) if session is None else session
    records=[]
    try:
        jobs=[j for j in manifest['jobs'] if j['service_id']=='reconciliation']
        for ordinal,index in enumerate(INDEXES):
            day=1+ordinal*20
            path=output/f'order-{index:03d}.json'
            job=jobs[index];raw=read(root/job['input'])
            # Price for a bounded production contract; full envelope paid even if checks fail.
            # This predeclared workload cap is not an assertion that all real work is cheap.
            cost=(TARIFF['delivery_base']+TARIFF['verification']+TARIFF['support']
                  +1000*TARIFF['metered_operation'])
            if path.exists():
                record=read(path)
                if record['source']!=source or record['policy']!=p or record['raw_sha256']!=digest(raw):
                    raise ValueError('RESUME_PLAN_SOURCE_CHANGED')
            else:
                # Quote/qualification expense remains paid for refusal and missing information.
                account.spend(f'quote-{index}','acquisition',TARIFF['quote'],day,
                              {'source':source,'job':job['id']},1,allow_seed=True)
                # Missing source units are an observable refusal, not free access to a hidden answer.
                known=all(raw['units'].get(t) for t in ('invoices','payments'))
                decision=choose(cost,account.snapshot()['summary']['available']) if known else None
                record={'index':index,'day':day,'job_id':job['id'],'policy':p,'source':source,
                        'raw_sha256':digest(raw),'decision':decision,'production_envelope':cost,
                        'status':'PLANNED','complete':False}
                save(path,record)  # durable before effects; retried effects use stable identities
            selected=record['decision']['selected'] if record['decision'] else None
            if selected is None:
                record.update(status='DECLINED',reason='MISSING_INFORMATION_OR_NO_PROFITABLE_FINANCEABLE_TRADE')
            else:
                order=f'omega-trade-{index}';price=selected['quote'];buyer=f'SIM-omega-{index}'
                account.execute('wallet',{'buyer':buyer,'amount':record['decision']['budget']},day)
                account.execute('offer',{'id':order,'buyer':buyer,'price':price,
                                        'job_id':job['id'],'deadline':day+10},day)
                for action in ('consent','fund'):
                    account.execute('event',{'id':order,'action':action,'event_id':order+'-'+action},day)
                paid=account.spend('produce-'+str(index),'production_contract',cost,day,
                                   {'source':source,'policy':p,'job':job['id'],'raw_sha256':digest(raw)},
                                   max(1,selected['net']),allow_seed=True)
                if paid is None:raise ValueError('CURRENT_NATIVE_FUNDS_INSUFFICIENT_AFTER_FUNDED_ORDER')
                actual=execute(raw,p)
                checked=audit_delivery('reconciliation',raw,actual)
                reference=read(root/job['artifact'])
                equal=substrate.digest(substrate._semantics(actual))==substrate.digest(substrate._semantics(reference))
                if (not checked['accepted'] or not equal or actual['outcome_scope']!='complete_outcome'
                        or actual['plan']['search']['operation_count']>1000):
                    # An invalid construction does not authorize native prepare/release.
                    record.update(status='FAILED_ACCEPTANCE',complete=False,artifact=actual,check=checked)
                    save(path,record)
                    raise ValueError('NO_SETTLEMENT_WITHOUT_INDEPENDENT_COMPLETE_ACCEPTANCE')
                account.cost('fee-'+str(index),selected['fee'],day)
                for action in ('prepare','release'):
                    account.execute('event',{'id':order,'action':action,'event_id':order+'-'+action},day+1)
                record.update(status='SETTLED',complete=True,artifact=actual,check=checked,
                              funding=paid,price=price,fee=selected['fee'],
                              binding='Native releases admitted bytes; current constructed output has identical checked normalized input and useful outcome. Search-trace byte equality is not asserted.')
            save(path,record);records.append(record)
        # A genuinely earned-funded successor construction budget, not revenue booked twice.
        successor=account.spend('omega-successor','instrument',TARIFF['successor'],325,
                                {'source':source,'parent_policy':digest(p),'purpose':'Fresh schema construction and independent validation'},1,allow_seed=False)
        successor_record=None
        if successor is not None:
            raw=substrate.synthetic_raw('reconciliation',26,99001)
            actual=execute(raw,p);check=audit_delivery('reconciliation',raw,actual)
            successor_record={'funding':successor,'raw':raw,'artifact':actual,'check':check,
                              'unique_causal_enablement':False,'scope':'Funded-by and executed; no claim remaining seed or an ordinary route could not do this.'}
            save(output/'SUCCESSOR.json',successor_record)
        account.cost('annual-maintenance',TARIFF['annual_maintenance'],364)
        # A frozen tax estimate is persisted before the action, so resume cannot tax twice.
        taxpath=output/'TAX.json'
        if not taxpath.exists():
            s=account.snapshot()['summary']
            save(taxpath,{'amount':max(0,s['profit'])*TARIFF['tax_bps']//10000})
        account.cost('modeled-tax',read(taxpath)['amount'],364)
        exported=account.export();save(output/'NATIVE_EXPORT.json',exported)
        checked=account.audit();summary=account.snapshot()['summary']
        result={'opening_microUSD':OPENING,'contract':CONTRACT,'native_summary':summary,
                'native_audit':checked,'record_sha256':[digest(r) for r in records],
                'settled':sum(r['complete'] for r in records),'refused':sum(not r['complete'] for r in records),
                'successor':successor_record,'tariff':TARIFF,'acquisition_work':acquisition_work,
                'clock':{'start_day':0,'end_day':364,'days':365,'schedule':'Sparse authored schedule; no annualization or demand forecast'},
                'profit_scope':'After every declared modeled cost, including development, failures, acquisition, delivery, checking, payment, support, maintenance, successor and tax. Actual host/model bills UNKNOWN.',
                'authority':'Fresh local simulation only; not the original existing Omega account, no live funds.'}
        save(output/'NATIVE_RESULT.json',result)
        return result
    finally:account.close()


def audit_operation(output,result,source,expected_policy=None):
    """Reconstruct commerce from native authority plus separately checked work.

    The finance auditor is authoritative for money. A report, hash, or producer
    success flag cannot manufacture acceptance, participation, funding or profit.
    """
    from .inventor import execute
    output=Path(output);root=output/'runtime';manifest=read(output/'MANIFEST.json')
    exported=read(output/'NATIVE_EXPORT.json')
    checked=audit_registered_journal(exported, root=root, manifest=manifest, opening=OPENING, contract=CONTRACT)
    if canonical(checked)!=canonical(result['native_audit']) or canonical(result['native_summary'])!=canonical(exported['ledger']['summary']):
        raise ValueError('NATIVE_AUDIT_OR_SUMMARY_CHANGED')
    if result['opening_microUSD']!=OPENING or result['contract']!=CONTRACT or result['tariff']!=TARIFF:
        raise ValueError('REGISTERED_FINANCIAL_CONTRACT_CHANGED')
    journal=exported['connected_journal']['entries'];acts=exported['ledger']['actions']
    def expense(ident,amount,day,work):
        matches=[e for e in journal if e['request'].get('operation')=='spend' and e['request'].get('id')==ident]
        if len(matches)!=1:raise ValueError('EXACT_NATIVE_EXPENSE_REQUIRED')
        e=matches[0];r=e['request']
        if e['status']!='COMPLETE' or r['amount']!=amount or r['day']!=day or r['work']!=work:
            raise ValueError('NATIVE_EXPENSE_BINDING_CHANGED')
        return e['receipt']
    for kind in ('setup','discovery'):
        expense('omega-'+kind,TARIFF[kind],0,{'source':source,'tariff':TARIFF,'scope':'AUTHORED_RESOURCE_ENVELOPE_NOT_ACTUAL_BILL'})
    records=[];settled_ids=set();expected_trades=[];jobs=[j for j in manifest['jobs'] if j['service_id']=='reconciliation']
    for ordinal,index in enumerate(INDEXES):
        r=read(output/f'order-{index:03d}.json');records.append(r);day=1+ordinal*20;job=jobs[index]
        if (r['source']!=source or r['day']!=day or r['index']!=index or r['job_id']!=job['id']
                or expected_policy is not None and r['policy']!=expected_policy):
            raise ValueError('UNBOUND_SOURCE_POLICY_OR_SCHEDULE')
        raw=read(root/job['input'])
        if digest(raw)!=r['raw_sha256']:raise ValueError('INPUT_CHANGED')
        quote_receipt=expense(f'quote-{index}',TARIFF['quote'],day,{'source':source,'job':job['id']})
        available=acts[quote_receipt['native_event_sequence']]['after']['available']
        cost=TARIFF['delivery_base']+TARIFF['verification']+TARIFF['support']+1000*TARIFF['metered_operation']
        known=all(raw['units'].get(t) for t in ('invoices','payments'))
        decision=choose(cost,available) if known else None
        if r['decision']!=decision or r['production_envelope']!=cost:
            raise ValueError('STRATEGIC_DECISION_CHANGED')
        selected=decision['selected'] if decision else None
        order=f'omega-trade-{index}'
        offers=[a for a in acts if a['op']=='offer' and a['args']['id']==order]
        releases=[a for a in acts if a['op']=='event' and a['args']['id']==order and a['args']['action']=='release']
        if selected is None:
            if r['status']!='DECLINED' or r['complete'] is not False or offers or releases:
                raise ValueError('UNSUPPORTED_TRADE_OR_REFUSAL')
            continue
        if r['status']!='SETTLED' or r['complete'] is not True:
            raise ValueError('REGISTERED_CAMPAIGN_INCOMPLETE')
        actual=execute(raw,r['policy']);check=audit_delivery('reconciliation',raw,actual)
        reference=read(root/job['artifact'])
        if (actual!=r['artifact'] or check!=r['check'] or not check['accepted']
                or actual['outcome_scope']!='complete_outcome'
                or substrate._semantics(actual)!=substrate._semantics(reference)
                or actual['plan']['search']['operation_count']>1000):
            raise ValueError('ACTUAL_CONSTRUCTION_CHANGED')
        funding=expense(f'produce-{index}',cost,day,{'source':source,'policy':r['policy'],'job':job['id'],'raw_sha256':digest(raw)})
        if r['funding']!=funding or r['fee']!=selected['fee'] or r['price']!=selected['quote']:
            raise ValueError('PRODUCTION_FUNDING_OR_PRICE_CHANGED')
        if (len(offers)!=1 or len(releases)!=1 or offers[0]['args']['price']!=r['price']
                or offers[0]['args']['job_id']!=job['id'] or offers[0]['day']!=day or releases[0]['day']!=day+1):
            raise ValueError('NATIVE_TRADE_NOT_EXACTLY_ONCE')
        buyer=f'SIM-omega-{index}'
        offer={'id':order,'buyer':buyer,'price':r['price'],'job_id':job['id'],'deadline':day+10}
        expected_trades.extend(trade_operations(buyer,decision['budget'],[offer],day,settled=True))
        settled_ids.add(order)
    audit_trade_operations(exported,expected_trades)
    if {a['args']['id'] for a in acts if a['op']=='offer'}!=settled_ids:
        raise ValueError('UNREPORTED_NATIVE_TRADE')
    if result['settled']!=len(settled_ids) or result['refused']!=len(INDEXES)-len(settled_ids):
        raise ValueError('OPERATING_DENOMINATORS_CHANGED')
    from .inventor_cost_audit import audit_costs
    audit_costs(exported,result,records,TARIFF,read(output/'TAX.json'))
    successor=result['successor']
    p=records[0]['policy']
    work={'source':source,'parent_policy':digest(p),'purpose':'Fresh schema construction and independent validation'}
    audit_earned_successor(exported, manifest, successor, output/'SUCCESSOR.json', ident='omega-successor',
                           day=325, amount=TARIFF['successor'], work=work, maintenance='annual-maintenance',
                           tax='modeled-tax', before_maintenance=True)
    if successor is not None:
        if successor!=read(output/'SUCCESSOR.json'):raise ValueError('SUCCESSOR_CHANGED')
        raw=substrate.synthetic_raw('reconciliation',26,99001)
        artifact=execute(raw,p);check=audit_delivery('reconciliation',raw,artifact)
        receipt=expense('omega-successor',TARIFF['successor'],325,
                        {'source':source,'parent_policy':digest(p),'purpose':'Fresh schema construction and independent validation'})
        if (receipt!=successor['funding'] or receipt['funding']!='EARNED'
                or successor['raw']!=raw or successor['artifact']!=artifact or successor['check']!=check
                or not check['accepted'] or successor['unique_causal_enablement'] is not False):
            raise ValueError('UNSUPPORTED_SUCCESSOR_OR_EARNED_FUNDING')
    if result['clock']!={'start_day':0,'end_day':364,'days':365,'schedule':'Sparse authored schedule; no annualization or demand forecast'}:
        raise ValueError('COMPLETE_YEAR_CLOCK_CHANGED')
    if [digest(r) for r in records]!=result['record_sha256'] or result!=read(output/'NATIVE_RESULT.json'):
        raise ValueError('OPERATING_REPORT_CHANGED')
    return {'accepted':True}
