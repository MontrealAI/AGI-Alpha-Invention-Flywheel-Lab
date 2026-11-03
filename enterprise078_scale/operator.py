"""Resumable full-year software-package operator over the existing native account.

The signed queue is operating state, never a second ledger. All money mutations
and ownership/recovery checks are delegated to JournalAccount/adaptive Account.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, os, time
from datetime import datetime, timedelta
from pathlib import Path
from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from commercial.terms_exact_v2 import prospective_terms
from connected_enterprise.scale import aggregate_native, trailing_profit
from .account import ScaleBusinessAccount as BusinessAccount, expected_requests
from enterprise078.service import prepare_manifest
from enterprise078.construct import produce
from enterprise078.verify import verify
from .model import USD, cost, capital, opportunities, public_market, quote, buyer_choice, fulfillment

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return strict_json(Path(path).read_bytes())

def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    atomic_bytes(path, canonical(value) + b'\n')

def driver_identity(root=ROOT):
    names = sorted([p.relative_to(root).as_posix() for p in (root/'enterprise078_scale').glob('*.py')]
                   + ['enterprise078_scale/PROTOCOL.json'])
    return {n: hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names}

def load_protocol():
    p = read(ROOT/'enterprise078_scale/PROTOCOL.json')
    if p['horizon_hours'] != p['period_hours'] * p['periods'] or p['horizon_hours'] != 8760:
        raise ValueError('ONE_REGISTERED_COMPLETE_YEAR_REQUIRED')
    return p

def event(hour, kind, **data):
    return {'hour': hour, 'kind': kind, 'data': data}

def enqueue(state, *items):
    state['queue'].extend(items)
    state['queue'].sort(key=lambda e: (e['hour'], e['kind'], digest(e['data'])))

def initial_state(context, p):
    s = {'context_sha256': digest(context), 'driver_sha256': digest(context['driver']),
         'queue': [], 'pending': None, 'clock': 0, 'events': [], 'orders': {},
         'buyers_committed': {}, 'contacts': {}, 'channels': {}, 'capacity': [],
         'used_slots': {}, 'capacity_lost': {}, 'quotes': [], 'retained': None,
         'K2': None, 'collected_K1': 0, 'collected_by_period': {}, 'zero_periods': 0,
         'halted': False, 'completed': False, 'funding': [], 'spending': []}
    enqueue(s, event(0, 'startup'), *(event(12+i*p['period_hours'], 'period', period=i)
            for i in range(p['periods'])), event(p['horizon_hours']-1, 'close'))
    return s

def lease_units(state, hour, period):
    return sum(x['units'] for x in state['capacity'] if x['active'] <= hour < x['expires']) - state['used_slots'].get(str(period), 0)

def reserve_need(p, w, price, kind):
    fee = price * p['payment_fee_basis_points'] // 10_000
    return price + fee + 200_000 + sum(cost(p, w, n) for n in (kind+'_production', kind+'_support', 'repair'))

def command(op, **args):
    return {'op': op, 'args': args}

def plan(a, state, item, p, w, context, inventory):
    """Choose only from current native state and permitted current observations."""
    s = copy.deepcopy(state); s['pending'] = None
    if not s['queue'] or s['queue'][0] != item: raise ValueError('QUEUE_HEAD_CHANGED')
    s['queue'].pop(0); h, kind, d = item['hour'], item['kind'], item['data']
    s['clock'] = h
    row = {'hour': h, 'event': kind, 'data': d, 'commands': [], 'decision': None,
           'native_prefix_before': len(a.export()['ledger']['actions'])}
    commands = []
    summary = a.snapshot()['summary']
    def expense(ident, amount):
        commands.append(command('cost', ident=ident, amount=amount, day=h))
    def spend(ident, label, amount, work, allow_seed=True):
        commands.append(command('spend', ident=ident, kind=label, amount=amount, day=h,
                                work=work, expected_net=max(1, amount), allow_seed=allow_seed))
    if kind == 'startup':
        expense('scale-research-and-failures', cost(p,w,'research_and_failed_search'))
        if context['opening'] == 0:
            s['halted'] = True; row['decision'] = 'NO_FINANCING_INCURRED_ASSESSMENT_PAYABLE'
        else:
            for n in ('construction_and_integration','equity_issuance','base_capacity_annual'):
                expense('scale-'+n, cost(p,w,n))
            s['capacity'].append({'invoice':'scale-base_capacity_annual', 'units':p['base_capacity_per_period'],
                                  'active':0,'expires':p['horizon_hours'],'funding':'OPENING_EQUITY'})
            row['decision'] = 'FUNDED_SOFTWARE_CONSTRUCTION'
    elif kind == 'period':
        t = d['period']; key = str(t)
        if t:
            s['zero_periods'] = s['zero_periods'] + 1 if s['collected_by_period'].get(str(t-1),0)==0 else 0
            if s['zero_periods'] >= 3: s['halted'] = True
        if s['halted']:
            row['decision'] = 'STOP_DISCRETIONARY_WORK_RETAIN_OBLIGATIONS'
        else:
            expense('scale-maintenance-'+key, cost(p,w,'maintenance_per_period'))
            room = summary['available'] - cost(p,w,'maintenance_per_period')
            earned_room = max(0, summary['unrestrictedEarned'] - cost(p,w,'maintenance_per_period'))
            extras = sum(x['invoice'].startswith('scale-extra-') for x in s['capacity'])
            lease_cost = cost(p,w,'extra_capacity_annual')
            if t and s['capacity_lost'].get(str(t-1),0) > 0 and extras < p['supplier_extra_capacity_units']:
                # Preserve enough present funds for at least a complete base order.
                minimum = reserve_need(p,w,min(p['quote_menu_USD']['preparation'])*USD,'preparation')
                if not summary['investmentStopped'] and min(room-minimum,earned_room) >= lease_cost:
                    ident='scale-extra-'+key
                    spend(ident,'capacity-lease',lease_cost,{'units':p['extra_capacity_per_period'],
                          'active':h+p['capacity_lead_hours'],'expires':h+p['capacity_lead_hours']+p['capacity_lifetime_hours']},False)
                    s['capacity'].append({'invoice':ident,'units':p['extra_capacity_per_period'],
                        'active':h+p['capacity_lead_hours'],'expires':h+p['capacity_lead_hours']+p['capacity_lifetime_hours'],'funding':'EARNED'})
                    room -= lease_cost; earned_room -= lease_cost
            for c in (0,1):
                label='direct' if c==0 else 'partner'
                channel_cost=cost(p,w,label+'_channel_per_period')
                if c==1 and s['collected_K1'] < 2: continue
                if room < channel_cost or (c==1 and earned_room < channel_cost) or summary['investmentStopped']: continue
                ident=f'scale-channel-{t}-{c}'
                spend(ident,'acquisition-channel',channel_cost,{'period':t,'channel':c,'expires':h+p['period_hours']},c==0)
                s['channels'][f'{t}:{c}']={'invoice':ident,'active':h,'expires':h+p['period_hours']}
                room -= channel_cost; earned_room = max(0, earned_room-channel_cost)
                count=p[label+'_contacts_per_period']
                enqueue(s,*(event(h+1+c*count+j,'contact',id=f'scale078-p{t:02d}-c{c}-s{j}') for j in range(count)))
            row['decision'] = 'OPERATE_COSTED_CHANNELS_AND_CAPACITY'
    elif kind == 'contact':
        o=inventory[d['id']]; t=o['period']; key=str(t); contact_key=f'{t}:{o["buyer"]}'
        public=public_market(p,w,o['request']['kind'],t,s['quotes']); price=quote(p,w,public)
        row.update(opportunity=o,public_market=public,quote=price)
        if contact_key in s['contacts']:
            row['decision']='OVERLAP_DEDUPLICATED_NO_SECOND_CONTACT'
        elif lease_units(s,h,t) <= 0:
            s['capacity_lost'][key]=s['capacity_lost'].get(key,0)+1
            row['decision']='CAPACITY_UNAVAILABLE_NO_CONTACT_OR_ORDER'
        elif price is None:
            row['decision']='NO_POSITIVE_MARGIN_PUBLIC_QUOTE'
        elif o['request']['kind']=='characterization' and not s['K2'] and s['collected_K1'] < 2:
            row['decision']='SUCCESSOR_NOT_YET_SUPPORTED'
        elif summary['available'] < cost(p,w,'contact') or summary['investmentStopped']:
            row['decision']='UNFUNDED_CONTACT'
        else:
            spend('scale-contact-'+o['id'],'customer-acquisition',cost(p,w,'contact'),{'opportunity':o['id'],'buyer':o['buyer']})
            s['contacts'][contact_key]=o['id']
            s['quotes'].append({'period':t,'kind':o['request']['kind'],'quote':price})
            response=buyer_choice(p,w,o,public,price,s['buyers_committed'].get(o['buyer'],0))
            row['buyer_response']=response
            need=reserve_need(p,w,price,o['request']['kind'])+cost(p,w,'contact')
            extra=cost(p,w,'K2_construction') if o['request']['kind']=='characterization' and not s['K2'] else 0
            if not response['accepted']:
                row['decision']='VOLUNTARY_BUYER_DECLINE'
            elif summary['available'] < need+extra or (extra and summary['unrestrictedEarned'] < extra+cost(p,w,'contact')):
                row['decision']='WHOLE_DELIVERY_UNFUNDED_NO_ORDER'
            else:
                if extra:
                    ident='scale-K2-construction'
                    spend(ident,'distinct-characterization-construction',extra,{'predecessor_collections':s['collected_K1'],
                          'retained_executor':s['retained'],'outcome':'monotone transition bracket'},False)
                    s['K2']={'invoice':ident,'hour':h,'retained':s['retained'] is not None,'funding':'EARNED'}
                order=w['id']+'-'+o['id']; completion=h+p['production_latency_hours']; payment=completion+p['collection_delay_hours']
                fee=price*p['payment_fee_basis_points']//10_000
                terms=prospective_terms(order,price,payment+w['maturity_delay_hours'],payment,
                    exposure=price+fee+200_000,residual=cost(p,w,'residual_per_order'),fee=fee,
                    counterparty_obligations='Software-only synthetic-interface preparation or characterization package, independent source-bound check; no physical instrument or live customer. Support, refunds and residual claims remain producer obligations.')
                commands.append(command('begin',job_id=o['id'],order_id=order,buyer_id=o['buyer'],price=price,
                                        buyer_budget=response['budget'],day=h,deadline=payment+24,terms=terms))
                spend('scale-production-'+o['id'],'production-and-verification',cost(p,w,o['request']['kind']+'_production'),
                      {'request_sha256':digest(o['request']),'request':o['id'],'latency_hours':p['production_latency_hours']})
                s['orders'][order]={'id':order,'job':o['id'],'buyer':o['buyer'],'price':price,'period':t,'kind':o['request']['kind'],
                                     'start':h,'completion':completion,'payment':payment,'status':'funded','terms':terms}
                s['buyers_committed'][o['buyer']]=s['buyers_committed'].get(o['buyer'],0)+price
                s['used_slots'][key]=s['used_slots'].get(key,0)+1
                enqueue(s,event(completion,'complete',order=order),event(payment,'payment',order=order),event(payment+1,'tax',period=t))
                row['decision']='VOLUNTARY_FUNDED_ORDER';row['order']=order
    elif kind == 'complete':
        order=s['orders'][d['order']]; request=inventory[order['job']]['request']
        flags=fulfillment(p,w,order['job']); retained=s['retained'] if request['kind']=='characterization' and w.get('retain_executor',True) else None
        artifact=produce(request,retained=retained)
        if flags['fault']:
            failed=copy.deepcopy(artifact);failed['rows'][0]['quantity']+=1
            failure_check=verify(request,failed)
            if failure_check['accepted']: raise ValueError('FAULT_NOT_DETECTED')
            row['failed_attempt']={'artifact':failed,'acceptance':failure_check}
            if summary['available'] >= cost(p,w,'repair') and not summary['investmentStopped']:
                spend('scale-repair-'+order['job'],'one-correction-and-recheck',cost(p,w,'repair'),{'request':order['job'],'failed_hash':digest(failed)})
                row['repair']='PAID_ONE_RETRY'
                artifact=produce(request,retained=retained)
            else: artifact=failed;row['repair']='UNFUNDED_REFUND_REQUIRED'
        check=verify(request,artifact)
        commands.append(command('deliver',order_id=order['id'],job_id=order['job'],artifact=artifact,day=h,expected_accepted=check['accepted']))
        expense('scale-support-'+order['job'],cost(p,w,request['kind']+'_support'))
        order['artifact_sha256']=digest(artifact);order['accepted']=check['accepted']
        order['status']='verified' if check['accepted'] else 'refunded'
        if not check['accepted']:
            commands.append(command('refund',order_id=order['id'],day=h))
            s['buyers_committed'][order['buyer']]-=order['price']
        elif request['kind']=='preparation':
            s['retained']={'family':artifact['family'],'policy':artifact['policy'],
                           'producer_sha256':context['native_producer_sha256']}
        row['decision']='ACCEPTED_SOFTWARE_ARTIFACT' if check['accepted'] else 'REJECTED_REFUNDED'
        row['artifact_sha256']=digest(artifact);row['acceptance']=check
    elif kind == 'payment':
        order=s['orders'][d['order']]
        if order['status']=='refunded': row['decision']='NO_REVENUE_REJECTED_ORDER'
        elif fulfillment(p,w,order['job'])['nonpayment']:
            commands.append(command('refund',order_id=order['id'],day=h))
            s['buyers_committed'][order['buyer']]-=order['price'];order['status']='refunded'
            row['decision']='ACCEPTED_BUT_NOT_COLLECTED_REFUND'
        else:
            commands.append(command('release',order_id=order['id'],day=h));order['status']='released'
            key=str(order['period']);s['collected_by_period'][key]=s['collected_by_period'].get(key,0)+1
            if order['kind']=='preparation':s['collected_K1']+=1
            row['decision']='COLLECTED_ACCEPTED_OUTPUT'
    elif kind in ('tax','close'):
        # Taxes are modeled nonrefundable installments, not a jurisdictional rule.
        if kind=='close':
            expense('scale-shutdown',cost(p,w,'shutdown'))
        tape=a.export()['ledger']; paid=sum(x['args']['amount'] for x in tape['actions']
            if x['op']=='cost' and x['args']['id'].startswith('scale-tax-'))
        pretax=summary['profit']+paid-(cost(p,w,'shutdown') if kind=='close' else 0)
        due=max(0,max(0,pretax)*p['positive_income_tax_basis_points']//10_000-paid)
        if due: expense('scale-tax-'+str(h),due)
        row['decision']='CLOSE_COMPLETE_WINDOW' if kind=='close' else 'ACCRUE_MODELED_TAX'
        if kind=='close':s['completed']=True
    else: raise ValueError('UNSUPPORTED_OPERATING_EVENT')
    row['commands']=copy.deepcopy(commands)
    s['events'].append(row)
    return commands,s

def execute(a, cmd):
    args=copy.deepcopy(cmd['args']);op=cmd['op']
    if op=='advance':return a.advance(args['day'])
    if op=='cost':return a.cost(**args)
    if op=='spend':
        result=a.spend(**args)
        if result is None:raise ValueError('PLANNED_RESOURCE_WAS_NOT_NATIVE_FUNDED')
        return result
    if op=='begin':return a.begin_order(**args)
    if op=='deliver':
        accepted=args.pop('expected_accepted');result=a.complete_order(**args)
        if result['accepted']!=accepted:raise ValueError('PRODUCER_INDEPENDENT_ACCEPTANCE_DISAGREEMENT')
        return result
    if op=='release':return a.release(**args)
    if op=='refund':return a.refund(**args)
    raise ValueError('UNSUPPORTED_NATIVE_COMMAND')

def initialize(output, world_id, p):
    pub=output/'public'/world_id;private=output/'private'/world_id
    if pub.exists() or private.exists():raise ValueError('EXISTING_CASE_REQUIRES_EXPLICIT_RESUME')
    world=next(w for w in p['worlds'] if w['id']==world_id)
    inventory=opportunities(p); profile=f'enterprise078/scale_inputs/{digest(p)[:16]}-{world_id}.json'
    value=[o['request'] for o in inventory]
    if (ROOT/profile).exists() and read(ROOT/profile)!=value:raise ValueError('FROZEN_PROFILE_CHANGED')
    save(ROOT/profile,value)
    manifest=prepare_manifest(ROOT,[{'id':o['id'],'profile_path':profile,
        'delivery_path':f'enterprise078/deliveries/scale-{digest(p)[:16]}-{world_id}/{o["id"]}.json'} for o in inventory])
    opening=capital(p,world)
    working=3*cost(p,world,'maintenance_per_period')+cost(p,world,'shutdown') if opening else 0
    context={'schema':'enterprise078-scale/context/v1','protocol_sha256':digest(p),'world':world,
        'opening':opening,'working':working,'contract':'enterprise078-scale-'+world_id,'driver':driver_identity(),
        'manifest_sha256':digest(manifest),'native_producer_sha256':manifest['source_hashes']['enterprise078/construct.py'],
        'original_account_continuation':False,'account_kind':'FRESH_REGISTERED_COUNTERFACTUAL_NOT_BASELINE_REPLACEMENT'}
    pub.mkdir(parents=True);private.mkdir(parents=True,mode=0o700)
    save(pub/'context.json',context);save(pub/'manifest.json',manifest)
    with BusinessAccount(ROOT,manifest,private/'account',opening=opening,working=working,contract=context['contract']) as a:
        save(private/'state.json',a.seal_checkpoint(initial_state(context,p)))
    return context,manifest

def assert_resume_suffix(a, envelope, state):
    record=a.export();tape=record['ledger'];prefix=envelope['body']['native_sequence']
    suffix=tape['actions'][prefix:]
    if not suffix:return
    pending=state.get('pending')
    if pending is None:raise ValueError('UNACKNOWLEDGED_NATIVE_SUFFIX_OUTSIDE_PENDING_COMMAND')
    if pending['phase']=='advance':
        if any(x['op']!='mature' or x['day']!=pending['event']['hour'] for x in suffix):
            raise ValueError('UNEXPECTED_FINANCIAL_ADVANCEMENT')
        return
    if pending['phase']!='execute' or pending['index']>=len(pending['commands']):
        raise ValueError('UNEXPECTED_NATIVE_SUFFIX')
    command=pending['commands'][pending['index']]
    wallets={x['args']['buyer'] for x in tape['actions'][:prefix] if x['op']=='wallet'}
    expected=expected_requests(command,wallets)
    extra=[]
    for entry in record['connected_journal']['entries']:
        receipt=entry.get('receipt')
        if not receipt:raise ValueError('UNRESOLVED_NATIVE_JOURNAL')
        end=receipt.get('sequence',receipt.get('native_event_sequence',-1)+1)
        if end>prefix:extra.append(entry['request'])
    if not extra or extra!=expected[:len(extra)] or any(x['day']!=command['args']['day'] for x in suffix):
        raise ValueError('NATIVE_SUFFIX_DOES_NOT_MATCH_PENDING_COMMAND')

def run_case(output,world_id,*,resume=False,max_events=None,interrupt_after=None):
    p=load_protocol();output=Path(output).absolute();pub=output/'public'/world_id;private=output/'private'/world_id
    if not resume:context,manifest=initialize(output,world_id,p)
    else:
        required=('account','account.adaptive-simulation-key','account.actions.jsonl','account.connected-journal.json','state.json')
        if any(not (private/n).is_file() or (private/n).is_symlink() for n in required):
            raise ValueError('ORIGINAL_PRIVATE_AUTHORITY_AND_NONEMPTY_OPERATING_STATE_REQUIRED')
        context,manifest=read(pub/'context.json'),read(pub/'manifest.json')
    if context['protocol_sha256']!=digest(p) or context['driver']!=driver_identity() or context['manifest_sha256']!=digest(manifest):
        raise ValueError('REGISTERED_OPERATING_SOURCE_CHANGED')
    w=next(w for w in p['worlds'] if w['id']==world_id)
    if context['world']!=w or context['opening']!=capital(p,w):raise ValueError('REGISTERED_SCENARIO_CHANGED')
    inventory={o['id']:o for o in opportunities(p)}
    completed=0;native_steps=0;cpu=time.process_time();wall=time.perf_counter()
    with BusinessAccount(ROOT,manifest,private/'account',opening=context['opening'],working=context['working'],contract=context['contract']) as a:
        envelope=read(private/'state.json');state=a.verify_checkpoint(envelope)
        assert_resume_suffix(a, envelope, state)
        if state['context_sha256']!=digest(context):raise ValueError('SIGNED_OPERATING_CONTEXT_CHANGED')
        def checkpoint():save(private/'state.json',a.seal_checkpoint(state))
        while state['queue'] or state['pending']:
            if max_events is not None and completed>=max_events:break
            if state['pending'] is None:
                item=state['queue'][0]
                state['pending']={'phase':'advance','event':item,'index':0,
                                  'commands':[command('advance',day=item['hour'])],'after':None,'receipts':[]}
                checkpoint()
            pending=state['pending']
            if pending['phase']=='advance':
                execute(a,pending['commands'][0]);pending['phase']='plan';checkpoint()
            if pending['phase']=='plan':
                commands,after=plan(a,state,pending['event'],p,w,context,inventory)
                pending.update(phase='execute',commands=commands,index=0,after=after,receipts=[]);checkpoint()
            while pending['index'] < len(pending['commands']):
                cmd=pending['commands'][pending['index']];receipt=execute(a,cmd);native_steps+=1
                if interrupt_after is not None and native_steps==interrupt_after:
                    raise InterruptedError('DEVELOPMENT_INTERRUPTION_AFTER_NATIVE_COMMIT_BEFORE_ACK')
                pending['receipts'].append(receipt if cmd['op']=='spend' else {'op':cmd['op'],'receipt_sha256':digest(receipt)})
                pending['index']+=1;checkpoint()
            state=pending['after']
            for cmd,receipt in zip(pending['commands'],pending['receipts']):
                if cmd['op']=='spend':
                    state['funding'].append(receipt)
                if cmd['op'] in ('cost','spend'):
                    state['spending'].append({'hour':cmd['args']['day'],'id':cmd['args']['ident'],
                                             'op':cmd['op'],'amount':cmd['args']['amount']})
            state['events'][-1]['native_receipts']=pending['receipts'];state['pending']=None
            checkpoint();completed+=1
        record=a.export();audited=a.audit()
        if state['completed'] and state['queue']:raise ValueError('FINISHED_WITH_PENDING_WORK')
        observer=trailing_profit(record['ledger'],operating_end_hour=p['horizon_hours'],operating_complete=state['completed'])
        summary=record['ledger']['summary']
        epoch=datetime.fromisoformat(p['epoch_utc']);end=epoch+timedelta(hours=p['horizon_hours'])
        result={'schema':'enterprise078-scale/result/v1','case':world_id,'completed':state['completed'],
            'scope':'CONDITIONAL_NATIVE_SOFTWARE_SIMULATION','context_sha256':digest(context),'native_audit':audited,
            'account_sha256':digest(record),'operating_state_sha256':digest(state),'summary':summary,'observer':observer,
            'period_utc':[epoch.isoformat(),end.isoformat()],'opening_microUSD':context['opening'],
            'collected_outputs':sum(o['status']=='released' for o in state['orders'].values()),
            'accepted_artifacts':sum(o.get('accepted',False) for o in state['orders'].values()),
            'net_collections_minus_payments_microUSD':summary['collections']-summary['expensePaid'],
            'equity_opportunity_charge_microUSD':context['opening']*p['equity_opportunity_basis_points']//10000,
            'native_threshold_crossed':observer['trailing_365_day_profit_microUSD'] is not None and observer['trailing_365_day_profit_microUSD']>=p['milestone_USD']*USD,
            'commercial_milestone_qualified':False,'real_revenue_microUSD':0,'actual_model_host_and_whole_development_billing':'UNKNOWN',
            'measured_worker_cpu_seconds':time.process_time()-cpu,'measured_worker_wall_seconds':time.perf_counter()-wall,
            'original_account_continuation':False,'source_binding':context['driver'],
            'limits':['Authored demand, prices, financing and cost envelopes are not market observations.',
                      'Original PR174 private account authority unavailable; this is a fresh registered scenario.',
                      'Native semantics and driver reproduction are not independent scientific authorship.',
                      'No physical laboratory, general discovery improvement or high-volume extrapolation is qualified.']}
        save(pub/'account.json',record);save(pub/'operating.json',state);save(pub/'result.json',result)
    with BusinessAccount(ROOT,manifest,private/'account',opening=context['opening'],working=context['working'],contract=context['contract']) as reopened:
        if reopened.export()!=record:raise ValueError('AUTHENTICATED_REOPEN_CHANGED_HISTORY')
        if reopened.verify_checkpoint(read(private/'state.json'))!=state:raise ValueError('AUTHENTICATED_REOPEN_CHANGED_QUEUE')
    result['unchanged_authenticated_reopen']=True;save(pub/'result.json',result)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--world',required=True)
    parser.add_argument('--resume',action='store_true');parser.add_argument('--max-events',type=int)
    args=parser.parse_args();os.umask(0o077)
    if args.max_events is not None and args.max_events<=0:raise ValueError('POSITIVE_QUANTUM_REQUIRED')
    r=run_case(args.output,args.world,resume=args.resume,max_events=args.max_events)
    print(json.dumps({k:r[k] for k in ('case','completed','collected_outputs','summary','unchanged_authenticated_reopen')},sort_keys=True))

if __name__=='__main__':main()
