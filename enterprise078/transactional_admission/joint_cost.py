"""Compose the pinned buyer review with complete scenario-specific costs.

Retrospective sensitivity only: the source-pinned reviewer consumes supplied
collections and acceptance outcomes. Its ranking is NOT a causal decision rule.
Use planning.plan for declared predecision assumptions; never pass future
realized outcomes to a prospective policy. Historical outcomes remain unchanged.
"""
import copy
from enterprise078_review.joint_choice import review
from .offer import COSTS


def evaluate(rows, bundles, *, wallets, available, earned, sunk_acquisition, scenarios):
    if not isinstance(scenarios, dict) or not scenarios:
        raise ValueError('REGISTERED_COST_SCENARIOS_REQUIRED')
    ids = {r['id'] for r in rows}
    cases = {}
    for name, scenario in scenarios.items():
        if not isinstance(scenario, dict) or set(scenario) != {'choice','costs'}:
            raise ValueError('EXPLICIT_CHOICE_AND_COMPLETE_COSTS_REQUIRED')
        costs=scenario['costs']
        if not isinstance(costs,dict) or set(costs) != ids:
            raise ValueError('COMPLETE_SCENARIO_OFFER_COSTS_REQUIRED')
        amended=copy.deepcopy(rows)
        for row in amended:
            if not isinstance(costs[row['id']],dict) or set(costs[row['id']]) != set(COSTS):
                raise ValueError('COMPLETE_SCENARIO_COST_CATEGORIES_REQUIRED')
            row['costs']=copy.deepcopy(costs[row['id']])
        cases[name]=review(amended,bundles,wallets=wallets,available=available,earned=earned,
                           sunk_acquisition=sunk_acquisition,scenarios={name:scenario['choice']})
    results=[]
    for index, bundle in enumerate([[]]+bundles):
        per_case={name:r['outcomes'][index] for name,r in cases.items()}
        known=all(r['robust_net_microUSD'] is not None for r in per_case.values())
        results.append({'bundle':bundle,'feasible':all(r['feasible'] for r in per_case.values()),
                        'worst_net_microUSD':min(r['robust_net_microUSD'] for r in per_case.values()) if known else None,
                        'cases':per_case})
    winner=results[0]
    for r in results[1:]:
        if r['feasible'] and r['worst_net_microUSD'] is not None and r['worst_net_microUSD']>winner['worst_net_microUSD']:
            winner=r
    return {'selected_bundle':winner['bundle'],'conditional_worst_net_microUSD':winner['worst_net_microUSD'],
            'outcomes':results,'native_catalog_admitted':False,'native_mutations':0,
            'forecast_expected_net':None,'information_timing':'retrospective',
            'prospective_selected_bundle':None,
            'scope':'authored retrospective sensitivity, not a prospective decision rule, native profit or observed demand'}
