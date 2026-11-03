"""Independent finite-policy acceptance and conventional exact construction.

No candidate-constructor import is permitted here. A complete declared model
family is an assumption; an observationally identical omitted mechanism can
still defeat a recipe. Neither method qualifies physical process operation.
"""
from __future__ import annotations

import copy
from functools import lru_cache
import hashlib
import json
import random


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest()


def _keys(value, expected, name):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError('INDEPENDENT_EXACT_FIELDS:' + name)


def _integer(value, minimum=None):
    if type(value) is not int or (minimum is not None and value < minimum):
        raise ValueError('INDEPENDENT_EXACT_INTEGER_REQUIRED')


def _named_rows(rows, minimum, maximum, fields, label):
    if type(rows) is not list or not minimum <= len(rows) <= maximum:
        raise ValueError('INDEPENDENT_DECLARED_DIMENSIONS:' + label)
    identities = []
    for row in rows:
        _keys(row, fields, label)
        if type(row['id']) is not str or not row['id'].strip():
            raise ValueError('INDEPENDENT_NONEMPTY_ID:' + label)
        identities.append(row['id'])
    if len(set(identities)) != len(identities):
        raise ValueError('INDEPENDENT_UNIQUE_IDS:' + label)
    return identities


def inspect_request(request):
    _keys(request, {'schema', 'name', 'ambition', 'currency', 'models', 'experiments',
                    'recipes', 'observations', 'target_minimum', 'max_total_cost_cents',
                    'max_experiments', 'consent'}, 'request')
    if request['schema'] != 'omega/process-request/v1' or request['currency'] != 'USD':
        raise ValueError('INDEPENDENT_SCHEMA_OR_CURRENCY')
    if any(type(request[k]) is not str or not request[k].strip() for k in ('name', 'ambition')):
        raise ValueError('INDEPENDENT_AMBITION_AND_NAME_REQUIRED')
    if type(request['consent']) is not bool:
        raise ValueError('INDEPENDENT_EXPLICIT_CONSENT_REQUIRED')
    _integer(request['target_minimum'], 1)
    _integer(request['max_total_cost_cents'], 0)
    _integer(request['max_experiments'], 0)
    if request['max_experiments'] > 4:
        raise ValueError('INDEPENDENT_REGISTERED_EXPERIMENT_BOUND')
    exps = _named_rows(request['experiments'], 0, 8, {'id', 'cost_cents'}, 'experiment')
    recipes = _named_rows(request['recipes'], 1, 8, {'id', 'cost_cents'}, 'recipe')
    _named_rows(request['models'], 1, 8, {'id', 'responses', 'yields'}, 'model')
    for row in request['experiments'] + request['recipes']:
        _integer(row['cost_cents'], 0)
    for model in request['models']:
        _keys(model['responses'], exps, 'responses')
        _keys(model['yields'], recipes, 'yields')
        for value in [*model['responses'].values(), *model['yields'].values()]:
            _integer(value)
    if type(request['observations']) is not list:
        raise ValueError('INDEPENDENT_OBSERVATIONS_LIST_REQUIRED')
    for row in request['observations']:
        _keys(row, {'experiment_id', 'value'}, 'observation')
        if type(row['experiment_id']) is not str or row['experiment_id'] not in exps:
            raise ValueError('INDEPENDENT_KNOWN_OBSERVATION_REQUIRED')
        _integer(row['value'])
    return request


def _surviving(request):
    return tuple(i for i, model in enumerate(request['models'])
                 if all(model['responses'][row['experiment_id']] == row['value']
                        for row in request['observations']))


def _empty_policy(request, status):
    return {'schema': 'omega/process-policy/v1', 'request_sha256': _digest(request),
            'status': status, 'worst_cost_cents': None, 'tree': None}


