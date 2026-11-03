import argparse
from collections import Counter
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parent
PROTOCOL_COMMIT = 'fa7a1117b91340afb27288ec09adbc33926d9ba4'
ARMS = ('fresh', 'frozen_first', 'accumulating', 'conventional')
LIMIT = 100000


def encoded(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':')).encode()


def digest(x):
    return hashlib.sha256(encoded(x)).hexdigest()


def vector(x):
    return tuple(F(v) for v in x)


def packed(x):
    return [str(v) for v in x]


class Exhausted(Exception):
    pass


class Meter:
    def __init__(self, limit=LIMIT):
        self.limit, self.total, self.phase, self.peak_bits = limit, 0, 'construction', 1
        self.counts = {p: dict.fromkeys(('add', 'sub', 'mul', 'div'), 0) for p in ('construction', 'verification', 'execution')}
        self.other = Counter()

    def op(self, operation, a, b):
        if self.total >= self.limit:
            raise Exhausted('Registered arithmetic allowance exhausted')
        self.total += 1
        self.counts[self.phase][operation] += 1
        a, b = F(a), F(b)
        if operation == 'add':
            c = a + b
        elif operation == 'sub':
            c = a - b
        elif operation == 'mul':
            c = a * b
        else:
            c = a / b
        self.peak_bits = max(self.peak_bits, a.numerator.bit_length(), a.denominator.bit_length(), b.numerator.bit_length(), b.denominator.bit_length(), c.numerator.bit_length(), c.denominator.bit_length())
        return c

    def record(self):
        return {'arithmetic_by_phase': self.counts, 'total_arithmetic': self.total,
                'peak_rational_bits': self.peak_bits, **dict(sorted(self.other.items()))}


def combine(a, b, operation, meter):
    return tuple(meter.op(operation, x, y) for x, y in zip(a, b))


def scale(a, c, meter):
    return tuple(meter.op('mul', c, x) for x in a)


def dot(a, b, meter):
    result = F(0)
    for x, y in zip(a, b):
        result = meter.op('add', result, meter.op('mul', x, y))
    return result


def source_id(a, unit):
    return digest({'operator': [packed(r) for r in a], 'unit': unit})


def artifact(a, q, unit, ast, certificate):
    body = {'operator': source_id(a, unit), 'unit': unit, 'target': packed(q),
            'ast': ast, 'certificate': packed(certificate)}
    return dict(body, id=digest(body))


def row_factorization(a, identity, state, meter):
    if identity in state['factorizations']:
        raw = state['factorizations'][identity]
        meter.other['factorization_bytes_read'] += len(raw)
        meter.other['factorization_cache_hits'] += 1
        saved = json.loads(raw)
        return [list(vector(r)) for r in saved['rows']], [list(vector(r)) for r in saved['transform']], saved['pivots']
    rows = [list(r) for r in a]
    m, n = len(rows), len(rows[0])
    transform = [[F(int(i == j)) for j in range(m)] for i in range(m)]
    pivots, position = [], 0
    for column in range(n):
        pivot = next((i for i in range(position, m) if rows[i][column]), None)
        if pivot is None:
            continue
        rows[position], rows[pivot] = rows[pivot], rows[position]
        transform[position], transform[pivot] = transform[pivot], transform[position]
        divisor = rows[position][column]
        rows[position] = [meter.op('div', x, divisor) for x in rows[position]]
        transform[position] = [meter.op('div', x, divisor) for x in transform[position]]
        for i in range(m):
            if i == position or not rows[i][column]:
                continue
            factor = rows[i][column]
            rows[i] = [meter.op('sub', x, meter.op('mul', factor, y)) for x, y in zip(rows[i], rows[position])]
            transform[i] = [meter.op('sub', x, meter.op('mul', factor, y)) for x, y in zip(transform[i], transform[position])]
        pivots.append(column)
        position += 1
        if position == m:
            break
    raw = encoded({'rows': [packed(r) for r in rows], 'transform': [packed(r) for r in transform], 'pivots': pivots})
    state['factorizations'][identity] = raw
    meter.other['factorization_bytes_written'] += len(raw)
    meter.other['factorizations_built'] += 1
    return rows, transform, pivots


