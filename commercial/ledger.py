"""Auditable action tape over the pinned native protected simulated exchange.

This adapter does not define an alternative earned balance. Monetary state and
investment admission come from the existing ProtectedExchange implementation.
"""
from __future__ import annotations
import copy
from contextlib import contextmanager
import hashlib
import json
import os
import shutil
from pathlib import Path
import stat
import tempfile
from commercial.native_engine import engine

SCOPE = 'SIMULATED'
UNIT = 'simulated-microUSD'
_AUDITED_CONTENT = set()
_ADAPTIVE_ACCOUNT_CAPABILITY = object()
_NO_EXPECTED_BEFORE = object()


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
    if type(value) is not int or value < (1 if positive else 0):
        raise ValueError('EXACT_INTEGER_MONETARY_AMOUNT_REQUIRED')
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
    if isinstance(manifest, dict) and manifest.get('schema') == 'industrial064/native-services/v1':
        from industrial064.service import load_contracts
        return load_contracts(root, manifest)
    if isinstance(manifest, dict) and manifest.get('schema') == 'flexibility063/native-services/v1':
        from flexibility063.service import load_contracts
        return load_contracts(root, manifest)
    if isinstance(manifest, dict) and manifest.get('schema') == 'inventory061/native-services/v1':
        from inventory061.service import load_contracts
        return load_contracts(root, manifest)
    if isinstance(manifest, dict) and manifest.get('schema') == 'production060/native-services/v1':
        from production060.service import load_contracts
        return load_contracts(root, manifest)
    if isinstance(manifest, dict) and manifest.get('schema') == 'agi-alpha/adaptive012-services/v1':
        from adaptive_enterprise.instruments import load_jobs as adaptive_jobs
        return adaptive_jobs(root, manifest)
    if isinstance(manifest, dict) and manifest.get('schema') == 'agi-alpha/enterprise011-services/v1':
        from enterprise.services import load_jobs as enterprise_jobs
        return enterprise_jobs(root, manifest)
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


def _adaptive_ownership(path, manifest, namespace, lease, capability):
    path = Path(path).absolute()
    marker = path.with_name(path.name + '.adaptive-account.json')
    adaptive = namespace == 'adaptive012' or isinstance(manifest, dict) and (manifest.get('schema') == 'agi-alpha/adaptive012-services/v1' or manifest.get('account_namespace') == 'adaptive012') or marker.exists() or marker.is_symlink()
    for candidate in [path, path.with_name(path.name + '.actions.jsonl')]:
        if candidate.exists() or candidate.is_symlink():
            info = candidate.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('SINGLE_REGULAR_ACCOUNT_FILE_REQUIRED')
    if not adaptive:
        return None
    if capability is not _ADAPTIVE_ACCOUNT_CAPABILITY:
        raise ValueError('ADAPTIVE_ACCOUNT_REQUIRES_MANDATORY_WRITER_ACCOUNT_FACADE')
    from commercial.tape_lease import WriterLease
    if not isinstance(lease, WriterLease) or lease.path != path.with_name(path.name + '.writer.lock'):
        raise ValueError('ADAPTIVE_ACCOUNT_REQUIRES_MANDATORY_WRITER_OWNERSHIP')
    lease.assert_owner()
    from adaptive_enterprise.account import assert_local_storage
    assert_local_storage(path)
    expected = {'schema': 'agi-alpha/adaptive012-account-namespace/v1', 'namespace': 'adaptive012', 'account_path': str(path)}
    if marker.exists() or marker.is_symlink():
        info = marker.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or strict_json(marker.read_bytes()) != expected:
            raise ValueError('ADAPTIVE_ACCOUNT_NAMESPACE_CHANGED')
    else:
        from commercial.persistence import atomic_bytes
        atomic_bytes(marker, canonical(expected) + b'\n')
    return lease


