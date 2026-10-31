"""Mandatory local account ownership over the native simulated exchange.

Authorization records bind plans to native reservation intents; they are not a
second financial ledger. The local HMAC is a simulation integrity proof, never
external payment authority or protection against a hostile account operator.
"""
from __future__ import annotations
import copy
import hashlib
import hmac
import json
import os
from pathlib import Path
import stat
import threading
from functools import wraps

from commercial.ledger import _ADAPTIVE_ACCOUNT_CAPABILITY, _audit_native_and_jobs, amount, canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from commercial.single_writer import SingleWriterExchange

NAMESPACE = 'adaptive012'
PROOF_SCHEMA = 'agi-alpha/adaptive012-action-proof/v1'
LOCAL_FILESYSTEMS = {'overlay', 'ext2', 'ext3', 'ext4', 'xfs', 'btrfs', 'tmpfs', 'ramfs', 'zfs'}


def _hex(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _identifier(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        raise ValueError('BOUNDED_ACTION_IDENTIFIER_REQUIRED')
    return value


def _selected_contracts(plan, jobs=None):
    selected = plan.get('selected_options', [])
    if not isinstance(selected, list):
        raise ValueError('SELECTED_OBLIGATION_CONTRACTS_REQUIRED')
    seen = set()
    for option in selected:
        if (not isinstance(option, dict) or not {'id', 'kind', 'execution'} <= set(option)
                or not isinstance(option['execution'], dict)):
            raise ValueError('TYPED_SELECTED_RESOURCE_CONTRACT_REQUIRED')
        ident = _identifier(option['id']); _identifier(option['kind'])
        if ident in seen:
            raise ValueError('UNIQUE_SELECTED_RESOURCE_IDENTIFIERS_REQUIRED')
        seen.add(ident)
        if option['kind'] == 'delivery':
            execution = option['execution']
            required = {'job_id', 'customer_id', 'payment_bps', 'payment_fixed_microUSD', 'onboarding_microUSD'}
            if not required <= set(execution):
                raise ValueError('EXPLICIT_DELIVERY_EXECUTION_TERMS_REQUIRED')
            _identifier(execution['job_id']); _identifier(execution['customer_id'])
            if type(execution['payment_bps']) is not int or not 0 <= execution['payment_bps'] <= 10_000:
                raise ValueError('DECLARED_PAYMENT_TERMS_REQUIRED')
            amount(execution['payment_fixed_microUSD']); amount(execution['onboarding_microUSD'])
            if jobs is not None and execution['job_id'] not in jobs:
                raise ValueError('ADMITTED_DELIVERY_JOB_REQUIRED')
    return selected


def _declared_later(plan):
    explicit = plan.get('worst_later_reserve', 0)
    amount(explicit)
    selected = _selected_contracts(plan)
    later = 0
    for option in selected:
        if not isinstance(option, dict) or not isinstance(option.get('later_liabilities'), dict) or not option['later_liabilities']:
            raise ValueError('EXPLICIT_LATER_LIABILITY_SCENARIOS_REQUIRED')
        for value in option['later_liabilities'].values():
            amount(value)
        later += max(option['later_liabilities'].values())
    return max(explicit, later)


def _declared_upfront(plan):
    upfront = plan.get('upfront_cost', 0)
    amount(upfront)
    selected = _selected_contracts(plan)
    if selected:
        total = 0
        for option in selected:
            if not isinstance(option, dict) or 'upfront_cost' not in option:
                raise ValueError('EXPLICIT_UPFRONT_RESOURCE_CONTRACT_REQUIRED')
            amount(option['upfront_cost'])
            total += option['upfront_cost']
        if 'upfront_cost' in plan and upfront != total:
            raise ValueError('DECLARED_UPFRONT_RESOURCE_CONTRACT_MISMATCH')
        return total
    return upfront


def _requires_resolution(plan):
    upfront, later = _declared_upfront(plan), _declared_later(plan)
    return bool(plan.get('selected_options')) or upfront > 0 or later > 0


def assert_local_storage(path, storage='local_posix'):
    if storage != 'local_posix' or os.name != 'posix' or not Path('/proc/self/mountinfo').is_file():
        raise ValueError('ONLY_VERIFIABLE_LOCAL_POSIX_STORAGE_SUPPORTED')
    path = Path(path).absolute()
    if any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError('ACCOUNT_SYMLINK_REFUSED')
    candidates = []
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        before, separator, after = line.partition(' - ')
        if not separator:
            continue
        fields = before.split()
        mount = Path(fields[4].replace('\\040', ' ').replace('\\011', '\t').replace('\\134', '\\'))
        if path == mount or mount in path.parents:
            candidates.append((len(mount.parts), after.split()[0]))
    if not candidates or max(candidates)[1] not in LOCAL_FILESYSTEMS:
        raise ValueError('DISTRIBUTED_OR_UNKNOWN_FILESYSTEM_REFUSED')
    return max(candidates)[1]


def action_digest(plan, expected_state_digest, amount_microUSD, expected_net_microUSD):
    if not isinstance(plan, dict) or not _hex(expected_state_digest):
        raise ValueError('PLAN_AND_NATIVE_STATE_DIGEST_REQUIRED')
    amount(amount_microUSD, positive=True)
    amount(expected_net_microUSD, positive=True)
    _identifier(plan.get('plan_id'))
    _identifier(plan.get('action_id'))
    for key in ['reserve_amount', 'amount_microUSD', 'reserve_amount_microUSD']:
        if key in plan and (type(plan[key]) is not int or plan[key] != amount_microUSD):
            raise ValueError('PLAN_RESERVATION_AMOUNT_MISMATCH')
    for key in ['expected_net', 'expected_net_microUSD']:
        if key in plan and (type(plan[key]) is not int or plan[key] != expected_net_microUSD):
            raise ValueError('PLAN_EXPECTED_NET_MISMATCH')
    if 'upfront_cost' in plan or 'worst_later_reserve' in plan:
        upfront, later = _declared_upfront(plan), _declared_later(plan)
        amount(upfront); amount(later)
        if amount_microUSD < upfront + later:
            raise ValueError('LATER_OBLIGATIONS_NOT_FULLY_RESERVED')
    if plan.get('selected_options'):
        upfront = _declared_upfront(plan)
        if amount_microUSD < upfront + _declared_later(plan):
            raise ValueError('SELECTED_LATER_OBLIGATIONS_NOT_FULLY_RESERVED')
    if _requires_resolution(plan) and not plan.get('selected_options'):
        raise ValueError('EXPLICIT_SELECTED_OBLIGATION_CONTRACTS_REQUIRED')
    clean = {k: v for k, v in plan.items() if k not in {'authorized_digest', 'expected_state_digest'}}
    if len(canonical(clean)) > 2_000_000:
        raise ValueError('BOUNDED_PLAN_REQUIRED')
    return digest({'schema': PROOF_SCHEMA, 'plan': clean, 'expected_state_digest': expected_state_digest,
                   'amount_microUSD': amount_microUSD, 'expected_net_microUSD': expected_net_microUSD})


def action_prefix_digests(actions):
    running = hashlib.sha256(b'[')
    empty = running.copy(); empty.update(b']')
    prefixes = [empty.hexdigest()]
    for index, event in enumerate(actions):
        if index:
            running.update(b',')
        running.update(canonical(event))
        prefix = running.copy(); prefix.update(b']')
        prefixes.append(prefix.hexdigest())
    return prefixes


def _operation_id(op, args):
    if op == 'mature':
        return op + ':' + _identifier(args.get('id')) + ':' + _identifier(args.get('event_id'))
    if op in {'claim', 'resolve_claim', 'recover_claim'}:
        suffix = ':' + _identifier(args.get('settlement_id')) if op != 'claim' else ''
        return op + ':' + _identifier(args.get('id')) + ':' + _identifier(args.get('claim_id')) + suffix
    if op == 'event':
        return 'event:' + _identifier(args.get('id')) + ':' + _identifier(args.get('event_id'))
    if op == 'wallet':
        return 'wallet:' + _identifier(args.get('buyer'))
    return op + ':' + _identifier(args.get('id'))


def _validate_resolution(tape, proof, receipt, actual, work_sha256, day, jobs, *, native_actions_sha256=None):
    fields = {'schema', 'plan_id', 'resolved_at_day', 'native_actions_sha256', 'work_artifact_sha256',
              'upfront_incurred_microUSD', 'later_incurred_microUSD', 'unused_reserve_microUSD', 'deliveries', 'growth'}
    if not isinstance(receipt, dict) or set(receipt) != fields or receipt['schema'] != 'agi-alpha/adaptive012-obligation-resolution/v1':
        raise ValueError('SOURCE_BOUND_OBLIGATION_RESOLUTION_REQUIRED')
    if not _hex(work_sha256) or type(receipt['resolved_at_day']) is not int:
        raise ValueError('ACTUAL_WORK_HASH_AND_RESOLUTION_DAY_REQUIRED')
    plan = proof['body']['plan']
    native_actions_sha256 = digest(tape['actions']) if native_actions_sha256 is None else native_actions_sha256
    if receipt['plan_id'] != plan['plan_id'] or receipt['resolved_at_day'] != day or receipt['native_actions_sha256'] != native_actions_sha256 or receipt['work_artifact_sha256'] != work_sha256:
        raise ValueError('OBLIGATION_RESOLUTION_SOURCE_OR_TIME_MISMATCH')
    for key in ['upfront_incurred_microUSD', 'later_incurred_microUSD', 'unused_reserve_microUSD']:
        amount(receipt[key])
    if actual != receipt['upfront_incurred_microUSD'] + receipt['later_incurred_microUSD'] or actual + receipt['unused_reserve_microUSD'] != proof['body']['amount_microUSD']:
        raise ValueError('OBLIGATION_RESOLUTION_COST_CONSERVATION')
    selected = _selected_contracts(plan, jobs)
    if not isinstance(selected, list) or not selected or any(not isinstance(o, dict) for o in selected):
        raise ValueError('EXPLICIT_SELECTED_OBLIGATION_CONTRACTS_REQUIRED')
    if receipt['upfront_incurred_microUSD'] != _declared_upfront(plan):
        raise ValueError('UPFRONT_RESOURCE_INVOICE_MISMATCH')
    deliveries = {o['id']: o for o in selected if o['kind'] == 'delivery'}
    growth = {o['id']: o for o in selected if o['kind'] != 'delivery'}
    if not isinstance(receipt['deliveries'], list) or not isinstance(receipt['growth'], list):
        raise ValueError('EXPLICIT_RESOURCE_RESOLUTION_ROWS_REQUIRED')
    if len(receipt['deliveries']) != len(deliveries) or len(receipt['growth']) != len(growth):
        raise ValueError('ALL_SELECTED_OBLIGATIONS_REQUIRE_RESOLUTION')
    trades = {}
    for event in tape['actions']:
        args = event['args']
        if event['op'] == 'offer':
            trades[args['id']] = {**args, 'state': 'offered'}
        elif event['op'] == 'event' and args['id'] in trades:
            trades[args['id']]['state'] = {'consent': 'consented', 'fund': 'funded', 'prepare': 'verified', 'release': 'released', 'refund': 'refunded', 'cancel': 'cancelled', 'late_reversal': 'breached'}.get(args['action'], args['action'])
    incurred, seen = 0, set()
    for row in receipt['deliveries']:
        expected_fields = {'option_id', 'job_id', 'order_id', 'artifact_sha256', 'customer_id', 'outcome', 'payment_fee_microUSD', 'onboarding_microUSD'}
        if not isinstance(row, dict) or set(row) != expected_fields or row['option_id'] not in deliveries or row['option_id'] in seen:
            raise ValueError('EXACT_UNIQUE_DELIVERY_RESOLUTION_REQUIRED')
        seen.add(row['option_id']); option = deliveries[row['option_id']]; execution = option['execution']
        if row['job_id'] != execution['job_id'] or row['customer_id'] != execution['customer_id'] or row['job_id'] not in jobs or row['artifact_sha256'] != jobs[row['job_id']]['job']['artifact_sha256']:
            raise ValueError('RESOLVED_DELIVERY_SOURCE_CONTRACT_MISMATCH')
        amount(row['payment_fee_microUSD']); amount(row['onboarding_microUSD'])
        if row['outcome'] == 'NO_ORDER':
            if row['order_id'] is not None or row['payment_fee_microUSD'] or row['onboarding_microUSD'] or any(t['job_id'] == row['job_id'] for t in trades.values()):
                raise ValueError('UNACTIVATED_ORDER_HAS_NATIVE_OBLIGATION')
        elif row['outcome'] == 'NATIVE_ACCEPTED':
            trade = trades.get(row['order_id'])
            if not trade or trade['job_id'] != row['job_id'] or trade['state'] not in {'verified', 'released', 'refunded'}:
                raise ValueError('NATIVE_ACCEPTANCE_AND_PROTECTION_NOT_OBSERVED')
            bps, fixed = execution['payment_bps'], execution['payment_fixed_microUSD']
            if type(bps) is not int or not 0 <= bps <= 10000:
                raise ValueError('DECLARED_PAYMENT_TERMS_REQUIRED')
            amount(fixed); amount(execution['onboarding_microUSD'])
            expected_fee = (trade['price'] * bps + 9999) // 10000 + fixed
            if row['payment_fee_microUSD'] != expected_fee or row['onboarding_microUSD'] != execution['onboarding_microUSD']:
                raise ValueError('INCURRED_NATIVE_FEE_OR_CONTEXT_INVOICE_MISMATCH')
        else:
            raise ValueError('OBSERVED_RESOLUTION_OUTCOME_REQUIRED')
        incurred += row['payment_fee_microUSD'] + row['onboarding_microUSD']
    seen = set()
    for row in receipt['growth']:
        if not isinstance(row, dict) or set(row) != {'option_id', 'execution_sha256', 'prepaid_support_microUSD'} or row['option_id'] not in growth or row['option_id'] in seen:
            raise ValueError('EXACT_UNIQUE_PREPAID_GROWTH_RECEIPT_REQUIRED')
        seen.add(row['option_id']); option = growth[row['option_id']]
        expected_support = max(option['later_liabilities'].values())
        if row['execution_sha256'] != digest(option['execution']) or row['prepaid_support_microUSD'] != expected_support:
            raise ValueError('PREPAID_SUPPORT_SOURCE_OR_INVOICE_MISMATCH')
        incurred += expected_support
    summary = tape['summary']
    if incurred != receipt['later_incurred_microUSD'] or summary['payables'] or summary['investmentStopped'] or summary['cash'] < summary['custodyReserve'] + summary['tailReserve'] + summary['workingCapital']:
        raise ValueError('LATER_INVOICE_OR_NATIVE_PROTECTION_UNRESOLVED')
    return digest({'work_artifact_sha256': work_sha256, 'obligation_receipt_sha256': digest(receipt)})


def audit_account(record, *, root, manifest, pending_source_transition=None):
    if not isinstance(record, dict) or record.get('schema') != 'agi-alpha/adaptive012-owned-account/v1' or record.get('scope') != 'SIMULATED':
        raise ValueError('ADAPTIVE_ACCOUNT_EXPORT_REQUIRED')
    tape, proofs = record['ledger'], record['action_proofs']
    if any(event.get('op') == 'cancel_investment' for event in tape['actions']):
        raise ValueError('UNRECONCILED_INVESTMENT_CANCELLATION_RETIRED')
    resolutions = record.get('obligation_resolutions', {})
    checked, jobs = _audit_native_and_jobs(tape, root=root, manifest=manifest)
    if manifest.get('schema') != 'agi-alpha/adaptive012-services/v1':
        # Other service schemas retain their previous second qualification.
        from commercial.ledger import load_jobs
        jobs = load_jobs(root, manifest)
    transitions = record.get('source_transitions', {})
    used = []
    for index, event in enumerate(tape['actions']):
        if event['op'] != 'source_transition':
            continue
        from connected_enterprise.upgrades import validate_ticket, transition_args, verify_historical
        ticket = transitions.get(event['args']['id'])
        body = validate_ticket(ticket)
        prior = body['prior_record']['ledger']
        if (event['args'] != transition_args(ticket) or event['day'] != body['day']
                or prior['config'] != tape['config'] or prior['actions'] != tape['actions'][:index]
                or prior['summary'] != event['before'] or event['before'] != event['after']
                or body['counter'] != len(used) + 1):
            raise ValueError('SOURCE_TRANSITION_NATIVE_CONTINUITY_MISMATCH')
        if used and body['from_source'] != transitions[used[-1]]['body']['to_source']:
            raise ValueError('SOURCE_TRANSITION_VERSION_CHAIN_BROKEN')
        prior_sources = [transitions[x]['body']['from_source']['sha256'] for x in used]
        if body['to_source']['sha256'] in prior_sources:
            raise ValueError('SOURCE_TRANSITION_DOWNGRADE_OR_FORK')
        verify_historical(ticket, manifest, root=root)
        used.append(event['args']['id'])
    pending_target = None
    if pending_source_transition is not None:
        from connected_enterprise.upgrades import validate_ticket, verify_historical
        pending = validate_ticket(pending_source_transition, root=root)
        if (pending['prior_record']['ledger'] != tape or pending['counter'] != len(used) + 1
                or used and pending['from_source'] != transitions[used[-1]]['body']['to_source']):
            raise ValueError('PENDING_SOURCE_TRANSITION_NOT_BOUND_TO_EXACT_CURRENT_HISTORY')
        verify_historical(pending_source_transition, manifest, root=root)
        pending_target = pending['to_source']
    if used:
        from connected_enterprise.finance import source_identity
        if transitions[used[-1]]['body']['to_source'] != source_identity(root) and pending_target != source_identity(root):
            raise ValueError('CURRENT_SOURCE_NOT_AUTHORIZED_BY_TRANSITION')
    prefixes = action_prefix_digests(tape['actions'])
    for index, event in enumerate(tape['actions']):
        if event['op'] == 'finish':
            proof = proofs.get(event['args']['id'])
            if proof and _requires_resolution(proof['body']['plan']):
                receipt = resolutions.get(event['args']['id'])
                if not isinstance(receipt, dict):
                    raise ValueError('FINISHED_LATER_OBLIGATION_RECEIPT_MISSING')
                prefix = {**tape, 'actions': tape['actions'][:index], 'summary': event['before']}
                bound = _validate_resolution(prefix, proof, receipt, event['args']['amount'], receipt['work_artifact_sha256'], event['day'], jobs, native_actions_sha256=prefixes[index])
                if event['args']['artifact_sha256'] != bound:
                    raise ValueError('NATIVE_FINISH_RESOLUTION_COMMITMENT_MISMATCH')
        if event['op'] != 'reserve':
            continue
        proof = proofs.get(event['args']['id'])
        if not isinstance(proof, dict) or digest(proof.get('body')) != event['args']['intent_sha256']:
            raise ValueError('PUBLIC_RESERVATION_INTENT_MISMATCH')
        body = proof['body']
        _selected_contracts(body['plan'], jobs)
        prior_digest = digest({'config': tape['config'], 'actions_sha256': prefixes[index], 'summary': event['before']})
        if body['expected_state_digest'] != prior_digest or body['day'] != event['day']:
            raise ValueError('PUBLIC_RESERVATION_STALE_STATE_OR_TIME')
        expected = action_digest(body['plan'], prior_digest, body['amount_microUSD'], body['expected_net_microUSD'])
        if body['authorized_digest'] != expected or body['plan']['plan_id'] != event['args']['id'] or body['amount_microUSD'] != event['args']['amount'] or body['expected_net_microUSD'] != event['args']['expected_net_value']:
            raise ValueError('PUBLIC_AUTHORIZED_ACTION_MISMATCH')
    return {**checked, 'state_bound_reservations': sum(e['op'] == 'reserve' for e in tape['actions']),
            'signature_scope': 'Public audit verifies native finance and state/action commitments. Private local HMAC authenticity is checked only by the account owner.'}


def _account_locked(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._mutex:
            return method(self, *args, **kwargs)
    return call


class Account:
    """One owned account; every mutation is executed by native TapeExchange."""
    def __init__(self, root, manifest, path, *, opening, working=0, contract='adaptive012', storage='local_posix', source_upgrade=None):
        self.path = Path(path).absolute()
        self.root, self.manifest = Path(root).absolute(), copy.deepcopy(manifest)
        self._initial_source_upgrade = copy.deepcopy(source_upgrade)
        self.filesystem = assert_local_storage(self.path, storage)
        self._closed, self._owner = False, None
        self._mutex = threading.RLock()
        self._proofs_path = self.path.with_name(self.path.name + '.adaptive-proofs.json')
        self._resolutions_path = self.path.with_name(self.path.name + '.adaptive-resolutions.json')
        self._key_path = self.path.with_name(self.path.name + '.adaptive-simulation-key')
        self._transitions_path = self.path.with_name(self.path.name + '.adaptive-source-transitions.json')
        self._source_marker_path = self.path.with_name(self.path.name + '.adaptive-connected-source.json')
        self._connected_source_bound = False
        try:
            self._owner = SingleWriterExchange(self.path, root=self.root, manifest=self.manifest,
                                               opening=opening, working=working, contract=contract,
                                               durable=True, _account_namespace=NAMESPACE,
                                               _account_capability=_ADAPTIVE_ACCOUNT_CAPABILITY)
            self._key = self._load_key()
            self._proofs = self._load_proofs()
            self._resolutions = self._load_resolutions()
            self._source_transitions = self._load_source_transitions()
            if self._source_marker_path.exists():
                info = self._source_marker_path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 1_000_000:
                    raise ValueError('BOUNDED_REGULAR_CONNECTED_SOURCE_MARKER_REQUIRED')
                marker = strict_json(self._source_marker_path.read_bytes())
                if not isinstance(marker, dict) or set(marker) != {'body', 'signature'} or not isinstance(marker['body'], dict):
                    raise ValueError('EXACT_CONNECTED_SOURCE_MARKER_REQUIRED')
                expected = hmac.new(self._key, b'connected-source-required\n' + canonical(marker['body']), hashlib.sha256).hexdigest()
                if marker['body'].get('account_path') != str(self.path) or not hmac.compare_digest(expected, str(marker.get('signature'))):
                    raise ValueError('CONNECTED_SOURCE_MARKER_SIGNATURE_MISMATCH')
                self._connected_source_bound = True
            self._verify_reservations()
            if any(e['op'] == 'finish' and _requires_resolution(self._proofs.get(e['args']['id'], {}).get('body', {}).get('plan', {})) for e in self._owner.export()['actions']):
                audit_account(self.export(), root=self.root, manifest=self.manifest,
                              pending_source_transition=self._pending_source_transition())
        except BaseException:
            self.close()
            raise

    def _assert_owner(self):
        if self._closed or self._owner is None:
            raise ValueError('ADAPTIVE_ACCOUNT_CLOSED')
        self._owner.lease.assert_owner()

    def _pending_source_transition(self):
        ticket = self._initial_source_upgrade
        if ticket is None:
            path = self.path.with_name(self.path.name + '.connected-journal.json')
            if not path.exists():
                return None
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 64_000_000:
                raise ValueError('REGULAR_BOUNDED_SOURCE_PREFLIGHT_JOURNAL_REQUIRED')
            envelope = strict_json(path.read_bytes()); body = envelope['body']
            signature = hmac.new(self._key, b'connected014-journal\n' + canonical(body), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(str(envelope.get('signature')), signature):
                raise ValueError('SOURCE_PREFLIGHT_JOURNAL_SIGNATURE_MISMATCH')
            history = body.get('source_history', [])
            if not history:
                return None
            ticket = history[-1]
        from connected_enterprise.upgrades import validate_ticket
        body = validate_ticket(ticket, key=self._key, root=self.root, path=self.path)
        tape = self._owner.export()
        if any(e['op'] == 'source_transition' and e['args']['id'] == body['id'] for e in tape['actions']):
            return None
        if body['prior_record']['ledger'] != tape:
            raise ValueError('STALE_PENDING_SOURCE_TRANSITION_PREFLIGHT')
        return ticket

    def _assert_source_write(self):
        journal_path = self.path.with_name(self.path.name + '.connected-journal.json')
        if not journal_path.exists():
            if self._connected_source_bound or self._source_transitions:
                raise ValueError('EXISTING_CONNECTED_SOURCE_AUTHORITY_MISSING')
            return
        if journal_path.is_symlink() or not journal_path.is_file():
            raise ValueError('REGULAR_CONNECTED_SOURCE_AUTHORITY_REQUIRED')
        envelope = strict_json(journal_path.read_bytes())
        body = envelope['body']
        expected = hmac.new(self._key, b'connected014-journal\n' + canonical(body), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(str(envelope.get('signature')), expected):
            raise ValueError('CONNECTED_SOURCE_AUTHORITY_SIGNATURE_MISMATCH')
        from connected_enterprise.finance import source_identity
        if body['source'] != source_identity(self.root):
            raise ValueError('EXPLICIT_AUTHENTICATED_SOURCE_UPGRADE_REQUIRED')
        history = body.get('source_history', [])
        if history:
            ident = history[-1]['body']['id']
            if not any(e['op'] == 'source_transition' and e['args']['id'] == ident for e in self._owner.export()['actions']):
                raise ValueError('PENDING_SOURCE_TRANSITION_MUST_RECOVER_FIRST')

    def bind_connected_source(self, envelope):
        self._assert_owner()
        expected = hmac.new(self._key, b'connected014-journal\n' + canonical(envelope['body']), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, str(envelope.get('signature'))):
            raise ValueError('CONNECTED_SOURCE_AUTHORITY_SIGNATURE_MISMATCH')
        if not self._connected_source_bound:
            body = {'schema': 'agi-alpha/connected-source-required/v1', 'account_path': str(self.path),
                    'initial_source': envelope['body']['source']}
            signature = hmac.new(self._key, b'connected-source-required\n' + canonical(body), hashlib.sha256).hexdigest()
            atomic_bytes(self._source_marker_path, canonical({'body': body, 'signature': signature}) + b'\n')
            self._connected_source_bound = True

    def _load_key(self):
        if self._key_path.exists():
            info = self._key_path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) & 0o077:
                raise ValueError('PRIVATE_REGULAR_SIMULATION_KEY_REQUIRED')
            key = self._key_path.read_bytes()
            if len(key) != 32:
                raise ValueError('SIMULATION_KEY_LENGTH_MISMATCH')
            return key
        if self._owner.export()['actions']:
            raise ValueError('EXISTING_ACCOUNT_SIGNING_KEY_MISSING')
        key = os.urandom(32)
        with self._key_path.open('xb') as stream:
            os.chmod(self._key_path, 0o600)
            stream.write(key); stream.flush(); os.fsync(stream.fileno())
        return key

    def _load_proofs(self):
        if not self._proofs_path.exists():
            return {}
        if self._proofs_path.is_symlink() or not self._proofs_path.is_file():
            raise ValueError('REGULAR_ACTION_PROOF_RECORD_REQUIRED')
        raw = self._proofs_path.read_bytes()
        if len(raw) > 32_000_000:
            raise ValueError('BOUNDED_ACTION_PROOFS_REQUIRED')
        records = strict_json(raw)
        if not isinstance(records, dict):
            raise ValueError('ACTION_PROOF_MAP_REQUIRED')
        for ident, record in records.items():
            if not isinstance(record, dict) or record.get('body', {}).get('plan', {}).get('plan_id') != ident:
                raise ValueError('ACTION_PROOF_IDENTITY_MISMATCH')
            signature = hmac.new(self._key, canonical(record['body']), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, str(record.get('signature', ''))):
                raise ValueError('ACTION_SIGNATURE_MISMATCH')
        return records

    def _load_resolutions(self):
        if not self._resolutions_path.exists():
            return {}
        if self._resolutions_path.is_symlink() or not self._resolutions_path.is_file():
            raise ValueError('REGULAR_OBLIGATION_RESOLUTION_RECORD_REQUIRED')
        raw = self._resolutions_path.read_bytes()
        if len(raw) > 32_000_000:
            raise ValueError('BOUNDED_OBLIGATION_RESOLUTIONS_REQUIRED')
        records = strict_json(raw)
        if not isinstance(records, dict):
            raise ValueError('OBLIGATION_RESOLUTION_MAP_REQUIRED')
        return records

    def _load_source_transitions(self):
        if not self._transitions_path.exists():
            return {}
        if self._transitions_path.is_symlink() or not self._transitions_path.is_file():
            raise ValueError('REGULAR_SOURCE_AUTHORIZATION_RECORD_REQUIRED')
        records = strict_json(self._transitions_path.read_bytes())
        if not isinstance(records, dict) or len(canonical(records)) > 32_000_000:
            raise ValueError('BOUNDED_SOURCE_AUTHORIZATION_MAP_REQUIRED')
        from connected_enterprise.upgrades import validate_ticket
        for ident, ticket in records.items():
            body = validate_ticket(ticket, key=self._key, path=self.path)
            if body['id'] != ident:
                raise ValueError('SOURCE_AUTHORIZATION_ID_CHANGED')
        return records

    def _verify_reservations(self):
        for event in self._owner.export()['actions']:
            if event['op'] == 'source_transition':
                from connected_enterprise.upgrades import transition_args
                ticket = self._source_transitions.get(event['args']['id'])
                if ticket is None or transition_args(ticket) != event['args'] or ticket['body']['day'] != event['day']:
                    raise ValueError('NATIVE_SOURCE_TRANSITION_AUTHORIZATION_MISSING')
            if event['op'] == 'cancel_investment':
                raise ValueError('UNRECONCILED_INVESTMENT_CANCELLATION_RETIRED')
            if event['op'] == 'finish':
                proof = self._proofs.get(event['args']['id'])
                if proof and _requires_resolution(proof['body']['plan']) and event['args']['id'] not in self._resolutions:
                    raise ValueError('FINISHED_RESOURCE_OBLIGATION_RECEIPT_MISSING')
            if event['op'] != 'reserve':
                continue
            proof = self._proofs.get(event['args']['id'])
            if proof is None or digest(proof.get('body')) != event['args']['intent_sha256']:
                raise ValueError('NATIVE_RESERVATION_PROOF_MISSING_OR_CHANGED')
            body = proof['body']
            _selected_contracts(body['plan'], self._owner._exchange.jobs)
            if body['amount_microUSD'] != event['args']['amount'] or body['expected_net_microUSD'] != event['args']['expected_net_value']:
                raise ValueError('NATIVE_RESERVATION_AMOUNT_PROOF_MISMATCH')

    @_account_locked
    def snapshot(self):
        self._assert_owner()
        tape = self._owner.export()
        return {'summary': copy.deepcopy(tape['summary']),
                'state_digest': digest({'config': tape['config'], 'actions_sha256': tape['actions_sha256'], 'summary': tape['summary']}),
                'actions_sha256': tape['actions_sha256'], 'sequence': len(tape['actions']),
                'scope': 'SIMULATED', 'ownership': 'MANDATORY_SINGLE_LOCAL_POSIX_WRITER',
                'filesystem': self.filesystem}

    def _prior(self, op, args, day):
        ident = _operation_id(op, args)
        matches = [e for e in self._owner.export()['actions'] if _operation_id(e['op'], e['args']) == ident]
        if matches:
            event = matches[-1]
            if event['op'] != op or event['args'] != args or event['day'] != day:
                raise ValueError('IDEMPOTENT_ACTION_PAYLOAD_CHANGED')
            return event
        return None

    @_account_locked
    def execute(self, op, args, day):
        self._assert_owner()
        self._assert_source_write()
        if op == 'source_transition':
            raise ValueError('AUTHENTICATED_SOURCE_TRANSITION_ENTRYPOINT_REQUIRED')
        if op == 'cancel_investment':
            raise ValueError('UNRECONCILED_INVESTMENT_CANCELLATION_RETIRED')
        if op == 'reserve':
            raise ValueError('STATE_BOUND_RESERVE_ENTRYPOINT_REQUIRED')
        if op == 'finish' and _requires_resolution(self._proofs.get(args.get('id'), {}).get('body', {}).get('plan', {})):
            raise ValueError('OBLIGATION_AWARE_FINISH_ENTRYPOINT_REQUIRED')
        args = copy.deepcopy(args)
        if self._prior(op, args, day) is None:
            self._owner.execute(op, args, day)
        return self.snapshot()

    @_account_locked
    def reserve(self, plan, *, expected_state_digest, authorized_digest, amount, expected_net, day):
        self._assert_owner()
        self._assert_source_write()
        expected = action_digest(plan, expected_state_digest, amount, expected_net)
        if not _hex(authorized_digest) or not hmac.compare_digest(expected, authorized_digest):
            raise ValueError('AUTHORIZED_ACTION_DIGEST_MISMATCH')
        if plan.get('expected_state_digest', expected_state_digest) != expected_state_digest or plan.get('authorized_digest', authorized_digest) != authorized_digest:
            raise ValueError('PLAN_STATE_OR_AUTHORIZATION_MISMATCH')
        _selected_contracts(plan, self._owner._exchange.jobs)
        body = {'schema': PROOF_SCHEMA, 'scope': 'SIMULATED_LOCAL_INTEGRITY_ONLY',
                'plan': {k: copy.deepcopy(v) for k, v in plan.items() if k not in {'authorized_digest', 'expected_state_digest'}},
                'expected_state_digest': expected_state_digest, 'authorized_digest': authorized_digest,
                'amount_microUSD': amount, 'expected_net_microUSD': expected_net, 'day': day}
        proof = {'body': body, 'signature': hmac.new(self._key, canonical(body), hashlib.sha256).hexdigest(),
                 'signature_scope': 'Local simulation-only HMAC; not external credentials or financial authority.'}
        ident = plan['plan_id']
        if any(p['body']['plan']['action_id'] == plan['action_id'] and name != ident for name, p in self._proofs.items()):
            raise ValueError('ACTION_IDENTIFIER_ALREADY_BOUND_TO_ANOTHER_PLAN')
        args = {'id': ident, 'amount': amount, 'expected_net_value': expected_net, 'intent_sha256': digest(body)}
        if self._prior('reserve', args, day) is not None:
            if self._proofs.get(ident) != proof:
                raise ValueError('IDEMPOTENT_RESERVATION_PROOF_CHANGED')
            return self.snapshot()
        if self.snapshot()['state_digest'] != expected_state_digest:
            raise ValueError('STALE_NATIVE_ACCOUNT_STATE')
        if ident in self._proofs and self._proofs[ident] != proof:
            raise ValueError('PLAN_IDENTIFIER_PROOF_COLLISION')
        new_proof = ident not in self._proofs
        native_before = copy.deepcopy(self._owner.export())
        exchange = self._owner._exchange
        last_day_before = exchange.last_day
        persistence = exchange.persistence
        durable_before = persistence.tape.read_bytes() if persistence is not None else None
        self._proofs[ident] = proof
        atomic_bytes(self._proofs_path, canonical(self._proofs) + b'\n')
        try:
            self._owner.execute('reserve', args, day)
        except ValueError:
            self._assert_owner()
            if (new_proof and persistence is not None and not persistence.failed
                    and ident not in self._resolutions
                    and exchange.last_day == last_day_before
                    and self._owner.export() == native_before
                    and persistence.tape.read_bytes() == durable_before):
                del self._proofs[ident]
                try:
                    atomic_bytes(self._proofs_path, canonical(self._proofs) + b'\n')
                except BaseException:
                    self._proofs[ident] = proof
                    raise
            raise
        return self.snapshot()

    @_account_locked
    def finish(self, ident, amount, artifact_sha256, day, *, obligation_receipt=None):
        self._assert_owner()
        self._assert_source_write()
        proof = self._proofs.get(ident)
        if proof and _requires_resolution(proof['body']['plan']):
            if obligation_receipt is None:
                raise ValueError('SOURCE_BOUND_OBLIGATION_RESOLUTION_REQUIRED_BEFORE_FINISH')
            bound = digest({'work_artifact_sha256': artifact_sha256, 'obligation_receipt_sha256': digest(obligation_receipt)})
            args = {'id': ident, 'amount': amount, 'artifact_sha256': bound}
            if self._prior('finish', args, day) is not None:
                if self._resolutions.get(ident) != obligation_receipt:
                    raise ValueError('IDEMPOTENT_OBLIGATION_RESOLUTION_CHANGED')
                return self.snapshot()
            _validate_resolution(self._owner.export(), proof, obligation_receipt, amount, artifact_sha256, day, self._owner._exchange.jobs)
            self._resolutions[ident] = copy.deepcopy(obligation_receipt)
            atomic_bytes(self._resolutions_path, canonical(self._resolutions) + b'\n')
            self._owner.execute('finish', args, day)
            return self.snapshot()
        return self.execute('finish', {'id': ident, 'amount': amount, 'artifact_sha256': artifact_sha256}, day)

    def cost(self, ident, amount, day):
        return self.execute('cost', {'id': ident, 'amount': amount}, day)

    @_account_locked
    def source_transition(self, ticket):
        self._assert_owner()
        from connected_enterprise.upgrades import validate_ticket, transition_args, verify_historical
        body = validate_ticket(ticket, key=self._key, root=self.root, path=self.path)
        args = transition_args(ticket)
        prior = self._prior('source_transition', args, body['day'])
        if prior is not None:
            if self._source_transitions.get(body['id']) != ticket:
                raise ValueError('SOURCE_TRANSITION_RETRY_CHANGED')
            return self.snapshot()
        tape = self._owner.export()
        committed = [e for e in tape['actions'] if e['op'] == 'source_transition']
        if body['counter'] != len(committed) + 1 or tape != body['prior_record']['ledger']:
            raise ValueError('STALE_SOURCE_TRANSITION_OR_FORK')
        if self.snapshot()['state_digest'] != body['expected_state_digest']:
            raise ValueError('STALE_SOURCE_TRANSITION_CHECKPOINT')
        if committed:
            latest = self._source_transitions[committed[-1]['args']['id']]['body']
            previous = {t['body']['from_source']['sha256'] for t in self._source_transitions.values()}
            if body['from_source'] != latest['to_source'] or body['to_source']['sha256'] in previous:
                raise ValueError('SOURCE_TRANSITION_DOWNGRADE_OR_FORK')
        original = body['prior_envelope']
        signed = hmac.new(self._key, b'connected014-journal\n' + canonical(original['body']), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signed, str(original['signature'])):
            raise ValueError('ORIGINAL_SOURCE_ENVELOPE_SIGNATURE_MISMATCH')
        verify_historical(ticket, self.manifest, root=self.root)
        if body['id'] in self._source_transitions and self._source_transitions[body['id']] != ticket:
            raise ValueError('SOURCE_TRANSITION_AUTHORIZATION_COLLISION')
        proposed={**self._source_transitions,body['id']:copy.deepcopy(ticket)}
        raw=canonical(proposed)
        if len(raw)>32_000_000:raise ValueError('BOUNDED_SOURCE_TRANSITIONS_REQUIRED')
        atomic_bytes(self._transitions_path,raw+b'\n')
        self._source_transitions=proposed
        self._owner.execute('source_transition', args, body['day'])
        return self.snapshot()

    @_account_locked
    def export(self):
        self._assert_owner()
        self._verify_reservations()
        return {'schema': 'agi-alpha/adaptive012-owned-account/v1', 'scope': 'SIMULATED',
                'ledger': self._owner.export(), 'snapshot': self.snapshot(),
                'action_proofs': copy.deepcopy(self._proofs),
                'obligation_resolutions': copy.deepcopy(self._resolutions),
                **({'source_transitions': copy.deepcopy(self._source_transitions)} if self._source_transitions else {}),
                'signature_verification': 'Verified with private local simulation key by owning process; exported proof is not externally certified.',
                'storage_scope': 'Operator-owned local POSIX filesystem only; distributed, NFS, aliases and hostile-host guarantees unsupported.'}

    def audit(self):
        self._assert_owner()
        self._verify_reservations()
        return audit_account(self.export(), root=self.root, manifest=self.manifest)

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._owner is not None:
            self._owner.close()

    def __enter__(self):
        self._assert_owner()
        return self

    def __exit__(self, *exc):
        self.close()
