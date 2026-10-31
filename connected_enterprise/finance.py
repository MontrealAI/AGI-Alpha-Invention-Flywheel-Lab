"""Durable resource commitments through the existing owned native Account.

The write-ahead journal is local simulation state. Its HMAC uses the Account's
existing simulation-only key; no key or recovery authority enters public exports.
Resource contracts prepay their declared reconciliation/support slice. Delivery
acceptance remains a separate native service operation.
"""
from __future__ import annotations
from connected_enterprise.transition_evidence import ticket_body

import copy
import hashlib
import hmac
import os
from pathlib import Path
import tempfile
import threading

from adaptive_enterprise.account import Account, action_digest, action_prefix_digests, audit_account
from commercial.ledger import amount as validate_amount, canonical, digest, strict_json, operating_state_digest
from commercial.persistence import atomic_bytes
from commercial.ledger import _ADAPTIVE_ACCOUNT_CAPABILITY
from commercial.single_writer import SingleWriterExchange

SCHEMA = 'agi-alpha/connected014-resource-journal/v1'
SOURCE_PATHS = ('connected_enterprise/transition_evidence.py', 'connected_enterprise/finance.py', 'adaptive_enterprise/account.py',
                'commercial/ledger.py', 'commercial/persistence.py',
                'commercial/single_writer.py', 'commercial/tape_lease.py',
                'experiments/commerce006.py', 'vendor/alpha_claim/contracts.py',
                'vendor/alpha_claim/protected_exchange.py',
                'vendor/alpha_claim/protected_exchange_legacy.py', 'commercial/terms.py',
                'vendor/alpha_claim/protected_exchange_prospective_v1.py', 'commercial/native_engine.py',
                'connected_enterprise/upgrades.py', 'connected_enterprise/migration.py',
                'connected_enterprise/engine.py', 'connected_enterprise/operations.py',
                'connected_enterprise/runner.py', 'connected_enterprise/verify.py',
                'connected_enterprise/channels.py', 'connected_enterprise/pricing.py',
                'connected_enterprise/recovery.py')


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
    if op == 'mature':
        return op + ':' + _identifier(args.get('id')) + ':' + _identifier(args.get('event_id'))
    if op in {'claim', 'resolve_claim', 'recover_claim'}:
        suffix = ':' + _identifier(args.get('settlement_id')) if op != 'claim' else ''
        return op + ':' + _identifier(args.get('id')) + ':' + _identifier(args.get('claim_id')) + suffix
    if op == 'event':
        return 'event:' + _identifier(args.get('id')) + ':' + _identifier(args.get('event_id'))
    return op + ':' + _identifier(args.get('buyer') if op == 'wallet' else args.get('id'))


def _validate_native_request(op, args, day):
    if op in {'reserve', 'finish', 'cancel_investment'}:
        raise ValueError('CONNECTED_RESOURCE_COMMITMENT_ENTRYPOINT_REQUIRED')
    if op not in {'cost', 'wallet', 'offer', 'event', 'register_terms', 'claim', 'resolve_claim', 'mature', 'recover_claim', 'source_transition', 'operating_checkpoint'} or not isinstance(args, dict) or type(day) is not int or day < 0:
        raise ValueError('DECLARED_CONNECTED_NATIVE_ACTION_REQUIRED')


def _find_action(tape, op, args, day, *, action_index=None):
    ident = _native_id(op, args)
    matches = action_index.get(ident, []) if action_index is not None else [row for row in tape['actions'] if _native_id(row['op'], row['args']) == ident]
    if not matches:
        raise ValueError('JOURNALED_NATIVE_ACTION_NOT_COMMITTED')
    if len(matches) != 1:
        raise ValueError('JOURNALED_NATIVE_ACTION_NOT_UNIQUE')
    row = matches[0]
    if row['op'] != op or row['args'] != args or row['day'] != day:
        raise ValueError('JOURNALED_NATIVE_ACTION_PAYLOAD_CHANGED')
    return row


def _native_snapshot(tape, native, filesystem, *, prefixes=None):
    sequence = native['seq'] + 1
    actions_sha256 = prefixes[sequence] if prefixes is not None else digest(tape['actions'][:sequence])
    return {'summary': copy.deepcopy(native['after']),
            'state_digest': digest({'config': tape['config'], 'actions_sha256': actions_sha256, 'summary': native['after']}),
            'actions_sha256': actions_sha256, 'sequence': sequence,
            'scope': 'SIMULATED', 'ownership': 'MANDATORY_SINGLE_LOCAL_POSIX_WRITER',
            'filesystem': filesystem}


def _seed_id(request, source_sha256):
    return 'connected014-seed-' + digest({'request': request, 'source_sha256': source_sha256})[:32]


def _journal_source_cuts(journal):
    # One detached resolution per version, after complete history validation.
    # Each entry still uses its original authenticated source boundary.
    cuts=[]
    for ticket in journal.get('source_history', []):
        body=ticket_body(ticket)
        cuts.append((len(body['prior_envelope']['body']['entries']),body['from_source']))
    return tuple(cuts)


def _journal_source_at(journal, index, *, cuts=None):
    for boundary, source in _journal_source_cuts(journal) if cuts is None else cuts:
        if index < boundary:return source
    return journal['source']


def _validate_source_history(journal, record, manifest, root):
    from .upgrades import validate_ticket, transition_args, verify_historical
    previous, cut, seen = None, -1, set()
    for counter, ticket in enumerate(journal.get('source_history', []), 1):
        body = validate_ticket(ticket)
        old = body['prior_envelope']['body']
        size = len(old['entries'])
        if (body['counter'] != counter or size <= cut or old['source'] != body['from_source']
                or journal['entries'][:size] != old['entries']
                or (previous is not None and body['from_source'] != previous)
                or body['to_source']['sha256'] in seen):
            raise ValueError('JOURNAL_SOURCE_HISTORY_CHAIN_CHANGED')
        if size >= len(journal['entries']):
            raise ValueError('SOURCE_TRANSITION_NATIVE_INTENT_MISSING')
        entry = journal['entries'][size]
        request = {'operation': 'execute', 'op': 'source_transition',
                   'args': transition_args(ticket), 'day': body['day']}
        if entry['request'] != request or entry['key'] != 'native:' + _native_id('source_transition', request['args']):
            raise ValueError('SOURCE_TRANSITION_JOURNAL_INTENT_CHANGED')
        prior = body['prior_record']['ledger']
        if prior['actions'] != record['ledger']['actions'][:len(prior['actions'])]:
            raise ValueError('SOURCE_TRANSITION_HISTORICAL_PREFIX_CHANGED')
        verify_historical(ticket, manifest, root=root)
        seen.add(body['from_source']['sha256']); previous, cut = body['to_source'], size
    if previous is not None and previous != journal['source']:
        raise ValueError('SOURCE_TRANSITION_CURRENT_JOURNAL_TARGET_CHANGED')


