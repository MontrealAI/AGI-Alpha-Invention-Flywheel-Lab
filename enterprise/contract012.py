"""A separately negotiated finite-liability simulated payment contract.

This extends the historical native state machine with one finality transition.
It is never used for the unchanged-obligation controller comparison. Money,
costs, reservation eligibility and ordinary trade transitions still come from
the pinned native exchange. Finality is a scenario contract, not a claim about
an actual payment provider or applicable law.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import tempfile

from commercial.ledger import TapeExchange, SCOPE, UNIT, amount, canonical, digest, load_jobs, strict_json
from commercial.persistence import DurableTape, memory_engine
from commercial.single_writer import SingleWriterExchange, _acquire
from experiments.commerce006 import engine

SCHEMA = 'agi-alpha/growth012-finite-contract/v1'
FINAL_STATE = 'contract-final'
SOURCE_PATHS = (
    'enterprise/contract012.py', 'commercial/ledger.py',
    'commercial/persistence.py', 'commercial/single_writer.py',
    'commercial/tape_lease.py', 'experiments/commerce006.py',
    'vendor/alpha_claim/protected_exchange.py', 'vendor/alpha_claim/contracts.py',
)


def source_hashes(root):
    result = {}
    for name in SOURCE_PATHS:
        path = Path(root) / name
        if path.is_symlink() or any(p.is_symlink() for p in path.parents):
            raise ValueError('FINITE_CONTRACT_SOURCE_SYMLINK')
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _terms(liability_ticks, time_unit, arrangement_cost):
    if type(liability_ticks) is not int or not 1 <= liability_ticks <= 87600:
        raise ValueError('POSITIVE_BOUNDED_FINITE_LIABILITY_REQUIRED')
    if time_unit not in {'hours', 'days'}:
        raise ValueError('FINITE_CONTRACT_EXPLICIT_TIME_UNIT_REQUIRED')
    amount(arrangement_cost, positive=True)
    return {'liability_ticks': liability_ticks, 'time_unit': time_unit,
            'arrangement_cost': arrangement_cost,
            'finality': 'Full principal-plus-fee reserve until release time plus liability_ticks; no contractual debit or reversal after finality.',
            'scope': 'Authored conditional simulated contract; buyer utility and recurring fees are separately costed by the operating policy.'}


class FiniteTapeExchange(TapeExchange):
    def __init__(self, path, *, root, manifest, opening, working, contract,
                 liability_ticks, time_unit, arrangement_cost, durable=True):
        from commercial import ledger as native_ledger
        ownership = getattr(native_ledger, '_adaptive_ownership', None)
        self._adaptive_writer = ownership(path, manifest, None, None, None) if ownership else None
        self.root = Path(root)
        self.manifest = copy.deepcopy(manifest)
        self.jobs = load_jobs(root, manifest)
        amount(opening)
        amount(working)
        if not isinstance(contract, str) or not contract:
            raise ValueError('CONTRACT_REQUIRED')
        self.terms = _terms(liability_ticks, time_unit, arrangement_cost)
        self.config = {'schema': SCHEMA, 'scope': SCOPE, 'currency': UNIT,
                       'opening': opening, 'working': working, 'contract': contract,
                       'manifest_sha256': digest(manifest), 'terms': self.terms,
                       'source_hashes': source_hashes(root)}
        self.actions, self.last_day = [], -1
        self.persistence = DurableTape(path, self.config, canonical, strict_json) if durable else None
        self._restoring = True
        self.arrangement_id = 'finite-contract-arrangement:' + digest({'contract': contract, 'terms': self.terms})
        self.ex = memory_engine(engine(), key=b'C' * 32,
                                contract='finite012/' + digest({'contract': contract, 'terms': self.terms}),
                                validate=self.validate, check=self.check,
                                opening=opening, working=working)
        try:
            for expected in self.persistence.recovery_actions if self.persistence else []:
                if expected.get('seq') != len(self.actions) or expected.get('before') != self.ex.snapshot():
                    raise ValueError('DURABLE_RECOVERY_SEQUENCE_OR_STATE_MISMATCH')
                after = self.execute(expected['op'], expected['args'], expected['day'])
                if self.actions[-1] != expected or after != expected['after']:
                    raise ValueError('DURABLE_RECOVERY_ACTION_MISMATCH')
        except BaseException:
            self.ex.close()
            if self.persistence:
                self.persistence.close()
            raise
        finally:
            self._restoring = False

    def _arranged(self):
        row = self.ex.db.execute('SELECT order_id,raw FROM events WHERE id=?', (self.arrangement_id,)).fetchone()
        return row is not None and row['order_id'] == '' and json.loads(row['raw']) == {'cost': self.terms['arrangement_cost']}

    def _mature(self, ident, event_id, tick):
        if not isinstance(ident, str) or not ident or not isinstance(event_id, str) or not event_id:
            raise ValueError('FINITE_CONTRACT_EVENT_ID_REQUIRED')
        payload = {'contract_terms_sha256': digest(self.terms)}
        raw = canonical({'action': 'contract_mature', 'payload': payload, 'now': tick}).decode()
        self.ex.db.execute('BEGIN IMMEDIATE')
        try:
            prior = self.ex.db.execute('SELECT * FROM events WHERE id=?', (event_id,)).fetchone()
            if prior:
                if prior['raw'] != raw or prior['order_id'] != ident:
                    raise ValueError('FINITE_CONTRACT_EVENT_REBOUND')
                self.ex.db.execute('COMMIT')
                return
            row = self.ex.order(ident)
            if row['state'] != 'released' or row['custody'] or int(row['refund_due']) or int(row['compensation_due']):
                raise ValueError('FINITE_CONTRACT_RELEASED_UNDISPUTED_ORDER_REQUIRED')
            previous = [json.loads(r[0]) for r in self.ex.db.execute('SELECT raw FROM events WHERE order_id=?', (ident,))]
            releases = [r['now'] for r in previous if r.get('action') == 'release']
            if len(releases) != 1 or tick < releases[0] + self.terms['liability_ticks']:
                raise ValueError('FINITE_LIABILITY_NOT_MATURE')
            if any(r.get('now', -1) > tick for r in previous):
                raise ValueError('FINITE_CONTRACT_TIME_REGRESSION')
            self.ex.db.execute('UPDATE trades SET state=? WHERE id=?', (FINAL_STATE, ident))
            self.ex.db.execute('INSERT INTO events VALUES(?,?,?)', (event_id, ident, raw))
            self.ex.db.execute('COMMIT')
        except BaseException:
            self.ex.db.execute('ROLLBACK')
            raise

    def execute(self, op, args, day, *, record=True):
        if op not in {'mature', 'arrange'}:
            if op == 'offer' and not self._arranged():
                raise ValueError('COSTED_FINITE_CONTRACT_ARRANGEMENT_REQUIRED')
            return super().execute(op, args, day, record=record)
        if self.persistence and (self.persistence.failed or not record):
            raise ValueError('DURABLE_ACTION_RECORD_REQUIRED')
        if type(day) is not int or day < self.last_day or day < 0:
            raise ValueError('EVENT_TIME_REGRESSION')
        required = {'id', 'event_id'} if op == 'mature' else set()
        if not isinstance(args, dict) or set(args) != required:
            raise ValueError('EXACT_FINITE_CONTRACT_ACTION_REQUIRED')
        before = self.ex.snapshot()
        if op == 'arrange':
            self.ex.cost(self.arrangement_id, self.terms['arrangement_cost'])
        else:
            if not self._arranged():
                raise ValueError('COSTED_FINITE_CONTRACT_ARRANGEMENT_REQUIRED')
            self._mature(args['id'], args['event_id'], day)
        after = self.ex.snapshot()
        self.last_day = day
        self.assert_conservation()
        if record:
            event = {'seq': len(self.actions), 'day': day, 'op': op,
                     'args': copy.deepcopy(args), 'before': before, 'after': after}
            if self.persistence and not self._restoring:
                self.persistence.append(event)
            self.actions.append(event)
        return after

    def export(self):
        result = super().export()
        finals = {row['id'] for row in result['orders'] if row['state'] == FINAL_STATE}
        for invoice in result['invoices']:
            if invoice['order'] in finals:
                invoice['state'] = 'PAID'
        return result

    def download(self, ident, buyer):
        row = self.ex.order(ident)
        if row['buyer'] != buyer or row['state'] not in {'released', FINAL_STATE}:
            raise PermissionError('ASSURED_FINITE_CONTRACT_BUYER_RELEASE_REQUIRED')
        return self.ex._decrypt(row)


class OwnedFiniteExchange(SingleWriterExchange):
    def __init__(self, path, **kwargs):
        self.lease = _acquire(path)
        self._closed, self._exchange = False, None
        try:
            self._exchange = FiniteTapeExchange(path, **kwargs)
        except BaseException:
            self.close()
            raise

    def download(self, ident, buyer):
        self.lease.assert_owner()
        return self._exchange.download(ident, buyer)


def audit_contract012(tape, *, root, manifest, expected_actions_sha256=None):
    if not isinstance(tape, dict) or not isinstance(tape.get('config'), dict):
        raise ValueError('FINITE_CONTRACT_TAPE_REQUIRED')
    c = tape['config']
    fields = {'schema', 'scope', 'currency', 'opening', 'working', 'contract',
              'manifest_sha256', 'terms', 'source_hashes'}
    if set(c) != fields or c.get('schema') != SCHEMA or c.get('scope') != SCOPE or c.get('currency') != UNIT:
        raise ValueError('FINITE_CONTRACT_EXACT_CONFIG_REQUIRED')
    if c['manifest_sha256'] != digest(manifest) or c['source_hashes'] != source_hashes(root):
        raise ValueError('FINITE_CONTRACT_SOURCE_OR_COHORT_CHANGED')
    terms = c['terms']
    if not isinstance(terms, dict) or terms != _terms(terms.get('liability_ticks'), terms.get('time_unit'), terms.get('arrangement_cost')):
        raise ValueError('FINITE_CONTRACT_TERMS_CHANGED')
    if not isinstance(tape.get('actions'), list) or digest(tape['actions']) != tape.get('actions_sha256'):
        raise ValueError('ACTION_TAPE_IDENTITY_MISMATCH')
    if expected_actions_sha256 is not None and tape['actions_sha256'] != expected_actions_sha256:
        raise ValueError('EXTERNAL_ACTION_IDENTITY_MISMATCH')
    with tempfile.TemporaryDirectory(prefix='growth012-contract-audit-') as tmp:
        replay = FiniteTapeExchange(Path(tmp)/'replay.sqlite', root=root, manifest=manifest,
                                   opening=c['opening'], working=c['working'], contract=c['contract'],
                                   liability_ticks=terms['liability_ticks'], time_unit=terms['time_unit'],
                                   arrangement_cost=terms['arrangement_cost'], durable=False)
        try:
            for seq, event in enumerate(tape['actions']):
                if event.get('seq') != seq or event.get('before') != replay.ex.snapshot():
                    raise ValueError('EVENT_SEQUENCE_OR_OPENING_STATE_MISMATCH')
                after = replay.execute(event['op'], event['args'], event['day'])
                if after != event.get('after'):
                    raise ValueError('EVENT_DERIVED_BALANCE_MISMATCH')
            rebuilt = replay.export()
            for key in ['config', 'summary', 'journal', 'orders', 'investments', 'investment_witnesses', 'invoices', 'receivables']:
                if rebuilt[key] != tape.get(key):
                    raise ValueError('DERIVED_' + key.upper() + '_MISMATCH')
        finally:
            replay.close()
    return {'accepted': True, 'scope': SCOPE, 'actions_sha256': tape['actions_sha256'],
            'summary': rebuilt['summary'], 'orders': rebuilt['orders'],
            'investments': rebuilt['investments'], 'terms': terms,
            'source_hashes': c['source_hashes'],
            'claim': 'Independent replay of a separate conditional finite-liability contract. Native original perpetual-tail contract is unchanged.'}


audit = audit_contract012
