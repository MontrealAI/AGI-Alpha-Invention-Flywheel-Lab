"""Public-state deterministic policy and stochastic SIM market transitions.

This module produces decisions only. It cannot mutate money or declare funds.
"""
from copy import deepcopy
from math import ceil
from fractions import Fraction
from .money import usd,floor_share,payment
from .market import rng,choose_price,draw_choices,outcomes,choice_probabilities

MICRO=1_000_000

def initial_state():return {'month':0,'active':0,'contacted':0,'capacity':0,'pending_leads':[],'expired_leads':0}

def propose(state,summary,world,reg,seed,unit_cost,opening,*,grow=True,funding_mode="capital_available",policy_name="balanced"):
    settings=reg['allocation_policies'][policy_name]
    m=state['month'];s=deepcopy(state)
    retained=int(rng(seed,m,'retention').binomial(s['active'],1-world['monthly_churn']))
    capacity=s['capacity']
    # Preserve operating liquidity and all native protections. Growth gets only
    # collected strict earnings after month0's separately labeled launch budget.
    strict=max(0,min(summary['available'],summary['unrestrictedEarned'],summary['profit']-summary['tailReserve']-summary['custodyReserve']-summary['workingCapital']))
    public_quote=choose_price(reg['price_candidates_usd'],unit_cost,world,m)['selected']
    quote_prior=public_quote['price_usd'] if public_quote else 0
    arriving=sum(c['count'] for c in s['pending_leads'] if c['active']<=m<=c['expires'])
    prob_new=choice_probabilities(quote_prior,world,m)[0]['ours'] if public_quote else 0
    prob_repeat=choice_probabilities(quote_prior,world,m,True)[0]['ours'] if public_quote else 0
    # Protect expected imminent production AND native collateral before buying
    # additional leads/capacity. No future realized choice/collection draw used.
    expected_jobs=min(capacity,ceil(arriving*prob_new+retained*prob_repeat))
    operating_reserve=usd(reg['fixed_maintenance_monthly_usd'])+expected_jobs*(usd(unit_cost+world['onboarding_usd']+quote_prior)+payment(usd(quote_prior),world)+200_000)
    launch=m==0
    growth_cash=summary['available'] if launch or funding_mode=='capital_available' else strict
    grow_budget=max(0,floor_share(growth_cash,settings['launch_fraction' if launch else 'growth_cash_fraction'])-operating_reserve) if grow or launch else 0
    # Capacity is a paid reusable monthly processing allowance, not a free limit.
    cap_spend=floor_share(grow_budget,settings['capacity_fraction_of_growth'])
    extra=cap_spend//int(world['capacity_unit_setup_usd']*MICRO)
    cap_spend=extra*int(world['capacity_unit_setup_usd']*MICRO);capacity+=extra
    saturated=Fraction(s['contacted'],max(1,world['reachable_firms']))
    lead_unit=int(usd(world['lead_cost_usd'])*(1+world['acquisition_saturation_cost_factor']*saturated))
    leads=min(world['reachable_firms']-s['contacted'],max(0,(grow_budget-cap_spend)//lead_unit))
    lead_spend=leads*lead_unit
    # Paid lead acquisition activates next month, with explicit expiry. Paid
    # reach consumed once; churned firms are not silently recycled as new leads.
    eligible=0;pending=[];expired=0
    for cohort in s['pending_leads']:
        if cohort['expires']<m:expired+=cohort['count']
        elif cohort['active']<=m:eligible+=cohort['count']
        else:pending.append(cohort)
    activated=int(rng(seed,m,'activation').binomial(leads,world['lead_activation']))
    pending.append({'count':activated,'active':m+1,'expires':m+world['channel_expiry_months']})
    p=choose_price(reg['price_candidates_usd'],unit_cost,world,m)
    quote=p['selected']['price_usd'] if p['selected'] else 0
    newchoice=draw_choices(eligible,quote,world,m,seed) if quote else {'eligible':eligible,'counts':{'ours':0}}
    repeatchoice=draw_choices(retained,quote,world,m,seed,True) if quote else {'eligible':retained,'counts':{'ours':0}}
    desired=newchoice['counts']['ours']+repeatchoice['counts']['ours']
    outage=bool(rng(seed,m,'outage').random()<world['supplier_outage_probability'])
    offered_capacity=0 if outage else capacity
    # Production must be prepaid from CURRENT cash after acquisition/capacity.
    cashleft=max(0,summary['available']-cap_spend-lead_spend-int(reg['fixed_maintenance_monthly_usd']*MICRO))
    # Worst-case onboarding is reserved for every processed job; unused repeat
    # onboarding is not charged below. This is a conservative funding limit.
    affordable=cashleft//(usd(unit_cost+world['onboarding_usd']+quote)+payment(usd(quote),world)+200_000) if quote else 0
    chosen=min(desired,offered_capacity,affordable)
    new_units=min(chosen,newchoice['counts']['ours']);repeat_units=chosen-new_units
    out=outcomes(chosen,world,m,seed)
    resource=int(unit_cost*MICRO)*chosen
    onboarding=int(world['onboarding_usd']*MICRO)*new_units
    # Rejected/uncollected work costs are retained. Support is prepaid inside
    # unit resource cost; this code does not manufacture ongoing free support.
    s.update(month=m+1,active=out['quality_accepted'],contacted=s['contacted']+leads,capacity=capacity,pending_leads=pending,expired_leads=s['expired_leads']+expired)
    return {'month':m,'state_before':state,'state_after':s,'price_choice':p,'unit_price_usd':quote,'new_choice':newchoice,'repeat_choice':repeatchoice,'lead_attempts':leads,'lead_activated':activated,'lead_unit_microUSD':lead_unit,'capacity_added':extra,'production_capacity':offered_capacity,'chosen_orders':chosen,'new_units':new_units,'repeat_units':repeat_units,'outage':outage,**out,'costs_microUSD':{'capacity':cap_spend,'acquisition':lead_spend,'resource':resource,'onboarding':onboarding,'maintenance':int(reg['fixed_maintenance_monthly_usd']*MICRO)},'funding':{'seed_permitted':launch or funding_mode=='capital_available','strict_earned_before':strict,'growth_budget':grow_budget},'scope':'SIMULATED_BULK_MARKET_NOT_OBSERVED_BUYERS'}
