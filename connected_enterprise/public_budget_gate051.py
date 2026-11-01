"""Costed public affordability screening; no private budget or future income."""
SCHEMA = 'connected-public-budget-gate051/v1'


def validate(cfg):
    p=cfg.get('public_budget_gate')
    if p is None:return
    if not isinstance(p,dict) or set(p)!={'schema','daily_cost_microUSD'} or p['schema']!=SCHEMA or type(p['daily_cost_microUSD']) is not int or p['daily_cost_microUSD']<=0:
        raise ValueError('POSITIVE_COSTED_PUBLIC_BUDGET_GATE_REQUIRED')
    if 'complete_offer_policy' not in cfg or 'strategic_policy' not in cfg:
        raise ValueError('PUBLIC_BUDGET_GATE_REQUIRES_COMPLETE_STRATEGIC_MARKET')
    if 'startup_acquisition_policy' in cfg or 'sequence' in cfg.get('strategic_allocation_policy',{}):
        raise ValueError('BUDGET_GATE_STARTUP_SEQUENCE_COMPOSITION_UNAVAILABLE')


def admits(profile, service, observed_spend, cfg, moment):
    """Conservative upper support: retain an offer if ANY public atom can pay."""
    if 'public_budget_gate' not in cfg:return True
    from .buyer_income import public_accrued
    if type(observed_spend) is not int or observed_spend<0:
        raise ValueError('NONNEGATIVE_PUBLIC_OBSERVED_SPEND_REQUIRED')
    budget=max(a['budget_microUSD'] for a in profile['atoms'])+public_accrued(cfg,moment)
    return budget-observed_spend >= min(profile['price_grids'][service])
