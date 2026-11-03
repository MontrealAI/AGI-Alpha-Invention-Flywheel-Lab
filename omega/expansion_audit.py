"""Read-only operating replay tied to exact native financial prefixes.

The trace contains public method observations, not an alternative balance model.
Financial observations are checked against the authenticated native action tape;
the market is then regenerated to verify paid reach and voluntary buyer choices.
Interrupted prefixes and resumed segments remain explicit rather than erased.
"""
from __future__ import annotations

import copy
import hashlib

from commercial.ledger import canonical, digest

SCHEMA = 'omega/expansion-operating-trace/v1'
METHODS = ('snapshot', 'advance', 'spend', 'deliver', 'order_receipt')
CENT = 10_000


class RecordingBridge:
    """Durably record bridge calls, with idempotent pending-call recovery.

    ``persist`` must durably save its argument before returning. The caller also
    preserves its signed MarketRunner checkpoint and calls ``begin_segment`` on
    every process start; native financial authority stays with NativeBridge.
    """
    def __init__(self, native, trace=None, persist=None):
        self.native = native
        self.persist = persist or (lambda value: None)
        self.trace = copy.deepcopy(trace) if trace is not None else {
            'schema': SCHEMA, 'values': [], 'calls': [], 'segments': [], 'pending': None}
        if self.trace.get('schema') != SCHEMA:
            raise ValueError('EXACT_OPERATING_TRACE_REQUIRED')
        self._values = {digest(v): i for i, v in enumerate(self.trace['values'])}
        if self.trace['pending'] is not None:
            self._complete_pending()

    def export(self):
        return copy.deepcopy(self.trace)

    def flush(self):
        """Persist buffered reads before the caller saves a market checkpoint."""
        self._save()

    def _save(self):
        self.persist(self.export())

    def _intern(self, value):
        value = copy.deepcopy(value)
        key = digest(value)
        if key not in self._values:
            self._values[key] = len(self.trace['values'])
            self.trace['values'].append(value)
        return self._values[key]

    def begin_segment(self, state):
        previous = self.trace['segments'][-1] if self.trace['segments'] else None
        if previous is not None and previous['end_call'] is None:
            previous['end_call'] = len(self.trace['calls'])
            previous['interrupted'] = True
        self.trace['segments'].append({'start_call': len(self.trace['calls']),
                                       'initial_state': copy.deepcopy(state),
                                       'end_call': None, 'final_state': None,
                                       'interrupted': False})
        self._save()

    def end_segment(self, state):
        if not self.trace['segments'] or self.trace['pending'] is not None:
            raise ValueError('NO_COMPLETE_OPERATING_SEGMENT')
        segment = self.trace['segments'][-1]
        segment['end_call'] = len(self.trace['calls'])
        segment['final_state'] = copy.deepcopy(state)
        self._save()

    def _complete_pending(self):
        p = self.trace['pending']
        result = getattr(self.native, p['method'])(*p['args'], **p['kwargs'])
        after = self.native.snapshot()
        row = [p['method'], self._intern(p['args']), self._intern(p['kwargs']),
               self._intern(result), p['before'], after['native_actions_count'],
               p['hour_before'], after['hour']]
        self.trace['calls'].append(row)
        self.trace['pending'] = None
        # Read observations cannot commit money. Buffer them until the next
        # mutation/segment boundary; the next durable intent includes them.
        if p['method'] not in {'snapshot', 'order_receipt'}:
            self._save()
        return copy.deepcopy(result)

    def _call(self, method, args, kwargs):
        if self.trace['pending'] is not None:
            raise ValueError('PENDING_BRIDGE_CALL_REQUIRES_RECOVERY')
        before = self.native.snapshot()
        self.trace['pending'] = {'method': method, 'args': list(copy.deepcopy(args)),
                                 'kwargs': copy.deepcopy(kwargs),
                                 'before': before['native_actions_count'],
                                 'hour_before': before['hour']}
        if method not in {'snapshot', 'order_receipt'}:
            self._save()
        return self._complete_pending()

    def snapshot(self): return self._call('snapshot', (), {})
    def advance(self, hour): return self._call('advance', (hour,), {})
    def spend(self, *args, **kwargs): return self._call('spend', args, kwargs)
    def deliver(self, order): return self._call('deliver', (order,), {})
    def order_receipt(self, ident): return self._call('order_receipt', (ident,), {})


