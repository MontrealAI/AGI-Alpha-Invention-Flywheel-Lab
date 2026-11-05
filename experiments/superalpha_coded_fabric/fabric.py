import hashlib
import itertools
import json

P = 65537


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate_blocks(blocks):
    if not isinstance(blocks, list) or len(blocks) != 3:
        raise ValueError('THREE_BLOCKS_REQUIRED')
    n = len(blocks[0])
    if not n or any(len(b) != n or any(len(r) != n for r in b) for b in blocks):
        raise ValueError('EQUAL_SQUARE_BLOCKS_REQUIRED')
    if any(type(v) is not int or not 0 <= v < P for b in blocks for r in b for v in r):
        raise ValueError('CANONICAL_FIELD_ELEMENTS_REQUIRED')
    return n


def weights(nodes, target):
    if len(nodes) != len(set(nodes)):
        raise ValueError('DISTINCT_NODES_REQUIRED')
    out = []
    for j, x in enumerate(nodes):
        num = den = 1
        for i, z in enumerate(nodes):
            if i != j:
                num = num * (target - z) % P
                den = den * (x - z) % P
        out.append(num * pow(den, -1, P) % P)
    return out


def combine(matrices, coefficients):
    n = len(matrices[0])
    return [[sum(c * a[i][j] for c, a in zip(coefficients, matrices)) % P
             for j in range(n)] for i in range(n)]


def multiply(a, b):
    n = len(a)
    return [[sum(a[i][k] * b[k][j] for k in range(n)) % P for j in range(n)] for i in range(n)]


def operation(block, kind, operand=None):
    if kind == 'linear':
        if operand is None or len(operand) != len(block) or any(len(r) != len(block) for r in operand):
            raise ValueError('MATCHED_OPERAND_REQUIRED')
        if any(type(v) is not int or not 0 <= v < P for r in operand for v in r):
            raise ValueError('CANONICAL_OPERAND_REQUIRED')
        return multiply(block, operand)
    if kind == 'gram':
        return multiply([list(r) for r in zip(*block)], block)
    raise ValueError('DECLARED_OPERATION_REQUIRED')


def recovery_threshold(kind):
    if kind not in {'linear', 'gram'}:
        raise ValueError('DECLARED_OPERATION_REQUIRED')
    return {'linear': 3, 'gram': 5}[kind]


def construct(kind, slots=(3, 3, 3), losses=1):
    threshold = recovery_threshold(kind)
    candidates = []
    for counts in itertools.product(*(range(s + 1) for s in slots)):
        worst = sum(counts) - sum(sorted(counts, reverse=True)[:losses])
        if worst >= threshold:
            candidates.append((sum(counts), counts))
    if not candidates:
        return None
    cost, counts = min(candidates)
    workers = []
    for domain, count in enumerate(counts):
        workers += [{'x': 4 + 3 * domain + i, 'domain': domain} for i in range(count)]
    return {'kind': kind, 'field': P, 'threshold': threshold, 'workers': workers,
            'counts': list(counts), 'worker_units': cost, 'domain_losses': losses}


def encode(blocks, plan, cache=None):
    n = validate_blocks(blocks)
    if plan['field'] != P or plan['threshold'] != recovery_threshold(plan['kind']):
        raise ValueError('CURRENT_OPERATION_CONTRACT_REQUIRED')
    binding = digest({'blocks': blocks, 'field': P})
    if cache is not None and (cache.get('input') != binding or cache.get('field') != P):
        raise ValueError('CACHE_INPUT_OR_FIELD_CHANGED')
    old = {} if cache is None else cache['shards']
    shards, new = {}, 0
    for w in plan['workers']:
        key = str(w['x'])
        if key in old:
            row = old[key]
            if digest(row['matrix']) != row['sha256']:
                raise ValueError('CACHE_BYTES_CHANGED')
        else:
            a = combine(blocks, weights([1, 2, 3], w['x']))
            row = {'matrix': a, 'sha256': digest(a)}
            new += 1
        shards[key] = row
    return {'input': binding, 'field': P, 'shards': shards}, {
        'new_shards': new, 'reused_shards': len(shards) - new,
        'encoding_scalar_multiplications': new * 3 * n * n,
        'new_outbound_field_elements': new * n * n}


def execute(cache, plan, operand=None):
    binding = digest({'input': cache['input'], 'kind': plan['kind'], 'operand': operand, 'field': P})
    returns = []
    for worker in plan['workers']:
        a = cache['shards'][str(worker['x'])]['matrix']
        returns.append({**worker, 'binding': binding, 'value': operation(a, plan['kind'], operand)})
    return binding, returns


def decode(returns, plan, binding):
    if plan['field'] != P or plan['threshold'] != recovery_threshold(plan['kind']):
        raise ValueError('CURRENT_OPERATION_CONTRACT_REQUIRED')
    permitted = {w['x']: w['domain'] for w in plan['workers']}
    xs = [r['x'] for r in returns]
    if len(xs) != len(set(xs)) or any(r['x'] not in permitted or permitted[r['x']] != r['domain'] for r in returns):
        raise ValueError('UNIQUE_DECLARED_WORKERS_REQUIRED')
    if any(r['binding'] != binding for r in returns):
        raise ValueError('JOB_BINDING_CHANGED')
    if len(returns) < plan['threshold']:
        raise ValueError('INSUFFICIENT_RETURNS')
    selected = sorted(returns, key=lambda r: r['x'])[:plan['threshold']]
    matrices = [r['value'] for r in selected]
    n = len(matrices[0])
    if any(len(m) != n or any(len(row) != n or any(type(v) is not int or not 0 <= v < P for v in row) for row in m) for m in matrices):
        raise ValueError('CANONICAL_RETURN_MATRICES_REQUIRED')
    return [combine(matrices, weights([r['x'] for r in selected], x)) for x in [1, 2, 3]]


def fixture(n, affine=False):
    blocks = [[[(i * 17 + j * 31 + b * 43 + i * j * (b + 1) + 3
                + (0 if affine else b * b * (7 + i + j * j))) % P
                for j in range(n)] for i in range(n)] for b in range(3)]
    operand = [[(i * 7 + j * 11 + i * j + 5) % P for j in range(n)] for i in range(n)]
    return blocks, operand
