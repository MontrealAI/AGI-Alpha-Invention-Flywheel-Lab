"""Finite registered bundle comparison, not a ledger, sale or demand forecast."""
from .offer import COSTS, compare


def money(n):
    if type(n) is not int or n < 0:
        raise ValueError('EXACT_NONNEGATIVE_MONEY_REQUIRED')
    return n


def evaluate(rows, bundles, *, wallets, available, earned, sunk_acquisition):
    """Amounts are microUSD; wallets are one common finite buyer scenario.

    Every row supplies disjoint complete incremental costs and an explicit
    collected amount for this scenario (including zero on nonpayment). Sunk
    acquisition is outside these costs and charged even to no-entry. Available
    and earned cash are AFTER that sunk expenditure. No receipts are booked.
    Caller registers bundles before inspection; this function never searches
    subsets, supplies missing demand or executes its recommendation.
    """
    money(available); money(earned); money(sunk_acquisition)
    for n in wallets.values(): money(n)
    by_id = {}
    for row in rows:
        if not isinstance(row['id'], str) or not row['id'] or row['id'] in by_id:
            raise ValueError('UNIQUE_OFFER_REQUIRED')
        if row['buyer'] not in wallets:
            raise ValueError('EXPLICIT_FINITE_WALLET_REQUIRED')
        if row['response'] not in ('uncontacted', 'refused', 'consented'):
            raise ValueError('EXPLICIT_RESPONSE_REQUIRED')
        money(row['collected'])
        if row['collected'] > money(row['price']):
            raise ValueError('COLLECTION_CANNOT_EXCEED_PRICE')
        # Validates full cost shape and exact amounts even for skipped offers.
        compare(costs=row['costs'],price=row['price'],buyer_value=row['value'],
                buyer_budget=wallets[row['buyer']],outside_surplus=row['outside'],
                available=available,earned=earned,consent=row['response']=='consented',
                acceptance=row['accepted'])
        by_id[row['id']] = row
    outcomes = [{'bundle': [], 'feasible': True, 'reasons': [],
                 'scenario_net_microUSD': -sunk_acquisition,
                 'incremental_cost_microUSD': 0, 'collections_microUSD': 0}]
    seen = {()}
    for ids in bundles:
        key = tuple(sorted(ids))
        if len(set(ids)) != len(ids) or key in seen or any(i not in by_id for i in ids):
            raise ValueError('DISTINCT_REGISTERED_BUNDLE_REQUIRED')
        seen.add(key)
        reasons = []; commitments = {}; total = 0; collections = 0; unknown = False
        for ident in ids:
            row = by_id[ident]
            quote = compare(costs=row['costs'],price=row['price'],buyer_value=row['value'],
                buyer_budget=wallets[row['buyer']],outside_surplus=row['outside'],
                available=available,earned=earned,consent=row['response']=='consented',
                acceptance=row['accepted'])
            # Native prohibition always survives separately below. Individual
            # price surplus is not a collection forecast; evaluate actual scenario collections.
            reasons.extend(r for r in quote['reasons'] if r not in (
                'NATIVE_CATALOG_TRANSITION_UNQUALIFIED','NO_POSITIVE_COMPLETE_SURPLUS'))
            if quote['whole_delivery_microUSD'] is None: unknown = True
            else: total += quote['whole_delivery_microUSD']
            commitments[row['buyer']] = commitments.get(row['buyer'],0)+row['price']
            collections += row['collected']
        if any(v > wallets[k] for k,v in commitments.items()): reasons.append('SHARED_BUYER_WALLET_EXCEEDED')
        if not unknown and total > min(available,earned): reasons.append('BUNDLE_NOT_EARNED_FUNDED')
        outcomes.append({'bundle':list(ids),'feasible':not reasons,
            'reasons':sorted(set(reasons)), 'scenario_net_microUSD':None if unknown else collections-total-sunk_acquisition,
            'incremental_cost_microUSD':None if unknown else total,'collections_microUSD':collections})
    # Strict improvement over no entry; deterministic registered order on ties.
    best = outcomes[0]
    for out in outcomes[1:]:
        if out['feasible'] and out['scenario_net_microUSD'] is not None and out['scenario_net_microUSD'] > best['scenario_net_microUSD']:
            best = out
    return {'outcomes':outcomes,'selected_bundle':best['bundle'],
            'selected_scenario_net_microUSD':best['scenario_net_microUSD'],
            'native_catalog_admitted':False,'native_mutations':0,'forecast_expected_net':None,
            'scope':'authored finite scenario; not buyer evidence, native profit or executable authority'}
