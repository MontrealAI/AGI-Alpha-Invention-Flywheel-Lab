"""Finite public-information price search; no latent buyer or seed input."""
from __future__ import annotations
import math

PUBLIC_FIELDS = {'anchor_usd', 'autonomous_cost_usd', 'onboarding_cost_usd', 'friction_usd', 'trust', 'rival_trust', 'urgency_value_hour', 'repeat_probability', 'payment_fraction', 'payment_fixed_usd'}


def public_observation(value):
    if not isinstance(value, dict) or set(value) != PUBLIC_FIELDS:
        raise ValueError('EXACT_PUBLIC_PRICING_INFORMATION_REQUIRED')
    for key, number in value.items():
        if type(number) not in {int, float} or not math.isfinite(number) or number < 0:
            raise ValueError('FINITE_PUBLIC_PRICING_INPUT_REQUIRED')
    if value['anchor_usd'] <= 0 or any(value[k] > 1 for k in ['trust', 'rival_trust', 'repeat_probability', 'payment_fraction']):
        raise ValueError('INVALID_PUBLIC_PRICE_RANGE_OR_PROBABILITY')
    return dict(value)


def utilities(value, ours, rival, public, regime):
    anchor = public['anchor_usd']
    quality = .99
    own = quality * public['trust'] * value - ours - public['friction_usd'] - regime['our_hours'] * public['urgency_value_hour']
    other = quality * public['rival_trust'] * value - rival - regime['rival_hours'] * public['urgency_value_hour']
    human = .99 * .96 * value - anchor - 48 * public['urgency_value_hour']
    self_service = .99 * .95 * value - anchor * regime['self_complete_cost_ratio'] - 16 * public['urgency_value_hour']
    return [own, other, human, self_service, 0.]


def probabilities(utilities_, model, temperature):
    if model == 'utility':
        best = max(range(len(utilities_)), key=lambda i: (utilities_[i], -i))
        return [float(i == best) for i in range(len(utilities_))]
    if model != 'logit' or temperature <= 0:
        raise ValueError('SUPPORTED_BUYER_MODEL_REQUIRED')
    top = max(utilities_)
    weights = [math.exp(max(-700, (u - top) / temperature)) for u in utilities_]
    return [w / sum(weights) for w in weights]


def expected_choice(ours, rival, public, regime, model):
    p = [0.] * 5
    for factor in [1.3, 1.7, 2.1, 2.5, 2.9, 3.3, 3.7]:
        row = probabilities(utilities(public['anchor_usd'] * factor, ours, rival, public, regime), model, public['anchor_usd'] * regime['temperature_ratio'])
        p = [a + b / 7 for a, b in zip(p, row)]
    return p


def competitor_best_response(ours, public, regime, model, *, lagged=False):
    public_observation(public)
    cost = public['autonomous_cost_usd'] * regime['rival_cost_multiplier']
    if lagged:
        rival = max(cost * 1.10, public['anchor_usd'] * .85)
        return {'price': rival, 'cost': cost, 'expected_profit': expected_choice(ours, rival, public, regime, model)[1] * (rival - cost), 'response': 'lagged_public_list_price', 'grid_residual': None}
    candidates = [cost * 1.03] + [public['anchor_usd'] * x / 10 for x in range(2, 21, 2)]
    curve = [(expected_choice(ours, p, public, regime, model)[1] * (p - cost), p) for p in candidates]
    gain, selected = max(curve, key=lambda x: (x[0], x[1]))
    if gain <= 0:
        return {'price': public['anchor_usd'] * 10, 'cost': cost, 'expected_profit': 0., 'response': 'no_bid', 'grid_residual': 0.}
    return {'price': selected, 'cost': cost, 'expected_profit': gain, 'response': 'responsive_finite_grid', 'grid_residual': max(x[0] for x in curve) - gain}


