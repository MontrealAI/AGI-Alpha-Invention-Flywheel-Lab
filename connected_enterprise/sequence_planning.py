"""Opt-in source-bound channel/capacity sequences, with first-action execution only."""
import copy
from fractions import Fraction
from commercial.ledger import digest
from adaptive_enterprise.strategies import offer_catalog
from .strategic_commerce import select
from .sequence_window import compare_window


def sequence_options(cfg, moment, snapshot, operating, jobs, used, investments,
                     public_buyers, contacts, failed_channels, scenarios, current_delivery_reserve=0, channel_state=None):
    if cfg['strategic_allocation_policy']['sequence'].get('composition')=='complete-offer-quantity-v1':
        return _complete_menu_options(cfg,moment,snapshot,operating,jobs,used,investments,public_buyers,scenarios,current_delivery_reserve,channel_state)
    if 'channel_menu_policy' in cfg:
        return _menu_options(cfg,moment,snapshot,operating,jobs,used,investments,public_buyers,scenarios,current_delivery_reserve,channel_state)
    policy=cfg['strategic_allocation_policy']['sequence']
    day=moment//24;future=moment+24*policy['window_delay_days']
    pilot=cfg['channels']['pilot']
    live=[i for i in investments if i['kind']=='acquisition' and i['expiry_time']>moment and i['plan_id'] not in failed_channels]
    eligible=[i for i in live if i['activation_time']<=future<i['expiry_time']]
    probability=Fraction(0)
    if eligible:
        # First edition admits no stacked tranches. Pending activation uses the
        # contract probability; an already observed active tranche is certain.
        i=eligible[0]
        probability=Fraction(1) if i['activation_time']<=moment else Fraction(pilot['activation_reliability_bps'],10000)
    active_capacity=sum(i['kind']=='capacity' and i['activation_time']<=future and future+cfg['production_hours']<i['expiry_time'] for i in investments)
    slots=min(cfg['maximum_slots'],cfg['initial_slots']+active_capacity)
    outage=cfg['supplier_outage_start_day']<=future//24<cfg['supplier_outage_start_day']+cfg['supplier_outage_days']
    if outage:slots=0
    owned=set(sorted(public_buyers)[:pilot.get('owned_audience_count',4)])
    reachable=sum(ident not in owned and (not b['onboarded'] or not b['active']) and
                  sum(c['day']<=day for c in contacts.get(ident,[]))<pilot.get('max_contacts_per_customer',3)
                  for ident,b in public_buyers.items())
    # Prevent current shortlisted jobs from appearing again in a future forecast.
    available=[j for j in jobs.values() if j['job']['id'] not in used and j['job']['accepted'] and j['artifact'].get('outcome_scope')=='complete_outcome' and j['job']['service_id'] in cfg['human_comparator']]
    cash=copy.deepcopy(snapshot);cash['summary']['available']=max(0,cash['summary']['available']-operating-current_delivery_reserve)
    cash['summary']['unrestrictedEarned']=max(0,cash['summary']['unrestrictedEarned']-operating-current_delivery_reserve)
    profiles=[]
    for service in sorted({j['job']['service_id'] for j in available}):
        cohort=[j for j in available if j['job']['service_id']==service];entry=min(cohort,key=lambda j:j['job']['id'])
        human=cfg['human_comparator'][service];anchor=int((human['hours']*human['loaded_usd_hour']+2)*1_000_000)
        offer=copy.deepcopy(next(o for o in offer_catalog() if o['service_id']==service and o['method']==entry['artifact']['method']))
        public={'anchor':anchor,'public_rival_price':int(anchor*policy['future_rival_price_bps']/10000),
                'base_cost':sum(cfg[k] for k in ('production_cost','supplier_unit_cost','support_cost','onboarding_cost'))+cfg.get('prospective_policy',{}).get('premium_microUSD',0),
                'payment_bps':cfg['payment_bps'],'payment_fixed':cfg['payment_fixed'],'available':cash['summary']['available'],
                'reserve_buffer':1_000_000,'quote_cost':cfg['exposure_cost']+cfg['qualification_cost'],
                'native_state_digest':snapshot['state_digest'],'profit_tax_bps':cfg['profit_tax_bps']}
        future_policy=copy.deepcopy(cfg['strategic_policy'])
        future_policy['public_basis']+=' Future rival quote is the explicit authored sequence-policy hypothesis, not an observed future quote.'
        selection=select(future_policy,cfg.get('mechanism_policy'),entry['job']['id'],offer,None,public)
        forecast=compare_window(cfg,policy,selection,cash,now_hours=moment,future_existing_slots=slots,
                                unused_inventory=len(cohort),eligible_new_contacts=reachable,
                                existing_channel_probability=str(probability),allow_channel=not live and reachable>0,
                                allow_capacity=not outage and slots<cfg['maximum_slots'])
        profiles.append({'service':service,'forecast':forecast})
    options=[]
    for profile in profiles:
        for route in profile['forecast']['routes']:
            if not route['channel'] and not route['capacity'] or not route['current_cash_feasible']:continue
            net=route['incremental_net_microUSD'];cost=route['first_action_cost']
            if set(net)!=set(scenarios):raise ValueError('MATCHED_SEQUENCE_SCENARIOS_REQUIRED')
            channel=route['channel'];kind='acquisition' if channel else 'capacity'
            ident='sequence-'+profile['service']+'-'+('channel-then-capacity' if channel and route['capacity'] else kind)+'-'+str(day)
            options.append({'id':ident,'kind':kind,'upfront_cost':cost,
                'later_liabilities':dict.fromkeys(scenarios,route['contingent_later_capacity_cost']),
                'future_net_cash':{k:v+cost for k,v in net.items()},
                'benefit_ids':['shared-sequence-window-'+str(day)],'requires':[],
                'exclusive_group':'sequence-investment-'+str(day),'authorized':True,'evidence':digest(profile),
                'execution':{'funding':'EARNED','first_investment':kind,'forecast':profile,
                    'contingent_capacity':bool(channel and route['capacity']),
                    'forecast_scope':'Conservative prefunding after maximum commitment for every current shortlisted customer, not selected-basket optimum. One public hypothetical window; only first native invoice is selected. Contingent capacity and future delivery must replan and re-reserve. No future cash authority.'}})
    return options


