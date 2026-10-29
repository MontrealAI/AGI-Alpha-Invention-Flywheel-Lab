"""Typed event-plan construction by bounded obligation-guided graph rewrites.

Self-contained for the source-pinned seccomp interpreter. Strategies are inert
programs in a finite supplied language; the useful acceptance specification is
external and cannot be rewritten by candidates.
"""

LANGUAGE = 'event-plan/v1'
MAX_PHASES = 48
MAX_RULES = 48


def _identifier(value):
    return type(value) is str and 0 < len(value) <= 120 and all(c.isalnum() or c in '_.:-/' for c in value)


def validate_task(task):
    if type(task) is not dict or not _identifier(task.get('id')):
        raise ValueError('TASK_ID')
    phases = task.get('phases')
    if type(phases) is not list or not 1 <= len(phases) <= MAX_PHASES:
        raise ValueError('PHASE_BOUND')
    nodes = {}
    for phase in phases:
        if type(phase) is not dict or not {'id', 'kind', 'deps', 'unit'} <= set(phase):
            raise ValueError('TYPED_PHASE')
        if not _identifier(phase['id']) or not _identifier(phase['kind']) or phase['unit'] != 'event':
            raise ValueError('PHASE_TYPE_OR_UNIT')
        if phase['id'] in nodes:
            raise ValueError('DUPLICATE_PHASE')
        if type(phase['deps']) is not list or any(not _identifier(x) for x in phase['deps']) or len(set(phase['deps'])) != len(phase['deps']):
            raise ValueError('DEPENDENCY_TYPE')
        nodes[phase['id']] = phase
    if not any(p['kind'] == 'reserve' for p in phases):
        raise ValueError('RESERVATION_REQUIRED')
    if not any(p['kind'] == 'commit' for p in phases):
        raise ValueError('PUBLICATION_REQUIRED')
    for phase in phases:
        if phase['id'] in phase['deps'] or any(dep not in nodes for dep in phase['deps']):
            raise ValueError('UNKNOWN_OR_SELF_DEPENDENCY')
    _topological(nodes)
    return nodes


def _topological(nodes):
    remaining, order = set(nodes), []
    while remaining:
        ready = [key for key in remaining if set(nodes[key]['deps']) <= set(order)]
        if not ready:
            raise ValueError('CYCLIC_TASK')
        key = min(ready, key=lambda x: (nodes[x]['kind'] != 'reserve', nodes[x]['kind'] == 'commit', nodes[x]['kind'], x))
        order.append(key)
        remaining.remove(key)
    return order


def _ancestors(nodes, phase):
    pending, found = list(nodes[phase]['deps']), set()
    while pending:
        node = pending.pop()
        if node not in found:
            found.add(node)
            pending.extend(nodes[node]['deps'])
    return found


def validate(task, program):
    nodes = validate_task(task)
    if type(program) is not dict or set(program) != {'language', 'order', 'protected', 'atomic', 'compensations'} or program['language'] != LANGUAGE:
        raise ValueError('PROGRAM_SCHEMA')
    order = program['order']
    if type(order) is not list or len(order) != len(nodes) or len(set(order)) != len(order) or set(order) != set(nodes):
        raise ValueError('EXACT_PHASE_EFFECTS')
    done = set()
    for phase in order:
        if not set(nodes[phase]['deps']) <= done:
            raise ValueError('DEPENDENCY_ORDER')
        done.add(phase)
    if nodes[order[0]]['kind'] != 'reserve':
        raise ValueError('RESERVATION_FIRST')
    for name in ('protected', 'atomic'):
        values = program[name]
        if type(values) is not list or any(type(x) is not str for x in values) or len(set(values)) != len(values) or not set(values) <= set(nodes):
            raise ValueError('TYPED_SCOPE')
    compensations = program['compensations']
    if type(compensations) is not dict or not set(compensations) <= set(nodes):
        raise ValueError('COMPENSATION_SCHEMA')
    for phase, resources in compensations.items():
        if type(resources) is not list or any(type(x) is not str or x not in nodes for x in resources) or len(set(resources)) != len(resources):
            raise ValueError('COMPENSATION_EFFECTS')
        if any(nodes[x]['kind'] != 'reserve' or x not in _ancestors(nodes, phase) for x in resources):
            raise ValueError('COMPENSATION_CAUSALITY')
    return True


