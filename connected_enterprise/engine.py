"""Event-clock simulated enterprise over the canonical owned native account."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import time
from adaptive_enterprise.instruments import load_jobs, execute_offer
from adaptive_enterprise.strategies import offer_catalog
from commercial.ledger import canonical, digest
from commercial.persistence import atomic_bytes
from .channels import ChannelBook, default_contracts, validate_contracts
from .finance import JournalAccount

MICRO=1_000_000
SERVICES=('reconciliation','kpi_variance','evidence_matrix')

def draw(seed,identity,stage):
    return int.from_bytes(hashlib.sha256(canonical(['connected014',seed,identity,stage])).digest()[:8],'big')/2**64

def default_config():
    return {'schema':'agi-alpha/connected014-config/v1','scope':'SIMULATED','epoch_utc':'2026-11-01T00:00:00Z','native_time_unit':'hour',
        'horizon_days':70,'customer_pool':36,'opening':5000*MICRO,'working':100*MICRO,'setup_cost':75*MICRO,'maintenance_daily':100_000,
        'exposure_cost':50_000,'qualification_cost':100_000,'onboarding_cost':500_000,'production_cost':1500_000,'support_cost':250_000,
        'supplier_unit_cost':250_000,'payment_bps':290,'payment_fixed':300_000,'profit_tax_bps':2000,'production_hours':2,'acceptance_hours':1,
        'clearing_hours':48,'payment_deadline_hours':240,'nonpayment_bps':200,'arrival_bps':7000,'retention_bps':9700,'initial_slots':1,'maximum_slots':3,
        'capacity_price':8*MICRO,'capacity_lead_hours':24,'capacity_duration_hours':21*24,'supplier_outage_start_day':-1,'supplier_outage_days':0,
        'price_pressure_bps':9000,'value_bps':10000,'buyer_budget_multiplier_bps':10000,'channels':default_contracts(),
        'human_comparator':{'reconciliation':{'hours':.65,'loaded_usd_hour':34.75},'kpi_variance':{'hours':.65,'loaded_usd_hour':60},'evidence_matrix':{'hours':.8,'loaded_usd_hour':55}},
        'cost_evidence':'AUTHORED_RESOURCE_ENVELOPES. Executed deterministic service/checker costs include acquisition, qualification, setup/development/failures, production, supplier, prepaid support, fees, maintenance, taxes. Host/model billing unavailable, never asserted zero. Human hours/wages are scenarios, not measurements or automatic sales.',
        'limits':['Synthetic non-personal work only; no actual customers or payments.','Finite authored buyer/channel/supplier contracts, no empirical conversion calibration.','Permanent native principal/fee protection tails remain; seed may back reserves.','No paid inference: capable-frontier AI economics represented by disclosed envelopes; actual executors are deterministic.','Finite frozen service inventory is an edition resource, not a universal market ceiling.']}

def fresh_account_config(manifest, *, prospective_policy=None, root=None):
    """Default exact-money registration for a NEW account, never a history upgrade.

    Returns (config, copied manifest). Historical default_config() and explicit
    legacy registrations remain unchanged. The caller must create a fresh account
    path and still declare finite market inputs/costs; this grants no demand/cash.
    """
    if not isinstance(manifest, dict):
        raise ValueError('FRESH_SERVICE_MANIFEST_REQUIRED')
    cfg = default_config()
    cfg['monetary_policy'] = 'exact-integer-v2'
    registered = copy.deepcopy(manifest)
    if prospective_policy is None:
        registered['native_engine'] = 'exact-permanent-v2'
    else:
        cfg['prospective_policy'] = copy.deepcopy(prospective_policy)
        registered['native_engine'] = 'exact-prospective-v2'
    from adaptive_enterprise.instruments import _validate_manifest
    _validate_manifest(Path(__file__).resolve().parents[1] if root is None else root, registered)
    return validate_config(cfg), registered


def validate_config(cfg):
    if set(cfg)-{'mechanism_policy','strategic_policy','strategic_allocation_policy','channel_menu_policy','prospective_policy','cash_diagnostic_available','monetary_policy'}!=set(default_config()) or cfg['scope']!='SIMULATED' or cfg['native_time_unit']!='hour':raise ValueError('EXACT_CONNECTED_CONFIGURATION_REQUIRED')
    for key in ['horizon_days','initial_slots','maximum_slots','production_hours','acceptance_hours','clearing_hours','payment_deadline_hours','capacity_lead_hours','capacity_duration_hours']:
        if type(cfg[key]) is not int or not 1<=cfg[key]<=10000:raise ValueError('FINITE_POSITIVE_RESOURCE_REQUIRED:'+key)
    # Explicit finite scenario population; no universal market ceiling.
    if type(cfg['customer_pool']) is not int or cfg['customer_pool']<1:raise ValueError('FINITE_POSITIVE_BUYER_POPULATION_REQUIRED')
    for key in ['nonpayment_bps','arrival_bps','retention_bps','payment_bps','profit_tax_bps']:
        if type(cfg[key]) is not int or not 0<=cfg[key]<=10000:raise ValueError('BASIS_POINTS_REQUIRED')
    if cfg['initial_slots']>cfg['maximum_slots'] or cfg['clearing_hours']>cfg['payment_deadline_hours']:raise ValueError('FINITE_VALID_CONTRACT_REQUIRED')
    if cfg['production_hours']+cfg['acceptance_hours']+cfg['clearing_hours']>cfg['payment_deadline_hours']:raise ValueError('COMPLETE_LIFECYCLE_EXCEEDS_PAYMENT_DEADLINE')
    for key in ['opening','working','setup_cost','maintenance_daily','exposure_cost','qualification_cost','onboarding_cost','production_cost','support_cost','supplier_unit_cost','capacity_price','payment_fixed']:
        if type(cfg[key]) is not int or cfg[key]<0:raise ValueError('INTEGER_RESOURCE_COST_REQUIRED')
    if 'monetary_policy' in cfg and cfg['monetary_policy']!='exact-integer-v2':raise ValueError('EXPLICIT_EXACT_MONETARY_POLICY_REQUIRED')
    if 'cash_diagnostic_available' in cfg and (type(cfg['cash_diagnostic_available']) is not int or not 0<=cfg['cash_diagnostic_available']<=10**15):raise ValueError('FINITE_DIAGNOSTIC_CASH_REQUIRED')
    if 'prospective_policy' in cfg:
        from .capital_lifecycle import validate_policy
        validate_policy(cfg['prospective_policy'],exact_money='monetary_policy' in cfg)
    if 'mechanism_policy' in cfg:
        from .mechanism_choice import validate_policy
        validate_policy(cfg['mechanism_policy'])
        if 'cost_contract' in cfg['mechanism_policy'] and cfg['mechanism_policy']['cost_contract']['production_envelope_microUSD']!=cfg['production_cost']:raise ValueError('COMMON_ENVELOPE_MUST_MATCH_PRODUCTION_CONFIG')
    if 'strategic_policy' in cfg:
        from .strategic_commerce import validate_policy
        validate_policy(cfg['strategic_policy'])
        from .joint_planning import validate_allocation_policy
        validate_allocation_policy(cfg.get('strategic_allocation_policy'))
        if cfg['maintenance_daily']<=0:raise ValueError('POSITIVE_PREPAID_STRATEGIC_PLANNING_CONTRACT_REQUIRED')
    elif 'strategic_allocation_policy' in cfg:raise ValueError('JOINT_STRATEGIC_POLICY_REQUIRED')
    contracts=validate_contracts(cfg['channels'])
    if 'channel_menu_policy' in cfg:
        from .channel_menu import validate_policy
        validate_policy(cfg['channel_menu_policy'],contracts)
        if 'strategic_policy' not in cfg:raise ValueError('CHANNEL_MENU_REQUIRES_NATIVE_JOINT_STRATEGY')
    if 'pilot' not in contracts:raise ValueError('CONNECTED_PILOT_CHANNEL_REQUIRED')
    if contracts['pilot']['lead_days']<1:raise ValueError('CONNECTED_CHANNEL_ADVANCE_LEAD_REQUIRED')
    normalized=copy.deepcopy(cfg);normalized['channels']=contracts
    return normalized

def _write(path,value):atomic_bytes(Path(path),canonical(value)+b'\n')

def _schedule(state,when,kind,ident,**fields):
    state['queue'].append({'id':ident,'time':when,'kind':kind,**fields})
    state['queue'].sort(key=lambda e:(e['time'],e['id']))

def _event(state,when,kind,ident,**fields):
    state['events'].append({'id':ident,'time':when,'kind':kind,**fields})

def _record_exposure(state,when,exposure,response=None):
    _event(state,when,'EXPOSURE',exposure['exposure_id'],customer_id=exposure['customer_id'],source_plan_id=exposure['source_plan_id'])
    if response is not None:_event(state,when,'REACTIVATION_RESPONSE',exposure['exposure_id']+'-reactivation',**response)

def _buyers(cfg,seed):
    result=[]
    for i in range(cfg['customer_pool']):
        ident=f'SIM-customer-{i:03d}';budget=int((180+400*draw(seed,ident,'budget'))*MICRO*cfg['buyer_budget_multiplier_bps']/10000)
        result.append({'id':ident,'initial_budget':budget,'remaining_budget':budget,'pending_commitments':{},'outside_spend':0,'our_settled_spend':0,'known':i<4,'active':True,'purchases':0,'onboarded':False,'next_need_time':0,'acquisition_source_plan_id':None,'exposure_time':0 if i<4 else None,'retention_decision_count':0,'service_index':i%3,'last_quote':None})
    return result

def _initial(cfg,seed,arm,source):
    s={'schema':'agi-alpha/connected014-live/v1','config':cfg,'seed':seed,'arm':arm,'source':source,'buyers':_buyers(cfg,seed),'queue':[],'events':[],'orders':[],
        'investments':[],'costs':[],'channel_state':ChannelBook(seed,cfg['channels']).export(),'used_jobs':[],'decisions':[],'current':None,'processed_events':0,'last_time':0,'tax_paid':0,
        'market':{'rival_cash':500*MICRO,'rival_collections':0,'rival_expenses':0,'rival_initial_cash':500*MICRO,'rival_observations':[],'public_rival_bps':cfg['price_pressure_bps'],'supplier_cash':100*MICRO,'supplier_initial_cash':100*MICRO,'supplier_collections':0,'supplier_expenses':0},'stop_reasons':[]}
    _schedule(s,0,'startup','000-startup')
    for day in range(cfg['horizon_days']):_schedule(s,day*24,'plan',f'plan-{day:04d}')
    return s

def _offer(jobs,state,buyer,cfg):
    service=SERVICES[buyer['service_index']%3]
    available=[entry for ident,entry in jobs.items() if ident not in state['used_jobs'] and entry['job']['service_id']==service and entry['artifact'].get('outcome_scope')=='complete_outcome' and entry['job']['accepted']]
    if not available:return None
    entry=sorted(available,key=lambda x:x['job']['id'])[0]
    method=entry['artifact']['method'];offer=copy.deepcopy(next(o for o in offer_catalog() if o['service_id']==service and o['method']==method))
    human=cfg['human_comparator'][service];anchor=int((human['hours']*human['loaded_usd_hour']+2)*MICRO)
    history=[d for d in state['decisions'] if d.get('service_id')==service and d.get('kind')=='offer'][-12:]
    winrate=sum(d['chosen'] for d in history)/len(history) if history else .5
    ratio=.88 if winrate<.4 else .98 if winrate>.8 else .93
    price=max(5*MICRO,int(anchor*ratio))
    if state['arm']=='competitive_growth':
        from .pricing import price as competitive_price
        base=cfg['production_cost']+cfg['supplier_unit_cost']+cfg['support_cost']+cfg['onboarding_cost']+cfg['qualification_cost']+cfg['exposure_cost']
        quote=competitive_price(anchor,price,int(anchor*state['market']['public_rival_bps']/10000),base,cfg['payment_bps'],cfg['payment_fixed'],[bool(d['chosen']) for d in history])
        if quote is not None:price=quote['price']
        offer['provenance']+=' Executed ordinary public competitive pricing with a complete direct-resource floor; no private buyer value or guaranteed sale.'
    offer['price_microUSD']=price
    return entry,offer,anchor

def _prepare_plan(state,account,jobs):
    cfg=state['config'];seed=state['seed'];ev=state['queue'][0];t=ev['time'];day=t//24
    prepared={'event':copy.deepcopy(ev),'before':account.snapshot(),'orders':[],'declines':[],'exposures':[],'reactivations':[],'channel_purchase':False,'capacity_purchase':False}
    if ev['kind']!='plan':return prepared
    book=ChannelBook(seed,cfg['channels'],state['channel_state']);exposures=book.expose(day,state['buyers']);prepared['channel_after']=book.export();prepared['exposures']=exposures
    simulated=copy.deepcopy(state);byid={b['id']:b for b in simulated['buyers']};owned_ids={b['id'] for b in state['buyers'][:4]};exposed_ids={x['customer_id'] for x in exposures}
    for x in exposures:
        b=byid[x['customer_id']]
        if not b['onboarded']:b['acquisition_source_plan_id']=x['source_plan_id'];b['exposure_time']=t
        if not b['active']:
            responded=draw(seed,[day,b['id']],'paid-reactivation-response')<.35
            prepared['reactivations'].append({'customer_id':b['id'],'responded':responded,'time':t,'source_plan_id':x['source_plan_id'],'response_probability_bps':3500})
            b['active']=responded
        b['known']=True
    production_time=t+cfg['production_hours']
    usable_capacity=[i for i in state['investments'] if i['kind']=='capacity' and i['activation_time']<=t and production_time<i['expiry_time']]
    slots=cfg['initial_slots']+len(usable_capacity)
    slots=min(cfg['maximum_slots'],slots)
    if cfg['supplier_outage_start_day']<=day<cfg['supplier_outage_start_day']+cfg['supplier_outage_days']:slots=0
    candidates=sorted((b for b in simulated['buyers'] if b['known'] and b['active'] and not b['pending_commitments'] and b['next_need_time']<=t and (b['id'] in owned_ids or b['onboarded'] or b['id'] in exposed_ids)),key=lambda b:(b['next_need_time'],b['id']))
    stats=prepared['channel_after']['exposures_by_day'][str(day)]
    prepared['outreach_units']=stats['attempted_slots']+sum(b['id'] not in exposed_ids for b in candidates)
    # Reserve the maximum qualification bill before commitments, including lost offers.
    operating_envelope=(0 if 'strategic_policy' in cfg else cfg['maintenance_daily'])+cfg['exposure_cost']*prepared['outreach_units']+cfg['qualification_cost']*len(candidates)
    prepared['operating_cost_envelope']=operating_envelope
    earned=prepared['before']['summary']['unrestrictedEarned'];margin_history=[o['price']-o['complete_cost'] for o in state['orders'] if o['outcome']=='SETTLED']
    live_channels=[i for i in prepared['channel_after']['instances'].values() if i['state'] not in {'FAILED','EXPIRED'} and i['expiry_day']>day]
    profitable=bool(margin_history and sum(margin_history)>0)
    pilot=cfg['channels']['pilot'];channel_invoice=pilot['price_microUSD']+pilot['support_microUSD']
    contacts=prepared['channel_after']['contacts']
    reachable=sum(b['id'] not in owned_ids and (not b['onboarded'] or not b['active']) and len(contacts.get(b['id'],[]))<pilot.get('max_contacts_per_customer',3) for b in state['buyers'])
    remaining=cfg['horizon_days']-day
    if state['arm']!='baseline' and profitable and reachable>0 and remaining>pilot['lead_days']+7 and not live_channels and ('strategic_policy' in cfg or earned>channel_invoice+operating_envelope+2*MICRO):
        known_access=pilot['activation_reliability_bps']*pilot['realization_bps']/10000**2
        forecast=sum(margin_history)/len(margin_history)*min(reachable,4)*.4*known_access
        prepared['channel_purchase']=forecast>channel_invoice;prepared['channel_predicted_net']=int(forecast-channel_invoice)
    lost_capacity=sum(d.get('kind')=='capacity_decline' and day-3<=d['time']//24<day for d in state['decisions'])
    live_capacity=sum(i['kind']=='capacity' and t<i['expiry_time'] for i in state['investments'])
    if state['arm'] in {'growth','competitive_growth'} and profitable and lost_capacity>=2 and slots<cfg['maximum_slots'] and live_capacity<cfg['maximum_slots']-cfg['initial_slots'] and remaining>7 and ('strategic_policy' in cfg or earned>cfg['capacity_price']+channel_invoice+operating_envelope+2*MICRO):
        capacity_forecast=sum(margin_history)/len(margin_history)*min(remaining,5)*.5;prepared['capacity_purchase']=capacity_forecast>cfg['capacity_price'];prepared['capacity_predicted_net']=int(capacity_forecast-cfg['capacity_price'])
    liquidity=prepared['before']['summary']['available']-operating_envelope-channel_invoice*bool(prepared['channel_purchase'])-cfg['capacity_price']*bool(prepared['capacity_purchase'])
    rival_capacity=2;rival_bps=state['market']['public_rival_bps'];rival_cash=state['market']['rival_cash']
    def buyer_choice(b,service,anchor,price=None):
        nonlocal rival_capacity,rival_cash
        value=int(anchor*(1.1+draw(seed,b['id'],'value'))*cfg['value_bps']/10000)
        rival_price=int(anchor*rival_bps/10000)
        prices={'human':anchor,'rival':rival_price}
        options=[('decline',0),('human',value-anchor)]
        if price is not None:prices['us']=price;options.append(('us',value-price))
        if rival_capacity>0 and rival_cash>MICRO:options.append(('rival',value-rival_price))
        options=[(name,u) for name,u in options if name=='decline' or b['remaining_budget']>=prices[name]]
        chosen=max(options,key=lambda p:(p[1],draw(seed,[day,b['id'],p[0]],'buyer-indifference')))[0]
        decision={'kind':'offer' if price is not None else 'outside_choice','time':t,'customer_id':b['id'],'service_id':service,'price':price,'human_price':anchor,'public_rival_price':rival_price,'chosen':chosen=='us','buyer_choice':chosen,'information':'Seller uses past public outcomes only; buyer utility is private environment, not policy observation. Unavailable enterprise offers do not remove outside alternatives.'}
        if chosen in {'human','rival'}:
            outside=prices[chosen];decision['outside_spend']=outside;b['remaining_budget']-=outside;b['next_need_time']=t+7*24
            if chosen=='rival':rival_capacity-=1;rival_cash+=outside-MICRO
        return decision
    joint=None; joint_by_customer={}; joint_selected={}
    if 'strategic_policy' in cfg:
        from .joint_planning import plan_actions
        joint=plan_actions(state,jobs,candidates,prepared,slots,operating_envelope,_offer,draw)
        prepared['joint_action']=joint
        joint_by_customer={d['customer_id']:d for d in joint['allocation']['deliveries']}
        from .strategic_commerce import selected_delivery
        for option in joint['allocation']['decision']['selected_options']:
            if option['kind']=='delivery':joint_selected[option['execution']['customer_id']]=selected_delivery(joint['allocation'],option['id'])
        chosen=joint['allocation']['decision']['selected']
        if 'channel_menu_policy' in cfg:
            prepared['channel_purchases']=[o for o in joint['allocation']['decision']['selected_options'] if o['kind']=='acquisition']
            prepared['channel_purchase']=bool(prepared['channel_purchases'])
            channel_invoice=sum(o['upfront_cost'] for o in prepared['channel_purchases'])
        else:prepared['channel_purchase']='channel-'+str(day) in chosen
        prepared['capacity_purchase']='capacity-'+str(day) in chosen
        if 'sequence' in cfg['strategic_allocation_policy']:
            picks=[o for o in joint['allocation']['decision']['selected_options'] if 'first_investment' in o['execution']]
            if len(picks)>1:raise ValueError('ONE_FIRST_SEQUENCE_INVESTMENT_REQUIRED')
            prepared['channel_purchase']=bool(picks and picks[0]['execution']['first_investment']=='acquisition')
            prepared['capacity_purchase']=bool(picks and picks[0]['execution']['first_investment']=='capacity')
            if picks:
                # Receipt value is only a disclosed planning hypothesis, not income.
                weights=cfg['strategic_allocation_policy']['risk']['scenarios']
                net=sum(weights[k]*(picks[0]['future_net_cash'][k]-picks[0]['upfront_cost']) for k in weights)//10000
                if net<=0:raise ValueError('POSITIVE_SEQUENCE_EXPECTATION_REQUIRED')
                prepared['channel_predicted_net']=prepared['capacity_predicted_net']=net

        liquidity=prepared['before']['summary']['available']-operating_envelope-channel_invoice*bool(prepared['channel_purchase'])-cfg['capacity_price']*bool(prepared['capacity_purchase'])
    for b in candidates:
        if draw(seed,[day,b['id']],'need')>=cfg['arrival_bps']/10000:continue
        service=SERVICES[b['service_index']%3];human=cfg['human_comparator'][service];anchor=int((human['hours']*human['loaded_usd_hour']+2)*MICRO)
        selected=_offer(jobs,simulated,b,cfg);blocked=None;method_plan=None;joint_choice=None
        if joint is not None:
            joint_choice=joint_selected.get(b['id'])
            if joint_choice:
                delivery=joint_by_customer[b['id']];entry=jobs[delivery['selection']['problem']['job_id']]
                selected=(entry,joint_choice['offer'],anchor)
            else:
                considered=joint_by_customer.get(b['id'])
                blocked='capacity_decline' if considered and considered['selection']['decision']['selected'] is not None and len(joint_selected)>=slots else 'joint_no_bid'
        if blocked:pass
        elif selected is None:blocked='inventory_decline'
        elif len(prepared['orders'])>=slots:blocked='capacity_decline'
        else:
            entry,offer,anchor=selected;price=offer['price_microUSD'];fee=(price*cfg['payment_bps']+9999)//10000+cfg['payment_fixed'];onboard=0 if b['onboarded'] else cfg['onboarding_cost'];cost=cfg['production_cost']+cfg['support_cost']+cfg['supplier_unit_cost']+fee+onboard+cfg.get('prospective_policy',{}).get('premium_microUSD',0)
            if joint_choice:method_plan=joint_choice['method_plan']
            elif 'mechanism_policy' in cfg and joint is None:
                from .mechanism_choice import order_plan
                method_plan=order_plan(cfg['mechanism_policy'],entry['job']['id'],offer,state.get('mechanism_memory'),cost)
            if method_plan:
                cost+=method_plan['cost']
                if method_plan['mode']=='hold':blocked='method_hold'
            if price-cost<=0 or liquidity<cost+price+MICRO:blocked='liquidity_decline'
        if blocked:
            prepared['declines'].append({'kind':blocked,'customer_id':b['id'],'time':t})
            choice=buyer_choice(b,service,anchor)
            if joint is not None:choice.update(joint_allocation_sha256=joint['id'],joint_option_id=None)
            prepared['declines'].append(choice)
            continue
        decision=buyer_choice(b,service,anchor,price)
        if joint_choice:decision.update(joint_allocation_sha256=joint['id'],joint_option_id=joint_choice['joint_option_id'])
        prepared['declines'].append(decision)
        if decision['buyer_choice']!='us':continue
        ident=f"order-{len(state['orders'])+len(prepared['orders']):04d}"
        order={'id':ident,'customer_id':b['id'],'job_id':entry['job']['id'],'work_keys':entry['job']['work_keys'],'offer':offer,'price':price,
            'qualified_time':t,'production_time':production_time,'acceptance_time':None,'collection_time':None,'clearing_due_time':None,'outcome':'PENDING',
            'complete_cost':cost,'fee':fee,'onboarding':onboard,'production_cost':cfg['production_cost']+cfg['supplier_unit_cost'],'support_cost':cfg['support_cost'],'service_receipt':None,
            'funding_receipt':None,'acquisition_source_plan_id':b['acquisition_source_plan_id'],'exposure_time':b['exposure_time'],
            'capacity_source_plan_id':usable_capacity[len(prepared['orders'])-cfg['initial_slots']]['plan_id'] if len(prepared['orders'])>=cfg['initial_slots'] else None}
        if 'prospective_policy' in cfg:
            from .capital_lifecycle import terms_for
            collection=production_time+cfg['acceptance_hours']+cfg['clearing_hours']
            terms=terms_for(ident,price,collection,cfg['prospective_policy'],fee,deadline=t+cfg['payment_deadline_hours'],exact_money='monetary_policy' in cfg)
            order.update(terms=terms,terms_id='terms-'+ident,terms_sha256=digest(terms),premium=terms['premium_microUSD'],resource_cost=cost-fee-terms['premium_microUSD'])
        if method_plan:order['method_plan']=method_plan
        if joint_choice:order.update(joint_allocation_sha256=joint['id'],joint_option_id=joint_choice['joint_option_id'])
        prepared['orders'].append(order);simulated['used_jobs'].append(order['job_id']);liquidity-=cost+price
    return prepared

def run_world(root,manifest,config,seed,arm,output,source=None,stop_after_events=None,failpoint=None):
    cfg=validate_config(copy.deepcopy(config));root=Path(root).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    expected_engine=('exact-prospective-v2' if 'prospective_policy' in cfg else 'exact-permanent-v2') if 'monetary_policy' in cfg else ('prospective-v1' if 'prospective_policy' in cfg else 'legacy-permanent-v1')
    if manifest.get('native_engine','legacy-permanent-v1')!=expected_engine:raise ValueError('FRESH_POLICY_NATIVE_ENGINE_REGISTRATION_MISMATCH')
    if arm not in {'baseline','channel','growth','competitive_growth'}:raise ValueError('REGISTERED_COMMERCIAL_OPTION_ARM_REQUIRED')
    if source is None:
        from .runner import identity
        source=identity(root)
    from .verify import check_source
    check_source(root,source)
    binding=digest({'config':cfg,'seed':seed,'arm':arm,'source':source,'manifest':manifest})
    path=output/'STATE.json'
    envelope=json.loads(path.read_text()) if path.exists() else None
    account=JournalAccount(root,manifest,output/'account.sqlite',opening=cfg['opening'],working=cfg['working'],contract='connected014/'+binding)
    try:
        state=account.verify_checkpoint(envelope) if envelope is not None else _initial(cfg,seed,arm,source)
        if digest({'config':state['config'],'seed':state['seed'],'arm':state['arm'],'source':state['source'],'manifest':manifest})!=binding:raise ValueError('LIVE_STATE_BINDING_CHANGED')
    except BaseException:
        account.close();raise
    jobs=load_jobs(root,manifest);cpu=time.process_time();wall=time.monotonic();performed=0
    def cost(ident,value,when,category,work=None,earned_only=False,expected_net=None):
        if not value:return None
        if category in {'acquisition_contract','capacity_contract','production_contract'}:
            receipt=account.spend(ident,category,value,when,work or {'resource_contract':ident,'category':category,'prepaid':True},max(1,expected_net or 1),allow_seed=not earned_only)
        else:receipt={'funding':'OPERATING_CASH','native_receipt':account.cost(ident,value,when),'id':ident,'amount':value,'day':when}
        if receipt is not None and not any(c['id']==ident for c in state['costs']):state['costs'].append({'id':ident,'amount':value,'category':category,'time':when,'funding_receipt':receipt})
        return receipt
    try:
        while state['queue']:
            if stop_after_events is not None and performed>=stop_after_events:break
            if state['current'] is None:
                if 'strategic_policy' in cfg and state['queue'][0]['kind']=='plan':
                    now=state['queue'][0]['time'];cost('maintenance-'+str(now//24),cfg['maintenance_daily'],now,'maintenance')
                state['current']=_prepare_plan(state,account,jobs);_write(path,account.seal_checkpoint(state))
            p=state['current'];ev=p['event'];t=ev['time'];day=t//24;kind=ev['kind'];byid={b['id']:b for b in state['buyers']}
            if kind=='startup':
                cost('complete-development-setup',cfg['setup_cost'],t,'development_integration_qualification_and_failed_search')
                _event(state,t,'STARTUP_FUNDED',ev['id'])
            elif kind=='plan':
                if p.get('joint_action'):state.setdefault('joint_actions',{})[p['joint_action']['id']]=p['joint_action']
                cost('maintenance-'+str(day),cfg['maintenance_daily'],t,'maintenance')
                state['channel_state']=p['channel_after'];book=ChannelBook(seed,cfg['channels'],state['channel_state'])
                for exposure in p['exposures']:
                    b=byid[exposure['customer_id']]
                    if not b['onboarded']:b['acquisition_source_plan_id']=exposure['source_plan_id'];b['exposure_time']=t
                    b['known']=True
                    response=next((r for r in p['reactivations'] if r['customer_id']==b['id']),None)
                    if response is not None:b['active']=response['responded']
                    _record_exposure(state,t,exposure,response)
                cost('outreach-'+str(day),cfg['exposure_cost']*p['outreach_units'],t,'outreach_including_failed_and_unused_slots')
                attempts=[d for d in p['declines'] if d['kind']=='offer'];qualified_candidates=(len(p['joint_action']['allocation']['deliveries']) if p.get('joint_action') else len(attempts));cost('qualification-'+str(day),cfg['qualification_cost']*qualified_candidates,t,'qualification_including_lost_offers')
                state['decisions'].extend(p['declines'])
                for d in p['declines']:
                    if d.get('outside_spend'):
                        b=byid[d['customer_id']];b['remaining_budget']-=d['outside_spend'];b['outside_spend']+=d['outside_spend'];b['next_need_time']=t+7*24
                        if d['buyer_choice']=='rival':
                            market=state['market'];market['rival_collections']+=d['outside_spend'];market['rival_cash']+=d['outside_spend']-MICRO;market['rival_expenses']+=MICRO
                if 'channel_menu_policy' in cfg:
                    for option in p.get('channel_purchases',[]):
                        contract_id=option['execution']['contract_id'];terms=cfg['channels'][contract_id];invoice=terms['price_microUSD']+terms['support_microUSD'];ident=option['id']
                        predicted=(sum(cfg['strategic_allocation_policy']['risk']['scenarios'][k]*(option['future_net_cash'][k]-invoice) for k in cfg['strategic_allocation_policy']['risk']['scenarios'])//10000 if 'first_investment' in option['execution'] else next(iter(option['future_net_cash'].values()))-invoice)
                        receipt=cost(ident,invoice,t,'acquisition_contract',{'terms':terms,'contract_id':contract_id,'investment':'expiring_contact_access'},earned_only=True,expected_net=predicted)
                        if receipt:
                            purchase=book.purchase(contract_id,day,receipt['plan_id']);state['investments'].append({'id':ident,'plan_id':receipt['plan_id'],'kind':'acquisition','contract_id':contract_id,'purchased_time':t,'activation_time':purchase['activation_day']*24,'expiry_time':purchase['expiry_day']*24,'cost':invoice,'funding_receipt':receipt,'contract_receipt':purchase,'predicted_net':predicted});_event(state,t,'INVESTMENT',ident,source_plan_id=receipt['plan_id'],investment_kind='acquisition',contract_id=contract_id)
                elif p['channel_purchase']:
                    terms=cfg['channels']['pilot'];invoice=terms['price_microUSD']+terms['support_microUSD'];ident='channel-'+str(day)
                    receipt=cost(ident,invoice,t,'acquisition_contract',{'terms':terms,'investment':'expiring_contact_access'},earned_only=True,expected_net=p['channel_predicted_net'])
                    if receipt:
                        purchase=book.purchase('pilot',day,receipt['plan_id']);state['investments'].append({'id':ident,'plan_id':receipt['plan_id'],'kind':'acquisition','purchased_time':t,'activation_time':purchase['activation_day']*24,'expiry_time':purchase['expiry_day']*24,'cost':invoice,'funding_receipt':receipt,'contract_receipt':purchase,'predicted_net':p['channel_predicted_net']});_event(state,t,'INVESTMENT',ident,source_plan_id=receipt['plan_id'],investment_kind='acquisition')
                if p['capacity_purchase']:
                    ident='capacity-'+str(day);receipt=cost(ident,cfg['capacity_price'],t,'capacity_contract',{'units_per_day':1,'lead_hours':cfg['capacity_lead_hours'],'duration_hours':cfg['capacity_duration_hours']},earned_only=True,expected_net=p['capacity_predicted_net'])
                    if receipt:state['investments'].append({'id':ident,'plan_id':receipt['plan_id'],'kind':'capacity','purchased_time':t,'activation_time':t+cfg['capacity_lead_hours'],'expiry_time':t+cfg['capacity_lead_hours']+cfg['capacity_duration_hours'],'cost':cfg['capacity_price'],'funding_receipt':receipt,'predicted_net':p['capacity_predicted_net']});_event(state,t,'INVESTMENT',ident,source_plan_id=receipt['plan_id'],investment_kind='capacity')
                state['channel_state']=book.export()
                for proposed in p['orders']:
                    o=copy.deepcopy(proposed);ident=o['id'];b=byid[o['customer_id']]
                    if 'terms' in o:account.execute('register_terms',{'id':o['terms_id'],'terms':o['terms']},t)
                    o['funding_receipt']=cost(ident+'-resources',o.get('resource_cost',o['complete_cost']),t,'production_contract',{'job_id':o['job_id'],'offer':o['offer'],'fee':o['fee'],'onboarding':o['onboarding'],'support':o['support_cost'],'resource_supplier':'SIMULATED_PREPAID_COMPLETE_RESOURCE_CONTRACT',**({'method_plan':o['method_plan'],**({'production_envelope_microUSD':cfg['production_cost']} if 'cost_contract' in o['method_plan'] else {})} if 'method_plan' in o else {})},expected_net=o['price']-o['complete_cost'])
                    if o['funding_receipt'] is None:raise ValueError('QUALIFIED_PRODUCTION_RESOURCE_CONTRACT_NOT_FUNDED')
                    account.execute('wallet',{'buyer':ident+'-wallet','amount':o['price']},t)
                    offered=account.execute('offer',{'id':ident,'buyer':ident+'-wallet','price':o['price'],'job_id':o['job_id'],'deadline':t+cfg['payment_deadline_hours'],**({'terms_id':o['terms_id']} if 'terms' in o else {})},t)
                    if 'terms' in o and o['fee']+o['premium'] and not any(c['id']==ident+'-prospective-charges' for c in state['costs']):state['costs'].append({'id':ident+'-prospective-charges','amount':o['fee']+o['premium'],'category':'prospective_contract_charges','time':t,'funding_receipt':offered})
                    for action in ['consent','fund']:account.execute('event',{'id':ident,'event_id':ident+'-'+action,'action':action},t)
                    b['pending_commitments'][ident]=o['price'];b['remaining_budget']-=o['price'];b['onboarded']=True;state['used_jobs'].append(o['job_id']);state['orders'].append(o)
                    _event(state,t,'QUALIFIED_ORDER',ident+'-qualified',order_id=ident,customer_id=b['id']);_schedule(state,o['production_time'],'produce',ident+'-produce',order_id=ident)
                if day and day%7==0:
                    observed=[d for d in state['decisions'] if d['kind']=='offer' and d['time']<=t-24][-20:]
                    if observed:
                        won=sum(d['buyer_choice']=='rival' for d in observed)/len(observed);old=state['market']['public_rival_bps'];state['market']['public_rival_bps']=max(5000,min(10500,old+(200 if won>.6 else -200)))
                _event(state,t,'BUSINESS_DECISION',ev['id'],offered=len(attempts),qualified=len(p['orders']),channel_selected=bool(p['channel_purchase']),capacity_selected=bool(p['capacity_purchase']),public_account_before=p['before']['summary'])
            elif kind=='produce':
                o=next(o for o in state['orders'] if o['id']==ev['order_id'])
                if 'method_plan' in o:
                    from .mechanism_choice import execute_funded
                    plan=o['method_plan'];execution=execute_funded(root,manifest,account,o['offer'],o['job_id'],ident=o['id']+'-method',day=t,mode=plan['mode'],costs=plan['costs'],memory=plan['memory'],prepaid_order=o['id'],cost_contract=plan.get('cost_contract'),backend=plan.get('backend'))
                    o['method_execution']=execution;o['service_receipt']=execution.get('service',{'accepted':False,'errors':[execution.get('error','METHOD_FAILED')]})
                    if execution.get('memory') is not None:state['mechanism_memory']=execution['memory']
                else:o['service_receipt']=execute_offer(root,manifest,o['offer'],o['job_id'])
                if not o['service_receipt'].get('accepted'):o['outcome']='QUALITY_REJECTED'
                _event(state,t,'PRODUCTION',ev['id'],order_id=o['id'],accepted_by_executor=o['service_receipt'].get('accepted'));_schedule(state,t+cfg['acceptance_hours'],'accept',o['id']+'-accept',order_id=o['id'])
                market=state['market'];supplier_receipt=cfg['supplier_unit_cost'];market['supplier_collections']+=supplier_receipt;market['supplier_expenses']+=supplier_receipt//2;market['supplier_cash']+=supplier_receipt-supplier_receipt//2
            elif kind=='accept':
                o=next(o for o in state['orders'] if o['id']==ev['order_id'])
                if o['outcome']=='QUALITY_REJECTED':_schedule(state,t,'clear',o['id']+'-clear',order_id=o['id'],refund=True)
                else:
                    account.execute('event',{'id':o['id'],'event_id':o['id']+'-prepare','action':'prepare'},t);o['acceptance_time']=t
                    _event(state,t,'ACCEPTANCE',ev['id'],order_id=o['id'])
                    default=draw(seed,[o['customer_id'],o['qualified_time'],o['offer']['service_id']],'nonpayment')<cfg['nonpayment_bps']/10000
                    delay=cfg['payment_deadline_hours']-cfg['production_hours']-cfg['acceptance_hours'] if default else cfg['clearing_hours']
                    o['clearing_due_time']=t+delay;_schedule(state,t+delay,'clear',o['id']+'-clear',order_id=o['id'],refund=default)
            elif kind=='clear':
                o=next(o for o in state['orders'] if o['id']==ev['order_id']);action='refund' if ev['refund'] else 'release';cleared=account.execute('event',{'id':o['id'],'event_id':o['id']+'-'+action,'action':action},t)
                b=byid[o['customer_id']];b['pending_commitments'].pop(o['id'],None)
                if not ev['refund']:
                    o['outcome']='SETTLED';o['collection_time']=t;b['our_settled_spend']+=o['price'];b['purchases']+=1;b['service_index']+=1
                    b['active']=draw(seed,[b['id'],b['retention_decision_count']],'retention')<cfg['retention_bps']/10000;b['retention_decision_count']+=1
                else:
                    b['remaining_budget']+=o['price'];o['outcome']='REFUNDED' if o['outcome']!='QUALITY_REJECTED' else o['outcome']
                b['next_need_time']=t+7*24
                _event(state,t,'COLLECTION' if not ev['refund'] else 'REFUND',ev['id'],order_id=o['id'])
                summary=cleared['summary'];taxable=max(0,summary['profit']+state['tax_paid']);tax=max(0,taxable*cfg['profit_tax_bps']//10000-state['tax_paid'])
                if tax:cost('tax-'+o['id'],tax,t,'tax_provision');state['tax_paid']+=tax
                if not ev['refund'] and 'terms' in o:_schedule(state,o['terms']['maturity_day']+1,'mature',o['id']+'-mature',order_id=o['id'])
            elif kind=='mature':
                o=next(o for o in state['orders'] if o['id']==ev['order_id'])
                before=account.snapshot()['summary'];after=account.advance_financial(t)['summary']
                o['maturity_time']=t
                _event(state,t,'PROTECTION_MATURITY',ev['id'],order_id=o['id'])
                if before['profit']!=after['profit'] or before['cash']!=after['cash']:raise ValueError('MATURITY_CANNOT_CREATE_CASH_OR_PROFIT')
            else:raise ValueError('UNKNOWN_OPERATING_EVENT')
            if failpoint:failpoint('after_event_before_checkpoint',state,account)
            state['queue'].pop(0);state['last_time']=t;state['processed_events']+=1;state['current']=None;_write(path,account.seal_checkpoint(state));performed+=1
        audit=account.audit();owned=account.export();summary=audit['summary'];settled=[o for o in state['orders'] if o['outcome']=='SETTLED'];customers={o['customer_id'] for o in settled};earned=[o for o in settled if o['funding_receipt']['funding']=='EARNED' and o['price']>o['complete_cost']]
        for b in state['buyers']:
            if b['initial_budget']!=b['remaining_budget']+b['outside_spend']+b['our_settled_spend']+sum(b['pending_commitments'].values()) or b['remaining_budget']<0:raise ValueError('SHARED_BUYER_BUDGET_CONSERVATION')
        result={k:copy.deepcopy(state[k]) for k in ['config','seed','arm','source','orders','buyers','investments','costs','events','decisions','market','stop_reasons']}
        if 'joint_actions' in state:result['joint_actions']=copy.deepcopy(state['joint_actions'])
        from .capital_lifecycle import capital_metrics
        result.update(schema='agi-alpha/connected014-result/v1',scope='CONDITIONAL_SIMULATION',channels=state['channel_state'],owned_account=owned,summary=summary,complete=not state['queue'],processed_events=state['processed_events'],
            accepted_jobs=sum(o['acceptance_time'] is not None for o in state['orders']),paid_jobs=len(settled),customers=len(customers),repeat_customers=sum(sum(o['customer_id']==c for o in settled)>1 for c in customers),profitable_earned_continuations=len(earned),
            conditional_simulated_commercial_success=len(settled)>=12 and len(customers)>=3 and sum(sum(o['customer_id']==c for o in settled)>1 for c in customers)>=2 and len(earned)>=2 and summary['profit']>0 and summary['unrestrictedEarned']>0 and summary['payables']==0 and not summary['investmentStopped'] and summary['cash']>=summary['custodyReserve']+summary['tailReserve']+summary['workingCapital'],
            actual_collections=0,actual_customers=0,actual_profit=None,resource_receipt={'process_cpu_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-wall,'billing':'UNAVAILABLE_ENVELOPED_NOT_ZERO'})
        result['productive_expansion']=[{'plan_id':i['plan_id'],'kind':i['kind'],'cost':i['cost'],'funding':i['funding_receipt']['funding'],'later_settled_order_ids':[o['id'] for o in settled if o.get('acquisition_source_plan_id' if i['kind']=='acquisition' else 'capacity_source_plan_id')==i['plan_id']],'scoped_collections':sum(o['price'] for o in settled if o.get('acquisition_source_plan_id' if i['kind']=='acquisition' else 'capacity_source_plan_id')==i['plan_id'])} for i in state['investments']]
        result['capital_metrics']=capital_metrics(result)
        result['resource_receipt'].update(process_cpu_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-wall)
        _write(output/'RESULT.json',result)
        return result
    finally:account.close()
