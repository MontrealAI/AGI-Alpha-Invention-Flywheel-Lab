import hashlib
import itertools
import json

ROLES = ('acquire', 'prepare', 'durable', 'consume', 'release')
SEMANTICS = {
    'sqlite_connect': 'acquire', 'sqlite_insert': 'prepare', 'sqlite_commit': 'durable',
    'sqlite_stream': 'consume', 'sqlite_close': 'release',
    'file_open': 'acquire', 'file_write': 'prepare', 'file_fsync': 'durable',
    'file_stream': 'consume', 'file_close': 'release',
}
DOMAINS = {'sqlite': 'sqlite_', 'file': 'file_'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def validate(spec):
    keys = {'schema', 'task_id', 'domain', 'effects', 'blocks', 'obligations'}
    if type(spec) is not dict or set(spec) != keys or spec['schema'] != 'agi-alpha/lifetime-spec007/v1':
        raise ValueError('SPEC_SCHEMA')
    if type(spec['task_id']) is not str or not 1 <= len(spec['task_id']) <= 80 or spec['domain'] not in DOMAINS:
        raise ValueError('SPEC_IDENTITY')
    obligations = {'durable_before_visible', 'live_during_consumption', 'close_on_exit'}
    if type(spec['obligations']) is not dict or set(spec['obligations']) != obligations or any(spec['obligations'][key] is not True for key in obligations):
        raise ValueError('UNSUPPORTED_OBLIGATIONS')
    if type(spec['effects']) is not list or len(spec['effects']) != 5:
        raise ValueError('FIVE_TYPED_EFFECTS_REQUIRED')
    ids = []
    roles = {}
    for effect in spec['effects']:
        if type(effect) is not dict or set(effect) != {'id', 'operation', 'resource'}:
            raise ValueError('EFFECT_SCHEMA')
        ident, operation, resource = (effect[k] for k in ('id', 'operation', 'resource'))
        if type(ident) is not str or not 1 <= len(ident) <= 80 or ident in ids:
            raise ValueError('EFFECT_IDENTITY')
        if type(operation) is not str or not operation.startswith(DOMAINS[spec['domain']]) or operation not in SEMANTICS:
            raise ValueError('UNKNOWN_EFFECT_SEMANTICS')
        if type(resource) is not str or not 1 <= len(resource) <= 80:
            raise ValueError('RESOURCE_SCHEMA')
        role = SEMANTICS[operation]
        if role in roles:
            raise ValueError('AMBIGUOUS_ROLE_MAPPING')
        roles[role] = ident
        ids.append(ident)
    if set(roles) != set(ROLES) or len({e['resource'] for e in spec['effects']}) != 1:
        raise ValueError('INAPPLICABLE_ROLE_GRAPH')
    if type(spec['blocks']) is not list or not 1 <= len(spec['blocks']) <= 5:
        raise ValueError('BLOCK_SCHEMA')
    flat = []
    for block in spec['blocks']:
        if type(block) is not dict or set(block) != {'effects', 'separable'} or type(block['separable']) is not bool:
            raise ValueError('BLOCK_SCHEMA')
        if type(block['effects']) is not list or not 1 <= len(block['effects']) <= 5 or any(type(x) is not str or x not in ids for x in block['effects']):
            raise ValueError('BLOCK_EFFECTS')
        flat.extend(block['effects'])
    if sorted(flat) != sorted(ids):
        raise ValueError('BLOCKS_MUST_PARTITION_EFFECTS')
    if len(canonical(spec)) > 16384:
        raise ValueError('SPEC_BYTE_CAP')
    return roles


def infer_mapping(spec):
    mapping = validate(spec)
    return {'donor': 'durable-publication-with-live-reader', 'roles': mapping,
            'origin': 'Developer supplied operation semantics and donor requirements; role correspondence computed from typed effects, not lexical similarity.'}


def violations(order, mapping):
    if len(order) != 5 or set(order) != set(mapping.values()):
        return ['EFFECT_COVERAGE']
    pos = {role: order.index(ident) for role, ident in mapping.items()}
    edges = [('acquire', 'prepare'), ('prepare', 'durable'), ('durable', 'consume'),
             ('acquire', 'consume'), ('consume', 'release')]
    return [a + '_BEFORE_' + b for a, b in edges if pos[a] >= pos[b]]


def construct(spec, *, allow_factorization=True):
    mapping = infer_mapping(spec)
    blocks = spec['blocks']
    eligible = [i for i, block in enumerate(blocks) if block['separable'] and len(block['effects']) > 1]
    attempts = []
    best = None
    for count in range(len(eligible) + 1 if allow_factorization else 1):
        for subset in itertools.combinations(eligible, count):
            units = []
            for i, block in enumerate(blocks):
                units.extend([[e] for e in block['effects']] if i in subset else [block['effects']])
            for permutation in itertools.permutations(units):
                order = [e for unit in permutation for e in unit]
                defects = violations(order, mapping['roles'])
                attempts.append({'order': order, 'split_blocks': list(subset), 'violations': defects})
                if not defects:
                    best = (order, list(subset))
                    break
            if best:
                break
        if best:
            break
    result = {'schema': 'agi-alpha/lifetime-plan007/v1', 'task_id': spec['task_id'],
              'spec_sha256': digest(spec), 'mapping': mapping, 'status': 'CONSTRUCTED' if best else 'INFEASIBLE_IN_GRAMMAR',
              'order': best[0] if best else [], 'split_blocks': best[1] if best else [],
              'search_attempts': len(attempts), 'failed_attempts': attempts if best is None else attempts[:-1],
              'origin': 'Bounded effect factoring and permutation search written by the development model; no mathematical novelty or autonomous discovery-policy advantage claimed.'}
    if best:
        result['generated_operator'] = {'schema': 'agi-alpha/factor-operator007/v1',
            'kind': 'separate-compound-effects', 'blocks': [blocks[i]['effects'] for i in best[1]],
            'precedence': [[mapping['roles'][a], mapping['roles'][b]] for a, b in zip(ROLES, ROLES[1:])]}
    return result


def validate_plan(spec, plan):
    mapping = validate(spec)
    if type(plan) is not dict or plan.get('schema') != 'agi-alpha/lifetime-plan007/v1' or plan.get('spec_sha256') != digest(spec) or plan.get('task_id') != spec['task_id']:
        raise ValueError('STALE_OR_FORGED_PLAN')
    if plan.get('status') != 'CONSTRUCTED' or plan.get('mapping') != infer_mapping(spec):
        raise ValueError('PLAN_APPLICABILITY')
    if type(plan.get('split_blocks')) is not list or any(type(i) is not int or i < 0 or i >= len(spec['blocks']) for i in plan['split_blocks']):
        raise ValueError('PLAN_FACTORIZATION')
    if len(set(plan['split_blocks'])) != len(plan['split_blocks']):
        raise ValueError('DUPLICATE_FACTORIZATION')
    order = plan.get('order')
    if type(order) is not list or any(type(i) is not str for i in order) or violations(order, mapping):
        raise ValueError('PLAN_CONTRACT_VIOLATION')
    for i, block in enumerate(spec['blocks']):
        positions = [order.index(e) for e in block['effects']]
        if i in plan['split_blocks']:
            if not block['separable']:
                raise ValueError('UNAUTHORIZED_EFFECT_FACTORIZATION')
        elif positions != list(range(min(positions), min(positions) + len(positions))):
            raise ValueError('UNDECLARED_FACTORIZATION')
    return mapping


def remap_operator(operator, source_spec, target_spec):
    source_roles, target_roles = validate(source_spec), validate(target_spec)
    expected = construct(source_spec).get('generated_operator')
    if operator != expected or expected is None:
        raise ValueError('CORRUPTED_OR_UNSUPPORTED_OPERATOR')
    reverse = {ident: role for role, ident in source_roles.items()}
    target_blocks = {tuple(b['effects']): i for i, b in enumerate(target_spec['blocks'])}
    mapped = [[target_roles[reverse[e]] for e in block] for block in operator['blocks']]
    if any(tuple(b) not in target_blocks or not target_spec['blocks'][target_blocks[tuple(b)]]['separable'] for b in mapped):
        raise ValueError('FAILED_TRANSFER_EFFECT_COUPLING')
    return {'schema': operator['schema'], 'kind': operator['kind'], 'blocks': mapped,
            'precedence': [[target_roles[reverse[a]], target_roles[reverse[b]]] for a, b in operator['precedence']]}


def construct_from_operator(spec, operator):
    roles = validate(spec)
    if type(operator) is not dict or operator.get('schema') != 'agi-alpha/factor-operator007/v1' or operator.get('kind') != 'separate-compound-effects':
        raise ValueError('OPERATOR_SCHEMA')
    expected_edges = [[roles[a], roles[b]] for a, b in zip(ROLES, ROLES[1:])]
    if operator.get('precedence') != expected_edges:
        raise ValueError('UNSUPPORTED_OPERATOR_INVARIANT')
    blocks = operator.get('blocks')
    if type(blocks) is not list or len(blocks) > 5 or any(type(block) is not list or not block for block in blocks):
        raise ValueError('OPERATOR_BLOCK_SCHEMA')
    split = []
    for effect_block in blocks:
        matches = [i for i, block in enumerate(spec['blocks']) if block['effects'] == effect_block and block['separable']]
        if len(matches) != 1 or matches[0] in split:
            raise ValueError('OPERATOR_APPLICABILITY')
        split.extend(matches)
    nodes = set(roles.values())
    edges = [tuple(edge) for edge in operator['precedence']]
    order = []
    while nodes:
        available = sorted(node for node in nodes if not any(b == node and a in nodes for a, b in edges))
        if not available:
            raise ValueError('OPERATOR_CYCLE')
        order.append(available[0])
        nodes.remove(available[0])
    result = {'schema': 'agi-alpha/lifetime-plan007/v1', 'task_id': spec['task_id'],
              'spec_sha256': digest(spec), 'mapping': infer_mapping(spec), 'status': 'CONSTRUCTED',
              'order': order, 'split_blocks': split, 'search_attempts': 0, 'failed_attempts': [],
              'generated_operator': operator, 'reuse_mode': 'equivalent-content-operator',
              'origin': 'Retrieved operator remapped to target roles and topologically compiled; ordinary reuse receives identical content.'}
    try:
        validate_plan(spec, result)
    except ValueError as exc:
        raise ValueError('OPERATOR_APPLICABILITY')
    return result
