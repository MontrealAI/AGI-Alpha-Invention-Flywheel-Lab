"""Current-state allocation over the unchanged native simulated exchange.

The signed-off protocol supplies an allocation ceiling, never fresh funds. The
live account must use SingleWriterExchange; independent replay proves its current
financial state before a plan is produced and again before it is committed.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import tempfile
import threading

from commercial.ledger import amount, audit, digest
from commercial.single_writer import SingleWriterExchange

SOURCE_PATHS = ('enterprise/finance012.py', 'commercial/ledger.py',
                'commercial/persistence.py', 'commercial/tape_lease.py',
                'commercial/single_writer.py', 'experiments/commerce006.py', 'vendor/alpha_claim/contracts.py',
                'vendor/alpha_claim/protected_exchange.py')


def source_identity(root, paths=SOURCE_PATHS):
    root = Path(root)
    identities = {}
    for relative in paths:
        path = root / relative
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
            raise ValueError('ALLOCATION_SOURCE_SYMLINK_REFUSED')
        identities[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest(identities)


class _IncrementalNativeReplay:
    """Replay each action once in a separate unchanged native instance.

    A previously checked prefix cannot be replaced, shortened or reinterpreted.
    Every observation still compares the complete derived public financial state.
    The operating runner additionally performs a fresh whole-tape final audit.
    """
    def __init__(self, *, root, manifest, config):
        from commercial.ledger import TapeExchange
        self.directory = tempfile.TemporaryDirectory(prefix='growth012-allocation-replay-')
        self.replay = None
        try:
            kwargs = {'root': root, 'manifest': manifest, 'opening': config['opening'],
                      'working': config['working'], 'contract': config['contract'], 'durable': False}
            if config['schema'] == 'agi-alpha/commercial010-tape/v1':
                kind = TapeExchange
            elif config['schema'] == 'agi-alpha/growth012-finite-contract/v1':
                from enterprise.contract012 import FiniteTapeExchange
                kind = FiniteTapeExchange
                terms = config['terms']
                kwargs.update({key: terms[key] for key in ['liability_ticks', 'time_unit', 'arrangement_cost']})
            else:
                raise ValueError('QUALIFIED_NATIVE_REPLAY_SCHEMA_REQUIRED')
            self.replay = kind(Path(self.directory.name) / 'audit.sqlite', **kwargs)
            if self.replay.config != config:
                raise ValueError('EXACT_NATIVE_REPLAY_CONFIG_REQUIRED')
        except BaseException:
            self.close()
            raise

    def check(self, tape):
        if self.replay is None:
            raise ValueError('ALLOCATION_REPLAY_CLOSED')
        if tape.get('config') != self.replay.config:
            raise ValueError('ALLOCATION_REPLAY_CONFIG_CHANGED')
        actions = tape.get('actions')
        if not isinstance(actions, list) or digest(actions) != tape.get('actions_sha256'):
            raise ValueError('ACTION_TAPE_IDENTITY_MISMATCH')
        previous = len(self.replay.actions)
        if len(actions) < previous or digest(actions[:previous]) != digest(self.replay.actions):
            raise ValueError('PREVIOUSLY_AUDITED_PREFIX_CHANGED')
        for event in actions[previous:]:
            if event.get('seq') != len(self.replay.actions) or event.get('before') != self.replay.ex.snapshot():
                raise ValueError('EVENT_SEQUENCE_OR_OPENING_STATE_MISMATCH')
            after = self.replay.execute(event['op'], event['args'], event['day'])
            if after != event.get('after') or self.replay.actions[-1] != event:
                raise ValueError('EVENT_DERIVED_BALANCE_MISMATCH')
        rebuilt = self.replay.export()
        for key in ['config', 'summary', 'journal', 'orders', 'investments', 'investment_witnesses', 'invoices', 'receivables']:
            if rebuilt[key] != tape.get(key):
                raise ValueError('DERIVED_' + key.upper() + '_MISMATCH')
        return {'accepted': True, 'scope': 'SIMULATED', 'actions_sha256': tape['actions_sha256'],
                'summary': rebuilt['summary'], 'independent_replay_mode': 'Incremental native replay with immutable checked prefix and complete derived-state comparison.'}

    def close(self):
        if self.replay is not None:
            self.replay.close()
            self.replay = None
        self.directory.cleanup()


class AuditedAllocation:
    """Serial owner-local CAS plus native atomic earned-cash reservation.

    An action's return remains a policy forecast. This gate establishes only its
    source/current-state identity, declared allocation and eligible cash, not that
    projected demand or return will materialize. All values are microUSD.
    """
    def __init__(self, exchange, *, root, manifest, allocation_id, cap):
        if not isinstance(exchange, SingleWriterExchange):
            raise ValueError('SINGLE_WRITER_EXCHANGE_REQUIRED')
        amount(cap)
        if not isinstance(allocation_id, str) or not allocation_id or ':' in allocation_id:
            raise ValueError('UNIQUE_ALLOCATION_ID_REQUIRED')
        self.exchange, self.root, self.manifest = exchange, Path(root), manifest
        self.allocation_id, self.cap = allocation_id, cap
        self.source_paths = SOURCE_PATHS
        if exchange.__class__.__module__ == 'enterprise.contract012':
            from enterprise.contract012 import OwnedFiniteExchange
            if not isinstance(exchange, OwnedFiniteExchange):
                raise ValueError('QUALIFIED_FINITE_CONTRACT_EXCHANGE_REQUIRED')
            self.source_paths = SOURCE_PATHS + ('enterprise/contract012.py',)
        self.initial_source = source_identity(root, self.source_paths)
        self._mutex = threading.RLock()
        self._replay = _IncrementalNativeReplay(root=root, manifest=manifest,
                                               config=exchange.export()['config'])

    def observe(self):
        with self._mutex:
            if source_identity(self.root, self.source_paths) != self.initial_source:
                raise ValueError('ALLOCATION_SOURCE_CHANGED')
            tape = self.exchange.export()
            proof = self._replay.check(tape)
            committed = sum(int(row['cap']) for row in tape['investments']
                            if row['id'].startswith(self.allocation_id + ':')
                            and row['state'] != 'cancelled')
            return {'schema': 'agi-alpha/growth012-audited-observation/v1',
                    'allocation_id': self.allocation_id, 'source_sha256': self.initial_source,
                    'actions_sha256': proof['actions_sha256'], 'summary': proof['summary'],
                    'allocation_remaining': max(0, self.cap - committed),
                    'independent_native_replay': proof['accepted'],
                    'replay_mode': proof['independent_replay_mode'],
                    'scope': 'SIMULATED'}

    def plan(self, ident, cap, expected_net_value, *, intent, observation=None):
        amount(cap, positive=True)
        amount(expected_net_value, positive=True)
        if not isinstance(ident, str) or not ident or ':' in ident:
            raise ValueError('UNIQUE_ACTION_ID_REQUIRED')
        observed = self.observe() if observation is None else observation
        return {'schema': 'agi-alpha/growth012-allocation-plan/v1',
                'id': self.allocation_id + ':' + ident, 'cap': cap,
                'expected_net_value': expected_net_value,
                'intent_sha256': digest(intent), 'observation': observed}

    def reserve(self, plan, day):
        with self._mutex:
            if not isinstance(plan, dict) or set(plan) != {'schema', 'id', 'cap', 'expected_net_value', 'intent_sha256', 'observation'}:
                raise ValueError('EXACT_ALLOCATION_PLAN_REQUIRED')
            if plan['schema'] != 'agi-alpha/growth012-allocation-plan/v1' or not plan['id'].startswith(self.allocation_id + ':'):
                raise ValueError('ALLOCATION_IDENTITY_MISMATCH')
            current = self.observe()
            if current != plan['observation']:
                raise ValueError('STALE_ALLOCATION_PLAN')
            amount(plan['cap'], positive=True)
            amount(plan['expected_net_value'], positive=True)
            if plan['cap'] > min(current['allocation_remaining'], current['summary']['unrestrictedEarned'], current['summary']['available']):
                raise ValueError('CURRENT_ELIGIBLE_FUNDS_OR_ALLOCATION_EXCEEDED')
            return self.exchange.execute('reserve', {
                'id': plan['id'], 'amount': plan['cap'],
                'expected_net_value': plan['expected_net_value'],
                'intent_sha256': digest(plan)}, day)

    def finish(self, plan, actual, artifact_sha256, day):
        with self._mutex:
            if not isinstance(plan, dict) or not plan.get('id', '').startswith(self.allocation_id + ':'):
                raise ValueError('ALLOCATION_IDENTITY_MISMATCH')
            amount(actual)
            return self.exchange.execute('finish', {'id': plan['id'], 'amount': actual,
                                                     'artifact_sha256': artifact_sha256}, day)

    def cancel(self, plan, day):
        with self._mutex:
            if not isinstance(plan, dict) or not plan.get('id', '').startswith(self.allocation_id + ':'):
                raise ValueError('ALLOCATION_IDENTITY_MISMATCH')
            return self.exchange.execute('cancel_investment', {'id': plan['id']}, day)

    def close(self):
        replay = getattr(self, '_replay', None)
        if replay is not None:
            replay.close()
            self._replay = None

    def __del__(self):
        self.close()
