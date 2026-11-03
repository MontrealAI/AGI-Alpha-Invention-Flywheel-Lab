from functools import lru_cache

METHOD = 'evidence-derived-qualified-reconciliation-v1'
RETAINED_FACTS = {
    'timeout': 'A missing request and a missing acknowledgement need different continuations.',
    'neither': 'Stale absence, non-idempotent replay, expiring holds and opaque observations require expanded state.',
    'fence': 'A tested present/absent fence can discriminate without repeating an effect.',
    'delay': 'A tested bounded wait can qualify a stale query within its measured delay.',
    'compensation': 'Cancellation on an empty token is not evidence that an existing effect is compensable.',
    'composition': 'Single-provider completion does not imply safe complementary bundle completion.',
    'scope': 'Finite synthetic interface; conformance probes do not certify arbitrary providers.'}


def _step(op, **extra):
    return dict(op=op, token='probe', **extra)


def _waits(ticks):
    return [_step('wait', ticks=min(8, ticks-i)) for i in range(0, ticks, 8)]


def construct(task, probe):
    trace, profiles = [], []
    remaining = task['probe_budget_microUSD']
    spent = 0

    def ask(provider, sequence, purpose):
        nonlocal remaining, spent
        cost = len(sequence)*provider['probe_unit_microUSD']
        if cost > remaining:
            trace.append({'action': 'stop_probe', 'provider': provider['id'], 'purpose': purpose,
                          'reason': 'declared_probe_budget', 'required_microUSD': cost,
                          'remaining_microUSD': remaining})
            return []
        result = probe(provider['id'], sequence)
        charge = result.get('cost_microUSD', 0)
        spent += charge
        remaining -= charge
        trace.append({'action': 'probe', 'provider': provider['id'], 'purpose': purpose,
                      'sequence': sequence, 'result': result})
        return result.get('observations', [])

    def known(row, effect, hold=0, response=None):
        return row.get('effect_count') == effect and row.get('hold_count') == hold and (
            response is None or row.get('response') == response)

    for provider in task['providers']:
        p = dict(provider, resolver=None, delay=0, compensation=False, prepared=False)
        rows = ask(provider, [_step('execute', fault='ack_lost'), _step('fence'),
                              _step('cancel')], 'distinguish_effect_query_and_compensation')
        if len(rows) == 3 and known(rows[0], 1):
            p['compensation'] = known(rows[2], 0, response='CANCELLED')
            if known(rows[1], 1, response='DONE'):
                absent = ask(provider, [_step('execute', fault='request_lost'), _step('fence')],
                             'validate_fence_on_genuine_absence')
                if len(absent) == 2 and known(absent[0], 0) and known(absent[1], 0, response='ABSENT'):
                    p['resolver'] = 'fence'
        if p['resolver'] is None:
            replay = ask(provider, [_step('execute', fault='ack_lost'), _step('execute')],
                         'test_immediate_fixed_token_replay')
            if len(replay) == 2 and known(replay[0], 1) and known(replay[1], 1, response='DONE'):
                if len(task['providers']) == 1:
                    p['resolver'] = 'retry'
                else:
                    trace.append({'action': 'reject_transfer', 'provider': p['id'],
                                  'candidate': 'reset_phase_immediate_replay',
                                  'reason': 'successor_global_clock_phase_not_qualified',
                                  'next': 'qualify_current_state_or_compensation_or_prepare'})
            elif len(replay) == 2 and replay[1].get('effect_count', 0) not in (0, 1, None):
                trace.append({'action': 'expand_hypotheses', 'provider': p['id'],
                              'added': 'non_idempotent_effects', 'evidence': 'measured_duplicate_replay'})
        if p['resolver'] is None:
            for delay in (0, 8, 16):
                seq = [_step('execute', fault='ack_lost'), *_waits(delay), _step('status')]
                rows = ask(provider, seq, 'qualify_bounded_status_delay')
                if not rows:
                    break
                if known(rows[0], 1) and known(rows[-1], 1, response='DONE'):
                    absent = ask(provider, [_step('execute', fault='request_lost'), *_waits(delay),
                                            _step('status')], 'validate_delayed_query_absence')
                    if absent and known(absent[0], 0) and known(absent[-1], 0, response='ABSENT'):
                        p['resolver'], p['delay'] = 'status', delay
                        if delay:
                            trace.append({'action': 'expand_hypotheses', 'provider': p['id'],
                                          'added': 'stale_observation_with_measured_delay',
                                          'delay_ticks': delay})
                        break
                if rows[-1].get('response') == 'UNKNOWN':
                    break
        if p['resolver'] is None and p['compensation']:
            p['resolver'] = 'compensate_on_uncertainty'
        profiles.append(p)

    def prepare(p):
        hold = ask(p, [_step('reserve', fault='ack_lost'), _step('reserve'), _step('cancel')],
                   'qualify_repeatable_reversible_hold')
        if not (len(hold) == 3 and known(hold[0], 0, 1) and known(hold[1], 0, 1,
                response='RESERVED') and known(hold[2], 0, response='CANCELLED')):
            return False
        commit = ask(p, [_step('reserve'), _step('commit', fault='ack_lost'), _step('commit')],
                     'construct_commit_reconciliation_primitive')
        p['prepared'] = (len(commit) == 3 and known(commit[0], 0, 1, response='RESERVED')
                         and known(commit[1], 1) and known(commit[2], 1, response='DONE'))
        return p['prepared']

    unresolved = [p for p in profiles if p['resolver'] is None]
    irreversible = [p for p in profiles if not p['compensation']]
    for p in unresolved:
        prepare(p)
    if len(irreversible) > 1:
        for p in irreversible:
            if not p['prepared']:
                prepare(p)
    irreducible = [p for p in profiles if not p['compensation'] and not p['prepared']]
    unsupported = [p for p in profiles if p['resolver'] is None and not p['prepared']]
    holds = [p for p in profiles if p['prepared']]
    critical_delay = 4*len(holds) + (irreducible[0]['delay']+4 if irreducible else 0)
    if holds and len(profiles) > 1:
        for p in holds:
            durable = ask(p, [_step('reserve'), *_waits(critical_delay), _step('commit')],
                          'qualify_hold_lifetime_for_composed_critical_interval')
            if not (durable and known(durable[0], 0, 1, response='RESERVED')
                    and known(durable[-1], 1, response='DONE')):
                unsupported.append(p)
    if unsupported or len(irreducible) > 1:
        program = {'entry': 'stop', 'nodes': {'stop': {'finish': 'aborted', 'obligations': []}}}
        trace.append({'action': 'stop', 'reason': 'no_qualified_complete_composition_in_allowance',
                      'unsupported': [p['id'] for p in unsupported],
                      'unprepared_irreversible_count': len(irreducible)})
    else:
        program = _compile(profiles)
        trace.append({'action': 'construct', 'primitive': 'qualified_reconciliation_and_obligation_graph',
                      'nodes': len(program['nodes']), 'profiles': profiles,
                      'scope': 'finite_synthetic_conformance_not_universal_guarantee'})
    return {'program': program, 'trace': trace, 'retained': RETAINED_FACTS,
            'method': METHOD, 'probe_cost_microUSD': spent,
            'construction_origin': 'included_model_agent_generated_then_deterministically_reused'}


