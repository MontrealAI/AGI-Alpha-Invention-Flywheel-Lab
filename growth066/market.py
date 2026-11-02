"""Explicit finite SIM market: paid reach is never an order or a funding source."""
from __future__ import annotations
from math import exp
import hashlib
import json
import numpy as np


def rng(seed,month,label):
    raw=json.dumps([seed,month,label],separators=(',',':')).encode()
    return np.random.default_rng(int.from_bytes(hashlib.sha256(raw).digest()[:8],'big'))


def choice_probabilities(price, world, month, repeat=False):
    """Seller sees these public prior utilities, never realized buyer draws.

    Random-utility logit is an authored behavior assumption, not observed demand.
    Every alternative includes normal software; no manual-only human strawman.
    """
    value=world['packet_value_usd']
    rival=world['rival_price_usd']*(world['imitation_price_factor'] if month>=world['imitation_month'] else 1)
    own_quality=world['quality_probability']
    effort=world['repeat_effort_usd'] if repeat else world['first_effort_usd']
    utility={'ours':value*own_quality-price-effort,
             'human_conventional':value*.995-world['human_complete_price_usd'],
             'human_ai':value*.99-world['hybrid_price_usd'],
             'autonomous_rival':value*world['rival_quality']-rival,
             'self_service':value*world['self_quality']-world['self_complete_cost_usd'],
             'no_purchase':0.}
    temperature=world['heterogeneity_usd'];mx=max(utility.values())
    weights={k:exp((u-mx)/temperature) for k,u in utility.items()};total=sum(weights.values())
    return {k:v/total for k,v in weights.items()},utility


def draw_choices(n,price,world,month,seed,repeat=False):
    probs,utility=choice_probabilities(price,world,month,repeat)
    names=sorted(probs)
    counts=rng(seed,month,'repeat' if repeat else 'new').multinomial(n,[probs[k] for k in names]).tolist()
    return {'eligible':n,'counts':dict(zip(names,counts)),'probabilities':probs,'utilities_usd':utility}


def choose_price(prices,unit_cost,world,month,repeat=False):
    rows=[]
    for p in prices:
        prob,_=choice_probabilities(p,world,month,repeat)
        # Actual failure work is charged separately; provision prices only paid releases.
        margin=p*(1-world['payment_rate'])-world['payment_fixed_usd']-unit_cost
        expected=prob['ours']*(world['quality_probability']*world['collection_probability']*p*(1-world['payment_rate'])-world['payment_fixed_usd']-unit_cost)
        rows.append({'price_usd':p,'expected_contribution_per_eligible_usd':expected,'unit_margin_usd':margin})
    best=max(rows,key=lambda r:(r['expected_contribution_per_eligible_usd'],-r['price_usd']))
    return {'selected':best if best['expected_contribution_per_eligible_usd']>0 else None,'tested':rows,'optimality':'best tested myopic price in public-prior random-utility model; not Nash/global'}


def outcomes(count,world,month,seed):
    accepted=int(rng(seed,month,'quality').binomial(count,world['quality_probability']))
    collected=int(rng(seed,month,'collection').binomial(accepted,world['collection_probability']))
    return {'attempted':count,'quality_accepted':accepted,'quality_failed':count-accepted,'collected_units':collected,'uncollected_units':accepted-collected}


def available_after_protection(summary):
    """Strict earned rather than seed-backed available cash for growth."""
    return max(0,min(summary['available'],summary['unrestrictedEarned'],summary['profit']-summary['tailReserve']-summary['custodyReserve']-summary['workingCapital']))