def optimize_price(public, regime, model, *, strategic=True, lagged=False):
    public = public_observation(public)
    anchor = public['anchor_usd']
    if not strategic:
        candidates = [anchor * .95]
    else:
        candidates = [anchor * (.2 + i * .05) for i in range(37)]
    curve = []
    def evaluate(price):
        rival = competitor_best_response(price, public, regime, model, lagged=lagged)
        conditional_win = expected_choice(price, rival['price'], public, regime, model)[0]
        exposure = regime['arrival_probability'] * regime['qualification_probability'] * (1 - regime['supplier_outage_probability'])
        win = conditional_win * exposure
        collected = regime['collection_probability'] * (1 - regime['refund_probability'])
        repeat_multiplier = 1 + public['repeat_probability'] + public['repeat_probability'] ** 2
        conditional_net_receipt = collected * price - price * public['payment_fraction'] - public['payment_fixed_usd']
        per_decision = win * conditional_net_receipt - public['autonomous_cost_usd'] - regime['quote_cost_usd']
        immediate = per_decision - win * public['onboarding_cost_usd']
        contribution = repeat_multiplier * per_decision - win * public['onboarding_cost_usd']
        return {'price': round(price, 6), 'win_probability': win, 'conditional_choice_probability_on_exposure': conditional_win, 'public_exposure_probability': exposure, 'expected_lifetime_contribution_per_opportunity': contribution, 'expected_immediate_contribution_per_opportunity': immediate, 'rival': rival, 'cost_rule': 'Production and quote acquisition incurred for every selected opportunity before arrival; conditional fees/onboarding only on purchase. Lifetime score charges production and acquisition at every declared repeat decision, onboarding only once. Future score is never realized revenue.'}
    curve = [evaluate(p) for p in candidates]
    best = max(curve, key=lambda x: (x['expected_lifetime_contribution_per_opportunity'], -x['price']))
    boundary = best['price'] == round(min(candidates), 6) or best['price'] == round(max(candidates), 6)
    if strategic:
        center = best['price']
        refined = [max(anchor * .025, center + anchor * i / 100) for i in range(-5, 6)]
        if boundary:
            refined += [anchor * x / 10 for x in range(1, 41)]
        curve += [evaluate(p) for p in refined]
        best = max(curve, key=lambda x: (x['expected_lifetime_contribution_per_opportunity'], -x['price']))
    no_bid = best['expected_lifetime_contribution_per_opportunity'] <= 0
    return {'price': None if no_bid else best['price'], 'win_probability': 0. if no_bid else best['win_probability'], 'expected_lifetime_contribution_per_opportunity': max(0., best['expected_lifetime_contribution_per_opportunity']), 'expected_immediate_contribution_per_opportunity': -public['autonomous_cost_usd'] - regime['quote_cost_usd'] if no_bid else best['expected_immediate_contribution_per_opportunity'], 'no_bid_option_value_before_commitment': 0., 'rival': best['rival'], 'candidate_curve': curve, 'boundary_triggered': boundary, 'tested_price_range': [min(x['price'] for x in curve), max(x['price'] for x in curve)], 'resolution_usd': anchor * .01, 'grid_profitable_deviation_residual': 0., 'scope': 'Best tested public-distribution finite leader/follower search, with local refinement and NO_BID. Not a market equilibrium, observed price or global continuous optimum. Lifetime expectation is a selection score only; ledger recognizes only actually settled simulated orders.'}


def optimize_bundle(publics, quotes, regime, model, *, strategic=True, coordination_cost_usd=3.):
    if len(publics) < 2 or len(publics) != len(quotes):
        raise ValueError('DISTINCT_BUNDLE_COMPONENTS_REQUIRED')
    if any(q['price'] is None for q in quotes):
        return {'price_factors': [], 'total_price': None, 'win_probability': 0., 'expected_immediate_contribution_per_opportunity': 0.}
    candidates = [.70, .80, .90, .95, 1., 1.05, 1.10] if strategic else [.95]
    curve = []
    for factor in candidates:
        total = sum(q['price'] * factor for q in quotes)
        probability = 0.
        for value_factor in [1.3, 1.7, 2.1, 2.5, 2.9, 3.3, 3.7]:
            rows = [utilities(p['anchor_usd'] * value_factor, q['price'] * factor, q['rival']['price'], p, regime) for p, q in zip(publics, quotes)]
            # Context approval is shared once, instead of counted per component.
            combined = [sum(row[i] for row in rows) for i in range(5)]
            combined[0] += sum(p['friction_usd'] for p in publics[1:])
            probability += probabilities(combined, model, sum(p['anchor_usd'] for p in publics) * regime['temperature_ratio'])[0] / 7
        exposure = regime['arrival_probability'] * regime['qualification_probability'] * (1 - regime['supplier_outage_probability'])
        unconditional_win = probability * exposure
        onboarding_once = publics[0]['onboarding_cost_usd']
        unconditional_cost = sum(p['autonomous_cost_usd'] for p in publics) + coordination_cost_usd + len(publics) * regime['quote_cost_usd']
        conditional_net_receipt = regime['collection_probability'] * (1-regime['refund_probability']) * total - total * publics[0]['payment_fraction'] - sum(p['payment_fixed_usd'] for p in publics) - onboarding_once
        contribution = unconditional_win * conditional_net_receipt - unconditional_cost
        curve.append({'factor': factor, 'total_price': total, 'win_probability': unconditional_win, 'conditional_choice_probability_on_exposure': probability, 'public_exposure_probability': exposure, 'unconditional_attempt_acquisition_coordination_cost': unconditional_cost, 'expected_immediate_contribution_per_opportunity': contribution})
    best = max(curve, key=lambda x: (x['expected_immediate_contribution_per_opportunity'], -x['total_price']))
    return {**best, 'price_factors': [best['factor']] * len(publics), 'candidate_curve': curve, 'scope': 'Joint complete-outcome bundle choice, fixed competitor component quotes, same total obligations. Declared coordination and each component acquisition/attempt cost charged even without sale. Shared context friction counted once. Conditional grid heuristic, not independent markets or equilibrium.'}