def solve_rank(a, q, identity, state, meter):
    rows, transform, pivots = row_factorization(a, identity, state, meter)
    residual, coefficients = tuple(q), (F(0),) * len(a)
    for i, p in enumerate(pivots):
        factor = residual[p]
        if factor:
            residual = combine(residual, scale(rows[i], factor, meter), 'sub', meter)
            coefficients = combine(coefficients, scale(transform[i], factor, meter), 'add', meter)
    if not any(residual):
        return coefficients, None
    free = next(i for i, value in enumerate(residual) if value)
    witness = [F(0)] * len(q)
    witness[free] = F(1)
    for i, p in enumerate(pivots):
        witness[p] = meter.op('sub', 0, rows[i][free])
    return None, tuple(witness)


def rank_program(coefficients, a, unit, eligible, registry, meter):
    remaining, pieces = tuple(coefficients), []
    for identifier in eligible:
        previous = vector(registry[identifier]['certificate'])
        support = [i for i, x in enumerate(previous) if x]
        if len(support) < 2 or any(not remaining[i] for i in support):
            continue
        ratio = meter.op('div', remaining[support[0]], previous[support[0]])
        if all(meter.op('mul', ratio, previous[i]) == remaining[i] for i in support):
            node = ['call', identifier]
            pieces.append(node if ratio == 1 else ['scale', str(ratio), node])
            remaining = combine(remaining, scale(previous, ratio, meter), 'sub', meter)
    identity = source_id(a, unit)
    for i, value in enumerate(remaining):
        if value:
            node = ['read', i, unit, identity]
            pieces.append(node if value == 1 else ['scale', str(value), node])
    if not pieces:
        return ['scale', '0', ['read', 0, unit, identity]]
    result = pieces[0]
    for node in pieces[1:]:
        result = ['add', result, node]
    return result


def expression_search(a, q, unit, eligible, registry, meter):
    identity = source_id(a, unit)
    atoms, known = [], {}
    for identifier in eligible:
        item = registry[identifier]
        entry = (vector(item['target']), vector(item['certificate']), ['call', identifier])
        if entry[0] not in known:
            known[entry[0]] = entry
            atoms.append(entry)
    for i, row in enumerate(a):
        entry = (tuple(row), tuple(F(int(j == i)) for j in range(len(a))), ['read', i, unit, identity])
        if entry[0] not in known:
            known[entry[0]] = entry
            atoms.append(entry)
    if tuple(q) in known:
        entry = known[tuple(q)]
        return entry[2], entry[1]
    proposals = 0

    def propose():
        nonlocal proposals
        if proposals >= 512:
            return False
        proposals += 1
        meter.other['search_proposals'] += 1
        return True

    for entry in list(atoms):
        for coefficient in (F(-1), F(1, 2), F(2)):
            if not propose():
                return None
            v, w = scale(entry[0], coefficient, meter), scale(entry[1], coefficient, meter)
            item = (v, w, ['scale', str(coefficient), entry[2]])
            if v == tuple(q):
                return item[2], w
            if v not in known and len(atoms) < 96:
                known[v] = item
                atoms.append(item)
    for _ in range(3):
        for left in list(atoms):
            for operation in ('sub', 'add'):
                if not propose():
                    return None
                needed = combine(q, left[0], operation, meter)
                if needed in known:
                    right = known[needed]
                    if operation == 'sub':
                        return ['add', left[2], right[2]], combine(left[1], right[1], 'add', meter)
                    return ['sub', right[2], left[2]], combine(right[1], left[1], 'sub', meter)
        before = list(atoms)
        for i, left in enumerate(before):
            for right in before[i:]:
                for operation in ('add', 'sub'):
                    if not propose():
                        return None
                    v = combine(left[0], right[0], operation, meter)
                    w = combine(left[1], right[1], operation, meter)
                    node = [operation, left[2], right[2]]
                    if v == tuple(q):
                        return node, w
                    if v not in known and len(atoms) < 96:
                        item = (v, w, node)
                        known[v] = item
                        atoms.append(item)
                        for relation in ('sub', 'add'):
                            if not propose():
                                return None
                            needed = combine(q, v, relation, meter)
                            if needed in known:
                                other = known[needed]
                                if relation == 'sub':
                                    return ['add', node, other[2]], combine(w, other[1], 'add', meter)
                                return ['sub', other[2], node], combine(other[1], w, 'sub', meter)
        if len(atoms) == len(before):
            break
    return None