def interpret(payload):
    task, program = payload['task'], payload['program']
    validate(task, program)
    nodes = {p['id']: p for p in task['phases']}
    fail = payload.get('interrupt_at')
    stage = payload.get('interrupt_stage', 'before')
    if fail is not None and fail not in nodes:
        raise ValueError('UNKNOWN_FAILURE_POINT')
    if stage not in ('before', 'during'):
        raise ValueError('UNKNOWN_FAILURE_STAGE')
    trace, reserved, committed = [], [], False
    for phase in program['order']:
        if phase == fail:
            partial = stage == 'during' and nodes[phase]['kind'] == 'commit' and phase not in program['atomic']
            compensated = [x for x in program['compensations'].get(phase, []) if x in reserved]
            marked = bool(reserved) and phase in program['protected']
            return {'trace': trace, 'state': 'INCOMPLETE' if marked else 'UNMARKED',
                    'completed': False, 'complete_exists': committed or partial, 'failure_at': phase,
                    'interrupted_marker': marked, 'partial_publication': partial,
                    'atomic_publication': not partial, 'reserved': reserved,
                    'compensated': compensated, 'directory_created': bool(reserved)}
        trace.append(phase)
        if nodes[phase]['kind'] == 'reserve':
            reserved.append(phase)
        if nodes[phase]['kind'] == 'commit':
            committed = True
    return {'trace': trace, 'state': 'COMPLETE', 'completed': True, 'complete_exists': True,
            'failure_at': None, 'interrupted_marker': False, 'partial_publication': False,
            'atomic_publication': True, 'reserved': reserved, 'compensated': [],
            'directory_created': bool(reserved)}


def _obligations(nodes, values):
    if type(values) is not list or len(values) > MAX_RULES:
        raise ValueError('OBLIGATION_BOUND')
    normalized = []
    for value in values:
        if type(value) is not dict or value.get('kind') not in ('protect', 'atomic_publish', 'compensate'):
            raise ValueError('OBLIGATION_TYPE')
        phases = value.get('phase_ids')
        if type(phases) is not list or not phases or len(set(phases)) != len(phases) or any(type(x) is not str or x not in nodes for x in phases):
            raise ValueError('OBLIGATION_PHASES')
        if value.get('status', 'established') not in ('established', 'hypothesis'):
            raise ValueError('UNSUPPORTED_OBLIGATION_STATUS')
        resources = value.get('resource_phase_ids')
        if resources is not None and (type(resources) is not list or any(x not in nodes or nodes[x]['kind'] != 'reserve' for x in resources)):
            raise ValueError('OBLIGATION_RESOURCE_TYPE')
        normalized.append({'kind': value['kind'], 'phase_ids': sorted(phases), **({'resource_phase_ids': sorted(resources)} if resources is not None else {})})
    return normalized


def _operator_obligations(nodes, operator):
    if operator is None:
        return [], {'rules': 0, 'matches': 0}
    if type(operator) is not dict or operator.get('language') != 'event-plan-rewrite/v1':
        raise ValueError('OPERATOR_LANGUAGE')
    rules, cap = operator.get('rules'), operator.get('max_matches', 32)
    if type(rules) is not list or len(rules) > MAX_RULES or type(cap) is not int or not 1 <= cap <= MAX_PHASES * MAX_RULES:
        raise ValueError('OPERATOR_BOUND')
    result, matched = [], 0
    for rule in rules:
        if type(rule) is not dict or set(rule) != {'match', 'emit'}:
            raise ValueError('REWRITE_RULE')
        match, emit = rule['match'], rule['emit']
        if type(match) is not dict or not {'kind', 'unit'} <= set(match) or set(match) - {'kind', 'unit', 'phase_ids'}:
            raise ValueError('TYPED_MATCH')
        if not _identifier(match['kind']) or match['unit'] != 'event':
            raise ValueError('MATCH_TYPE')
        selection = match.get('phase_ids', list(nodes))
        if type(selection) is not list or any(x not in nodes for x in selection):
            raise ValueError('MATCH_PHASES')
        if type(emit) is not dict or set(emit) != {'kind', 'phase_ids'} or emit.get('kind') not in ('protect', 'atomic_publish', 'compensate') or emit.get('phase_ids') != ['$match']:
            raise ValueError('TYPED_REWRITE')
        for phase in sorted(selection):
            if nodes[phase]['kind'] == match['kind'] and nodes[phase]['unit'] == match['unit']:
                matched += 1
                if matched > cap:
                    raise ValueError('OPERATOR_MATCH_BOUND')
                result.append({'kind': emit['kind'], 'phase_ids': [phase]})
    return result, {'rules': len(rules), 'matches': matched}


