"""Ordinary public competitive pricing; no private buyer state or sale guarantee."""
from __future__ import annotations

MICRO=1_000_000


def price(anchor,legacy_price,public_rival_price,base_resource_cost,payment_bps,payment_fixed,recent_own_choices):
    terms={'anchor':anchor,'legacy_price':legacy_price,'public_rival_price':public_rival_price,'base_resource_cost':base_resource_cost,'payment_bps':payment_bps,'payment_fixed':payment_fixed}
    if any(type(v) is not int or v<0 for v in terms.values()) or anchor<1 or legacy_price<1 or payment_bps>10000:
        raise ValueError('BOUNDED_INTEGER_PUBLIC_PRICING_TERMS_REQUIRED')
    if not isinstance(recent_own_choices,list) or any(type(choice) is not bool for choice in recent_own_choices):
        raise ValueError('ONLY_PUBLIC_BOOLEAN_OWN_OFFER_OUTCOMES_ALLOWED')
    if payment_bps==10000:return None
    contribution_margin=MICRO
    required=base_resource_cost+payment_fixed+contribution_margin
    denominator=10000-payment_bps
    floor=(required*10000+denominator-1)//denominator
    wins=sum(recent_own_choices);count=len(recent_own_choices)
    responsive=count>0 and wins<count and wins*5<2*count
    target=min(legacy_price,public_rival_price-250_000) if responsive else legacy_price
    if target<floor:
        if floor>legacy_price:return None
        target=floor
        reason='direct_resource_floor_under_public_competition' if responsive else 'direct_resource_floor'
    else:reason='public_competition_after_observed_declines' if responsive else 'retained_public_price'
    fee=(target*payment_bps+9999)//10000+payment_fixed
    contribution=target-base_resource_cost-fee
    if contribution<contribution_margin:raise ValueError('INTERNAL_DIRECT_CONTRIBUTION_FLOOR_FAILURE')
    return {'schema':'agi-alpha/connected014-public-price/v1','price':target,'floor':floor,'reason':reason,'public_terms':terms,'past_own_offer_count':count,'past_own_wins':wins,'past_own_declines':count-wins,'past_own_win_fraction':wins/count if count else None,'competitive_response':responsive,'minimum_direct_contribution_microUSD':contribution_margin,'forecast_direct_contribution_microUSD':contribution,'forecast_payment_fee_microUSD':fee,'scope':'Public-price action and direct-resource forecast only; complete enterprise profit and voluntary buyer choice remain separate.'}
