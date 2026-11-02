"""Finite SIM recurring market with persistent relative-choice quantiles.

128 equally spaced preference bins approximate a uniform latent taste. A firm's
bin never changes, including paid reactivation. It chooses us iff its bin lies
below the public logit share against ALL outside options. This rank-preserving
coupling is an authored structural assumption, not identified buyer behavior.
No monthly iid taste redraw, affinity bonus, or MRR-to-logo conversion is used.
"""
from copy import deepcopy
from fractions import Fraction
from math import ceil
from growth066 import policy as legacy
from growth066.money import usd, floor_share, payment
from growth066.market import rng, choice_probabilities, outcomes

BINS=128

def initial_state():return legacy.initial_state()
def zero():return [0]*BINS
def add(a,b):return [x+y for x,y in zip(a,b)]
def sub(a,b):return [x-y for x,y in zip(a,b)]
def cohort(v,**kw):return {'count':sum(v),'bins':v,**kw}
def willing(v,p):return [n if (i+.5)/BINS<p else 0 for i,n in enumerate(v)]
def renewal_probabilities(price,world,month):return choice_probabilities(price,world,month,True)
def population_total(s):return s['untouched']+s['inactive']+s['opted_out']+s['active']+sum(c['count'] for c in s['cooldown']+s['pending_leads'])

def _sample(v,n,random):
    n=min(n,sum(v))
    if not n:return zero()
    return list(map(int,random.multivariate_hypergeometric(v,n)))

def choose_current_price(prices,cost,world,m,new,active,backlog,capacity):
    """Finite quotes, current observed cohorts, public future contact prior only."""
    rows=[]
    for q in prices:
        pn=choice_probabilities(q,world,m)[0]['ours'];pr=renewal_probabilities(q,world,m)[0]['ours']
        n=sum(new)*pn;r=sum(willing(active,pr))*(1-world['relationship_failure_probability'])
        b=sum(c['count'] for c in backlog if q<=c['quote'])
        # No installed demand yet: launch quote uses one public-prior prospect.
        forecast=n+r+b if sum(new)+sum(active)+sum(c['count'] for c in backlog) else pn
        expected=min(forecast,capacity) if capacity else forecast
        margin=world['quality_probability']*world['collection_probability']*(q*(1-world['payment_rate'])-world['payment_fixed_usd'])-cost
        # New-client onboarding is real cost, not a free acquisition subsidy.
        onboarding=world['onboarding_usd']*(n/max(1,n+r+b) if n+r+b else 1)
        value=expected*(margin-onboarding)
        rows.append({'price_usd':q,'expected_contribution_per_eligible_usd':value,'unit_margin_usd':margin,'expected_current_orders':n+r+b})
    best=max(rows,key=lambda x:(x['expected_contribution_per_eligible_usd'],-x['price_usd']))
    return {'selected':best if best['expected_contribution_per_eligible_usd']>0 else None,'tested':rows,'optimality':'finite current-cohort expected contribution; public priors; not global equilibrium'}