def _violations(nodes, program, obligations):
    errors = []
    for obligation in obligations:
        for phase in obligation['phase_ids']:
            kind = obligation['kind']
            if kind == 'protect' and phase not in program['protected']:
                errors.append({'kind': kind, 'phase': phase})
            elif kind == 'atomic_publish' and phase not in program['atomic']:
                errors.append({'kind': kind, 'phase': phase})
            elif kind == 'compensate':
                resources = obligation.get('resource_phase_ids', [x for x in _ancestors(nodes, phase) if nodes[x]['kind'] == 'reserve'])
                if not set(resources) <= set(program['compensations'].get(phase, [])):
                    errors.append({'kind': kind, 'phase': phase, 'resources': sorted(resources)})
    return errors


def _rewrite(nodes, program, defect, closure=False):
    out = {'language': LANGUAGE, 'order': list(program['order']), 'protected': list(program['protected']),
           'atomic': list(program['atomic']), 'compensations': {k: list(v) for k, v in program['compensations'].items()}}
    phase, kind = defect['phase'], defect['kind']
    if kind == 'compensate':
        out['compensations'][phase] = sorted(set(out['compensations'].get(phase, [])) | set(defect['resources']))
    else:
        field = 'protected' if kind == 'protect' else 'atomic'
        scope = {phase}
        if closure:
            scope |= {x for x in _ancestors(nodes, phase) if nodes[x]['kind'] != 'reserve'}
        out[field] = sorted(set(out[field]) | scope)
    return out


def _identity(program):
    return (tuple(program['order']), tuple(program['protected']), tuple(program['atomic']),
            tuple((key, tuple(value)) for key, value in sorted(program['compensations'].items())))


def _cost(program):
    return len(program['protected']) + 2 * len(program['atomic']) + sum(len(x) for x in program['compensations'].values())


def construct(task, obligations=None, max_candidates=64, operator=None):
    nodes = validate_task(task)
    if type(max_candidates) is not int or not 1 <= max_candidates <= 256:
        raise ValueError('SEARCH_BOUND')
    inherited, operator_trace = _operator_obligations(nodes, operator)
    obligations = _obligations(nodes, (obligations or []) + inherited)
    base = {'language': LANGUAGE, 'order': _topological(nodes), 'protected': [], 'atomic': [], 'compensations': {}}
    pending, seen, attempts = [(base, [])], set(), []
    while pending and len(attempts) < max_candidates:
        pending.sort(key=lambda item: (_cost(item[0]) + len(_violations(nodes, item[0], obligations)),
                                       len(_violations(nodes, item[0], obligations)), _cost(item[0]), _identity(item[0])))
        program, delta = pending.pop(0)
        identity = _identity(program)
        if identity in seen:
            continue
        seen.add(identity)
        validate(task, program)
        violations = _violations(nodes, program, obligations)
        attempts.append({'program': program, 'violations': violations, 'delta': delta, 'logical_cost': _cost(program)})
        if not violations:
            return {'status': 'constructed', 'program': program, 'attempts': attempts, 'obligations': obligations,
                    'operator_trace': operator_trace, 'candidate_count': len(attempts),
                    'search': 'obligation-guided best-first typed graph rewrites; no permutations',
                    'novelty': 'New composition within supplied grammar; no new primitive or unrestricted invention',
                    'effects': 'Pure event-plan interpreter; actual file effects require trusted confined broker'}
        first = violations[0]
        for closure in (False, True):
            changed = _rewrite(nodes, program, first, closure)
            pending.append((changed, [{'repair': first, 'causal_closure': closure}]))
        bundle = program
        for defect in violations:
            bundle = _rewrite(nodes, bundle, defect)
        pending.append((bundle, [{'repair': defect, 'complementary_bundle': True} for defect in violations]))
    return {'status': 'exhausted', 'program': None, 'attempts': attempts, 'obligations': obligations,
            'operator_trace': operator_trace, 'candidate_count': len(attempts), 'reason': 'Declared candidate bound or exhausted frontier'}


