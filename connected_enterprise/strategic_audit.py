"""Independent reconstruction of main-ledger strategic inputs and selected effects."""
import copy
from commercial.ledger import digest,read_bound
from adaptive_enterprise.account import action_prefix_digests
from adaptive_enterprise.strategies import offer_catalog
from .strategic_commerce import rederive_actions,selected_delivery
from .joint_planning import investment_option

def check_capacity_effect(option, row, cfg, moment, risk, game_decision=None):
    execution=option['execution'];units=execution['purchased_units']
    expected={'id':option['id'],'kind':'capacity','capacity_units':units,
        'cost':option['upfront_cost'],'purchased_time':moment,
        'activation_time':moment+cfg['capacity_lead_hours'],
        'expiry_time':moment+cfg['capacity_lead_hours']+cfg['capacity_duration_hours'],
        'predicted_net':sum(risk['scenarios'][k]*option['future_net_cash'][k] for k in risk['scenarios'])//10000-option['upfront_cost']}
    if game_decision is not None:
        from adaptive_enterprise.strategic_game import investment_expected_net
        expected['predicted_net']=investment_expected_net(game_decision,option['id'])
    if row is None or any(row.get(k)!=v for k,v in expected.items()) or option['upfront_cost']!=units*cfg['capacity_price']:
        raise ValueError('SELECTED_CAPACITY_QUANTITY_NOT_NATIVE_EXECUTED')


def _recourse_choices(record,wrapper,choices,needs,cfg):
    from .refusal_recourse import recourse
    trace=wrapper.get('refusal_recourse')
    if not isinstance(trace,dict) or set(trace)!={'policy','attempts','rounds'} or trace['policy']!=cfg['refusal_recourse_policy']:raise ValueError('EXACT_REFUSAL_RECOURSE_TRACE_REQUIRED')
    remaining=list(needs);active=record;attempts=[];rounds=[];bound={}
    for choice in choices:
        selected={o['execution']['customer_id']:o for o in active['decision']['selected_options'] if o['kind']=='delivery'}
        expected=next((ident for ident in remaining if ident in selected),remaining[0] if remaining else None)
        ident=choice['customer_id']
        if ident!=expected or choice.get('joint_recourse_round')!=len(rounds):raise ValueError('RECOURSE_READS_UNOBSERVED_OR_DUPLICATE_RESPONSE')
        remaining.remove(ident);bound[ident]=(active,selected.get(ident),len(rounds))
        if choice['kind']=='offer':
            option=selected.get(ident)
            if option is None or choice.get('joint_option_id')!=option['id']:raise ValueError('RECOURSE_QUOTE_NOT_CURRENT_SELECTED_ACTION')
            attempts.append({'customer_id':ident,'option_id':option['id'],'accepted':choice['buyer_choice']=='us'})
            if choice['buyer_choice']!='us':
                active=recourse(record,attempts)
                rounds.append({'after_attempts':len(attempts),'allocation':active})
    if remaining or trace['attempts']!=attempts or trace['rounds']!=rounds:raise ValueError('REFUSAL_RECOURSE_NOT_REDERIVED')
    return bound


def audit_decisions(root,manifest,result,lifecycle):
    cfg=result['config']
    if 'strategic_policy' not in cfg:
        if result.get('joint_actions'):raise ValueError('UNAUTHORIZED_JOINT_PLANNING')
        return {}
    actions=result.get('joint_actions');tape=result['owned_account']['ledger'];prefixes=action_prefix_digests(tape['actions'])
    if not isinstance(actions,dict) or len(actions)!=cfg['horizon_days']:raise ValueError('COMPLETE_JOINT_PLANNING_CALENDAR_REQUIRED')
    jobs={j['id']:j for j in manifest['jobs']};artifacts={j['id']:read_bound(root,j['artifact'],j['artifact_sha256']) for j in manifest['jobs']}
    events={e['time']:(i,e) for i,e in enumerate(result['events']) if e['kind']=='BUSINESS_DECISION'}
    states=0;quotes=0;no_bids=0;selected_investments=set();startup_evaluation_required=False
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
        charge=charges[0]
        if 'startup_acquisition_policy' in cfg and moment==0:
            from .startup_acquisition048 import preflight as startup_preflight
            from .engine import _offer_menu
            needs_evaluation=startup_preflight(cfg,lifecycle['daily_public_buyers'][0],{ident:{'job':job,'artifact':artifacts[ident]} for ident,job in jobs.items()},_offer_menu)
            startup_evaluation_required=bool(needs_evaluation)
            paid=[a for a in tape['actions'] if a['op']=='cost' and a['args'].get('id')=='startup-acquisition-evaluation']
            fee=cfg['startup_acquisition_policy']['planning_cost_microUSD']
            if not needs_evaluation:
                if paid:raise ValueError('STARTUP_EMPTY_OR_INCONSISTENT_REACH_CANNOT_BE_CHARGED')
            else:
                if len(paid)!=1 or paid[0]['day']!=0 or paid[0]['seq']!=charge['seq']+1 or paid[0]['args']['amount']!=fee or paid[0]['before']['available']<fee or paid[0]['before'].get('investmentStopped') or paid[0]['before']['cash']-paid[0]['after']['cash']!=fee or paid[0]['before']['payables']!=paid[0]['after']['payables']:raise ValueError('STARTUP_PLANNING_NOT_CASH_PREPAID')
                charge=paid[0]
        selective=cfg.get('refusal_recourse_policy',{}).get('schema')=='connected-selective-refusal-recourse/v2'
        selective_purchase=True
        if selective:
            from .refusal_recourse import selective_decision
            expected_selective=selective_decision(record,cfg['refusal_recourse_policy'],wrapper['candidate_ids'])
            if wrapper.get('selective_recourse_decision')!=expected_selective:raise ValueError('SELECTIVE_RECOURSE_DECISION_NOT_PUBLIC_REDERIVED')
            selective_purchase=expected_selective['purchase']
            evaluation=[a for a in tape['actions'] if a['op']=='cost' and a['args'].get('id')=='recourse-evaluation-'+str(day)]
            fee=cfg['refusal_recourse_policy']['daily_evaluation_cost']
            if len(evaluation)!=1 or evaluation[0]['day']!=moment or evaluation[0]['seq']!=charge['seq']+1 or evaluation[0]['args']!={'id':'recourse-evaluation-'+str(day),'amount':fee}:raise ValueError('SELECTIVE_EVALUATION_NOT_PREPAID')
            before=evaluation[0]['before'];after=evaluation[0]['after']
            if before['available']<fee or before.get('investmentStopped') or before['cash']-after['cash']!=fee or before['payables']!=after['payables']:raise ValueError('SELECTIVE_EVALUATION_NOT_CASH_FUNDED')
            charge=evaluation[0]
            if not selective_purchase and any(a['op']=='cost' and a['args'].get('id')=='recourse-planning-'+str(day) for a in tape['actions']):raise ValueError('SELECTIVE_HOLD_CHARGED_ALLOWANCE')
        elif 'selective_recourse_decision' in wrapper:raise ValueError('UNREGISTERED_SELECTIVE_RECOURSE')
        if 'refusal_recourse_policy' in cfg and selective_purchase:
            paid=[a for a in tape['actions'] if a['op']=='cost' and a['args'].get('id')=='recourse-planning-'+str(day)]
            if len(paid)!=1 or paid[0]['day']!=moment or paid[0]['seq']!=charge['seq']+1 or paid[0]['args'].get('amount')!=cfg['refusal_recourse_policy']['daily_planning_cost']:raise ValueError('NATIVE_PREPAID_REFUSAL_RECOURSE_REQUIRED')
            charge=paid[0]
            fee=cfg['refusal_recourse_policy']['daily_planning_cost'];before=charge['before'];after=charge['after']
            if before['available']<fee or before.get('investmentStopped') or before['cash']-after['cash']!=fee or before['payables']!=after['payables']:raise ValueError('RECOURSE_PLANNING_NOT_CASH_PREPAID')
        seq=charge['seq']+1;summary=charge['after'];state_digest=digest({'config':tape['config'],'actions_sha256':prefixes[seq],'summary':summary})
        if snapshot['sequence']!=seq or snapshot['summary']!=summary or snapshot['actions_sha256']!=prefixes[seq] or snapshot['state_digest']!=state_digest:raise ValueError('JOINT_CASH_NOT_CURRENT_NATIVE_PREFIX')
        candidates=lifecycle['daily_candidate_ids_recomputed'][moment];buyers=lifecycle['daily_public_buyers'][moment]
        operating=cfg['exposure_cost']*lifecycle['daily_outreach_units_recomputed'][moment]+cfg['qualification_cost']*len(candidates)*(4 if 'complete_offer_policy' in cfg else 1)
        if selective and not selective_purchase:operating+=cfg['refusal_recourse_policy']['daily_planning_cost']
        if wrapper['operating_envelope']!=operating or wrapper['candidate_ids']!=candidates:raise ValueError('JOINT_OPERATING_RESERVE_CHANGED')
        from .verify import _private_draw
        needs=[ident for ident in candidates if _private_draw(result['seed'],[day,ident],'need')<cfg['arrival_bps']/10000]
        if wrapper['observed_need_ids']!=needs:raise ValueError('CURRENT_NEED_OBSERVATION_CHANGED')
        # Only evaluator uses the source seed here; the selector receives observed current needs, not future draws.
        used={o['job_id'] for o in result['orders'] if o['qualified_time']<moment};expected_deliveries=[]
        considered=0
        for ident in needs:
            if considered>=cfg['strategic_allocation_policy']['max_customers']:break
            services=[('reconciliation','kpi_variance','evidence_matrix')[buyers[ident]['service_index']%3]]
            if 'complete_offer_policy' in cfg:
                from .complete_offer_market import request_profile
                profile=request_profile(cfg['complete_offer_policy'],ident)
                services=profile['services'] if cfg['complete_offer_policy']['selection']=='menu' else [service for service in services if service in profile['services']]
            menu=[]
            consumed={key for jobid in used for key in jobs[jobid]['work_keys']}
            for service in services:
                available=[j for j in jobs.values() if j['id'] not in used and j['accepted'] and j['service_id']==service and artifacts[j['id']]['outcome_scope']=='complete_outcome' and ('complete_offer_policy' not in cfg or (j['id'] in cfg['complete_offer_policy']['requested_jobs'][ident] and not consumed.intersection(j['work_keys'])))]
                if available:menu.append(min(available,key=lambda j:j['id']))
            if menu:considered+=1
            for job in menu:used.add(job['id']);expected_deliveries.append((ident,job))
        if [(d['customer_id'],d['selection']['problem']['job_id']) for d in record['deliveries']]!=[(ident,j['id']) for ident,j in expected_deliveries]:raise ValueError('DECLARED_FINITE_SHORTLIST_CHANGED')
        if 'complete_offer_policy' in cfg:
            fixed=cfg['exposure_cost']*lifecycle['daily_outreach_units_recomputed'][moment]+cfg['qualification_cost']*len(expected_deliveries)
            expected_evaluation={'fixed_evaluation_cost':fixed,'hold_net_after_evaluation':-fixed,
                'selected_expected_net_after_evaluation':record['decision']['expected_net']-fixed,
                'scope':'Conditional marginal allocation after fixed offer evaluation. Entire evaluation bill is incurred for selected and no-bid alternatives and separately charged natively; risk score is incremental, not whole-business risk or profit.'}
            if wrapper.get('evaluation_cost')!=expected_evaluation:raise ValueError('COMMON_OFFER_EVALUATION_COST_CHANGED')
        elif 'evaluation_cost' in wrapper:raise ValueError('UNREGISTERED_COMMON_EVALUATION_RECEIPT')
        risk=copy.deepcopy(cfg['strategic_allocation_policy']['risk']);risk['authorized_allocation']=min(risk['authorized_allocation'],max(0,summary['available']-operating))
        if record['riskpolicy']!=risk or record['earned_deduction']!=operating or record['allow_seed'] is not True:raise ValueError('JOINT_TOTAL_OR_EARNED_RESERVE_CHANGED')
        if record.get('strategic_game')!=cfg['strategic_allocation_policy'].get('strategic_game'):raise ValueError('UNREGISTERED_STRATEGIC_RESPONSE_GAME')
        from .joint_planning import category_upfront_caps
        if record.get('category_upfront_caps')!=category_upfront_caps(cfg['strategic_allocation_policy'],snapshot,operating):raise ValueError('CATEGORY_BUDGET_CAPS_NOT_FROM_CURRENT_EARNINGS')
        previous_investments=[i for i in result['investments'] if i['purchased_time']<moment]
        usable=[i for i in previous_investments if i['kind']=='capacity' and i['activation_time']<=moment and moment+cfg['production_hours']<i['expiry_time']]
        slots=min(cfg['maximum_slots'],cfg['initial_slots']+sum(i.get('capacity_units',1) for i in usable))
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
        if 'capacity_menu' not in cfg['strategic_allocation_policy'] and result['arm'] in {'growth','competitive_growth'} and profitable and lost>=2 and slots<cfg['maximum_slots'] and live_capacity<cfg['maximum_slots']-cfg['initial_slots'] and remaining>7:
            forecast=sum(margins)/len(margins)*min(remaining,5)*.5
            if forecast>cfg['capacity_price']:
                contract={'price':cfg['capacity_price'],'lead_hours':cfg['capacity_lead_hours'],'duration_hours':cfg['capacity_duration_hours']}
                expected_investments.append(investment_option('capacity-'+str(day),'capacity',cfg['capacity_price'],int(forecast-cfg['capacity_price']),risk['scenarios'],day,contract))
        if 'sequence' in cfg['strategic_allocation_policy']:
            from .sequence_planning import sequence_options
            sequence_buyers=buyers
            if cfg['strategic_allocation_policy']['sequence'].get('composition')=='complete-offer-quantity-v1':
                sequence_buyers=copy.deepcopy(buyers)
                refund_times={a['args']['id']:a['day'] for a in tape['actions'] if a['op']=='event' and a['args']['action']=='refund'}
                for ident,buyer in sequence_buyers.items():
                    outside=sum(d.get('outside_spend',0) for d in result['decisions'] if d.get('customer_id')==ident and d['time']<moment)
                    committed=sum(o['price'] for o in result['orders'] if o['customer_id']==ident and o['qualified_time']<moment and (o['id'] not in refund_times or refund_times[o['id']]>moment))
                    buyer['observed_spend']=outside+committed
            expected_investments=sequence_options(cfg,moment,snapshot,operating,
                {ident:{'job':job,'artifact':artifacts[ident]} for ident,job in jobs.items()},
                used,previous_investments,sequence_buyers,contacts,failed,risk['scenarios'],
                sum(max((r['required_current_cash'] for r in d['selection']['candidates']),default=0) for d in record['deliveries']),
                channel_state=sequence_book.export() if 'channel_menu_policy' in cfg else None)
        if 'startup_acquisition_policy' in cfg:
            from .startup_acquisition048 import options as startup_options
            from .engine import _offer_menu
            expected_investments.extend(startup_options(cfg,result['arm'],moment,snapshot,operating,{ident:{'job':job,'artifact':artifacts[ident]} for ident,job in jobs.items()},used,buyers,risk['scenarios'],_offer_menu,prior_orders=any(o['qualified_time']<moment for o in result['orders']),prior_investments=bool(previous_investments)))
        if 'capacity_menu' in cfg['strategic_allocation_policy']:
            from .joint_planning import capacity_recourse
            expected_capacity=capacity_recourse(cfg,moment,snapshot,operating,record['deliveries'],previous_investments,slots,risk)
            if wrapper.get('capacity_recourse')!=expected_capacity:raise ValueError('CAPACITY_RECOURSE_INPUTS_OR_RESULTS_CHANGED')
            expected_investments.extend(expected_capacity['options'])
        elif 'capacity_recourse' in wrapper:raise ValueError('UNREGISTERED_CAPACITY_RECOURSE')
        if record['investments']!=expected_investments:raise ValueError('INVESTMENT_HYPOTHESIS_NOT_FROM_PUBLIC_HISTORY')
        for delivery,(ident,job) in zip(record['deliveries'],expected_deliveries):
            selection=delivery['selection'];problem=selection['problem'];offer=problem['offer'];service=job['service_id']
            if 'complete_offer_policy' in cfg:
                from .complete_offer_market import request_profile,market_context
                anchor=max(request_profile(cfg['complete_offer_policy'],ident)['price_grids'][service])
            else:
                human=cfg['human_comparator'][service];anchor=int((human['hours']*human['loaded_usd_hour']+2)*1_000_000)
            if problem['policy']!=cfg['strategic_policy'] or problem['method_policy']!=cfg.get('mechanism_policy'):raise ValueError('STRATEGIC_POLICY_CHANGED')
            onboard=0 if buyers[ident]['onboarded'] else cfg['onboarding_cost']
            template=next(o for o in offer_catalog(include_packet='complete_offer_policy' in cfg) if o['service_id']==service and o['method']==artifacts[job['id']]['method'])
            if any(offer.get(k)!=v for k,v in template.items() if k not in {'price_microUSD','provenance'}):raise ValueError('ADMITTED_OFFER_CONTRACT_CHANGED')
            rival_bps=cfg['price_pressure_bps']
            for update_day in range(7,day+1,7):
                if update_day*24>=moment:break
                visible=[d for d in result['decisions'] if d.get('kind')=='offer' and d['time']<=update_day*24-24][-20:]
                if visible:rival_bps=max(5000,min(10500,rival_bps+(200 if sum(d['buyer_choice']=='rival' for d in visible)/len(visible)>.6 else -200)))
            expected={'anchor':anchor,'public_rival_price':int(anchor*rival_bps/10000),'base_cost':(offer['capacity_units'] if 'complete_offer_policy' in cfg else 1)*(cfg['production_cost']+cfg['supplier_unit_cost']+cfg['support_cost'])+onboard+cfg.get('prospective_policy',{}).get('premium_microUSD',0),'payment_bps':cfg['payment_bps'],'payment_fixed':cfg['payment_fixed'],'available':max(0,summary['available']-operating),'reserve_buffer':1_000_000,'quote_cost':0 if 'complete_offer_policy' in cfg else cfg['exposure_cost']+cfg['qualification_cost'],'native_state_digest':state_digest,'profit_tax_bps':cfg['profit_tax_bps']}
            if problem['public']!=expected or delivery['onboarding']!=onboard:raise ValueError('STRATEGIC_INPUT_NOT_PUBLIC_CURRENT_FACTS')
            if 'complete_offer_policy' in cfg:
                outside=sum(d.get('outside_spend',0) for d in result['decisions'] if d.get('customer_id')==ident and d['time']<moment)
                refunds={a['args']['id']:a['day'] for a in tape['actions'] if a['op']=='event' and a['args']['action']=='refund'}
                committed=sum(o['price'] for o in result['orders'] if o['customer_id']==ident and o['qualified_time']<moment and (o['id'] not in refunds or refunds[o['id']]>moment))
                if problem.get('market_context')!=market_context(cfg['complete_offer_policy'],ident,outside+committed):raise ValueError('COMPLETE_MARKET_FORECAST_READS_PRIVATE_STATE')
                if delivery.get('capacity_units')!=offer['capacity_units'] or delivery.get('work_keys')!=job['work_keys']:raise ValueError('COMPLETE_PRODUCTION_WORK_OR_UNITS_CHANGED')
            elif 'market_context' in problem:raise ValueError('UNAUTHORIZED_COMPLETE_MARKET')
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
            investments={o['id'] for o in record['decision']['selected_options'] if o['kind']!='delivery' and 'first_investment' not in o['execution']} if cfg['strategic_allocation_policy']['sequence'].get('composition')=='complete-offer-quantity-v1' else set()
            for option in picked:
                ident=option['id'] if 'purchased_units' in option['execution'] or 'channel_menu_policy' in cfg and option['execution']['first_investment']=='acquisition' else ('channel-' if option['execution']['first_investment']=='acquisition' else 'capacity-')+str(day)
                native=next((i for i in result['investments'] if i['id']==ident),None)
                expected_net=sum(risk['scenarios'][k]*(option['future_net_cash'][k]-option['upfront_cost']) for k in risk['scenarios'])//10000
                if 'strategic_game' in record:
                    from adaptive_enterprise.strategic_game import investment_expected_net
                    expected_net=investment_expected_net(record['decision'],option['id'])
                if native is None or native['cost']!=option['upfront_cost'] or native['predicted_net']!=expected_net:raise ValueError('SEQUENCE_FIRST_NATIVE_INVOICE_CHANGED')
                investments.add(ident)
        if 'capacity_menu' in cfg['strategic_allocation_policy']:
            for option in record['decision']['selected_options']:
                if option['kind']=='capacity':
                    row=next((i for i in result['investments'] if i['id']==option['id']),None)
                    check_capacity_effect(option,row,cfg,moment,risk,record['decision'] if 'strategic_game' in record else None)
        if 'strategic_game' in record:
            from adaptive_enterprise.strategic_game import investment_expected_net
            for option in record['decision']['selected_options']:
                if option['kind']=='delivery':continue
                ident=option['id']
                if 'first_investment' in option['execution'] and not ('channel_menu_policy' in cfg and option['execution']['first_investment']=='acquisition') and 'purchased_units' not in option['execution']:
                    ident=('channel-' if option['execution']['first_investment']=='acquisition' else 'capacity-')+str(day)
                native=next((i for i in result['investments'] if i['id']==ident),None)
                if native is None or native['cost']!=option['upfront_cost'] or native['predicted_net']!=investment_expected_net(record['decision'],option['id']):raise ValueError('NATIVE_INVESTMENT_NOT_CHOSEN_GAME_FORECAST')
        selected_investments|=investments
        if events[moment][1]['channel_selected']!=(any(o['kind']=='acquisition' for o in record['decision']['selected_options']) if 'channel_menu_policy' in cfg else ('channel-'+str(day) in investments)) or events[moment][1]['capacity_selected']!=(any(o['kind']=='capacity' for o in record['decision']['selected_options']) if 'capacity_menu' in cfg['strategic_allocation_policy'] else ('capacity-'+str(day) in investments)):raise ValueError('SELECTED_INVESTMENT_FLAGS_CHANGED')
        choices=[d for d in result['decisions'] if d.get('kind') in {'offer','outside_choice'} and d['time']==moment]
        recourse_bound=None
        if 'refusal_recourse_policy' in cfg and selective_purchase:
            recourse_bound=_recourse_choices(record,wrapper,choices,needs,cfg)
        else:
            if 'refusal_recourse' in wrapper or any('joint_recourse_round' in d for d in choices):raise ValueError('UNREGISTERED_REFUSAL_RECOURSE')
            if [d['customer_id'] for d in choices]!=needs:raise ValueError('EVERY_OBSERVED_NEED_REQUIRES_ONE_JOINT_DECISION')
        capacity_only_customers=set()
        if 'complete_offer_policy' in cfg:
            from .capacity_signal import capacity_declined_customers
            capacity_only_customers=capacity_declined_customers(record)
        for choice in choices:
            if choice.get('joint_allocation_sha256')!=key:raise ValueError('JOINT_DECISION_REFERENCE_MISSING')
            active_record=record
            if recourse_bound is not None:
                active_record,option,active_round=recourse_bound[choice['customer_id']]
                from .capacity_signal import capacity_declined_customers
                capacity_only_customers=capacity_declined_customers(active_record)
            else:option=selected.get(choice['customer_id'])
            quotes+=1
            if option is None:
                no_bids+=1
                if 'complete_offer_policy' in cfg:
                    reasons=[d['kind'] for d in result['decisions'] if d.get('customer_id')==choice['customer_id'] and d.get('time')==moment and d.get('kind') not in {'offer','outside_choice'}]
                    expected_reason='capacity_decline' if choice['customer_id'] in capacity_only_customers else 'joint_no_bid'
                    if reasons!=[expected_reason]:raise ValueError('CAPACITY_ONLY_OPPORTUNITY_NOT_REDERIVED')
                if choice['kind']!='outside_choice' or choice.get('joint_option_id') is not None:raise ValueError('UNSELECTED_CUSTOMER_WAS_QUOTED')
                continue
            contract=selected_delivery(active_record,option['id'])
            if choice['kind']!='offer' or choice.get('joint_option_id')!=option['id'] or choice['price']!=contract['price']:raise ValueError('JOINT_SELECTED_QUOTE_NOT_USED')
            if choice['chosen']:
                order=next(o for o in result['orders'] if o['customer_id']==choice['customer_id'] and o['qualified_time']==moment)
                if recourse_bound is not None and order.get('joint_recourse_round')!=active_round:raise ValueError('ORDER_RECOURSE_SELECTION_CHANGED')
                if order['offer']!=contract['offer'] or order.get('method_plan')!=contract['method_plan'] or order['complete_cost']!=contract['complete_cost'] or order.get('joint_option_id')!=option['id']:raise ValueError('JOINT_SELECTED_METHOD_NOT_EXECUTED')
    if {i['id'] for i in result['investments']}!=selected_investments:raise ValueError('JOINT_SELECTED_INVESTMENTS_NOT_NATIVE_EXECUTED')
    return {**({'startup_evaluation_required':startup_evaluation_required} if 'startup_acquisition_policy' in cfg else {}),'joint_plans_rederived':len(actions),'joint_states_evaluated':states,'strategic_quotes_and_no_bids_rederived':quotes,'strategic_no_bids_rederived':no_bids,'joint_optimality_scope':'Exact declared finite shortlist under public conditional-mean forecasts; not a global or long-horizon optimum.'}