def _compile(profiles):
    nodes, finish_cache = {}, {}
    by_id = {p['id']: p for p in profiles}

    def finish(kind, obligations=()):
        key = kind, tuple(sorted(set(obligations)))
        if key not in finish_cache:
            ident = 'n'+str(len(nodes))
            nodes[ident] = {'finish': kind, 'obligations': list(key[1])}
            finish_cache[key] = ident
        return finish_cache[key]

    def call(p, op, next_, ticks=None):
        ident = 'n'+str(len(nodes))
        nodes[ident] = dict(op=op, provider=p, token='order', next=next_)
        if ticks is not None:
            nodes[ident]['ticks'] = ticks
        return ident

    @lru_cache(None)
    def cleanup(cancelable, exposed=()):
        if not cancelable:
            return finish('unresolved' if exposed else 'aborted', exposed)
        p, *rest = cancelable
        ok = cleanup(tuple(rest), exposed)
        bad = cleanup(tuple(rest), tuple(sorted(set(exposed+(p,)))))
        return call(p, 'cancel', {'CANCELLED': ok, 'ABSENT': ok, '*': bad})

    normal = [p for p in profiles if p['compensation'] and not p['prepared']]
    prepared = [p for p in profiles if p['prepared']]
    irreversible = [p for p in profiles if not p['compensation'] and not p['prepared']]

    def rollback(effects, holds, uncertain=()):
        pending = set(effects+holds+uncertain)
        cancelable = tuple(sorted(p for p in pending if by_id[p]['compensation'] or p in holds))
        exposed = tuple(sorted(pending-set(cancelable)))
        return cleanup(cancelable, exposed)

    def execute(p, success, effects, holds):
        pid = p['id']
        failed = rollback(effects, holds)
        unknown = rollback(effects, holds, (pid,))
        retry = call(pid, 'execute', {'DONE': success, 'REFUSED': failed, 'UNSUPPORTED': failed, '*': unknown})
        if p['resolver'] == 'retry':
            recover = retry
        elif p['resolver'] in ('fence', 'status'):
            recover = call(pid, p['resolver'], {'DONE': success, 'ABSENT': retry, '*': unknown})
            for i in reversed(range(0, p['delay'], 8)):
                recover = call(pid, 'wait', {'*': recover}, min(8, p['delay']-i))
        else:
            recover = unknown
        return call(pid, 'execute', {'DONE': success, 'TIMEOUT': recover, 'REFUSED': failed,
                                    'UNSUPPORTED': failed, '*': unknown})

    def commit_phase(i, effects, holds):
        if i == len(prepared):
            return finish('delivered')
        p = prepared[i]['id']
        later_holds = tuple(x for x in holds if x != p)
        success = commit_phase(i+1, effects+(p,), later_holds)
        uncertain = rollback(effects, later_holds, (p,))
        failed = rollback(effects, holds)
        retry = call(p, 'commit', {'DONE': success, 'ABSENT': failed, 'REFUSED': failed, '*': uncertain})
        return call(p, 'commit', {'DONE': success, 'TIMEOUT': retry, 'ABSENT': failed,
                                  'REFUSED': failed, '*': uncertain})

    def irreversible_phase(effects, holds):
        if not irreversible:
            return commit_phase(0, effects, holds)
        p = irreversible[0]
        return execute(p, commit_phase(0, effects+(p['id'],), holds), effects, holds)

    def reserve_phase(i, effects, holds):
        if i == len(prepared):
            return irreversible_phase(effects, holds)
        pid = prepared[i]['id']
        success = reserve_phase(i+1, effects, holds+(pid,))
        failed = rollback(effects, holds)
        unknown = rollback(effects, holds+(pid,))
        retry = call(pid, 'reserve', {'RESERVED': success, 'REFUSED': failed,
                                     'UNSUPPORTED': failed, '*': unknown})
        return call(pid, 'reserve', {'RESERVED': success, 'TIMEOUT': retry,
                                    'REFUSED': failed, 'UNSUPPORTED': failed, '*': unknown})

    def normal_phase(i, effects):
        if i == len(normal):
            return reserve_phase(0, effects, ())
        p = normal[i]
        return execute(p, normal_phase(i+1, effects+(p['id'],)), effects, ())

    entry = normal_phase(0, ())
    return {'entry': entry, 'nodes': nodes}
