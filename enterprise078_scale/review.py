"""Read-only native audit, complete operating replay and cross-record checks.

This uses the existing independent delivery checker and native full-history audit.
Controller replay is same-source reproduction, not independent external authorship.
"""
from __future__ import annotations
import argparse, copy, json
from pathlib import Path
from commercial.ledger import digest
from connected_enterprise.finance import audit_journal
from connected_enterprise.scale import trailing_profit, aggregate_native
from enterprise078.service import load_contracts, verify_delivery
from .operator import ROOT, read, save, load_protocol, driver_identity, initial_state, plan
from .model import opportunities, capital, cost, USD
from .account import expected_requests

class NativePrefixView:
    def __init__(self,tape,index):
        self.tape=tape;self.index=index
        self.summary=tape['actions'][index-1]['after'] if index else tape['actions'][0]['before']
    def snapshot(self):return {'summary':copy.deepcopy(self.summary)}
    def export(self):return {'ledger':{'actions':copy.deepcopy(self.tape['actions'][:self.index]),'summary':copy.deepcopy(self.summary)}}


def review(case,*,complete=True):
    case=Path(case);p=load_protocol();context=read(case/'context.json');m=read(case/'manifest.json')
    record=read(case/'account.json');operating=read(case/'operating.json');result=read(case/'result.json')
    w=next(x for x in p['worlds'] if x['id']==context['world']['id'])
    if context['world']!=w or context['protocol_sha256']!=digest(p) or context['driver']!=driver_identity():raise ValueError('FROZEN_OPERATING_CONTEXT_MISMATCH')
    if context['opening']!=capital(p,w) or context['manifest_sha256']!=digest(m):raise ValueError('CAPITAL_OR_MANIFEST_MISMATCH')
    if result['account_sha256']!=digest(record) or result['operating_state_sha256']!=digest(operating):raise ValueError('RESULT_RECORD_BINDING_MISMATCH')
    inventory={o['id']:o for o in opportunities(p)}
    contracts=load_contracts(ROOT,m)
    if set(contracts)!=set(inventory):raise ValueError('REGISTERED_REQUEST_DENOMINATOR_CHANGED')
    for ident,o in inventory.items():
        if next(j for j in m['jobs'] if j['id']==ident)['request']!=o['request']:raise ValueError('REGISTERED_REQUEST_CHANGED')
    native=audit_journal(record,root=ROOT,manifest=m)
    tape=record['ledger'];entries=record['connected_journal']['entries']
    regular=[x for x in entries if not (x['request'].get('operation')=='execute' and x['request'].get('op')=='mature')]
    replay=initial_state(context,p);cursor=0;wallets=set();last_prefix=0;earned_cost=0
    for index,observed in enumerate(operating['events']):
        if not replay['queue']:raise ValueError('EXTRA_OPERATING_EVENT')
        item=replay['queue'][0];prefix=observed.get('native_prefix_before')
        if type(prefix) is not int or not last_prefix<=prefix<=len(tape['actions']):raise ValueError('NATIVE_PREFIX_ORDER_MISMATCH')
        if prefix and tape['actions'][prefix-1]['day']>item['hour']:raise ValueError('FUTURE_NATIVE_STATE_USED_FOR_DECISION')
        for action in tape['actions'][last_prefix:prefix]:
            if action['op']!='mature' or action['day']!=item['hour']:raise ValueError('UNEXPLAINED_NATIVE_ADVANCEMENT')
        commands,after=plan(NativePrefixView(tape,prefix),replay,item,p,w,context,inventory)
        candidate=after['events'][-1]
        if candidate!={k:v for k,v in observed.items() if k!='native_receipts'}:raise ValueError('OPERATING_DECISION_REPLAY_MISMATCH:'+str(index))
        receipts=[];end_prefix=prefix
        for cmd in commands:
            requests=expected_requests(cmd,wallets);matched=[]
            for expected in requests:
                if cursor>=len(regular) or regular[cursor]['request']!=expected:raise ValueError('NATIVE_REQUEST_COVERAGE_MISMATCH:'+str(cursor))
                entry=regular[cursor];cursor+=1;matched.append(entry)
                seq=entry['receipt'].get('native_event_sequence')
                end=seq+1 if seq is not None else entry['receipt'].get('sequence')
                if type(end) is not int or end<end_prefix or end>len(tape['actions']):raise ValueError('INVALID_NATIVE_RECEIPT_SEQUENCE')
                if any(x['day']!=item['hour'] for x in tape['actions'][end_prefix:end]):raise ValueError('COST_OR_OUTPUT_OUTSIDE_EVENT_CLOCK')
                end_prefix=end
            if cmd['op']=='spend':
                receipt=matched[0]['receipt'];receipts.append(receipt);after['funding'].append(receipt)
                if receipt['funding']=='EARNED':earned_cost+=receipt['amount']
            else:
                # Bind operation receipts through the native journal, while the
                # original delivery verifier separately checks artifact content.
                receipts.append(observed['native_receipts'][len(receipts)])
            if cmd['op'] in ('cost','spend'):
                after['spending'].append({'hour':cmd['args']['day'],'id':cmd['args']['ident'],
                                          'op':cmd['op'],'amount':cmd['args']['amount']})
        after['events'][-1]['native_receipts']=receipts
        if receipts!=observed['native_receipts']:raise ValueError('RESOURCE_FUNDING_RECEIPT_CHANGED')
        replay=after;last_prefix=end_prefix
    if cursor!=len(regular) or last_prefix!=len(tape['actions']):raise ValueError('UNACCOUNTED_NATIVE_OPERATION')
    if replay!=operating:raise ValueError('COMPLETE_OPERATING_STATE_REPLAY_MISMATCH')
    if complete and (not replay['completed'] or replay['queue'] or replay['pending']):raise ValueError('INCOMPLETE_OPERATING_WINDOW')
    if replay['completed']:
        periods=[e['data']['period'] for e in replay['events'] if e['event']=='period']
        if periods!=list(range(p['periods'])):raise ValueError('MISSING_REGISTERED_PERIOD')
        if not any(e['event']=='close' and e['hour']==p['horizon_hours']-1 for e in replay['events']):raise ValueError('MISSING_CLOSURE_COSTS')
    accepted=0;collected=0
    for order in replay['orders'].values():
        j=next(x for x in m['jobs'] if x['id']==order['job'])
        actual=read(ROOT/j['delivery_path'])
        if digest(actual)!=order['artifact_sha256']:raise ValueError('DELIVERY_IDENTITY_MISMATCH')
        checked=verify_delivery(ROOT,m,order['job'],actual)
        if checked['accepted']!=order['accepted']:raise ValueError('ACCEPTANCE_RECONSTRUCTION_MISMATCH')
        accepted+=checked['accepted'];collected+=order['status']=='released'
    if len({x['job'] for x in replay['orders'].values()})!=len(replay['orders']):raise ValueError('DUPLICATE_JOB')
    for funding in replay['funding']:
        if funding['kind'] in ('capacity-lease','distinct-characterization-construction') and funding['funding']!='EARNED':raise ValueError('SUCCESSOR_OR_EXPANSION_NOT_EARNED_FUNDED')
    fees=sum(a['after']['expenses']-a['before']['expenses'] for a in tape['actions']
             if a['op']=='event' and a['args'].get('action') in ('release','refund'))
    recorded_costs=sum(x['amount'] for x in replay['spending'])
    if recorded_costs+fees!=tape['summary']['expenses']:raise ValueError('COMPLETE_MODELED_COST_RECONCILIATION_FAILED')
    observer=trailing_profit(tape,operating_end_hour=p['horizon_hours'],operating_complete=replay['completed'])
    if result['observer']!=observer or result['summary']!=tape['summary'] or result['collected_outputs']!=collected or result['accepted_artifacts']!=accepted:raise ValueError('REPORTED_FINANCE_OR_DELIVERY_CHANGED')
    if result['commercial_milestone_qualified'] or result['real_revenue_microUSD'] or result['original_account_continuation']:raise ValueError('UNSUPPORTED_REAL_OR_CONTINUATION_CLAIM')
    threshold=observer['trailing_365_day_profit_microUSD'] is not None and observer['trailing_365_day_profit_microUSD']>=p['milestone_USD']*USD
    if result['native_threshold_crossed']!=threshold:raise ValueError('FALSE_MILESTONE_FLAG')
    return {'accepted':True,'scope':'KEY_FREE_NATIVE_AUDIT_AND_SAME_SOURCE_OPERATING_REPRODUCTION',
        'native':native,'operating_events':len(replay['events']),'native_actions':len(tape['actions']),
        'accepted_artifacts':accepted,'collected_outputs':collected,'earned_funded_spend_microUSD':earned_cost,
        'complete_cost_reconciled_microUSD':recorded_costs+fees,'native_to_daily_deviation_microUSD':aggregate_native(tape)['max_overlap_deviation_microUSD'],
        'discovery_advantage':'NOT_ESTABLISHED','market_calibration':'NOT_ESTABLISHED','original_account_continuation':False}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('case',type=Path);args=parser.parse_args()
    print(json.dumps(review(args.case),sort_keys=True))
if __name__=='__main__':main()
