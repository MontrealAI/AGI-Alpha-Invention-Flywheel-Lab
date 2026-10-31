"""Reconstruct strategic observations from native prefixes and operating records."""
import copy
import hashlib
from commercial.ledger import digest,read_bound,canonical
from adaptive_enterprise.account import action_prefix_digests
from adaptive_enterprise.strategies import offer_catalog
from .strategic_commerce import rederive

def expected_evaluations(root,manifest,result,lifecycle):
    """Reconstruct all observed needs and eligible sequential evaluations, not receipts."""
    cfg=result['config']; answer={}; services=('reconciliation','kpi_variance','evidence_matrix')
    admitted={j['id']:j for j in manifest['jobs'] if j['accepted'] and read_bound(root,j['artifact'],j['artifact_sha256']).get('outcome_scope')=='complete_outcome'}
    for moment,candidates in lifecycle['daily_candidate_ids_recomputed'].items():
        choices=[d for d in result['decisions'] if d['time']==moment and d.get('kind') in {'offer','outside_choice'}]
        needs=[ident for ident in candidates if int.from_bytes(hashlib.sha256(canonical(['connected014',result['seed'],[moment//24,ident],'need'])).digest()[:8],'big')/2**64<cfg['arrival_bps']/10000]
        if [d['customer_id'] for d in choices]!=needs:raise ValueError('SEQUENTIAL_NEED_COVERAGE_CHANGED')
        used={o['job_id'] for o in result['orders'] if o['qualified_time']<moment};count=0
        slots=min(cfg['maximum_slots'],cfg['initial_slots']+sum(i['kind']=='capacity' and i['activation_time']<=moment and moment+cfg['production_hours']<i['expiry_time'] for i in result['investments']))
        if cfg['supplier_outage_start_day']<=moment//24<cfg['supplier_outage_start_day']+cfg['supplier_outage_days']:slots=0
        for d in choices:
            service=services[lifecycle['daily_public_buyers'][moment][d['customer_id']]['service_index']%3]
            available=sorted(ident for ident,j in admitted.items() if ident not in used and j['service_id']==service)
            job=available[0] if available and count<slots else None
            answer[(moment,d['customer_id'])]=job
            selection=d.get('strategic_selection')
            if (selection is not None)!=(job is not None):raise ValueError('SEQUENTIAL_EVALUATION_RECEIPT_COVERAGE_CHANGED')
            if selection is not None and selection['problem']['job_id']!=job:raise ValueError('SEQUENTIAL_ADMITTED_JOB_CHANGED')
            if d.get('chosen'):
                order=next(o for o in result['orders'] if o['qualified_time']==moment and o['customer_id']==d['customer_id'])
                if order['job_id']!=job:raise ValueError('SEQUENTIAL_SELECTED_JOB_CHANGED')
                used.add(job);count+=1
    return answer

def audit_decisions(root,manifest,result,lifecycle):
    cfg=result['config']
    if 'strategic_policy' not in cfg:return {}
    tape=result['owned_account']['ledger'];prefixes=action_prefix_digests(tape['actions'])
    jobs={j['id']:j for j in manifest['jobs']};events={e['time']:e for e in result['events'] if e['kind']=='BUSINESS_DECISION'}
    evaluations=expected_evaluations(root,manifest,result,lifecycle)
    lifecycle['sequential_evaluation_counts']={t:sum(moment==t and job is not None for (moment,_),job in evaluations.items()) for t in lifecycle['daily_candidate_ids_recomputed']}
    prior_orders=[];count=0;no_bid=0
    for position,decision in enumerate(result['decisions']):
        if decision.get('kind') not in {'offer','outside_choice'}:continue
        selection=decision.get('strategic_selection')
        if selection is None:
            if decision['kind']=='offer':raise ValueError('STRATEGIC_QUOTE_RECEIPT_MISSING')
            continue
        count+=1;moment=decision['time'];problem=selection['problem'];cash=decision['cash_basis'];snapshot=cash['snapshot']
        if problem['policy']!=cfg['strategic_policy'] or problem['method_policy']!=cfg.get('mechanism_policy'):
            raise ValueError('STRATEGIC_POLICY_DIFFERS_FROM_FROZEN_CONFIG')
        charges=[a for a in tape['actions'] if a['op']=='cost' and a['args'].get('id')=='maintenance-'+str(moment//24)]
        if len(charges)!=1 or charges[0]['day']!=moment or charges[0]['args'].get('amount')!=cfg['maintenance_daily']:
            raise ValueError('NATIVE_PREPAID_PLANNING_CONTRACT_REQUIRED')
        charge=charges[0];seq=charge['seq']+1;summary=charge['after']
        state_digest=digest({'config':tape['config'],'actions_sha256':prefixes[seq],'summary':summary})
        if snapshot['sequence']!=seq or snapshot['summary']!=summary or snapshot['actions_sha256']!=prefixes[seq] or snapshot['state_digest']!=state_digest:
            raise ValueError('STRATEGIC_CASH_NOT_CURRENT_NATIVE_PREFIX')
        day_event=events[moment];contracts=cfg['channels']['pilot']
        operating=cfg['exposure_cost']*lifecycle['daily_outreach_units_recomputed'][moment]+cfg['qualification_cost']*len(lifecycle['daily_candidate_ids_recomputed'][moment])
        channel=(contracts['price_microUSD']+contracts['support_microUSD'])*bool(day_event['channel_selected'])
        capacity=cfg['capacity_price']*bool(day_event['capacity_selected'])
        earlier_choices=result['decisions'][:position]
        earlier_customers={d['customer_id'] for d in earlier_choices if d.get('kind')=='offer' and d['time']==moment and d.get('chosen')}
        committed=sum(o['complete_cost']+o['price'] for o in result['orders'] if o['qualified_time']==moment and o['customer_id'] in earlier_customers)
        if set(cash)!={'snapshot','operating_envelope','channel_reserve','capacity_reserve','prior_order_commitments'} or cash['operating_envelope']!=operating or cash['channel_reserve']!=channel or cash['capacity_reserve']!=capacity or cash['prior_order_commitments']!=committed:
            raise ValueError('STRATEGIC_CASH_DEDUCTIONS_NOT_RECONSTRUCTED')
        public=problem['public'];service=decision['service_id'];human=cfg['human_comparator'][service]
        anchor=int((human['hours']*human['loaded_usd_hour']+2)*1_000_000)
        already_onboarded=any(o['customer_id']==decision['customer_id'] and o['qualified_time']<moment for o in result['orders'])
        base=cfg['production_cost']+cfg['supplier_unit_cost']+cfg['support_cost']+(0 if already_onboarded else cfg['onboarding_cost'])
        expected={'anchor':anchor,'public_rival_price':decision['public_rival_price'],'base_cost':base,
                  'payment_bps':cfg['payment_bps'],'payment_fixed':cfg['payment_fixed'],
                  'available':max(0,summary['available']-operating-channel-capacity-committed),
                  'reserve_buffer':1_000_000,'quote_cost':cfg['exposure_cost']+cfg['qualification_cost'],
                  'native_state_digest':state_digest,'profit_tax_bps':cfg['profit_tax_bps']}
        if public!=expected:raise ValueError('STRATEGIC_INPUT_NOT_PUBLIC_OPERATING_OBSERVATION')
        job=jobs.get(problem['job_id'])
        if not job or job['service_id']!=service or not job['accepted']:raise ValueError('STRATEGIC_JOB_NOT_ADMITTED')
        artifact=read_bound(root,job['artifact'],job['artifact_sha256']);offer=problem['offer']
        template=next(o for o in offer_catalog() if o['service_id']==service and o['method']==artifact['method'])
        if any(offer.get(k)!=v for k,v in template.items() if k not in {'price_microUSD','provenance'}):
            raise ValueError('STRATEGIC_OFFER_CONTRACT_CHANGED')
        memory=problem['memory']
        if memory is not None:
            positions={(e.get('order_id'),e['kind']):i for i,e in enumerate(result['events']) if e.get('order_id')}
            planning_positions=[i for i,e in enumerate(result['events']) if e['kind']=='BUSINESS_DECISION' and e['time']==moment]
            if len(planning_positions)!=1:raise ValueError('UNIQUE_SEQUENTIAL_PLANNING_EVENT_REQUIRED')
            current_position=planning_positions[0]
            prior=[o for o in result['orders'] if o['production_time']<=moment and positions.get((o['id'],'PRODUCTION'),len(result['events']))<current_position and o.get('method_execution',{}).get('mode')=='critic_retain' and o['method_execution'].get('memory')==memory]
            if not prior:raise ValueError('STRATEGIC_MEMORY_HAS_NO_PRIOR_ACQUISITION')
        rederive(selection)
        selected=selection['offer']
        if selected is None:
            no_bid+=1
            if decision['kind']!='outside_choice' or decision['price'] is not None:raise ValueError('NO_BID_BECAME_OFFER')
        else:
            if decision['kind']!='offer' or decision['price']!=selected['price_microUSD']:raise ValueError('SELECTED_STRATEGIC_PRICE_NOT_USED')
            if decision['chosen']:
                order=next(o for o in result['orders'] if o['customer_id']==decision['customer_id'] and o['qualified_time']==moment)
                if order['offer']!=selected or order.get('method_plan')!=selection['method_plan']:raise ValueError('SELECTED_METHOD_NOT_OPERATED')
    return {'strategic_decisions_rederived':count,'strategic_no_bids_rederived':no_bid,
            'strategic_scope':'FINITE_PUBLIC_BELIEF_PRICE_METHOD_CHOICE; ACTUAL_MARKET_UNCHANGED_AND_MAY_BE_MISSPECIFIED'}
