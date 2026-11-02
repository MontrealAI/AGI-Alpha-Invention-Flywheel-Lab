"""Exact finite pessimistic Stackelberg enumeration, not a global Nash claim."""
from copy import deepcopy
from functools import lru_cache
import json
from fractions import Fraction
from commercial.ledger import canonical,digest
from growth066.market import choice_probabilities
from .planning import expected_net


def micro(value):
    x=Fraction(str(value))*1_000_000
    return x.numerator//x.denominator


def solve(state,summary,world,reg,seed,unit_cost,opening,**kwargs):
    args=[state,summary,world,reg,seed,unit_cost,opening,kwargs]
    # Pure source-bound memoization; public replay in a new process recomputes.
    return json.loads(_solve(canonical(args).decode()))

@lru_cache(maxsize=256)
def _solve(encoded):
    from .policy import base_propose
    state,summary,world,reg,seed,cost,opening,kwargs=json.loads(encoded)
    m=state['month'];g=reg['finite_game'];factor=world['imitation_price_factor'] if m>=world['imitation_month'] else 1
    reference=world['rival_price_usd']*factor
    # Rival has a nonnegative-margin cost-price option; prices are SIM choices.
    rival_cost=world['rival_unit_cost_usd']
    floor=(rival_cost+world['payment_fixed_usd'])/(1-world['payment_rate'])
    quotes=sorted(set([round(max(floor,reference*x),6) for x in g['rival_quote_multipliers']]+[round(floor+0.000001,6)]))
    actions=[]
    for name in g['seller_allocation_candidates']:
      for price in reg['price_candidates_usd']:
       for invest in [False,True]:
        cells=[]
        for rq in quotes:
            w=deepcopy(world);w['rival_price_usd']=rq/factor
            r=deepcopy(reg);r['price_candidates_usd']=[price]
            kw=dict(kwargs);kw['policy_name']=name
            kw['grow']=bool(kwargs.get('grow',True) and invest)
            # A no-invest action is available even at launch (legacy grow=False
            # alone deliberately retains initial launch spending).
            if not invest:
                r['allocation_policies'][name]['launch_fraction']=0
                r['allocation_policies'][name]['growth_cash_fraction']=0
            p=base_propose(state,summary,w,r,seed,cost,opening,**kw)
            seller=expected_net(p,w,r,cost)
            probs=choice_probabilities(p['unit_price_usd'] or price,w,m)[0]
            if not p['unit_price_usd']:
                outside=1-probs['ours'];probs={k:(0 if k=='ours' else v/outside) for k,v in probs.items()}
            # Competitor objective is contribution per public eligible prospect;
            # no secured buyer, audience size, financing or revenue is invented.
            rival=micro(probs['autonomous_rival']*(rq*(1-w['payment_rate'])-w['payment_fixed_usd']-rival_cost))
            cells.append((rival,seller,rq,p,w))
        best_rival=max(c[0] for c in cells)
        best_responses=[c for c in cells if c[0]==best_rival]
        chosen=min(best_responses,key=lambda c:(c[1],c[2]))
        actions.append({'action':{'allocation':name,'price_usd':price,'invest':invest,'withdraw_if_nonpositive':True},'seller_value_microUSD':chosen[1],'rival_best_value_microUSD':best_rival,'rival_quote_usd':chosen[2],'rival_regret_microUSD':best_rival-chosen[0],'proposal':chosen[3],'world':chosen[4]})
    winner=min(actions,key=lambda x:(-x['seller_value_microUSD'],x['action']['invest'],x['action']['price_usd'],x['action']['allocation']))
    p=winner['proposal'];p['game_certificate']={
       'concept':'PESSIMISTIC_FINITE_STACKELBERG_LEADER_OPTIMUM',
       'seller_action_count':len(actions),'rival_action_count':len(quotes),
       'seller_action':winner['action'],'actual_seller_quote_usd':p['unit_price_usd'],'rival_quote_usd':winner['rival_quote_usd'],
       'seller_value_microUSD':winner['seller_value_microUSD'],
       'seller_optimality_gap_microUSD':max(a['seller_value_microUSD'] for a in actions)-winner['seller_value_microUSD'],
       'rival_best_response_regret_microUSD':winner['rival_regret_microUSD'],
       'all_action_values':[{'action':a['action'],'seller_value_microUSD':a['seller_value_microUSD'],'rival_quote_usd':a['rival_quote_usd']} for a in actions],
       'effective_world':winner['world'],'planning_horizon_months':reg['planning_horizon_months'],
       'not_global_or_empirical_optimality':True}
    return canonical(p).decode()