def construct(a, q, unit, arm, eligible, state, meter):
    if arm != 'conventional':
        found = expression_search(a, q, unit, eligible, state['registry'], meter)
        if found:
            ast, certificate = found
            return artifact(a, q, unit, ast, certificate), None, 'expression'
    coefficients, witness = solve_rank(a, q, source_id(a, unit), state, meter)
    if witness is not None:
        return None, witness, 'rank' if arm == 'conventional' else 'rank_fallback'
    ast = rank_program(coefficients, a, unit, eligible, state['registry'], meter)
    return artifact(a, q, unit, ast, coefficients), None, 'rank' if arm == 'conventional' else 'rank_fallback'


def verify_artifact(item, a, q, unit, registry, allowed, meter):
    identity = source_id(a, unit)
    checked, active = {}, set()

    def inspect(program):
        body = {k: v for k, v in program.items() if k != 'id'}
        if program['id'] != digest(body) or program['operator'] != identity or program['unit'] != unit:
            raise ValueError('Artifact identity, observation operator or quantity type changed')
        if program['id'] in checked:
            return checked[program['id']]
        if program['id'] in active:
            raise ValueError('Cyclic inheritance')
        active.add(program['id'])
        weights = expand(program['ast'])
        claimed = vector(program['certificate'])
        if weights != claimed or len(weights) != len(a):
            raise ValueError('AST does not implement its coefficient certificate')
        measured = tuple(dot(weights, column, meter) for column in zip(*a))
        if measured != vector(program['target']):
            raise ValueError('Decoder certificate does not establish the target')
        active.remove(program['id'])
        checked[program['id']] = weights
        return weights

    def expand(node):
        if not isinstance(node, list) or not node:
            raise ValueError('Malformed AST')
        operation = node[0]
        if operation == 'read' and len(node) == 4:
            if type(node[1]) is not int or not 0 <= node[1] < len(a) or node[2:] != [unit, identity]:
                raise ValueError('Invalid typed observation read')
            return tuple(F(int(i == node[1])) for i in range(len(a)))
        if operation == 'call' and len(node) == 2:
            if node[1] not in allowed or node[1] not in registry:
                raise ValueError('Unqualified inherited call')
            return inspect(registry[node[1]])
        if operation == 'scale' and len(node) == 3:
            child = expand(node[2])
            return tuple(meter.op('mul', F(node[1]), value) for value in child)
        if operation in ('add', 'sub') and len(node) == 3:
            left, right = expand(node[1]), expand(node[2])
            return tuple(meter.op(operation, left[i], right[i]) for i in range(len(a)))
        raise ValueError('Unrecognized AST operation')

    weights = inspect(item)
    if vector(item['target']) != tuple(q):
        raise ValueError('Artifact solves a different request')
    return weights


def verify_witness(h, a, q, meter):
    if len(h) != len(q) or any(dot(row, h, meter) for row in a) or dot(q, h, meter) == 0:
        raise ValueError('Invalid nonidentifiability witness')


def execute_ast(node, values, registry, meter, cache=None):
    if cache is None:
        cache = {}
    meter.other['runtime_ast_visits'] += 1
    key = encoded(node)
    if key in cache:
        return cache[key]
    operation = node[0]
    if operation == 'read':
        meter.other['primitive_reads'] += 1
        result = values[node[1]]
    elif operation == 'call':
        meter.other['retained_calls'] += 1
        result = execute_ast(registry[node[1]]['ast'], values, registry, meter, cache)
    elif operation == 'scale':
        result = meter.op('mul', F(node[1]), execute_ast(node[2], values, registry, meter, cache))
    else:
        left = execute_ast(node[1], values, registry, meter, cache)
        right = execute_ast(node[2], values, registry, meter, cache)
        result = meter.op(operation, left, right)
    cache[key] = result
    return result


def inheritance_depth(node, registry):
    if node[0] == 'call':
        return 1 + inheritance_depth(registry[node[1]]['ast'], registry)
    if node[0] == 'scale':
        return inheritance_depth(node[2], registry)
    if node[0] in ('add', 'sub'):
        return max(inheritance_depth(node[1], registry), inheritance_depth(node[2], registry))
    return 0


