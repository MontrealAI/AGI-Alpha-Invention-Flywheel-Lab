"""Read-only independent operating replay alongside canonical financial audit."""
from pathlib import Path
from bisect import bisect_left, bisect_right
from fractions import Fraction
from commercial.ledger import digest,strict_json
from connected_enterprise.finance import audit_journal
from connected_enterprise.scale import trailing_profit
from .registration import design
from .policy import initial_state,propose
from . import service


def audit(root,manifest,result,export):
    native=audit_journal(export,root=root,manifest=manifest)
    reg=design();cfg=manifest['configuration'];world=reg['worlds'][cfg['world']]
    if cfg!=result['configuration']:raise ValueError('CONFIG_CHANGED')
    state=initial_state();previous=None;total_units=0;actual_packets=0;last_index=-1
    actions=export['ledger']['actions'];journal=export['connected_journal']['entries']
    for m,row in enumerate(result['rows']):
        d=row['decision'];p=d['proposal'];summary=d['summary'];hour=m*reg['month_days']*24
        if d['state']!=state or p['month']!=m or d['previous_decision_sha256']!=previous or d['native_before_sha256']!=digest(summary):raise ValueError('OPERATING_STATE_CHAIN_CHANGED')
        index=d['native_sequence_before']
        if type(index) is not int or index<last_index or index>len(actions) or (actions[index-1]['after'] if index else actions[0]['before'])!=summary or (index and actions[index-1]['day']>hour) or digest(actions[:index])!=d['native_actions_before_sha256']:raise ValueError('OPERATING_OBSERVATION_NOT_NATIVE_CURRENT_STATE')
        last_index=index
        expected=propose(state,summary,world,reg,cfg['seed'],cfg['unit_cost'],cfg['opening'],grow=cfg['grow'],funding_mode=cfg['funding_mode'],policy_name=cfg['policy_name'])
        if p!=expected:raise ValueError('CHOICE_CAPACITY_COUNTS_NOT_REPLAYED')
        core=d
        paid=0
        for kind,cost in p['costs_microUSD'].items():
            if not cost:continue
            entries=[e for e in journal if e['request'].get('id')==f'm{m}-{kind}' and e['request'].get('operation')=='spend']
            receipt=row['funding'].get(kind)
            if receipt is None:
                if row['funded']:raise ValueError('MISSING_PAID_RESOURCE')
                continue
            if len(entries)!=1:raise ValueError('UNIQUE_RESOURCE_FUNDING_REQUIRED')
            e=entries[0];request=e['request']
            if e['status']!='COMPLETE' or request['amount']!=cost or request['day']!=hour or request['kind']!='reconciliation_bulk_resource' or request['work']['decision_sha256']!=digest(core) or e['receipt']!=receipt:raise ValueError('RESOURCE_COST_OR_DECISION_BINDING_CHANGED')
            if cfg['funding_mode']=='earned_only' and m>0 and kind in {'capacity','acquisition'} and e['funding']!='EARNED':raise ValueError('GROWTH_SUBSTITUTED_SEED')
            paid+=cost
        if row['native_after']['expenses']-summary['expenses']!=paid:raise ValueError('MONTH_COMPLETE_COST_MISMATCH')
        if row['funded']:
            state=p['state_after'];total_units+=p['collected_units']
            if p['collected_units']:
                job=manifest['jobs'][m];a=service.delivery(root,manifest,job['id'])
                if not service.check_delivery(root,manifest,job['id'],a)['accepted'] or a['market_receipt']!=p:raise ValueError('ACCEPTED_MODEL_CONTRACT_CHANGED')
                offers=[x for x in actions if x['op']=='offer' and x['args']['job_id']==job['id']]
                if len([o for o in offers if not o['args']['id'].endswith('-uncollected')])!=1 or any(o['args']['decision_sha256']!=digest(d) for o in offers):raise ValueError('OFFER_DECISION_NOT_BOUND')
                if not row['actual_production'] or row['actual_production']['output_sha256']!=digest(a['actual_output']):raise ValueError('ACTUAL_TEMPLATE_EVIDENCE_CHANGED')
                actual_packets+=1
        elif m!=len(result['rows'])-1:raise ValueError('CONTINUED_AFTER_TERMINAL_STOP')
        previous=digest(d)
    if actual_packets!=result['actual_packets'] or total_units!=result['modeled_collected_units']:raise ValueError('COUNT_REPORT_CHANGED')
    annual=trailing_profit(export['ledger'],operating_end_hour=result['operating_end_hour'],operating_complete=True)
    if annual!=result['annual']:raise ValueError('ANNUAL_WINDOW_CHANGED')
    costs=check_financial_schedule(reg,world,manifest,result,export)
    expected_attainment=daily_attainment(export['ledger'],result['operating_end_hour'],reg['primary_target_trailing365_profit_usd']*1_000_000)
    if result.get('attainment')!=expected_attainment:raise ValueError('DAILY_ATTAINMENT_CHANGED')
    expected_economic={str(rate):annual['trailing_365_day_profit_microUSD']-(cfg['opening']*Fraction(str(rate))).numerator//(cfg['opening']*Fraction(str(rate))).denominator for rate in reg['capital_opportunity_rates']}
    if result.get('rolling365_economic_profit_microUSD')!=expected_economic:raise ValueError('ECONOMIC_PROFIT_OPPORTUNITY_COST_CHANGED')
    return {'accepted':native['accepted'],'scope':'AUDITED_SIM_BULK_MODEL_AND_ACTUAL_TEMPLATES_NOT_OBSERVED_INDIVIDUAL_DEMAND','complete_cost_checks':costs,'months':len(result['rows']),'modeled_collected_units':total_units,'actual_template_productions':actual_packets,'annual':annual,'native_actions_sha256':export['ledger']['actions_sha256']}


def daily_attainment(tape,end,target):
    """Exact [day-365days,day) signed native profit at preregistered daily ticks."""
    actions=tape['actions'];hours=[];prefix=[0]
    for a in actions:
        hours.append(a['day']);prefix.append(prefix[-1]+a['after']['profit']-a['before']['profit'])
    first=None
    for t in range(365*24,end+1,24):
        value=prefix[bisect_left(hours,t)]-prefix[bisect_left(hours,t-365*24)]
        if value>=target and first is None:first={'hour':t,'trailing365_profit_microUSD':value}
    return {'first_daily_attainment':first,'target_microUSD':target,'observation':'fixed daily boundaries; not annualized exit rate'}


def _usd(value):
    amount=Fraction(str(value))*1_000_000
    if amount.denominator!=1:raise ValueError('WHOLE_MICROUSD_SOURCE_REQUIRED')
    return amount.numerator


def _ceil(value):return -(-value.numerator//value.denominator)


def payment_unit_microUSD(unit_price,world):
    """Independent exact per-unit fee, then multiplied by released quantity."""
    return _ceil(Fraction(unit_price)*Fraction(str(world['payment_rate']))+_usd(world['payment_fixed_usd']))


def check_financial_schedule(reg,world,manifest,result,export):
    """Require every declared cost and settlement; conservation alone is insufficient.

    Assumes canonical native replay was accepted by caller. No money is mutated.
    Tax convention is floor to microUSD, cumulative positive pretax profit less
    already paid tax; prior tax is never refunded after a subsequent loss.
    """
    actions=export['ledger']['actions'];journal=export['connected_journal']['entries']
    if not actions:raise ValueError('NATIVE_ORIGIN_ACTION_REQUIRED')
    if result.get('summary')!=actions[-1]['after']:raise ValueError('FINAL_SUMMARY_NOT_NATIVE')
    end=reg['operating_days']*24
    if result.get('operating_end_hour')!=end or result.get('complete') is not True:raise ValueError('REGISTERED_COMPLETE_HORIZON_REQUIRED')
    rows=result['rows'];maximum=(reg['operating_days']-1)//reg['month_days']+1
    stopped=bool(rows and rows[-1]['funded'] is False)
    if (not rows or len(rows)>maximum or (not stopped and len(rows)!=maximum)
        or result.get('financially_stopped')!=stopped):raise ValueError('REGISTERED_MONTH_DENOMINATOR_REQUIRED')
    expected_spends={'initial-development':(_usd(reg['setup_usd']),0)}
    expected_offers={};expected_events={};processing={};checkpoints={};hours=[a['day'] for a in actions]
    def at(index):return actions[index-1]['after'] if index else actions[0]['before']
    for month,row in enumerate(rows):
        decision=row['decision'];proposal=decision['proposal'];hour=month*reg['month_days']*24
        checkpoints[hour]=decision['native_sequence_before']
        after_index=bisect_right(hours,hour+2)
        if row['native_after']!=at(after_index):raise ValueError('MONTH_AFTER_SUMMARY_NOT_NATIVE')
        for kind,receipt in row['funding'].items():
            if receipt is not None:expected_spends[f'm{month}-{kind}']=(proposal['costs_microUSD'][kind],hour)
        if not row['funded']:continue
        job=manifest['jobs'][month]['id'];collected=proposal['collected_units']
        failed=proposal['chosen_orders']-collected;unit=_usd(proposal['unit_price_usd'])
        when=hour+world['settlement_days']*24
        for ident,quantity,released in ((job,collected,True),(job+'-uncollected',failed,False)):
            if not quantity:continue
            expected_offers[ident]={'job_id':job,'price':quantity*unit,'hour':hour+1,
                                    'decision_sha256':digest(decision),'collection':when,'released':released}
            for event in ('consent','fund'):expected_events[(ident,event)]=hour+1
            if released:
                expected_events[(ident,'prepare')]=hour+2
                expected_events[(ident,'release')]=when
                processing['processing-'+ident]=(quantity*payment_unit_microUSD(unit,world),when)
            else:expected_events[(ident,'refund')]=when
    spends=[e for e in journal if e['request'].get('operation')=='spend']
    if len(spends)!=len(expected_spends) or {e['request']['id'] for e in spends}!=set(expected_spends):raise ValueError('UNACCOUNTED_OR_MISSING_RESOURCE_SPEND')
    for entry in spends:
        request=entry['request'];amount,day=expected_spends[request['id']]
        if entry['status']!='COMPLETE' or request['amount']!=amount or request['day']!=day:raise ValueError('SETUP_OR_RESOURCE_COST_CHANGED')
        if request['id']=='initial-development':
            if (entry['funding']!='SEED' or request['kind']!='reconciliation_bulk_resource'
                or request['work']!={'registration':digest(reg),'kind':'shared_development'}):raise ValueError('INITIAL_SETUP_SOURCE_OR_FUNDING_CHANGED')
    offered=[a for a in actions if a['op']=='offer']
    if len(offered)!=len(expected_offers) or {a['args']['id'] for a in offered}!=set(expected_offers):raise ValueError('MISSING_OR_EXTRA_MODELED_COHORT')
    for action in offered:
        expected=expected_offers[action['args']['id']]
        if action['day']!=expected['hour'] or any(action['args'].get(k)!=expected[k] for k in ('job_id','price','decision_sha256')):raise ValueError('COHORT_PRICE_QUANTITY_TIMING_CHANGED')
    events=[a for a in actions if a['op']=='event']
    if len(events)!=len(expected_events):raise ValueError('MISSING_OR_EXTRA_SETTLEMENT_EVENT')
    seen=set()
    for action in events:
        key=(action['args']['id'],action['args']['action'])
        if key in seen or key not in expected_events or action['day']!=expected_events[key]:raise ValueError('SETTLEMENT_OR_REFUND_SCHEDULE_CHANGED')
        seen.add(key)
    terms_actions=[a for a in actions if a['op']=='register_terms']
    if (len(terms_actions)!=len(expected_offers) or {a['args']['id'] for a in terms_actions}!={ident+'-terms' for ident in expected_offers}):raise ValueError('MISSING_OR_EXTRA_REGISTERED_TERMS')
    drain=max([end]+[o['collection']+world['tail_days']*24+1 for o in expected_offers.values()])
    if result.get('settlement_drain_hour')!=drain:raise ValueError('SETTLEMENT_DRAIN_CHANGED')
    checkpoints[end-1]=bisect_right(hours,end-1)
    checkpoints[drain]=bisect_right(hours,drain)
    costs=[e for e in journal if e['request'].get('operation')=='execute' and e['request'].get('op')=='cost']
    known={};taxes={}
    for entry in costs:
        request=entry['request'];args=request['args'];ident=args['id']
        if entry['status']!='COMPLETE' or ident in known:raise ValueError('UNIQUE_COMPLETE_COST_REQUIRED')
        known[ident]=(args['amount'],request['day'])
        if ident.startswith('tax-'):
            day=request['day']
            if ident!='tax-'+str(day) or day not in checkpoints or day in taxes:raise ValueError('UNREGISTERED_TAX_CHECKPOINT')
            taxes[day]=args['amount']
        elif ident not in processing or known[ident]!=processing[ident]:raise ValueError('UNEXPECTED_OR_CHANGED_OPERATING_COST')
    if {k:v for k,v in known.items() if not k.startswith('tax-')}!=processing:raise ValueError('PAYMENT_PROCESSING_COST_MISSING')
    paid_tax=0;rate=Fraction(str(reg['tax_rate']))
    for day,index in sorted(checkpoints.items()):
        actual=taxes.get(day,0)
        pretax=at(index)['profit']+paid_tax+actual
        total_due=max(0,pretax)*rate
        due=max(0,total_due.numerator//total_due.denominator-paid_tax)
        if actual!=due:raise ValueError('CUMULATIVE_TAX_PROVISION_MISMATCH')
        paid_tax+=actual
    if any(a['day']>drain for a in actions):raise ValueError('EVENT_AFTER_DECLARED_DRAIN')
    return {'accepted':True,'setup_microUSD':_usd(reg['setup_usd']),
            'processing_microUSD':sum(amount for amount,_ in processing.values()),
            'tax_paid_microUSD':paid_tax,'cohorts':len(expected_offers),
            'settlement_events':len(expected_events),'cost_arithmetic':'EXACT_INTEGER_RATIONAL_MICROUSD'}
