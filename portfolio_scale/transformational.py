"""Read-only, bounded capital planning; no ledger, payment or success authority."""
from __future__ import annotations

import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

SCHEMA = 'alpha-transformational-allocation/v1'


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def integer(value: Any, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError('NONNEGATIVE_INTEGER_REQUIRED')
    return value


def fields(value: Any, expected: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError('EXACT_SCHEMA_REQUIRED')


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        raise ValueError('NONEMPTY_BOUNDED_IDENTIFIER_REQUIRED')
    return value


def read_json(path: Path) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('DUPLICATE_FIELD')
            result[key] = value
        return result
    if path.is_symlink() or not path.is_file():
        raise ValueError('REGULAR_INPUT_FILE_REQUIRED')
    with path.open('rb') as stream:
        raw = stream.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('INPUT_BYTE_LIMIT')
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


def choose(request: dict, universe: dict) -> dict:
    """Exact subset comparison within a declared planning budget, not market optimality."""
    fields(request, {'schema', 'scope', 'currency', 'funding', 'scenarios', 'actions',
                     'synergies', 'max_states', 'worst_loss_limit', 'downside_penalty_bps'})
    if (request['schema'], request['scope'], request['currency']) != (
            SCHEMA, 'SIMULATED', 'simulated-microUSD'):
        raise ValueError('SIMULATED_SCOPE_AND_UNIT_REQUIRED')
    funding = request['funding']
    fields(funding, {'source', 'available', 'unrestrictedEarned', 'authorized_allocation'})
    identifier(funding['source'])
    for name in ('available', 'unrestrictedEarned', 'authorized_allocation'):
        if funding[name] is not None:
            integer(funding[name])
    scenarios = request['scenarios']
    if not isinstance(scenarios, dict) or not scenarios or len(scenarios) > 128:
        raise ValueError('BOUNDED_SCENARIOS_REQUIRED')
    for name, weight in scenarios.items():
        identifier(name)
        integer(weight, 1)
    if sum(scenarios.values()) != 10000:
        raise ValueError('SCENARIO_WEIGHTS_MUST_SUM_TO_10000')
    penalty = integer(request['downside_penalty_bps'])
    loss_limit = integer(request['worst_loss_limit'])
    max_states = integer(request['max_states'], 1)
    if max_states > 1_048_576:
        raise ValueError('PLANNING_RESOURCE_LIMIT')
    catalog = {job['id'] for job in universe['jobs']}
    if len(catalog) != len(universe['jobs']):
        raise ValueError('DUPLICATE_CATALOG_ID')
    actions, ids, unknown = request['actions'], set(), []
    if not isinstance(actions, list):
        raise ValueError('ACTION_LIST_REQUIRED')
    for action in actions:
        fields(action, {'id', 'lane', 'catalog_id', 'cost', 'requires', 'exclusive_group',
                        'cash_returns', 'evidence', 'authorized'})
        ident = identifier(action['id'])
        if ident in ids:
            raise ValueError('DUPLICATE_ACTION')
        ids.add(ident)
        if action['lane'] not in {'delivery', 'instrument', 'research'}:
            raise ValueError('UNKNOWN_LANE')
        if type(action['authorized']) is not bool:
            raise ValueError('EXPLICIT_AUTHORIZATION_FLAG_REQUIRED')
        if action['lane'] == 'delivery' and action['catalog_id'] not in catalog:
            raise ValueError('UNKNOWN_EXISTING_PORTFOLIO_SERVICE')
        if action['lane'] != 'delivery' and action['catalog_id'] is not None:
            raise ValueError('NON_DELIVERY_CATALOG_REFERENCE')
        integer(action['cost'])
        identifier(action['evidence'])
        if action['exclusive_group'] is not None:
            identifier(action['exclusive_group'])
        deps = action['requires']
        if not isinstance(deps, list) or len(set(deps)) != len(deps) or ident in deps:
            raise ValueError('INVALID_DEPENDENCIES')
        for dependency in deps:
            identifier(dependency)
        returns = action['cash_returns']
        if returns is None:
            unknown.append(ident)
        else:
            fields(returns, set(scenarios))
            for value in returns.values():
                integer(value)
    by_id = {a['id']: a for a in actions}
    for action in actions:
        if not set(action['requires']) <= ids:
            raise ValueError('MISSING_DEPENDENCY')
    visiting, visited = set(), set()
    def visit(ident):
        if ident in visiting:
            raise ValueError('CYCLIC_DEPENDENCY')
        if ident in visited:
            return
        visiting.add(ident)
        for dependency in by_id[ident]['requires']:
            visit(dependency)
        visiting.remove(ident)
        visited.add(ident)
    for ident in ids:
        visit(ident)
    synergies, benefit_ids = request['synergies'], set()
    if not isinstance(synergies, list):
        raise ValueError('SYNERGY_LIST_REQUIRED')
    for extra in synergies:
        fields(extra, {'id', 'members', 'incremental_cash', 'evidence'})
        benefit_id = identifier(extra['id'])
        members = extra['members']
        if benefit_id in benefit_ids:
            raise ValueError('DUPLICATE_JOINT_BENEFIT')
        benefit_ids.add(benefit_id)
        if (not isinstance(members, list) or len(set(members)) != len(members)
                or len(members) < 2 or not set(members) <= ids):
            raise ValueError('INVALID_JOINT_MEMBERS')
        identifier(extra['evidence'])
        fields(extra['incremental_cash'], set(scenarios))
        for value in extra['incremental_cash'].values():
            integer(value)
    output = {'schema': SCHEMA, 'request_sha256': digest(request),
              'catalog_sha256': digest(universe), 'scope': 'SIMULATED_PLANNING_ONLY',
              'selected': [], 'cost': 0, 'joint_benefits': [],
              'net_cash_by_scenario': dict.fromkeys(scenarios, 0),
              'expected_net_cash': '0', 'risk_adjusted_value': '0',
              'unknown_return_actions': sorted(unknown), 'funding_source': funding['source'],
              'funding_independently_audited_here': False,
              'execute_authorized': False, 'commercial_success': 'NOT_EVALUATED',
              'capability_improvement': 'NOT_EVALUATED', 'physical_impact': 'NOT_EVALUATED',
              'optimality_scope': 'NONE', 'states_evaluated': 0}
    if any(funding[key] is None for key in ('available', 'unrestrictedEarned', 'authorized_allocation')):
        return {**output, 'decision': 'UNKNOWN_FUNDING', 'budget': None}
    budget = min(funding['available'], funding['unrestrictedEarned'], funding['authorized_allocation'])
    output['budget'] = budget
    eligible = [a for a in actions if a['authorized'] and a['cash_returns'] is not None]
    if len(eligible) >= max_states.bit_length():
        return {**output, 'decision': 'DECOMPOSE_OR_RAISE_AUTHORIZED_PLANNING_BUDGET'}
    best_key = (Fraction(0), Fraction(0), 0)
    for mask in range(1 << len(eligible)):
        output['states_evaluated'] += 1
        chosen = [a for i, a in enumerate(eligible) if mask & (1 << i)]
        selected = {a['id'] for a in chosen}
        cost = sum(a['cost'] for a in chosen)
        if cost > budget or any(not set(a['requires']) <= selected for a in chosen):
            continue
        groups = [a['exclusive_group'] for a in chosen if a['exclusive_group'] is not None]
        if len(groups) != len(set(groups)):
            continue
        extras = [b for b in synergies if set(b['members']) <= selected]
        net = {s: sum(a['cash_returns'][s] for a in chosen)
                   + sum(b['incremental_cash'][s] for b in extras) - cost for s in scenarios}
        downside = max(0, -min(net.values()))
        if downside > loss_limit:
            continue
        expected = sum((Fraction(scenarios[s], 10000) * net[s] for s in scenarios), Fraction(0))
        score = expected - Fraction(penalty, 10000) * downside
        key = (score, expected, -cost)
        if key > best_key:
            best_key = key
            output.update(selected=sorted(selected), cost=cost,
                          joint_benefits=sorted(b['id'] for b in extras),
                          net_cash_by_scenario=net, expected_net_cash=str(expected),
                          risk_adjusted_value=str(score))
    output.update(decision='CANDIDATE_ALLOCATION' if output['selected'] else 'RETAIN_CASH',
                  optimality_scope='EXACT_FINITE_SHORTLIST_UNDER_SUPPLIED_SCENARIOS',
                  unallocated_budget=budget-output['cost'])
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--universe', type=Path, default=Path(__file__).with_name('universe.json'))
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = choose(read_json(args.input), read_json(args.universe))
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write('\n')
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        parser.exit(2, f'REFUSED: {exc}\n')
    print(result['decision'] + '; planning only, no execution authority')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
