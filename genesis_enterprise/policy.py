"""Exact, no-invention-bias commercial choices, not a second financial ledger.

All amounts are integer micro-USD. Inputs are explicit scenario assumptions;
none is promoted to observed demand or a universally optimal strategy.
"""
from __future__ import annotations
import hashlib
import json
import math


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def loads(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('DUPLICATE_JSON_FIELD')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


def money(value):
    if type(value) is not int or value < 0:
        raise ValueError('NONNEGATIVE_INTEGER_MICRO_USD_REQUIRED')
    return value


def choose(offer, tools, *, available, earned, seed_allowed):
    """Solve the declared finite posted-price/buyer-outside-option game.

    Quotes must strictly beat both outside quotes; the buyer declines on a tie.
    Fixed already-incurred costs are not charged again in marginal selection.
    Candidate costs include checking and tool maintenance. Unknown access loses
    no money: it is ineligible, rather than optimistically treated as installed.
    """
    if type(seed_allowed) is not bool:
        raise ValueError('EXPLICIT_SEED_AUTHORITY_REQUIRED')
    money(available); money(earned)
    if earned > available:
        raise ValueError('EARNED_CANNOT_EXCEED_AVAILABLE')
    for field in ('value', 'outside_utility', 'friction', 'budget', 'rival', 'self_service', 'fee', 'reserve'):
        money(offer[field])
    if not isinstance(offer['prices'], list) or not offer['prices']:
        raise ValueError('NONEMPTY_PRICE_MENU_REQUIRED')
    for p in offer['prices']:
        money(p)
    if not isinstance(tools, list) or not tools:
        raise ValueError('NONEMPTY_TOOL_PORTFOLIO_REQUIRED')
    seen = set()
    accepted, excluded = [], []
    for tool in tools:
        if (not isinstance(tool['id'], str) or not tool['id'] or tool['id'] in seen
                or tool['mode'] not in ('conventional', 'pooled')):
            raise ValueError('UNIQUE_QUALIFIED_EXECUTOR_REQUIRED')
        seen.add(tool['id'])
        cost = money(tool['production']) + money(tool['maintenance'])
        if cost == 0:
            raise ValueError('POSITIVE_COMPLETE_MODELED_RESOURCE_COST_REQUIRED')
        if tool['access'] not in ('qualified_local', 'unverified', 'restricted', 'revoked'):
            raise ValueError('EXPLICIT_ACCESS_STATE_REQUIRED')
        if tool['access'] != 'qualified_local':
            excluded.append({'tool': tool['id'], 'reason': 'ACCESS_NOT_QUALIFIED'})
            continue
        # A reserve is protected, not itself an expense. Its opportunity cost
        # belongs in an independently specified complete-cost assumption.
        if cost + offer['reserve'] > available:
            excluded.append({'tool': tool['id'], 'reason': 'INSUFFICIENT_AVAILABLE_CASH'})
            continue
        if not seed_allowed and cost + offer['fee'] > earned:
            excluded.append({'tool': tool['id'], 'reason': 'INSUFFICIENT_EARNED_FUNDS'})
            continue
        ceiling = min(offer['budget'], offer['value'] - offer['outside_utility'] - offer['friction'])
        for price in sorted(set(offer['prices'])):
            if price > ceiling or price >= offer['rival'] or price >= offer['self_service']:
                continue
            # Validated native terms require price >= 200,000 microUSD, so
            # default pre-settlement collateral is the whole price. The fee
            # is paid at offer time, before collateral and production. Existing
            # tail obligations are already excluded from available cash.
            if price + offer['fee'] + cost > available:
                continue
            contribution = price - cost - offer['fee']
            if contribution > 0:
                accepted.append({'tool': tool['id'], 'mode': tool['mode'], 'price': price,
                    'resource_cost': cost, 'contribution': contribution,
                    'buyer_surplus': offer['value'] - offer['outside_utility'] - offer['friction'] - price})
    accepted.sort(key=lambda x: (-x['contribution'], x['resource_cost'], x['tool'], x['price']))
    return {'decision': 'TRADE_IN_MODEL' if accepted else 'NO_ENTRY',
            'selected': accepted[0] if accepted else None, 'excluded': excluded,
            'feasible_count': len(accepted),
            'scope': 'EXACT_FINITE_POSTED_PRICE_MODEL_NOT_OBSERVED_MARKET',
            'optimality_gap_in_declared_menu': 0}


def independently_choose(offer, tools, *, available, earned, seed_allowed):
    """Separate reference enumeration; does not call choose or reuse its list."""
    rows = []
    for price in set(offer['prices']):
        if not (price <= offer['budget'] and
                price + offer['friction'] + offer['outside_utility'] <= offer['value'] and
                price < min(offer['rival'], offer['self_service'])):
            continue
        for t in tools:
            c = t['production'] + t['maintenance']
            gain = price - c - offer['fee']
            if (t['access'] == 'qualified_local' and c + offer['reserve'] <= available
                    and price + offer['fee'] + c <= available
                    and (seed_allowed or c + offer['fee'] <= earned) and gain > 0):
                rows.append((-gain, c, t['id'], price, t['mode']))
    if not rows:
        return None
    neg, cost, tool, price, mode = min(rows)
    return {'tool': tool, 'mode': mode, 'price': price, 'resource_cost': cost,
            'contribution': -neg,
            'buyer_surplus': offer['value'] - offer['outside_utility'] - offer['friction'] - price}


def improvement_decision(pairs, *, alpha, practical_margin, candidate_error, baseline_error):
    """Fixed-sample width-two Hoeffding gate on independent paired campaigns.

    A caller must separately establish independence, freeze/exposure and monetary
    conversion. This helper cannot certify those premises. Repeated testing needs
    a shared error allocation; it is not an anytime or unlimited-retry gate.
    """
    if not pairs or not 0 < alpha < 1:
        raise ValueError('NONEMPTY_PAIRS_AND_VALID_ERROR_ALLOCATION_REQUIRED')
    for value in (practical_margin, candidate_error, baseline_error):
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError('FINITE_NONNEGATIVE_ERROR_OR_MARGIN_REQUIRED')
    seen, gains = set(), []
    for row in pairs:
        if row['campaign_id'] in seen or not row['campaign_id']:
            raise ValueError('DISTINCT_CAMPAIGN_REPLICATION_REQUIRED')
        seen.add(row['campaign_id'])
        for key in ('candidate', 'baseline'):
            v = row[key]
            if type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1:
                raise ValueError('BOUNDED_PAIRED_SCORE_REQUIRED')
        gains.append(row['candidate'] - row['baseline'])
    mean = math.fsum(gains) / len(gains)
    lower = mean - math.sqrt(2 * math.log(1 / alpha) / len(gains))
    corrected = lower - candidate_error - baseline_error
    return {'n_campaigns': len(gains), 'mean_gain': mean, 'lower_bound': lower,
            'calibration_corrected_lower_bound': corrected,
            'decision': 'ELIGIBLE_IF_PREMISES_VALID' if corrected > practical_margin else 'RETAIN_INCUMBENT',
            'self_improvement_established': False}
