"""Evaluator-owned authored tool semantics and development-only observation API."""
from __future__ import annotations
import copy
import hashlib
import itertools
import json


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate_request(request):
    if not isinstance(request, dict) or set(request) != {'id', 'stage', 'family', 'seed'}:
        raise ValueError('EXACT_OUTLEARNING073_REQUEST_REQUIRED')
    if not isinstance(request['id'], str) or not 1 <= len(request['id']) <= 80 or request['stage'] not in {'K1', 'K2'} or request['family'] not in {'development', 'confirmation'} or type(request['seed']) is not int or not 0 <= request['seed'] < 10000:
        raise ValueError('BOUNDED_OUTLEARNING073_REQUEST_REQUIRED')
    if request['family'] == 'development' and request['stage'] != 'K1' or request['family'] == 'confirmation' and request['stage'] != 'K2':
        raise ValueError('DECLARED_STAGE_FAMILY_REQUIRED')
    if request['family'] == 'development' and request['seed'] not in range(4) or request['family'] == 'confirmation' and request['seed'] not in range(100, 124):
        raise ValueError('PREREGISTERED_REQUEST_SEED_REQUIRED')
    return copy.deepcopy(request)


def development_requests():
    return [{'id': 'k1-development-' + str(i), 'stage': 'K1', 'family': 'development', 'seed': i} for i in range(4)]


def confirmation_requests():
    return [{'id': 'k2-' + identity({'purpose': 'confirmation', 'sample': i})[:12], 'stage': 'K2', 'family': 'confirmation', 'seed': 100 + i} for i in range(24)]


def _spec(request):
    request = validate_request(request)
    dev = [
        ('global', 0, 2, False, 0),
        ('intent', 0, 2, False, 0),
        ('none', 2, 2, False, 0),
        ('none', None, None, False, 0),
    ]
    fresh = [
        ('global', 2, 3, False, 0),
        ('intent', None, 3, False, 0),
        ('none', 0, 3, False, 0),
        ('none', 2, 3, False, 0),
        ('none', None, None, False, 0),
        ('global', 2, 3, True, 0),
        ('intent', 0, 3, False, 40),
        ('none', 2, 3, True, 0),
    ]
    index = request['seed'] if request['family'] == 'development' else (request['seed'] - 100) % 8
    if not 0 <= index < (4 if request['family'] == 'development' else 8):
        raise ValueError('REGISTERED_REQUEST_SEED_REQUIRED')
    dedup, visibility, bound, noisy, probe_setup = (dev if request['family'] == 'development' else fresh)[index]
    seed = request['seed']
    if request['stage'] == 'K1':
        objects = [{'intent': 'archive' + str(i), 'content': 'source-object-' + identity({'seed': seed, 'object': i})[:20]} for i in range(2)]
        public = {'id': request['id'], 'stage': 'K1', 'objects': objects, 'intents': ['archive0', 'archive1'], 'dependencies': {}, 'output_contract': 'For each archive intent: exact content and sha256 of UTF-8 content.'}
    else:
        rows = [((seed + 17) * (i + 3) * (i + 5)) % 97 - 40 for i in range(5 + seed % 5)]
        public = {'id': request['id'], 'stage': 'K2', 'rows': rows, 'intents': ['reserve', 'publish'], 'dependencies': {'publish': 'reserve'}, 'output_contract': 'reserve={job_id,rows}; publish={job_id,count,sum,sum_squares,source_sha256}, source_sha256 is canonical JSON rows. Publish must use actual acknowledged reservation token.'}
    public.update(max_inflight=bound, visibility_bound=visibility, deadline=16, diagnostic_budget=32, probe_setup_units=probe_setup, operation_unit_cost=1, scope='AUTHORED_SOFTWARE_SANDBOX_ONLY')
    return {'request': request, 'public': public, 'dedup': dedup, 'visibility': visibility, 'bound': bound, 'noisy': noisy, 'probe_setup': probe_setup, 'semantic_family': index}