def workload():
    cases = []
    for family_index, family in enumerate(('shared', 'disjoint', 'changed', 'rank_deficient')):
        for variant, seed in enumerate((17, 29, 43)):
            episode = family_index * 3 + variant
            rng = random.Random(seed)
            original = [[F(int(i == j)) for j in range(6)] for i in range(6)]
            for _ in range(6):
                i, j = rng.sample(range(6), 2)
                multiplier = rng.choice((-1, 1))
                original[i] = [x + multiplier * y for x, y in zip(original[i], original[j])]
            original = [original[i] for i in rng.sample(range(6), 6)]
            for generation in range(3):
                a = [list(row) for row in original]
                unit = 'u'
                if family == 'changed':
                    if variant in (0, 2):
                        a[0] = [x + generation * y for x, y in zip(a[0], a[1])]
                    if variant in (1, 2):
                        unit = ('u', 'v', 'w')[generation]
                if family == 'rank_deficient':
                    for row in a:
                        row[-1] = F(0)
                    q = [x + y for x, y in zip(a[0], a[1])] if generation == 0 else [F(int(i == 5)) + (a[2][i] if generation == 2 else 0) for i in range(6)]
                elif family == 'disjoint':
                    q = [x + y for x, y in zip(a[2 * generation], a[2 * generation + 1])]
                else:
                    q = [sum(row[i] for row in a[:generation + 2]) for i in range(6)]
                inputs = []
                for replicate in range(3):
                    draw = random.Random(10000 + 100 * episode + 10 * generation + replicate)
                    inputs.append([draw.randint(-11, 11) for _ in range(6)])
                cases.append({'episode': episode + 1, 'generation': generation + 1, 'family': family,
                              'operator': [packed(row) for row in a], 'target': packed(q), 'unit': unit, 'latent_inputs': inputs})
    return cases


def read_archive(state, identity, unit, meter):
    raw = encoded([state['registry'][i] for i in state['archive']])
    meter.other['archive_bytes_read'] += len(raw)
    loaded = json.loads(raw)
    eligible = []
    for item in reversed(loaded):
        meter.other['archive_bytes_validated'] += len(encoded(item))
        if item['operator'] != identity or item['unit'] != unit:
            meter.other['invalidated_programs'] += 1
        else:
            eligible.append(item['id'])
    return eligible


def new_state():
    return {'registry': {}, 'archive': [], 'factorizations': {}, 'history': []}


def run_request(case, arm, state):
    start_wall, start_cpu = time.perf_counter(), time.process_time()
    meter, item, witness, error, path = Meter(), None, None, None, None
    a, q, unit = [vector(row) for row in case['operator']], vector(case['target']), case['unit']
    eligible = read_archive(state, source_id(a, unit), unit, meter)
    row = {key: case[key] for key in ('episode', 'generation', 'family')}
    row.update({'arm': arm, 'eligible_inheritance': eligible, 'fresh_input_checks': 0})
    try:
        item, witness, path = construct(a, q, unit, arm, eligible, state, meter)
        meter.phase = 'verification'
        if witness is not None:
            verify_witness(witness, a, q, meter)
            status = 'NONIDENTIFIABLE'
        else:
            verify_artifact(item, a, q, unit, state['registry'], set(eligible), meter)
            for latent in case['latent_inputs']:
                values = tuple(sum(x * F(z) for x, z in zip(observation, latent)) for observation in a)
                meter.phase = 'execution'
                actual = execute_ast(item['ast'], values, state['registry'], meter)
                meter.phase = 'verification'
                expected = dot(q, latent, meter)
                if actual != expected:
                    raise ValueError('Constructed program returned a wrong fresh-input answer')
                row['fresh_input_checks'] += 1
            status = 'ACCEPTED'
            serialized = encoded(item)
            meter.other['artifact_bytes_written'] += len(serialized)
            state['registry'][item['id']] = json.loads(serialized)
            if arm in ('accumulating', 'conventional') or (arm == 'frozen_first' and case['generation'] == 1):
                state['archive'].append(item['id'])
                meter.other['archive_bytes_written'] += len(serialized)
            row['inheritance_depth'] = inheritance_depth(item['ast'], state['registry'])
    except Exhausted as exc:
        status, error = 'EXHAUSTED', str(exc)
    except ValueError as exc:
        status, error = 'REJECTED', str(exc)
    except Exception as exc:
        status, error = 'IMPLEMENTATION_ERROR', type(exc).__name__ + ': ' + str(exc)
    row.update({'status': status, 'compiler_path': path, 'program_id': item['id'] if item else None,
                'witness': packed(witness) if witness is not None else None, 'error': error,
                'cost': meter.record(), 'retained_programs': len(state['archive'])})
    state['history'].append({'target': packed(q), 'status': status, 'cost': meter.total})
    row['timing_seconds'] = {'wall': time.perf_counter() - start_wall, 'cpu': time.process_time() - start_cpu}
    return row, item


