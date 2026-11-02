"""Bounded public-prior forecast for native investment metadata, never cash."""
from fractions import Fraction
from growth066.market import choice_probabilities
from .money import usd

def expected_net(proposal,world,reg,unit_cost):
    if 'game_certificate' in proposal:return proposal['game_certificate']['seller_value_microUSD']
    q=proposal['unit_price_usd'];m=proposal['month']
    if not q:return -(sum(v for k,v in proposal['costs_microUSD'].items() if k!='maintenance')+usd(reg['fixed_maintenance_monthly_usd'])*reg['planning_horizon_months'])
    selected=proposal['price_choice']['selected'] or {}
    # This quantity precedes realization of quality/collection/outage draws.
    existing=selected.get('expected_current_orders',proposal['new_choice']['eligible']*choice_probabilities(q,world,m)[0]['ours']+proposal['repeat_choice']['eligible']*choice_probabilities(q,world,m,True)[0]['ours'])
    new=proposal['lead_attempts']*world['lead_activation']*choice_probabilities(q,world,m+1)[0]['ours']
    capacity=proposal['state_after']['capacity']
    baseprob=max(1e-12,choice_probabilities(q,world,m,True)[0]['ours'])
    margin=world['quality_probability']*world['collection_probability']*(q*(1-world['payment_rate'])-world['payment_fixed_usd'])-unit_cost
    value=-float((proposal['costs_microUSD']['acquisition']+proposal['costs_microUSD']['capacity'])/1_000_000)
    hazard=world.get('relationship_failure_probability',world.get('monthly_churn',0))
    for t in range(reg['planning_horizon_months']):
        relative=min(1,choice_probabilities(q,world,m+t,True)[0]['ours']/baseprob)
        orders=min(capacity,(existing+(new if t else 0))*(1-hazard)**t*world['quality_probability']**t*relative)
        value+=orders*(1-world['supplier_outage_probability'])*margin-reg['fixed_maintenance_monthly_usd']
    value-=(existing+new)*world['onboarding_usd']
    # Conservative downward conversion; monetary ledger never uses floats.
    ratio=Fraction(str(value))*1_000_000
    return ratio.numerator//ratio.denominator