class TapeExchange:
    def __init__(self, path, *, root, manifest, opening, working, contract, durable=True, _writer_lease=None, _account_namespace=None, _account_capability=None):
        self._adaptive_writer = _adaptive_ownership(path, manifest, _account_namespace, _writer_lease, _account_capability)
        self.root = Path(root)
        self.manifest = copy.deepcopy(manifest)
        self.native_engine = self.manifest.get('native_engine', 'legacy-permanent-v1')
        if self.native_engine not in {'legacy-permanent-v1', 'prospective-v1','exact-permanent-v2','exact-prospective-v2'}:
            raise ValueError('EXPLICIT_SUPPORTED_NATIVE_ENGINE_REQUIRED')
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
        self.ex = memory_engine(engine(version=self.native_engine), key=b'C' * 32, contract=contract,
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
        if self.manifest.get('schema') == 'industrial064/native-services/v1':
            from industrial064.service import check_delivery
            return check_delivery(self.root, self.manifest, task['job_id'], artifact)
        if self.manifest.get('schema') == 'flexibility063/native-services/v1':
            from flexibility063.service import check_delivery
            return check_delivery(self.root, self.manifest, task['job_id'], artifact)
        if self.manifest.get('schema') == 'inventory061/native-services/v1':
            from inventory061.service import check_delivery
            return check_delivery(self.root, self.manifest, task['job_id'], artifact)
        if self.manifest.get('schema') == 'production060/native-services/v1':
            from production060.service import check_delivery
            return check_delivery(self.root, self.manifest, task['job_id'], artifact)
        if self.manifest.get('schema') == 'agi-alpha/adaptive012-services/v1':
            from adaptive_enterprise.instruments import check_job
            checked = check_job(self.root, self.manifest, self.jobs[task['job_id']]['job'], artifact)
            return {'accepted': checked['receipt']['accepted'], 'decisive': True, 'scope': SCOPE,
                    'authority': checked['job']['receipt_sha256']}
        if self.manifest.get('schema') == 'agi-alpha/enterprise011-services/v1':
            from enterprise.services import check_job
            checked = check_job(self.root, self.manifest, self.jobs[task['job_id']]['job'], artifact)
            return {'accepted': checked['receipt']['accepted'], 'decisive': True, 'scope': SCOPE,
                    'authority': checked['job']['receipt_sha256']}
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

    def execute(self, op, args, day, *, record=True, _expected_before=_NO_EXPECTED_BEFORE):
        if self._adaptive_writer is not None:
            self._adaptive_writer.assert_owner()
        if self.persistence and (self.persistence.failed or not record):
            raise ValueError('DURABLE_ACTION_RECORD_REQUIRED')
        # Audit opening-state validation still precedes action validation/effects.
        # The exchange is a private in-memory SQLite connection; no callback or
        # native write occurs between this read and the operation below.
        before = None
        if _expected_before is not _NO_EXPECTED_BEFORE:
            before = self.ex.snapshot()
            if before != _expected_before:
                raise ValueError('EVENT_SEQUENCE_OR_OPENING_STATE_MISMATCH')
        if type(day) is not int or day < self.last_day or day < 0:
            raise ValueError('EVENT_TIME_REGRESSION')
        schemas = {'cost': {'id', 'amount'}, 'wallet': {'buyer', 'amount'},
                   'offer': {'id', 'buyer', 'price', 'job_id', 'deadline'},
                   'event': {'id', 'action', 'event_id'},
                   'reserve': {'id', 'amount', 'expected_net_value', 'intent_sha256'},
                   'finish': {'id', 'amount', 'artifact_sha256'}, 'cancel_investment': {'id'}}
        schemas.update(register_terms={'id', 'terms'}, claim={'id', 'claim_id', 'amount', 'kind'},
                       resolve_claim={'id', 'claim_id', 'settlement_id', 'resolution'}, mature={'id', 'event_id'},
                       recover_claim={'id', 'claim_id', 'settlement_id', 'amount', 'source_tx'})
        if op not in schemas or not isinstance(args, dict):
            raise ValueError('ACTION_ARGUMENTS_REQUIRED')
        optional = {'source_tx', 'crash'} if op == 'event' else {'terms_id'} if op == 'offer' else set()
        dynamic_prepare = (op == 'event' and args.get('action') == 'prepare'
                           and self.manifest.get('schema') in {'production060/native-services/v1', 'inventory061/native-services/v1', 'flexibility063/native-services/v1', 'industrial064/native-services/v1'})
        if dynamic_prepare:
            optional = optional | {'artifact_sha256'}
            if not isinstance(args.get('artifact_sha256'), str) or len(args['artifact_sha256']) != 64:
                raise ValueError('PRODUCTION060_ACTUAL_DELIVERY_HASH_REQUIRED')
        if not schemas[op] <= set(args) or set(args) - schemas[op] - optional:
            raise ValueError('EXACT_ACTION_ARGUMENT_SCHEMA_REQUIRED')
        if 'crash' in args and type(args['crash']) is not bool:
            raise ValueError('EXPLICIT_CRASH_BOOLEAN_REQUIRED')
        if op in {'register_terms', 'claim', 'resolve_claim', 'mature', 'recover_claim'} and self.native_engine not in {'prospective-v1','exact-prospective-v2'}:
            raise ValueError('PROSPECTIVE_NATIVE_ENGINE_OPT_IN_REQUIRED')
        if _expected_before is _NO_EXPECTED_BEFORE:
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
            extra = {'terms_id': a['terms_id'], 'now': day} if 'terms_id' in a else {}
            self.ex.offer(a['id'], a['buyer'], a['price'], 'nonrecourse-simulated',
                          self.task(a['job_id']), a['deadline'], **extra)
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
                if self.manifest.get('schema') in {'production060/native-services/v1', 'inventory061/native-services/v1', 'flexibility063/native-services/v1', 'industrial064/native-services/v1'}:
                    if self.manifest.get('schema') == 'industrial064/native-services/v1':
                        from industrial064.service import delivery
                    elif self.manifest.get('schema') == 'flexibility063/native-services/v1':
                        from flexibility063.service import delivery
                    elif self.manifest.get('schema') == 'inventory061/native-services/v1':
                        from inventory061.service import delivery
                    else:
                        from production060.service import delivery
                    payload = delivery(self.root, self.manifest, task['job_id'])
                    if digest(payload) != a['artifact_sha256']:
                        raise ValueError('PRODUCTION060_ACTUAL_DELIVERY_HASH_CHANGED')
                else:
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
        elif op == 'register_terms':
            self.ex.register_terms(a['id'], a['terms'], day)
        elif op in {'claim', 'resolve_claim', 'mature', 'recover_claim'}:
            for key in ['id', 'claim_id', 'settlement_id', 'event_id']:
                if key in a and (not isinstance(a[key], str) or not a[key].strip() or len(a[key]) > 160):
                    raise ValueError('BOUNDED_NATIVE_PROSPECTIVE_IDENTIFIER_REQUIRED')
            self.ex.prospective_event(op, a, day)
        else:
            raise ValueError('UNKNOWN_NATIVE_OPERATION')
        after = self.ex.snapshot()
        self.last_day = day
        # Only last_day changed since this fresh post-operation snapshot.
        self._assert_conservation_snapshot(after)
        if record:
            event = {'seq': len(self.actions), 'day': day, 'op': op, 'args': a, 'before': before, 'after': after}
            if self.persistence and not self._restoring:
                self.persistence.append(event)
            self.actions.append(event)
        return after

    def assert_conservation(self):
        self._assert_conservation_snapshot(self.ex.snapshot())

    def _assert_conservation_snapshot(self, s):
        if s['cash'] != self.ex.opening + s['collections'] + s['recoveryIncome'] - s['expensePaid']:
            raise ValueError('CASH_CONSERVATION_FAILURE')
        if s['profit'] != s['revenue'] + s['recoveryIncome'] - s['expenses']:
            raise ValueError('PROFIT_CONSERVATION_FAILURE')
        if s['unrestrictedEarned'] < 0 or s['unrestrictedEarned'] > s['available']:
            raise ValueError('EARNED_OR_RESTRICTED_BALANCE_FAILURE')
        if s['cash'] < 0 or s['payables'] < 0:
            raise ValueError('NEGATIVE_BALANCE_FAILURE')

    def export(self):
        if self._adaptive_writer is not None:
            self._adaptive_writer.assert_owner()
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
        exported = {'config': self.config, 'actions': self.actions, 'actions_sha256': digest(self.actions),
                'journal': journal, 'orders': states, 'investments': investments, 'investment_witnesses': witnesses,
                'invoices': invoices, 'receivables': receivables, 'summary': self.ex.snapshot()}
        if self.native_engine in {'prospective-v1','exact-prospective-v2'}:
            prospective = {
                'prospective_terms': [dict(x) for x in self.ex.db.execute('SELECT * FROM prospective_terms ORDER BY id')],
                'prospective_orders': [dict(x) for x in self.ex.db.execute('SELECT * FROM prospective_orders ORDER BY order_id')],
                'prospective_claims': [dict(x) for x in self.ex.db.execute('SELECT * FROM prospective_claims ORDER BY id')]}
            if any(prospective.values()):
                exported.update(prospective)
        return exported

    def close(self):
        try:
            if self.persistence and not self.persistence.failed:
                self.persistence.checkpoint(self.ex.db, self.actions)
        finally:
            self.ex.close()
            if self.persistence:
                self.persistence.close()


def audit(tape, *, root, manifest, expected_actions_sha256=None):
    checked, _ = _audit_native_and_jobs(tape, root=root, manifest=manifest,
                                       expected_actions_sha256=expected_actions_sha256)
    return checked


class _NativePrefixReplay:
    """Ephemeral private verifier state; never a portable/public audit receipt.

    Only native replay is incremental. All exported derived fields, service
    bindings, reservation proofs and connected journal checks still run fresh.
    The owner guard rebinds source/account/key/writer identity before AND after.
    """
    def __init__(self, owner_guard):
        self.owner_guard = owner_guard
        self._pid = os.getpid()
        self._tmp = self._owned = self._replay = None
        self._identity = self._config = self._prefix = None
        self._length = 0

    def close(self):
        try:
            if self._owned is not None:
                self._owned.close()
            elif self._replay is not None:
                self._replay.close()
        finally:
            self._owned = self._replay = None
            if self._tmp is not None and os.getpid() == self._pid:
                shutil.rmtree(self._tmp)
            self._tmp = None
            self._identity = self._config = self._prefix = None
            self._length = 0

    def begin(self, tape, *, root, manifest):
        identity = canonical([self.owner_guard(), str(Path(root).absolute()), manifest])
        config = canonical(tape['config'])
        # Compare actual complete prefix bytes, not mtimes, size, supplied head,
        # or an externally supplied digest. Rewind/change falls back to replay.
        reusable = (self._replay is not None and identity == self._identity
                    and config == self._config and len(tape['actions']) >= self._length
                    and canonical(tape['actions'][:self._length]) == self._prefix)
        if not reusable:
            self.close()
            self._pid = os.getpid()
            self._tmp = Path(tempfile.mkdtemp(prefix='native-prefix037-'))
            from commercial.single_writer import SingleWriterExchange
            c = tape['config']
            self._owned = SingleWriterExchange(self._tmp/'replay.sqlite', root=root, manifest=manifest,
                opening=c['opening'], working=c['working'], contract=c['contract'], durable=False,
                _account_capability=_ADAPTIVE_ACCOUNT_CAPABILITY)
            self._replay = self._owned._exchange
            self._identity, self._config = identity, config
        else:
            self._owned.lease.assert_owner()
            # Reuse deterministic adaptive service acceptance only after every
            # source/input/artifact/receipt byte is rebound to the same manifest.
            # Other schemas keep their full historical qualification.
            if manifest.get('schema') == 'agi-alpha/adaptive012-services/v1':
                from adaptive_enterprise.instruments import _validate_manifest, _read
                _validate_manifest(root, manifest)
                for job in manifest['jobs']:
                    current = {field: _read(root, job[field], job[field + '_sha256'])
                               for field in ['input', 'artifact', 'receipt']}
                    if job['accepted'] and self._replay.jobs.get(job['id']) != {
                            'job': job, 'artifact': current['artifact'], 'receipt': current['receipt']}:
                        raise ValueError('AUDITED_JOB_AUTHORITY_CHANGED')
                _validate_manifest(root, manifest)
            else:
                current_jobs = load_jobs(root, manifest)
                if current_jobs != self._replay.jobs:
                    raise ValueError('AUDITED_JOB_AUTHORITY_CHANGED')
                if manifest.get('schema') in {'production060/native-services/v1', 'inventory061/native-services/v1', 'flexibility063/native-services/v1', 'industrial064/native-services/v1'}:
                    if manifest.get('schema') == 'industrial064/native-services/v1':
                        from industrial064.service import rebind_prepared
                    elif manifest.get('schema') == 'flexibility063/native-services/v1':
                        from flexibility063.service import rebind_prepared
                    elif manifest.get('schema') == 'inventory061/native-services/v1':
                        from inventory061.service import rebind_prepared
                    else:
                        from production060.service import rebind_prepared
                    rebind_prepared(root, manifest, tape['actions'][:self._length], current_jobs)
        return self._replay, self._length

    def accept(self, tape, *, root, manifest):
        if canonical([self.owner_guard(), str(Path(root).absolute()), manifest]) != self._identity:
            raise ValueError('PREFIX_OWNER_OR_SOURCE_CHANGED')
        self._prefix = canonical(tape['actions'])
        self._length = len(tape['actions'])


@contextmanager
def _native_replay_context(tape, *, root, manifest, session):
    if session is not None:
        yield session.begin(tape, root=root, manifest=manifest)
        return
    c = tape['config']
    with tempfile.TemporaryDirectory(prefix='commercial010-audit-') as tmp:
        owned = None
        if manifest.get('schema') == 'agi-alpha/adaptive012-services/v1' or manifest.get('account_namespace') == 'adaptive012':
            from commercial.single_writer import SingleWriterExchange
            owned = SingleWriterExchange(Path(tmp)/'replay.sqlite', root=root, manifest=manifest,
                opening=c['opening'], working=c['working'], contract=c['contract'], durable=False,
                _account_capability=_ADAPTIVE_ACCOUNT_CAPABILITY)
            replay = owned._exchange
        else:
            replay = TapeExchange(Path(tmp)/'replay.sqlite', root=root, manifest=manifest,
                opening=c['opening'], working=c['working'], contract=c['contract'], durable=False)
        try:
            yield replay, 0
        finally:
            owned.close() if owned is not None else replay.close()


def _audit_native_and_jobs(tape, *, root, manifest, expected_actions_sha256=None, _session=None):
    try:
        return _audit_native_impl(tape, root=root, manifest=manifest,
            expected_actions_sha256=expected_actions_sha256, _session=_session)
    except BaseException:
        if _session is not None:
            _session.close()
        raise


def _audit_native_impl(tape, *, root, manifest, expected_actions_sha256=None, _session=None):
    """One complete native replay and call-local, freshly rebound job authority."""
    if not isinstance(tape, dict) or tape.get('config', {}).get('scope') != SCOPE or tape['config'].get('currency') != UNIT:
        raise ValueError('SIMULATED_SCOPE_AND_UNIT_REQUIRED')
    if tape['config'].get('manifest_sha256') != digest(manifest):
        raise ValueError('SOURCE_COHORT_MISMATCH')
    if digest(tape['actions']) != tape.get('actions_sha256'):
        raise ValueError('ACTION_TAPE_IDENTITY_MISMATCH')
    if expected_actions_sha256 is not None and tape['actions_sha256'] != expected_actions_sha256:
        raise ValueError('EXTERNAL_ACTION_IDENTITY_MISMATCH')
    c = copy.deepcopy(tape['config'])
    if set(c) != {'schema', 'scope', 'currency', 'opening', 'working', 'contract', 'manifest_sha256'} or c['schema'] != 'agi-alpha/commercial010-tape/v1':
        raise ValueError('EXACT_TAPE_CONFIG_REQUIRED')
    with _native_replay_context(tape, root=root, manifest=manifest, session=_session) as (replay, start):
        for seq, event in enumerate(tape['actions'][start:], start):
            if event.get('seq') != seq:
                raise ValueError('EVENT_SEQUENCE_OR_OPENING_STATE_MISMATCH')
            after = replay.execute(event['op'], event['args'], event['day'],
                                   _expected_before=event.get('before'))
            if after != event.get('after'):
                raise ValueError('EVENT_DERIVED_BALANCE_MISMATCH')
        rebuilt = replay.export()
        derived_keys = ['config', 'summary', 'journal', 'orders', 'investments', 'investment_witnesses', 'invoices', 'receivables']
        if replay.native_engine in {'prospective-v1','exact-prospective-v2'}:
            prospective_keys = {'prospective_terms', 'prospective_orders', 'prospective_claims'}
            actual_keys = prospective_keys.intersection(rebuilt)
            if actual_keys != prospective_keys.intersection(tape):
                raise ValueError('PROSPECTIVE_TAPE_EXPORTED_STATE_PRESENCE_MISMATCH')
            derived_keys += sorted(actual_keys)
        elif any(key in tape for key in ['prospective_terms', 'prospective_orders', 'prospective_claims']):
            raise ValueError('LEGACY_TAPE_CANNOT_ASSERT_PROSPECTIVE_STATE')
        for key in derived_keys:
            if rebuilt[key] != tape.get(key):
                raise ValueError('DERIVED_' + key.upper() + '_MISMATCH')
        jobs = replay.jobs
    if manifest.get('schema') == 'agi-alpha/adaptive012-services/v1':
        from adaptive_enterprise.instruments import _validate_manifest
        _validate_manifest(root, manifest)
        if set(jobs) != {job['id'] for job in manifest['jobs'] if job['accepted']}:
            raise ValueError('AUDITED_JOB_AUTHORITY_SET_CHANGED')
        fresh_jobs = {}
        for job in manifest['jobs']:
            current = {field: read_bound(root, job[field], job[field + '_sha256'])
                       for field in ['input', 'artifact', 'receipt']}
            if job['accepted'] and jobs[job['id']] != {'job': job, 'artifact': current['artifact'], 'receipt': current['receipt']}:
                raise ValueError('AUDITED_JOB_AUTHORITY_CHANGED')
            if job['accepted']:
                # The bound reads already produced detached JSON objects. Copy
                # only caller-owned metadata, not another complete artifact map.
                fresh_jobs[job['id']] = {'job': copy.deepcopy(job), 'artifact': current['artifact'], 'receipt': current['receipt']}
        _validate_manifest(root, manifest)
        if digest(manifest) != c['manifest_sha256'] or tape['config'] != c:
            raise ValueError('SOURCE_COHORT_MISMATCH')
        jobs = fresh_jobs
    if manifest.get('schema') in {'production060/native-services/v1', 'inventory061/native-services/v1', 'flexibility063/native-services/v1', 'industrial064/native-services/v1'}:
        # Dynamic outputs are not the precommitted request placeholders in
        # jobs. Rebind all historical preparations at the end too, for both
        # complete public replay and private financial-prefix reuse.
        current_jobs = load_jobs(root, manifest)
        if current_jobs != jobs:
            raise ValueError('AUDITED_JOB_AUTHORITY_CHANGED')
        if manifest.get('schema') == 'industrial064/native-services/v1':
            from industrial064.service import rebind_prepared
        elif manifest.get('schema') == 'flexibility063/native-services/v1':
            from flexibility063.service import rebind_prepared
        elif manifest.get('schema') == 'inventory061/native-services/v1':
            from inventory061.service import rebind_prepared
        else:
            from production060.service import rebind_prepared
        rebind_prepared(root, manifest, tape['actions'], current_jobs)
        if digest(manifest) != c['manifest_sha256'] or tape['config'] != c:
            raise ValueError('SOURCE_COHORT_MISMATCH')
    if _session is not None:
        _session.accept(tape, root=root, manifest=manifest)
    return ({'accepted': True, 'scope': SCOPE, 'actions_sha256': tape['actions_sha256'],
             'summary': rebuilt['summary'], 'orders': rebuilt['orders'], 'investments': rebuilt['investments']}, jobs)