def adverse_controls():
    a = [tuple(F(int(i == j)) for j in range(3)) for i in range(3)]
    q, unit = (F(1), F(1), F(0)), 'u'
    identity = source_id(a, unit)
    original = artifact(a, q, unit, ['add', ['read', 0, unit, identity], ['read', 1, unit, identity]], q)
    outcomes = {}

    def rejected(name, action):
        try:
            action()
        except ValueError:
            outcomes[name] = True
        else:
            outcomes[name] = False

    changed = json.loads(encoded(original))
    changed['certificate'][0] = '2'
    changed['id'] = digest({k: v for k, v in changed.items() if k != 'id'})
    rejected('changed_coefficient', lambda: verify_artifact(changed, a, q, unit, {}, set(), Meter()))
    changed_ast = json.loads(encoded(original))
    changed_ast['ast'][2][1] = 2
    changed_ast['id'] = digest({k: v for k, v in changed_ast.items() if k != 'id'})
    rejected('changed_read', lambda: verify_artifact(changed_ast, a, q, unit, {}, set(), Meter()))
    other_a = [tuple(row) for row in a]
    other_a[0] = (F(1), F(1), F(0))
    rejected('changed_operator', lambda: verify_artifact(original, other_a, q, unit, {}, set(), Meter()))
    rejected('changed_type', lambda: verify_artifact(original, a, q, 'v', {}, set(), Meter()))
    rejected('false_nullspace', lambda: verify_witness((F(1), F(0), F(0)), a, q, Meter()))
    try:
        construct(a, q, unit, 'fresh', [], new_state(), Meter(limit=0))
    except Exhausted:
        outcomes['exhaustion_is_not_impossibility'] = True
    else:
        outcomes['exhaustion_is_not_impossibility'] = False
    meters = [Meter(), Meter()]
    for meter in meters:
        meter.phase = 'execution'
    values = (F(2), F(3), F(5))
    direct = execute_ast(original['ast'], values, {}, meters[0])
    called = execute_ast(['call', original['id']], values, {original['id']: original}, meters[1])
    outcomes['expanded_call_arithmetic'] = direct == called == 5 and meters[0].total == meters[1].total == 1
    return outcomes


def summarize(records):
    summaries = {}
    for family in ('all', 'shared', 'disjoint', 'changed', 'rank_deficient'):
        summaries[family] = {}
        for arm in ARMS:
            rows = [r for r in records if r['arm'] == arm and (family == 'all' or r['family'] == family)]
            summaries[family][arm] = {'requests': len(rows), 'statuses': dict(sorted(Counter(r['status'] for r in rows).items())),
                                     'arithmetic': sum(r['cost']['total_arithmetic'] for r in rows),
                                     'by_generation': {str(g): sum(r['cost']['total_arithmetic'] for r in rows if r['generation'] == g) for g in (1, 2, 3)},
                                     'max_inheritance_depth': max((r.get('inheritance_depth', 0) for r in rows), default=0)}
    return summaries


def run():
    cases, records, artifacts, states = workload(), [], {}, {}
    result = {'schema': 'agi-alpha-instrument-foundry-results/1', 'evidence_kind': 'authored_finite_computational_experiment',
              'protocol_public_commit': PROTOCOL_COMMIT, 'protocol_sha256': hashlib.sha256((ROOT / 'FOUNDRY_PROTOCOL.md').read_bytes()).hexdigest(),
              'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'python': sys.version.split()[0],
              'workload_sha256': digest(cases), 'registered_requests_per_arm': 36, 'cases': cases, 'records': records, 'artifacts': artifacts}
    try:
        for case in cases:
            for arm in ARMS:
                state = states.setdefault((case['episode'], arm), new_state())
                record, item = run_request(case, arm, state)
                records.append(record)
                if record['status'] == 'IMPLEMENTATION_ERROR':
                    raise RuntimeError(record['error'])
                if item is not None:
                    artifacts[item['id']] = item
        result['controls'] = adverse_controls()
        result['run_status'] = 'COMPLETE' if all(result['controls'].values()) and not any(r['status'] == 'REJECTED' for r in records) else 'INVALID_ACCEPTANCE'
    except Exception as exc:
        result['run_status'] = 'INVALID_IMPLEMENTATION'
        result['implementation_error'] = type(exc).__name__ + ': ' + str(exc)
    result['summary'] = summarize(records)
    return result


