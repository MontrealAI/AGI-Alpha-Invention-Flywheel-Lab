"""Bounded paid contact-menu hypotheses; no free reach or spending authority."""
from fractions import Fraction
from commercial.ledger import digest

def validate_policy(policy,contracts):
    if not isinstance(policy,dict) or set(policy)!={'schema','contract_ids','conversion_bps'} or policy['schema']!='connected-channel-menu/v1':raise ValueError('EXPLICIT_CHANNEL_MENU_POLICY_REQUIRED')
    ids=policy['contract_ids']
    if not isinstance(ids,list) or not 1<=len(ids)<=4 or ids!=sorted(set(ids)) or any(x not in contracts for x in ids):raise ValueError('BOUNDED_DECLARED_CHANNEL_MENU_REQUIRED')
    if type(policy['conversion_bps']) is not int or not 0<=policy['conversion_bps']<=10000:raise ValueError('DECLARED_CHANNEL_CONVERSION_HYPOTHESIS_REQUIRED')
    return policy

def menu_options(cfg,arm,day,buyers,contacts,live,margins,slots,scenarios):
    """Inputs are dated public operating history, not future exposure/buyer draws.

    Existing live rights consume a conservative shared reach allowance. All new
    expansion options share one benefit identity, forbidding unvalidated additive
    channel/channel or channel/capacity forecasts. Actual contacts remain subject
    to ChannelBook's shared fatigue, cooldown, overlap, expiry and realization.
    """
    from .joint_planning import investment_option
    policy=validate_policy(cfg['channel_menu_policy'],cfg['channels'])
    if arm=='baseline' or not margins or sum(margins)<=0 or slots<=0:return []
    remaining=cfg['horizon_days']-day;options=[]
    for ident in policy['contract_ids']:
        terms=cfg['channels'][ident]
        owned=set(sorted(buyers)[:terms['owned_audience_count']])
        if sum(x['contract_id']==ident for x in live)>=terms['max_active_tranches']:continue
        days=min(terms['duration_days'],remaining-terms['lead_days'])
        if days<=0:continue
        reachable=sum(i not in owned and (not b['onboarded'] or not b['active']) and len(contacts.get(i,[]))<terms['max_contacts_per_customer'] for i,b in buyers.items())
        if not reachable:continue
        potential=Fraction(terms['slots_per_day']*days*terms['activation_reliability_bps']*terms['realization_bps']*(10000-terms['overlap_bps']),10000**3)
        live_reach=Fraction(0)
        for x in live:
            t=cfg['channels'][x['contract_id']];active_days=max(0,min(day+terms['lead_days']+days,x['expiry_day'])-max(day+terms['lead_days'],x['activation_day']))
            live_reach+=Fraction(t['slots_per_day']*active_days*t['activation_reliability_bps']*t['realization_bps']*(10000-t['overlap_bps']),10000**3)
        contacts_forecast=min(potential,max(Fraction(0),Fraction(reachable)-live_reach))
        deliveries=min(Fraction(slots*days),contacts_forecast*Fraction(policy['conversion_bps'],10000))
        # No unpaid future capacity assumed. Extra attempts/qualification costs
        # are charged in the hypothesis as well as actual native operation.
        benefit=deliveries*Fraction(sum(margins),len(margins))*Fraction(10000-cfg['profit_tax_bps'],10000)-terms['slots_per_day']*days*cfg['exposure_cost']-contacts_forecast*cfg['qualification_cost']
        invoice=terms['price_microUSD']+terms['support_microUSD'];net=benefit.numerator//benefit.denominator-invoice
        if net<=0:continue
        o=investment_option('channel-'+str(day)+'-'+ident,'acquisition',invoice,net,scenarios,day,terms)
        o['execution']['contract_id']=ident
        o['execution']['forecast_scope']='Declared conversion hypothesis, observed settled margins, after-modeled-tax haircut, full attempt costs, shared live reach saturation, current capacity only; not income or calibrated demand.'
        o['execution']['forecast_inputs']={'reachable':reachable,'live_reach_fraction':str(live_reach),'new_contact_fraction':str(contacts_forecast),'delivery_fraction':str(deliveries),'current_slots':slots,'conversion_bps':policy['conversion_bps']}
        options.append(o)
    return options
