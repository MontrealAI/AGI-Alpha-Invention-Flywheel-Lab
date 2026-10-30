"""Durable resource commitments through the existing owned native Account.

The write-ahead journal is local simulation state. Its HMAC uses the Account's
existing simulation-only key; no key or recovery authority enters public exports.
Resource contracts prepay their declared reconciliation/support slice. Delivery
acceptance remains a separate native service operation.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
from pathlib import Path
import threading

from adaptive_enterprise.account import Account, action_digest, audit_account
from commercial.ledger import amount as validate_amount, canonical, digest, strict_json
from commercial.persistence import atomic_bytes

SCHEMA = 'agi-alpha/connected014-resource-journal/v1'
SOURCE_PATHS = ('connected_enterprise/finance.py', 'adaptive_enterprise/account.py',
                'commercial/ledger.py', 'commercial/persistence.py',
                'commercial/single_writer.py', 'commercial/tape_lease.py',
                'experiments/commerce006.py', 'vendor/alpha_claim/contracts.py',
                'vendor/alpha_claim/protected_exchange.py')


def source_identity(root):
    root = Path(root).absolute()
    files = {}
    for name in SOURCE_PATHS:
        path = root / name
        if not path.is_file() or any(p.is_symlink() for p in [path, *path.parents]):
            raise ValueError('REGULAR_CONNECTED_FINANCE_SOURCE_REQUIRED:' + name)
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {'files': files, 'sha256': digest(files)}


def _identifier(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        raise ValueError('BOUNDED_CONNECTED_ACTION_ID_REQUIRED')
    return value


def _native_id(op, args):
    if op == 'event':
        return 'event:' + _identifier(args.get('id')) + ':' + _identifier(args.get('event_id'))
    return op + ':' + _identifier(args.get('buyer') if op == 'wallet' else args.get('id'))


def _find_action(tape, op, args, day):
    ident = _native_id(op, args)
    matches = [row for row in tape['actions'] if _native_id(row['op'], row['args']) == ident]
    if not matches:
        raise ValueError('JOURNALED_NATIVE_ACTION_NOT_COMMITTED')
    row = matches[-1]
    if row['op'] != op or row['args'] != args or row['day'] != day:
        raise ValueError('JOURNALED_NATIVE_ACTION_PAYLOAD_CHANGED')
    return row


def _native_snapshot(tape, native, filesystem):
    prefix = tape['actions'][:native['seq'] + 1]
    actions_sha256 = digest(prefix)
    return {'summary': copy.deepcopy(native['after']),
            'state_digest': digest({'config': tape['config'], 'actions_sha256': actions_sha256, 'summary': native['after']}),
            'actions_sha256': actions_sha256, 'sequence': len(prefix),
            'scope': 'SIMULATED', 'ownership': 'MANDATORY_SINGLE_LOCAL_POSIX_WRITER',
            'filesystem': filesystem}


def _seed_id(request, source_sha256):
    return 'connected014-seed-' + digest({'request': request, 'source_sha256': source_sha256})[:32]


class JournalAccount:
    def __init__(self, root, manifest, path, *, opening, working, contract):
        self.root, self.path = Path(root).absolute(), Path(path).absolute()
        self.manifest = copy.deepcopy(manifest)
        self._mutex, self._closed = threading.RLock(), False
        self._account = None
        self.journal_path = self.path.with_name(self.path.name + '.connected-journal.json')
        self.source = source_identity(self.root)
        self._header = {'schema': SCHEMA, 'scope': 'SIMULATED_LOCAL_POSIX',
                        'source': self.source, 'manifest_sha256': digest(manifest),
                        'opening': opening, 'working': working, 'contract': contract}
        try:
            self._account = Account(self.root, manifest, self.path, opening=opening,
                                    working=working, contract=contract)
            self._journal = self._load()
            self._recover()
        except BaseException:
            self.close()
            raise

    def _assert_current(self):
        if self._closed or self._account is None:
            raise ValueError('CONNECTED_ACCOUNT_CLOSED')
        self._account._assert_owner()
        if source_identity(self.root) != self.source:
            raise ValueError('CONNECTED_FINANCE_SOURCE_CHANGED')

    def _signature(self, body):
        return hmac.new(self._account._key, b'connected014-journal\n' + canonical(body), hashlib.sha256).hexdigest()

    def _load(self):
        if not self.journal_path.exists():
            if self._account.export()['ledger']['actions']:
                raise ValueError('EXISTING_CONNECTED_ACCOUNT_JOURNAL_MISSING')
            body = {**copy.deepcopy(self._header), 'entries': []}
            self._save(body)
            return body
        if self.journal_path.is_symlink() or not self.journal_path.is_file():
            raise ValueError('REGULAR_CONNECTED_JOURNAL_REQUIRED')
        raw = self.journal_path.read_bytes()
        if len(raw) > 64_000_000:
            raise ValueError('BOUNDED_CONNECTED_JOURNAL_REQUIRED')
        envelope = strict_json(raw)
        if not isinstance(envelope, dict) or set(envelope) != {'body', 'signature'}:
            raise ValueError('EXACT_CONNECTED_JOURNAL_ENVELOPE_REQUIRED')
        body = envelope['body']
        if not hmac.compare_digest(str(envelope['signature']), self._signature(body)):
            raise ValueError('CONNECTED_JOURNAL_SIGNATURE_MISMATCH')
        if not isinstance(body, dict) or {k: v for k, v in body.items() if k != 'entries'} != self._header:
            raise ValueError('CONNECTED_JOURNAL_SOURCE_OR_AUTHORITY_CHANGED')
        if not isinstance(body.get('entries'), list):
            raise ValueError('CONNECTED_JOURNAL_ENTRIES_REQUIRED')
        keys = [row.get('key') for row in body['entries']]
        if any(not isinstance(k, str) for k in keys) or len(keys) != len(set(keys)):
            raise ValueError('UNIQUE_CONNECTED_JOURNAL_ACTIONS_REQUIRED')
        return body

    def _save(self, body=None):
        body = self._journal if body is None else body
        atomic_bytes(self.journal_path, canonical({'body': body, 'signature': self._signature(body)}) + b'\n')

    def _recover(self):
        self._assert_current()
        for entry in self._journal['entries']:
            if entry['status'] == 'PENDING':
                self._perform(entry)
            elif entry['status'] != 'COMPLETE':
                raise ValueError('UNSUPPORTED_CONNECTED_JOURNAL_STATUS')
        self.audit()

    def _entry(self, key, request, *, plan=None, funding=None):
        prior = next((row for row in self._journal['entries'] if row['key'] == key), None)
        if prior:
            if prior['request'] != request:
                raise ValueError('IDEMPOTENT_CONNECTED_ACTION_PAYLOAD_CHANGED')
            return prior
        if any(row['status'] != 'COMPLETE' for row in self._journal['entries']):
            raise ValueError('PENDING_CONNECTED_ACTION_REQUIRES_RECOVERY')
        row = {'key': key, 'request': copy.deepcopy(request), 'plan': copy.deepcopy(plan),
               'funding': funding, 'status': 'PENDING', 'receipt': None, 'obligation_receipt': None}
        self._journal['entries'].append(row)
        self._save()
        return row

    def _perform(self, entry):
        if entry['status'] == 'COMPLETE':
            return copy.deepcopy(entry['receipt'])
        request = entry['request']
        if request['operation'] == 'execute':
            self._account.execute(request['op'], request['args'], request['day'])
            tape = self._account.export()['ledger']
            native = _find_action(tape, request['op'], request['args'], request['day'])
            receipt = _native_snapshot(tape, native, self._account.filesystem)
        elif request['operation'] == 'spend':
            plan = entry['plan']
            work_sha256 = digest(request['work'])
            if entry['funding'] == 'EARNED':
                self._account.reserve(plan, expected_state_digest=plan['expected_state_digest'],
                                      authorized_digest=plan['authorized_digest'], amount=request['amount'],
                                      expected_net=request['expected_net'], day=request['day'])
                if entry['obligation_receipt'] is None:
                    option = plan['selected_options'][0]
                    support = max(option['later_liabilities'].values())
                    entry['obligation_receipt'] = {
                        'schema': 'agi-alpha/adaptive012-obligation-resolution/v1',
                        'plan_id': plan['plan_id'], 'resolved_at_day': request['day'],
                        'native_actions_sha256': self._account.snapshot()['actions_sha256'],
                        'work_artifact_sha256': work_sha256,
                        'upfront_incurred_microUSD': option['upfront_cost'],
                        'later_incurred_microUSD': support, 'unused_reserve_microUSD': 0,
                        'deliveries': [], 'growth': [{'option_id': option['id'],
                            'execution_sha256': digest(option['execution']), 'prepaid_support_microUSD': support}]}
                    self._save()
                self._account.finish(plan['plan_id'], request['amount'], work_sha256, request['day'],
                                     obligation_receipt=entry['obligation_receipt'])
                finish_args = {'id': plan['plan_id'], 'amount': request['amount'],
                               'artifact_sha256': digest({'work_artifact_sha256': work_sha256,
                                                        'obligation_receipt_sha256': digest(entry['obligation_receipt'])})}
                tape = self._account.export()['ledger']
                native = _find_action(tape, 'finish', finish_args, request['day'])
            else:
                args = {'id': _seed_id(request, self.source['sha256']), 'amount': request['amount']}
                self._account.cost(args['id'], args['amount'], request['day'])
                tape = self._account.export()['ledger']
                native = _find_action(tape, 'cost', args, request['day'])
            receipt = {'id': request['id'], 'kind': request['kind'], 'amount': request['amount'],
                       'day': request['day'], 'funding': entry['funding'],
                       'plan_id': plan['plan_id'] if plan else None,
                       'work_sha256': work_sha256, 'source_sha256': self.source['sha256'],
                       'native_event_sequence': native['seq'],
                       'native_actions_sha256': digest(tape['actions'][:native['seq'] + 1]),
                       'obligation_receipt_sha256': digest(entry['obligation_receipt']) if entry['obligation_receipt'] else None,
                       'prepaid_support_microUSD': max(plan['selected_options'][0]['later_liabilities'].values()) if plan else 0}
        else:
            raise ValueError('UNSUPPORTED_CONNECTED_JOURNAL_OPERATION')
        entry['receipt'], entry['status'] = copy.deepcopy(receipt), 'COMPLETE'
        self._save()
        return copy.deepcopy(receipt)

    def snapshot(self):
        with self._mutex:
            self._assert_current()
            return self._account.snapshot()

    def execute(self, op, args, day):
        with self._mutex:
            self._assert_current()
            if op in {'reserve', 'finish', 'cancel_investment'}:
                raise ValueError('CONNECTED_RESOURCE_COMMITMENT_ENTRYPOINT_REQUIRED')
            if op not in {'cost', 'wallet', 'offer', 'event'} or not isinstance(args, dict) or type(day) is not int or day < 0:
                raise ValueError('DECLARED_CONNECTED_NATIVE_ACTION_REQUIRED')
            request = {'operation': 'execute', 'op': op, 'args': copy.deepcopy(args), 'day': day}
            entry = self._entry('native:' + _native_id(op, args), request)
            return self._perform(entry)

    def cost(self, ident, amount, day):
        validate_amount(amount)
        return self.execute('cost', {'id': _identifier(ident), 'amount': amount}, day)

    def spend(self, ident, kind, amount, day, work, expected_net, allow_seed=False):
        with self._mutex:
            self._assert_current()
            _identifier(ident); _identifier(kind); validate_amount(amount)
            if type(day) is not int or day < 0 or type(expected_net) is not int or type(allow_seed) is not bool:
                raise ValueError('DECLARED_CONNECTED_RESOURCE_CONTRACT_REQUIRED')
            if len(canonical(work)) > 1_000_000:
                raise ValueError('BOUNDED_CONNECTED_RESOURCE_WORK_REQUIRED')
            request = {'operation': 'spend', 'id': ident, 'kind': kind, 'amount': amount,
                       'day': day, 'work': copy.deepcopy(work), 'expected_net': expected_net, 'allow_seed': allow_seed}
            existing = next((row for row in self._journal['entries'] if row['key'] == 'spend:' + ident), None)
            if existing:
                return self._perform(self._entry('spend:' + ident, request))
            if amount == 0:
                return None
            self._account.audit()
            snapshot = self._account.snapshot()
            summary = snapshot['summary']
            earned = expected_net > 0 and min(summary['available'], summary['unrestrictedEarned']) >= amount
            if not earned and (not allow_seed or summary['available'] < amount):
                return None
            plan = None
            if earned:
                support = min(amount, 10_000)
                plan_id = 'connected014-resource-' + digest(ident)[:32]
                option = {'id': plan_id + '-prepaid', 'kind': 'prepaid_resource',
                          'upfront_cost': amount - support, 'later_liabilities': {'prepaid_support': support},
                          'execution': {'kind': kind, 'work_sha256': digest(work),
                                        'source_sha256': self.source['sha256'],
                                        'prepaid_support_microUSD': support,
                                        'support_contract': 'Resource price includes prepaid reconciliation/support; no later unpaid resource invoice.'}}
                plan = {'plan_id': plan_id, 'action_id': plan_id + '-action',
                        'source_hashes': self.source['files'], 'upfront_cost': amount - support,
                        'worst_later_reserve': support, 'reserve_amount': amount, 'expected_net': expected_net,
                        'selected_options': [option], 'expected_state_digest': snapshot['state_digest']}
                plan['authorized_digest'] = action_digest(plan, snapshot['state_digest'], amount, expected_net)
            return self._perform(self._entry('spend:' + ident, request, plan=plan,
                                             funding='EARNED' if earned else 'SEED'))

    def export(self):
        with self._mutex:
            self._assert_current()
            record = copy.deepcopy(self._account.export())
            record['connected_journal'] = copy.deepcopy(self._journal)
            record['connected_journal_sha256'] = digest(self._journal)
            return record

    def audit(self):
        with self._mutex:
            self._assert_current()
            return audit_journal(self.export(), root=self.root, manifest=self.manifest)

    def seal_checkpoint(self, state):
        with self._mutex:
            self._assert_current()
            if not isinstance(state, dict) or len(canonical(state)) > 32_000_000:
                raise ValueError('BOUNDED_OPERATING_CHECKPOINT_STATE_REQUIRED')
            tape = self._account.export()['ledger']
            body = {'schema': 'agi-alpha/connected014-operating-checkpoint/v1',
                    'scope': 'SIMULATED_LOCAL_POSIX', 'contract': self._header['contract'],
                    'source_sha256': self.source['sha256'],
                    'manifest_sha256': self._header['manifest_sha256'],
                    'native_sequence': len(tape['actions']),
                    'native_actions_sha256': tape['actions_sha256'], 'state': copy.deepcopy(state)}
            signature = hmac.new(self._account._key, b'connected014-operating-state\n' + canonical(body), hashlib.sha256).hexdigest()
            return {'body': body, 'signature': signature}

    def verify_checkpoint(self, envelope):
        with self._mutex:
            self._assert_current()
            if not isinstance(envelope, dict) or set(envelope) != {'body', 'signature'}:
                raise ValueError('EXACT_OPERATING_CHECKPOINT_ENVELOPE_REQUIRED')
            body = envelope['body']
            expected_keys = {'schema', 'scope', 'contract', 'source_sha256', 'manifest_sha256',
                             'native_sequence', 'native_actions_sha256', 'state'}
            if not isinstance(body, dict) or set(body) != expected_keys or len(canonical(body)) > 33_000_000:
                raise ValueError('EXACT_BOUNDED_OPERATING_CHECKPOINT_REQUIRED')
            signature = hmac.new(self._account._key, b'connected014-operating-state\n' + canonical(body), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(str(envelope['signature']), signature):
                raise ValueError('OPERATING_CHECKPOINT_SIGNATURE_MISMATCH')
            if body['schema'] != 'agi-alpha/connected014-operating-checkpoint/v1' or body['scope'] != 'SIMULATED_LOCAL_POSIX' or body['contract'] != self._header['contract'] or body['source_sha256'] != self.source['sha256'] or body['manifest_sha256'] != self._header['manifest_sha256']:
                raise ValueError('OPERATING_CHECKPOINT_SOURCE_OR_AUTHORITY_CHANGED')
            sequence = body['native_sequence']
            tape = self._account.export()['ledger']
            if type(sequence) is not int or sequence < 0 or sequence > len(tape['actions']) or digest(tape['actions'][:sequence]) != body['native_actions_sha256']:
                raise ValueError('OPERATING_CHECKPOINT_NATIVE_PREFIX_MISMATCH')
            if not isinstance(body['state'], dict):
                raise ValueError('OPERATING_CHECKPOINT_STATE_REQUIRED')
            return copy.deepcopy(body['state'])

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._account is not None:
            self._account.close()

    def __enter__(self):
        self._assert_current()
        return self

    def __exit__(self, *exc):
        self.close()


def audit_journal(record, *, root, manifest):
    """Public independent finance replay and journal/native source reconciliation."""
    checked = audit_account(record, root=root, manifest=manifest)
    journal = record.get('connected_journal')
    if not isinstance(journal, dict) or digest(journal) != record.get('connected_journal_sha256'):
        raise ValueError('CONNECTED_JOURNAL_PUBLIC_IDENTITY_MISMATCH')
    tape = record['ledger']
    if journal.get('source') != source_identity(root) or journal.get('manifest_sha256') != digest(manifest):
        raise ValueError('CONNECTED_JOURNAL_PUBLIC_SOURCE_MISMATCH')
    if journal.get('schema') != SCHEMA or any(journal.get(k) != tape['config'].get(k) for k in ['opening', 'working', 'contract']):
        raise ValueError('CONNECTED_JOURNAL_NATIVE_AUTHORITY_MISMATCH')
    keys, spent = set(), 0
    for entry in journal['entries']:
        if entry['key'] in keys or entry['status'] != 'COMPLETE':
            raise ValueError('COMPLETE_UNIQUE_CONNECTED_JOURNAL_REQUIRED')
        keys.add(entry['key'])
        request, receipt = entry['request'], entry['receipt']
        if request['operation'] == 'execute':
            native = _find_action(tape, request['op'], request['args'], request['day'])
            if entry['key'] != 'native:' + _native_id(request['op'], request['args']) or receipt != _native_snapshot(tape, native, receipt.get('filesystem')):
                raise ValueError('CONNECTED_NATIVE_RECEIPT_CHANGED')
        elif request['operation'] == 'spend':
            if receipt['id'] != request['id'] or receipt['kind'] != request['kind'] or receipt['amount'] != request['amount'] or receipt['day'] != request['day'] or receipt['work_sha256'] != digest(request['work']) or receipt['source_sha256'] != journal['source']['sha256'] or receipt['funding'] != entry['funding']:
                raise ValueError('CONNECTED_SPEND_RECEIPT_CHANGED')
            if entry['funding'] == 'EARNED':
                plan = entry['plan']
                public_proof = record['action_proofs'].get(plan['plan_id'])
                clean = {k: v for k, v in plan.items() if k not in {'authorized_digest', 'expected_state_digest'}}
                if not public_proof or public_proof['body']['plan'] != clean or public_proof['body']['amount_microUSD'] != request['amount'] or public_proof['body']['expected_net_microUSD'] != request['expected_net'] or record['obligation_resolutions'].get(plan['plan_id']) != entry['obligation_receipt']:
                    raise ValueError('CONNECTED_SPEND_NATIVE_PROOF_MISMATCH')
                execution = plan['selected_options'][0]['execution']
                if execution['kind'] != request['kind'] or execution['work_sha256'] != digest(request['work']) or execution['source_sha256'] != journal['source']['sha256'] or plan['source_hashes'] != journal['source']['files']:
                    raise ValueError('CONNECTED_RESOURCE_CONTRACT_SOURCE_MISMATCH')
                artifact = digest({'work_artifact_sha256': digest(request['work']),
                                   'obligation_receipt_sha256': digest(entry['obligation_receipt'])})
                native = _find_action(tape, 'finish', {'id': plan['plan_id'], 'amount': request['amount'], 'artifact_sha256': artifact}, request['day'])
                if receipt['plan_id'] != plan['plan_id'] or receipt['obligation_receipt_sha256'] != digest(entry['obligation_receipt']):
                    raise ValueError('CONNECTED_SPEND_RESOLUTION_CHANGED')
            elif entry['funding'] == 'SEED' and request['allow_seed']:
                native = _find_action(tape, 'cost', {'id': _seed_id(request, journal['source']['sha256']), 'amount': request['amount']}, request['day'])
                if receipt['plan_id'] is not None:
                    raise ValueError('SEED_CANNOT_CLAIM_EARNED_RESERVATION')
            else:
                raise ValueError('AUTHORIZED_CONNECTED_FUNDING_REQUIRED')
            expected_receipt = {'id': request['id'], 'kind': request['kind'], 'amount': request['amount'],
                               'day': request['day'], 'funding': entry['funding'],
                               'plan_id': entry['plan']['plan_id'] if entry['plan'] else None,
                               'work_sha256': digest(request['work']), 'source_sha256': journal['source']['sha256'],
                               'native_event_sequence': native['seq'],
                               'native_actions_sha256': digest(tape['actions'][:native['seq'] + 1]),
                               'obligation_receipt_sha256': digest(entry['obligation_receipt']) if entry['obligation_receipt'] else None,
                               'prepaid_support_microUSD': max(entry['plan']['selected_options'][0]['later_liabilities'].values()) if entry['plan'] else 0}
            if entry['key'] != 'spend:' + request['id'] or receipt != expected_receipt:
                raise ValueError('CONNECTED_SPEND_NATIVE_COMMITMENT_CHANGED')
            spent += request['amount']
        else:
            raise ValueError('SUPPORTED_CONNECTED_JOURNAL_OPERATION_REQUIRED')
    return {**checked, 'connected_journal_entries': len(keys),
            'source_bound_resource_spend_microUSD': spent,
            'journal_authenticity_scope': 'Public source/native commitments verified; private local WAL HMAC checked only on owner reopen.'}