def conventional_policy(request):
    """Complete conventional decision-tree optimization on this finite contract.

    Independently written dynamic programming considers every permitted next
    test and every recipe. This exact control is permitted ordinary reuse and
    identical information, rather than a passive or myopic straw baseline.
    """
    inspect_request(request)
    if not request['consent']:
        return _empty_policy(request, 'BUYER_DECLINED')
    surviving = _surviving(request)
    if not surviving:
        return _empty_policy(request, 'MODEL_MISMATCH')
    observed = {r['experiment_id'] for r in request['observations']}
    remaining = tuple(i for i, exp in enumerate(request['experiments']) if exp['id'] not in observed)
    models, tests, recipes = request['models'], request['experiments'], request['recipes']

    @lru_cache(None)
    def solve(possible, available, depth):
        choices = []
        for recipe in recipes:
            if all(models[i]['yields'][recipe['id']] >= request['target_minimum'] for i in possible):
                choices.append((recipe['cost_cents'], {'kind': 'produce', 'recipe_id': recipe['id']}))
        if depth:
            for test_index in available:
                test = tests[test_index]
                groups = {}
                for model_index in possible:
                    y = models[model_index]['responses'][test['id']]
                    groups.setdefault(y, []).append(model_index)
                if len(groups) == 1:
                    continue
                children, costs = {}, []
                for response, group in sorted(groups.items()):
                    result = solve(tuple(group), tuple(i for i in available if i != test_index), depth - 1)
                    if result is None:
                        break
                    costs.append(result[0])
                    children[str(response)] = result[1]
                else:
                    choices.append((test['cost_cents'] + max(costs),
                                    {'kind': 'test', 'experiment_id': test['id'], 'branches': children}))
        if not choices:
            return None
        return min(choices, key=lambda row: (row[0], json.dumps(row[1], sort_keys=True, separators=(',', ':'))))

    optimum = solve(surviving, remaining, request['max_experiments'])
    if optimum is None or optimum[0] > request['max_total_cost_cents']:
        return _empty_policy(request, 'NO_QUALIFIED_POLICY')
    return {'schema': 'omega/process-policy/v1', 'request_sha256': _digest(request),
            'status': 'QUALIFIED_POLICY', 'worst_cost_cents': optimum[0], 'tree': copy.deepcopy(optimum[1])}


def verify_policy(request, policy):
    """Verify the delivered policy by replaying every compatible declared model."""
    inspect_request(request)
    _keys(policy, {'schema', 'request_sha256', 'status', 'worst_cost_cents', 'tree'}, 'policy')
    if policy['schema'] != 'omega/process-policy/v1' or policy['request_sha256'] != _digest(request):
        raise ValueError('INDEPENDENT_REQUEST_BINDING_MISMATCH')
    if policy['status'] != 'QUALIFIED_POLICY':
        if policy['status'] not in {'BUYER_DECLINED', 'MODEL_MISMATCH', 'NO_QUALIFIED_POLICY'}:
            raise ValueError('INDEPENDENT_UNKNOWN_POLICY_STATUS')
        if policy['tree'] is not None or policy['worst_cost_cents'] is not None:
            raise ValueError('INDEPENDENT_REFUSAL_WITH_DELIVERY')
        actual = conventional_policy(request)
        if actual['status'] != policy['status']:
            raise ValueError('INDEPENDENT_UNSUPPORTED_REFUSAL')
        return {'accepted': False, 'refusal_verified': True, 'status': policy['status'],
                'scope': 'FINITE_MODEL_REFUSAL_NOT_PROOF_OF_PHYSICAL_IMPOSSIBILITY'}
    if not request['consent']:
        raise ValueError('INDEPENDENT_BUYER_DECLINED')
    possible = _surviving(request)
    if not possible:
        raise ValueError('INDEPENDENT_MODEL_MISMATCH')
    _integer(policy['worst_cost_cents'], 0)
    tests = {row['id']: row for row in request['experiments']}
    recipes = {row['id']: row for row in request['recipes']}
    observed = {row['experiment_id'] for row in request['observations']}
    paths = []

    def visit(node, group, used, cost, trace):
        if type(node) is not dict:
            raise ValueError('INDEPENDENT_POLICY_NODE_REQUIRED')
        if node.get('kind') == 'produce':
            _keys(node, {'kind', 'recipe_id'}, 'production')
            if type(node['recipe_id']) is not str or node['recipe_id'] not in recipes:
                raise ValueError('INDEPENDENT_KNOWN_RECIPE_REQUIRED')
            total = cost + recipes[node['recipe_id']]['cost_cents']
            if total > request['max_total_cost_cents']:
                raise ValueError('INDEPENDENT_COST_BUDGET_EXCEEDED')
            for i in group:
                model = request['models'][i]
                actual_yield = model['yields'][node['recipe_id']]
                if actual_yield < request['target_minimum']:
                    raise ValueError('INDEPENDENT_TARGET_FAILED:' + model['id'])
                paths.append({'model_id': model['id'], 'recipe_id': node['recipe_id'],
                              'yield': actual_yield, 'cost_cents': total, 'experiments': trace})
            return total
        if node.get('kind') != 'test':
            raise ValueError('INDEPENDENT_KNOWN_NODE_KIND_REQUIRED')
        _keys(node, {'kind', 'experiment_id', 'branches'}, 'test')
        name = node['experiment_id']
        if type(name) is not str or name not in tests:
            raise ValueError('INDEPENDENT_KNOWN_TEST_REQUIRED')
        if name in used or name in observed:
            raise ValueError('INDEPENDENT_EXPERIMENT_REPEATED')
        if len(used) >= request['max_experiments']:
            raise ValueError('INDEPENDENT_EXPERIMENT_BUDGET_EXCEEDED')
        groups = {}
        for i in group:
            groups.setdefault(str(request['models'][i]['responses'][name]), []).append(i)
        _keys(node['branches'], groups, 'all_observation_branches')
        running_cost = cost + tests[name]['cost_cents']
        if running_cost > request['max_total_cost_cents']:
            raise ValueError('INDEPENDENT_COST_BUDGET_EXCEEDED')
        totals = []
        for response, members in groups.items():
            totals.append(visit(node['branches'][response], tuple(members), used | {name}, running_cost,
                                trace + [{'experiment_id': name, 'value': int(response)}]))
        return max(totals)

    actual_cost = visit(policy['tree'], possible, set(), 0, [])
    if actual_cost != policy['worst_cost_cents']:
        raise ValueError('INDEPENDENT_REPORTED_COST_MISMATCH')
    return {'accepted': True, 'request_sha256': _digest(request), 'policy_sha256': _digest(policy),
            'worst_cost_cents': actual_cost, 'models_covered': len(possible), 'paths': paths,
            'scope': 'DECLARED_FINITE_MODELS_ONLY_NOT_PHYSICAL_VALIDATION_OR_OPEN_WORLD_GUARANTEE',
            'authority': []}