def _prefix_hashes(actions):
    h = hashlib.sha256(b'[')
    result = [digest([])]
    for i, action in enumerate(actions):
        if i:
            h.update(b',')
        h.update(canonical(action))
        end = h.copy(); end.update(b']')
        result.append(end.hexdigest())
    return result


def _snapshot(actions, initial, prefixes, count, hour):
    summary = actions[count - 1]['after'] if count else initial
    pairs = [('available', 'available'), ('cash', 'cash'), ('profit', 'profit'),
             ('unrestricted_earned', 'unrestrictedEarned'), ('payables', 'payables'),
             ('tail_reserve', 'tailReserve')]
    return {**{a + '_cents': summary[b] // CENT for a, b in pairs}, 'hour': hour,
            'native_actions_count': count, 'native_actions_sha256': prefixes[count]}


class _TraceEnded(Exception):
    pass


class _ReplayBridge:
    def __init__(self, trace, start, end):
        self.trace, self.index, self.end = trace, start, end

    def _call(self, method, args, kwargs):
        if self.index >= self.end:
            raise _TraceEnded()
        row = self.trace['calls'][self.index]
        values = self.trace['values']
        if row[0] != method or canonical(values[row[1]]) != canonical(list(args)) or values[row[2]] != kwargs:
            raise ValueError('MARKET_CALL_DOES_NOT_REPLAY:' + str(self.index))
        self.index += 1
        return copy.deepcopy(values[row[3]])

    def snapshot(self): return self._call('snapshot', (), {})
    def advance(self, hour): return self._call('advance', (hour,), {})
    def spend(self, *args, **kwargs): return self._call('spend', args, kwargs)
    def deliver(self, order): return self._call('deliver', (order,), {})
    def order_receipt(self, ident): return self._call('order_receipt', (ident,), {})


def _receipt(actions, count, request, returned, config):
    """Validate order observations from native operations, not seller flags."""
    if not isinstance(returned, dict) or returned.get('request') != request:
        raise ValueError('ORDER_OBSERVATION_REQUEST_CHANGED')
    ident = request['id']
    events = [a for a in actions[:count]
              if a['op'] == 'event' and a['args']['id'] == ident]
    names = [a['args']['action'] for a in events]
    collected = 'release' in names
    paid_cost = sum(a['args']['amount'] for a in actions[:count] if a['op'] == 'cost'
                    and (a['args']['id'].startswith('exp-order:' + ident + ':')
                         or a['args']['id'] == 'exp-tax:' + ident))
    expected_contribution = ((request['price_cents'] * CENT if collected else 0) - paid_cost) // CENT
    if returned.get('collected') is not collected or returned.get('collected_cents') != (request['price_cents'] if collected else 0):
        raise ValueError('FUTURE_OR_FICTITIOUS_COLLECTION_OBSERVED')
    if returned.get('contribution_cents') != expected_contribution:
        raise ValueError('ORDER_PROFIT_DOES_NOT_MATCH_NATIVE_PREFIX')
    status = returned.get('status')
    if status == 'released' and not collected:
        raise ValueError('UNRELEASED_ORDER_REPORTED_COLLECTED')
    if status == 'accepted_uncollected' and ('prepare' not in names or collected):
        raise ValueError('INVALID_UNCOLLECTED_ACCEPTANCE')
    if status == 'refunded' and 'refund' not in names:
        raise ValueError('REFUND_NOT_NATIVE')
    if status == 'nonpayment' and ('cancel' not in names or request['pay']):
        raise ValueError('NONPAYMENT_NOT_NATIVE')
    if status in {'declined', 'liquidity_deferred'} and events:
        raise ValueError('DECLINED_ORDER_HAS_NATIVE_COMMITMENT')
    if status not in {'declined', 'liquidity_deferred', 'nonpayment', 'refunded', 'accepted_uncollected', 'released'}:
        raise ValueError('UNKNOWN_ORDER_OBSERVATION')
    return collected


def audit_market(world, mode, seed, settings, state, trace, native_record, *, root, manifest):
    """Replay every operation, with financial observations bound to native tape."""
    from connected_enterprise.finance import audit_journal
    from omega.expansion_market import MarketRunner
    from omega.expansion_native import validate_order

    financial = audit_journal(native_record, root=root, manifest=manifest)
    if not financial['accepted']:
        raise ValueError('NATIVE_FINANCIAL_AUDIT_REQUIRED')
    if not isinstance(trace, dict) or set(trace) != {'schema', 'values', 'calls', 'segments', 'pending'} or trace['schema'] != SCHEMA or trace['pending'] is not None:
        raise ValueError('COMPLETE_OPERATING_TRACE_REQUIRED')
    actions = native_record['ledger']['actions']
    if not actions:
        raise ValueError('NATIVE_COMPLETE_HISTORY_REQUIRED')
    initial = actions[0]['before']; prefixes = _prefix_hashes(actions)
    journal = {e['key']: e for e in native_record['connected_journal']['entries']}
    previous, previous_hour, requests, observed_spends = 0, 0, {}, set()
    for i, row in enumerate(trace['calls']):
        if not isinstance(row, list) or len(row) != 8 or row[0] not in METHODS:
            raise ValueError('INVALID_OPERATING_CALL')
        method, ai, ki, ri, before, after, bhour, ahour = row
        if any(type(v) is not int or v < 0 for v in (ai, ki, ri, before, after, bhour, ahour)):
            raise ValueError('INVALID_OPERATING_CALL_INDEX')
        if before != previous or bhour != previous_hour or not before <= after <= len(actions) or ahour < bhour:
            raise ValueError('NONCONTIGUOUS_NATIVE_OPERATING_PREFIX')
        if any(a['day'] > ahour for a in actions[before:after]):
            raise ValueError('FUTURE_NATIVE_ACTION_IN_OBSERVATION')
        try:
            args, kwargs, result = (trace['values'][j] for j in (ai, ki, ri))
        except IndexError:
            raise ValueError('MISSING_OPERATING_VALUE') from None
        if not isinstance(args, list) or not isinstance(kwargs, dict):
            raise ValueError('INVALID_OPERATING_ARGUMENTS')
        if method in {'snapshot', 'advance'}:
            if result != _snapshot(actions, initial, prefixes, after, ahour):
                raise ValueError('FINANCIAL_OBSERVATION_NOT_NATIVE_PREFIX')
            if method == 'snapshot' and (before != after or bhour != ahour):
                raise ValueError('READ_ONLY_SNAPSHOT_MUTATED')
            if method == 'advance' and args != [ahour]:
                raise ValueError('OPERATING_CLOCK_CHANGED')
        elif method == 'spend':
            if len(args) != 4 or type(result) is not bool:
                raise ValueError('EXACT_SPEND_OBSERVATION_REQUIRED')
            ident, cents, hour, category = args
            entry = journal.get('spend:' + ident)
            expected = {'operation': 'spend', 'id': ident, 'kind': category,
                        'amount': cents * CENT, 'day': hour,
                        'work': {'resource': category, 'quote_cents': cents},
                        'expected_net': kwargs.get('expected_net_cents', 1) * CENT,
                        'allow_seed': kwargs.get('allow_seed', True)}
            if result and cents:
                if entry is None or entry['status'] != 'COMPLETE' or entry['request'] != expected or entry['receipt']['native_event_sequence'] >= after:
                    raise ValueError('UNFUNDED_ACQUISITION_OR_WORK')
                observed_spends.add(ident)
            elif entry is not None and entry['status'] == 'COMPLETE' and entry['receipt']['native_event_sequence'] < after:
                raise ValueError('COMMITTED_COST_REPORTED_UNFUNDED')
            elif not result:
                summary = actions[after - 1]['after'] if after else initial
                earned = (expected['expected_net'] > 0 and
                          min(summary['available'], summary['unrestrictedEarned']) >= cents * CENT)
                accessible = expected['allow_seed'] and summary['available'] >= cents * CENT
                if cents == 0 or (not summary['investmentStopped'] and (earned or accessible)):
                    raise ValueError('AVAILABLE_FUNDING_FALSELY_REJECTED')
        elif method == 'deliver':
            if len(args) != 1:
                raise ValueError('EXACT_ORDER_CALL_REQUIRED')
            request = validate_order(args[0])
            first_admission = request['id'] not in requests
            if request['id'] in requests and requests[request['id']] != request:
                raise ValueError('REPLAY_ORDER_REQUEST_CHANGED')
            requests[request['id']] = request
            _receipt(actions, after, request, result, manifest['config'])
            if first_admission and result['status'] in {'declined', 'liquidity_deferred'}:
                qualified = request['choice'] and request['acquired'] and request['budget_cents'] >= request['price_cents']
                if result['status'] == 'declined' and qualified:
                    raise ValueError('VOLUNTARY_ORDER_FALSELY_DECLINED')
                cfg = manifest['config']
                processing = (request['price_cents'] * cfg['payment_bps'] + 9999) // 10000 + cfg['payment_fixed_cents']
                required = (request['price_cents'] + sum(cfg['unit_costs_cents'].values()) + processing + 20) * CENT
                summary = actions[after - 1]['after'] if after else initial
                if result['status'] == 'liquidity_deferred' and (not qualified or summary['available'] >= required):
                    raise ValueError('AFFORDABLE_ORDER_FALSELY_DEFERRED')
        else:
            if len(args) != 1 or args[0] not in requests:
                raise ValueError('ORDER_OBSERVATION_BEFORE_REQUEST')
            _receipt(actions, after, requests[args[0]], result, manifest['config'])
            if before != after or bhour != ahour:
                raise ValueError('READ_ONLY_ORDER_OBSERVATION_MUTATED')
        previous, previous_hour = after, ahour

    # Every spend must be caused by the operating policy. Remaining native work
    # after the recorded market is restricted to settlement and the year marker.
    native_spends = {e['request']['id'] for e in journal.values()
                     if e['request']['operation'] == 'spend' and e['status'] == 'COMPLETE'}
    if native_spends != observed_spends:
        raise ValueError('UNEXPLAINED_NATIVE_INVESTMENT')
    for a in actions:
        if a['op'] == 'offer':
            if a['args']['id'] not in requests:
                raise ValueError('NATIVE_ORDER_WITHOUT_MARKET_CHOICE')
        if a['op'] == 'event' and a['args']['action'] == 'release':
            request = requests.get(a['args']['id'])
            if request is None or a['day'] != request['hour'] + request['collection_delay_hours']:
                raise ValueError('COLLECTION_TIMING_DOES_NOT_MATCH_CONTRACT')
    for a in actions[previous:]:
        permitted = a['op'] == 'mature' or (a['op'] == 'event' and a['args']['action'] == 'release') or (
            a['op'] == 'cost' and (a['args']['id'].startswith('exp-tax:') or
                                  (a['args']['id'] == 'exp-operating-complete' and a['args']['amount'] == 0)))
        if not permitted:
            raise ValueError('UNEXPLAINED_POST_MARKET_NATIVE_ACTION')

    cursor = 0
    if not trace['segments']:
        raise ValueError('REGISTERED_OPERATING_SEGMENT_REQUIRED')
    fresh = MarketRunner(world, mode=mode, seed=seed, settings=settings).export()
    permitted_checkpoints = {digest(fresh)}
    for number, segment in enumerate(trace['segments']):
        if segment['start_call'] != cursor or type(segment['end_call']) is not int or segment['end_call'] < cursor:
            raise ValueError('OPERATING_SEGMENT_GAP')
        if digest(segment['initial_state']) not in permitted_checkpoints:
            raise ValueError('UNAUTHORED_INITIAL_OR_RECOVERY_STATE_REQUIRED')
        runner = MarketRunner(world, mode=mode, seed=seed, settings=settings, state=segment['initial_state'])
        replay = _ReplayBridge(trace, cursor, segment['end_call'])
        exhausted = False
        try:
            runner.run(replay, lambda checkpoint: permitted_checkpoints.add(digest(checkpoint)))
        except _TraceEnded:
            exhausted = True
        if replay.index != segment['end_call']:
            raise ValueError('UNUSED_OPERATING_OBSERVATIONS')
        if segment['interrupted']:
            if not exhausted or segment['final_state'] is not None:
                raise ValueError('INVALID_INTERRUPTED_SEGMENT')
        elif exhausted or runner.export() != segment['final_state']:
            raise ValueError('MARKET_FINAL_STATE_DOES_NOT_REPLAY')
        cursor = segment['end_call']
    if cursor != len(trace['calls']) or trace['segments'][-1]['final_state'] != state or not state.get('completed'):
        raise ValueError('INCOMPLETE_OPERATING_YEAR')
    return {'accepted': True, 'scope': 'NATIVE_PREFIX_BOUND_CAUSAL_MARKET_REPLAY',
            'trace_sha256': digest(trace), 'state_sha256': digest(state),
            'native_actions_sha256': native_record['ledger']['actions_sha256'],
            'calls': len(trace['calls']), 'segments': len(trace['segments']),
            'order_requests': len(requests), 'funded_work': len(observed_spends),
            'market_assumptions_empirically_validated': False,
            'independent_algorithm_discovery_or_market_forecast': False}
