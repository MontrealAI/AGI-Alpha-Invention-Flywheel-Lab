"""Auditable action tape over the pinned native protected simulated exchange.

This adapter does not define an alternative earned balance. Monetary state and
investment admission come from the existing ProtectedExchange implementation.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from experiments.commerce006 import engine

SCOPE = 'SIMULATED'
UNIT = 'simulated-microUSD'
MAX_AMOUNT = 10**12
_AUDITED_CONTENT = set()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('DUPLICATE_JSON_FIELD')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def amount(value, *, positive=False):
    if type(value) is not int or not (1 if positive else 0) <= value <= MAX_AMOUNT:
        raise ValueError('BOUNDED_INTEGER_MONETARY_AMOUNT_REQUIRED')
    return value


def read_bound(root, path, expected):
    if not isinstance(path, str) or not isinstance(expected, str) or len(expected) != 64:
        raise ValueError('SOURCE_IDENTITY_REQUIRED')
    relative = Path(path)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('RELATIVE_SOURCE_REQUIRED')
    candidate = Path(root) / relative
    if candidate.is_symlink() or any(x.is_symlink() for x in candidate.parents):
        raise ValueError('SYMLINK_REFUSED')
    raw = candidate.read_bytes()
    if len(raw) > 2_000_000 or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('SOURCE_OR_ARTIFACT_CHANGED')
    return strict_json(raw)


def load_jobs(root, manifest):
    if not isinstance(manifest, dict) or not isinstance(manifest.get('jobs'), list):
        raise ValueError('SERVICE_COHORT_REQUIRED')
    from verification.commercial010_audit import audit_service, _bound
    # Cache only independent semantic checking. Every source/input/output/receipt
    # byte identity is re-read and verified before a cached result can be used.
    # The manifest and frozen checker identities are part of the cache key.
    protocol = read_bound(root, manifest['source_freeze'], manifest['source_freeze_sha256'])
    for path, expected in protocol['source_hashes'].items():
        _bound(root, path, expected)
    for record in manifest['jobs']:
        for field in ['input', 'artifact', 'receipt']:
            _bound(root, record[field], record[field + '_sha256'])
    for record in manifest['attempts']:
        _bound(root, record['artifact'], record['artifact_sha256'])
    identity = (str(Path(root).absolute()), digest(manifest), digest(protocol))
    if identity not in _AUDITED_CONTENT:
        audit_service(root, manifest)
        _AUDITED_CONTENT.add(identity)
    jobs = {}
    for job in manifest['jobs']:
        if not isinstance(job, dict) or not isinstance(job.get('id'), str) or job['id'] in jobs:
            raise ValueError('UNIQUE_JOB_ID_REQUIRED')
        if type(job.get('accepted')) is not bool:
            raise ValueError('EXPLICIT_ACCEPTANCE_REQUIRED')
        if job['accepted']:
            artifact = read_bound(root, job['artifact'], job['artifact_sha256'])
            receipt = read_bound(root, job['receipt'], job['receipt_sha256'])
            if receipt.get('accepted') is not True or receipt.get('artifact_sha256') != job['artifact_sha256']:
                raise ValueError('SCOPED_ACCEPTANCE_BINDING_REQUIRED')
            jobs[job['id']] = {'job': job, 'artifact': artifact, 'receipt': receipt}
    if not jobs:
        raise ValueError('NO_ACCEPTED_SERVICE_ARTIFACTS')
    return jobs


class TapeExchange:
    def __init__(self, path, *, root, manifest, opening, working, contract, durable=True):
        self.root = Path(root)
        self.manifest = copy.deepcopy(manifest)
        self.jobs = load_jobs(root, manifest)
        amount(opening)
        amount(working)
        if not isinstance(contract, str) or not contract:
            raise ValueError('CONTRACT_REQUIRED')
        self.config = {'schema': 'agi-alpha/commercial010-tape/v1', 'scope': SCOPE,
                       'currency': UNIT, 'opening': opening, 'working': working,
                       'contract': contract, 'manifest_sha256': digest(manifest)}
        self.actions = []
        self.last_day = -1
        from commercial.persistence import DurableTape, memory_engine
        self.persistence = DurableTape(path, self.config, canonical, strict_json) if durable else None
        self._restoring = True
        self.ex = memory_engine(engine(), key=b'C' * 32, contract=contract,
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

    def validate(self, task):
        if not isinstance(task, dict) or set(task) != {'scope', 'job_id', 'artifact_sha256', 'receipt_sha256'}:
            raise ValueError('TASK_SCHEMA')
        if task['scope'] != SCOPE or task['job_id'] not in self.jobs:
            raise ValueError('INVALID_SCOPE_TRANSITION_OR_UNQUALIFIED_JOB')
        job = self.jobs[task['job_id']]['job']
        if task['artifact_sha256'] != job['artifact_sha256'] or task['receipt_sha256'] != job['receipt_sha256']:
            raise ValueError('TASK_AUTHORITY_CHANGED')

    def task(self, job_id):
        job = self.jobs[job_id]['job']
        return {'scope': SCOPE, 'job_id': job_id, 'artifact_sha256': job['artifact_sha256'],
                'receipt_sha256': job['receipt_sha256']}

    def check(self, task, artifact):
        self.validate(task)
        from commercial.service_verifier import audit_delivery
        job = self.jobs[task['job_id']]['job']
        order = read_bound(self.root, job['input'], job['input_sha256'])
        current = read_bound(self.root, job['artifact'], job['artifact_sha256'])
        receipt = read_bound(self.root, job['receipt'], job['receipt_sha256'])
        if hashlib.sha256((self.root / 'commercial/service_verifier.py').read_bytes()).hexdigest() != receipt.get('checker_source_sha256'):
            raise ValueError('CHECKER_SOURCE_CHANGED')
        fresh = audit_delivery(order, artifact)
        accepted = fresh['accepted'] is True and canonical(artifact) == canonical(current) and all(receipt.get(k) == v for k, v in fresh.items())
        return {'accepted': accepted, 'decisive': True, 'scope': SCOPE, 'authority': job['receipt_sha256']}

    def execute(self, op, args, day, *, record=True):
        if self.persistence and (self.persistence.failed or not record):
            raise ValueError('DURABLE_ACTION_RECORD_REQUIRED')
        if type(day) is not int or day < self.last_day or day < 0:
            raise ValueError('EVENT_TIME_REGRESSION')
        schemas = {'cost': {'id', 'amount'}, 'wallet': {'buyer', 'amount'},
                   'offer': {'id', 'buyer', 'price', 'job_id', 'deadline'},
                   'event': {'id', 'action', 'event_id'},
                   'reserve': {'id', 'amount', 'expected_net_value', 'intent_sha256'},
                   'finish': {'id', 'amount', 'artifact_sha256'}, 'cancel_investment': {'id'}}
        if op not in schemas or not isinstance(args, dict):
            raise ValueError('ACTION_ARGUMENTS_REQUIRED')
        optional = {'source_tx', 'crash'} if op == 'event' else set()
        if not schemas[op] <= set(args) or set(args) - schemas[op] - optional:
            raise ValueError('EXACT_ACTION_ARGUMENT_SCHEMA_REQUIRED')
        if 'crash' in args and type(args['crash']) is not bool:
            raise ValueError('EXPLICIT_CRASH_BOOLEAN_REQUIRED')
        before = self.ex.snapshot()
        a = copy.deepcopy(args)
        if op == 'cost':
            amount(a['amount'])
            self.ex.cost(a['id'], a['amount'])
        elif op == 'wallet':
            amount(a['amount'])
            self.ex.wallet(a['buyer'], a['amount'])
        elif op == 'offer':
            amount(a['price'], positive=True)
            self.ex.offer(a['id'], a['buyer'], a['price'], 'nonrecourse-simulated',
                          self.task(a['job_id']), a['deadline'])
        elif op == 'event':
            ident, action = a['id'], a['action']
            row = self.ex.order(ident)
            if action == 'consent':
                terms = {k: row[k] for k in ['id', 'buyer', 'price', 'rail', 'task_hash', 'contract', 'deadline']}
                from vendor.alpha_claim.contracts import digest as native_digest
                payload = {'buyer': row['buyer'], 'termsHash': native_digest(terms)}
            elif action in {'fund', 'release'}:
                payload = self.ex.provider.issue(row, 'funded' if action == 'fund' else 'cleared', a.get('source_tx'))
            elif action == 'prepare':
                task = json.loads(row['task'])
                payload = self.jobs[task['job_id']]['artifact']
            elif action in {'refund', 'cancel', 'late_reversal'}:
                payload = {}
            else:
                raise ValueError('UNSUPPORTED_TAPE_TRANSITION')
            self.ex.event(ident, a['event_id'], action, payload, day, crash=a.get('crash', False))
        elif op == 'reserve':
            amount(a['amount'], positive=True)
            amount(a['expected_net_value'], positive=True)
            self.ex.reserve_investment(a['id'], a['amount'], a['expected_net_value'], intent_hash=a['intent_sha256'])
        elif op == 'finish':
            amount(a['amount'])
            self.ex.finish_investment(a['id'], a['amount'], a['artifact_sha256'])
        elif op == 'cancel_investment':
            self.ex.cancel_investment(a['id'])
        else:
            raise ValueError('UNKNOWN_NATIVE_OPERATION')
        after = self.ex.snapshot()
        self.last_day = day
        self.assert_conservation()
        if record:
            event = {'seq': len(self.actions), 'day': day, 'op': op, 'args': a, 'before': before, 'after': after}
            if self.persistence and not self._restoring:
                self.persistence.append(event)
            self.actions.append(event)
        return after

    def assert_conservation(self):
        s = self.ex.snapshot()
        if s['cash'] != self.ex.opening + s['collections'] + s['recoveryIncome'] - s['expensePaid']:
            raise ValueError('CASH_CONSERVATION_FAILURE')
        if s['profit'] != s['revenue'] + s['recoveryIncome'] - s['expenses']:
            raise ValueError('PROFIT_CONSERVATION_FAILURE')
        if s['unrestrictedEarned'] < 0 or s['unrestrictedEarned'] > s['available']:
            raise ValueError('EARNED_OR_RESTRICTED_BALANCE_FAILURE')
        if s['cash'] < 0 or s['payables'] < 0:
            raise ValueError('NEGATIVE_BALANCE_FAILURE')

    def export(self):
        journal = [dict(x) for x in self.ex.db.execute('SELECT seq,order_id,kind,amount FROM journal ORDER BY seq')]
        states = [{k: dict(x)[k] for k in ('id', 'buyer', 'price', 'state', 'refund_due', 'compensation_due', 'custody')}
                  for x in self.ex.db.execute('SELECT * FROM trades ORDER BY id')]
        investments = [dict(x) for x in self.ex.db.execute('SELECT * FROM investments ORDER BY id')]
        witnesses = [dict(x) for x in self.ex.db.execute('SELECT * FROM investment_events ORDER BY seq')]
        invoices = []
        for row in self.ex.db.execute('SELECT id,price,state,artifact_hash FROM trades ORDER BY id'):
            if row['artifact_hash'] is not None:
                invoices.append({'id': 'SIM-INVOICE-' + row['id'], 'order': row['id'], 'amount': int(row['price']),
                                 'scope': SCOPE, 'basis': 'Derived from independently accepted native prepare; revenue recognized only on assured native release',
                                 'state': 'PAID' if row['state'] == 'released' else 'VOID_OR_DISPUTED' if row['state'] in {'refunded', 'breached', 'custody-lost'} else 'ISSUED',
                                 'receivable': int(row['price']) if row['state'] == 'verified' else 0})
        receivables = sum(x['receivable'] for x in invoices)
        return {'config': self.config, 'actions': self.actions, 'actions_sha256': digest(self.actions),
                'journal': journal, 'orders': states, 'investments': investments, 'investment_witnesses': witnesses,
                'invoices': invoices, 'receivables': receivables, 'summary': self.ex.snapshot()}

    def close(self):
        try:
            if self.persistence and not self.persistence.failed:
                self.persistence.checkpoint(self.ex.db, self.actions)
        finally:
            self.ex.close()
            if self.persistence:
                self.persistence.close()


def audit(tape, *, root, manifest, expected_actions_sha256=None):
    if not isinstance(tape, dict) or tape.get('config', {}).get('scope') != SCOPE or tape['config'].get('currency') != UNIT:
        raise ValueError('SIMULATED_SCOPE_AND_UNIT_REQUIRED')
    if tape['config'].get('manifest_sha256') != digest(manifest):
        raise ValueError('SOURCE_COHORT_MISMATCH')
    if digest(tape['actions']) != tape.get('actions_sha256'):
        raise ValueError('ACTION_TAPE_IDENTITY_MISMATCH')
    if expected_actions_sha256 is not None and tape['actions_sha256'] != expected_actions_sha256:
        raise ValueError('EXTERNAL_ACTION_IDENTITY_MISMATCH')
    c = tape['config']
    if set(c) != {'schema', 'scope', 'currency', 'opening', 'working', 'contract', 'manifest_sha256'} or c['schema'] != 'agi-alpha/commercial010-tape/v1':
        raise ValueError('EXACT_TAPE_CONFIG_REQUIRED')
    with tempfile.TemporaryDirectory(prefix='commercial010-audit-') as tmp:
        replay = TapeExchange(Path(tmp) / 'replay.sqlite', root=root, manifest=manifest,
                              opening=c['opening'], working=c['working'], contract=c['contract'], durable=False)
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
            'summary': rebuilt['summary'], 'orders': rebuilt['orders'], 'investments': rebuilt['investments']}