class JournalAccount:
    def __init__(self, root, manifest, path, *, opening, working, contract, source_upgrade=None):
        self.root, self.path = Path(root).absolute(), Path(path).absolute()
        self.manifest = copy.deepcopy(manifest)
        self._mutex, self._closed, self._journal_failed = threading.RLock(), False, False
        self._account = None
        self._upgrade_ticket = copy.deepcopy(source_upgrade)
        self.journal_path = self.path.with_name(self.path.name + '.connected-journal.json')
        self.source = source_identity(self.root)
        self._header = {'schema': SCHEMA, 'scope': 'SIMULATED_LOCAL_POSIX',
                        'source': self.source, 'manifest_sha256': digest(manifest),
                        'opening': opening, 'working': working, 'contract': contract}
        try:
            self._account = Account(self.root, manifest, self.path, opening=opening,
                                    working=working, contract=contract, source_upgrade=self._upgrade_ticket)
            self._journal = self._load()
            self._account.bind_connected_source(strict_json(self.journal_path.read_bytes()))
            self._recover()
            self._recover_operating_checkpoint()
        except BaseException:
            self.close()
            raise

    def _assert_current(self):
        if self._closed or self._account is None:
            raise ValueError('CONNECTED_ACCOUNT_CLOSED')
        if self._journal_failed:
            raise ValueError('CONNECTED_JOURNAL_DURABILITY_REQUIRES_REOPEN')
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
        if not isinstance(body, dict):
            raise ValueError('CONNECTED_JOURNAL_SOURCE_OR_AUTHORITY_CHANGED')
        header = {k: v for k, v in body.items() if k not in {'entries', 'source_history'}}
        if header != self._header:
            from .upgrades import validate_ticket, verify_historical, transition_args
            if self._upgrade_ticket is None:
                raise ValueError('CONNECTED_JOURNAL_SOURCE_OR_AUTHORITY_CHANGED')
            ticket = self._upgrade_ticket
            authority = validate_ticket(ticket, key=self._account._key, root=self.root, path=self.path)
            if (authority['prior_envelope'] != envelope or authority['from_source'] != body['source']
                    or authority['prior_record']['ledger'] != self._account.export()['ledger']
                    or {k: v for k, v in header.items() if k != 'source'} != {k: v for k, v in self._header.items() if k != 'source'}):
                raise ValueError('SOURCE_UPGRADE_PRIOR_AUTHORITY_CHANGED')
            verify_historical(ticket, self.manifest, root=self.root)
            args = transition_args(ticket)
            history = body.get('source_history', [])
            seen_sources = {t['body']['from_source']['sha256'] for t in history}
            if (authority['counter'] != len(history) + 1
                    or authority['to_source']['sha256'] in seen_sources
                    or any(t['body']['id'] == authority['id'] for t in history)
                    or any(e['key'] == 'native:' + _native_id('source_transition', args) for e in body['entries'])
                    or (history and history[-1]['body']['to_source'] != authority['from_source'])):
                raise ValueError('SOURCE_UPGRADE_FORWARD_CHAIN_OR_IDENTITY_INVALID')
            request = {'operation': 'execute', 'op': 'source_transition', 'args': args, 'day': authority['day']}
            entry = {'key': 'native:' + _native_id('source_transition', args), 'request': request,
                     'plan': None, 'funding': None, 'status': 'PENDING', 'receipt': None,
                     'obligation_receipt': None, 'attempt': None}
            body = {**copy.deepcopy(self._header), 'entries': copy.deepcopy(body['entries']) + [entry],
                    'source_history': copy.deepcopy(body.get('source_history', [])) + [ticket]}
            self._save(body)
        elif self._upgrade_ticket is not None and (not body.get('source_history') or body['source_history'][-1] != self._upgrade_ticket):
            raise ValueError('SOURCE_UPGRADE_RETRY_AUTHORIZATION_CHANGED')
        for ticket in body.get('source_history', []):
            from .upgrades import validate_ticket
            validate_ticket(ticket, key=self._account._key, path=self.path)
        if not isinstance(body.get('entries'), list):
            raise ValueError('CONNECTED_JOURNAL_ENTRIES_REQUIRED')
        keys = [row.get('key') for row in body['entries']]
        if any(not isinstance(k, str) for k in keys) or len(keys) != len(set(keys)):
            raise ValueError('UNIQUE_CONNECTED_JOURNAL_ACTIONS_REQUIRED')
        return body

    def _save(self, body=None):
        body = self._journal if body is None else body
        raw = canonical({'body': body, 'signature': self._signature(body)}) + b'\n'
        if len(raw) > 64_000_000:raise ValueError('BOUNDED_RESOURCE_JOURNAL_REQUIRED')
        atomic_bytes(self.journal_path, raw)

    def _recover(self):
        self._assert_current()
        pending = [entry for entry in self._journal['entries'] if entry['status'] == 'PENDING']
        if pending:
            if len(pending) != 1 or pending[0] is not self._journal['entries'][-1]:
                raise ValueError('ONE_FINAL_PENDING_CONNECTED_ACTION_REQUIRED')
            _audit_journal(self.export(), root=self.root, manifest=self.manifest, pending_key=pending[0]['key'])
        for entry in self._journal['entries']:
            if entry['status'] == 'PENDING':
                # Only fresh-format intents carry a preattempt certificate.
                # An advanced/partial native tail retains the ordinary recovery path.
                certified = isinstance(entry.get('attempt'), dict) and entry['attempt'] == self._attempt_identity(entry['request'])
                if certified:
                    try:
                        self._attempt(entry, new_entry=True)
                    except ValueError:
                        if entry['status'] != 'REJECTED':
                            raise
                else:
                    self._perform(entry)
            elif entry['status'] not in {'COMPLETE', 'REJECTED'}:
                raise ValueError('UNSUPPORTED_CONNECTED_JOURNAL_STATUS')
        self.audit()

    def _entry(self, key, request, *, plan=None, funding=None):
        prior = next((row for row in self._journal['entries'] if row['key'] == key), None)
        if prior:
            if prior['request'] != request:
                raise ValueError('IDEMPOTENT_CONNECTED_ACTION_PAYLOAD_CHANGED')
            return prior
        if any(row['status'] not in {'COMPLETE', 'REJECTED'} for row in self._journal['entries']):
            raise ValueError('PENDING_CONNECTED_ACTION_REQUIRES_RECOVERY')
        self.audit()
        row = {'key': key, 'request': copy.deepcopy(request), 'plan': copy.deepcopy(plan),
               'funding': funding, 'status': 'PENDING', 'receipt': None, 'obligation_receipt': None,
               'attempt': self._attempt_identity(request)}
        self._journal['entries'].append(row)
        self._save()
        return row

    def _attempt_identity(self, request):
        before = self._account.export()
        exchange = self._account._owner._exchange
        persistence = exchange.persistence
        if persistence is None or persistence.failed:
            return None
        return {'source_sha256': self.source['sha256'], 'request_sha256': digest(request),
                'account_record_sha256': digest(before), 'native_record_sha256': digest(before['ledger']),
                'native_sequence': before['snapshot']['sequence'],
                'native_state_digest': before['snapshot']['state_digest'],
                'native_actions_sha256': before['snapshot']['actions_sha256'],
                'last_day': exchange.last_day,
                'durable_tape_sha256': hashlib.sha256(persistence.tape.read_bytes()).hexdigest()}

    def _perform(self, entry):
        if entry['status'] == 'COMPLETE':
            return copy.deepcopy(entry['receipt'])
        if entry['status'] == 'REJECTED':
            raise ValueError(entry['receipt']['error'])
        request = entry['request']
        if request['operation'] == 'execute':
            _validate_native_request(request['op'], request['args'], request['day'])
            if request['op'] == 'source_transition':
                ticket = next((t for t in self._journal.get('source_history', []) if t['body']['id'] == request['args']['id']), None)
                if ticket is None:
                    raise ValueError('JOURNALED_SOURCE_AUTHORIZATION_REQUIRED')
                self._account.source_transition(ticket)
            else:
                self._account.execute(request['op'], request['args'], request['day'])
            tape = self._account.export()['ledger']
            native = _find_action(tape, request['op'], request['args'], request['day'])
            receipt = _native_snapshot(tape, native, self._account.filesystem)
        elif request['operation'] == 'spend':
            if type(request.get('seed_only', False)) is not bool or (request.get('seed_only') and entry['funding'] != 'SEED'):
                raise ValueError('DECLARED_SEED_ONLY_FINANCING_REQUIRED')
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

    def _attempt(self, entry, *, new_entry):
        """Retire only a new, reproducibly rejected, zero-effect native attempt."""
        if not new_entry:
            return self._perform(entry)
        before = self._account.export()
        exchange = self._account._owner._exchange
        persistence, last_day = exchange.persistence, exchange.last_day
        durable = persistence.tape.read_bytes() if persistence is not None else None
        try:
            return self._perform(entry)
        except ValueError as error:
            self._assert_current()
            if (persistence is None or persistence.failed or exchange.last_day != last_day
                    or entry['status'] != 'PENDING' or entry['obligation_receipt'] is not None
                    or self._account.export() != before or persistence.tape.read_bytes() != durable
                    or not str(error) or len(str(error)) > 4096):
                raise
            snapshot = before['snapshot']
            rejection = {'schema': 'agi-alpha/connected014-native-rejection/v1',
                         'error_type': 'ValueError', 'error': str(error),
                         'request_sha256': digest(entry['request']),
                         'native_sequence': snapshot['sequence'],
                         'native_actions_sha256': snapshot['actions_sha256'],
                         'native_state_digest': snapshot['state_digest'],
                         'native_record_sha256': digest(before['ledger'])}
            proposed = {**copy.deepcopy(entry), 'status': 'REJECTED', 'receipt': rejection}
            try:
                _audit_rejection(proposed, before, self.source, len(before['ledger']['actions']),
                                 root=self.root, manifest=self.manifest)
            except (ValueError, OSError):
                raise error
            entry['status'], entry['receipt'] = 'REJECTED', rejection
            try:
                self._save()
            except BaseException:
                entry['status'], entry['receipt'] = 'PENDING', None
                self._journal_failed = True
                raise
            raise

    def snapshot(self):
        with self._mutex:
            self._assert_current()
            return self._account.snapshot()

    def execute(self, op, args, day):
        with self._mutex:
            self._assert_current()
            if op == 'source_transition':
                raise ValueError('EXPLICIT_SOURCE_UPGRADE_ENTRYPOINT_REQUIRED')
            _validate_native_request(op, args, day)
            request = {'operation': 'execute', 'op': op, 'args': copy.deepcopy(args), 'day': day}
            key = 'native:' + _native_id(op, args)
            new_entry = not any(row['key'] == key for row in self._journal['entries'])
            entry = self._entry(key, request)
            return self._attempt(entry, new_entry=new_entry)

    def cost(self, ident, amount, day):
        validate_amount(amount)
        return self.execute('cost', {'id': _identifier(ident), 'amount': amount}, day)

    def advance_financial(self, day):
        """Process eligible expiries before any new funding snapshot.

        Claims at the inclusive boundary must be admitted before calling this
        operation at the next clock tick. Pending claims remain protected.
        """
        with self._mutex:
            self._assert_current()
            if type(day) is not int or day < 0:
                raise ValueError('EXPLICIT_FINANCIAL_EVENT_DAY_REQUIRED')
            tape = self._account.export()['ledger']
            if tape['actions'] and day < tape['actions'][-1]['day']:
                raise ValueError('EVENT_TIME_REGRESSION')
            terms = {t['id']: strict_json(t['terms']) for t in tape.get('prospective_terms', [])}
            states = {t['id']: t['state'] for t in tape['orders']}
            for row in tape.get('prospective_orders', []):
                if row['matured_at'] is None and states[row['order_id']] in {'released', 'breached'} and day > terms[row['terms_id']]['maturity_day']:
                    before = self._account.snapshot()['summary']
                    self.execute('mature', {'id': row['order_id'], 'event_id': 'maturity:' + row['order_id'] + ':' + row['terms_sha256'][:20]}, day)
                    after = self._account.snapshot()['summary']
                    if any(before[name] != after[name] for name in ('cash', 'profit')):
                        raise ValueError('MATURITY_CANNOT_CREATE_CASH_OR_PROFIT')
            return self._account.snapshot()

    @classmethod
    def upgrade_source(cls, root, manifest, path, *, opening, working, contract, authorization):
        return cls(root, manifest, path, opening=opening, working=working,
                   contract=contract, source_upgrade=authorization)

    def spend(self, ident, kind, amount, day, work, expected_net, allow_seed=False, seed_only=False):
        with self._mutex:
            self._assert_current()
            _identifier(ident); _identifier(kind); validate_amount(amount)
            if type(day) is not int or day < 0 or type(expected_net) is not int or type(allow_seed) is not bool or type(seed_only) is not bool or (seed_only and not allow_seed):
                raise ValueError('DECLARED_CONNECTED_RESOURCE_CONTRACT_REQUIRED')
            if len(canonical(work)) > 1_000_000:
                raise ValueError('BOUNDED_CONNECTED_RESOURCE_WORK_REQUIRED')
            request = {'operation': 'spend', 'id': ident, 'kind': kind, 'amount': amount,
                       'day': day, 'work': copy.deepcopy(work), 'expected_net': expected_net, 'allow_seed': allow_seed}
            if seed_only:
                request['seed_only'] = True
            existing = next((row for row in self._journal['entries'] if row['key'] == 'spend:' + ident), None)
            if existing:
                return self._perform(self._entry('spend:' + ident, request))
            if amount == 0:
                return None
            # A rollback attempt must retain the canonical zero-effect rejection
            # receipt. Do not process due events for a stale requested clock;
            # the native writer below rejects and journals that exact attempt.
            if day >= self._account._owner._exchange.last_day:
                self.advance_financial(day)
            snapshot = self._account.snapshot()
            summary = snapshot['summary']
            if seed_only:
                seed_remaining = max(0, self._header['opening'] - self._header['working'] - summary['expensePaid'] - summary['payables'] - summary['reservedInvestment'])
                if amount > seed_remaining:
                    return None
            earned = not seed_only and expected_net > 0 and min(summary['available'], summary['unrestrictedEarned']) >= amount
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
            return self._attempt(self._entry('spend:' + ident, request, plan=plan,
                                            funding='EARNED' if earned else 'SEED'), new_entry=True)

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

    def seal_checkpoint(self, state, *, anchored=False):
        with self._mutex:
            self._assert_current()
            if not isinstance(state, dict) or len(canonical(state)) > 32_000_000:
                raise ValueError('BOUNDED_OPERATING_CHECKPOINT_STATE_REQUIRED')
            tape = self._account.export()['ledger']
            markers = [e for e in tape['actions'] if e['op'] == 'operating_checkpoint']
            if anchored or markers:
                state_sha256 = operating_state_digest(state)
                prior = next((e for e in markers if e['args']['state_sha256'] == state_sha256), None)
                if prior is not None and prior is not markers[-1]:
                    raise ValueError('STALE_SIGNED_OPERATING_STATE_REWIND_FORBIDDEN')
                if prior is None:
                    current = state.get('current')
                    event = current.get('event', current) if isinstance(current, dict) else {}
                    clocks = [state.get('last_time', 0), state.get('last_hour', 0), event.get('time', event.get('hour', 0))]
                    if any(type(value) is not int or value < 0 for value in clocks):
                        raise ValueError('OPERATING_CHECKPOINT_INTEGER_CLOCK_REQUIRED')
                    day = max([e['day'] for e in tape['actions']] + clocks)
                    self.execute('operating_checkpoint', {'id': 'operating-state-' + state_sha256,
                                 'state_sha256': state_sha256, 'counter': len(markers) + 1}, day)
                    tape = self._account.export()['ledger']
            body = {'schema': 'agi-alpha/connected014-operating-checkpoint/v1',
                    'scope': 'SIMULATED_LOCAL_POSIX', 'contract': self._header['contract'],
                    'source_sha256': self.source['sha256'],
                    'manifest_sha256': self._header['manifest_sha256'],
                    'native_sequence': len(tape['actions']),
                    'native_actions_sha256': tape['actions_sha256'], 'state': copy.deepcopy(state)}
            signature = hmac.new(self._account._key, b'connected014-operating-state\n' + canonical(body), hashlib.sha256).hexdigest()
            return {'body': body, 'signature': signature}

    def _checkpoint_intent_signature(self, body):
        return hmac.new(self._account._key, b'connected-operating-checkpoint-intent\n' + canonical(body), hashlib.sha256).hexdigest()

    def _clear_operating_intent(self, path):
        path.unlink()
        descriptor=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)

    def _reject_obsolete_operating_intent(self, intent_path, body):
        target = self.path.parent / 'STATE.json'
        if not target.is_file() or target.is_symlink():
            return False
        envelope = strict_json(target.read_bytes())
        tape = self._account.export()['ledger']
        try:
            self.verify_checkpoint(envelope)
        except ValueError as error:
            # During a committed source transition STATE can still be the exact
            # signed predecessor authorized by that transition. No other old
            # checkpoint or native tail is a compatible recovery authority.
            if str(error) != 'OPERATING_CHECKPOINT_SOURCE_OR_AUTHORITY_CHANGED' or self._upgrade_ticket is None:
                raise
            from .upgrades import validate_ticket
            ticket=validate_ticket(self._upgrade_ticket,key=self._account._key,root=self.root,path=self.path)
            prior=ticket.get('operating',{}).get('prior_checkpoint')
            if envelope != prior or envelope['body']['source_sha256'] != ticket['from_source']['sha256']:
                raise ValueError('OPERATING_INTENT_PENDING_TRANSITION_CHECKPOINT_CHANGED')
            signed=hmac.new(self._account._key,b'connected014-operating-state\n'+canonical(envelope['body']),hashlib.sha256).hexdigest()
            n=envelope['body']['native_sequence'];tail=tape['actions'][n:]
            if (not hmac.compare_digest(str(envelope['signature']),signed)
                    or digest(tape['actions'][:n])!=envelope['body']['native_actions_sha256']
                    or len(tail) not in {1,2} or tail[0]['op']!='source_transition'
                    or tail[0]['args']['id']!=ticket['id']
                    or len(tail)==2 and (tail[1]['op']!='cost' or tail[1]['args']!={'id':'source-upgrade-'+ticket['id'],'amount':ticket['operating']['policy']['upgrade_cost_microUSD']})):
                raise ValueError('OPERATING_INTENT_PENDING_TRANSITION_NATIVE_TAIL_CHANGED')
        markers = [e for e in tape['actions'] if e['op'] == 'operating_checkpoint']
        if (not markers or envelope['body']['native_sequence'] <= body['prior_sequence']
                or operating_state_digest(envelope['body']['state']) != markers[-1]['args']['state_sha256']):
            return False
        raw = intent_path.read_bytes(); sha = hashlib.sha256(raw).hexdigest()
        archive = self.path.with_name(self.path.name + '.rejected-operating-intents')
        if archive.is_symlink():
            raise ValueError('OPERATING_INTENT_ARCHIVE_SYMLINK_REFUSED')
        archive.mkdir(exist_ok=True)
        rejected = archive / (sha + '.json')
        if rejected.exists() and rejected.read_bytes() != raw:
            raise ValueError('REJECTED_OPERATING_INTENT_HISTORY_CHANGED')
        os.replace(intent_path, rejected)
        for directory in [archive, intent_path.parent]:
            descriptor=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(descriptor)
            finally:os.close(descriptor)
        return True

    def _recover_operating_checkpoint(self):
        intent_path = self.path.with_name(self.path.name + '.operating-checkpoint-intent.json')
        if not intent_path.exists():
            return
        if intent_path.is_symlink() or not intent_path.is_file() or intent_path.stat().st_size > 34_000_000:
            raise ValueError('BOUNDED_REGULAR_OPERATING_CHECKPOINT_INTENT_REQUIRED')
        envelope = strict_json(intent_path.read_bytes())
        if not isinstance(envelope, dict) or set(envelope) != {'body', 'signature'}:
            raise ValueError('SIGNED_OPERATING_CHECKPOINT_INTENT_REQUIRED')
        body = envelope['body']
        fields = {'schema', 'path', 'source_sha256', 'manifest_sha256', 'prior_sequence', 'prior_actions_sha256', 'state'}
        if (not isinstance(body, dict) or set(body) != fields
                or body['schema'] != 'agi-alpha/connected-operating-checkpoint-intent/v1'
                or not hmac.compare_digest(str(envelope['signature']), self._checkpoint_intent_signature(body))
                or body['manifest_sha256'] != self._header['manifest_sha256']
                or body['path'] != str(self.path.parent / 'STATE.json')):
            raise ValueError('OPERATING_CHECKPOINT_INTENT_AUTHORITY_CHANGED')
        tape = self._account.export()['ledger']; n = body['prior_sequence']
        if type(n) is not int or not 0 <= n <= len(tape['actions']) or digest(tape['actions'][:n]) != body['prior_actions_sha256']:
            raise ValueError('OPERATING_CHECKPOINT_INTENT_NATIVE_PREFIX_CHANGED')
        if body['source_sha256'] != self.source['sha256']:
            history = self._account.export().get('source_transitions', {}).values()
            known = {t['body'][field]['sha256'] for t in history for field in ['from_source', 'to_source']}
            if body['source_sha256'] in known and self._reject_obsolete_operating_intent(intent_path, body):
                return
            raise ValueError('OPERATING_CHECKPOINT_INTENT_SOURCE_AUTHORITY_CHANGED')
        tail = tape['actions'][n:]
        if tail and (len(tail) != 1 or tail[0]['op'] != 'operating_checkpoint' or tail[0]['args']['state_sha256'] != operating_state_digest(body['state'])):
            if self._reject_obsolete_operating_intent(intent_path, body):
                return
            raise ValueError('OPERATING_CHECKPOINT_INTENT_HISTORY_REWIND_FORBIDDEN')
        checkpoint = self.seal_checkpoint(body['state'], anchored=True)
        target = Path(body['path'])
        if target.is_symlink() or any(p.is_symlink() for p in target.parents):
            raise ValueError('OPERATING_CHECKPOINT_PATH_SYMLINK_REFUSED')
        atomic_bytes(target, canonical(checkpoint) + b'\n')
        self._clear_operating_intent(intent_path)

    def save_checkpoint(self, path, state):
        with self._mutex:
            self._assert_current(); path = Path(path).absolute()
            if path != self.path.parent / 'STATE.json' or path.is_symlink() or any(p.is_symlink() for p in path.parents):
                raise ValueError('OWNED_CANONICAL_OPERATING_CHECKPOINT_PATH_REQUIRED')
            if not isinstance(state, dict) or len(canonical(state)) > 32_000_000:
                raise ValueError('BOUNDED_OPERATING_CHECKPOINT_STATE_REQUIRED')
            tape = self._account.export()['ledger']; state_sha256 = operating_state_digest(state)
            markers = [e for e in tape['actions'] if e['op'] == 'operating_checkpoint']
            prior = next((e for e in markers if e['args']['state_sha256'] == state_sha256), None)
            if prior is not None and prior is not markers[-1]:
                raise ValueError('STALE_SIGNED_OPERATING_STATE_REWIND_FORBIDDEN')
            body = {'schema': 'agi-alpha/connected-operating-checkpoint-intent/v1', 'path': str(path),
                    'source_sha256': self.source['sha256'], 'manifest_sha256': self._header['manifest_sha256'],
                    'prior_sequence': len(tape['actions']), 'prior_actions_sha256': tape['actions_sha256'],
                    'state': copy.deepcopy(state)}
            intent = {'body': body, 'signature': self._checkpoint_intent_signature(body)}
            intent_path = self.path.with_name(self.path.name + '.operating-checkpoint-intent.json')
            try:
                atomic_bytes(intent_path, canonical(intent) + b'\n')
                checkpoint = self.seal_checkpoint(state, anchored=True)
                atomic_bytes(path, canonical(checkpoint) + b'\n')
                self._clear_operating_intent(intent_path)
            except BaseException:
                self._journal_failed = True
                raise
            return checkpoint

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
            markers = [e for e in tape['actions'] if e['op'] == 'operating_checkpoint']
            if markers and (operating_state_digest(body['state']) != markers[-1]['args']['state_sha256']
                            or type(sequence) is not int or sequence <= markers[-1]['seq']):
                raise ValueError('STALE_SIGNED_OPERATING_STATE_REWIND_FORBIDDEN')
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


