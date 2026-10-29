LANGUAGE = 'discovery-policy/v1'
FEATURES = ('gain', 'cost', 'rarity', 'redundancy', 'breadth', 'remaining')
OPERATIONS = ('add', 'sub', 'mul', 'div', 'min', 'max')
KINDS = ('measure', 'represent', 'construct', 'repair')
MAX_DEPTH, MAX_NODES, MAX_ACTIONS = 6, 47, 256
OMEGA_PROGRAMS_SHA256 = 'daaf229882ea07b25202db9e0a7325ec34f37baf83dec6fdd3fe3a7066163fa5'


def _finite(value, bound=1000000000):
    return type(value) in (int, float) and value == value and abs(value) <= bound


def _name(value):
    return type(value) is str and 0 < len(value) <= 120 and all(x.isalnum() or x in '_.:-/' for x in value)


def _sha(value):
    return type(value) is str and len(value) == 64 and all(x in '0123456789abcdef' for x in value)


def validate_expression(expression, depth=0):
    if depth > MAX_DEPTH:
        raise ValueError('EXPRESSION_DEPTH')
    if _finite(expression, 8):
        return 1
    if type(expression) is str and expression in FEATURES:
        return 1
    if type(expression) is not list or len(expression) != 3 or expression[0] not in OPERATIONS:
        raise ValueError('EXPRESSION_GRAMMAR')
    count = 1 + validate_expression(expression[1], depth + 1) + validate_expression(expression[2], depth + 1)
    if count > MAX_NODES:
        raise ValueError('EXPRESSION_NODES')
    return count


def validate(policy):
    if type(policy) is not dict or set(policy) != {'language', 'priority', 'stop_below'} or policy['language'] != LANGUAGE:
        raise ValueError('POLICY_SCHEMA')
    validate_expression(policy['priority'])
    if not _finite(policy['stop_below'], 1000000000):
        raise ValueError('STOP_THRESHOLD')
    return True


def _evaluate(expression, features):
    if type(expression) in (int, float):
        return float(expression)
    if type(expression) is str:
        return features[expression]
    left, right = _evaluate(expression[1], features), _evaluate(expression[2], features)
    operation = expression[0]
    if operation == 'add':
        value = left + right
    elif operation == 'sub':
        value = left - right
    elif operation == 'mul':
        value = left * right
    elif operation == 'div':
        value = left / (right if abs(right) >= .000001 else (.000001 if right >= 0 else -.000001))
    elif operation == 'min':
        value = min(left, right)
    else:
        value = max(left, right)
    return max(-1000000000, min(1000000000, value))


def _budget(value, spent=False):
    if type(value) is not dict or set(value) != {'steps', 'cost_units', 'kinds'}:
        raise ValueError('BUDGET_SCHEMA')
    if any(type(value[x]) is not int or not 0 <= value[x] <= 1000000 for x in ('steps', 'cost_units')):
        raise ValueError('BUDGET_BOUNDS')
    if type(value['kinds']) is not dict or set(value['kinds']) != set(KINDS) or any(type(x) is not int or not 0 <= x <= 1000000 for x in value['kinds'].values()):
        raise ValueError('KIND_BUDGET')
    if not spent and value['steps'] > 256:
        raise ValueError('STEP_LIMIT')


