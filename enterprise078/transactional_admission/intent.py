"""Finite registered bundle comparison, not a ledger, sale or demand forecast."""
from .offer import compare
from .choice import money, participation, registered_rows, registered_bundles, partner_participation


def evaluate(rows, bundles, *, wallets, available, earned, sunk_acquisition,
             buyer_choices=None, partners=None):
    """Retrospective diagnostic only, NEVER a prospective decision rule.

    Amounts are microUSD; wallets are one common finite buyer scenario.
    Exact-package buyer choices bind the quote and terms; per-row values and
    scalar outside options are legacy diagnostics, not joint utility evidence.
    Missing whole-buyer/partner evidence fails closed. No-entry wins ties.

    Every row supplies disjoint complete incremental costs and an explicit
    collected amount for this scenario (including zero on nonpayment). Sunk
    acquisition is outside these costs and charged even to no-entry. Available
    and earned cash are AFTER that sunk expenditure. No receipts are booked.
    Caller registers bundles before inspection; this function never searches
    subsets, supplies missing demand or executes any action.
    """
    money(available); money(earned); money(sunk_acquisition)
    for n in wallets.values(): money(n)
    rows = list(rows)
    by_id = registered_rows(rows, wallets)
    bundles = registered_bundles(bundles, by_id)
    partners = {} if partners is None else partners
    if not isinstance(partners, dict):
        raise ValueError("EXPLICIT_PARTNER_MAP_REQUIRED")
    for row in rows:
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
    for ids in bundles:
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
                'NATIVE_CATALOG_TRANSITION_UNQUALIFIED', 'NO_POSITIVE_COMPLETE_SURPLUS',
                'BUYER_OUTSIDE_OPTION_WINS_OR_TIES', 'NO_VOLUNTARY_CONSENT'))
            if quote['whole_delivery_microUSD'] is None: unknown = True
            else: total += quote['whole_delivery_microUSD']
            commitments[row['buyer']] = commitments.get(row['buyer'],0)+row['price']
            collections += row['collected']
        reasons.extend(participation([by_id[i] for i in ids], buyer_choices))
        reasons.extend(partner_participation([by_id[i] for i in ids], partners))
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
            'information_timing':'retrospective', 'prospective_selected_bundle':None,
            'scope':'authored retrospective diagnostic; not a decision rule, buyer evidence, native profit or authority'}
