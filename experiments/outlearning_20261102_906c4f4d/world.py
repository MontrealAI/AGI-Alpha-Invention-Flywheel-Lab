import copy
import hashlib
import json
import random

OPS = ('execute', 'reserve', 'commit', 'cancel', 'status', 'fence', 'wait')
RESPONSES = ('DONE', 'ABSENT', 'RESERVED', 'CANCELLED', 'TIMEOUT', 'UNSUPPORTED', 'REFUSED', 'UNKNOWN')
SCHEDULES = ('healthy', 'lost_request', 'lost_ack', 'provider_refusal')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def provider_config(kind):
    base = {'idempotency': 'none', 'status': 'linearizable', 'fence': True,
            'prepare': False, 'compensation': True, 'status_lag': 0, 'key_ttl': 2,
            'hold_ttl': 0, 'effect_cost_microUSD': 8000000}
    overrides = {
        'durable': {'idempotency': 'persistent', 'prepare': True},
        'query': {},
        'stale': {'status': 'stale', 'status_lag': 3},
        'prepared': {'status': 'opaque', 'fence': False, 'prepare': True, 'compensation': False},
        'expiring': {'idempotency': 'epoch', 'status': 'stale', 'status_lag': 4, 'fence': False, 'compensation': False},
        'eventual': {'status': 'stale', 'status_lag': 3, 'fence': False},
        'irreversible': {'idempotency': 'persistent', 'status': 'opaque', 'fence': False, 'compensation': False},
        'opaque': {'status': 'opaque', 'fence': False, 'compensation': False},
        'fragile_hold': {'prepare': True, 'hold_ttl': 2, 'compensation': False},
    }
    if kind not in overrides:
        raise ValueError('UNKNOWN_PROVIDER_KIND')
    base.update(overrides[kind])
    return base


def make_world(seed, stage='K2', stratum=0):
    if stage not in ('K1', 'K2') or type(stratum) is not int or not 0 <= stratum < (8 if stage == 'K1' else 6):
        raise ValueError('REGISTERED_WORLD_FAMILY_REQUIRED')
    rng = random.Random(int(digest({'seed': str(seed), 'stage': stage}), 16))
    if stage == 'K1':
        kinds = [('durable',), ('query',), ('stale',), ('prepared',), ('expiring',), ('eventual',), ('irreversible',), ('opaque',)][stratum]
    else:
        families = [
            ('durable', 'prepared', 'durable'),
            ('query', 'stale', 'eventual'),
            ('irreversible', 'opaque'),
            ('stale', 'query', 'stale'),
            ('expiring', 'fragile_hold', 'irreversible'),
            ('opaque', 'eventual', 'prepared'),
        ]
        kinds = list(families[stratum])
        if rng.randrange(2) and len(kinds) == 3:
            kinds = kinds[:2]
        rng.shuffle(kinds)
    providers = []
    for i, kind in enumerate(kinds):
        cfg = provider_config(kind)
        if stage == 'K2':
            cfg['status_lag'] += rng.randrange(2) if cfg['status'] == 'stale' else 0
            cfg['key_ttl'] = 2 + rng.randrange(2)
            cfg['effect_cost_microUSD'] = rng.choice((6000000, 8000000, 12000000))
        ident = 'provider-' + digest({'seed': str(seed), 'slot': i})[:10]
        probe_unit = 250000 if stage == 'K1' else rng.choice((100000, 250000, 1000000, 3000000))
        providers.append({'id': ident, 'config': cfg, 'probe_unit_microUSD': probe_unit,
                          'call_microUSD': rng.choice((100000, 200000, 400000)),
                          'sandbox_noise': stage == 'K2' and stratum == 5})
    return {'schema': 'outlearning-protocol-world/v1', 'stage': stage,
            'world_id': digest({'seed': str(seed), 'stage': stage})[:16], 'seed': str(seed),
            'stratum': stratum, 'providers': providers, 'max_steps': 48,
            'probe_budget_microUSD': 24000000,
            'refusal_provider': providers[rng.randrange(len(providers))]['id'],
            'schedules': list(SCHEDULES), 'loss_per_excess_effect_microUSD': 50000000}


def public_task(spec):
    return {'schema': 'outlearning-public-task/v1', 'world_id': spec['world_id'], 'stage': spec['stage'],
            'providers': [{'id': p['id'], 'probe_unit_microUSD': p['probe_unit_microUSD'],
                           'call_microUSD': p['call_microUSD']} for p in spec['providers']],
            'probe_budget_microUSD': spec['probe_budget_microUSD'], 'max_steps': spec['max_steps'],
            'order_token': 'order',
            'schedules': list(SCHEDULES), 'outcome': 'exactly_once_single' if spec['stage'] == 'K1' else 'complete_complementary_bundle',
            'maximum_program_nodes': 256, 'ops': list(OPS), 'responses': list(RESPONSES)}