def interpret(payload):
    if type(payload) is not dict or set(payload) != {'policy', 'observation', 'budget', 'spent'}:
        raise ValueError('SELECTOR_PAYLOAD')
    policy, observation, budget, spent = (payload[x] for x in ('policy', 'observation', 'budget', 'spent'))
    validate(policy)
    _budget(budget)
    _budget(spent, True)
    if any(spent[x] > budget[x] for x in ('steps', 'cost_units')) or any(spent['kinds'][x] > budget['kinds'][x] for x in KINDS):
        raise ValueError('ALREADY_OVERRUN')
    if type(observation) is not dict or set(observation) != {'actions', 'evidence_sha256'} or not _sha(observation['evidence_sha256']):
        raise ValueError('OBSERVATION_SCHEMA')
    actions = observation['actions']
    if type(actions) is not list or len(actions) > MAX_ACTIONS:
        raise ValueError('ACTION_BOUND')
    identities, eligible, blocked = set(), [], []
    for action in actions:
        if type(action) is not dict or set(action) != {'id', 'kind', 'features', 'feature_provenance', 'source_identities', 'cost_units'}:
            raise ValueError('ACTION_SCHEMA')
        if not _name(action['id']) or action['id'] in identities or action['kind'] not in KINDS:
            raise ValueError('ACTION_ID_OR_KIND')
        identities.add(action['id'])
        if type(action['cost_units']) is not int or not 1 <= action['cost_units'] <= 1000000:
            raise ValueError('ACTION_COST')
        features = action['features']
        if type(features) is not dict or set(features) != set(FEATURES) or any(not _finite(x, 1) or x < 0 for x in features.values()):
            raise ValueError('NORMALIZED_FEATURES')
        provenance = action['feature_provenance']
        if type(provenance) is not dict or set(provenance) != set(FEATURES) or any(x not in ('observed', 'development_prediction') for x in provenance.values()):
            raise ValueError('FEATURE_PROVENANCE')
        if type(action['source_identities']) is not list or not 1 <= len(action['source_identities']) <= 16 or any(not _sha(x) for x in action['source_identities']):
            raise ValueError('FEATURE_SOURCE_IDENTITIES')
        if spent['steps'] + 1 > budget['steps'] or spent['cost_units'] + action['cost_units'] > budget['cost_units'] or spent['kinds'][action['kind']] + 1 > budget['kinds'][action['kind']]:
            blocked.append(action['id'])
            continue
        eligible.append({'action_id': action['id'], 'kind': action['kind'], 'cost_units': action['cost_units'], 'score': _evaluate(policy['priority'], features)})
    eligible.sort(key=lambda x: (-x['score'], x['action_id']))
    selected = eligible[0] if eligible and eligible[0]['score'] >= policy['stop_below'] else None
    return {'state': 'SELECTED' if selected is not None else 'STOP', 'selected': selected,
            'ranked': eligible, 'budget_blocked': blocked, 'evidence_sha256': observation['evidence_sha256'],
            'boundary': 'Inert action identity only; feature provenance is declared, not authenticated truth; external broker owns actual effects, costs and unchanged acceptance'}


def _paths(tree, path=()):
    out = [path]
    if type(tree) is list:
        out.extend(_paths(tree[1], path + (1,)))
        out.extend(_paths(tree[2], path + (2,)))
    return out


def _subtree(tree, path):
    for item in path:
        tree = tree[item]
    return tree


def _replace(tree, path, replacement):
    if not path:
        return replacement
    out = [tree[0], tree[1], tree[2]]
    out[path[0]] = _replace(out[path[0]], path[1:], replacement)
    return out