def conventional(task):
    nodes = validate_task(task)
    order = _topological(nodes)
    program = {'language': LANGUAGE, 'order': order, 'protected': sorted(nodes),
               'atomic': sorted(x for x in nodes if nodes[x]['kind'] == 'commit'),
               'compensations': {x: sorted(y for y in _ancestors(nodes, x) if nodes[y]['kind'] == 'reserve') for x in nodes}}
    validate(task, program)
    return program


OLD_POLICY_SHA256 = '93b00697efbbdb2e29c357ee83f30e46ac220068783731568c297f0017453b17'
EVENT_CAPABILITIES = ('protect', 'atomic_publish', 'compensate')


def evaluate_policy(task, policy, capabilities, obligations=None, max_candidates=64):
    """Cross search policy with starting tools; return construction, never a grade.

The source-pinned historical search executes directly for <=7 canonical aliases.
For larger graphs its unchanged permutations generator executes through the
shared typed event-plan adapter. That adapter is not an original-engine result.
"""
    import hashlib
    from pathlib import Path
    import time
    started, cpu = time.monotonic(), time.process_time()
    nodes = validate_task(task)
    if policy not in ('old', 'new') or type(capabilities) is not list or len(set(capabilities)) != len(capabilities) or any(x not in EVENT_CAPABILITIES for x in capabilities):
        raise ValueError('POLICY_OR_CAPABILITY_SCHEMA')
    if type(max_candidates) is not int or not 1 <= max_candidates <= 256:
        raise ValueError('SEARCH_BOUND')
    required = _obligations(nodes, obligations or [])
    active = [x for x in required if x['kind'] in capabilities]
    unavailable = [x for x in required if x['kind'] not in capabilities]
    source_identity, adapter = None, None
    if policy == 'new':
        built = construct(task, active, max_candidates=max_candidates)
    else:
        path = Path(__file__).resolve().parents[1] / 'flywheel/strategy.py'
        if path.is_symlink() or not path.is_file():
            raise ValueError('OLD_POLICY_SOURCE_MISMATCH')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != OLD_POLICY_SHA256:
            raise ValueError('OLD_POLICY_SOURCE_MISMATCH')
        original = {'__name__': '_source_pinned_old_policy'}
        exec(compile(raw, str(path), 'exec'), original)
        source_identity = OLD_POLICY_SHA256
        phases = [p['id'] for p in task['phases']]
        protection = sorted({p for value in active if value['kind'] == 'protect' for p in value['phase_ids']})
        attempts, chosen = [], None

        def extend(order, guard):
            program = {'language': LANGUAGE, 'order': list(order),
                       'protected': sorted(order[guard:]) if 'protect' in capabilities else [],
                       'atomic': [], 'compensations': {}}
            for value in active:
                if value['kind'] != 'protect':
                    for phase in value['phase_ids']:
                        defect = {'kind': value['kind'], 'phase': phase}
                        if value['kind'] == 'compensate':
                            defect['resources'] = value.get('resource_phase_ids', [x for x in _ancestors(nodes, phase) if nodes[x]['kind'] == 'reserve'])
                        program = _rewrite(nodes, program, defect)
            return program

        if len(phases) <= 7:
            reserve = next(p for p in phases if nodes[p]['kind'] == 'reserve')
            available = iter(('start', 'work', 'complete', 'manifest', 'build', 'publish'))
            aliases = {p: 'reserve' if p == reserve else next(available) for p in phases}
            inverse = {value: key for key, value in aliases.items()}
            old_task = {'id': task['id'], 'phases': [aliases[p] for p in phases],
                        'dependencies': [[aliases[dep], aliases[p]] for p in phases for dep in nodes[p]['deps']]}
            constraints = [{'status': 'established', 'kind': 'protect_phase', 'phase': aliases[p]} for p in protection]
            old = original['synthesize'](old_task, constraints, max_candidates=max_candidates)
            for attempt in old['attempts']:
                candidate = attempt['program']
                rendered = extend([inverse[p] for p in candidate['body']], candidate['protected_from'])
                attempts.append({'program': rendered, 'violations': attempt['violations'], 'origin': 'actual old synthesize canonical alias adapter'})
            if old.get('program') is not None:
                candidate = old['program']
                chosen = extend([inverse[p] for p in candidate['body']], candidate['protected_from'])
            adapter = 'Actual unchanged old synthesize; bijective aliases only, shared additional primitive adapter'
        else:
            adapter = 'Actual unchanged old permutations; shared event-plan validator extends original <=7 representation; not original synthesize result'
            exhausted = False
            for order in original['permutations'](phases):
                for guard in [len(phases)-1] + [g for g in range(len(phases)+1) if g != len(phases)-1]:
                    if len(attempts) >= max_candidates:
                        exhausted = True
                        break
                    candidate = extend(order, guard)
                    try:
                        validate(task, candidate)
                        violations = _violations(nodes, candidate, active)
                    except ValueError as error:
                        violations = [{'kind': 'invalid', 'reason': str(error)}]
                    attempts.append({'program': candidate, 'violations': violations, 'origin': 'actual old permutations shared typed adapter'})
                    if not violations:
                        chosen = candidate
                        break
                if chosen is not None or exhausted:
                    break
        built = {'status': 'constructed' if chosen is not None else 'exhausted', 'program': chosen,
                 'attempts': attempts, 'candidate_count': len(attempts)}
    if built.get('program') is not None:
        validate(task, built['program'])
    adapter_identity = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return {**built, 'policy': policy, 'capabilities': sorted(capabilities),
            'unavailable_obligations': unavailable, 'old_source_sha256': source_identity,
            'policy_source_sha256': source_identity if policy == 'old' else adapter_identity,
            'adapter_source_sha256': adapter_identity,
            'adapter_scope': adapter, 'wall_seconds': time.monotonic()-started,
            'cpu_seconds': time.process_time()-cpu,
            'acceptance': 'UNASSESSED_EXTERNAL_SPECIFICATION_REQUIRED',
            'claim_scope': 'Developer-authored policy engineering comparison; no learned discovery policy or general superiority claim'}


