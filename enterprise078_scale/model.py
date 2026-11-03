"""Declared synthetic buyer environment and public-only ordinary policy.

No live customers, prices, revenues, or hidden real-world information are used.
"""
from __future__ import annotations
import hashlib
from commercial.ledger import canonical

USD = 1_000_000

def atom(protocol, *parts):
    key = canonical([protocol['seed'], *parts])
    return int.from_bytes(hashlib.sha256(key).digest()[:8], 'big')

def cost(protocol, world, name):
    return protocol['costs_USD'][name] * world['cost_multiplier'] * USD

def capital(protocol, world):
    if not world.get('financing_available', True):
        return 0
    required = sum(cost(protocol, world, name) for name in (
        'research_and_failed_search', 'construction_and_integration', 'equity_issuance',
        'base_capacity_annual', 'direct_channel_per_period', 'contact',
        'preparation_production', 'preparation_support', 'shutdown'))
    required += 3 * cost(protocol, world, 'maintenance_per_period')
    required += max(protocol['quote_menu_USD']['preparation']) * USD + 200_000
    if 'capital_override_USD' in world:
        return world['capital_override_USD'] * USD
    return next((n * USD for n in protocol['capital_menu_USD'] if n * USD >= required), 0)

def opportunity(protocol, period, channel, slot):
    buyer = (period * 3 + slot + channel * 2) % protocol['buyer_pool']
    ident = f'scale078-p{period:02d}-c{channel}-s{slot}'
    kind = 'preparation' if period < 2 or slot == 0 else 'characterization'
    request = {'id': ident, 'kind': kind, 'family': 'both_capabilities'}
    if kind == 'preparation':
        request.update(samples=2 + period % 4, components=2 + slot % 2,
                       quantity=3 + (period + slot) % 7)
    else:
        request.update(hidden_threshold=1 + (period * 7 + slot * 11) % 64,
                       response_model='monotone_step')
    return {'id': ident, 'buyer': f'buyer-{buyer:04d}', 'period': period,
            'channel': channel, 'slot': slot, 'request': request}

def opportunities(protocol):
    return [opportunity(protocol, t, c, s) for t in range(protocol['periods'])
            for c, count in enumerate((protocol['direct_contacts_per_period'],
                                       protocol['partner_contacts_per_period'])) for s in range(count)]

def public_market(protocol, world, kind, period, past_quotes):
    base = protocol['public_outside_USD'][kind] * USD
    reference = base * world['price_multiplier_basis_points'] // 10_000
    # A one-period-lag rival responds only to a previously published quote.
    previous = [q for q in past_quotes if q['kind'] == kind and q['period'] < period]
    rival = reference
    if period >= 4 and previous:
        rival = min(reference, max(base // 2, previous[-1]['quote'] * 95 // 100))
    return {'kind': kind, 'self_service': reference, 'rival_ai': rival,
            'human_conventional': reference * 3 // 2,
            'human_plus_ai': reference * 11 // 10,
            'observed_at_period': period}

def quote(protocol, world, public):
    # The policy receives public alternatives, never buyer values or future atoms.
    kind = public['kind']
    marginal = cost(protocol, world, kind + '_production') + cost(protocol, world, kind + '_support')
    marginal += cost(protocol, world, 'contact') + cost(protocol, world, 'repair')
    ceiling = min(public[k] for k in ('self_service', 'rival_ai', 'human_conventional', 'human_plus_ai'))
    eligible = [q * USD for q in protocol['quote_menu_USD'][kind]
                if q * USD < ceiling and q * USD * (10_000 - protocol['payment_fee_basis_points']) // 10_000 > marginal]
    return max(eligible, default=None)

def buyer_budget(protocol, buyer):
    return protocol['buyer_budget_USD'][atom(protocol, 'budget', buyer) % len(protocol['buyer_budget_USD'])] * USD

def buyer_choice(protocol, world, offer, public, price, spent):
    buyer, period = offer['buyer'], offer['period']
    balance = buyer_budget(protocol, buyer) - spent
    need = atom(protocol, 'need', buyer, period) % 10_000 < world['need_basis_points']
    multiplier = protocol['buyer_value_multipliers_basis_points'][atom(protocol, 'value', buyer, period) % 3]
    value = protocol['public_outside_USD'][public['kind']] * USD * multiplier // 10_000
    options = {'no_purchase': 0}
    if need:
        for name in ('self_service', 'rival_ai', 'human_conventional', 'human_plus_ai'):
            if balance >= public[name]:
                options[name] = value - public[name]
    ours = value - price if need and balance >= price else -1
    alternative, best = max(options.items(), key=lambda x: x[1])
    accepted = ours > best
    return {'accepted': accepted, 'outside_choice': alternative, 'remaining_budget': balance,
            'own_surplus': ours, 'outside_surplus': best, 'need': need,
            'budget': buyer_budget(protocol, buyer), 'scope': 'PRIVATE_SYNTHETIC_ENVIRONMENT_NOT_SELLER_INPUT'}

def fulfillment(protocol, world, ident):
    return {'fault': atom(protocol, 'fault', ident) % 10_000 < world['failure_basis_points'],
            'nonpayment': atom(protocol, 'nonpayment', ident) % 10_000 < world['nonpayment_basis_points']}
