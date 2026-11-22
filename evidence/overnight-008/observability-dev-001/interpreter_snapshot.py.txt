"""Exact bounded linear-ambiguity interpreter, initialized after seccomp.

This checks and composes inert rational measurement programs. It cannot certify
global identifiability, physical calibration, costs, or buyer participation.
"""

def _gcd(a, b):
    while b:
        a, b = b, a % b
    return abs(a)


def _q(a, b=1):
    if not b:
        raise ValueError('ZERO_DENOMINATOR')
    if a.bit_length() > 8192 or b.bit_length() > 8192:
        raise ValueError('RATIONAL_GROWTH_LIMIT')
    d = _gcd(a, b)
    if b < 0:
        d = -d
    return a // d, b // d


def _parse(x):
    if type(x) is int and x.bit_length() <= 128:
        return x, 1
    if type(x) is not str or not 0 < len(x) <= 100:
        raise ValueError('RATIONAL_INPUT_REQUIRED')
    pieces = x.split('/')
    if len(pieces) not in (1, 2) or any(not s.lstrip('-').isdigit() for s in pieces):
        raise ValueError('RATIONAL_INPUT_REQUIRED')
    a, b = int(pieces[0]), int(pieces[1]) if len(pieces) == 2 else 1
    if a.bit_length() > 128 or b.bit_length() > 128:
        raise ValueError('RATIONAL_INPUT_LIMIT')
    return _q(a, b)


def _add(a, b):
    return _q(a[0] * b[1] + b[0] * a[1], a[1] * b[1])


def _neg(a):
    return -a[0], a[1]


def _mul(a, b):
    return _q(a[0] * b[0], a[1] * b[1])


def _div(a, b):
    return _q(a[0] * b[1], a[1] * b[0])


def _text(a):
    return str(a[0]) if a[1] == 1 else str(a[0]) + '/' + str(a[1])


def _rows(values, n):
    if type(values) is not list or len(values) > 512:
        raise ValueError('ROW_COUNT_LIMIT')
    if any(type(row) is not list or len(row) != n for row in values):
        raise ValueError('ROW_WIDTH')
    return [[_parse(x) for x in row] for row in values]


def _rank(rows, n):
    a = [row[:] for row in rows if any(x[0] for x in row)]
    r = 0
    for c in range(n):
        pivot = next((j for j in range(r, len(a)) if a[j][c][0]), None)
        if pivot is None:
            continue
        a[r], a[pivot] = a[pivot], a[r]
        z = a[r][c]
        a[r] = [_div(x, z) for x in a[r]]
        for j in range(r + 1, len(a)):
            z = a[j][c]
            if z[0]:
                a[j] = [_add(x, _neg(_mul(z, y))) for x, y in zip(a[j], a[r])]
        r += 1
        if r == len(a):
            break
    return r


def _validate(payload):
    if type(payload) is not dict or payload.get('language') != 'linear-ambiguity-plan/v1':
        raise ValueError('LANGUAGE')
    n = payload.get('dimension')
    if type(n) is not int or not 1 <= n <= 48:
        raise ValueError('DIMENSION_LIMIT')
    rows = _rows(payload.get('constraints'), n)
    measurements = payload.get('measurements')
    if type(measurements) is not list or len(measurements) > 32:
        raise ValueError('MEASUREMENT_COUNT_LIMIT')
    ids, parsed = set(), []
    for item in measurements:
        if type(item) is not dict or set(item) != {'id', 'row', 'calibrated', 'cost_units'}:
            raise ValueError('MEASUREMENT_SCHEMA')
        name = item['id']
        if type(name) is not str or not 0 < len(name) <= 100 or name in ids:
            raise ValueError('MEASUREMENT_ID')
        if type(item['calibrated']) is not bool or type(item['cost_units']) is not int or not 0 <= item['cost_units'] <= 1000000000:
            raise ValueError('MEASUREMENT_CONDITION')
        ids.add(name)
        parsed.append((item, _rows([item['row']], n)[0]))
    obligation = payload.get('requires_absolute_calibration')
    if type(obligation) is not bool:
        raise ValueError('TYPED_CALIBRATION_OBLIGATION')
    max_plans = payload.get('max_plans', 256)
    if type(max_plans) is not int or not 1 <= max_plans <= 2048:
        raise ValueError('PLAN_SEARCH_LIMIT')
    return n, rows, parsed, obligation, max_plans


def interpret(payload):
    n, rows, measurements, obligation, cap = _validate(payload)
    initial = _rank(rows, n)
    available, refused = [], []
    for item, row in measurements:
        if obligation and not item['calibrated']:
            refused.append({'id': item['id'], 'reason': 'UNKNOWN_GAIN_DOES_NOT_FIX_ABSOLUTE_SCALE'})
        else:
            available.append((item, row))
    mode = payload.get('mode', 'construct')
    if mode not in ('construct', 'ordinary', 'execute'):
        raise ValueError('MODE')
    checked, trace = 0, []
    selected, rank = [], initial
    if mode == 'execute':
        plan = payload.get('plan')
        if type(plan) is not list or any(type(x) is not str for x in plan) or len(set(plan)) != len(plan):
            raise ValueError('PLAN_SCHEMA')
        by_id = {item['id']: (item, row) for item, row in available}
        if any(x not in by_id for x in plan):
            raise ValueError('INAPPLICABLE_MEASUREMENT_IN_PLAN')
        selected = [by_id[x] for x in plan]
        rank = _rank(rows + [row for _, row in selected], n)
        checked = 1
    elif mode == 'construct':
        while rank < n and len(selected) < len(available):
            options = []
            for item, row in available:
                if any(x['id'] == item['id'] for x, _ in selected):
                    continue
                checked += 1
                if checked > cap:
                    return {'status': 'SEARCH_LIMIT', 'checked': cap, 'remaining_ambiguity': n - rank, 'scope': 'linear supplied ambiguity only'}
                after = _rank(rows + [r for _, r in selected] + [row], n)
                if after > rank:
                    options.append((item['cost_units'], item['id'], after, item, row))
            if not options:
                break
            _, _, after, item, row = min(options, key=lambda x: (x[0], x[1]))
            trace.append({'rank_before': rank, 'add': item['id'], 'rank_after': after})
            selected.append((item, row))
            rank = after
    else:
        best = None
        count = len(available)
        if count > 20:
            raise ValueError('ORDINARY_EXHAUSTIVE_SIZE_LIMIT')
        for mask in range(1 << count):
            if checked >= cap:
                return {'status': 'SEARCH_LIMIT', 'checked': checked, 'remaining_ambiguity': None, 'scope': 'linear supplied ambiguity only'}
            checked += 1
            subset = [available[i] for i in range(count) if mask & (1 << i)]
            cost = sum(item['cost_units'] for item, _ in subset)
            if best is not None and (cost, len(subset)) >= best[:2]:
                continue
            after = _rank(rows + [r for _, r in subset], n)
            if after == n:
                best = (cost, len(subset), subset)
        if best is not None:
            selected, rank = best[2], n
    return {'status': 'DETECTED_LINEAR_AMBIGUITIES_REMOVED' if rank == n else 'INSUFFICIENT_MEASUREMENTS',
            'initial_ambiguity': n - initial, 'remaining_ambiguity': n - rank,
            'plan': [item['id'] for item, _ in selected], 'cost_units': sum(item['cost_units'] for item, _ in selected),
            'checked': checked, 'trace': trace, 'refused': refused,
            'scope': 'Supplied exact linear ambiguity constraints only; no global/practical identifiability, physical feasibility or commercial validation',
            'calibration_obligation_enforced': obligation, 'physical_calibration_acquired': False}