def reframe(objective, method_assumptions, capabilities, snapshot_receipt=None):
    """Preserve ends and hard obligations while varying dependency provenance."""
    import hashlib
    import json
    if type(objective) is not dict or not {'source_identities', 'full_checks', 'service_obligations', 'safety_obligations'} <= set(objective):
        raise ValueError('EXPLICIT_OBJECTIVE_OBLIGATIONS_REQUIRED')
    if type(objective['source_identities']) is not dict or not objective['source_identities']:
        raise ValueError('SOURCE_IDENTITIES_REQUIRED')
    for field in ('full_checks', 'service_obligations', 'safety_obligations'):
        if type(objective[field]) is not list or not objective[field] or any(type(x) is not str or not x for x in objective[field]):
            raise ValueError('UNCHANGED_OBLIGATIONS_REQUIRED')
    if type(method_assumptions) not in (dict, list) or type(capabilities) is not list or any(type(x) is not str for x in capabilities):
        raise ValueError('REFRAME_INPUT_SCHEMA')
    encoded = json.dumps(objective, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    frozen = json.loads(encoded)
    objective_hash = hashlib.sha256(encoded).hexdigest()
    receipt = snapshot_receipt or {}
    supported = (type(receipt) is dict and receipt.get('verified') is True
                 and receipt.get('objective_sha256') == objective_hash
                 and receipt.get('source_identities') == frozen['source_identities']
                 and type(receipt.get('checks')) is dict
                 and set(receipt['checks']) == set(frozen['full_checks'])
                 and all(value is True for value in receipt['checks'].values()))
    alternatives = []
    for representation, available in [('git_history', 'git_history' in capabilities),
                                       ('verified_snapshot', 'verified_snapshot' in capabilities and supported)]:
        alternatives.append({'representation': representation, 'objective_sha256': objective_hash,
                             'objective': frozen, 'status': 'admitted' if available else 'refused',
                             'removes_git_dependency': representation == 'verified_snapshot',
                             'requirements': 'All exact source, full-check, service and safety obligations retained',
                             'evidence_scope': 'Snapshot admission requires an objective-bound external verification receipt; hashes bind identity, not truth'})
    return {'objective': frozen, 'objective_sha256': objective_hash,
            'method_assumptions': json.loads(json.dumps(method_assumptions, allow_nan=False)),
            'alternatives': alternatives,
            'snapshot_receipt_supported': supported,
            'claim_scope': 'Dependency-provenance reframing, not relaxation of the useful objective or historical proof'}