def _pending_native_coverage(entry, tape, record, start, prefixes):
    request = entry['request']
    if entry['receipt'] is not None:
        raise ValueError('PENDING_CONNECTED_RECEIPT_MUST_BE_UNACKNOWLEDGED')
    commands = []
    if request['operation'] == 'execute':
        _validate_native_request(request['op'], request['args'], request['day'])
        commands.append({'op': request['op'], 'args': request['args'], 'day': request['day']})
        if entry['key'] != 'native:' + _native_id(request['op'], request['args']) or entry['plan'] is not None or entry['funding'] is not None or entry['obligation_receipt'] is not None:
            raise ValueError('PENDING_CONNECTED_NATIVE_AUTHORITY_MISMATCH')
    elif request['operation'] == 'spend':
        if entry['key'] != 'spend:' + request['id']:
            raise ValueError('PENDING_CONNECTED_SPEND_IDENTITY_MISMATCH')
        if entry['funding'] == 'EARNED':
            plan = entry['plan']
            before = tape['actions'][start]['before'] if start < len(tape['actions']) else tape['summary']
            expected_state = digest({'config': tape['config'], 'actions_sha256': prefixes[start], 'summary': before})
            if plan['expected_state_digest'] != expected_state or action_digest(plan, expected_state, request['amount'], request['expected_net']) != plan['authorized_digest']:
                raise ValueError('PENDING_CONNECTED_SPEND_AUTHORIZATION_MISMATCH')
            options = plan['selected_options']
            if len(options) != 1 or options[0]['kind'] != 'prepaid_resource':
                raise ValueError('PENDING_CONNECTED_RESOURCE_CONTRACT_REQUIRED')
            execution = options[0]['execution']
            source = record['connected_journal']['source']
            if plan['source_hashes'] != source['files'] or execution['source_sha256'] != source['sha256'] or execution['kind'] != request['kind'] or execution['work_sha256'] != digest(request['work']):
                raise ValueError('PENDING_CONNECTED_RESOURCE_SOURCE_MISMATCH')
            if start == len(tape['actions']) and entry['obligation_receipt'] is not None:
                raise ValueError('PENDING_CONNECTED_RESOLUTION_REQUIRES_NATIVE_RESERVATION')
            body = {'schema': 'agi-alpha/adaptive012-action-proof/v1', 'scope': 'SIMULATED_LOCAL_INTEGRITY_ONLY',
                    'plan': {k: v for k, v in plan.items() if k not in {'authorized_digest', 'expected_state_digest'}},
                    'expected_state_digest': plan['expected_state_digest'], 'authorized_digest': plan['authorized_digest'],
                    'amount_microUSD': request['amount'], 'expected_net_microUSD': request['expected_net'], 'day': request['day']}
            proof = record['action_proofs'].get(plan['plan_id'])
            if proof is not None and proof['body'] != body:
                raise ValueError('PENDING_CONNECTED_SPEND_NATIVE_PROOF_MISMATCH')
            commands.append({'op': 'reserve', 'args': {'id': plan['plan_id'], 'amount': request['amount'],
                'expected_net_value': request['expected_net'], 'intent_sha256': digest(body)}, 'day': request['day']})
            if entry['obligation_receipt'] is not None:
                commands.append({'op': 'finish', 'args': {'id': plan['plan_id'], 'amount': request['amount'],
                    'artifact_sha256': digest({'work_artifact_sha256': digest(request['work']),
                        'obligation_receipt_sha256': digest(entry['obligation_receipt'])})}, 'day': request['day']})
        elif entry['funding'] == 'SEED' and request['allow_seed'] and entry['plan'] is None and entry['obligation_receipt'] is None:
            commands.append({'op': 'cost', 'args': {'id': _seed_id(request, record['connected_journal']['source']['sha256']),
                'amount': request['amount']}, 'day': request['day']})
        else:
            raise ValueError('AUTHORIZED_CONNECTED_FUNDING_REQUIRED')
    else:
        raise ValueError('SUPPORTED_CONNECTED_JOURNAL_OPERATION_REQUIRED')
    tail = [{'op': row['op'], 'args': row['args'], 'day': row['day']} for row in tape['actions'][start:]]
    if len(tail) > len(commands) or tail != commands[:len(tail)]:
        raise ValueError('PENDING_CONNECTED_NATIVE_TAIL_MISMATCH')
    return list(range(start, len(tape['actions'])))