class Provider:
    def __init__(self, config):
        self.cfg = copy.deepcopy(config)
        self.effects = []
        self.holds = {}
        self.tick = 0
        self.fault_used = False
        self.fenced = False

    def _advance(self, ticks):
        self.tick += ticks
        ttl = self.cfg['hold_ttl']
        if ttl:
            self.holds = {k: t for k, t in self.holds.items() if self.tick-t < ttl}

    def call(self, op, token='order', *, fault='none', ticks=1, refuse=False):
        self._advance(ticks if op == 'wait' else 1)
        if op == 'wait':
            return 'DONE'
        if op in ('status', 'fence'):
            if op == 'fence':
                if not self.cfg['fence']:
                    return 'UNSUPPORTED'
                self.fenced = True
            elif self.cfg['status'] == 'opaque':
                return 'UNKNOWN'
            visible = [e for e in self.effects if e['token'] == token and
                       (op == 'fence' or self.cfg['status'] != 'stale' or self.tick-e['tick'] >= self.cfg['status_lag'])]
            if visible:
                return 'DONE'
            if token in self.holds:
                return 'RESERVED'
            return 'ABSENT'
        if op == 'reserve':
            if not self.cfg['prepare']:
                return 'UNSUPPORTED'
            if refuse:
                return 'REFUSED'
            if any(e['token'] == token for e in self.effects):
                return 'DONE'
            self.holds.setdefault(token, self.tick)
            return 'RESERVED'
        if op == 'cancel':
            self.holds.pop(token, None)
            selected = [e for e in self.effects if e['token'] == token]
            if selected and not self.cfg['compensation']:
                return 'REFUSED'
            self.effects = [e for e in self.effects if e['token'] != token]
            return 'CANCELLED'
        if op not in ('execute', 'commit'):
            raise ValueError('UNKNOWN_OPERATION')
        if fault == 'request_lost':
            return 'TIMEOUT'
        existing = [e for e in self.effects if e['token'] == token]
        if op == 'commit':
            if not self.cfg['prepare']:
                return 'UNSUPPORTED'
            if existing:
                return 'TIMEOUT' if fault == 'ack_lost' else 'DONE'
            if token not in self.holds:
                return 'REFUSED'
            self.holds.pop(token)
        else:
            if refuse:
                return 'REFUSED'
            mode = self.cfg['idempotency']
            epoch = self.tick // self.cfg['key_ttl']
            if existing and (mode == 'persistent' or (mode == 'epoch' and any(e['epoch'] == epoch for e in existing))):
                return 'TIMEOUT' if fault == 'ack_lost' else 'DONE'
        self.effects.append({'token': token, 'tick': self.tick, 'epoch': self.tick // self.cfg['key_ttl']})
        return 'TIMEOUT' if fault == 'ack_lost' else 'DONE'


class ProbeSession:
    def __init__(self, spec):
        self._spec = copy.deepcopy(spec)
        self._providers = {p['id']: p for p in spec['providers']}
        self.spent_microUSD = 0
        self.transcript = []

    def __call__(self, provider_id, sequence):
        if provider_id not in self._providers or not isinstance(sequence, list) or not 1 <= len(sequence) <= 16:
            raise ValueError('BOUNDED_PROBE_REQUIRED')
        p = self._providers[provider_id]
        cost = len(sequence) * p['probe_unit_microUSD']
        if self.spent_microUSD + cost > self._spec['probe_budget_microUSD']:
            entry = {'provider': provider_id, 'sequence': copy.deepcopy(sequence), 'cost_microUSD': 0, 'error': 'BUDGET_EXHAUSTED'}
            self.transcript.append(entry)
            return {'error': 'BUDGET_EXHAUSTED', 'remaining_microUSD': self._spec['probe_budget_microUSD']-self.spent_microUSD}
        engine = Provider(p['config'])
        observations = []
        for action in sequence:
            if not isinstance(action, dict) or action.get('op') not in OPS or action.get('fault', 'none') not in ('none', 'request_lost', 'ack_lost'):
                raise ValueError('VALID_PROBE_ACTION_REQUIRED')
            ticks = action.get('ticks', 1)
            if type(ticks) is not int or not 1 <= ticks <= 8:
                raise ValueError('BOUNDED_WAIT_REQUIRED')
            response = engine.call(action['op'], action.get('token', 'probe'), fault=action.get('fault', 'none'), ticks=ticks)
            noise = p['sandbox_noise'] and action['op'] in ('status', 'fence')
            observations.append({'op': action['op'], 'response': 'UNKNOWN' if noise else response,
                                 'effect_count': None if noise else len(engine.effects),
                                 'hold_count': None if noise else len(engine.holds), 'tick': engine.tick,
                                 'measurement': 'missing' if noise else 'sandbox_ledger'})
        self.spent_microUSD += cost
        result = {'observations': observations, 'cost_microUSD': cost,
                  'remaining_microUSD': self._spec['probe_budget_microUSD']-self.spent_microUSD}
        self.transcript.append({'provider': provider_id, 'sequence': copy.deepcopy(sequence), **copy.deepcopy(result)})
        return result


def development_evidence():
    sequences = {
        'ambiguous_ack': [{'op': 'execute', 'fault': 'ack_lost'}, {'op': 'status'}],
        'stable_retry': [{'op': 'execute', 'fault': 'ack_lost'}, {'op': 'execute'}, {'op': 'status'}],
        'delayed_retry': [{'op': 'execute', 'fault': 'ack_lost'}, {'op': 'wait', 'ticks': 8}, {'op': 'execute'}, {'op': 'fence'}],
        'prepared': [{'op': 'reserve'}, {'op': 'commit', 'fault': 'ack_lost'}, {'op': 'commit'}, {'op': 'cancel'}],
        'reconcile': [{'op': 'execute', 'fault': 'ack_lost'}, {'op': 'fence'}, {'op': 'cancel'}],
    }
    evidence = []
    for i in range(8):
        spec = make_world('development-only-' + str(i), 'K1', i)
        probe = ProbeSession(spec)
        provider = public_task(spec)['providers'][0]['id']
        records = {name: probe(provider, seq) for name, seq in sequences.items()}
        evidence.append({'task': public_task(spec), 'observations': records, 'probe_cost_microUSD': probe.spent_microUSD})
    return {'schema': 'outlearning-k1-development/v1', 'scope': 'EXPOSED_DEVELOPMENT_NOT_CONFIRMATION',
            'initial_explanations': ['H1 request lost before effect', 'H2 effect committed but acknowledgement lost'],
            'challenge': 'Some observations cannot be represented by H1/H2 alone; construct additional state and a deployable protocol.',
            'records': evidence}