def _menu_options(cfg,moment,snapshot,operating,jobs,used,investments,buyers,scenarios,delivery_reserve,channel_state):
    from .channel_menu import validate_policy
    from .sequence_channels import forecast_contract
    menu=validate_policy(cfg['channel_menu_policy'],cfg['channels'])
    policy=cfg['strategic_allocation_policy']['sequence'];future=moment+24*policy['window_delay_days']
    if channel_state is None:raise ValueError('OBSERVED_CHANNEL_BOOK_REQUIRED')
    slots=min(cfg['maximum_slots'],cfg['initial_slots']+sum(i['kind']=='capacity' and i['activation_time']<=future and future+cfg['production_hours']<i['expiry_time'] for i in investments))
    outage=cfg['supplier_outage_start_day']<=future//24<cfg['supplier_outage_start_day']+cfg['supplier_outage_days']
    if outage:slots=0
    cash=copy.deepcopy(snapshot)
    for k in ('available','unrestrictedEarned'):cash['summary'][k]=max(0,cash['summary'][k]-operating-delivery_reserve)
    available=[j for j in jobs.values() if j['job']['id'] not in used and j['job']['accepted'] and j['artifact'].get('outcome_scope')=='complete_outcome' and j['job']['service_id'] in cfg['human_comparator']]
    forecasts={ident:forecast_contract(cfg['channels'],channel_state,buyers,moment//24,future//24,ident,owned_contact_count=policy['owned_contact_count']) for ident in menu['contract_ids']}
    options=[];capacity_seen=set()
    for service in sorted({j['job']['service_id'] for j in available}):
        cohort=[j for j in available if j['job']['service_id']==service];entry=min(cohort,key=lambda j:j['job']['id'])
        human=cfg['human_comparator'][service];anchor=int((human['hours']*human['loaded_usd_hour']+2)*1_000_000)
        offer=copy.deepcopy(next(o for o in offer_catalog() if o['service_id']==service and o['method']==entry['artifact']['method']))
        public={'anchor':anchor,'public_rival_price':int(anchor*policy['future_rival_price_bps']/10000),
                'base_cost':sum(cfg[k] for k in ('production_cost','supplier_unit_cost','support_cost','onboarding_cost'))+cfg.get('prospective_policy',{}).get('premium_microUSD',0),
                'payment_bps':cfg['payment_bps'],'payment_fixed':cfg['payment_fixed'],'available':cash['summary']['available'],
                'reserve_buffer':1_000_000,'quote_cost':cfg['exposure_cost']+cfg['qualification_cost'],'native_state_digest':snapshot['state_digest'],'profit_tax_bps':cfg['profit_tax_bps']}
        future_policy=copy.deepcopy(cfg['strategic_policy']);future_policy['public_basis']+=' Declared future quote hypothesis, not a hidden future quote.'
        selection=select(future_policy,cfg.get('mechanism_policy'),entry['job']['id'],offer,None,public)
        for contract_id,channel in forecasts.items():
            forecast=compare_window(cfg,policy,selection,cash,now_hours=moment,future_existing_slots=slots,unused_inventory=len(cohort),
                eligible_new_contacts=len(buyers),allow_channel=channel['new_tranche_admissible'],allow_capacity=not outage and slots<cfg['maximum_slots'],channel_forecast=channel)
            for route in forecast['routes']:
                if not route['channel'] and not route['capacity'] or not route['current_cash_feasible']:continue
                if not route['channel']:
                    if service in capacity_seen:continue
                    capacity_seen.add(service)
                net=route['incremental_net_microUSD'];cost=route['first_action_cost']
                if set(net)!=set(scenarios):raise ValueError('MATCHED_SEQUENCE_SCENARIOS_REQUIRED')
                kind='acquisition' if route['channel'] else 'capacity'
                ident='sequence-'+service+'-'+contract_id+'-'+('channel-capacity' if route['channel'] and route['capacity'] else kind)+'-'+str(moment//24)
                options.append({'id':ident,'kind':kind,'upfront_cost':cost,'later_liabilities':dict.fromkeys(scenarios,route['contingent_later_capacity_cost']),
                    'future_net_cash':{k:v+cost for k,v in net.items()},'benefit_ids':['shared-sequence-window-'+str(moment//24)],'requires':[],
                    'exclusive_group':'sequence-investment-'+str(moment//24),'authorized':True,'evidence':digest(forecast),
                    'execution':{'funding':'EARNED','first_investment':kind,'contract_id':contract_id if route['channel'] else None,
                        'contract':cfg['channels'][contract_id] if route['channel'] else {'price':cfg['capacity_price']},
                        'forecast':{'service':service,'forecast':forecast},'contingent_capacity':bool(route['channel'] and route['capacity']),
                        'forecast_scope':'Actual observed multi-tranche contract state under paired public hypothetical future seeds. One first invoice; later capacity must replan. No future financial authority.'}})
    return options


def _complete_menu_options(cfg,moment,snapshot,operating,jobs,used,investments,buyers,scenarios,delivery_reserve,channel_state):
    """Compose existing paired-channel and quantity forecasts for admitted work.

    Context groups share only public request/budget hypotheses. A counted future
    job must be requested by every group member and have disjoint admitted work.
    This conservative common pool avoids assigning one packet to several buyers
    or assuming an inaccessible job will match a future contact. Only the first
    costed invoice can execute; subsequent observations must replan everything.
    """
    from .channel_menu import validate_policy
    from .sequence_channels import forecast_contract
    from .complete_offer_market import market_context
    if channel_state is None:raise ValueError('OBSERVED_CHANNEL_BOOK_REQUIRED')
    policy=cfg['strategic_allocation_policy']['sequence'];future=moment+24*policy['window_delay_days'];finish=future+cfg['production_hours']
    menu=validate_policy(cfg['channel_menu_policy'],cfg['channels'])
    usable=[i for i in investments if i['kind']=='capacity' and i['activation_time']<=future and finish<i['expiry_time']]
    slots=min(cfg['maximum_slots'],cfg['initial_slots']+sum(i.get('capacity_units',1) for i in usable))
    start=cfg['supplier_outage_start_day']*24;end=start+cfg['supplier_outage_days']*24
    outage=bool(cfg['supplier_outage_days'] and future<end and finish>=start)
    if outage:slots=0
    live_units=sum(i.get('capacity_units',1) for i in investments if i['kind']=='capacity' and i['expiry_time']>moment)
    remaining=max(0,cfg['maximum_slots']-cfg['initial_slots']-live_units)
    cash=copy.deepcopy(snapshot)
    cash['summary']['available']=max(0,cash['summary']['available']-operating-delivery_reserve)
    cash['summary']['unrestrictedEarned']=max(0,cash['summary']['unrestrictedEarned']-operating)
    consumed={key for ident in used if ident in jobs for key in jobs[ident]['job']['work_keys']}
    groups={}
    for ident,buyer in sorted(buyers.items()):
        pending=bool(buyer['pending_commitments']) if 'pending_commitments' in buyer else buyer.get('pending') is not None
        if not buyer['active'] or pending or buyer['next_need_time']>future:continue
        spend=buyer['observed_spend'] if 'observed_spend' in buyer else buyer['outside_spend']+buyer['our_settled_spend']+sum(buyer['pending_commitments'].values())
        context=market_context(cfg['complete_offer_policy'],ident,spend,True);key=digest(context)
        group=groups.setdefault(key,{'context':context,'ids':[]});group['ids'].append(ident)
    options=[]
    for group_id,group in sorted(groups.items()):
        context=group['context'];ids=group['ids']
        common=set.intersection(*(set(cfg['complete_offer_policy']['requested_jobs'][ident]) for ident in ids))
        available=[entry for ident,entry in sorted(jobs.items()) if ident in common and ident not in used and entry['job']['accepted'] and entry['artifact'].get('outcome_scope')=='complete_outcome' and not consumed.intersection(entry['job']['work_keys'])]
        for service in context['profile']['services']:
            cohort=[];work=set(consumed)
            for entry in available:
                if entry['job']['service_id']!=service or work.intersection(entry['job']['work_keys']):continue
                if cohort and entry['artifact']['method']!=cohort[0]['artifact']['method']:continue
                cohort.append(entry);work.update(entry['job']['work_keys'])
            if not cohort:continue
            entry=cohort[0];offer=copy.deepcopy(next(o for o in offer_catalog(include_packet=True) if o['service_id']==service and o['method']==entry['artifact']['method']))
            units=offer['capacity_units'];anchor=max(context['profile']['price_grids'][service])
            public={'anchor':anchor,'public_rival_price':anchor*policy['future_rival_price_bps']//10000,
                'base_cost':units*sum(cfg[k] for k in ('production_cost','supplier_unit_cost','support_cost'))+cfg['onboarding_cost']+cfg.get('prospective_policy',{}).get('premium_microUSD',0),
                'payment_bps':cfg['payment_bps'],'payment_fixed':cfg['payment_fixed'],'available':cash['summary']['available'],
                'reserve_buffer':1_000_000,'quote_cost':0,'native_state_digest':snapshot['state_digest'],'profit_tax_bps':cfg['profit_tax_bps']}
            selection=select(cfg['strategic_policy'],cfg.get('mechanism_policy'),entry['job']['id'],offer,None,public,market_context=context)
            capacity_seen=set()
            for contract_id in menu['contract_ids']:
                channel=forecast_contract(cfg['channels'],channel_state,buyers,moment//24,future//24,contract_id,owned_contact_count=policy['owned_contact_count'],target_customer_ids=ids)
                forecast=compare_window(cfg,policy,selection,cash,now_hours=moment,future_existing_slots=slots,unused_inventory=len(cohort),eligible_new_contacts=len(ids),allow_channel=channel['new_tranche_admissible'],allow_capacity=not outage and remaining>0,channel_forecast=channel,max_capacity_quantity=remaining)
                profile={'service':service,'public_context_sha256':group_id,'customer_ids':ids,'admitted_job_ids':[e['job']['id'] for e in cohort],
                    'admitted_work_keys':sorted({key for e in cohort for key in e['job']['work_keys']}),'capacity_units':units,'forecast':forecast}
                for route in forecast['routes']:
                    quantity=route['capacity_quantity']
                    if quantity>remaining or not route['channel'] and not quantity or not route['current_cash_feasible']:continue
                    if route['channel'] and not any(row.get('candidate',{}).get('window_contacts',0)>0 for row in channel['rows']):continue
                    if not route['channel']:
                        if quantity in capacity_seen:continue
                        capacity_seen.add(quantity)
                    net=route['incremental_net_microUSD'];cost=route['first_action_cost']
                    if not any(value>0 for value in net.values()):continue
                    if set(net)!=set(scenarios):raise ValueError('MATCHED_SEQUENCE_SCENARIOS_REQUIRED')
                    kind='acquisition' if route['channel'] else 'capacity'
                    ident='sequence-complete-'+group_id[:10]+'-'+service+'-'+contract_id+'-'+kind+'-'+str(quantity)+'-'+str(moment//24)
                    execution={'funding':'EARNED','first_investment':kind,'contract_id':contract_id if route['channel'] else None,
                        'contract':cfg['channels'][contract_id] if route['channel'] else {'price':cfg['capacity_price']},
                        'forecast':profile,'contingent_capacity':bool(route['channel'] and quantity),'contingent_capacity_units':quantity if route['channel'] else 0,
                        'forecast_scope':'Exact public one-window profile, weighted disjoint admitted work, paired costed contact hypotheses and conservative current cash. First invoice only; later capacity and delivery reobserve/replan/reserve, never future cash authority.'}
                    if kind=='capacity':execution['purchased_units']=quantity
                    options.append({'id':ident,'kind':kind,'upfront_cost':cost,'later_liabilities':dict.fromkeys(scenarios,route['contingent_later_capacity_cost']),
                        'future_net_cash':{key:value+cost for key,value in net.items()},
                        'benefit_ids':['unvalidated-shared-expansion-window-'+str(moment//24)]+['delivery-'+e['job']['id'] for e in cohort],
                        'requires':[],'exclusive_group':'sequence-investment-'+str(moment//24),'authorized':True,'evidence':digest(profile),'execution':execution})
    return options