def audit_journal(record, *, root, manifest):
    """Public independent finance replay and journal/native source reconciliation."""
    return _audit_journal(record, root=root, manifest=manifest)


def _audit_rejection(entry, record, source, start, *, root, manifest):
    """Reproduce the rejection at its exact native prefix without live writes."""
    receipt, tape = entry['receipt'], record['ledger']
    fields = {'schema', 'error_type', 'error', 'request_sha256', 'native_sequence',
              'native_actions_sha256', 'native_state_digest', 'native_record_sha256'}
    if (not isinstance(receipt, dict) or set(receipt) != fields
            or receipt['schema'] != 'agi-alpha/connected014-native-rejection/v1'
            or receipt['error_type'] != 'ValueError' or not isinstance(receipt['error'], str)
            or not 1 <= len(receipt['error']) <= 4096 or type(receipt['native_sequence']) is not int
            or receipt['native_sequence'] != start or receipt['request_sha256'] != digest(entry['request'])):
        raise ValueError('SOURCE_BOUND_CONNECTED_REJECTION_REQUIRED')
    actions = tape['actions'][:start]
    summary = tape['actions'][start]['before'] if start < len(tape['actions']) else tape['summary']
    prefix_sha256 = digest(actions)
    if (receipt['native_actions_sha256'] != prefix_sha256
            or receipt['native_state_digest'] != digest({'config': tape['config'], 'actions_sha256': prefix_sha256, 'summary': summary})):
        raise ValueError('CONNECTED_REJECTION_NATIVE_PREFIX_MISMATCH')
    attempt = entry.get('attempt')
    durable = canonical({'schema': 'agi-alpha/commercial010-durable-actions/v1', 'config': tape['config']}) + b'\n'
    durable += b''.join(canonical(row) + b'\n' for row in actions)
    if (not isinstance(attempt, dict) or set(attempt) != {'source_sha256', 'request_sha256', 'account_record_sha256',
            'native_record_sha256', 'native_sequence', 'native_state_digest', 'native_actions_sha256', 'last_day', 'durable_tape_sha256'}
            or attempt['source_sha256'] != source['sha256'] or attempt['request_sha256'] != receipt['request_sha256']
            or any(attempt[key] != receipt[key] for key in ['native_sequence', 'native_record_sha256', 'native_state_digest', 'native_actions_sha256'])
            or attempt['last_day'] != (actions[-1]['day'] if actions else -1)
            or attempt['durable_tape_sha256'] != hashlib.sha256(durable).hexdigest()
            or not isinstance(attempt['account_record_sha256'], str) or len(attempt['account_record_sha256']) != 64):
        raise ValueError('CONNECTED_REJECTION_ATTEMPT_CERTIFICATE_MISMATCH')
    prefix = {**tape, 'actions': actions, 'summary': summary}
    pending = {**entry, 'status': 'PENDING', 'receipt': None}
    authority = {**record, 'connected_journal': {'source': source}}
    _pending_native_coverage(pending, prefix, authority, start, action_prefix_digests(actions))
    request = entry['request']
    if request['operation'] == 'execute':
        op, args = request['op'], request['args']
    elif entry['funding'] == 'EARNED':
        plan = entry['plan']
        body = {'schema': 'agi-alpha/adaptive012-action-proof/v1', 'scope': 'SIMULATED_LOCAL_INTEGRITY_ONLY',
                'plan': {k: v for k, v in plan.items() if k not in {'authorized_digest', 'expected_state_digest'}},
                'expected_state_digest': plan['expected_state_digest'], 'authorized_digest': plan['authorized_digest'],
                'amount_microUSD': request['amount'], 'expected_net_microUSD': request['expected_net'], 'day': request['day']}
        op, args = 'reserve', {'id': plan['plan_id'], 'amount': request['amount'],
                              'expected_net_value': request['expected_net'], 'intent_sha256': digest(body)}
    else:
        op, args = 'cost', {'id': _seed_id(request, source['sha256']), 'amount': request['amount']}
    cfg = tape['config']
    with tempfile.TemporaryDirectory(prefix='connected014-rejection-audit-') as temporary:
        with SingleWriterExchange(Path(temporary) / 'replay.sqlite', root=root, manifest=manifest,
                                  opening=cfg['opening'], working=cfg['working'], contract=cfg['contract'],
                                  durable=False, _account_capability=_ADAPTIVE_ACCOUNT_CAPABILITY) as owner:
            replay = owner._exchange
            for event in actions:
                replay.execute(event['op'], event['args'], event['day'])
            before, day = replay.export(), replay.last_day
            if digest(before) != receipt['native_record_sha256']:
                raise ValueError('CONNECTED_REJECTION_NATIVE_RECORD_MISMATCH')
            try:
                replay.execute(op, args, request['day'])
            except ValueError as error:
                if str(error) == receipt['error'] and replay.export() == before and replay.last_day == day:
                    return
            raise ValueError('CONNECTED_REJECTION_NOT_REPRODUCIBLE_WITHOUT_MUTATION')