class ToolSandbox:
    def __init__(self, spec, faults, *, diagnostic=False):
        self.spec = spec
        self.faults = dict(faults)
        self.diagnostic = diagnostic
        self.time = 0
        self.pending = []
        self.effects = []
        self.keys = {}
        self.tokens = {}
        self.observed = {}
        self.calls = {}
        self.trace = []
        self.cost_units = 0
        self.stopped = False
        self.reason = None

    def _commit(self, effect):
        mode = self.spec['dedup']
        key = effect['key']
        scope = None if mode == 'none' or key is None else key if mode == 'global' else (effect['intent'], key)
        if scope is not None and scope in self.keys:
            return self.keys[scope]
        effect = copy.deepcopy(effect)
        effect.update(committed_at=self.time, token='token-' + identity({'intent': effect['intent'], 'n': len(self.effects), 'payload': effect['payload']})[:16])
        self.effects.append(effect)
        if scope is not None:
            self.keys[scope] = effect
        return effect

    def _advance(self, ticks=1):
        for _ in range(ticks):
            self.time += 1
            due = [x for x in self.pending if x[0] <= self.time]
            self.pending = [x for x in self.pending if x[0] > self.time]
            for _, effect in due:
                self._commit(effect)

    def _observation(self, intent, status, token=None):
        result = {'intent': intent, 'status': status, 'time': self.time}
        if token is not None:
            result['token'] = token
            self.tokens[intent] = token
        self.observed[intent] = status
        self.trace.append(copy.deepcopy(result))
        return result

    def _value(self, value, output):
        if isinstance(value, str) and value.startswith('$output:'):
            return copy.deepcopy(output.get(value[len('$output:'):]))
        return copy.deepcopy(value)

    def _write(self, step, output):
        intent, key = step['intent'], step.get('key')
        if key is not None and (not isinstance(key, str) or not 1 <= len(key) <= 160):
            raise ValueError('BOUNDED_KEY_REQUIRED')
        allowed = {'p0', 'p1'} if self.diagnostic else set(self.spec['public']['intents'])
        if intent not in allowed:
            raise ValueError('DECLARED_INTENT_REQUIRED')
        dependency = step.get('dependency')
        if isinstance(dependency, str) and dependency.startswith('$token:'):
            dependency = self.tokens.get(dependency[len('$token:'):])
        effect = {'intent': intent, 'key': key, 'payload': self._value(step.get('value'), output), 'dependency': dependency, 'submitted_at': self.time}
        self.calls[intent] = self.calls.get(intent, 0) + 1
        fault = self.faults.get(intent, 'ack') if self.calls[intent] == 1 else 'ack'
        if fault == 'drop_before':
            return self._observation(intent, 'timeout')
        if fault == 'late':
            delay = self.spec['bound'] if self.spec['bound'] is not None else 24
            self.pending.append((self.time + delay, effect))
            return self._observation(intent, 'timeout')
        committed = self._commit(effect)
        if fault == 'lost_ack':
            return self._observation(intent, 'timeout')
        return self._observation(intent, 'committed', committed['token'])

    def _read(self, intent):
        visibility = self.spec['visibility']
        if visibility is None:
            return self._observation(intent, 'unknown')
        visible = [e for e in self.effects if e['intent'] == intent and e['committed_at'] + visibility <= self.time]
        return self._observation(intent, 'committed', visible[-1]['token']) if visible else self._observation(intent, 'absent')

    def execute(self, steps, output=None, *, depth=0):
        if not isinstance(steps, list) or len(steps) > 80 or depth > 8:
            raise ValueError('BOUNDED_PLAN_REQUIRED')
        output = {} if output is None else output
        for step in steps:
            if self.stopped:
                break
            if not isinstance(step, dict) or 'op' not in step or self.cost_units >= 100:
                raise ValueError('BOUNDED_VALID_STEP_REQUIRED')
            op = step['op']
            if op == 'if':
                if set(step) != {'op', 'test', 'then', 'else'} or set(step['test']) != {'intent', 'is'}:
                    raise ValueError('EXACT_OBSERVATION_BRANCH_REQUIRED')
                test = step['test']
                self.execute(step['then'] if self.observed.get(test['intent']) == test['is'] else step['else'], output, depth=depth + 1)
                continue
            if op == 'stop':
                self.stopped, self.reason = True, str(step.get('reason', 'declined'))[:200]
                continue
            if op == 'wait':
                ticks = step.get('ticks')
                if type(ticks) is not int or not 0 <= ticks <= 40:
                    raise ValueError('BOUNDED_WAIT_REQUIRED')
                if self.cost_units + ticks > 100:
                    raise ValueError('OPERATION_ENVELOPE_EXCEEDED')
                self.cost_units += ticks
                self._advance(ticks)
                continue
            self.cost_units += 1
            self._advance()
            if op == 'write':
                if set(step) - {'op', 'intent', 'key', 'value', 'dependency'} or not {'op', 'intent', 'value'} <= set(step):
                    raise ValueError('EXACT_WRITE_REQUIRED')
                self._write(step, output)
            elif op == 'read':
                if set(step) != {'op', 'intent'}:
                    raise ValueError('EXACT_READ_REQUIRED')
                self._read(step['intent'])
            else:
                raise ValueError('DECLARED_OPCODE_REQUIRED')
        return self

    def drain(self):
        if self.pending:
            self._advance(max(due for due, _ in self.pending) - self.time)


class Session:
    def __init__(self, request):
        self._spec = _spec(request)
        self.public = copy.deepcopy(self._spec['public'])
        self.units_spent = 0
        self.probes = []

    def probe(self, actions):
        sandbox = ToolSandbox(self._spec, {'p0': 'lost_ack', 'p1': 'late'}, diagnostic=True)
        sandbox.execute(actions)
        charge = self._spec['probe_setup'] + sandbox.cost_units
        remaining = self.public['diagnostic_budget'] - self.units_spent
        if charge > remaining:
            result = {'status': 'unaffordable', 'cost_units': 0, 'quoted_units': charge, 'remaining_units': remaining, 'observations': [], 'effects': None}
        else:
            self.units_spent += charge
            counts = {intent: len([e for e in sandbox.effects if e['intent'] == intent]) for intent in ('p0', 'p1')}
            result = {'status': 'uncertain' if self._spec['noisy'] else 'observed', 'cost_units': charge, 'remaining_units': self.public['diagnostic_budget'] - self.units_spent, 'observations': copy.deepcopy(sandbox.trace), 'effects': None if self._spec['noisy'] else counts}
        self.probes.append({'actions': copy.deepcopy(actions), 'result': copy.deepcopy(result)})
        return result


def make_session(request):
    return Session(request)


def fault_schedules(public):
    return [dict(zip(public['intents'], faults)) for faults in itertools.product(('ack', 'drop_before', 'lost_ack', 'late'), repeat=len(public['intents']))]
