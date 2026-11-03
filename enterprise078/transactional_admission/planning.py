"""Conditional predecision maximin comparison, never a future-outcome oracle."""
from .choice import money, participation, registered_bundles, registered_rows, subset_key, partner_participation
from .offer import COSTS


def plan(rows, bundles, *, wallets, available, earned, sunk_acquisition,
         decision_time, scenarios):
    """Choose one fixed package using ONLY explicitly declared assumptions.

    Rows have id/buyer/price/terms_id and optional partner. Each scenario supplies
    exact-package buyers, collection_lower_bounds, complete PACKAGE costs, partners and
    assumptions_known_at. Realized collected/accepted observations are forbidden.
    Bounds and participation are authored assumptions, not guaranteed future facts
    or observations. They must already be declared by decision_time; timestamps
    are caller assertions, not independently authenticated evidence.

    Joint value is gross buyer value of the complete contracted outcome, after
    disclosed outcome risks/friction but before its quoted payment. Outside
    options are net utilities on the same scale. terms_id identifies the complete
    contract, including contingent fulfillment/payment/refund obligations. Every
    candidate is a mutually exclusive proposed arrangement, not a public menu.
    costs maps each canonical full-bundle key to its full COSTS vector, including
    joint construction/coordination, partner compensation and contingent burdens.
    Shared costs must not be omitted or double counted by summing row estimates.
    Each per-offer collection lower bound must hold in every registered package
    containing that offer. Package-dependent payment terms need distinct IDs.
    """
    for value in (available, earned, sunk_acquisition, decision_time):
        money(value)
    if not isinstance(wallets, dict):
        raise ValueError('EXPLICIT_WALLETS_REQUIRED')
    for value in wallets.values():
        money(value)
    rows = list(rows)
    required = {'id', 'buyer', 'price', 'terms_id'}
    for row in rows:
        if not isinstance(row, dict) or not required <= set(row) or set(row) - required - {'partner'}:
            raise ValueError('PREDECISION_OFFER_FIELDS_ONLY')
    by_id = registered_rows(rows, wallets)
    bundles = registered_bundles(bundles, by_id)
    if not isinstance(scenarios, dict) or not scenarios:
        raise ValueError('REGISTERED_PREDECISION_SCENARIOS_REQUIRED')
    fields = {'buyers', 'collection_lower_bounds', 'costs', 'partners', 'assumptions_known_at'}
    for name, scenario in scenarios.items():
        if not isinstance(name, str) or not name:
            raise ValueError('SCENARIO_ID_REQUIRED')
        if not isinstance(scenario, dict) or set(scenario) != fields:
            raise ValueError('PREDECISION_SCENARIO_FIELDS_ONLY')
        if money(scenario['assumptions_known_at']) > decision_time:
            raise ValueError('FUTURE_INFORMATION_FORBIDDEN')
        if not all(isinstance(scenario[k], dict) for k in fields - {'assumptions_known_at'}):
            raise ValueError('EXPLICIT_SCENARIO_MAPS_REQUIRED')
        # Validate unselected input too; unknown entries remain unknown, not zero.
        if set(scenario['collection_lower_bounds']) - set(by_id):
            raise ValueError('UNREGISTERED_SCENARIO_OFFER')
        if set(scenario['costs']) - {subset_key(ids) for ids in bundles}:
            raise ValueError('UNREGISTERED_SCENARIO_BUNDLE')
        for ident, lower in scenario['collection_lower_bounds'].items():
            if lower is not None and money(lower) > by_id[ident]['price']:
                raise ValueError('COLLECTION_BOUND_EXCEEDS_PRICE')
        for costs in scenario['costs'].values():
            if not isinstance(costs, dict) or set(costs) != set(COSTS):
                raise ValueError('COMPLETE_COST_CATEGORIES_REQUIRED')
            for cost in costs.values():
                if cost is not None:
                    money(cost)
    outcomes = [{'bundle': [], 'feasible': True, 'reasons': [],
                 'scenario_nets_microUSD': {name: -sunk_acquisition for name in scenarios},
                 'worst_case_net_microUSD': -sunk_acquisition}]
    for ids in bundles:
        selected = [by_id[ident] for ident in ids]
        reasons = set()
        commitments = {}
        for row in selected:
            buyer = row['buyer']
            commitments[buyer] = commitments.get(buyer, 0) + row['price']
        if any(amount > wallets[buyer] for buyer, amount in commitments.items()):
            reasons.add('SHARED_BUYER_WALLET_EXCEEDED')
        nets = {}
        for name, scenario in sorted(scenarios.items()):
            reasons.update(reason + ':' + name for reason in participation(selected, scenario['buyers']))
            reasons.update(reason + ':' + name for reason in partner_participation(selected, scenario['partners']))
            costs = scenario['costs'].get(subset_key(ids))
            unknown = costs is None or any(value is None for value in costs.values())
            total = None if unknown else sum(costs.values())
            if unknown:
                reasons.add('UNKNOWN_COMPLETE_COST:' + name)
            receipts = 0
            for row in selected:
                ident = row['id']
                lower = scenario['collection_lower_bounds'].get(ident)
                if lower is None:
                    reasons.add('COLLECTION_BOUND_UNESTABLISHED:' + name + ':' + ident)
                    unknown = True
                else:
                    receipts += lower
            if total is not None and total > min(available, earned):
                reasons.add('BUNDLE_NOT_EARNED_FUNDED:' + name)
            nets[name] = None if unknown else receipts - total - sunk_acquisition
        worst = None if any(value is None for value in nets.values()) else min(nets.values())
        outcomes.append({'bundle': ids, 'feasible': not reasons,
                         'reasons': sorted(reasons), 'scenario_nets_microUSD': nets,
                         'worst_case_net_microUSD': worst})
    best = outcomes[0]
    for outcome in outcomes[1:]:
        if (outcome['feasible'] and outcome['worst_case_net_microUSD'] is not None
                and outcome['worst_case_net_microUSD'] > best['worst_case_net_microUSD']):
            best = outcome
    return {'selected_bundle': list(best['bundle']),
            'worst_case_net_microUSD': best['worst_case_net_microUSD'],
            'outcomes': outcomes, 'information_timing': 'predecision_assumptions',
            'decision_time': decision_time, 'native_catalog_admitted': False,
            'native_mutations': 0, 'observed_customer_evidence': False,
            'paid_commerce': False, 'forecast_expected_net': None,
            'scope': 'conditional maximin on supplied finite scenarios; not calibrated demand, a guarantee, native profit or authority'}