def base_propose(state,summary,world,reg,seed,unit_cost,opening,*,grow=True,funding_mode='capital_available',policy_name='balanced',renewal_mode=None):
    mode=renewal_mode or world.get('renewal_mode','corrected')
    if mode=='legacy':return legacy.propose(state,summary,world,reg,seed,unit_cost,opening,grow=grow,funding_mode=funding_mode,policy_name=policy_name)
    if mode!='corrected':raise ValueError('UNKNOWN_RENEWAL_MODE')
    for key in ['reactivation_cooldown_months','backlog_expiry_months']:
        if type(world[key]) is not int or world[key]<1:raise ValueError(key)
    for key in ['contact_optout_probability','relationship_failure_probability']:
        if not 0<=world[key]<=1:raise ValueError(key)
    s=deepcopy(state);m=s['month'];pop=world['reachable_firms']
    if 'population' not in s:
        if m or s['active'] or s['contacted'] or s['pending_leads']:raise ValueError('FRESH_CORRECTED_STATE_REQUIRED')
        # Fixed population quantiles, including deterministic remainder bins.
        v=[((i+1)*pop)//BINS-(i*pop)//BINS for i in range(BINS)]
        s.update(population=pop,untouched=pop,inactive=0,opted_out=0,cooldown=[],lead_attempts_total=0,untouched_bins=v,inactive_bins=zero(),active_bins=zero(),opted_out_bins=zero())
    if s['population']!=pop or population_total(s)!=pop:raise ValueError('POPULATION_CHANGED')
    serial=0
    def exit_pool(v):
        nonlocal serial
        if not sum(v):return
        opt=list(map(int,rng(seed,m,'067-exit-'+str(serial)).binomial(v,world['contact_optout_probability'])));serial+=1
        s['opted_out_bins']=add(s['opted_out_bins'],opt)
        rest=sub(v,opt)
        if sum(rest):s['cooldown'].append(cohort(rest,eligible_month=m+world['reactivation_cooldown_months']))
    cold=[]
    for c in s['cooldown']:
        if c['eligible_month']<=m:s['inactive_bins']=add(s['inactive_bins'],c['bins'])
        else:cold.append(c)
    s['cooldown']=cold
    pending=[];new=zero();ready=[];expired=0
    for c in s['pending_leads']:
        if c['expires']<m:expired+=c['count'];exit_pool(c['bins'])
        elif c['active']>m:pending.append(c)
        elif c['willing']:ready.append(c)
        else:new=add(new,c['bins'])
    p=choose_current_price(reg['price_candidates_usd'],unit_cost,world,m,new,s['active_bins'],ready,s['capacity'])
    quote=p['selected']['price_usd'] if p['selected'] else 0
    pn=choice_probabilities(quote,world,m)[0]['ours'] if quote else 0
    pr=renewal_probabilities(quote,world,m)[0]['ours'] if quote else 0
    expected_new=sum(new)*pn;expected_repeat=sum(willing(s['active_bins'],pr))*(1-world['relationship_failure_probability'])
    expected_backlog=sum(c['count'] for c in ready if quote and quote<=c['quote'])
    expected=ceil(expected_new+expected_repeat+expected_backlog)
    settings=reg['allocation_policies'][policy_name];capacity=s['capacity']
    strict=max(0,min(summary['available'],summary['unrestrictedEarned'],summary['profit']-summary['tailReserve']-summary['custodyReserve']-summary['workingCapital']))
    perunit=usd(unit_cost+world['onboarding_usd']+quote)+payment(usd(quote),world)+200_000
    maintenance=usd(reg['fixed_maintenance_monthly_usd'])
    # Capital remains locked until settlement, then residual until maturity.
    horizon=max(1,ceil((world['settlement_days']+world['tail_days'])/reg['month_days']))
    tail=usd(world['residual_per_unit_usd'])*max(1,ceil(world['tail_days']/reg['month_days']))
    downstream=perunit*horizon+tail
    reserve=maintenance+expected*downstream
    launch=m==0;growth_cash=summary['available'] if launch or funding_mode=='capital_available' else strict
    budget=max(0,floor_share(growth_cash,settings['launch_fraction' if launch else 'growth_cash_fraction'])-reserve) if grow or launch else 0
    saturation=Fraction(pop-sum(s['untouched_bins']),max(1,pop))
    lead_unit=int(usd(world['lead_cost_usd'])*(1+world['acquisition_saturation_cost_factor']*saturation))
    if lead_unit<=0:raise ValueError('PAID_CONTACT_REQUIRED')
    pool=add(s['untouched_bins'],s['inactive_bins']);capunit=usd(world['capacity_unit_setup_usd'])
    if world.get('allocation_mode','liquidity_aware')=='aggressive':
        extra=floor_share(budget,settings['capacity_fraction_of_growth'])//capunit
        leads=min(sum(pool),max(0,(budget-extra*capunit)//lead_unit));provision=0
    else:
        # Prospect provision is a conservative budget hold, never an expense.
        probability=Fraction(str(world['lead_activation']))*Fraction(str(pn))
        lead_provision=ceil(probability*downstream)
        cap_budget=floor_share(budget,settings['capacity_fraction_of_growth'])
        leads=min(sum(pool),max(0,(budget-cap_budget)//(lead_unit+lead_provision)))
        near=expected+ceil(leads*probability)
        financeable=max(0,(summary['available']-maintenance-leads*lead_unit)//downstream)
        extra=min(cap_budget//capunit,max(0,min(near,financeable)-capacity))
        provision=leads*lead_provision
    cap_spend=extra*capunit;capacity+=extra;lead_spend=leads*lead_unit
    # Contacts are sampled without replacement from the same persistent bins.
    contacted=_sample(pool,leads,rng(seed,m,'067-contact'))
    fresh=[]
    for i,n in enumerate(contacted):
        fresh.append(int(rng(seed,m,'067-origin-'+str(i)).hypergeometric(s['untouched_bins'][i],s['inactive_bins'][i],n)) if n else 0)
    s['untouched_bins']=sub(s['untouched_bins'],fresh);s['inactive_bins']=sub(s['inactive_bins'],sub(contacted,fresh))
    activated=list(map(int,rng(seed,m,'067-activation').binomial(contacted,world['lead_activation'])))
    exit_pool(sub(contacted,activated))
    if sum(activated):pending.append(cohort(activated,active=m+1,expires=m+world['channel_expiry_months'],willing=False,repeat=False))
    ours_new=willing(new,pn);ours_repeat=willing(s['active_bins'],pr)
    # One independent relationship disruption hazard, not a second taste draw.
    survivors=list(map(int,rng(seed,m,'067-relationship').binomial(ours_repeat,1-world['relationship_failure_probability'])))
    exit_pool(sub(new,ours_new));exit_pool(sub(s['active_bins'],survivors))
    def report(v,ours,repeat):
        probs,utility=choice_probabilities(quote,world,m,repeat)
        return {'eligible':sum(v),'counts':{'ours':sum(ours),'outside_composite':sum(v)-sum(ours)},'probabilities':probs,'utilities_usd':utility,'choice_model':'persistent_quantile_composite_outside_option'}
    newchoice=report(new,ours_new,False);repeatchoice=report(s['active_bins'],survivors,True)
    for repeat,v in [(False,ours_new),(True,survivors)]:
        if sum(v):ready.append(cohort(v,active=m,expires=m+world['backlog_expiry_months']-1,willing=True,repeat=repeat,quote=quote))
    stable=[]
    for c in ready:
        if not quote or quote>c['quote']:pending.append(c)
        else:stable.append(c)
    ready=sorted(stable,key=lambda c:(c['expires'],c['active'],not c['repeat']))
    outage=bool(rng(seed,m,'outage').random()<world['supplier_outage_probability']);offered=0 if outage else capacity
    cash=max(0,summary['available']-cap_spend-lead_spend-maintenance)
    chosen=min(sum(c['count'] for c in ready),offered,cash//perunit if quote else 0)
    left=chosen;new_units=0;processed=zero()
    for i,c in enumerate(ready):
        n=min(left,c['count']);left-=n;v=_sample(c['bins'],n,rng(seed,m,'067-service-'+str(i)))
        processed=add(processed,v)
        if not c['repeat']:new_units+=n
        rest=sub(c['bins'],v)
        if sum(rest):pending.append({**c,'count':sum(rest),'bins':rest})
    out=outcomes(chosen,world,m,seed)
    accepted=_sample(processed,out['quality_accepted'],rng(seed,m,'067-quality-assignment'))
    exit_pool(sub(processed,accepted))
    s.update(month=m+1,active=sum(accepted),active_bins=accepted,untouched=sum(s['untouched_bins']),inactive=sum(s['inactive_bins']),opted_out=sum(s['opted_out_bins']),contacted=pop-sum(s['untouched_bins']),capacity=capacity,pending_leads=pending,expired_leads=s['expired_leads']+expired,lead_attempts_total=s['lead_attempts_total']+leads)
    totals=add(add(s['untouched_bins'],s['inactive_bins']),add(s['active_bins'],s['opted_out_bins']))
    for c in s['cooldown']+s['pending_leads']:totals=add(totals,c['bins'])
    if totals!=[((i+1)*pop)//BINS-(i*pop)//BINS for i in range(BINS)] or population_total(s)!=pop:raise ValueError('PERSISTENT_POPULATION_NOT_CONSERVED')
    return {'month':m,'state_before':state,'state_after':s,'price_choice':p,'unit_price_usd':quote,'new_choice':newchoice,'repeat_choice':repeatchoice,'lead_attempts':leads,'lead_activated':sum(activated),'lead_unit_microUSD':lead_unit,'capacity_added':extra,'production_capacity':offered,'chosen_orders':chosen,'new_units':new_units,'repeat_units':chosen-new_units,'outage':outage,**out,'costs_microUSD':{'capacity':cap_spend,'acquisition':lead_spend,'resource':usd(unit_cost)*chosen,'onboarding':usd(world['onboarding_usd'])*new_units,'maintenance':maintenance},'funding':{'seed_permitted':launch or funding_mode=='capital_available','strict_earned_before':strict,'growth_budget':budget,'downstream_provision_microUSD':provision,'provision_is_expense':False},'scope':'SIMULATED_BULK_MARKET_NOT_OBSERVED_BUYERS'}


def propose(state,summary,world,reg,seed,unit_cost,opening,**kwargs):
    if kwargs.get("policy_name","balanced")=="finite_game":
        from .game import solve
        return solve(state,summary,world,reg,seed,unit_cost,opening,**kwargs)
    return base_propose(state,summary,world,reg,seed,unit_cost,opening,**kwargs)