def generate(seed=0, count=32, parents=None, omega_source_path=None):
    import hashlib
    import importlib.util
    import json
    from pathlib import Path
    import random
    import sys
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1 or type(count) is not int or not 1 <= count <= 256:
        raise ValueError('GENERATOR_BUDGET')
    parents = parents if parents is not None else [{'language': LANGUAGE, 'priority': ['div', 'gain', 'cost'], 'stop_below': 0}]
    if type(parents) is not list or not 1 <= len(parents) <= 16:
        raise ValueError('PARENT_BOUND')
    for parent in parents:
        validate(parent)
    rng, programs, seen, trace = random.Random(seed), [], set(), []
    omega = None
    if omega_source_path is not None:
        path = Path(omega_source_path)
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != OMEGA_PROGRAMS_SHA256:
            raise ValueError('OMEGA_SOURCE_IDENTITY')
        name = '_agi_alpha_omega006_pinned'
        spec = importlib.util.spec_from_file_location(name, path)
        omega = importlib.util.module_from_spec(spec)
        sys.modules[name] = omega
        spec.loader.exec_module(omega)
    def key(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    def random_tree(depth):
        if depth == 0 or rng.random() < .4:
            return rng.choice(FEATURES) if rng.random() < .8 else round(rng.uniform(-3, 3), 3)
        return [rng.choice(OPERATIONS), random_tree(depth - 1), random_tree(depth - 1)]
    attempts = 0
    while len(programs) < count and attempts < count * 100:
        index = len(programs)
        attempts += 1
        parent_index = rng.randrange(len(parents))
        parent = parents[parent_index]
        if index < len(parents):
            candidate = json.loads(json.dumps(parents[index]))
            method = 'supplied-parent'
        elif omega is not None:
            prior = omega.Program.create('evidence', parent['priority'])
            other = omega.Program.create('evidence', rng.choice(parents)['priority'])
            proposed = omega.mutate(prior, rng, other)
            candidate = {'language': LANGUAGE, 'priority': proposed.expression, 'stop_below': parent['stop_below']}
            method = 'source-pinned-Omega-mutate'
        else:
            path = rng.choice(_paths(parent['priority']))
            other_priority = rng.choice(parents)['priority']
            replacement = (random_tree(2) if rng.random() < .65 else _subtree(other_priority, rng.choice(_paths(other_priority))))
            candidate = {'language': LANGUAGE, 'priority': _replace(parent['priority'], path, replacement), 'stop_below': parent['stop_below']}
            method = 'independent-bounded-subtree-mutation'
        try:
            validate(candidate)
        except ValueError:
            trace.append({'attempt': attempts, 'state': 'refused-generated-expression', 'method': method})
            continue
        identity = key(candidate)
        if identity in seen:
            trace.append({'attempt': attempts, 'state': 'duplicate', 'sha256': identity, 'method': method})
            continue
        seen.add(identity)
        programs.append(candidate)
        trace.append({'attempt': attempts, 'state': 'generated', 'index': index, 'sha256': identity,
                      'parent_sha256': key(parent), 'method': method, 'priority_changed': candidate['priority'] != parent['priority']})
    if len(programs) != count:
        raise RuntimeError('GENERATION_EXHAUSTED')
    return {'language': LANGUAGE, 'programs': programs, 'trace': trace, 'seed': seed,
            'grammar': {'features': list(FEATURES), 'operations': list(OPERATIONS), 'max_depth': MAX_DEPTH, 'max_nodes': MAX_NODES},
            'omega_source_sha256': OMEGA_PROGRAMS_SHA256 if omega is not None else None,
            'authorship': 'All primitives, units, provenance rules and generator/adaptor are developer-authored; generated priority compositions are not a supplied menu of complete workflows; no new primitive, learned utility or scientific advantage is certified'}


def run(policy, broker, budget, source_path, expected_source_sha256):
    import hashlib
    import json
    import time
    from flywheel import sandbox
    validate(policy)
    _budget(budget)
    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    spent = {'steps': 0, 'cost_units': 0, 'kinds': {kind: 0 for kind in KINDS}}
    started, cpu, records = time.monotonic(), time.process_time(), []
    status = 'BUDGET_EXHAUSTED'
    for index in range(budget['steps'] + 1):
        observation = broker.observe()
        payload = {'policy': policy, 'observation': observation, 'budget': budget, 'spent': spent}
        selection = sandbox.run(source_path, 'interpret', payload, expected_source_sha256)
        if selection['state'] != 'COMPLETE':
            records.append({'selection': selection, 'state': 'CONFINED_SELECTION_FAILED'})
            status = 'REFUSED'
            break
        decision = selection['worker']['result']
        if decision['state'] == 'STOP':
            records.append({'selection': selection, 'state': 'STOP'})
            status = 'STOP'
            break
        action = decision['selected']
        spent = {'steps': spent['steps'] + 1, 'cost_units': spent['cost_units'] + action['cost_units'],
                 'kinds': {kind: spent['kinds'][kind] + int(kind == action['kind']) for kind in KINDS}}
        before = digest(observation)
        try:
            outcome = broker.execute(action['action_id'])
        except Exception as error:
            records.append({'selection': selection, 'before_sha256': before, 'state': 'BROKER_FAILED',
                            'charged': action, 'error_type': type(error).__name__, 'message': str(error)[:300]})
            status = 'FAILED'
            break
        if type(outcome) is not dict or set(outcome) != {'action_id', 'kind', 'cost_units', 'artifact_sha256', 'observation_sha256'} or outcome['action_id'] != action['action_id'] or outcome['kind'] != action['kind'] or outcome['cost_units'] != action['cost_units'] or not _sha(outcome['artifact_sha256']) or not _sha(outcome['observation_sha256']):
            records.append({'selection': selection, 'before_sha256': before, 'state': 'BROKER_RECEIPT_MISMATCH', 'charged': action})
            status = 'REFUSED'
            break
        records.append({'selection': selection, 'before_sha256': before, 'state': 'EXECUTED', 'outcome': outcome})
    return {'state': status, 'policy_sha256': digest(policy), 'source_sha256': expected_source_sha256,
            'records': records, 'spent': spent, 'budget': budget,
            'resources': {'wall_seconds': time.monotonic() - started, 'host_cpu_seconds': time.process_time() - cpu,
                          'selection_worker_cpu_seconds': sum(row['selection'].get('worker', {}).get('worker_cpu_seconds', 0) for row in records),
                          'complete_monetary_cost': None, 'broker_resource_costs': 'Must be included by the enclosing domain experiment'},
            'scope': 'Generated JSON arithmetic action selectors execute inside seccomp; fixed trusted broker effects are external. No result here is final scientific/commercial acceptance.'}
