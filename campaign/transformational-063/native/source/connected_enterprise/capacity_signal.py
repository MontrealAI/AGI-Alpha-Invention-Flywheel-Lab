"""Capacity-only marginal opportunities in an already selected finite basket.

No reservation, executable recommendation or realized-demand claim is returned.
All non-capacity constraints and the current selected actions stay fixed.
"""
from fractions import Fraction


def _score(options,risk):
    ids={o['id'] for o in options}
    joints=[j for j in risk['interactions'] if set(j['members'])<=ids]
    upfront=sum(o['upfront_cost'] for o in options)
    net={s:sum(o['future_net_cash'][s] for o in options)+sum(j['net_cash'][s] for j in joints)-upfront for s in risk['scenarios']}
    downside=max(0,-min(net.values()))
    expected=sum(Fraction(w,10000)*net[s] for s,w in risk['scenarios'].items())
    return expected-Fraction(risk['downside_penalty_bps'],10000)*downside,expected,downside,joints


def capacity_only(record,candidate):
    """True only for a feasible, value-improving addition blocked by units."""
    chosen=record['decision']['selected_options'];risk=record['riskpolicy'];summary=record['observation']['summary']
    if summary.get('investmentStopped',False):return False
    if candidate['kind']!='delivery' or not candidate['authorized'] or candidate['future_net_cash'] is None:return False
    if candidate['id'] in {o['id'] for o in chosen}:return False
    used=sum(o['execution'].get('capacity_units',1) for o in chosen if o['kind']=='delivery')
    if used+candidate['execution'].get('capacity_units',1)<=record['max_delivery_slots']:return False
    basket=[*chosen,candidate];ids={o['id'] for o in basket}
    if any(not set(o['requires'])<=ids for o in basket):return False
    groups=[o['exclusive_group'] for o in basket if o['exclusive_group'] is not None]
    if len(groups)!=len(set(groups)):return False
    work=[k for o in basket if o['kind']=='delivery' for k in o['execution'].get('work_keys',[])]
    if len(work)!=len(set(work)):return False
    score,expected,downside,joints=_score(basket,risk)
    benefits=[x for o in basket for x in o['benefit_ids']]+[x for j in joints for x in j['benefit_ids']]
    if len(benefits)!=len(set(benefits)):return False
    reserves=[o['upfront_cost']+o['execution'].get('cash_lock',0)+max(max(o['later_liabilities'].values()),max(0,-min(o['future_net_cash'].values()))) for o in basket]
    interaction_reserve=sum(max(0,-min(j['net_cash'].values())) for j in joints)
    earned=max(0,summary['unrestrictedEarned']-record['earned_deduction'])
    budget=min(summary['available'],risk['authorized_allocation'],earned if not record['allow_seed'] else summary['available'])
    if sum(reserves)+interaction_reserve>budget:return False
    if record['allow_seed'] and sum(r for o,r in zip(basket,reserves) if o['execution']['funding']=='EARNED')+interaction_reserve>earned:return False
    return downside<=risk['worst_loss_limit'] and expected>=1 and score>_score(chosen,risk)[0]


def capacity_declined_customers(record):
    from .strategic_commerce import _action_options
    selected={o['execution']['customer_id'] for o in record['decision']['selected_options'] if o['kind']=='delivery'}
    options=_action_options(record['observation'],record['deliveries'],record['investments'],record['riskpolicy'])
    return {o['execution']['customer_id'] for o in options if o['kind']=='delivery' and o['execution']['customer_id'] not in selected and capacity_only(record,o)}