def _audit_journal(record, *, root, manifest, pending_key=None):
    journal = record.get('connected_journal')
    if not isinstance(journal, dict) or digest(journal) != record.get('connected_journal_sha256'):
        raise ValueError('CONNECTED_JOURNAL_PUBLIC_IDENTITY_MISMATCH')
    tape = record['ledger']
    if journal.get('source') != source_identity(root) or journal.get('manifest_sha256') != digest(manifest):
        raise ValueError('CONNECTED_JOURNAL_PUBLIC_SOURCE_MISMATCH')
    if journal.get('schema') != SCHEMA or any(journal.get(k) != tape['config'].get(k) for k in ['opening', 'working', 'contract']):
        raise ValueError('CONNECTED_JOURNAL_NATIVE_AUTHORITY_MISMATCH')
    pending_transition = None
    if pending_key is not None and journal.get('entries'):
        entry = journal['entries'][-1]; request = entry.get('request', {})
        if entry.get('key') == pending_key and entry.get('status') == 'PENDING' and request.get('op') == 'source_transition':
            history = journal.get('source_history', [])
            if not history:
                raise ValueError('SIGNED_PENDING_SOURCE_HISTORY_REQUIRED')
            from .upgrades import transition_args
            pending_transition = history[-1]
            if request != {'operation': 'execute', 'op': 'source_transition', 'args': transition_args(pending_transition), 'day': pending_transition['body']['day']}:
                raise ValueError('PENDING_SOURCE_INTENT_ARGUMENTS_CHANGED')
            if any(e['op'] == 'source_transition' and e['args']['id'] == pending_transition['body']['id'] for e in tape['actions']):
                pending_transition = None
    checked = audit_account(record, root=root, manifest=manifest, pending_source_transition=pending_transition)
    _validate_source_history(journal, record, manifest, root)
    source_cuts = _journal_source_cuts(journal)
    prefixes = action_prefix_digests(tape['actions'])
    action_index = {}
    for native in tape['actions']:
        action_index.setdefault(_native_id(native['op'], native['args']), []).append(native)
    keys, spent, covered, rejected = set(), 0, [], 0
    for index, entry in enumerate(journal['entries']):
        entry_source = _journal_source_at(journal, index, cuts=source_cuts)
        if pending_key is not None and entry['key'] == pending_key:
            if index != len(journal['entries']) - 1 or entry['status'] != 'PENDING' or covered != list(range(len(covered))):
                raise ValueError('ONE_FINAL_PENDING_CONNECTED_ACTION_REQUIRED')
            covered.extend(_pending_native_coverage(entry, tape, record, len(covered), prefixes))
            continue
        if entry['key'] not in keys and entry['status'] == 'REJECTED':
            if covered != list(range(len(covered))):
                raise ValueError('CONNECTED_REJECTION_NATIVE_PREFIX_MISMATCH')
            if entry_source == journal['source']:
                _audit_rejection(entry, record, entry_source, len(covered), root=root, manifest=manifest)
            keys.add(entry['key']); rejected += 1
            continue
        if entry['key'] in keys or entry['status'] != 'COMPLETE':
            raise ValueError('COMPLETE_UNIQUE_CONNECTED_JOURNAL_REQUIRED')
        keys.add(entry['key'])
        request, receipt = entry['request'], entry['receipt']
        if request['operation'] == 'execute':
            _validate_native_request(request['op'], request['args'], request['day'])
            native = _find_action(tape, request['op'], request['args'], request['day'], action_index=action_index)
            if entry['key'] != 'native:' + _native_id(request['op'], request['args']) or receipt != _native_snapshot(tape, native, receipt.get('filesystem'), prefixes=prefixes):
                raise ValueError('CONNECTED_NATIVE_RECEIPT_CHANGED')
            covered.append(native['seq'])
        elif request['operation'] == 'spend':
            if receipt['id'] != request['id'] or receipt['kind'] != request['kind'] or receipt['amount'] != request['amount'] or receipt['day'] != request['day'] or receipt['work_sha256'] != digest(request['work']) or receipt['source_sha256'] != entry_source['sha256'] or receipt['funding'] != entry['funding']:
                raise ValueError('CONNECTED_SPEND_RECEIPT_CHANGED')
            if entry['funding'] == 'EARNED':
                plan = entry['plan']
                public_proof = record['action_proofs'].get(plan['plan_id'])
                clean = {k: v for k, v in plan.items() if k not in {'authorized_digest', 'expected_state_digest'}}
                if not public_proof or public_proof['body']['plan'] != clean or public_proof['body']['amount_microUSD'] != request['amount'] or public_proof['body']['expected_net_microUSD'] != request['expected_net'] or record['obligation_resolutions'].get(plan['plan_id']) != entry['obligation_receipt']:
                    raise ValueError('CONNECTED_SPEND_NATIVE_PROOF_MISMATCH')
                reservation = _find_action(tape, 'reserve', {'id': plan['plan_id'], 'amount': request['amount'],
                    'expected_net_value': request['expected_net'], 'intent_sha256': digest(public_proof['body'])}, request['day'], action_index=action_index)
                covered.append(reservation['seq'])
                execution = plan['selected_options'][0]['execution']
                if execution['kind'] != request['kind'] or execution['work_sha256'] != digest(request['work']) or execution['source_sha256'] != entry_source['sha256'] or plan['source_hashes'] != entry_source['files']:
                    raise ValueError('CONNECTED_RESOURCE_CONTRACT_SOURCE_MISMATCH')
                artifact = digest({'work_artifact_sha256': digest(request['work']),
                                   'obligation_receipt_sha256': digest(entry['obligation_receipt'])})
                native = _find_action(tape, 'finish', {'id': plan['plan_id'], 'amount': request['amount'], 'artifact_sha256': artifact}, request['day'], action_index=action_index)
                if receipt['plan_id'] != plan['plan_id'] or receipt['obligation_receipt_sha256'] != digest(entry['obligation_receipt']):
                    raise ValueError('CONNECTED_SPEND_RESOLUTION_CHANGED')
            elif entry['funding'] == 'SEED' and request['allow_seed']:
                native = _find_action(tape, 'cost', {'id': _seed_id(request, entry_source['sha256']), 'amount': request['amount']}, request['day'], action_index=action_index)
                if request.get('seed_only'):
                    before = native['before']
                    seed_remaining = max(0, tape['config']['opening'] - tape['config']['working'] - before['expensePaid'] - before['payables'] - before['reservedInvestment'])
                    if request['amount'] > seed_remaining:
                        raise ValueError('SEED_ONLY_CAPITAL_ENVELOPE_EXCEEDED')
                if receipt['plan_id'] is not None:
                    raise ValueError('SEED_CANNOT_CLAIM_EARNED_RESERVATION')
            else:
                raise ValueError('AUTHORIZED_CONNECTED_FUNDING_REQUIRED')
            expected_receipt = {'id': request['id'], 'kind': request['kind'], 'amount': request['amount'],
                               'day': request['day'], 'funding': entry['funding'],
                               'plan_id': entry['plan']['plan_id'] if entry['plan'] else None,
                               'work_sha256': digest(request['work']), 'source_sha256': entry_source['sha256'],
                               'native_event_sequence': native['seq'],
                               'native_actions_sha256': prefixes[native['seq'] + 1],
                               'obligation_receipt_sha256': digest(entry['obligation_receipt']) if entry['obligation_receipt'] else None,
                               'prepaid_support_microUSD': max(entry['plan']['selected_options'][0]['later_liabilities'].values()) if entry['plan'] else 0}
            if entry['key'] != 'spend:' + request['id'] or receipt != expected_receipt:
                raise ValueError('CONNECTED_SPEND_NATIVE_COMMITMENT_CHANGED')
            covered.append(native['seq'])
            spent += request['amount']
        else:
            raise ValueError('SUPPORTED_CONNECTED_JOURNAL_OPERATION_REQUIRED')
    if covered != list(range(len(tape['actions']))):
        raise ValueError('CONNECTED_JOURNAL_NATIVE_ACTION_COVERAGE_REQUIRED')
    return {**checked, **({'recovery_preflight_only': True} if pending_key is not None else {}),
            'connected_journal_entries': len(keys),
            'connected_rejected_entries': rejected,
            'connected_native_actions_covered': len(covered),
            'source_bound_resource_spend_microUSD': spent,
            'journal_authenticity_scope': 'Public source/native commitments verified; private local WAL HMAC checked only on owner reopen.'}
