"""Finite two-stage contract forecast, not financial or execution authority.

Evaluate one shared future delivery window under explicit public hypotheses.
Existing one-order quote/method selection supplies price, cost and win beliefs.
No hidden customer values, scenario draws or future receipts enter funding.
"""
from fractions import Fraction as F
from math import comb, floor
from commercial.ledger import digest
from connected_enterprise.strategic_commerce import rederive


def _binomial(n, p):
    return [F(comb(n, k)) * p**k * (1-p)**(n-k) for k in range(n+1)]


def _expected_deliveries(n, p, extra, q, limit):
    return sum(a*b*min(i+j, limit) for i,a in enumerate(_binomial(n,p))
               for j,b in enumerate(_binomial(extra,q)))


def compare_window(config, policy, selection, observation, *, now_hours,
                   future_existing_slots, unused_inventory, eligible_new_contacts,
                   existing_channel_probability="0", allow_channel=True, allow_capacity=True, channel_forecast=None):
    """Compare no investment/channel/capacity/both on one common cashflow model.

    policy is authored PUBLIC forecast input, never a realized buyer observation.
    The caller must reconstruct and bind it, inventory and slots to native state.
    Baseline subtraction prevents assigning existing business profit to expansion.
    Future production must be reselected/re-reserved after actual observations.
    """
    required = {'schema','provenance','window_delay_days','owned_contact_count',
                'owned_available_bps','service_share_bps','arrival_bps','future_rival_price_bps'}
    if set(policy) != required or policy['schema'] != 'public-sequence-window/v1':
        raise ValueError('EXPLICIT_PUBLIC_TRANSITION_HYPOTHESES_REQUIRED')
    if not isinstance(policy['provenance'],str) or not policy['provenance'].strip():
        raise ValueError('PUBLIC_HYPOTHESIS_PROVENANCE_REQUIRED')
    for key in required-{'schema','provenance'}:
        if type(policy[key]) is not int or policy[key] < 0:
            raise ValueError('NONNEGATIVE_INTEGER_TRANSITION_REQUIRED')
    if not 1 <= policy['window_delay_days'] <= 30 or policy['owned_contact_count'] > 8:
        raise ValueError('FINITE_TWO_STAGE_WINDOW_REQUIRED')
    if policy['future_rival_price_bps']>30000:raise ValueError('FINITE_FUTURE_RIVAL_HYPOTHESIS_REQUIRED')
    if any(policy[k] > 10000 for k in ('owned_available_bps','service_share_bps','arrival_bps')):
        raise ValueError('PUBLIC_TRANSITION_BASIS_POINTS_REQUIRED')
    for value in (now_hours, future_existing_slots, unused_inventory, eligible_new_contacts):
        if type(value) is not int or value < 0:
            raise ValueError('BOUND_CURRENT_PUBLIC_STATE_REQUIRED')
    rederive(selection)
    if selection['problem']['public']['native_state_digest'] != observation['state_digest']:
        raise ValueError('CURRENT_NATIVE_STATE_BINDING_REQUIRED')
    row = selection['decision']['selected']
    if row is None:
        return {'schema':'two-stage-window/v1','decision':'NO_ADMISSIBLE_DELIVERY_PROFILE','routes':[]}
    full_base = sum(config[k] for k in ('production_cost','supplier_unit_cost','support_cost','onboarding_cost'))
    extra_onboarding = max(0, full_base-selection['problem']['public']['base_cost'])
    future_cost = row['cost']+extra_onboarding
    required_cash = row['required_current_cash']+extra_onboarding
    terms = config['channels'][channel_forecast['contract_id'] if channel_forecast is not None else 'pilot']
    horizon = now_hours + 24*policy['window_delay_days']
    channel_active = (terms['lead_days']*24 <= horizon-now_hours <
                      (terms['lead_days']+terms['duration_days'])*24)
    capacity_active = (config['capacity_lead_hours'] <= horizon-now_hours and
                       horizon-now_hours+config['production_hours'] <
                       config['capacity_lead_hours']+config['capacity_duration_hours'])
    if horizon >= config['horizon_days']*24:
        channel_active = capacity_active = False
    available = observation['summary']['available']
    earned = observation['summary']['unrestrictedEarned']
    arrival = F(policy['arrival_bps'],10000)*F(policy['service_share_bps'],10000)
    owned = len(channel_forecast['owned_customer_ids']) if channel_forecast is not None else policy['owned_contact_count']
    extra = min(eligible_new_contacts, terms['slots_per_day'], 8)
    reach = F(terms['realization_bps'],10000)*F(10000-terms['overlap_bps'],10000)
    activation = F(terms['activation_reliability_bps'],10000) if channel_active else F(0)
    quote_cost = config['exposure_cost']+config['qualification_cost']
    invoice = terms['price_microUSD']+terms['support_microUSD']
    existing = F(existing_channel_probability)
    if not 0 <= existing <= 1: raise ValueError('PUBLIC_CHANNEL_PROBABILITY_REQUIRED')
    routes=[]
    for channel,capacity in ((False,False),(True,False),(False,True),(True,True)):
        if channel and not allow_channel or capacity and not allow_capacity: continue
        cost = channel*invoice + capacity*config['capacity_price']
        feasible = cost <= min(available,earned)
        cash = max(0,available-cost-config['maintenance_daily']*policy['window_delay_days'])
        # Treat all future delivery cost+principal locks as simultaneous: no
        # forecast collections, reserve releases or earned cash can fund them.
        if channel_forecast is not None:
            route_samples=[r['candidate' if channel else 'baseline'] for r in channel_forecast['rows']]
            contact_cash=max(x['attempted_slots_to_window']*config['exposure_cost']+x['realized_contacts_to_window']*config['qualification_cost'] for x in route_samples)+owned*quote_cost*policy['window_delay_days']
            cash=max(0,cash-contact_cash)
        cap_ready = capacity_active and (not channel or config['capacity_lead_hours']+24 <= horizon-now_hours)
        limit = min(unused_inventory, config['maximum_slots'], future_existing_slots+int(capacity and cap_ready),
                    cash//required_cash)
        if horizon >= config['horizon_days']*24: limit=0
        values={};counts={}
        for forecast in row['forecasts']:
            win=F(str(forecast['win_probability']))
            p=arrival*F(policy['owned_available_bps'],10000)*win
            q=arrival*reach*win
            plain=_expected_deliveries(owned,p,0,F(0),limit)
            with_channel=_expected_deliveries(owned,p,extra,q,limit)
            access=activation if channel else existing
            count=(1-access)*plain+access*with_channel
            paid=F(str(forecast['accept_collect_probability']))
            contribution=paid*row['price']-future_cost-paid*max(0,row['price']-future_cost)*F(config['profit_tax_bps'],10000)
            contacts=owned*F(policy['owned_available_bps'],10000)+access*extra*reach
            if channel_forecast is not None:
                samples=[r['candidate' if channel else 'baseline'] for r in channel_forecast['rows']]
                count=sum(_expected_deliveries(owned,p,x['window_contacts'],arrival*win,limit) for x in samples)/len(samples)
                outreach=sum(F(x['attempted_slots_to_window']) for x in samples)/len(samples)
                qualification=sum(F(x['realized_contacts_to_window']) for x in samples)/len(samples)
                costed_contacts=owned*quote_cost*policy['window_delay_days']+outreach*config['exposure_cost']+qualification*config['qualification_cost']
            else:costed_contacts=contacts*quote_cost
            values[forecast['belief']]=count*contribution-costed_contacts-cost
            counts[forecast['belief']]=str(count)
        routes.append({'channel':channel,'capacity':capacity,'first_action_cost':(invoice if channel else cost),
                       'contingent_later_capacity_cost':(config['capacity_price'] if channel and capacity else 0),
                       'current_cash_feasible':feasible,'future_delivery_cash_limit':limit,**({'future_contact_reserve_microUSD':contact_cash} if channel_forecast is not None else {}),
                       'expected_deliveries':counts,'_values':values})
    baseline=routes[0]['_values']
    for route in routes:
        route['incremental_net_microUSD']={k:floor(v-baseline[k]) for k,v in route.pop('_values').items()}
    return {'schema':'two-stage-window/v1','current_state_digest':observation['state_digest'],
            'public_hypotheses_sha256':digest(policy),'selection_sha256':digest(selection),
            'future_window_hours':horizon,'routes':routes,**({'channel_forecast':channel_forecast} if channel_forecast is not None else {}),
            'scope':'AUTHORED_PUBLIC_ONE_WINDOW_RECOURSE_FORECAST_NOT_EXECUTION',
            'limits':'Same costed delivery profile used for a declared future service mix. Combined route buys channel first and forecasts capacity at the next daily decision; that purchase is not authorized. No calibrated demand, repeated customer availability, future method benefit or native execution claimed. Activation failure/reach are explicit hypotheses; no retry credit assumed. First actions require native reservation, and actual future delivery must replan.'}