def deterministic(result):
    result = json.loads(encoded(result))
    for record in result['records']:
        record.pop('timing_seconds', None)
    return result


def report(result):
    lines = ['# Instrument foundry results', '', '**Scope:** authored finite exact-arithmetic program construction; no business accounts, market evidence or physical qualification.', '',
             'Protocol: [FOUNDRY_PROTOCOL.md](FOUNDRY_PROTOCOL.md). Source: [instrument_foundry.py](instrument_foundry.py). Exact records: [foundry-results.json](foundry-results.json).', '',
             '## All registered requests', '', '| Arm | Accepted | Certified nonidentifiable | Exhausted | Rejected | Scalar arithmetic operations |', '| --- | ---: | ---: | ---: | ---: | ---: |']
    for arm, s in result['summary']['all'].items():
        c = s['statuses']
        lines.append(f"| {arm} | {c.get('ACCEPTED', 0)} | {c.get('NONIDENTIFIABLE', 0)} | {c.get('EXHAUSTED', 0)} | {c.get('REJECTED', 0)} | {s['arithmetic']} |")
    lines += ['', '## Whole-episode cost by family', '', '| Family | Fresh | Frozen first generation | Accumulating | Conventional |', '| --- | ---: | ---: | ---: | ---: |']
    for family in ('shared', 'disjoint', 'changed', 'rank_deficient'):
        values = result['summary'][family]
        lines.append('| ' + family + ' | ' + ' | '.join(str(values[a]['arithmetic']) for a in ARMS) + ' |')
    lines += ['', 'Counts include executed construction, failed search, certificate checking and expanded runtime arithmetic. They are unit scalar rational-operation counts, not calibrated compute cost, money or profit. Bit lengths, serialization traffic, node visits, invalidations and descriptive timing are in the JSON.', '',
              'Fresh and frozen-first-generation policies are mechanism ablations. Conventional rank-aware reuse is the competitive comparator and may win. A positive accumulation difference does not establish an improved discovery policy: all supplied compilers remain fixed.', '',
              'Every accepted program remains in the supplied observation span. No retained program creates an unobserved distinction. Full-rank program fixtures, invalid-identity/type controls, a false-nullspace control and explicit exhaustion are checked separately from the 36 requests per arm.', '',
              '## Reproduce', '', '```sh', 'python3 examples/instrument_foundry.py --check', 'python3 examples/instrument_foundry.py --run --output /absolute/new/foundry-results.json', '```', '',
              'Run from `docs/agi-alpha-flywheel`. The check is a deterministic replay of public, exposed tasks, not new independent confirmation. Timing can vary and is excluded from exact replay equality. A new output path preserves the original registered record.', '',
              f"Run status: **{result['run_status']}**. Public protocol commit: `{PROTOCOL_COMMIT}`."]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description='Exact typed instrument construction; no network or financial accounts.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--run', action='store_true')
    group.add_argument('--check', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.check:
        expected = json.loads((ROOT / 'foundry-results.json').read_text())
        actual = run()
        if actual['run_status'] != 'COMPLETE' or deterministic(actual) != deterministic(expected):
            raise SystemExit('FAIL: source/protocol/results differ or deterministic replay is invalid')
        print('PASS: source-bound deterministic replay, exact certificates, adverse controls and expanded calls.')
    else:
        if args.output is None:
            parser.error('--run requires --output')
        if args.output.exists():
            raise SystemExit('Refusing to overwrite an existing registered result; choose a new output path.')
        result = run()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
        if args.output.resolve() == (ROOT / 'foundry-results.json').resolve():
            (ROOT / 'FOUNDRY.md').write_text(report(result))
        print(json.dumps({'run_status': result['run_status'], 'output': str(args.output), 'summary': result['summary']}, sort_keys=True))
        if result['run_status'] != 'COMPLETE':
            raise SystemExit(1)


if __name__ == '__main__':
    main()
