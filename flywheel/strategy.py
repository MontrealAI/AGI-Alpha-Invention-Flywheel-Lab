"""Finite typed strategy synthesis. No Python proposals, eval or candidate-owned judge."""

def permutations(items):
    if not items:
        yield ()
    for i, item in enumerate(items):
        for tail in permutations(items[:i] + items[i+1:]):
            yield (item,) + tail

OPS = ('reserve', 'start', 'work', 'complete', 'manifest', 'build', 'publish')


def discover(donors, target):
    reports = []
    tn = {n['id']: n for n in target['nodes']}
    for donor in donors:
        dn = {n['id']: n for n in donor['nodes']}
        mappings = []
        if len(dn) == len(tn) and len(tn) <= 7:
            for permutation in permutations(list(tn)):
                m = dict(zip(dn, permutation))
                if any((n['kind'], n['unit']) != (tn[m[k]]['kind'], tn[m[k]]['unit']) for k, n in dn.items()):
                    continue
                mapped = {(m[a], r, m[b]) for a, r, b in donor['relations']}
                if mapped <= {tuple(e) for e in target['relations']}:
                    mappings.append(m)
        mismatches = [k for k, v in donor['conditions'].items() if target['conditions'].get(k) != v]
        reports.append({'source': donor['id'], 'target': target['id'], 'correspondences': mappings,
                        'preserved_relations': donor['relations'] if mappings else [],
                        'changed_assumptions': target.get('changed_assumptions', []),
                        'unresolved_mismatches': mismatches, 'applicable': bool(mappings) and not mismatches,
                        'origin': 'developer supplied donor representation; exhaustive structural matcher selected mapping',
                        'prediction': 'Moving the exception scope before initialization preserves an incomplete marker on initialization interruption',
                        'expected_benefit': 'Evidence completeness under declared process interruption boundary; no economic claim'})
    return sorted(reports, key=lambda r: (not r['applicable'], r['source']))


def validate(task, program):
    if set(program) != {'body', 'protected_from'}:
        raise ValueError('PROGRAM_FIELDS')
    body, guard = program['body'], program['protected_from']
    if not isinstance(body, list) or not 1 <= len(body) <= 7 or any(x not in OPS for x in body):
        raise ValueError('TYPED_OPERATIONS')
    if len(set(body)) != len(body) or set(body) != set(task['phases']):
        raise ValueError('PHASE_EFFECTS')
    if type(guard) is not int or not 0 <= guard <= len(body):
        raise ValueError('GUARD_BOUND')
    if body[0] != 'reserve':
        raise ValueError('RESERVATION_FIRST')
    if any(body.index(a) >= body.index(b) for a, b in task['dependencies']):
        raise ValueError('DEPENDENCY_ORDER')
    return True


def interpret(payload):
    task, program = payload['task'], payload['program']
    validate(task, program)
    fail = payload.get('interrupt_at')
    if fail is not None and fail not in program['body']:
        raise ValueError('UNKNOWN_FAILURE_POINT')
    trace, reserved = [], False
    for index, phase in enumerate(program['body']):
        if phase == fail:
            marked = reserved and index >= program['protected_from']
            return {'trace': trace, 'state': 'INCOMPLETE' if marked else 'UNMARKED',
                    'interrupted_marker': marked, 'completed': False, 'failure_at': phase}
        trace.append(phase)
        reserved = reserved or phase == 'reserve'
    return {'trace': trace, 'state': 'COMPLETE', 'completed': True, 'interrupted_marker': False}


def synthesize(task, constraints, max_candidates=64, inherited=None):
    if not 1 <= max_candidates <= 256:
        raise ValueError('SEARCH_BOUND')
    required = []
    for constraint in constraints:
        if constraint.get('status') != 'established' or constraint.get('kind') != 'protect_phase':
            raise ValueError('UNADJUDICATED_CONSTRAINT')
        if constraint['phase'] not in task['phases']:
            raise ValueError('CONSTRAINT_PHASE')
        required.append(constraint['phase'])
    guard_order = [task['phases'].index('work') if 'work' in task['phases'] else len(task['phases'])-1]
    if inherited is not None:
        if inherited != {'operator': 'protect_initialization', 'language': 'bounded-evidence/v1'}:
            raise ValueError('UNSUPPORTED_OPERATOR')
        guard_order = [1]
    guard_order += [g for g in range(len(task['phases'])+1) if g not in guard_order]
    attempts = []
    for body in permutations(task['phases']):
        for guard in guard_order:
            if len(attempts) >= max_candidates:
                return {'status': 'exhausted', 'program': None, 'attempts': attempts}
            program = {'body': list(body), 'protected_from': guard}
            try:
                validate(task, program)
                errors = [p for p in required if not interpret({'task': task, 'program': program, 'interrupt_at': p})['interrupted_marker']]
            except ValueError as exc:
                errors = [str(exc)]
            attempts.append({'program': program, 'violations': errors})
            if not errors:
                return {'status': 'constructed', 'program': program, 'attempts': attempts,
                        'novelty': 'new bounded composition/guard scope, no new primitive or unrestricted invention',
                        'effects': 'pure protocol interpreter; file effects require separate fixed trusted executor'}
    return {'status': 'exhausted', 'program': None, 'attempts': attempts}