def independent_execution(request, policy, actual_responses, actual_yields):
    """Challenge a model-valid policy using independent measured/oracle outcomes.

    Matching predicted test outcomes cannot rule out an omitted mechanism. The
    terminal result is accepted only if the actual production yield also passes.
    This test helper does not operate hardware or establish its measurement rights.
    """
    accepted = verify_policy(request, policy)
    if not accepted['accepted']:
        return {'status': policy['status'], 'production_accepted': False, 'cost_cents': 0,
                'experiments': [], 'scope': 'INDEPENDENT_AUTHORED_ORACLE_ONLY'}
    tests = {x['id']: x for x in request['experiments']}
    recipes = {x['id']: x for x in request['recipes']}
    _keys(actual_responses, tests, 'actual_responses')
    _keys(actual_yields, recipes, 'actual_yields')
    for value in [*actual_responses.values(), *actual_yields.values()]:
        _integer(value)
    for observation in request['observations']:
        if actual_responses[observation['experiment_id']] != observation['value']:
            return {'status': 'MODEL_MISMATCH', 'production_accepted': False, 'cost_cents': 0,
                    'experiments': [], 'scope': 'INDEPENDENT_AUTHORED_ORACLE_ONLY'}
    node, cost, trace = policy['tree'], 0, []
    while node['kind'] == 'test':
        name = node['experiment_id']
        value = actual_responses[name]
        cost += tests[name]['cost_cents']
        trace.append({'experiment_id': name, 'value': value})
        if str(value) not in node['branches']:
            return {'status': 'MODEL_MISMATCH', 'production_accepted': False, 'cost_cents': cost,
                    'experiments': trace, 'scope': 'INDEPENDENT_AUTHORED_ORACLE_ONLY'}
        node = node['branches'][str(value)]
    recipe = node['recipe_id']
    cost += recipes[recipe]['cost_cents']
    yielded = actual_yields[recipe]
    valid = yielded >= request['target_minimum']
    return {'status': 'ACCEPTED' if valid else 'PRODUCTION_REJECTED', 'production_accepted': valid,
            'recipe_id': recipe, 'yield': yielded, 'cost_cents': cost, 'experiments': trace,
            'scope': 'INDEPENDENT_AUTHORED_ORACLE_ONLY'}


def unfamiliar_cases():
    """18 procedural holdouts; authored by evaluator before candidate execution."""
    rng = random.Random(2026110317)
    cases = []
    for index in range(18):
        exps = [{'id': 'test' + str(i), 'cost_cents': rng.randrange(0, 10)}
                for i in range(rng.randrange(1, 5))]
        recipes = [{'id': 'recipe' + str(i), 'cost_cents': rng.randrange(1, 38)}
                   for i in range(rng.randrange(2, 4))]
        models = [{'id': 'model' + str(i),
                   'responses': {x['id']: rng.randrange(-1, 3) for x in exps},
                   'yields': {x['id']: rng.randrange(0, 16) for x in recipes}}
                  for i in range(rng.randrange(2, 6))]
        observations = []
        if index % 3 == 0:
            observations = [{'experiment_id': exps[0]['id'],
                             'value': models[-1]['responses'][exps[0]['id']]}]
        cases.append({'schema': 'omega/process-request/v1', 'name': 'Independent finite case ' + str(index),
                      'ambition': 'Accept a minimum finite-model yield under an exact total resource budget.',
                      'currency': 'USD', 'models': models, 'experiments': exps, 'recipes': recipes,
                      'observations': observations, 'target_minimum': rng.randrange(5, 14),
                      'max_total_cost_cents': rng.randrange(5, 55), 'max_experiments': rng.randrange(0, 5),
                      'consent': True})
    return cases
