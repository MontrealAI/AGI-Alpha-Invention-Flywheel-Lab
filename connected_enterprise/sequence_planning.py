"""Opt-in source-bound channel/capacity sequences, with first-action execution only."""
import copy
from fractions import Fraction
from commercial.ledger import digest
from adaptive_enterprise.strategies import offer_catalog
from .strategic_commerce import select
from .sequence_window import compare_window


def sequence_options(cfg, moment, snapshot, operating, jobs, used, investments,
                     public_buyers, contacts, failed_channels, scenarios, current_delivery_reserve=0):
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
                'base_cost':sum(cfg[k] for k in ('production_cost','supplier_unit_cost','support_cost','onboarding_cost')),
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
