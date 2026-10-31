"""Independent reconstruction of main-ledger strategic inputs and selected effects."""
import copy
from commercial.ledger import digest,read_bound
from adaptive_enterprise.account import action_prefix_digests
from adaptive_enterprise.strategies import offer_catalog
from .strategic_commerce import rederive_actions,selected_delivery
from .joint_planning import investment_option

def audit_decisions(root,manifest,result,lifecycle):
    cfg=result['config']
    if 'strategic_policy' not in cfg:
        if result.get('joint_actions'):raise ValueError('UNAUTHORIZED_JOINT_PLANNING')
        return {}
    actions=result.get('joint_actions');tape=result['owned_account']['ledger'];prefixes=action_prefix_digests(tape['actions'])
    if not isinstance(actions,dict) or len(actions)!=cfg['horizon_days']:raise ValueError('COMPLETE_JOINT_PLANNING_CALENDAR_REQUIRED')
    jobs={j['id']:j for j in manifest['jobs']};artifacts={j['id']:read_bound(root,j['artifact'],j['artifact_sha256']) for j in manifest['jobs']}
    events={e['time']:(i,e) for i,e in enumerate(result['events']) if e['kind']=='BUSINESS_DECISION'}
    states=0;quotes=0;no_bids=0;selected_investments=set()
    if 'sequence' in cfg['strategic_allocation_policy'] and 'channel_menu_policy' in cfg:
        from .channels import ChannelBook
        sequence_book=ChannelBook(result['seed'],cfg['channels'])
    for moment in range(0,cfg['horizon_days']*24,24):
        wrappers=[w for w in actions.values() if w['time']==moment]
        if len(wrappers)!=1:raise ValueError('UNIQUE_JOINT_PLANNING_DAY_REQUIRED')
        if 'sequence' in cfg['strategic_allocation_policy'] and 'channel_menu_policy' in cfg:
            for investment in result['investments']:
                if investment['kind']=='acquisition' and investment['purchased_time']==moment-24:
                    sequence_book.purchase(investment['contract_receipt']['contract_id'],(moment-24)//24,investment['plan_id'])
            sequence_book.expose(moment//24,result['buyers'])
        wrapper=wrappers[0];record=wrapper['allocation'];key=digest(record);day=moment//24
        if wrapper['id']!=key or actions.get(key)!=wrapper:raise ValueError('JOINT_ALLOCATION_ID_CHANGED')
        snapshot=record['observation'];charges=[a for a in tape['actions'] if a['op']=='cost' and a['args'].get('id')=='maintenance-'+str(day)]
        if len(charges)!=1 or charges[0]['day']!=moment or charges[0]['args'].get('amount')!=cfg['maintenance_daily']:raise ValueError('NATIVE_PREPAID_PLANNING_REQUIRED')
        charge=charges[0];seq=charge['seq']+1;summary=charge['after'];state_digest=digest({'config':tape['config'],'actions_sha256':prefixes[seq],'summary':summary})
        if snapshot['sequence']!=seq or snapshot['summary']!=summary or snapshot['actions_sha256']!=prefixes[seq] or snapshot['state_digest']!=state_digest:raise ValueError('JOINT_CASH_NOT_CURRENT_NATIVE_PREFIX')
        candidates=lifecycle['daily_candidate_ids_recomputed'][moment];buyers=lifecycle['daily_public_buyers'][moment]
        operating=cfg['exposure_cost']*lifecycle['daily_outreach_units_recomputed'][moment]+cfg['qualification_cost']*len(candidates)
        if wrapper['operating_envelope']!=operating or wrapper['candidate_ids']!=candidates:raise ValueError('JOINT_OPERATING_RESERVE_CHANGED')
        from .verify import _private_draw
        needs=[ident for ident in candidates if _private_draw(result['seed'],[day,ident],'need')<cfg['arrival_bps']/10000]
        if wrapper['observed_need_ids']!=needs:raise ValueError('CURRENT_NEED_OBSERVATION_CHANGED')
        # Only evaluator uses the source seed here; the selector receives observed current needs, not future draws.
        used={o['job_id'] for o in result['orders'] if o['qualified_time']<moment};expected_deliveries=[]
        for ident in needs:
            if len(expected_deliveries)>=cfg['strategic_allocation_policy']['max_customers']:break
            service=('reconciliation','kpi_variance','evidence_matrix')[buyers[ident]['service_index']%3]
            available=[j for j in jobs.values() if j['id'] not in used and j['accepted'] and j['service_id']==service and artifacts[j['id']]['outcome_scope']=='complete_outcome']
            if not available:continue
            job=min(available,key=lambda j:j['id']);used.add(job['id']);expected_deliveries.append((ident,job))
        if [(d['customer_id'],d['selection']['problem']['job_id']) for d in record['deliveries']]!=[(ident,j['id']) for ident,j in expected_deliveries]:raise ValueError('DECLARED_FINITE_SHORTLIST_CHANGED')
        risk=copy.deepcopy(cfg['strategic_allocation_policy']['risk']);risk['authorized_allocation']=min(risk['authorized_allocation'],max(0,summary['available']-operating))
        if record['riskpolicy']!=risk or record['earned_deduction']!=operating or record['allow_seed'] is not True:raise ValueError('JOINT_TOTAL_OR_EARNED_RESERVE_CHANGED')
        previous_investments=[i for i in result['investments'] if i['purchased_time']<moment]
        usable=[i for i in previous_investments if i['kind']=='capacity' and i['activation_time']<=moment and moment+cfg['production_hours']<i['expiry_time']]
        slots=min(cfg['maximum_slots'],cfg['initial_slots']+len(usable))
        if cfg['supplier_outage_start_day']<=day<cfg['supplier_outage_start_day']+cfg['supplier_outage_days']:slots=0
        if record['max_delivery_slots']!=slots:raise ValueError('CURRENT_DELIVERY_CAPACITY_CHANGED')
        # Reconstruct disclosed investment hypotheses, not their unrealized future returns.
        margins=[o['price']-o['complete_cost'] for o in result['orders'] if o['outcome']=='SETTLED' and o['collection_time']<=moment]
        profitable=bool(margins and sum(margins)>0);remaining=cfg['horizon_days']-day;pilot=cfg['channels']['pilot'];invoice=pilot['price_microUSD']+pilot['support_microUSD']
        failed={e['source_plan_id'] for e in result['channels']['events'] if e['day']<=day and e['kind']=='CHANNEL_ACTIVATION_FAILED'}
        live_channels=[i for i in previous_investments if i['kind']=='acquisition' and i['expiry_time']>moment and i['plan_id'] not in failed]
        owned=set(sorted(buyers)[:4]);contacts=result['channels']['contacts']
        reachable=sum(ident not in owned and (not b['onboarded'] or not b['active']) and sum(c['day']<=day for c in contacts.get(ident,[]))<pilot.get('max_contacts_per_customer',3) for ident,b in buyers.items())
        expected_investments=[]
        if 'channel_menu_policy' in cfg:
            from .channel_menu import menu_options
            dated_contacts={ident:[c for c in rows if c['day']<=day] for ident,rows in contacts.items()}
            live=[{'contract_id':i['contract_receipt']['contract_id'],'activation_day':i['activation_time']//24,'expiry_day':i['expiry_time']//24} for i in live_channels]
            expected_investments.extend(menu_options(cfg,result['arm'],day,buyers,dated_contacts,live,margins,slots,risk['scenarios']))
        elif result['arm']!='baseline' and profitable and reachable>0 and remaining>pilot['lead_days']+7 and not live_channels:
            forecast=sum(margins)/len(margins)*min(reachable,4)*.4*(pilot['activation_reliability_bps']*pilot['realization_bps']/10000**2)
            if forecast>invoice:expected_investments.append(investment_option('channel-'+str(day),'acquisition',invoice,int(forecast-invoice),risk['scenarios'],day,pilot))
        lost=sum(d.get('kind')=='capacity_decline' and day-3<=d['time']//24<day for d in result['decisions'])
        live_capacity=sum(i['kind']=='capacity' and moment<i['expiry_time'] for i in previous_investments)
        if result['arm'] in {'growth','competitive_growth'} and profitable and lost>=2 and slots<cfg['maximum_slots'] and live_capacity<cfg['maximum_slots']-cfg['initial_slots'] and remaining>7:
            forecast=sum(margins)/len(margins)*min(remaining,5)*.5
            if forecast>cfg['capacity_price']:
                contract={'price':cfg['capacity_price'],'lead_hours':cfg['capacity_lead_hours'],'duration_hours':cfg['capacity_duration_hours']}
                expected_investments.append(investment_option('capacity-'+str(day),'capacity',cfg['capacity_price'],int(forecast-cfg['capacity_price']),risk['scenarios'],day,contract))
        if 'sequence' in cfg['strategic_allocation_policy']:
            from .sequence_planning import sequence_options
            expected_investments=sequence_options(cfg,moment,snapshot,operating,
                {ident:{'job':job,'artifact':artifacts[ident]} for ident,job in jobs.items()},
                used,previous_investments,buyers,contacts,failed,risk['scenarios'],
                sum(max((r['required_current_cash'] for r in d['selection']['candidates']),default=0) for d in record['deliveries']),
                channel_state=sequence_book.export() if 'channel_menu_policy' in cfg else None)
        if record['investments']!=expected_investments:raise ValueError('INVESTMENT_HYPOTHESIS_NOT_FROM_PUBLIC_HISTORY')
        for delivery,(ident,job) in zip(record['deliveries'],expected_deliveries):
            selection=delivery['selection'];problem=selection['problem'];offer=problem['offer'];service=job['service_id'];human=cfg['human_comparator'][service];anchor=int((human['hours']*human['loaded_usd_hour']+2)*1_000_000)
            if problem['policy']!=cfg['strategic_policy'] or problem['method_policy']!=cfg.get('mechanism_policy'):raise ValueError('STRATEGIC_POLICY_CHANGED')
            onboard=0 if buyers[ident]['onboarded'] else cfg['onboarding_cost']
            template=next(o for o in offer_catalog() if o['service_id']==service and o['method']==artifacts[job['id']]['method'])
            if any(offer.get(k)!=v for k,v in template.items() if k not in {'price_microUSD','provenance'}):raise ValueError('ADMITTED_OFFER_CONTRACT_CHANGED')
            rival_bps=cfg['price_pressure_bps']
            for update_day in range(7,day+1,7):
                if update_day*24>=moment:break
                visible=[d for d in result['decisions'] if d.get('kind')=='offer' and d['time']<=update_day*24-24][-20:]
                if visible:rival_bps=max(5000,min(10500,rival_bps+(200 if sum(d['buyer_choice']=='rival' for d in visible)/len(visible)>.6 else -200)))
            expected={'anchor':anchor,'public_rival_price':int(anchor*rival_bps/10000),'base_cost':cfg['production_cost']+cfg['supplier_unit_cost']+cfg['support_cost']+onboard+cfg.get('prospective_policy',{}).get('premium_microUSD',0),'payment_bps':cfg['payment_bps'],'payment_fixed':cfg['payment_fixed'],'available':max(0,summary['available']-operating),'reserve_buffer':1_000_000,'quote_cost':cfg['exposure_cost']+cfg['qualification_cost'],'native_state_digest':state_digest,'profit_tax_bps':cfg['profit_tax_bps']}
            if problem['public']!=expected or delivery['onboarding']!=onboard:raise ValueError('STRATEGIC_INPUT_NOT_PUBLIC_CURRENT_FACTS')
            memory=problem['memory']
            if memory is not None:
                positions={(e.get('order_id'),e['kind']):i for i,e in enumerate(result['events']) if e.get('order_id')}
                prior=[o for o in result['orders'] if o['production_time']<=moment and positions.get((o['id'],'PRODUCTION'),len(result['events']))<events[moment][0] and o.get('method_execution',{}).get('mode')=='critic_retain' and o['method_execution'].get('memory')==memory]
                if not prior:raise ValueError('MEMORY_NOT_ACQUIRED_BEFORE_PLANNING')
        rederive_actions(record);states+=record['decision']['states_evaluated']
        selected={o['execution']['customer_id']:o for o in record['decision']['selected_options'] if o['kind']=='delivery'}
        investments={o['id'] for o in record['decision']['selected_options'] if o['kind']!='delivery'}
        if 'sequence' in cfg['strategic_allocation_policy']:
            picked=[o for o in record['decision']['selected_options'] if 'first_investment' in o['execution']]
            if len(picked)>1:raise ValueError('ONE_NATIVE_SEQUENCE_FIRST_ACTION_REQUIRED')
            investments=set()
            for option in picked:
                ident=option['id'] if 'channel_menu_policy' in cfg and option['execution']['first_investment']=='acquisition' else ('channel-' if option['execution']['first_investment']=='acquisition' else 'capacity-')+str(day)
                native=next((i for i in result['investments'] if i['id']==ident),None)
                expected_net=sum(risk['scenarios'][k]*(option['future_net_cash'][k]-option['upfront_cost']) for k in risk['scenarios'])//10000
                if native is None or native['cost']!=option['upfront_cost'] or native['predicted_net']!=expected_net:raise ValueError('SEQUENCE_FIRST_NATIVE_INVOICE_CHANGED')
                investments.add(ident)
        selected_investments|=investments
        if events[moment][1]['channel_selected']!=(any(o['kind']=='acquisition' for o in record['decision']['selected_options']) if 'channel_menu_policy' in cfg else ('channel-'+str(day) in investments)) or events[moment][1]['capacity_selected']!=('capacity-'+str(day) in investments):raise ValueError('SELECTED_INVESTMENT_FLAGS_CHANGED')
        choices=[d for d in result['decisions'] if d.get('kind') in {'offer','outside_choice'} and d['time']==moment]
        if [d['customer_id'] for d in choices]!=needs:raise ValueError('EVERY_OBSERVED_NEED_REQUIRES_ONE_JOINT_DECISION')
        for choice in choices:
            if choice.get('joint_allocation_sha256')!=key:raise ValueError('JOINT_DECISION_REFERENCE_MISSING')
            option=selected.get(choice['customer_id']);quotes+=1
            if option is None:
                no_bids+=1
                if choice['kind']!='outside_choice' or choice.get('joint_option_id') is not None:raise ValueError('UNSELECTED_CUSTOMER_WAS_QUOTED')
                continue
            contract=selected_delivery(record,option['id'])
            if choice['kind']!='offer' or choice.get('joint_option_id')!=option['id'] or choice['price']!=contract['price']:raise ValueError('JOINT_SELECTED_QUOTE_NOT_USED')
            if choice['chosen']:
                order=next(o for o in result['orders'] if o['customer_id']==choice['customer_id'] and o['qualified_time']==moment)
                if order['offer']!=contract['offer'] or order.get('method_plan')!=contract['method_plan'] or order['complete_cost']!=contract['complete_cost'] or order.get('joint_option_id')!=option['id']:raise ValueError('JOINT_SELECTED_METHOD_NOT_EXECUTED')
    if {i['id'] for i in result['investments']}!=selected_investments:raise ValueError('JOINT_SELECTED_INVESTMENTS_NOT_NATIVE_EXECUTED')
    return {'joint_plans_rederived':len(actions),'joint_states_evaluated':states,'strategic_quotes_and_no_bids_rederived':quotes,'strategic_no_bids_rederived':no_bids,'joint_optimality_scope':'Exact declared finite shortlist under public conditional-mean forecasts; not a global or long-horizon optimum.'}
