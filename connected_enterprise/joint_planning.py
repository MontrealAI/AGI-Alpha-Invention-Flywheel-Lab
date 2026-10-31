"""Source-bound finite planning over existing connected delivery/expansion actions."""
import copy
from commercial.ledger import digest
from adaptive_enterprise.allocation import default_riskpolicy
from .strategic_commerce import select,allocate_actions

def validate_allocation_policy(policy):
    if not isinstance(policy,dict) or set(policy)-{'sequence'}!={'risk','max_customers'} or type(policy['max_customers']) is not int or not 1<=policy['max_customers']<=8:
        raise ValueError('EXPLICIT_BOUNDED_JOINT_ALLOCATION_POLICY_REQUIRED')
    if not isinstance(policy['risk'],dict) or set(policy['risk'])!=set(default_riskpolicy()):
        raise ValueError('EXACT_JOINT_RISK_POLICY_REQUIRED')
    return policy

def investment_option(ident,kind,cost,predicted_net,scenarios,day,contract):
    return {'id':ident,'kind':kind,'upfront_cost':cost,'later_liabilities':dict.fromkeys(scenarios,0),
        'future_net_cash':dict.fromkeys(scenarios,predicted_net+cost),
        'benefit_ids':['unvalidated-shared-expansion-window-'+str(day)],'requires':[],
        'exclusive_group':None,'authorized':True,'evidence':digest(contract),
        'execution':{'funding':'EARNED','contract':contract,'forecast_scope':'Historical margin and public contract hypothesis; not income. Shared benefit identity forbids unverified additive channel/capacity gains.'}}

def observed_sequence_buyers(state, prepared):
    buyers={b['id']:copy.deepcopy(b) for b in state['buyers']}
    for response in prepared['reactivations']:
        buyers[response['customer_id']]['active']=response['responded']
    return buyers

def plan_actions(state,jobs,candidates,prepared,slots,operating_envelope,offer_fn,draw_fn):
    cfg=state['config'];day=prepared['event']['time']//24;policy=validate_allocation_policy(cfg['strategic_allocation_policy'])
    snapshot=prepared['before'];available=max(0,snapshot['summary']['available']-operating_envelope)
    risk=copy.deepcopy(policy['risk']);risk['authorized_allocation']=min(risk['authorized_allocation'],available)
    deliveries=[];tentative=copy.deepcopy(state);needs=[]
    for buyer in candidates:
        if draw_fn(state['seed'],[day,buyer['id']],'need')>=cfg['arrival_bps']/10000:continue
        needs.append(buyer['id'])
        if len(deliveries)>=policy['max_customers']:continue
        selected=offer_fn(jobs,tentative,buyer,cfg)
        if selected is None:continue
        entry,offer,anchor=selected;job=entry['job'];onboard=0 if buyer['onboarded'] else cfg['onboarding_cost']
        public={'anchor':anchor,'public_rival_price':int(anchor*state['market']['public_rival_bps']/10000),
            'base_cost':cfg['production_cost']+cfg['supplier_unit_cost']+cfg['support_cost']+onboard,
            'payment_bps':cfg['payment_bps'],'payment_fixed':cfg['payment_fixed'],'available':available,
            'reserve_buffer':1_000_000,'quote_cost':cfg['exposure_cost']+cfg['qualification_cost'],
            'native_state_digest':snapshot['state_digest'],'profit_tax_bps':cfg['profit_tax_bps']}
        selection=select(cfg['strategic_policy'],cfg.get('mechanism_policy'),job['id'],offer,state.get('mechanism_memory'),public)
        deliveries.append({'id':'quote-'+str(day)+'-'+buyer['id'],'customer_id':buyer['id'],'onboarding':onboard,
                           'exclusive_group':'customer-'+buyer['id'],'selection':selection,'requires':[]})
        tentative['used_jobs'].append(job['id'])
    investments=[]
    if prepared['channel_purchase']:
        terms=cfg['channels']['pilot'];invoice=terms['price_microUSD']+terms['support_microUSD']
        investments.append(investment_option('channel-'+str(day),'acquisition',invoice,prepared['channel_predicted_net'],risk['scenarios'],day,terms))
    if prepared['capacity_purchase']:
        contract={'price':cfg['capacity_price'],'lead_hours':cfg['capacity_lead_hours'],'duration_hours':cfg['capacity_duration_hours']}
        investments.append(investment_option('capacity-'+str(day),'capacity',cfg['capacity_price'],prepared['capacity_predicted_net'],risk['scenarios'],day,contract))
    if 'sequence' in policy:
        from .sequence_planning import sequence_options
        failed={e['source_plan_id'] for e in prepared['channel_after']['events'] if e['day']<=day and e['kind']=='CHANNEL_ACTIVATION_FAILED'}
        public_buyers=observed_sequence_buyers(state,prepared)
        investments=sequence_options(cfg,prepared['event']['time'],snapshot,operating_envelope,jobs,
            set(state['used_jobs'])|{d['selection']['problem']['job_id'] for d in deliveries},
            state['investments'],public_buyers,prepared['channel_after']['contacts'],failed,risk['scenarios'],
            sum(max((r['required_current_cash'] for r in d['selection']['candidates']),default=0) for d in deliveries))
    allocation=allocate_actions(snapshot,deliveries,investments,risk,allow_seed=True,max_delivery_slots=slots,earned_deduction=operating_envelope)
    if allocation['decision']['optimality_scope']=='NONE':raise ValueError('JOINT_PLANNING_SHORTLIST_EXCEEDS_DECLARED_FINITE_BOUND')
    return {'id':digest(allocation),'time':prepared['event']['time'],'allocation':allocation,
            'operating_envelope':operating_envelope,'candidate_ids':[b['id'] for b in candidates],
            'observed_need_ids':needs,'scope':'Exact finite declared shortlist only; hypothetical expansion returns are not spendable. No hidden future draws enter the selector.'}
